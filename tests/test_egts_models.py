"""Тесты Этапа 1: модели и типы."""

import pytest

from libs.egts.models import Packet, ParseResult, Record, ResponseRecord, Subrecord
from libs.egts.types import PacketType, ResultCode, ServiceType, SubrecordType


class TestTypes:
    """Проверка перечислений."""

    def test_packet_type_values(self):
        assert PacketType.RESPONSE == 0
        assert PacketType.APPDATA == 1
        assert PacketType.SIGNED_APPDATA == 2

    def test_service_type_values(self):
        assert ServiceType.AUTH == 1
        assert ServiceType.TELEDATA == 2
        assert ServiceType.COMMANDS == 4
        assert ServiceType.FIRMWARE == 9
        assert ServiceType.ECALL == 10

    def test_subrecord_type_values(self):
        assert SubrecordType.RECORD_RESPONSE == 0
        assert SubrecordType.TERM_IDENTITY == 1
        assert SubrecordType.MODULE_DATA == 2
        assert SubrecordType.VEHICLE_DATA == 3
        assert SubrecordType.AUTH_PARAMS == 6
        assert SubrecordType.AUTH_INFO == 7
        assert SubrecordType.SERVICE_INFO == 8
        assert SubrecordType.RESULT_CODE == 9
        assert SubrecordType.ACCEL_DATA == 20
        assert SubrecordType.SERVICE_PART_DATA == 33
        assert SubrecordType.SERVICE_FULL_DATA == 34
        assert SubrecordType.COMMAND_DATA == 51
        assert SubrecordType.RAW_MSD_DATA == 62
        assert SubrecordType.TRACK_DATA == 63

    def test_result_code_values(self):
        assert ResultCode.OK == 0
        assert ResultCode.IN_PROGRESS == 1
        assert ResultCode.UNS_PROTOCOL == 128
        assert ResultCode.DECRYPT_ERROR == 129
        assert ResultCode.PROC_DENIED == 130
        assert ResultCode.HEADERCRC_ERROR == 137
        assert ResultCode.DATACRC_ERROR == 138

    def test_result_code_count(self):
        """Все коды из приложения В: 0, 1, 128-154 = 29 кодов."""
        assert len(ResultCode) == 29

    def test_int_enum_behavior(self):
        """IntEnum должен работать как int."""
        assert PacketType.APPDATA == 1
        assert int(PacketType.RESPONSE) == 0
        assert ServiceType.AUTH in {1, 2, 4}


class TestPacket:
    """Проверка модели Packet."""

    def test_defaults(self):
        pkt = Packet(packet_id=1, packet_type=1)
        assert pkt.protocol_version == 1
        assert pkt.security_key_id == 0
        assert pkt.prefix is False
        assert pkt.routing is False
        assert pkt.encryption == 0
        assert pkt.compressed is False
        assert pkt.priority == 0
        assert pkt.header_encoding == 0
        assert pkt.packet_id == 1
        assert pkt.packet_type == 1
        assert pkt.peer_address is None
        assert pkt.recipient_address is None
        assert pkt.ttl is None
        assert pkt.response_packet_id is None
        assert pkt.processing_result is None
        assert pkt.signature_data is None
        assert pkt.records == []
        assert pkt.header_length == 11
        assert pkt.raw_bytes == b""

    def test_with_records(self):
        sub = Subrecord(subrecord_type=9, data={"rcd": 0})
        rec = Record(record_id=1, service_type=1, subrecords=[sub])
        pkt = Packet(packet_id=42, packet_type=1, records=[rec])
        assert len(pkt.records) == 1
        assert pkt.records[0].subrecords[0].subrecord_type == 9

    def test_response_packet(self):
        pkt = Packet(
            packet_id=100,
            packet_type=0,
            response_packet_id=42,
            processing_result=0,
        )
        assert pkt.packet_type == 0
        assert pkt.response_packet_id == 42
        assert pkt.processing_result == 0

    def test_raw_bytes_stored(self):
        raw = bytes([0x01, 0x00, 0x00, 0x0B, 0x00])
        pkt = Packet(packet_id=1, packet_type=1, raw_bytes=raw)
        assert pkt.raw_bytes == raw


class TestRecord:
    """Проверка модели Record."""

    def test_defaults(self):
        rec = Record(record_id=1, service_type=1)
        assert rec.record_id == 1
        assert rec.service_type == 1
        assert rec.recipient_service_type == 0
        assert rec.subrecords == []
        assert rec.object_id is None
        assert rec.event_id is None
        assert rec.timestamp is None
        assert rec.ssod is False
        assert rec.rsod is False
        assert rec.rpp == 0

    def test_with_optional_fields(self):
        rec = Record(
            record_id=2,
            service_type=2,
            object_id=12345,
            event_id=1,
            timestamp=1000000,
            ssod=True,
            rsod=False,
            rpp=3,
        )
        assert rec.object_id == 12345
        assert rec.event_id == 1
        assert rec.timestamp == 1000000
        assert rec.ssod is True
        assert rec.rpp == 3


class TestSubrecord:
    """Проверка модели Subrecord."""

    def test_defaults(self):
        sr = Subrecord(subrecord_type=9)
        assert sr.subrecord_type == 9
        assert sr.data == {}
        assert sr.raw_bytes == b""
        assert sr.parse_error is None

    def test_dict_data(self):
        sr = Subrecord(subrecord_type=9, data={"rcd": 0})
        assert isinstance(sr.data, dict)
        assert sr.data["rcd"] == 0

    def test_bytes_data(self):
        raw = bytes([0xDE, 0xAD])
        sr = Subrecord(subrecord_type=62, data=raw)
        assert isinstance(sr.data, bytes)
        assert sr.data == raw

    def test_raw_bytes_stored(self):
        raw = bytes([0x09, 0x00, 0x00])
        sr = Subrecord(subrecord_type=9, data={"rcd": 0}, raw_bytes=raw)
        assert sr.raw_bytes == raw


class TestParseResult:
    """Проверка модели ParseResult."""

    def test_success(self):
        pkt = Packet(packet_id=1, packet_type=1)
        result = ParseResult(packet=pkt)
        assert result.is_success
        assert not result.errors
        assert not result.warnings

    def test_with_errors(self):
        result = ParseResult(packet=None, errors=["CRC-8 error"])
        assert not result.is_success
        assert len(result.errors) == 1

    def test_with_warnings(self):
        pkt = Packet(packet_id=1, packet_type=1)
        result = ParseResult(packet=pkt, warnings=["Unknown SRT=99"])
        assert result.is_success
        assert len(result.warnings) == 1

    def test_frozen(self):
        """ParseResult должен быть неизменяемым."""
        pkt = Packet(packet_id=1)
        result = ParseResult(packet=pkt)
        with pytest.raises(Exception):  # FrozenInstanceError или AttributeError
            result.packet = None


class TestResponseRecord:
    """Проверка модели ResponseRecord."""

    def test_defaults(self):
        rr = ResponseRecord(rn=1, service=1, subrecords=[])
        assert rr.rn == 1
        assert rr.service == 1
        assert rr.rsod is True  # По умолчанию True

    def test_custom_rsod(self):
        rr = ResponseRecord(rn=1, service=1, subrecords=[], rsod=False)
        assert rr.rsod is False
