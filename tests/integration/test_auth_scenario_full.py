"""Интеграционный тест полного сценария авторизации со ScenarioManager.

Сервер:
  - Запускает CoreEngine
  - Загружает сценарий scenarios/auth/scenario.json
  - Выполняет сценарий в фоне (ждёт пакеты, отправляет RESPONSE/RESULT_CODE)

Клиент (эмулятор УСВ):
  - Подключается к TCP-серверу
  - Отправляет TERM_IDENTITY, получает RESPONSE
  - Отправляет VEHICLE_DATA, получает RESPONSE
  - Получает RESULT_CODE от сервера
  - Отправляет RECORD_RESPONSE, получает RESPONSE

Проверяет:
  - Сценарий выполнен полностью (PASS)
  - FSM: CONNECTED → AUTHENTICATING → AUTHORIZED → RUNNING
  - Лог-файл содержит все этапы

Использование::

    pytest tests/integration/test_auth_scenario_full.py -v -s
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
from core.engine import CoreEngine
from core.event_bus import EventBus

# Путь к сценарию
SCENARIO_PATH = Path(__file__).resolve().parent.parent.parent / "scenarios" / "auth" / "scenario.json"

# Пакеты УСВ (из scenarios/auth/packets/usv/)
TERM_IDENTITY_HEX = (
    "0100000B002E002A0001CC2700490080010101240001000000"
    "16383630383033303636343438333133303235303737303031"
    "373135363433390F3A"
)

VEHICLE_DATA_HEX = (
    "0100000B0023002B0001781C004A0080010103190031443447"
    "5032354230333831303837373501000000010000006CE1"
)

# Этот пакет УСВ отправляет ПОСЛЕ того как платформа шлёт RESULT_CODE
RECORD_RESPONSE_RESULT_HEX = (
    "0100000B0010002C00006A20000006004B008001010003002F0000F139"
)

TEST_PORT = 3097


async def _read_one_packet(reader: asyncio.StreamReader, timeout: float = 5.0) -> bytes | None:
    """Прочитать один EGTS-пакет из TCP-потока.

    EGTS: байт 3 = HL (длина заголовка), байты 5-6 = FDL (длина тела).
    Общий размер = HL + FDL + 2 (CRC16).
    """
    # Читаем минимум 7 байт чтобы узнать HL и FDL
    header = await asyncio.wait_for(reader.readexactly(7), timeout=timeout)
    hl = header[3]  # длина заголовка
    fdl = int.from_bytes(header[5:7], "little")  # длина тела
    # Остаток = тело + CRC16(2) - уже прочитанные 7 байт заголовка
    remaining = hl + fdl + 2 - 7
    if remaining > 0:
        rest = await asyncio.wait_for(reader.readexactly(remaining), timeout=timeout)
    else:
        rest = b""
    return header + rest


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def config(tmp_path: Path) -> Config:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        gost_version="2015",
        tcp_port=TEST_PORT,
        cmw500=CmwConfig(ip=None),
        logging=LogConfig(
            dir=str(log_dir),
            level="DEBUG",
        ),
        timeouts=TimeoutsConfig(),
    )


class TestAuthScenarioFull:
    """Полный сценарий авторизации через ScenarioManager."""

    async def test_auth_scenario_with_scenario_manager(
        self, config: Config, event_bus: EventBus, tmp_path: Path
    ):
        """Тест: ScenarioManager выполняет auth/scenario.json, клиент подыгрывает."""
        state_events: list[dict[str, Any]] = []
        packet_events: list[dict[str, Any]] = []
        command_events: list[dict[str, Any]] = []
        scenario_result: dict[str, str] = {"status": "NOT_STARTED"}
        connection_id_holder: dict[str, str | None] = {"cid": None}

        async def on_connection_changed(data: dict[str, Any]) -> None:
            state_events.append(data)
            cid = data.get("connection_id")
            if cid and connection_id_holder["cid"] is None:
                connection_id_holder["cid"] = cid

        async def on_packet_processed(data: dict[str, Any]) -> None:
            packet_events.append(data)
            cid = data.get("connection_id")
            if cid and connection_id_holder["cid"] is None:
                connection_id_holder["cid"] = cid

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

        # Подписка на ВСЕ события EventBus для полной отладки
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

        # 1. Запускаем сервер
        engine = CoreEngine(config=config, bus=event_bus)
        await engine.start()
        assert engine.is_running

        # 2. Загружаем сценарий
        engine.scenario_mgr.load(SCENARIO_PATH)
        steps = engine.scenario_mgr.steps
        assert len(steps) == 6, f"Ожидалось 6 шагов, загружено {len(steps)}"
        print(f"\n[СЦЕНАРИЙ] Загружено {len(steps)} шагов:")
        for i, s in enumerate(steps, 1):
            print(f"  {i}. {type(s).__name__}: {s.name}", end="")
            if hasattr(s, "packet_file") and s.packet_file:
                # Преобразуем относительный путь в абсолютный
                abs_path = (SCENARIO_PATH.parent / s.packet_file).resolve()
                s.packet_file = str(abs_path)
                print(f" → {abs_path}")
            else:
                print()

        # 3. Подключаем клиента СНАЧАЛА чтобы получить connection_id
        print("[ТЕСТ] Подключаю клиента для получения connection_id...")
        reader, writer = await asyncio.open_connection("127.0.0.1", TEST_PORT)
        await asyncio.sleep(0.3)

        # Теперь у нас есть connection_id
        conn_id = connection_id_holder["cid"]
        assert conn_id is not None, "connection_id не получен!"
        print(f"[ТЕСТ] connection_id = {conn_id}")

        received_packets: list[bytes] = []

        # 4. Запускаем сценарий с правильным connection_id
        async def run_scenario() -> None:
            print("[СЦЕНАРИЙ] Начинаю выполнение...")
            result = await engine.scenario_mgr.execute(
                bus=event_bus,
                connection_id=conn_id,
                timeout=30.0,
            )
            print(f"[СЦЕНАРИЙ] Результат: {result}")
            for h in engine.scenario_mgr.context.history:
                print(f"  {h.step_name}: {h.result} ({h.duration:.3f}s)")
            scenario_result["status"] = result

        scenario_task = asyncio.create_task(run_scenario())
        await asyncio.sleep(0.3)

        try:
            # --- Шаг 1: TERM_IDENTITY → ждём RECORD_RESPONSE ---
            print("[КЛИЕНТ] TERM_IDENTITY (PID=42)")
            writer.write(bytes.fromhex(TERM_IDENTITY_HEX))
            await writer.drain()

            resp1 = await _read_one_packet(reader, timeout=5.0)
            assert resp1 is not None, "Нет RESPONSE на TERM_IDENTITY"
            received_packets.append(resp1)
            print(f"[КЛИЕНТ] RESPONSE #{1}: {len(resp1)} байт")

            # --- Шаг 3: VEHICLE_DATA → ждём RECORD_RESPONSE ---
            await asyncio.sleep(0.5)
            print("[КЛИЕНТ] VEHICLE_DATA (PID=43)")
            writer.write(bytes.fromhex(VEHICLE_DATA_HEX))
            await writer.drain()

            resp2 = await _read_one_packet(reader, timeout=5.0)
            assert resp2 is not None, "Нет RESPONSE на VEHICLE_DATA"
            received_packets.append(resp2)
            print(f"[КЛИЕНТ] RESPONSE #{2}: {len(resp2)} байт")

            # Даём сценарию время обработать VEHICLE_DATA
            # Сценарий: ExpectStep(шаг 3) → SendStep(шаг 4) → SendStep(шаг 5: RESULT_CODE)
            print("[КЛИЕНТ] Жду пока сценарий обработает VEHICLE_DATA и отправит RESULT_CODE...")
            await asyncio.sleep(2.0)
            print("[КЛИЕНТ] Жду RESULT_CODE от сервера...")
            result_code_pkt = await _read_one_packet(reader, timeout=5.0)
            if result_code_pkt:
                received_packets.append(result_code_pkt)
                print(f"[КЛИЕНТ] RESULT_CODE: {len(result_code_pkt)} байт")
            else:
                print("[КЛИЕНТ] RESULT_CODE не получен (таймаут)")

            # --- Шаг 6: УСВ подтверждает RESULT_CODE ---
            await asyncio.sleep(0.3)
            print("[КЛИЕНТ] RECORD_RESPONSE_RESULT (PID=44)")
            writer.write(bytes.fromhex(RECORD_RESPONSE_RESULT_HEX))
            await writer.drain()

            resp3 = await _read_one_packet(reader, timeout=5.0)
            if resp3:
                received_packets.append(resp3)
                print(f"[КЛИЕНТ] RESPONSE #{3}: {len(resp3)} байт")

            writer.close()
            await writer.wait_closed()

            # Ждём завершения сценария
            print("[ТЕСТ] Жду завершения сценария...")
            await asyncio.wait_for(scenario_task, timeout=15.0)

            # ===== ПРОВЕРКИ =====

            # 1. Сценарий выполнен
            assert scenario_result["status"] == "PASS", (
                f"Сценарий: {scenario_result['status']}"
            )

            # 2. Все шаги PASS
            history = engine.scenario_mgr.context.history
            passed = [h for h in history if h.result == "PASS"]
            assert len(passed) == 6, (
                f"6/6 шагов должны пройти PASS, прошло {len(passed)}. "
                f"История: {[(h.step_name, h.result) for h in history]}"
            )

            # 3. FSM: CONNECTED → AUTHENTICATING → AUTHORIZED → RUNNING
            states = [e.get("state") for e in state_events]
            states_lower = [s.lower() if isinstance(s, str) else s for s in states]
            assert "connected" in states_lower, f"Нет CONNECTED: {states}"
            assert "authenticating" in states_lower, f"Нет AUTHENTICATING: {states}"
            assert "authorized" in states_lower or "running" in states_lower, (
                f"Нет AUTHORIZED/RUNNING: {states}"
            )

            # 4. Пакеты обработаны
            assert len(packet_events) >= 3, (
                f"Ожидалось ≥3 packet.processed, получено {len(packet_events)}"
            )

            # 5. RESPONSE валидны
            from libs.egts_protocol_gost2015.gost2015_impl.packet import Packet

            for idx, resp in enumerate(received_packets):
                assert resp[0] == 0x01, f"Пакет {idx}: PR={resp[0]:#x}"
                pkt = Packet.from_bytes(resp)
                # RESPONSE или DATA (RESULT_CODE)
                assert pkt.packet_type.value in (0, 1), (
                    f"Пакет {idx}: PT={pkt.packet_type.value}"
                )

            # 6. Логи
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
            assert len(packet_entries) >= 3

            # Вывод
            print("\n===== FSM =====")
            for evt in state_events:
                print(f"  {evt.get('state')} — {evt.get('action')}")

            print("\n===== ЛОГИ =====")
            for i, line in enumerate(log_lines[:12], 1):
                entry = json.loads(line)
                lt = entry.get("log_type", "?")
                extra = ""
                if lt == "packet":
                    parsed = entry.get("parsed", {})
                    extra = f"  pid={parsed.get('packet_id', '?')}"
                    if entry.get("response_hex"):
                        extra += f"  response={len(bytes.fromhex(entry['response_hex']))}b"
                print(f"  [{i}] {lt}{extra}")

        finally:
            if not scenario_task.done():
                scenario_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scenario_task
            await engine.stop()
