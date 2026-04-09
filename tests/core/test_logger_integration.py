# mypy: ignore-errors
"""Интеграционный тест LogManager — реальный формат логов.

Запускает EventBus → Pipeline → LogManager на реальных EGTS-пакетах,
записывает логи и выводит содержимое.

Запуск::
    pytest tests/core/test_logger_integration.py -v -s
"""

import asyncio
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.event_bus import EventBus
from core.logger import LogManager
from core.pipeline import (
    AutoResponseMiddleware,
    CrcValidationMiddleware,
    DuplicateDetectionMiddleware,
    EventEmitMiddleware,
    PacketContext,
    PacketPipeline,
    ParseMiddleware,
)
from core.session import SessionManager, UsvConnection
from libs.egts_protocol_gost2015 import EgtsProtocol2015
from libs.egts_protocol_gost2015.gost2015_impl.packet import Packet, Record
from libs.egts_protocol_gost2015.gost2015_impl.subrecord import Subrecord


class TestLogManagerRealFormat:
    """Интеграционный тест — реальный формат логов LogManager."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def protocol(self):
        return EgtsProtocol2015()

    @pytest.fixture
    def session_mgr(self, event_bus, protocol):
        sm = SessionManager(bus=event_bus, gost_version="2015")
        conn = UsvConnection(connection_id="test-tcp-001")
        conn.protocol = protocol
        sm.connections["test-tcp-001"] = conn
        return sm

    @pytest.fixture
    def pipeline(self, event_bus, session_mgr):
        """Pipeline с ПРАВИЛЬНЫМ порядком: CRC → Parse → Dedup → AutoResp → Emit."""
        p = PacketPipeline()
        p.add("crc", CrcValidationMiddleware(session_mgr), order=1)
        p.add("parse", ParseMiddleware(session_mgr), order=2)
        p.add("dedup", DuplicateDetectionMiddleware(session_mgr), order=3)
        p.add("auto_resp", AutoResponseMiddleware(session_mgr), order=4)
        p.add("emit", EventEmitMiddleware(event_bus), order=5)
        return p

    @pytest.fixture
    def log_manager(self, event_bus, tmp_path):
        with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
            return LogManager(
                bus=event_bus, log_dir=tmp_path,
                flush_interval=999, flush_batch_size=9999,
            )

    def _build_valid_packet(self, protocol, pid=1, records=None):
        """Собрать валидный EGTS-пакет через протокол."""
        pkt = Packet(
            packet_id=pid,
            packet_type=1,  # APPDATA
            priority=0,
            records=records or [],
        )
        return protocol.build_packet(pkt)

    @pytest.mark.asyncio
    async def test_real_log_format(self, event_bus, pipeline, session_mgr,
                                    log_manager, protocol, tmp_path):
        """Прогнать 5 пакетов через pipeline, записать логи, вывести формат."""
        # Пакет 1: обычный APPDATA с записью
        rec = Record(record_id=1, service_type=2, subrecords=[])
        raw1 = self._build_valid_packet(protocol, pid=1, records=[rec])

        # Пакет 2: тот же PID — дубликат
        raw2 = raw1

        # Пакет 3: битый CRC (портим последний байт)
        raw3 = raw1[:-1] + bytes([(raw1[-1] + 1) % 256])

        # Пакет 4: слишком короткий (мусор)
        raw4 = b"\x01\x00\xFF"

        # Пакет 5: другой PID, пустой
        raw5 = self._build_valid_packet(protocol, pid=42)

        # Пакет 6: RESPONSE (проверка логирования ответных пакетов)
        raw6 = protocol.build_response(pid=1, result_code=0)

        packets = [
            ("tcp", raw1, "Обычный APPDATA"),
            ("tcp", raw2, "Дубликат PID=1"),
            ("tcp", raw3, "Битый CRC-16"),
            ("sms", raw4, "Короткий пакет (мусор)"),
            ("tcp", raw5, "PID=42"),
            ("tcp", raw6, "RESPONSE PID=1"),
        ]

        for channel, raw, desc in packets:
            ctx = PacketContext(raw=raw, connection_id="test-tcp-001", channel=channel)
            await pipeline.process(ctx)

        # Фиксируем событие connection.changed
        await event_bus.emit("connection.changed", {
            "connection_id": "test-tcp-001",
            "state": "DISCONNECTED",
            "prev_state": "CONNECTED",
            "timestamp": asyncio.get_event_loop().time(),
        })

        # Сбрасываем логи
        await log_manager.flush()

        # Читаем и выводим
        today = date.today().isoformat()
        log_file = tmp_path / f"{today}.jsonl"
        assert log_file.exists(), f"Файл логов {log_file} не создан"

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        entries = [json.loads(line) for line in lines]

        print("\n" + "=" * 100)
        print(f"ЛОГ-ФАЙЛ: {log_file}")
        print(f"Записей: {len(entries)}")
        print("=" * 100)

        for i, entry in enumerate(entries):
            log_type = entry.get("log_type", "unknown")
            print(f"\n--- Запись #{i + 1} ({log_type}) ---")
            print(json.dumps(entry, indent=2, ensure_ascii=False, default=str))

        print("\n" + "=" * 100)

        # === Проверки ===
        packet_entries = [e for e in entries if e["log_type"] == "packet"]
        conn_entries = [e for e in entries if e["log_type"] == "connection"]

        assert len(packet_entries) == 6, f"Ожидалось 6 пакетов, получено {len(packet_entries)}"
        assert len(conn_entries) == 1

        # 1. Обычный пакет — CRC валиден, terminated=False
        ok = packet_entries[0]
        assert ok["crc_valid"] is True
        assert ok["terminated"] is False
        assert ok["channel"] == "tcp"
        assert " " not in ok["hex"]  # hex без пробелов
        assert ok["parsed"] is not None, "parsed должен быть для валидного пакета"

        # 2. Дубликат
        dup = packet_entries[1]
        assert dup["is_duplicate"] is True
        assert dup["terminated"] is True

        # 3. Битый CRC
        crc_err = packet_entries[2]
        assert crc_err["crc_valid"] is False
        assert crc_err["terminated"] is True

        # 4. SMS-канал, короткий пакет
        sms = packet_entries[3]
        assert sms["channel"] == "sms"
        assert sms["crc_valid"] is False

        # 5. PID=42
        pkt42 = packet_entries[4]
        assert pkt42["crc_valid"] is True

        # 6. RESPONSE
        resp = packet_entries[5]
        assert resp["crc_valid"] is True

        # Сортировка по timestamp
        timestamps = [e["timestamp"] for e in entries]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_stop_flushes_and_writes(self, event_bus, tmp_path):
        """stop() сбрасывает буфер — логи записаны после остановки."""
        with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
            lm = LogManager(
                bus=event_bus, log_dir=tmp_path,
                flush_interval=999, flush_batch_size=9999,
            )

        ctx = PacketContext(
            raw=b"\xDE\xAD\xBE\xEF",
            connection_id="test-conn",
            channel="tcp",
            crc_valid=False,
        )
        await lm._on_packet_processed({
            "ctx": ctx,
            "connection_id": "test-conn",
            "channel": "tcp",
            "crc_valid": False,
            "is_duplicate": False,
            "terminated": True,
        })

        # НЕ вызываем flush вручную — только stop()
        await lm.stop()

        today = date.today().isoformat()
        log_file = tmp_path / f"{today}.jsonl"
        assert log_file.exists(), "stop() не сбросил буфер"

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])

        print("\n" + "=" * 60)
        print("ЛОГ ПОСЛЕ stop():")
        print(json.dumps(entry, indent=2, ensure_ascii=False, default=str))
        print("=" * 60)

        assert entry["log_type"] == "packet"
        assert entry["connection_id"] == "test-conn"
        assert entry["hex"] == "DEADBEEF"
