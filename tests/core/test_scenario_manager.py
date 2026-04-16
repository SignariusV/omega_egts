"""Tests for ScenarioManager — загрузка и выполнение сценариев через parser_factory."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.scenario import ScenarioManager, ScenarioValidationError, StepFactory
from core.scenario_parser import ScenarioParserFactory, ScenarioParserRegistry, ScenarioParserV1


def _make_scenario(tmp_path: Path, data: dict) -> Path:
    """Создать scenario.json во временной директории."""
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return scenario_file


VALID_SCENARIO = {
    "scenario_version": "1",
    "name": "Test Scenario",
    "gost_version": "ГОСТ 33465-2015",
    "timeout": 30,
    "description": "Test",
    "steps": [
        {"name": "step1", "type": "expect", "channel": "tcp", "timeout": 5},
        {"name": "step2", "type": "send", "channel": "tcp", "timeout": 5},
    ],
}


class TestScenarioManagerLoad:
    """ScenarioManager.load — загрузка через parser_factory."""

    def test_load_valid_scenario(self, tmp_path: Path) -> None:
        """Загрузка валидного scenario.json."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)

        file = _make_scenario(tmp_path, VALID_SCENARIO)
        mgr = ScenarioManager(parser_factory=factory)
        mgr.load(file)

        assert mgr.metadata.name == "Test Scenario"
        assert len(mgr.steps) == 2

    def test_load_invalid_scenario_raises(self, tmp_path: Path) -> None:
        """Ошибка валидации → ScenarioValidationError."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)

        invalid = {"scenario_version": "1", "steps": [{"name": "s", "type": "invalid"}]}
        file = _make_scenario(tmp_path, invalid)
        mgr = ScenarioManager(parser_factory=factory)

        with pytest.raises(ScenarioValidationError):
            mgr.load(file)

    def test_load_unsupported_version_raises(self, tmp_path: Path) -> None:
        """Неподдерживаемая версия → NotImplementedError."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)

        data = {"scenario_version": "99", "steps": []}
        file = _make_scenario(tmp_path, data)
        mgr = ScenarioManager(parser_factory=factory)

        with pytest.raises(NotImplementedError):
            mgr.load(file)


class TestStepFactory:
    """StepFactory — создание шагов по типу."""

    def test_create_expect_step(self) -> None:
        """StepDefinition type='expect' → ExpectStep."""
        from core.scenario_parser import StepDefinition

        step_def = StepDefinition(
            name="test", type="expect", channel="tcp", timeout=5.0
        )
        step = StepFactory.create(step_def)
        assert type(step).__name__ == "ExpectStep"
        assert step.name == "test"
        assert step.channel == "tcp"

    def test_create_send_step(self) -> None:
        """StepDefinition type='send' → SendStep."""
        from core.scenario_parser import StepDefinition

        step_def = StepDefinition(
            name="test", type="send", channel="sms", timeout=10.0
        )
        step = StepFactory.create(step_def)
        assert type(step).__name__ == "SendStep"
        assert step.name == "test"
        assert step.channel == "sms"

    def test_create_wait_step(self) -> None:
        """StepDefinition type='wait' → NotImplementedError (пока не реализован)."""
        from core.scenario_parser import StepDefinition

        step_def = StepDefinition(
            name="test", type="wait", channel=None, timeout=5.0
        )
        with pytest.raises(NotImplementedError):
            StepFactory.create(step_def)

    def test_create_unknown_step_raises(self) -> None:
        """Unknown type → NotImplementedError."""
        from core.scenario_parser import StepDefinition

        step_def = StepDefinition(
            name="test", type="unknown", channel=None, timeout=5.0
        )
        with pytest.raises(NotImplementedError):
            StepFactory.create(step_def)


class TestScenarioManagerExecute:
    """ScenarioManager.execute — выполнение шагов."""

    @pytest.mark.asyncio
    async def test_execute_all_pass(self, tmp_path: Path) -> None:
        """Все шаги PASS → результат PASS."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)

        # Сценарий с expect шагом
        data = {
            "scenario_version": "1",
            "name": "Test",
            "steps": [
                {"name": "step1", "type": "expect", "channel": "tcp"},
            ],
        }
        file = _make_scenario(tmp_path, data)
        mgr = ScenarioManager(parser_factory=factory)
        mgr.load(file)

        # Мок EventBus
        from core.event_bus import EventBus

        bus = EventBus()

        # Симуляция: packet приходит сразу
        async def emit_packet() -> None:

            parsed_mock = MagicMock()
            parsed_mock.extra = {"service": 1}
            ctx_mock = MagicMock()
            ctx_mock.parsed = parsed_mock
            await bus.emit(
                "packet.processed",
                {"ctx": ctx_mock, "connection_id": "conn-1", "channel": "tcp"},
            )

        import asyncio

        task = asyncio.create_task(emit_packet())
        result = await mgr.execute(bus, connection_id="conn-1")
        await task

        assert result == "PASS"
        assert mgr.context.all_passed()

    @pytest.mark.asyncio
    async def test_execute_step_fail(self, tmp_path: Path) -> None:
        """Шаг не проходит → результат FAIL."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)

        data = {
            "scenario_version": "1",
            "name": "Test",
            "steps": [
                {"name": "step1", "type": "expect", "channel": "tcp", "checks": {"service": 99}},
            ],
        }
        file = _make_scenario(tmp_path, data)
        mgr = ScenarioManager(parser_factory=factory)
        mgr.load(file)

        from core.event_bus import EventBus

        bus = EventBus()

        # Пакет не совпадает с checks → TIMEOUT
        result = await mgr.execute(bus, connection_id="conn-1", timeout=0.1)
        assert result == "TIMEOUT"
