"""Tests for ScenarioParser abstraction — Protocol, V1 parser, Registry, Factory."""

import pytest

from core.scenario_parser import (
    IScenarioParser,
    ScenarioMetadata,
    ScenarioParserFactory,
    ScenarioParserRegistry,
    ScenarioParserV1,
)

VALID_SCENARIO_V1 = {
    "scenario_version": "1",
    "name": "Test Scenario",
    "gost_version": "ГОСТ 33465-2015",
    "timeout": 30,
    "description": "Test description",
    "channels": ["tcp", "sms"],
    "steps": [
        {
            "name": "step1",
            "type": "send",
            "channel": "tcp",
            "packet_file": "packets/test.hex",
            "timeout": 10,
        },
        {
            "name": "step2",
            "type": "expect",
            "channel": "sms",
            "timeout": 15,
            "checks": {"service": 1},
            "capture": {"tid": "data.TID"},
        },
    ],
}


# --- IScenarioParser Protocol ---


class TestIScenarioParserProtocol:
    """IScenarioParser Protocol interface."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol is @runtime_checkable."""
        parser = ScenarioParserV1()
        assert isinstance(parser, IScenarioParser)

    def test_protocol_requires_load_method(self) -> None:
        """Protocol requires load() method."""
        assert hasattr(IScenarioParser, "load")

    def test_protocol_requires_validate_method(self) -> None:
        """Protocol requires validate() method."""
        assert hasattr(IScenarioParser, "validate")

    def test_protocol_requires_get_steps_method(self) -> None:
        """Protocol requires get_steps() method."""
        assert hasattr(IScenarioParser, "get_steps")

    def test_protocol_requires_get_metadata_method(self) -> None:
        """Protocol requires get_metadata() method."""
        assert hasattr(IScenarioParser, "get_metadata")


# --- ScenarioParserV1: Validation ---


class TestScenarioParserV1Validate:
    """ScenarioParserV1 validation logic."""

    def test_valid_scenario_returns_empty_errors(self) -> None:
        """Valid scenario.json returns 0 errors."""
        parser = ScenarioParserV1()
        errors, warnings = parser.validate(VALID_SCENARIO_V1)
        assert errors == []

    def test_missing_steps_returns_error(self) -> None:
        """Missing 'steps' returns error."""
        parser = ScenarioParserV1()
        data = {"scenario_version": "1", "name": "Test"}
        errors, _ = parser.validate(data)
        assert any("steps" in e for e in errors)

    def test_step_without_type_returns_error(self) -> None:
        """Step without 'type' returns error."""
        parser = ScenarioParserV1()
        data = {
            "scenario_version": "1",
            "steps": [{"name": "step1"}],
        }
        errors, _ = parser.validate(data)
        assert any("type" in e for e in errors)

    def test_invalid_step_type_returns_error(self) -> None:
        """Invalid step type (not send/expect/wait/check) returns error."""
        parser = ScenarioParserV1()
        data = {
            "scenario_version": "1",
            "steps": [{"name": "step1", "type": "invalid"}],
        }
        errors, _ = parser.validate(data)
        assert any("type" in e for e in errors)

    def test_invalid_channel_returns_error(self) -> None:
        """Invalid channel (not tcp/sms) returns error."""
        parser = ScenarioParserV1()
        data = {
            "scenario_version": "1",
            "steps": [{"name": "step1", "type": "send", "channel": "udp"}],
        }
        errors, _ = parser.validate(data)
        assert any("channel" in e for e in errors)

    def test_none_channel_is_valid(self) -> None:
        """None channel is valid (channel-agnostic step)."""
        parser = ScenarioParserV1()
        data = {
            "scenario_version": "1",
            "steps": [{"name": "step1", "type": "wait", "timeout": 5}],
        }
        errors, _ = parser.validate(data)
        assert not any("channel" in e for e in errors)

    def test_missing_timeout_returns_warning(self) -> None:
        """Missing timeout returns warning (default applied)."""
        parser = ScenarioParserV1()
        data = {
            "scenario_version": "1",
            "steps": [{"name": "step1", "type": "expect"}],
        }
        errors, warnings = parser.validate(data)
        assert errors == []
        assert any("timeout" in w.lower() for w in warnings)

    def test_duplicate_step_names_returns_warning(self) -> None:
        """Duplicate step names return warning."""
        parser = ScenarioParserV1()
        data = {
            "scenario_version": "1",
            "steps": [
                {"name": "dup", "type": "send"},
                {"name": "dup", "type": "expect"},
            ],
        }
        errors, warnings = parser.validate(data)
        assert errors == []
        assert any("duplicate" in w.lower() for w in warnings)

    def test_valid_step_types(self) -> None:
        """Valid step types: send, expect, wait, check."""
        parser = ScenarioParserV1()
        for step_type in ("send", "expect", "wait", "check"):
            data = {
                "scenario_version": "1",
                "steps": [{"name": f"s{step_type}", "type": step_type}],
            }
            errors, _ = parser.validate(data)
            assert not any(step_type in e for e in errors)

    def test_valid_channels(self) -> None:
        """Valid channels: tcp, sms, None."""
        parser = ScenarioParserV1()
        for channel in ("tcp", "sms", None):
            data = {
                "scenario_version": "1",
                "steps": [{"name": "s1", "type": "send", "channel": channel}],
            }
            errors, _ = parser.validate(data)
            assert not any("channel" in e for e in errors)


