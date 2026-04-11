"""Тест подтверждения гипотезы ISSUE-003: race condition между клиентом и сценарием

Гипотеза: клиент отправляет VEHICLE_DATA слишком рано — до того как
сценарий перешёл к шагу 3 (ExpectStep: VEHICLE_DATA). Пакет обрабатывается
pipeline и эмитит packet.processed, но ExpectStep #3 ещё не подписался.

Запуск::

    pytest tests/integration/test_issue003_race_condition.py -v -s
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
from core.engine import CoreEngine
from core.event_bus import EventBus

# Путь к сценарию
SCENARIO_PATH = Path(__file__).resolve().parent.parent.parent / "scenarios" / "auth" / "scenario.json"

# Пакеты УСВ
TERM_IDENTITY_HEX = (
    "0100000B002E002A0001CC2700490080010101240001000000"
    "16383630383033303636343438333133303235303737303031"
    "373135363433390F3A"
)

VEHICLE_DATA_HEX = (
    "0100000B0023002B0001781C004A0080010103190031443447"
    "5032354230333831303837373501000000010000006CE1"
)

RECORD_RESPONSE_RESULT_HEX = (
    "0100000B0010002C00006A20000006004B008001010003002F0000F139"
)

TEST_PORT = 3098


async def _read_one_packet(reader: asyncio.StreamReader, timeout: float = 5.0) -> bytes | None:
    """Прочитать один EGTS-пакет из TCP-потока."""
    header = await asyncio.wait_for(reader.readexactly(7), timeout=timeout)
    hl = header[3]
    fdl = int.from_bytes(header[5:7], "little")
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
        logging=LogConfig(dir=str(log_dir), level="DEBUG"),
        timeouts=TimeoutsConfig(),
    )


class TestIssue003_RaceCondition:
    """Проверка гипотезы: race condition между клиентом и сценарием."""

    # --- ТЕСТ 1: Воспроизведение бага (клиент отправляет слишком рано) ---

    async def test_race_condition_vehicle_data_sent_too_early(
        self, config: Config, event_bus: EventBus, tmp_path: Path
    ):
        """Клиент отправляет VEHICLE_DATA сразу после RESPONSE #1 — сценарий не успевает подписаться.

        Это должно привести к FAIL — VEHICLE_DATA будет пропущен ExpectStep #3.
        """
        state_events: list[dict[str, Any]] = []
        packet_events: list[dict[str, Any]] = []
        scenario_result = {"status": "NOT_STARTED"}
        connection_id_holder: dict[str, str | None] = {"cid": None}

        async def on_connection_changed(data: dict[str, Any]) -> None:
            state_events.append(data)
            cid = data.get("connection_id")
            if cid and connection_id_holder["cid"] is None:
                connection_id_holder["cid"] = cid

        async def on_packet_processed(data: dict[str, Any]) -> None:
            packet_events.append(data)

        event_bus.on("connection.changed", on_connection_changed, ordered=True)
        event_bus.on("packet.processed", on_packet_processed, ordered=True)

        engine = CoreEngine(config=config, bus=event_bus)
        await engine.start()

        engine.scenario_mgr.load(SCENARIO_PATH)
        for s in engine.scenario_mgr.steps:
            if hasattr(s, "packet_file") and s.packet_file:
                abs_path = (SCENARIO_PATH.parent / s.packet_file).resolve()
                s.packet_file = str(abs_path)

        reader, writer = await asyncio.open_connection("127.0.0.1", TEST_PORT)
        await asyncio.sleep(0.3)
        conn_id = connection_id_holder["cid"]
        assert conn_id is not None

        async def run_scenario() -> None:
            result = await engine.scenario_mgr.execute(
                bus=event_bus, connection_id=conn_id, timeout=15.0
            )
            scenario_result["status"] = result

        scenario_task = asyncio.create_task(run_scenario())
        await asyncio.sleep(0.3)

        try:
            # Клиент отправляет TERM_IDENTITY
            writer.write(bytes.fromhex(TERM_IDENTITY_HEX))
            await writer.drain()
            resp1 = await _read_one_packet(reader, timeout=5.0)
            assert resp1 is not None, "Нет RESPONSE на TERM_IDENTITY"

            # !!! КЛИЕНТ ОТПРАВЛЯЕТ VEHICLE_DATA СРАЗУ (race condition) !!!
            # Сценарий ещё обрабатывает шаг 2 (SendStep), шаг 3 не подписан
            writer.write(bytes.fromhex(VEHICLE_DATA_HEX))
            await writer.drain()
            resp2 = await _read_one_packet(reader, timeout=5.0)
            assert resp2 is not None, "Нет RESPONSE на VEHICLE_DATA"

            # Ждём RESULT_CODE — его не будет, сценарий застрял
            await asyncio.sleep(2.0)
            result_code_pkt = await _read_one_packet(reader, timeout=3.0)

            # RESULT_CODE не придёт — сценарий застрял на шаге 1 или 3 (TIMEOUT)
            writer.close()
            await writer.wait_closed()

            await asyncio.wait_for(scenario_task, timeout=10.0)

            # Проверяем что сценарий НЕ PASS (race condition привёл к TIMEOUT)
            history = engine.scenario_mgr.context.history
            print(f"\n[ТЕСТ 1] Сценарий: {scenario_result['status']}")
            print(f"[ТЕСТ 1] История: {[(h.step_name, h.result, f'{h.duration:.3f}s') for h in history]}")
            print(f"[ТЕСТ 1] Пакетов обработано: {len(packet_events)}")
            print(f"[ТЕСТ 1] RESULT_CODE получен: {result_code_pkt is not None}")

            # Гипотеза подтверждается: сценарий НЕ PASS
            assert scenario_result["status"] != "PASS", (
                f"Ожидался FAIL из-за race condition, но сценарий: {scenario_result['status']}"
            )

        finally:
            if not scenario_task.done():
                scenario_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scenario_task
            await engine.stop()

    # --- ТЕСТ 2: Клиент ждёт перехода сценария к шагу 3 ---

    async def test_vehicle_data_sent_after_scenario_reaches_expect_step(
        self, config: Config, event_bus: EventBus, tmp_path: Path
    ):
        """Клиент отправляет VEHICLE_DATA только после того как сценарий перешёл к шагу 3.

        Если гипотеза верна — сценарий должен PASS.
        """
        state_events: list[dict[str, Any]] = []
        packet_events: list[dict[str, Any]] = []
        scenario_result = {"status": "NOT_STARTED"}
        connection_id_holder: dict[str, str | None] = {"cid": None}

        # Флаг: сценарий перешёл к шагу 3 (ExpectStep: VEHICLE_DATA)
        scenario_ready_for_vehicle_data = asyncio.Event()

        async def on_connection_changed(data: dict[str, Any]) -> None:
            state_events.append(data)
            cid = data.get("connection_id")
            if cid and connection_id_holder["cid"] is None:
                connection_id_holder["cid"] = cid

        async def on_packet_processed(data: dict[str, Any]) -> None:
            packet_events.append(data)

        event_bus.on("connection.changed", on_connection_changed, ordered=True)
        event_bus.on("packet.processed", on_packet_processed, ordered=True)

        engine = CoreEngine(config=config, bus=event_bus)
        await engine.start()

        engine.scenario_mgr.load(SCENARIO_PATH)
        for s in engine.scenario_mgr.steps:
            if hasattr(s, "packet_file") and s.packet_file:
                abs_path = (SCENARIO_PATH.parent / s.packet_file).resolve()
                s.packet_file = str(abs_path)

        reader, writer = await asyncio.open_connection("127.0.0.1", TEST_PORT)
        await asyncio.sleep(0.3)
        conn_id = connection_id_holder["cid"]
        assert conn_id is not None

        async def run_scenario() -> None:
            # Модифицируем execute чтобы сигналить когда доходит до шага 3
            steps = engine.scenario_mgr._steps
            ctx = engine.scenario_mgr._context
            ctx.connection_id = conn_id

            import time
            start_total = time.monotonic()

            for i, step in enumerate(steps):
                # Сигналим когда дошли до ExpectStep #3 (VEHICLE_DATA)
                if i == 2 and hasattr(step, "checks"):
                    print(f"[СЦЕНАРИЙ] Перехожу к шагу {i+1}: {step.name} — СИГНАЛ КЛИЕНТУ")
                    scenario_ready_for_vehicle_data.set()

                elapsed = time.monotonic() - start_total
                remaining = 30.0 - elapsed
                if remaining <= 0:
                    ctx.add_history(step.name, "TIMEOUT", 0.0)
                    scenario_result["status"] = "TIMEOUT"
                    return

                start_time = time.monotonic()
                try:
                    result = await step.execute(ctx, event_bus, timeout=remaining)
                except Exception as exc:
                    print(f"[СЦЕНАРИЙ] Ошибка шага {step.name}: {exc}")
                    result = "ERROR"

                duration = time.time() - start_time
                ctx.add_history(step.name, result, duration)

                if result != "PASS":
                    print(f"[СЦЕНАРИЙ] Шаг {step.name}: {result}")
                    scenario_result["status"] = result
                    return

            scenario_result["status"] = "PASS"
            print(f"[СЦЕНАРИЙ] Результат: PASS")

        scenario_task = asyncio.create_task(run_scenario())

        # Ждём пока сценарий дойдёт до шага 3
        print("[КЛИЕНТ] Жду пока сценарий перейдёт к шагу 3 (VEHICLE_DATA)...")
        try:
            await asyncio.wait_for(scenario_ready_for_vehicle_data.wait(), timeout=10.0)
        except TimeoutError:
            print("[КЛИЕНТ] ТАЙМАУТ ожидания готовности сценария")

        try:
            # Шаг 1: TERM_IDENTITY
            print("[КЛИЕНТ] TERM_IDENTITY (PID=42)")
            writer.write(bytes.fromhex(TERM_IDENTITY_HEX))
            await writer.drain()
            resp1 = await _read_one_packet(reader, timeout=5.0)
            assert resp1 is not None, "Нет RESPONSE на TERM_IDENTITY"
            print(f"[КЛИЕНТ] RESPONSE #1: {len(resp1)} байт")

            # !!! Ждём сигнал от сценария что он готов к VEHICLE_DATA !!!
            print("[КЛИЕНТ] Жду сигнала что сценарий готов к VEHICLE_DATA...")
            await asyncio.wait_for(scenario_ready_for_vehicle_data.wait(), timeout=5.0)
            print("[КЛИЕНТ] Сценарий готов — отправляю VEHICLE_DATA")

            # Шаг 3: VEHICLE_DATA
            await asyncio.sleep(0.2)
            writer.write(bytes.fromhex(VEHICLE_DATA_HEX))
            await writer.drain()
            resp2 = await _read_one_packet(reader, timeout=5.0)
            assert resp2 is not None, "Нет RESPONSE на VEHICLE_DATA"
            print(f"[КЛИЕНТ] RESPONSE #2: {len(resp2)} байт")

            # Ждём RESULT_CODE
            print("[КЛИЕНТ] Жду RESULT_CODE от сервера...")
            result_code_pkt = await _read_one_packet(reader, timeout=5.0)
            if result_code_pkt:
                print(f"[КЛИЕНТ] RESULT_CODE: {len(result_code_pkt)} байт")
            else:
                print("[КЛИЕНТ] RESULT_CODE не получен (таймаут)")

            writer.close()
            await writer.wait_closed()

            await asyncio.wait_for(scenario_task, timeout=10.0)

            history = engine.scenario_mgr.context.history
            print(f"\n[ТЕСТ 2] Сценарий: {scenario_result['status']}")
            print(f"[ТЕСТ 2] История: {[(h.step_name, h.result, f'{h.duration:.3f}s') for h in history]}")
            print(f"[ТЕСТ 2] Пакетов обработано: {len(packet_events)}")

            # Если гипотеза верна — сценарий PASS когда клиент ждёт
            assert scenario_result["status"] == "PASS", (
                f"При синхронизации сценарий должен PASS, но: {scenario_result['status']}. "
                f"История: {[(h.step_name, h.result) for h in history]}"
            )

        finally:
            if not scenario_task.done():
                scenario_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scenario_task
            await engine.stop()
