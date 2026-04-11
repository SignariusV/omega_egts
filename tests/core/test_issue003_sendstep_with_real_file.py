"""Тест изоляции ISSUE-003: SendStep с реальным файлом

Проверяет что SendStep с существующим HEX-файлом эмитит command.send
и возвращает PASS.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from core.event_bus import EventBus
from core.scenario import (
    ExpectStep,
    ScenarioContext,
    ScenarioManager,
    SendStep,
)
from core.scenario_parser import (
    ScenarioParserFactory,
    ScenarioParserRegistry,
    ScenarioParserV1,
)
from tests.core.test_issue003_scenario_execution import MockPacketContext, MockParsed


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def scenario_manager() -> ScenarioManager:
    registry = ScenarioParserRegistry()
    registry.register("1", ScenarioParserV1)
    factory = ScenarioParserFactory(registry)
    return ScenarioManager(parser_factory=factory)


class TestIssue003_SendStepWithRealFile:
    """Проверка SendStep с реальным HEX-файлом."""

    @pytest.mark.asyncio
    async def test_send_step_with_existing_file_emits_command_send(
        self, event_bus: EventBus, scenario_manager: ScenarioManager
    ) -> None:
        """SendStep с существующим packet_file должен эмитить command.send."""
        command_send_events: list[dict[str, Any]] = []
        command_sent_events: list[dict[str, Any]] = []

        async def on_command_send(data: dict[str, Any]) -> None:
            command_send_events.append(data)
            # Эмитируем command.sent чтобы SendStep завершился PASS
            asyncio.get_event_loop().create_task(
                event_bus.emit("command.sent", {"step_name": data.get("step_name", "")})
            )

        async def on_command_sent(data: dict[str, Any]) -> None:
            command_sent_events.append(data)

        event_bus.on("command.send", on_command_send)
        event_bus.on("command.sent", on_command_sent)

        # Путь к реальному HEX-файлу
        hex_path = Path("scenarios/auth/packets/platform/record_response_term_identity.hex")
        assert hex_path.exists(), f"HEX файл должен существовать: {hex_path}"

        scenario_manager._steps = [
            ExpectStep(name="Expect TermIdentity", checks={"service": 1}, timeout=5.0),
            SendStep(name="Send Response", packet_file=str(hex_path.resolve()), channel="tcp"),
        ]

        # Запуск сценария
        execute_task = asyncio.create_task(
            scenario_manager.execute(event_bus, connection_id="test-conn", timeout=10.0)
        )
        await asyncio.sleep(0.2)

        # Эмитируем пакет — ExpectStep должен PASS
        mock_ctx = MockPacketContext(MockParsed(extra={"service": 1}))
        await event_bus.emit("packet.processed", {"ctx": mock_ctx, "channel": "tcp"})

        # Ждём завершения
        result = await asyncio.wait_for(execute_task, timeout=10.0)

        print(f"[ТЕСТ] Сценарий: {result}")
        print(f"[ТЕСТ] command.send: {len(command_send_events)}")
        print(f"[ТЕСТ] command.sent: {len(command_sent_events)}")
        print(f"[ТЕСТ] History: {[(h.step_name, h.result) for h in scenario_manager.context.history]}")

        if command_send_events:
            print(f"[ТЕСТ] command.send data: {command_send_events[0].keys()}")

        assert len(command_send_events) == 1, (
            f"SendStep должен эмитить command.send, но эмитов: {len(command_send_events)}"
        )
        assert len(command_sent_events) == 1, (
            f"SendStep должен получить command.sent, но получено: {len(command_sent_events)}"
        )

        history = scenario_manager.context.history
        assert len(history) == 2, f"Должно быть 2 шага в истории, но: {len(history)}"
        assert history[0].result == "PASS", f"ExpectStep должен PASS: {history[0].result}"
        assert history[1].result == "PASS", f"SendStep должен PASS: {history[1].result}"
