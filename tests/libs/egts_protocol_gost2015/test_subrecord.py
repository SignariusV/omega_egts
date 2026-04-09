"""Тесты на подзапись уровня ППУ EGTS (ГОСТ 33465-2015, раздел 6.6.3)

Покрывает:
- Сборку подзаписей (to_bytes)
- Парсинг подзаписей (from_bytes)
- parse_subrecords / serialize_subrecords
- Краевые случаи (max SRL, large data)
"""

import pytest

from libs.egts_protocol_gost2015.gost2015_impl.subrecord import (
    Subrecord,
    parse_subrecords,
    serialize_subrecords,
)
from libs.egts_protocol_gost2015.gost2015_impl.types import (
    SUBRECORD_HEADER_SIZE,
    SubrecordType,
)


class TestSubrecordBuild:
    """Тесты на сборку подзаписей"""

    def test_subrecord_build_minimal(self) -> None:
        """Сборка минимальной подзаписи без данных"""
        subrecord = Subrecord(subrecord_type=SubrecordType.EGTS_SR_TERM_IDENTITY)
        raw = subrecord.to_bytes()

        assert len(raw) == SUBRECORD_HEADER_SIZE
        assert isinstance(raw, bytes)

    def test_subrecord_build_with_data(self) -> None:
        """Сборка подзаписи с данными"""
        subrecord = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_MODULE_DATA,
            data=b"\x01\x02\x03\x04",
        )
        raw = subrecord.to_bytes()

        assert len(raw) == 7  # SRT(1) + SRL(2) + SRD(4)
        assert raw[0] == SubrecordType.EGTS_SR_MODULE_DATA
        assert int.from_bytes(raw[1:3], "little") == 4

    def test_subrecord_build_with_bytes_data(self) -> None:
        """Сборка подзаписи с bytes данными"""
        subrecord = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_VEHICLE_DATA,
            data=b"\xde\xad\xbe\xef",
        )
        raw = subrecord.to_bytes()
        assert raw[0] == SubrecordType.EGTS_SR_VEHICLE_DATA
        assert raw[1:3] == b"\x04\x00"
        assert raw[3:] == b"\xde\xad\xbe\xef"


class TestSubrecordParse:
    """Тесты на парсинг подзаписей"""

    def test_subrecord_parse_minimal(self) -> None:
        """Парсинг минимальной подзаписи"""
        raw = bytes([SubrecordType.EGTS_SR_TERM_IDENTITY, 0x00, 0x00])
        subrecord = Subrecord.from_bytes(raw)

        assert subrecord.subrecord_type == SubrecordType.EGTS_SR_TERM_IDENTITY
        assert subrecord.data == b""

    def test_subrecord_parse_with_data(self) -> None:
        """Парсинг подзаписи с данными"""
        raw = bytes([
            SubrecordType.EGTS_SR_MODULE_DATA, 0x04, 0x00,
            0xAA, 0xBB, 0xCC, 0xDD,
        ])
        subrecord = Subrecord.from_bytes(raw)

        assert subrecord.subrecord_type == SubrecordType.EGTS_SR_MODULE_DATA
        assert len(subrecord.data) == 4
        assert subrecord.data == b"\xaa\xbb\xcc\xdd"

    def test_subrecord_parse_roundtrip(self) -> None:
        """Круговой тест: сборка → парсинг → сверка"""
        original = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_AUTH_PARAMS,
            data=b"\x01\x02\x03\x04\x05",
        )
        raw = original.to_bytes()
        parsed = Subrecord.from_bytes(raw)

        assert parsed.subrecord_type == SubrecordType.EGTS_SR_AUTH_PARAMS
        assert parsed.data == b"\x01\x02\x03\x04\x05"


