"""Тесты на адаптер EgtsProtocol2015

Проверка всех методов IEgtsProtocol через конкретную реализацию ГОСТ 2015.
"""

import pytest

from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015
from libs.egts_protocol_gost2015.crc import crc8, crc16, verify_crc8, verify_crc16
from libs.egts_protocol_iface import IEgtsProtocol, create_protocol
from libs.egts_protocol_iface.models import Packet, Record, Subrecord


class TestCRC:
    """Тесты CRC функций (чистая реализация на Python)"""

    def test_crc8_known_vector(self) -> None:
        """CRC-8: полином 0x31, init 0xFF, без отражения."""
        # Для "123456789": CRC-8 = 0xF7 (247)
        assert crc8(b"123456789") == 0xF7

    def test_crc16_known_vector(self) -> None:
        """CRC-16 CCITT для известного вектора."""
        # "123456789" → CRC-16 CCITT = 0x29B1
        assert crc16(b"123456789") == 0x29B1

    def test_crc8_empty(self) -> None:
        """CRC-8 пустых данных = init value."""
        assert crc8(b"") == 0xFF

    def test_crc16_empty(self) -> None:
        """CRC-16 пустых данных = init value."""
        assert crc16(b"") == 0xFFFF

    def test_verify_crc8_valid(self) -> None:
        """verify_crc8 — корректный CRC."""
        data = b"test"
        assert verify_crc8(data, crc8(data)) is True

    def test_verify_crc8_invalid(self) -> None:
        """verify_crc8 — некорректный CRC."""
        assert verify_crc8(b"test", 0x00) is False

    def test_verify_crc16_valid(self) -> None:
        """verify_crc16 — корректный CRC."""
        data = b"test"
        assert verify_crc16(data, crc16(data)) is True

    def test_verify_crc16_invalid(self) -> None:
        """verify_crc16 — некорректный CRC."""
        assert verify_crc16(b"test", 0x0000) is False

    def test_crc8_deterministic(self) -> None:
        """CRC-8 детерминирован — одинаковый результат."""
        assert crc8(b"hello") == crc8(b"hello")

    def test_crc16_deterministic(self) -> None:
        """CRC-16 детерминирован — одинаковый результат."""
        assert crc16(b"hello") == crc16(b"hello")


class TestEgtsProtocol2015:
    """Тесты адаптера EgtsProtocol2015"""

    @pytest.fixture()
    def proto(self) -> EgtsProtocol2015:
        return EgtsProtocol2015()

    def test_version(self, proto: EgtsProtocol2015) -> None:
        assert proto.version == "2015"

    def test_capabilities(self, proto: EgtsProtocol2015) -> None:
        caps = proto.capabilities
        assert "sms_pdu" in caps
        assert "auth" in caps

    def test_parse_empty_data(self, proto: EgtsProtocol2015) -> None:
        result = proto.parse_packet(b"")
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.raw_bytes == b""

    def test_parse_too_short(self, proto: EgtsProtocol2015) -> None:
        result = proto.parse_packet(b"\x00\x01\x02")
        assert result.is_valid is False
        assert len(result.errors) >= 1

    def test_calculate_crc8(self, proto: EgtsProtocol2015) -> None:
        assert proto.calculate_crc8(b"test") == crc8(b"test")

    def test_calculate_crc16(self, proto: EgtsProtocol2015) -> None:
        assert proto.calculate_crc16(b"test") == crc16(b"test")

    def test_validate_crc8(self, proto: EgtsProtocol2015) -> None:
        expected = crc8(b"data")
        assert proto.validate_crc8(b"data", expected) is True
        assert proto.validate_crc8(b"data", 0x00) is False

    def test_validate_crc16(self, proto: EgtsProtocol2015) -> None:
        expected = crc16(b"data")
        assert proto.validate_crc16(b"data", expected) is True
        assert proto.validate_crc16(b"data", 0x0000) is False

    def test_build_response(self, proto: EgtsProtocol2015) -> None:
        resp = proto.build_response(42, 0)
        assert isinstance(resp, bytes)
        assert len(resp) > 0

    def test_build_response_with_rpid(self, proto: EgtsProtocol2015) -> None:
        resp = proto.build_response(10, 0, rpid=20)
        assert isinstance(resp, bytes)
        # RESPONSE должен содержать RPID
        assert len(resp) >= 14  # минимальный размер RESPONSE

    def test_build_record_response(self, proto: EgtsProtocol2015) -> None:
        rr = proto.build_record_response(1, 0)
        assert isinstance(rr, bytes)
        # SRT(1) + SRL(2) + CRN(2) + RST(1) = 6 байт
        assert len(rr) == 6
        assert rr[0] == 0  # SRT = 0 (RECORD_RESPONSE)

    def test_build_packet_roundtrip(self, proto: EgtsProtocol2015) -> None:
        """build_packet → parse_packet → те же поля."""
        pkt = Packet(
            packet_id=1,
            packet_type=1,
            priority=0,
            records=[],
        )
        raw = proto.build_packet(pkt)
        result = proto.parse_packet(raw)
        assert result.is_valid is True
        assert result.packet is not None
        assert result.packet.packet_id == 1
        assert result.packet.packet_type == 1

    def test_roundtrip_with_records(self, proto: EgtsProtocol2015) -> None:
        """Roundtrip с записью и подзаписью."""
        sub = Subrecord(
            subrecord_type=1,
            data=b"\x01\x02\x03\x04",
        )
        rec = Record(
            record_id=5,
            service_type=1,
            subrecords=[sub],
        )
        pkt = Packet(
            packet_id=10,
            packet_type=1,
            priority=0,
            records=[rec],
        )
        raw = proto.build_packet(pkt)
        result = proto.parse_packet(raw)
        assert result.is_valid is True
        assert result.packet is not None
        assert result.packet.packet_id == 10
        assert len(result.packet.records) == 1
        assert result.packet.records[0].record_id == 5

    def test_parse_sms_pdu_raises_on_invalid(self, proto: EgtsProtocol2015) -> None:
        """parse_sms_pdu реализован — бросает ValueError на коротком PDU."""
        with pytest.raises(ValueError, match="Слишком короткие данные"):
            proto.parse_sms_pdu(b"")

    def test_build_sms_pdu(self, proto: EgtsProtocol2015) -> None:
        """build_sms_pdu — реализован (задача 2.4, параллельный агент)."""
        # Метод реализован, проверяем что возвращает bytes
        pdu = proto.build_sms_pdu(b"\x01\x02", "+79001234567")
        assert isinstance(pdu, bytes)
        assert len(pdu) > 0


class TestFactoryIntegration:
    """Тесты factory create_protocol для ГОСТ 2015"""

    def test_create_2015_returns_adapter(self) -> None:
        proto = create_protocol("2015")
        assert isinstance(proto, EgtsProtocol2015)
        assert isinstance(proto, IEgtsProtocol)

    def test_2015_crc_via_factory(self) -> None:
        proto = create_protocol("2015")
        assert proto.calculate_crc8(b"test") == 191
        assert proto.calculate_crc16(b"test") == 8134
