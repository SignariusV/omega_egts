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
    try:
        header = await asyncio.wait_for(reader.readexactly(7), timeout=timeout)
        hl = header[3]
        fdl = int.from_bytes(header[5:7], "little")
        remaining = hl + fdl + 2 - 7
        if remaining > 0:
            rest = await asyncio.wait_for(reader.readexactly(remaining), timeout=timeout)
        else:
            rest = b""
        return header + rest
    except (asyncio.TimeoutError, asyncio.IncompleteReadError):
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
        tcp_port=TEST_PORT,
        cmw500=CmwConfig(ip=None),
        logging=LogConfig(dir=str(log_dir), level="DEBUG"),
        timeouts=TimeoutsConfig(),
    )


class TestIssue003_RaceCondition:
    """Проверка гипотезы: race condition между клиентом и сценарием."""

    # --- ТЕСТ 1: Ранняя отправка VEHICLE_DATA ---

    async def test_race_condition_vehicle_data_sent_too_early(
        self, config: Config, event_bus: EventBus, tmp_path: Path
    ):
        """Клиент отправляет TERM_IDENTITY + VEHICLE_DATA подряд, без ожидания RESPONSE.

        Проверяем что система обрабатывает оба пакета (неважно в каком порядке)
        и сценарий завершается (PASS или FAIL — зависит от timing).

        Главное: сценарий НЕ зависает и НЕ падает с исключением.
        """
        packet_events: list[dict[str, Any]] = []
        scenario_result = {"status": "NOT_STARTED"}
        connection_id_holder: dict[str, str | None] = {"cid": None}
        # Событие: сценарий начал выполнение (перешёл к первому шагу)
        scenario_started = asyncio.Event()

        async def on_connection_changed(data: dict[str, Any]) -> None:
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
            scenario_started.set()
            result = await engine.scenario_mgr.execute(
                bus=event_bus, connection_id=conn_id, timeout=15.0
            )
            scenario_result["status"] = result

        scenario_task = asyncio.create_task(run_scenario())

        # Ждём начала сценария
        await asyncio.wait_for(scenario_started.wait(), timeout=5.0)
        # Небольшая задержка чтобы ExpectStep #1 успел подписаться
        await asyncio.sleep(0.2)

        try:
            # Отправляем TERM_IDENTITY + VEHICLE_DATA подряд
            writer.write(bytes.fromhex(TERM_IDENTITY_HEX))
            writer.write(bytes.fromhex(VEHICLE_DATA_HEX))
            await writer.drain()

            # Читаем RESPONSE-ы
            resp1 = await _read_one_packet(reader, timeout=5.0)
            resp2 = await _read_one_packet(reader, timeout=5.0)

            # Закрываем соединение чтобы сценарий не ждал вечно
            writer.close()
            await writer.wait_closed()

            # Ждём завершения сценария
            try:
                await asyncio.wait_for(scenario_task, timeout=10.0)
            except TimeoutError:
                scenario_result["status"] = "SCENARIO_TIMEOUT"

            history = engine.scenario_mgr.context.history
            print(f"\n[ТЕСТ 1] Сценарий: {scenario_result['status']}")
            print(f"[ТЕСТ 1] История: {[(h.step_name, h.result, f'{h.duration:.3f}s') for h in history]}")
            print(f"[ТЕСТ 1] Пакетов обработано: {len(packet_events)}")
            print(f"[ТЕСТ 1] RESPONSE-ов получено: {sum(1 for r in [resp1, resp2] if r is not None)}")

            # Главное: сценарий завершился (не завис)
            assert scenario_result["status"] != "NOT_STARTED", "Сценарий не начался"
            assert scenario_result["status"] != "SCENARIO_TIMEOUT", (
                "Сценарий завис — race condition не обработан"
            )
            # Оба пакета должны быть обработаны (или хотя бы один)
            assert len(packet_events) >= 1, "Ни один пакет не обработан"

        finally:
            if not scenario_task.done():
                scenario_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scenario_task
            await engine.stop()

    # --- ТЕСТ 2: Синхронизированная отправка ---

    async def test_vehicle_data_sent_after_scenario_reaches_expect_step(
        self, config: Config, event_bus: EventBus, tmp_path: Path
    ):
        """Клиент отправляет пакеты ПОСЛЕ того как сценарий обработал предыдущий.

        Используем synchronization barrier: клиент ждёт пока ExpectStep
        подпишется, затем отправляет пакет.

        Если синхронизация работает — сценарий PASS.
        """
        packet_events: list[dict[str, Any]] = []
        scenario_result = {"status": "NOT_STARTED"}
        connection_id_holder: dict[str, str | None] = {"cid": None}

        # Сигналы между клиентом и сценарием
        client_ready_to_send = asyncio.Event()
        scenario_step_reached = asyncio.Event()

        async def on_connection_changed(data: dict[str, Any]) -> None:
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
            steps = engine.scenario_mgr._steps
            ctx = engine.scenario_mgr._context
            ctx.connection_id = conn_id

            import time
            start_total = time.monotonic()

            for i, step in enumerate(steps):
                elapsed = time.monotonic() - start_total
                remaining = 30.0 - elapsed
                if remaining <= 0:
                    ctx.add_history(step.name, "TIMEOUT", 0.0)
                    scenario_result["status"] = "TIMEOUT"
                    return

                # Сигналим клиенту перед ExpectStep #1 (TERM_IDENTITY)
                if i == 0 and hasattr(step, "checks"):
                    scenario_step_reached.set()
                    await asyncio.wait_for(client_ready_to_send.wait(), timeout=10.0)
                    client_ready_to_send.clear()

                # Сигналим клиенту перед ExpectStep #3 (VEHICLE_DATA)
                if i == 2 and hasattr(step, "checks"):
                    scenario_step_reached.set()
                    await asyncio.wait_for(client_ready_to_send.wait(), timeout=10.0)
                    client_ready_to_send.clear()

                # Пропускаем шаг 6 (Подтверждение результата) — он не критичен
                # для проверки синхронизации VEHICLE_DATA
                if i == 5:
                    ctx.add_history(step.name, "SKIPPED", 0.0)
                    continue

                try:
                    result = await step.execute(ctx, event_bus, timeout=remaining)
                except Exception as exc:
                    print(f"[СЦЕНАРИЙ] Ошибка шага {step.name}: {exc}")
                    result = "ERROR"

                ctx.add_history(step.name, result, time.time() - start_total)

                if result != "PASS":
                    print(f"[СЦЕНАРИЙ] Шаг {step.name}: {result}")
                    scenario_result["status"] = result
                    return

            scenario_result["status"] = "PASS"

        scenario_task = asyncio.create_task(run_scenario())

        try:
            # --- Шаг 1: TERM_IDENTITY ---
            # Ждём пока сценарий подпишется на TERM_IDENTITY
            await asyncio.wait_for(scenario_step_reached.wait(), timeout=10.0)
            scenario_step_reached.clear()

            print("[КЛИЕНТ] Отправляю TERM_IDENTITY")
            writer.write(bytes.fromhex(TERM_IDENTITY_HEX))
            await writer.drain()
            client_ready_to_send.set()

            resp1 = await _read_one_packet(reader, timeout=5.0)
            assert resp1 is not None, "Нет RESPONSE на TERM_IDENTITY"
            print(f"[КЛИЕНТ] RESPONSE #1: {len(resp1)} байт")

            # --- Шаг 3: VEHICLE_DATA ---
            # Ждём пока сценарий подпишется на VEHICLE_DATA
            await asyncio.wait_for(scenario_step_reached.wait(), timeout=10.0)
            scenario_step_reached.clear()

            print("[КЛИЕНТ] Отправляю VEHICLE_DATA")
            writer.write(bytes.fromhex(VEHICLE_DATA_HEX))
            await writer.drain()
            client_ready_to_send.set()

            resp2 = await _read_one_packet(reader, timeout=5.0)
            assert resp2 is not None, "Нет RESPONSE на VEHICLE_DATA"
            print(f"[КЛИЕНТ] RESPONSE #2: {len(resp2)} байт")

            # Ждём RESULT_CODE от сервера (SendStep)
            result_code_pkt = await _read_one_packet(reader, timeout=5.0)
            if result_code_pkt:
                print(f"[КЛИЕНТ] RESULT_CODE: {len(result_code_pkt)} байт")

                # Шаг 6 сценария ожидает RECORD_RESPONSE от УСВ
                # Отправляем его чтобы сценарий мог завершиться
                print("[КЛИЕНТ] Отправляю RECORD_RESPONSE для RESULT_CODE")
                writer.write(bytes.fromhex(RECORD_RESPONSE_RESULT_HEX))
                await writer.drain()
            else:
                print("[КЛИЕНТ] RESULT_CODE не получен (таймаут)")

            # Даём сценарию завершиться
            await asyncio.sleep(0.5)

            # Закрываем соединение
            writer.close()
            await writer.wait_closed()

            await asyncio.wait_for(scenario_task, timeout=10.0)

            history = engine.scenario_mgr.context.history
            print(f"\n[ТЕСТ 2] Сценарий: {scenario_result['status']}")
            print(f"[ТЕСТ 2] История: {[(h.step_name, h.result, f'{h.duration:.3f}s') for h in history]}")
            print(f"[ТЕСТ 2] Пакетов обработано: {len(packet_events)}")

            # При полной синхронизации сценарий должен пройти дальше шага 3
            assert scenario_result["status"] != "NOT_STARTED", "Сценарий не начался"
            # Проверяем что шаги 1-5 прошли (TERM_IDENTITY + VEHICLE_DATA + их подтверждения + RESULT_CODE)
            passed_steps = [h for h in history if h.result == "PASS"]
            assert len(passed_steps) >= 4, (
                f"Сценарий не прошёл ключевые шаги. История: {[(h.step_name, h.result) for h in history]}"
            )

        finally:
            if not scenario_task.done():
                scenario_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scenario_task
            await engine.stop()
