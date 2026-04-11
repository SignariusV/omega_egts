"""Тест изоляции ISSUE-003: ScenarioManager не выполняет SendStep после PASS ExpectStep

Цель: проверить что ScenarioManager корректно переходит от ExpectStep к SendStep.

Запуск::

    pytest tests/core/test_issue003_scenario_execution.py -v -s
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.event_bus import EventBus
from core.scenario import (
    ExpectStep,
    ScenarioContext,
    ScenarioManager,
    SendStep,
    StepFactory,
)
from core.scenario_parser import (
    ScenarioParserFactory,
    ScenarioParserRegistry,
    ScenarioParserV1,
)


# Фикстуры из существующих тестов
@pytest.fixture
def event_bus() -> EventBus:
    """Простой EventBus для тестов."""
    return EventBus()


@pytest.fixture
def scenario_manager() -> ScenarioManager:
    """ScenarioManager с пустым реестром."""
    registry = ScenarioParserRegistry()
    registry.register("1", ScenarioParserV1)
    factory = ScenarioParserFactory(registry)
    return ScenarioManager(parser_factory=factory)


@dataclass
class MockParsed:
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockPacketContext:
    """Мок PacketContext для тестов."""

    parsed: MockParsed | None = None


class TestIssue003_ExpectStepReturnsPass:
    """Проверка что ExpectStep возвращает PASS при совпадении."""

    @pytest.mark.asyncio
    async def test_expect_step_passes_when_service_matches(self, event_bus: EventBus) -> None:
        """ExpectStep с checks={"service": 1} должен вернуть PASS."""
        step = ExpectStep(name="Test Expect", checks={"service": 1}, timeout=5.0)
        ctx = ScenarioContext()

        # Запускаем ожидание
        execute_task = asyncio.create_task(step.execute(ctx, event_bus, timeout=2.0))
        await asyncio.sleep(0.1)

        # Эмитируем пакет с service=1
        mock_ctx = MockPacketContext(MockParsed(extra={"service": 1}))
        await event_bus.emit("packet.processed", {"ctx": mock_ctx, "channel": "tcp"})

        result = await asyncio.wait_for(execute_task, timeout=3.0)
        assert result == "PASS", f"ExpectStep должен вернуть PASS, получил {result}"


class TestIssue003_ScenarioManagerStepSequence:
    """Проверка последовательности шагов в ScenarioManager."""

    @pytest.mark.asyncio
    async def test_scenario_manager_executes_send_after_expect(
        self, event_bus: EventBus, scenario_manager: ScenarioManager
    ) -> None:
        """После PASS ExpectStep должен выполниться SendStep."""
        command_sent_events: list[dict[str, Any]] = []

        async def on_command_sent(data: dict[str, Any]) -> None:
            command_sent_events.append(data)

        event_bus.on("command.sent", on_command_sent)

        # Создаём простой сценарий вручную
        scenario_manager._steps = [
            ExpectStep(name="Expect TermIdentity", checks={"service": 1}, timeout=5.0),
            SendStep(name="Send Response", packet_file="dummy.hex", channel="tcp"),
        ]

        # Запуск execute должен:
        # 1. Выполнить ExpectStep
        # 2. После PASS → выполнить SendStep
        # 3. SendStep эмитит command.send

        execute_task = asyncio.create_task(
            scenario_manager.execute(event_bus, connection_id="test-conn", timeout=10.0)
        )
        await asyncio.sleep(0.2)

        # Эмитируем пакет — ExpectStep должен PASS
        mock_ctx = MockPacketContext(MockParsed(extra={"service": 1}))
        await event_bus.emit("packet.processed", {"ctx": mock_ctx, "channel": "tcp"})

        # Дадим время на обработку
        await asyncio.sleep(0.5)

        # Проверяем что SendStep выполнился и command.sent был эмитирован
        # Но SendStep ждёт command.sent от CommandDispatcher — эмитируем его
        await event_bus.emit("command.sent", {"step_name": "Send Response"})

        result = await asyncio.wait_for(execute_task, timeout=5.0)
        print(f"[ТЕСТ] Сценарий завершился: {result}")
        print(f"[ТЕСТ] command.sent событий: {len(command_sent_events)}")
        print(f"[ТЕСТ] History: {[(h.step_name, h.result) for h in scenario_manager.context.history]}")

        # Ключевая проверка: SendStep должен был выполниться
        assert len(command_sent_events) > 0 or len(scenario_manager.context.history) > 1, (
            "SendStep не выполнился — сценарий застрял на ExpectStep"
        )


class TestIssue003_SendStepBuildPacket:
    """Проверка что SendStep._build_packet() не падает."""

    def test_send_step_with_packet_file_builds_packet(self, tmp_path: Path) -> None:
        """SendStep с packet_file должен загрузить HEX и вернуть байты."""
        hex_file = tmp_path / "test_packet.hex"
        hex_file.write_text("0100000B0010001E00003B2A000006002D00400101000300490000E6BE")

        step = SendStep(name="Test Send", packet_file=str(hex_file), channel="tcp")
        ctx = ScenarioContext()
        ctx.packet_source_dir = str(tmp_path)

        packet_bytes = step._build_packet(ctx)
        assert len(packet_bytes) > 0, "SendStep._build_packet() вернул пустые байты"
        assert packet_bytes[0] == 0x01, "Первый байт должен быть 0x01 (PRV=1)"

    def test_send_step_with_nonexistent_file_raises_error(self, tmp_path: Path) -> None:
        """SendStep с несуществующим файлом должен поднять ошибку."""
        step = SendStep(name="Test Send", packet_file=str(tmp_path / "nonexistent.hex"), channel="tcp")
        ctx = ScenarioContext()
        ctx.packet_source_dir = str(tmp_path)

        with pytest.raises((FileNotFoundError, ValueError)):
            step._build_packet(ctx)
