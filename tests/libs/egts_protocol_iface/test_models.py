"""Тесты на dataclass-модели EGTS: Packet, Record, Subrecord, ParseResult

Все тестовые методы имеют явную аннотацию -> None для mypy.
"""

from libs.egts_protocol_iface.models import Packet, ParseResult, Record, Subrecord


class TestPacket:
    """Тесты на dataclass Packet (транспортный уровень)"""

    def test_create_minimal_packet(self) -> None:
        """Минимальный пакет — только обязательные поля"""
        pkt = Packet(packet_id=1, packet_type=1)

        assert pkt.packet_id == 1
        assert pkt.packet_type == 1
        assert pkt.priority == 0
        assert pkt.records == []
        assert pkt.response_packet_id is None
        assert pkt.processing_result is None
        assert pkt.sender_address is None
        assert pkt.receiver_address is None
        assert pkt.ttl is None
        assert pkt.skid == 0
        assert pkt.raw_bytes == b""
        assert pkt.prf is False
        assert pkt.rte is False
        assert pkt.ena is False
        assert pkt.cmp is False
        assert pkt.crc8_valid is None
        assert pkt.crc16_valid is None
        assert pkt.extra == {}

    def test_create_response_packet(self) -> None:
        """RESPONSE-пакет с RPID и processing_result"""
        pkt = Packet(
            packet_id=2,
            packet_type=0,
            response_packet_id=1,
            processing_result=0,
        )

        assert pkt.packet_type == 0
        assert pkt.response_packet_id == 1
        assert pkt.processing_result == 0

    def test_create_packet_with_records(self) -> None:
        """Пакет с записями"""
        rec = Record(record_id=1, service_type=1)
        pkt = Packet(packet_id=1, packet_type=1, records=[rec])

        assert len(pkt.records) == 1
        assert pkt.records[0].record_id == 1

    def test_packet_raw_bytes(self) -> None:
        """raw_bytes хранит сырые данные пакета"""
        raw = b"\x01\x00\x00\x0b\x00\x00\x00\x01\x00\x00\x00"
        pkt = Packet(packet_id=1, packet_type=1, raw_bytes=raw)

        assert pkt.raw_bytes == raw

    def test_packet_crc_valid(self) -> None:
        """crc8_valid/crc16_valid устанавливаются"""
        pkt = Packet(packet_id=1, packet_type=1, crc8_valid=True, crc16_valid=False)

        assert pkt.crc8_valid is True
        assert pkt.crc16_valid is False

    def test_packet_extra(self) -> None:
        """extra dict для расширений"""
        pkt = Packet(packet_id=1, packet_type=1, extra={"gost": "2023"})

        assert pkt.extra["gost"] == "2023"

    def test_packet_pr_flags(self) -> None:
        """pr_flags собирает флаги в байт"""
        pkt = Packet(
            packet_id=1,
            packet_type=1,
            priority=2,
            prf=True,
            rte=True,
            ena=True,
            cmp=True,
        )
        flags = pkt.pr_flags

        assert flags & 0x80  # PRF
        assert flags & 0x40  # RTE
        assert flags & 0x20  # ENA
        assert flags & 0x10  # CMP
        assert (flags >> 2) & 0x03 == 2  # PR


