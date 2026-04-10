"""Тесты CLI — парсинг аргументов (задача 9.1)."""

from __future__ import annotations

import pytest

from cli.app import build_parser


@pytest.fixture
def parser():
    return build_parser()


class TestStartCommand:
    """Тесты команды start."""

    def test_start_minimal(self, parser):
        """start без дополнительных параметров."""
        args = parser.parse_args(["start"])
        assert args.command == "start"
        assert args.port == 3001
        assert args.gost == "2015"
        assert args.cmw is None
        assert args.log_level == "INFO"

    def test_start_all_options(self, parser):
        """start со всеми параметрами."""
        args = parser.parse_args([
            "start", "--port", "8080", "--gost", "2015",
            "--cmw", "192.168.1.100", "--log-level", "DEBUG",
        ])
        assert args.command == "start"
        assert args.port == 8080
        assert args.gost == "2015"
        assert args.cmw == "192.168.1.100"
        assert args.log_level == "DEBUG"


class TestStopCommand:
    """Тесты команды stop."""

    def test_stop(self, parser):
        """stop без параметров."""
        args = parser.parse_args(["stop"])
        assert args.command == "stop"


class TestStatusCommand:
    """Тесты команды status."""

    def test_status(self, parser):
        """status без параметров."""
        args = parser.parse_args(["status"])
        assert args.command == "status"


class TestCmwStatusCommand:
    """Тесты команды cmw-status."""

    def test_cmw_status(self, parser):
        """cmw-status без параметров."""
        args = parser.parse_args(["cmw-status"])
        assert args.command == "cmw-status"


class TestRunScenarioCommand:
    """Тесты команды run-scenario."""

    def test_run_scenario_required(self, parser):
        """run-scenario требует путь к сценарию."""
        args = parser.parse_args(["run-scenario", "scenarios/auth/"])
        assert args.command == "run-scenario"
        assert args.scenario_path == "scenarios/auth/"
        assert args.connection_id is None

    def test_run_scenario_with_connection_id(self, parser):
        """run-scenario с connection_id."""
        args = parser.parse_args([
            "run-scenario", "scenarios/auth/", "--connection-id", "conn-123",
        ])
        assert args.command == "run-scenario"
        assert args.scenario_path == "scenarios/auth/"
        assert args.connection_id == "conn-123"


class TestReplayCommand:
    """Тесты команды replay."""

    def test_replay_required(self, parser):
        """replay требует путь к логу."""
        args = parser.parse_args(["replay", "logs/session.jsonl"])
        assert args.command == "replay"
        assert args.log_path == "logs/session.jsonl"
        assert args.scenario is None

    def test_replay_with_scenario(self, parser):
        """replay с опциональным сценарием."""
        args = parser.parse_args([
            "replay", "logs/session.jsonl", "--scenario", "scenarios/auth/",
        ])
        assert args.command == "replay"
        assert args.log_path == "logs/session.jsonl"
        assert args.scenario == "scenarios/auth/"


class TestBatchCommand:
    """Тесты команды batch."""

    def test_batch_single(self, parser):
        """batch с одним сценарием."""
        args = parser.parse_args(["batch", "--scenario", "auth"])
        assert args.command == "batch"
        assert args.scenarios == ["auth"]
        assert args.output is None

    def test_batch_multiple(self, parser):
        """batch с несколькими сценариями."""
        args = parser.parse_args([
            "batch", "--scenario", "auth", "--scenario", "telemetry",
            "--output", "report.json",
        ])
        assert args.command == "batch"
        assert args.scenarios == ["auth", "telemetry"]
        assert args.output == "report.json"


class TestExportCommand:
    """Тесты команды export."""

    def test_export_required(self, parser):
        """export требует type, format, output."""
        args = parser.parse_args([
            "export", "packets", "--format", "csv", "--output", "packets.csv",
        ])
        assert args.command == "export"
        assert args.data_type == "packets"
        assert args.format == "csv"
        assert args.output == "packets.csv"

    def test_export_json(self, parser):
        """export в JSON."""
        args = parser.parse_args([
            "export", "scenarios", "--format", "json", "--output", "report.json",
        ])
        assert args.command == "export"
        assert args.data_type == "scenarios"
        assert args.format == "json"


class TestMonitorCommand:
    """Тесты команды monitor."""

    def test_monitor(self, parser):
        """monitor без параметров."""
        args = parser.parse_args(["monitor"])
        assert args.command == "monitor"


class TestNoCommand:
    """Тесты отсутствия команды."""

    def test_no_args_command_is_none(self, parser):
        """Без аргументов command == None (помогает parser.print_help)."""
        args = parser.parse_args([])
        assert args.command is None


class TestEntryPoint:
    """Тесты точки входа main()."""

    def test_main_importable(self):
        """main() импортируется без ошибок."""
        from cli.app import main
        assert callable(main)
