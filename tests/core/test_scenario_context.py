"""Tests for ScenarioContext — variables, TTL, substitution, connection_id resolution."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.scenario import ScenarioContext, ScenarioManager, Variable
from core.scenario_parser import ScenarioParserFactory, ScenarioParserRegistry, ScenarioParserV1


class TestVariable:
    """Variable dataclass with TTL."""

    def test_variable_is_not_expired(self) -> None:
        """Variable with TTL in the future is not expired."""
        var = Variable(value="test", ttl=10.0, created_at=time.time())
        assert not var.is_expired

    def test_variable_is_expired(self) -> None:
        """Variable with TTL in the past is expired."""
        var = Variable(value="test", ttl=0.1, created_at=time.time() - 1.0)
        assert var.is_expired

    def test_variable_without_ttl_never_expires(self) -> None:
        """Variable without TTL (None) never expires."""
        var = Variable(value="test", ttl=None, created_at=time.time() - 1000.0)
        assert not var.is_expired


class TestScenarioContextVariables:
    """ScenarioContext variable management."""

    def test_set_and_get_variable(self) -> None:
        """Set and get variable."""
        ctx = ScenarioContext()
        ctx.set("tid", 12345)
        assert ctx.get("tid") == 12345

    def test_get_nonexistent_variable_returns_none(self) -> None:
        """Get nonexistent variable returns None."""
        ctx = ScenarioContext()
        assert ctx.get("missing") is None

    def test_variable_ttl_expires(self) -> None:
        """Variable TTL expires correctly."""
        ctx = ScenarioContext()
        ctx.set("temp", "value", ttl=0.1)
        assert ctx.get("temp") == "value"
        time.sleep(0.15)
        assert ctx.get("temp") is None  # expired

    def test_overwrite_variable(self) -> None:
        """Overwrite existing variable."""
        ctx = ScenarioContext()
        ctx.set("tid", 12345)
        ctx.set("tid", 67890)
        assert ctx.get("tid") == 67890


class TestScenarioContextSubstitution:
    """ScenarioContext template substitution {{var}}."""

    def test_substitute_single_variable(self) -> None:
        """Substitute single {{var}}."""
        ctx = ScenarioContext()
        ctx.set("tid", 12345)
        result = ctx.substitute("TID={{tid}}")
        assert result == "TID=12345"

    def test_substitute_multiple_variables(self) -> None:
        """Substitute multiple {{var}}."""
        ctx = ScenarioContext()
        ctx.set("tid", 12345)
        ctx.set("imei", "ABCDEF")
        result = ctx.substitute("TID={{tid}}, IMEI={{imei}}")
        assert result == "TID=12345, IMEI=ABCDEF"

    def test_substitute_missing_variable_keeps_placeholder(self) -> None:
        """Missing variable keeps placeholder."""
        ctx = ScenarioContext()
        result = ctx.substitute("{{missing}}")
        assert result == "{{missing}}"

    def test_substitute_with_complex_template(self) -> None:
        """Substitute with complex template."""
        ctx = ScenarioContext()
        ctx.set("service", 2)
        ctx.set("token", "abc123")
        template = "service={{service}}, token={{token}}, extra={{none}}"
        result = ctx.substitute(template)
        assert "service=2" in result
        assert "token=abc123" in result
        assert "{{none}}" in result


class TestScenarioContextConnection:
    """ScenarioContext connection_id resolution."""

    def test_resolve_connection_id_explicit(self) -> None:
        """Explicit connection_id takes priority."""
        ctx = ScenarioContext()
        ctx.connection_id = "conn-123"
        result = ctx._resolve_connection_id("conn-456")
        assert result == "conn-123"

    def test_resolve_connection_id_from_step(self) -> None:
        """Step connection_id used when ctx is None."""
        ctx = ScenarioContext()
        ctx.connection_id = None
        result = ctx._resolve_connection_id("conn-456")
        assert result == "conn-456"

    def test_resolve_connection_id_none(self) -> None:
        """None when both are None."""
        ctx = ScenarioContext()
        ctx.connection_id = None
        result = ctx._resolve_connection_id(None)
        assert result is None


class TestScenarioContextHistory:
    """ScenarioContext execution history."""

    def test_add_step_result(self) -> None:
        """Add step result to history."""
        ctx = ScenarioContext()
        ctx.add_history("step1", "PASS")
        assert len(ctx.history) == 1
        assert ctx.history[0].step_name == "step1"
        assert ctx.history[0].result == "PASS"

    def test_add_multiple_step_results(self) -> None:
        """Add multiple step results."""
        ctx = ScenarioContext()
        ctx.add_history("step1", "PASS")
        ctx.add_history("step2", "FAIL")
        assert len(ctx.history) == 2

    def test_all_steps_passed(self) -> None:
        """all_passed() returns True when all steps PASS."""
        ctx = ScenarioContext()
        ctx.add_history("step1", "PASS")
        ctx.add_history("step2", "PASS")
        assert ctx.all_passed()

    def test_all_steps_failed(self) -> None:
        """all_passed() returns False when any step fails."""
        ctx = ScenarioContext()
        ctx.add_history("step1", "PASS")
        ctx.add_history("step2", "FAIL")
        assert not ctx.all_passed()


class TestScenarioContextMetadata:
    """ScenarioContext metadata fields."""

    def test_scenario_version(self) -> None:
        """scenario_version is set."""
        ctx = ScenarioContext(scenario_version="1")
        assert ctx.scenario_version == "1"

    def test_gost_version(self) -> None:
        """gost_version is set."""
        ctx = ScenarioContext(gost_version="ГОСТ 33465-2015")
        assert ctx.gost_version == "ГОСТ 33465-2015"

    def test_parser_reference(self) -> None:
        """parser reference can be set."""
        ctx = ScenarioContext()
        mock_parser = MagicMock()
        ctx.parser = mock_parser
        assert ctx.parser is mock_parser


class TestScenarioContextAutoIncrement:
    """ScenarioContext auto-increment variables."""

    def test_simple_variable_not_auto_incremented(self) -> None:
        """Обычная переменная не инкрементится."""
        ctx = ScenarioContext()
        ctx.set("pid", 100)
        assert ctx.get("pid") == 100
        assert ctx.get("pid") == 100

    def test_auto_increment_increases_on_each_get(self) -> None:
        """auto_increment=True: каждое чтение увеличивает на 1."""
        ctx = ScenarioContext()
        ctx.set("pid", 100, auto_increment=True)
        assert ctx.get("pid") == 100
        assert ctx.get("pid") == 101
        assert ctx.get("pid") == 102

    def test_auto_increment_substitute(self) -> None:
        """Подстановка auto-increment переменной через шаблон."""
        ctx = ScenarioContext()
        ctx.set("pid", 100, auto_increment=True)
        assert ctx.substitute("{{pid}}") == "100"
        assert ctx.substitute("{{pid}}") == "101"
        assert ctx.substitute("{{pid}}") == "102"

    def test_multiple_auto_increment_variables(self) -> None:
        """Несколько auto-increment переменных независимы."""
        ctx = ScenarioContext()
        ctx.set("pid", 100, auto_increment=True)
        ctx.set("rid", 200, auto_increment=True)
        assert ctx.get("pid") == 100
        assert ctx.get("rid") == 200
        assert ctx.get("pid") == 101
        assert ctx.get("rid") == 201

    def test_auto_increment_mixed_with_static(self) -> None:
        """auto-increment и статические переменные вместе."""
        ctx = ScenarioContext()
        ctx.set("pid", 100, auto_increment=True)
        ctx.set("service", 4)
        assert ctx.get("pid") == 100
        assert ctx.get("service") == 4
        assert ctx.get("pid") == 101
        assert ctx.get("service") == 4


class TestScenarioManagerVariables:
    """ScenarioManager.load — загрузка variables с auto_increment."""

    @pytest.fixture
    def factory(self) -> ScenarioParserFactory:
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        return ScenarioParserFactory(registry)

    def _make_scenario(self, tmp_path: Path, data: dict) -> Path:
        scenario_file = tmp_path / "scenario.json"
        scenario_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return scenario_file

    def test_load_simple_variables(self, tmp_path: Path, factory: ScenarioParserFactory) -> None:
        """Загрузка простых переменных (старый формат)."""
        data = {
            "scenario_version": "1",
            "name": "Test",
            "steps": [{"name": "s1", "type": "send", "channel": "tcp", "timeout": 5}],
            "variables": {"tid": 123, "imei": "abc"},
        }
        mgr = ScenarioManager(parser_factory=factory)
        mgr.load(self._make_scenario(tmp_path, data))
        assert mgr.context.get("tid") == 123
        assert mgr.context.get("imei") == "abc"

    def test_load_auto_increment_variables(self, tmp_path: Path, factory: ScenarioParserFactory) -> None:
        """Загрузка переменных с auto_increment (новый формат)."""
        data = {
            "scenario_version": "1",
            "name": "Test",
            "steps": [{"name": "s1", "type": "send", "channel": "tcp", "timeout": 5}],
            "variables": {
                "pid": {"start": 100, "auto": True},
                "rid": {"start": 200, "auto": True},
            },
        }
        mgr = ScenarioManager(parser_factory=factory)
        mgr.load(self._make_scenario(tmp_path, data))

        assert mgr.context.get("pid") == 100
        assert mgr.context.get("pid") == 101
        assert mgr.context.get("rid") == 200
        assert mgr.context.get("rid") == 201

    def test_load_mixed_variables(self, tmp_path: Path, factory: ScenarioParserFactory) -> None:
        """Смешанный формат: простые и auto-increment переменные."""
        data = {
            "scenario_version": "1",
            "name": "Test",
            "steps": [{"name": "s1", "type": "send", "channel": "tcp", "timeout": 5}],
            "variables": {
                "pid": {"start": 27, "auto": True},
                "rid": {"start": 42, "auto": True},
                "service_type": 4,
                "unit_id_hex": "00000001",
            },
        }
        mgr = ScenarioManager(parser_factory=factory)
        mgr.load(self._make_scenario(tmp_path, data))

        assert mgr.context.get("pid") == 27
        assert mgr.context.get("rid") == 42
        assert mgr.context.get("service_type") == 4
        assert mgr.context.get("unit_id_hex") == "00000001"
        assert mgr.context.get("pid") == 28
        assert mgr.context.get("rid") == 43
