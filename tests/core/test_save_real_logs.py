# mypy: ignore-errors
"""Сохраняет реальные логи в project_root/logs/ для изучения.

Запуск::
    pytest tests/core/test_save_real_logs.py -v -s
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PACKETS_DIR = PROJECT_ROOT / "data" / "packets"
_LOGS_DIR = PROJECT_ROOT / "logs"


def _load_packets(filename: str) -> list[dict]:
    filepath = _PACKETS_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_save_real_logs_to_project():
    """Прогнать все реальные пакеты, сохранить логи в logs/ проекта."""
    packets = _load_packets("all_packets_correct_20260406_190414.json")
    assert packets, "Пакеты не найдены"

    # Создаём logs/ в проекте
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Удаляем старый файл за сегодня если есть
    today = date.today().isoformat()
    old_log = _LOGS_DIR / f"{today}.jsonl"
    if old_log.exists():
        old_log.unlink()

    # Компоненты
    event_bus = EventBus()
    protocol = EgtsProtocol2015()
    session_mgr = SessionManager(bus=event_bus, gost_version="2015")
    conn = UsvConnection(connection_id="usv-test-001")
    conn.protocol = protocol
    conn.tid = 12345
    conn.imei = "351234567890123"
    session_mgr.connections["usv-test-001"] = conn

    pipeline = PacketPipeline()
    pipeline.add("crc", CrcValidationMiddleware(session_mgr), order=1)
    pipeline.add("parse", ParseMiddleware(session_mgr), order=2)
    pipeline.add("dedup", DuplicateDetectionMiddleware(session_mgr), order=3)
    pipeline.add("auto_resp", AutoResponseMiddleware(session_mgr), order=4)
    pipeline.add("emit", EventEmitMiddleware(event_bus), order=5)

    with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
        log_mgr = LogManager(
            bus=event_bus, log_dir=_LOGS_DIR,
            flush_interval=999, flush_batch_size=9999,
        )

    print(f"\n{'=' * 100}")
    print(f"ОБРАБОТКА {len(packets)} РЕАЛЬНЫХ ПАКЕТОВ")
    print(f"{'=' * 100}")

    stats = {"crc_ok": 0, "crc_err": 0, "dup": 0, "parsed": 0, "err": 0}

    for i, pkt_info in enumerate(packets):
        hex_str = pkt_info.get("hex", "")
        try:
            raw = bytes.fromhex(hex_str)
            ctx = PacketContext(raw=raw, connection_id="usv-test-001", channel="tcp")
            await pipeline.process(ctx)

            if ctx.crc_valid:
                stats["crc_ok"] += 1
            else:
                stats["crc_err"] += 1
            if ctx.is_duplicate:
                stats["dup"] += 1
            if ctx.parsed is not None:
                stats["parsed"] += 1

            status = "OK" if ctx.crc_valid else "ERR"
            dup = " DUP" if ctx.is_duplicate else ""
            parsed = f"  PID={ctx.parsed.packet.packet_id}" if ctx.parsed and ctx.parsed.packet else ""
            print(f"  [{i+1:3d}] {status}{dup}  {len(raw):4d}B{parsed}")

        except Exception as e:
            stats["err"] += 1
            print(f"  [{i+1:3d}] EXCEPTION: {e}")

    # События
    await event_bus.emit("connection.changed", {
        "connection_id": "usv-test-001",
        "state": "CONNECTED",
        "prev_state": "DISCONNECTED",
        "timestamp": asyncio.get_event_loop().time(),
    })
    await event_bus.emit("scenario.step", {
        "scenario_name": "auth",
        "step_name": "expect_term_identity",
        "step_type": "expect",
        "result": "PASS",
        "details": {"packets_processed": len(packets)},
        "timestamp": asyncio.get_event_loop().time() + 0.1,
    })
    await event_bus.emit("connection.changed", {
        "connection_id": "usv-test-001",
        "state": "AUTHORIZED",
        "prev_state": "CONNECTED",
        "timestamp": asyncio.get_event_loop().time() + 0.2,
    })
    await event_bus.emit("scenario.step", {
        "scenario_name": "telemetry",
        "step_name": "expect_telemetry",
        "step_type": "expect",
        "result": "PASS",
        "details": {},
        "timestamp": asyncio.get_event_loop().time() + 0.3,
    })

    # Сброс
    await log_mgr.flush()
    await log_mgr.stop()

    # Читаем и выводим
    log_file = _LOGS_DIR / f"{today}.jsonl"
    assert log_file.exists(), f"Лог {log_file} не создан"

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(line) for line in lines]

    print(f"\n{'=' * 100}")
    print(f"ЛОГ-ФАЙЛ: {log_file}")
    print(f"Записей: {len(entries)}")
    print(f"Размер: {log_file.stat().st_size:,} байт")
    print(f"{'=' * 100}")

    print(f"\nСТАТИСТИКА:")
    print(f"  Пакетов CRC OK:   {stats['crc_ok']}")
    print(f"  Пакетов CRC ERR:  {stats['crc_err']}")
    print(f"  Дубликатов:       {stats['dup']}")
    print(f"  Распарсено:       {stats['parsed']}")
    print(f"  Ошибок:           {stats['err']}")

    # Вывод всех записей
    for i, entry in enumerate(entries):
        lt = entry["log_type"]
        if lt == "packet":
            crc = "OK" if entry["crc_valid"] else "ERR"
            dup = " DUP" if entry.get("is_duplicate") else ""
            parsed = entry.get("parsed") or {}
            pid = parsed.get("packet_id", "?")
            hex_preview = entry.get("hex", "")[:60]
            print(f"\n  [{i+1:3d}] PACKET  crc={crc}{dup}  PID={pid}")
            print(f"        hex: {hex_preview}...")
        elif lt == "connection":
            print(f"\n  [{i+1:3d}] CONNECTION  {entry.get('prev_state')} → {entry['state']}")
        elif lt == "scenario":
            print(f"\n  [{i+1:3d}] SCENARIO  {entry['scenario_name']}/{entry['step_name']} = {entry['result']}")

    # Полный JSON первых 3 записей
    print(f"\n{'=' * 100}")
    print("ПОЛНЫЙ JSON (первые 3 записи):")
    print(f"{'=' * 100}")
    for entry in entries[:3]:
        print(json.dumps(entry, indent=2, ensure_ascii=False, default=str))
        print()

    assert len(entries) > 0
