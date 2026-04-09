# mypy: ignore-errors
"""Интеграционный тест LogManager — реальные данные из data/packets/.

Загружает настоящие EGTS-пакеты из hex-каталога, прогоняет через
полный pipeline → LogManager, сохраняет логи в temp-директорию
и выводит содержимое.

Запуск::
    pytest tests/core/test_logger_real_data.py -v -s
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


# Загрузка реальных пакетов
_PACKETS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "packets"


def _load_hex_packets(filename: str) -> list[dict]:
    """Загрузить пакеты из JSON-файла с hex-данными."""
    filepath = _PACKETS_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


class TestLogManagerRealData:
    """LogManager с реальными EGTS-пакетами из data/packets/."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def protocol(self):
        return EgtsProtocol2015()

    @pytest.fixture
    def session_mgr(self, event_bus, protocol):
        sm = SessionManager(bus=event_bus, gost_version="2015")
        conn = UsvConnection(connection_id="usv-001")
        conn.protocol = protocol
        # Эмуляция реального устройства
        conn.tid = 12345
        conn.imei = "351234567890123"
        conn.imsi = "250011234567890"
        sm.connections["usv-001"] = conn
        return sm

    @pytest.fixture
    def pipeline(self, event_bus, session_mgr):
        """Правильный порядок: CRC → Parse → Dedup → AutoResp → Emit."""
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

    @pytest.mark.asyncio
    async def test_real_data_from_hex_catalog(self, event_bus, pipeline, session_mgr,
                                               log_manager, protocol, tmp_path):
        """Прогнать реальные пакеты из all_packets_correct через pipeline."""
        packets = _load_hex_packets("all_packets_correct_20260406_190414.json")
        if not packets:
            pytest.skip("all_packets_correct не найден")

        print(f"\n\n{'=' * 100}")
        print(f"ИНТЕГРАЦИОННЫЙ ТЕСТ: {len(packets)} реальных EGTS-пакетов")
        print(f"{'=' * 100}")

        results = []
        for i, pkt_info in enumerate(packets[:10]):  # первые 10 пакетов
            hex_str = pkt_info.get("hex", "")
            description = pkt_info.get("description", "")[:80]
            direction = pkt_info.get("direction", "?")

            try:
                raw = bytes.fromhex(hex_str)
                ctx = PacketContext(
                    raw=raw,
                    connection_id="usv-001",
                    channel="tcp",
                )
                await pipeline.process(ctx)

                results.append({
                    "num": i + 1,
                    "hex_len": len(raw),
                    "crc_valid": ctx.crc_valid,
                    "terminated": ctx.terminated,
                    "is_duplicate": ctx.is_duplicate,
                    "has_parsed": ctx.parsed is not None,
                    "errors": ctx.errors,
                    "description": description,
                    "direction": direction,
                })
            except Exception as e:
                results.append({
                    "num": i + 1,
                    "hex_len": len(hex_str) // 2,
                    "error": str(e),
                    "description": description,
                    "direction": direction,
                })

        # События подключения и отключения
        await event_bus.emit("connection.changed", {
            "connection_id": "usv-001",
            "state": "CONNECTED",
            "prev_state": "DISCONNECTED",
            "timestamp": asyncio.get_event_loop().time(),
        })

        # Событие шага сценария
        await event_bus.emit("scenario.step", {
            "scenario_name": "auth",
            "step_name": "expect_term_identity",
            "step_type": "expect",
            "result": "PASS",
            "details": {"packet_received": True, "tid": 12345},
            "timestamp": asyncio.get_event_loop().time() + 0.1,
        })

        await event_bus.emit("connection.changed", {
            "connection_id": "usv-001",
            "state": "AUTHORIZED",
            "prev_state": "CONNECTED",
            "timestamp": asyncio.get_event_loop().time() + 0.2,
        })

        # Сбрасываем логи
        await log_manager.flush()

        # Выводим результаты обработки пакетов
        print("\nРЕЗУЛЬТАТЫ ОБРАБОТКИ ПАКЕТОВ:")
        print(f"{'#':>3} | {'CRC':>5} | {'DUP':>3} | {'TERM':>4} | "
              f"{'Parsed':>6} | {'Size':>5} | Описание")
        print("-" * 100)
        for r in results:
            crc = "OK" if r.get("crc_valid") else "ERR"
            dup = "Y" if r.get("is_duplicate") else "N"
            term = "Y" if r.get("terminated") else "N"
            parsed = "Y" if r.get("has_parsed") else "N"
            size = r.get("hex_len", "?")
            desc = r.get("description", r.get("error", ""))[:60]
            print(f"{r['num']:>3} | {crc:>5} | {dup:>3} | {term:>4} | "
                  f"{parsed:>6} | {size:>5} | {desc}")

        # Выводим содержимое лог-файла
        today = date.today().isoformat()
        log_file = tmp_path / f"{today}.jsonl"
        assert log_file.exists(), f"Лог-файл {log_file} не создан"

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        entries = [json.loads(line) for line in lines]

        print(f"\n\n{'=' * 100}")
        print(f"ЛОГ-ФАЙЛ: {log_file}")
        print(f"Всего записей: {len(entries)}")
        print(f"{'=' * 100}")

        for i, entry in enumerate(entries):
            log_type = entry.get("log_type", "?")
            conn_id = entry.get("connection_id", "?")
            channel = entry.get("channel", "?")

            if log_type == "packet":
                hex_preview = entry.get("hex", "")[:40]
                crc = "CRC:OK" if entry.get("crc_valid") else "CRC:ERR"
                dup = "DUP" if entry.get("is_duplicate") else ""
                print(f"\n  [{i+1}] PACKET  conn={conn_id}  {channel}  "
                      f"{crc}  {dup}")
                print(f"       hex: {hex_preview}...")
                if entry.get("parsed"):
                    print(f"       parsed: {json.dumps(entry['parsed'], ensure_ascii=False)}")
                if entry.get("errors"):
                    print(f"       errors: {entry['errors']}")
            elif log_type == "connection":
                state = entry.get("state", "?")
                prev = entry.get("prev_state", "?")
                print(f"\n  [{i+1}] CONNECTION  conn={conn_id}  {prev} → {state}")
            elif log_type == "scenario":
                step = entry.get("step_name", "?")
                result = entry.get("result", "?")
                scenario = entry.get("scenario_name", "?")
                print(f"\n  [{i+1}] SCENARIO  {scenario}/{step}  result={result}")

        print(f"\n{'=' * 100}")

        # Полный JSON первой записи каждого типа
        print("\nПОЛНЫЙ JSON записей (по одной каждого типа):\n")
        for log_type in ["packet", "connection", "scenario"]:
            match = next((e for e in entries if e["log_type"] == log_type), None)
            if match:
                print(f"--- {log_type.upper()} ---")
                print(json.dumps(match, indent=2, ensure_ascii=False, default=str))
                print()

        # Статистика
        packet_entries = [e for e in entries if e["log_type"] == "packet"]
        conn_entries = [e for e in entries if e["log_type"] == "connection"]
        scenario_entries = [e for e in entries if e["log_type"] == "scenario"]

        crc_ok = sum(1 for e in packet_entries if e.get("crc_valid"))
        crc_err = sum(1 for e in packet_entries if not e.get("crc_valid"))
        dups = sum(1 for e in packet_entries if e.get("is_duplicate"))

        print(f"\nСТАТИСТИКА ЛОГОВ:")
        print(f"  Пакетов:     {len(packet_entries)}")
        print(f"  CRC OK:      {crc_ok}")
        print(f"  CRC ERR:     {crc_err}")
        print(f"  Дубликаты:   {dups}")
        print(f"  Connection:  {len(conn_entries)}")
        print(f"  Scenario:    {len(scenario_entries)}")

        assert len(packet_entries) > 0, "Нет записей пакетов в логах"
        assert len(conn_entries) >= 2, "Нет записей connection.changed"
        assert len(scenario_entries) >= 1, "Нет записей scenario.step"
