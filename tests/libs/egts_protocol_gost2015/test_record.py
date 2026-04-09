"""Тесты на запись уровня ППУ EGTS (ГОСТ 33465-2015, раздел 6.6)

Покрывает:
- Сборку записей (to_bytes)
- Парсинг записей (from_bytes)
- Флаги RFL (OID, EVID, TM)
- Краевые случаи (max ID, zero ID, all services)
- Парсинг нескольких записей
"""


from libs.egts_protocol_gost2015.gost2015_impl.record import Record
from libs.egts_protocol_gost2015.gost2015_impl.subrecord import Subrecord
from libs.egts_protocol_gost2015.gost2015_impl.types import (
    EGTS_RFL_EVFE_MASK,
    EGTS_RFL_OBFE_MASK,
    EGTS_RFL_TMFE_MASK,
    RECORD_MIN_SIZE,
    ServiceType,
)


class TestRecordBuild:
    """Тесты на сборку записей"""

    def test_record_build_minimal(self) -> None:
        """Сборка минимальной записи без подзаписей"""
        record = Record(
            record_id=1,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
        )
        raw = record.to_bytes()

        assert len(raw) >= RECORD_MIN_SIZE
        assert isinstance(raw, bytes)

    def test_record_build_with_subrecords(self) -> None:
        """Сборка записи с подзаписями"""
        subrecord = Subrecord(subrecord_type=0x01, data=b"\x01\x02\x03")
        record = Record(
            record_id=2,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            subrecords=[subrecord],
        )
        raw = record.to_bytes()
        assert isinstance(raw, bytes)
        assert len(raw) > RECORD_MIN_SIZE

    def test_record_build_with_flags(self) -> None:
        """Сборка записи с флагами (OID, EVID, TM)"""
        record = Record(
            record_id=3,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            object_id=12345,
            event_id=67890,
            timestamp=1234567890,
        )
        raw = record.to_bytes()

        # С флагами: 7 + 4 (OID) + 4 (EVID) + 4 (TM) = 19 байт минимум
        assert len(raw) >= RECORD_MIN_SIZE + 12


class TestRecordParse:
    """Тесты на парсинг записей"""

    def test_record_parse_minimal(self) -> None:
        """Парсинг минимальной записи"""
        original = Record(
            record_id=42,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
        )
        raw = original.to_bytes()
        parsed = Record.from_bytes(raw)

        assert parsed.record_id == 42
        assert parsed.service_type == ServiceType.EGTS_AUTH_SERVICE

    def test_record_parse_with_flags(self) -> None:
        """Парсинг записи с флагами"""
        original = Record(
            record_id=100,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            object_id=1000,
            event_id=2000,
            timestamp=987654321,
        )
        raw = original.to_bytes()
        parsed = Record.from_bytes(raw)

        assert parsed.record_id == 100
        assert parsed.object_id == 1000
        assert parsed.event_id == 2000
        assert parsed.timestamp == 987654321

    def test_record_parse_roundtrip(self) -> None:
        """Круговой тест: сборка → парсинг → сверка"""
        for record_id in [1, 100, 1000, 65535]:
            original = Record(
                record_id=record_id,
                service_type=ServiceType.EGTS_AUTH_SERVICE,
            )
            raw = original.to_bytes()
            parsed = Record.from_bytes(raw)

            assert parsed.record_id == record_id
            assert parsed.service_type == ServiceType.EGTS_AUTH_SERVICE


class TestRecordFlags:
    """Тесты на флаги записи"""

    def test_record_flag_oid(self) -> None:
        """Флаг наличия OID"""
        record = Record(
            record_id=1,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            object_id=12345,
        )
        raw = record.to_bytes()

        rfl = raw[4]
        assert (rfl & EGTS_RFL_OBFE_MASK) == EGTS_RFL_OBFE_MASK

    def test_record_flag_evid(self) -> None:
        """Флаг наличия EVID"""
        record = Record(
            record_id=1,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            event_id=67890,
        )
        raw = record.to_bytes()

        rfl = raw[4]
        assert (rfl & EGTS_RFL_EVFE_MASK) == EGTS_RFL_EVFE_MASK

    def test_record_flag_tm(self) -> None:
        """Флаг наличия TM"""
        record = Record(
            record_id=1,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            timestamp=1234567890,
        )
        raw = record.to_bytes()

        rfl = raw[4]
        assert (rfl & EGTS_RFL_TMFE_MASK) == EGTS_RFL_TMFE_MASK

    def test_record_all_flags(self) -> None:
        """Все флаги установлены"""
        record = Record(
            record_id=1,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            object_id=100,
            event_id=200,
            timestamp=300,
        )
        raw = record.to_bytes()

        rfl = raw[4]
        expected = EGTS_RFL_OBFE_MASK | EGTS_RFL_EVFE_MASK | EGTS_RFL_TMFE_MASK
        assert (rfl & expected) == expected


class TestRecordEdgeCases:
    """Тесты на краевые случаи"""

    def test_record_max_id(self) -> None:
        """Запись с максимальным ID (65535)"""
        record = Record(
            record_id=65535,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
        )
        raw = record.to_bytes()
        parsed = Record.from_bytes(raw)
        assert parsed.record_id == 65535

    def test_record_zero_id(self) -> None:
        """Запись с ID 0"""
        record = Record(
            record_id=0,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
        )
        raw = record.to_bytes()
        parsed = Record.from_bytes(raw)
        assert parsed.record_id == 0

    def test_record_all_services(self) -> None:
        """Записи всех типов сервисов"""
        for st in ServiceType:
            record = Record(
                record_id=1,
                service_type=st,
            )
            raw = record.to_bytes()
            parsed = Record.from_bytes(raw)
            assert parsed.service_type == st


class TestRecordParseMultiple:
    """Тесты на парсинг нескольких записей"""

    def test_parse_records_single(self) -> None:
        """Парсинг одной записи из ППУ данных"""
        subrecord = Subrecord(subrecord_type=1, data=b"\x01\x02\x03\x04\x05")
        record = Record(
            record_id=1,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            subrecords=[subrecord],
        )

        record_bytes = record.to_bytes()
        parsed_records = Record.parse_records(record_bytes, 1)

        assert len(parsed_records) == 1
        assert parsed_records[0].record_id == 1
        assert parsed_records[0].service_type == ServiceType.EGTS_AUTH_SERVICE

    def test_parse_records_multiple(self) -> None:
        """Парсинг нескольких записей из ППУ данных"""
        record1 = Record(
            record_id=1,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            subrecords=[Subrecord(subrecord_type=1, data=b"\x01\x02\x03\x04\x05")],
        )
        record2 = Record(
            record_id=2,
            service_type=ServiceType.EGTS_AUTH_SERVICE,
            subrecords=[Subrecord(subrecord_type=2, data=b"\x02\x03\x04\x05\x06")],
        )

        ppu_data = record1.to_bytes() + record2.to_bytes()
        parsed_records = Record.parse_records(ppu_data, 1)

        assert len(parsed_records) == 2
        assert parsed_records[0].record_id == 1
        assert parsed_records[1].record_id == 2

    def test_parse_records_empty(self) -> None:
        """Парсинг пустых данных"""
        parsed_records = Record.parse_records(b"", 1)
        assert len(parsed_records) == 0

    def test_parse_records_incomplete(self) -> None:
        """Парсинг неполных данных"""
        parsed_records = Record.parse_records(b"\x05\x00", 1)
        assert len(parsed_records) == 0
