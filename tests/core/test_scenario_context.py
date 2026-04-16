"""Tests for ScenarioContext — variables, TTL, substitution, connection_id resolution."""

import time
from unittest.mock import MagicMock

from core.scenario import ScenarioContext, Variable


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