class TestRecord:
    """Тесты на dataclass Record (сервисный уровень)"""

    def test_create_minimal_record(self) -> None:
        """Минимальная запись — только обязательные поля"""
        rec = Record(record_id=1, service_type=1)

        assert rec.record_id == 1
        assert rec.service_type == 1
        assert rec.subrecords == []
        assert rec.object_id is None
        assert rec.event_id is None
        assert rec.timestamp is None
        assert rec.rst_service_type == 0
        assert rec.first_record is False
        assert rec.last_record is False
        assert rec.ongoing_record is False
        assert rec.parse_error is None
        assert rec.extra == {}
        assert rec._raw_data == b""

    def test_record_rf_flags(self) -> None:
        """rf_flags собирает флаги RFL согласно ГОСТ 33465 таблица 14.

        Биты RFL:
        - 7: SSOD (Source Service On Device)
        - 6: RSOD (Recipient Service On Device)
        - 5-3: RPP (Record Processing Priority)
        - 2: TMFE (Time Field Exists)
        - 1: EVFE (Event ID Field Exists)
        - 0: OBFE (Object ID Field Exists)
        """
        # Базовый случай — все false
        rec = Record(record_id=1, service_type=1)
        flags = rec.rf_flags
        assert flags == 0

        # SSOD/RSOD
        rec_ssod = Record(record_id=1, service_type=1, ssod=True, rsod=True)
        flags_ssod = rec_ssod.rf_flags
        assert flags_ssod & 0x80  # SSOD
        assert flags_ssod & 0x40  # RSOD

        # RPP
        rec_rpp = Record(record_id=1, service_type=1, rpp=5)
        flags_rpp = rec_rpp.rf_flags
        assert (flags_rpp >> 3) & 0x07 == 5  # RPP в битах 5-3

        # TMFE (timestamp != None)
        rec_tm = Record(record_id=1, service_type=1, timestamp=12345)
        flags_tm = rec_tm.rf_flags
        assert flags_tm & 0x04  # TMFE

        # EVFE (event_id != None)
        rec_ev = Record(record_id=1, service_type=1, event_id=42)
        flags_ev = rec_ev.rf_flags
        assert flags_ev & 0x02  # EVFE

        # OBFE (object_id != None)
        rec_ob = Record(record_id=1, service_type=1, object_id=100)
        flags_ob = rec_ob.rf_flags
        assert flags_ob & 0x01  # OBFE

    def test_record_parse_error(self) -> None:
        """parse_error сохраняется"""
        rec = Record(record_id=1, service_type=1, parse_error="unknown subrecord")

        assert rec.parse_error == "unknown subrecord"

    def test_record_extra(self) -> None:
        """extra dict для расширений"""
        rec = Record(record_id=1, service_type=1, extra={"new_field": 42})

        assert rec.extra["new_field"] == 42

    def test_record_raw_data_is_internal(self) -> None:
        """_raw_data — внутреннее поле, не в __init__"""
        rec = Record(record_id=1, service_type=1)

        assert rec._raw_data == b""

        rec._raw_data = b"\x00\x01\x02"
        assert rec._raw_data == b"\x00\x01\x02"


class TestSubrecord:
    """Тесты на dataclass Subrecord"""

    def test_create_minimal_subrecord(self) -> None:
        """Минимальная подзапись"""
        sub = Subrecord(subrecord_type=1, data=b"\x00")

        assert sub.subrecord_type == 1
        assert sub.data == b"\x00"
        assert sub.raw_data == b""
        assert sub.parse_error is None
        assert sub.extra == {}

    def test_subrecord_parse_error(self) -> None:
        """parse_error сохраняется"""
        sub = Subrecord(
            subrecord_type=99,
            data=None,
            parse_error="unknown subrecord type",
        )

        assert sub.parse_error == "unknown subrecord type"

    def test_subrecord_extra(self) -> None:
        """extra dict для расширений"""
        sub = Subrecord(subrecord_type=1, data=b"", extra={"v2_field": "data"})

        assert sub.extra["v2_field"] == "data"


class TestParseResult:
    """Тесты на dataclass ParseResult"""

    def test_create_empty_result(self) -> None:
        """Пустой результат парсинга"""
        result = ParseResult()

        assert result.packet is None
        assert result.errors == []
        assert result.warnings == []
        assert result.raw_bytes == b""
        assert result.is_success is False
        assert result.is_valid is False
        assert result.is_partial is False

    def test_create_result_with_packet(self) -> None:
        """Результат с пакетом"""
        pkt = Packet(packet_id=1, packet_type=1)
        result = ParseResult(packet=pkt)

        assert result.packet is pkt
        assert result.is_success is True
        assert result.is_valid is True
        assert result.is_partial is False

    def test_create_result_with_errors(self) -> None:
        """Результат с ошибками — пакет не распарсен"""
        result = ParseResult(
            errors=["CRC-8 error", "CRC-16 error"],
            warnings=["Unknown subrecord type"],
        )

        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.is_success is False
        assert result.is_valid is False
        assert result.is_partial is False

    def test_is_partial(self) -> None:
        """Частичный успех — пакет есть, но с ошибками"""
        result = ParseResult(
            packet=Packet(packet_id=1, packet_type=1),
            errors=["CRC-16 error"],
            warnings=["partial data"],
        )

        assert result.is_success is True
        assert result.is_valid is False
        assert result.is_partial is True

    def test_parse_result_with_raw_bytes(self) -> None:
        """raw_bytes сохраняется"""
        raw = b"\x01\x02\x03\x04"
        result = ParseResult(raw_bytes=raw)

        assert result.raw_bytes == raw