# --- ScenarioParserV1: Parsing ---


class TestScenarioParserV1Parse:
    """ScenarioParserV1 parsing logic."""

    def test_load_extracts_metadata(self) -> None:
        """Load extracts name, version, gost_version, timeout, description, channels."""
        parser = ScenarioParserV1()
        metadata = parser.load(VALID_SCENARIO_V1)
        assert metadata.name == "Test Scenario"
        assert metadata.version == "1"
        assert metadata.gost_version == "ГОСТ 33465-2015"
        assert metadata.timeout == 30
        assert metadata.description == "Test description"
        assert metadata.channels == ["tcp", "sms"]

    def test_load_parses_steps(self) -> None:
        """Load parses steps with all fields."""
        parser = ScenarioParserV1()
        parser.load(VALID_SCENARIO_V1)
        steps = parser.get_steps()
        assert len(steps) == 2

        step1 = steps[0]
        assert step1.name == "step1"
        assert step1.type == "send"
        assert step1.channel == "tcp"
        assert step1.packet_file == "packets/test.hex"
        assert step1.timeout == 10

        step2 = steps[1]
        assert step2.name == "step2"
        assert step2.type == "expect"
        assert step2.channel == "sms"
        assert step2.checks == {"service": 1}
        assert step2.capture == {"tid": "data.TID"}
        assert step2.timeout == 15

    def test_capture_nested_paths(self) -> None:
        """Capture paths support nested paths like records[0].fields.RN."""
        parser = ScenarioParserV1()
        data = {
            "scenario_version": "1",
            "steps": [
                {
                    "name": "capture_test",
                    "type": "expect",
                    "capture": {
                        "rn": "records[0].fields.RN",
                        "tid": "data.TID",
                    },
                },
            ],
        }
        parser.load(data)
        steps = parser.get_steps()
        assert steps[0].capture["rn"] == "records[0].fields.RN"

    def test_optional_fields_defaults(self) -> None:
        """Optional fields default to None."""
        parser = ScenarioParserV1()
        data = {
            "scenario_version": "1",
            "steps": [{"name": "s1", "type": "wait"}],
        }
        parser.load(data)
        steps = parser.get_steps()
        assert steps[0].channel is None
        assert steps[0].checks == {}
        assert steps[0].capture == {}
        assert steps[0].packet_file is None
        assert steps[0].build is None
        assert steps[0].timeout is None

    def test_get_metadata_returns_scenario_metadata(self) -> None:
        """get_metadata() returns ScenarioMetadata after load."""
        parser = ScenarioParserV1()
        parser.load(VALID_SCENARIO_V1)
        metadata = parser.get_metadata()
        assert isinstance(metadata, ScenarioMetadata)
        assert metadata.name == "Test Scenario"


# --- ScenarioParserRegistry ---


class TestScenarioParserRegistry:
    """ScenarioParserRegistry — version → parser registration."""

    def test_register_and_get(self) -> None:
        """Register parser class, retrieve by version."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        parser_cls = registry.get("1")
        assert parser_cls is ScenarioParserV1

    def test_get_unregistered_version_raises_keyerror(self) -> None:
        """Get unregistered version raises KeyError."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        with pytest.raises(KeyError):
            registry.get("99")

    def test_iterate_all_versions(self) -> None:
        """Iterate over all registered versions."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        registry.register("2", ScenarioParserV1)
        versions = {v for v, _ in registry}
        assert versions == {"1", "2"}

    def test_default_registry_has_v1(self) -> None:
        """Default registry has V1 pre-registered."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        parser_cls = registry.get("1")
        assert parser_cls is ScenarioParserV1


# --- ScenarioParserFactory ---


class TestScenarioParserFactory:
    """ScenarioParserFactory — create parser by version or detect from data."""

    def test_create_version_1_returns_v1_parser(self) -> None:
        """create('1') returns ScenarioParserV1 instance."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)
        parser = factory.create("1")
        assert isinstance(parser, ScenarioParserV1)

    def test_create_unsupported_version_raises_not_implemented(self) -> None:
        """create('2') raises NotImplementedError (not yet implemented)."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)
        with pytest.raises(NotImplementedError):
            factory.create("2")

    def test_detect_and_create_from_data(self) -> None:
        """detect_and_create() reads scenario_version from data."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)
        parser = factory.detect_and_create(VALID_SCENARIO_V1)
        assert isinstance(parser, ScenarioParserV1)

    def test_detect_and_create_missing_version_uses_v1(self) -> None:
        """detect_and_create() defaults to '1' if scenario_version missing."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)
        data = {"name": "Test", "steps": [{"name": "s1", "type": "send"}]}
        parser = factory.detect_and_create(data)
        assert isinstance(parser, ScenarioParserV1)

    def test_detect_and_create_unknown_version_raises(self) -> None:
        """detect_and_create() raises for unknown version."""
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)
        data = {"scenario_version": "99", "steps": []}
        with pytest.raises(NotImplementedError):
            factory.detect_and_create(data)
