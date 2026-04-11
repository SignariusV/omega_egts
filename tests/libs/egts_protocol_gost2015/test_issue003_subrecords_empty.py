"""Тест подтверждения: парсер AUTH сервиса не разбирает subrecords

Гипотеза: при парсинге TERM_IDENTITY пакета record.subrecords = [],
поэтому adapter.parse_packet() не может заполнить extra["subrecord_type"].

Запуск::

    pytest tests/libs/egts_protocol_gost2015/test_issue003_subrecords_empty.py -v -s
"""

from __future__ import annotations

import pytest

from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015


# TERM_IDENTITY HEX из интеграционных тестов
TERM_IDENTITY_HEX = (
    "0100000B002E002A0001CC2700490080010101240001000000"
    "16383630383033303636343438333133303235303737303031"
    "373135363433390F3A"
)


class TestIssue003_SubrecordsParsing:
    """Проверка что парсер AUTH сервиса разбирает subrecords."""

    def test_term_identity_record_has_subrecords(self) -> None:
        """TERM_IDENTITY пакет должен содержать subrecords в записи."""
        adapter = EgtsProtocol2015()
        raw = bytes.fromhex(TERM_IDENTITY_HEX)

        result = adapter.parse_packet(raw)

        # Базовые проверки
        assert result.packet is not None
        assert len(result.packet.records) > 0, "Пакет должен содержать записи"

        record = result.packet.records[0]
        assert record.service_type == 1, f"service_type должен быть 1 (AUTH), но: {record.service_type}"

        # !!! КЛЮЧЕВАЯ ПРОВЕРКА !!!
        print(f"\n[ПАКСЕР] record_id={record.record_id}")
        print(f"[ПАКСЕР] service_type={record.service_type}")
        print(f"[ПАКСЕР] subrecords={record.subrecords}")
        print(f"[ПАКСЕР] extra={result.extra}")

        assert len(record.subrecords) > 0, (
            f"subrecords не должны быть пустыми для TERM_IDENTITY пакета. "
            f"record_id={record.record_id}, service_type={record.service_type}. "
            f"Это означает что парсер AUTH сервиса не разбирает подзаписи."
        )

        # Проверяем что subrecord_type определён
        subrecord = record.subrecords[0]
        assert subrecord.subrecord_type is not None, (
            f"subrecord_type должен быть определён, но: {subrecord.subrecord_type}"
        )
        print(f"[ПАКСЕР] subrecord_type={subrecord.subrecord_type}")

    def test_parse_packet_extra_has_subrecord_type(self) -> None:
        """parse_packet() должен заполнить extra['subrecord_type']."""
        adapter = EgtsProtocol2015()
        raw = bytes.fromhex(TERM_IDENTITY_HEX)

        result = adapter.parse_packet(raw)

        print(f"\n[EXTRA] {result.extra}")

        assert "service" in result.extra, "extra должен содержать 'service'"
        assert result.extra["service"] == 1, f"service должен быть 1, но: {result.extra['service']}"

        assert "subrecord_type" in result.extra, (
            "extra должен содержать 'subrecord_type'. "
            "Отсутствие означает что парсер subrecords не работает или adapter не извлекает тип."
        )
        assert result.extra["subrecord_type"] is not None, (
            f"subrecord_type не должен быть None"
        )
