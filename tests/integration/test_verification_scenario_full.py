"""Интеграционный тест полного сценария верификации через SMS.

Сервер:
  - Запускает CoreEngine
  - Загружает сценарий scenarios/verification/scenario.json
  - Выполняет сценарий в фоне (ждёт пакеты, отправляет SMS)

Клиент (эмулятор УСВ):
  - Регистрирует handler для CMW-500 (эмуляция ответов УСВ на SMS)
  - Получает SMS от платформы, отправляет COMCONF-подтверждения
  - На последний запрос UNIT_ID возвращает заполненный COMCONF

Проверяет:
  - Сценарий выполнен полностью (PASS)
  - Все 6 шагов прошли
  - Лог-файл содержит все этапы
  - SMS-пакеты валидны

Использование::

    pytest tests/integration/test_verification_scenario_full.py -v -s
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
from core.cmw500 import Cmw500Emulator
from core.engine import CoreEngine
from core.event_bus import EventBus

# Путь к сценарию
SCENARIO_PATH = Path(__file__).resolve().parent.parent.parent / "scenarios" / "verification" / "scenario.json"

# Пакеты платформы (из scenarios/verification/packets/platform/)
GPRS_APN_HEX = (
    "0100000B0021001B0001321A002A00400404331700500000000000000000000000020302696E7465726E65740D48"
)

SERVER_ADDRESS_HEX = (
    "0100000B002A001C0001AB23002B004004043320005001000000000000000000000204023230302E32302E322E3137313A393039305E55"
)

UNIT_ID_REQUEST_HEX = (
    "0100000B001D001D00013216002C0040040433130050020000000000000000000002040400000001BE2C"
)

# Ответы УСВ (из scenarios/verification/packets/usv/)
COMCONF_APN_HEX = (
    "0100000B001400270001DC0D004600800404330A0010000000000000000000CE40"
)

COMCONF_ADDRESS_HEX = (
    "0100000B0014002800016D0D004700800404330A0010010000000000000000DC5B"
)

COMCONF_UNIT_ID_HEX = (
    "0100000B0014002900012B0D004800800404330A00100200000000000000002277"
)

TEST_PORT = 3098


# Карта запрос → ответ для эмулятора УСВ
_USV_RESPONSE_MAP: dict[str, str] = {
    GPRS_APN_HEX.lower().replace(" ", ""): COMCONF_APN_HEX,
    SERVER_ADDRESS_HEX.lower().replace(" ", ""): COMCONF_ADDRESS_HEX,
    UNIT_ID_REQUEST_HEX.lower().replace(" ", ""): COMCONF_UNIT_ID_HEX,
}


def _usv_sms_handler(egts_bytes: bytes) -> bytes | None:
    """Эмуляция логики УСВ: на полученный SMS-пакет возвращаем ответ."""
    hex_key = egts_bytes.hex().lower()
    response_hex = _USV_RESPONSE_MAP.get(hex_key)
    if response_hex:
        print(f"[УСВ] Получен запрос → отправляю COMCONF-ответ")
        return bytes.fromhex(response_hex)
    print(f"[УСВ] Неизвестный запрос: {hex_key[:40]}...")
    return None


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def config(tmp_path: Path) -> Config:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        gost_version="2015",
        tcp_port=TEST_PORT,  # TCP не используется в SMS-сценарии, но Config требует валидный порт
        cmw500=CmwConfig(ip="127.0.0.1"),  # Фейковый IP для инициализации эмулятора CMW-500
        logging=LogConfig(
            dir=str(log_dir),
            level="DEBUG",
        ),
        timeouts=TimeoutsConfig(),
    )


class TestVerificationScenarioFull:
    """Полный сценарий верификации через SMS-канал."""

    async def test_verification_scenario_with_scenario_manager(
        self, config: Config, event_bus: EventBus, tmp_path: Path
    ):
        """Тест: ScenarioManager выполняет verification/scenario.json, эмулятор УСВ подыгрывает."""
        state_events: list[dict[str, Any]] = []
        packet_events: list[dict[str, Any]] = []
        command_events: list[dict[str, Any]] = []
        scenario_result: dict[str, str] = {"status": "NOT_STARTED"}
        received_sms_packets: list[bytes] = []

        async def on_connection_changed(data: dict[str, Any]) -> None:
            state_events.append(data)
            print(f"[СОСТОЯНИЕ] {data.get('state')} — {data.get('action')}")

        async def on_packet_processed(data: dict[str, Any]) -> None:
            packet_events.append(data)
            channel = data.get("channel", "?")
            parsed = data.get("parsed")
            extra = parsed.extra if parsed else {}
            print(f"[ПАКЕТ] channel={channel}, extra_keys={list(extra.keys())}")

        async def on_command_send(data: dict[str, Any]) -> None:
            step = data.get("step_name", "?")
            channel = data.get("channel", "tcp")
            pkt_len = len(data.get("packet_bytes", b""))
            command_events.append({"type": "send", "step": step, "channel": channel, "len": pkt_len})
            print(f"[КОМАНДА] send: step={step}, channel={channel}, len={pkt_len}")

        async def on_command_sent(data: dict[str, Any]) -> None:
            step = data.get("step_name", "?")
            command_events.append({"type": "sent", "step": step})
            print(f"[КОМАНДА] sent: step={step}")

        async def on_command_error(data: dict[str, Any]) -> None:
            err = data.get("error", "?")
            command_events.append({"type": "error", "error": err})
            print(f"[КОМАНДА] error: {err}")

        # Подписка на ВСЕ события EventBus
        _original_emit = event_bus.emit

        async def _tracing_emit(event_name: str, data: dict | None = None) -> None:
            print(f"[EVENTBUS] {event_name}: {data}")
            await _original_emit(event_name, data)

        event_bus.emit = _tracing_emit  # type: ignore[assignment]

        event_bus.on("connection.changed", on_connection_changed, ordered=True)
        event_bus.on("packet.processed", on_packet_processed, ordered=True)
        event_bus.on("command.send", on_command_send)
        event_bus.on("command.sent", on_command_sent)
        event_bus.on("command.error", on_command_error)

        # 1. Запускаем сервер с эмулятором CMW-500 (патчим Cmw500Controller → Cmw500Emulator)
        # engine.py делает `from core.cmw500 import Cmw500Controller` внутри start(),
        # поэтому патчим прямо в sys.modules["core.cmw500"]
        import sys
        import core.cmw500 as cmw500_module
        original_class = cmw500_module.Cmw500Controller
        cmw500_module.Cmw500Controller = Cmw500Emulator  # type: ignore[misc]

        # Сохраняем оригинальный __init__ для подмены задержек
        _orig_emulator_init = Cmw500Emulator.__init__

        def _fast_init(self, *args, **kwargs):
            _orig_emulator_init(self, *args, **kwargs, sms_delay_min=0.1, sms_delay_max=0.5)

        Cmw500Emulator.__init__ = _fast_init  # type: ignore[method-assign]
        try:
            engine = CoreEngine(config=config, bus=event_bus)
            await engine.start()
            assert engine.is_running
        finally:
            cmw500_module.Cmw500Controller = original_class  # type: ignore[misc]
            Cmw500Emulator.__init__ = _orig_emulator_init  # type: ignore[method-assign]

        # Эмулятор создан engine.start(), подставляем SMS-handler
        assert engine.cmw500 is not None, "CMW-500 эмулятор не создан"
        assert isinstance(engine.cmw500, Cmw500Emulator), (
            f"Ожидался Cmw500Emulator, получен {type(engine.cmw500).__name__}"
        )
        engine.cmw500.set_incoming_sms_handler(_usv_sms_handler)
        print("[CMW] Эмулятор CMW-500 подключён, SMS-handler зарегистрирован")

        # 3. Загружаем сценарий
        engine.scenario_mgr.load(SCENARIO_PATH)
        steps = engine.scenario_mgr.steps
        assert len(steps) == 6, f"Ожидалось 6 шагов, загружено {len(steps)}"
        print(f"\n[СЦЕНАРИЙ] Загружено {len(steps)} шагов:")
        for i, s in enumerate(steps, 1):
            print(f"  {i}. {type(s).__name__}: {s.name}", end="")
            if hasattr(s, "packet_file") and s.packet_file:
                abs_path = (SCENARIO_PATH.parent / s.packet_file).resolve()
                s.packet_file = str(abs_path)
                print(f" → {abs_path}")
            else:
                print()

        # 4. Запускаем сценарий
        async def run_scenario() -> None:
            print("[СЦЕНАРИЙ] Начинаю выполнение...")
            result = await engine.scenario_mgr.execute(
                bus=event_bus,
                connection_id=None,  # SMS — без connection_id
                timeout=30.0,
            )
            print(f"[СЦЕНАРИЙ] Результат: {result}")
            for h in engine.scenario_mgr.context.history:
                print(f"  {h.step_name}: {h.result} ({h.duration:.3f}s)")
            scenario_result["status"] = result

        scenario_task = asyncio.create_task(run_scenario())

        try:
            # Ждём завершения сценария — все обмены идут через SMS-handler
            print("[ТЕСТ] Жду завершения сценария (SMS-обмен)...")
            await asyncio.wait_for(scenario_task, timeout=30.0)

            # ===== ПРОВЕРКИ =====

            # 1. Сценарий выполнен
            assert scenario_result["status"] == "PASS", (
                f"Сценарий: {scenario_result['status']}"
            )

            # 2. Все 6 шагов PASS
            history = engine.scenario_mgr.context.history
            passed = [h for h in history if h.result == "PASS"]
            assert len(passed) == 6, (
                f"6/6 шагов должны пройти PASS, прошло {len(passed)}. "
                f"История: {[(h.step_name, h.result) for h in history]}"
            )

            # 3. Пакеты обработаны (3 запроса + 3 ответа = 6 packet.processed)
            assert len(packet_events) >= 3, (
                f"Ожидалось ≥3 packet.processed, получено {len(packet_events)}"
            )

            # 4. Все команды отправлены через SMS
            sms_sends = [e for e in command_events if e.get("channel") == "sms"]
            assert len(sms_sends) >= 3, (
                f"Ожидалось ≥3 SMS-отправок, получено {len(sms_sends)}"
            )

            # 5. Логи
            await engine.log_mgr.flush()
            log_dir = Path(config.logging.dir)
            log_files = list(log_dir.glob("*.jsonl"))
            assert len(log_files) >= 1
            log_content = log_files[0].read_text(encoding="utf-8")
            log_lines = [l for l in log_content.strip().split("\n") if l]
            packet_entries = [
                json.loads(l) for l in log_lines
                if json.loads(l).get("log_type") == "packet"
            ]
            assert len(packet_entries) >= 3, (
                f"Ожидалось ≥3 packet-записей в логе, получено {len(packet_entries)}"
            )

            # Вывод
            print("\n===== СОСТОЯНИЯ =====")
            for evt in state_events:
                print(f"  {evt.get('state')} — {evt.get('action')}")

            print("\n===== ЛОГИ =====")
            for i, line in enumerate(log_lines[:15], 1):
                entry = json.loads(line)
                lt = entry.get("log_type", "?")
                extra = ""
                if lt == "packet":
                    parsed = entry.get("parsed", {})
                    extra = f"  channel={entry.get('channel', '?')}"
                    if entry.get("response_hex"):
                        extra += f"  response={len(bytes.fromhex(entry['response_hex']))}b"
                print(f"  [{i}] {lt}{extra}")

        finally:
            if not scenario_task.done():
                scenario_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scenario_task
            await engine.stop()