class TestParseSubrecords:
    """Тесты на парсинг списка подзаписей"""

    def test_parse_single_subrecord(self) -> None:
        """Парсинг одной подзаписи"""
        data = bytes([
            SubrecordType.EGTS_SR_TERM_IDENTITY, 0x02, 0x00,
            0xAA, 0xBB,
        ])
        subrecords = parse_subrecords(data, service_type=1)

        assert len(subrecords) == 1
        assert subrecords[0].subrecord_type == SubrecordType.EGTS_SR_TERM_IDENTITY
        assert subrecords[0].data == b"\xaa\xbb"

    def test_parse_multiple_subrecords(self) -> None:
        """Парсинг нескольких подзаписей"""
        data = bytes([
            SubrecordType.EGTS_SR_TERM_IDENTITY, 0x02, 0x00, 0xAA, 0xBB,
            SubrecordType.EGTS_SR_MODULE_DATA, 0x01, 0x00, 0xCC,
        ])
        subrecords = parse_subrecords(data, service_type=1)

        assert len(subrecords) == 2
        assert subrecords[0].subrecord_type == SubrecordType.EGTS_SR_TERM_IDENTITY
        assert subrecords[0].data == b"\xaa\xbb"
        assert subrecords[1].subrecord_type == SubrecordType.EGTS_SR_MODULE_DATA
        assert subrecords[1].data == b"\xcc"

    def test_parse_empty_data(self) -> None:
        """Парсинг пустых данных"""
        subrecords = parse_subrecords(b"", service_type=1)
        assert len(subrecords) == 0

    def test_parse_incomplete_subrecord(self) -> None:
        """Парсинг неполной подзаписи вызывает ValueError"""
        data = bytes([SubrecordType.EGTS_SR_TERM_IDENTITY, 0x02])
        with pytest.raises(ValueError, match="Недостаточно данных"):
            parse_subrecords(data, service_type=1)


class TestSerializeSubrecords:
    """Тесты на сериализацию списка подзаписей"""

    def test_serialize_single_subrecord(self) -> None:
        """Сериализация одной подзаписи"""
        subrecord = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_TERM_IDENTITY,
            data=b"\xaa\xbb",
        )
        data = serialize_subrecords([subrecord])

        assert data == bytes([
            SubrecordType.EGTS_SR_TERM_IDENTITY, 0x02, 0x00, 0xAA, 0xBB,
        ])

    def test_serialize_multiple_subrecords(self) -> None:
        """Сериализация нескольких подзаписей"""
        subrecord1 = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_TERM_IDENTITY,
            data=b"\xaa\xbb",
        )
        subrecord2 = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_MODULE_DATA,
            data=b"\xcc",
        )
        data = serialize_subrecords([subrecord1, subrecord2])

        assert data == bytes([
            SubrecordType.EGTS_SR_TERM_IDENTITY, 0x02, 0x00, 0xAA, 0xBB,
            SubrecordType.EGTS_SR_MODULE_DATA, 0x01, 0x00, 0xCC,
        ])

    def test_serialize_empty_list(self) -> None:
        """Сериализация пустого списка"""
        data = serialize_subrecords([])
        assert data == b""


class TestSubrecordEdgeCases:
    """Тесты на краевые случаи"""

    def test_subrecord_max_srl(self) -> None:
        """Подзапись с большой длиной данных"""
        subrecord = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_RECORD_RESPONSE,
            data=b"\x00" * 100,
        )
        raw = subrecord.to_bytes()
        assert int.from_bytes(raw[1:3], "little") == 100

    def test_subrecord_zero_type(self) -> None:
        """Подзапись с типом 0 (EGTS_SR_RECORD_RESPONSE)"""
        subrecord = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_RECORD_RESPONSE,
            data=b"\x01\x00\x00",
        )
        raw = subrecord.to_bytes()
        parsed = Subrecord.from_bytes(raw)

        assert parsed.subrecord_type == SubrecordType.EGTS_SR_RECORD_RESPONSE
        assert parsed.data == b"\x01\x00\x00"

    def test_subrecord_large_data(self) -> None:
        """Подзапись с большими данными"""
        large_data = bytes(range(256)) * 10  # 2560 байт
        subrecord = Subrecord(
            subrecord_type=SubrecordType.EGTS_SR_ACCEL_DATA,
            data=large_data,
        )
        raw = subrecord.to_bytes()
        parsed = Subrecord.from_bytes(raw)

        assert parsed.subrecord_type == SubrecordType.EGTS_SR_ACCEL_DATA
        assert len(parsed.data) == 2560
        assert parsed.data == large_data
