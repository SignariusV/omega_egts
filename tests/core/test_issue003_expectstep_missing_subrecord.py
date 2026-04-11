"""Тест подтверждения: ExpectStep FAIL из-за отсутствия subrecord_type в extra

Гипотеза: сценарий застревает на шаге 1 (ExpectStep: TERM_IDENTITY)
потому что checks требуют subrecord_type="EGTS_SR_TERM_IDENTITY",
но adapter.parse_packet() не заполняет subrecord_type (subrecords=[]).

Запуск::

    pytest tests/core/test_issue003_expectstep_missing_subrecord.py -v -s
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from core.event_bus import EventBus
from core.scenario import ExpectStep, ScenarioContext


@dataclass
class MockParsed:
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockPacketContext:
    parsed: MockParsed | None = None


class TestIssue003_ExpectStepMissingSubrecord:
    """Проверка что ExpectStep не PASS без subrecord_type."""

    @pytest.mark.asyncio
    async def test_expectstep_fails_without_subrecord_type(self) -> None:
        """ExpectStep с checks={"service": 1, "subrecord_type": "..."} не PASS если subrecord_type отсутствует."""
        event_bus = EventBus()
        step = ExpectStep(
            name="Test Expect",
            checks={"service": 1, "subrecord_type": "EGTS_SR_TERM_IDENTITY"},
            timeout=5.0,
        )
        ctx = ScenarioContext()

        execute_task = asyncio.create_task(step.execute(ctx, event_bus, timeout=2.0))
        await asyncio.sleep(0.1)

        # Эмитируем пакет как в реальности: service=1, но НЕТ subrecord_type
        mock_ctx = MockPacketContext(MockParsed(extra={"service": 1}))
        await event_bus.emit("packet.processed", {"ctx": mock_ctx, "channel": "tcp"})

        # Ждём timeout — ExpectStep не должен PASS
        result = await asyncio.wait_for(execute_task, timeout=5.0)

        assert result == "TIMEOUT", (
            f"Ожидался TIMEOUT (нет subrecord_type), но результат: {result}"
        )

    @pytest.mark.asyncio
    async def test_expectstep_passes_with_both_service_and_subrecord(self) -> None:
        """ExpectStep PASS когда есть и service, и subrecord_type."""
        event_bus = EventBus()
        step = ExpectStep(
            name="Test Expect",
            checks={"service": 1, "subrecord_type": "EGTS_SR_TERM_IDENTITY"},
            timeout=5.0,
        )
        ctx = ScenarioContext()

        execute_task = asyncio.create_task(step.execute(ctx, event_bus, timeout=2.0))
        await asyncio.sleep(0.1)

        # Полный extra — как должно быть
        mock_ctx = MockPacketContext(MockParsed(extra={
            "service": 1,
            "subrecord_type": "EGTS_SR_TERM_IDENTITY",
        }))
        await event_bus.emit("packet.processed", {"ctx": mock_ctx, "channel": "tcp"})

        result = await asyncio.wait_for(execute_task, timeout=5.0)

        assert result == "PASS", (
            f"Ожидался PASS, но результат: {result}"
        )

    @pytest.mark.asyncio
    async def test_expectstep_passes_with_service_only(self) -> None:
        """ExpectStep с checks={"service": 1} PASS без subrecord_type."""
        event_bus = EventBus()
        # Проверка только service (без subrecord_type)
        step = ExpectStep(
            name="Test Expect",
            checks={"service": 1},
            timeout=5.0,
        )
        ctx = ScenarioContext()

        execute_task = asyncio.create_task(step.execute(ctx, event_bus, timeout=2.0))
        await asyncio.sleep(0.1)

        mock_ctx = MockPacketContext(MockParsed(extra={"service": 1}))
        await event_bus.emit("packet.processed", {"ctx": mock_ctx, "channel": "tcp"})

        result = await asyncio.wait_for(execute_task, timeout=5.0)

        assert result == "PASS", (
            f"Ожидался PASS с проверкой только service, но результат: {result}"
        )
