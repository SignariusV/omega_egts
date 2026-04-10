"""Тесты CLI REPL — EGTSTesterCLI (задача 9.2)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.app import EGTSTesterCLI


def _mock_core_engine():
    """Создать мок CoreEngine."""
    engine = MagicMock()
    engine.is_running = False
    engine.start = AsyncMock()
    engine.stop = AsyncMock()
    engine.get_status = AsyncMock(return_value={
        "running": True, "port": 3001, "gost_version": "2015",
        "tcp_server": "running", "cmw500": "disconnected",
        "session_mgr": True, "log_mgr": True, "scenario_mgr": True,
    })
    engine.cmw_status = AsyncMock(return_value={
        "connected": False, "error": "CMW-500 не инициализирован",
    })
    engine.run_scenario = AsyncMock(return_value={
        "name": "auth", "status": "PASS",
        "steps_total": 3, "steps_passed": 3,
    })
    engine.replay = AsyncMock(return_value={
        "processed": 10, "skipped_duplicates": 2,
    })
    engine.export = AsyncMock(return_value={
        "rows": 5, "file": "out.csv",
    })
    return engine


def _mock_config():
    """Создать мок Config."""
    cfg = MagicMock()
    cfg.gost_version = "2015"
    cfg.tcp_port = 3001
    cfg.cmw500.ip = None
    cfg.logging.level = "INFO"
    cfg.timeouts = MagicMock()
    cfg.timeouts.egts_sl_not_auth_to = 6.0
    return cfg


@pytest.fixture
def repl():
    """Создать REPL без engine."""
    cli = EGTSTesterCLI()
    # Переопределяем _run чтобы не блокировал REPL тесты
    cli._run = MagicMock(side_effect=lambda coro: asyncio.get_event_loop().run_until_complete(coro))
    return cli


@pytest.fixture
def repl_with_engine():
    """Создать REPL с моком engine."""
    cli = EGTSTesterCLI()
    engine = _mock_core_engine()
    cli._engine = engine
    cli._config = _mock_config()
    cli._run = MagicMock(side_effect=lambda coro: asyncio.get_event_loop().run_until_complete(coro))
    return cli


class TestEnsureEngine:
    """Тесты _ensure_engine()."""

    def test_creates_engine_if_none(self):
        """_ensure_engine создаёт engine если None."""
        cli = EGTSTesterCLI()
        assert cli._engine is None

        cli._ensure_engine()

        assert cli._engine is not None
        assert cli._config is not None
        assert cli._bus is not None

    def test_does_not_recreate_if_exists(self):
        """_ensure_engine не пересоздаёт существующий engine."""
        cli = EGTSTesterCLI()
        cli._ensure_engine()
        first_engine = cli._engine

        cli._ensure_engine()

        assert cli._engine is first_engine


class TestDoStart:
    """Тесты команды REPL: start."""

    def test_start_default_args(self, repl):
        """start без параметров — порт 3001, ГОСТ 2015."""
        # do_start вызывает _engine.start() — мокнём чтобы не блокировать
        repl._run = MagicMock()

        repl.do_start("")

        assert repl._engine is not None
        assert repl._engine.config.tcp_port == 3001
        assert repl._engine.config.gost_version == "2015"
        repl._run.assert_called_once()

    def test_start_with_port(self, repl):
        """start --port 8080 — создаёт engine с портом 8080."""
        repl._run = MagicMock()

        repl.do_start("--port 8080")

        assert repl._engine is not None
        assert repl._engine.config.tcp_port == 8080

    def test_start_with_gost(self, repl):
        """start --gost 2023 — создаёт engine с ГОСТ 2023."""
        repl._run = MagicMock()

        repl.do_start("--gost 2023")

        assert repl._engine is not None
        assert repl._engine.config.gost_version == "2023"

    def test_start_with_cmw(self, repl):
        """start --cmw 192.168.1.100 — создаёт engine с CMW."""
        repl._run = MagicMock()

        repl.do_start("--cmw 192.168.1.100")

        assert repl._engine is not None
        assert repl._engine.config.cmw500.ip == "192.168.1.100"

    def test_start_already_running(self, repl_with_engine, capsys):
        """start когда сервер уже запущен — сообщение."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_start("")

        captured = capsys.readouterr()
        assert "уже запущен" in captured.out
        repl_with_engine._engine.start.assert_not_awaited()

    def test_start_recreates_engine(self, repl):
        """start после stop создаёт новый engine."""
        repl._run = MagicMock()
        repl.do_start("--port 9090")
        first_engine = repl._engine

        repl._engine.stop = AsyncMock()
        repl._engine._started = False  # симулируем stop

        repl.do_start("--port 7070")

        assert repl._engine is not first_engine
        assert repl._engine.config.tcp_port == 7070


class TestDoStop:
    """Тесты команды REPL: stop."""

    def test_stop_when_running(self, repl_with_engine):
        """stop когда сервер запущен — вызывает stop()."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_stop("")

        repl_with_engine._engine.stop.assert_awaited_once()

    def test_stop_when_not_running(self, repl_with_engine, capsys):
        """stop когда сервер не запущен — сообщение."""
        repl_with_engine._engine.is_running = False

        repl_with_engine.do_stop("")

        captured = capsys.readouterr()
        assert "не запущен" in captured.out
        repl_with_engine._engine.stop.assert_not_awaited()

    def test_stop_when_no_engine(self, repl, capsys):
        """stop без engine — сообщение."""
        repl.do_stop("")

        captured = capsys.readouterr()
        assert "не запущен" in captured.out


class TestDoStatus:
    """Тесты команды REPL: status."""

    def test_status_calls_get_status(self, repl_with_engine, capsys):
        """status вызывает engine.get_status()."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_status("")

        repl_with_engine._engine.get_status.assert_awaited_once()
        captured = capsys.readouterr()
        assert "Состояние" in captured.out


class TestDoCmwStatus:
    """Тесты команды REPL: cmw-status."""

    def test_cmw_status_calls_engine(self, repl_with_engine, capsys):
        """cmw-status вызывает engine.cmw_status()."""
        repl_with_engine._engine.cmw_status = AsyncMock(return_value={
            "connected": True, "status": "registered",
        })

        repl_with_engine.do_cmw_status("")

        repl_with_engine._engine.cmw_status.assert_awaited_once()
        captured = capsys.readouterr()
        assert "CMW-500" in captured.out


class TestDoRunScenario:
    """Тесты команды REPL: run-scenario."""

    def test_run_scenario_minimal(self, repl_with_engine):
        """run-scenario scenarios/auth/."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_run_scenario("scenarios/auth/")

        repl_with_engine._engine.run_scenario.assert_awaited_once_with(
            "scenarios/auth/", None
        )

    def test_run_scenario_with_connection_id(self, repl_with_engine):
        """run-scenario с --connection-id."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_run_scenario("scenarios/auth/ --connection-id conn-1")

        repl_with_engine._engine.run_scenario.assert_awaited_once_with(
            "scenarios/auth/", "conn-1"
        )

    def test_run_scenario_requires_path(self, repl_with_engine, capsys):
        """run-scenario без пути — сообщение об использовании."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_run_scenario("")

        captured = capsys.readouterr()
        assert "Использование" in captured.out

    def test_run_scenario_requires_running_server(self, repl_with_engine, capsys):
        """run-scenario без запущенного сервера — сообщение."""
        repl_with_engine._engine.is_running = False

        repl_with_engine.do_run_scenario("scenarios/auth/")

        captured = capsys.readouterr()
        assert "Сначала запустите" in captured.out


class TestDoReplay:
    """Тесты команды REPL: replay."""

    def test_replay_minimal(self, repl_with_engine):
        """replay logs/session.jsonl."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_replay("logs/session.jsonl")

        repl_with_engine._engine.replay.assert_awaited_once_with(
            "logs/session.jsonl", None
        )

    def test_replay_with_scenario(self, repl_with_engine):
        """replay с --scenario."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_replay("logs/session.jsonl --scenario scenarios/auth/")

        repl_with_engine._engine.replay.assert_awaited_once_with(
            "logs/session.jsonl", "scenarios/auth/"
        )

    def test_replay_requires_path(self, repl_with_engine, capsys):
        """replay без пути — сообщение."""
        repl_with_engine.do_replay("")

        captured = capsys.readouterr()
        assert "Использование" in captured.out


class TestDoExport:
    """Тесты команды REPL: export."""

    def test_export_minimal(self, repl_with_engine):
        """export packets --format csv --output out.csv."""
        repl_with_engine._engine.is_running = True

        repl_with_engine.do_export("packets --format csv --output out.csv")

        repl_with_engine._engine.export.assert_awaited_once_with(
            "packets", "csv", "out.csv"
        )

    def test_export_requires_args(self, repl_with_engine, capsys):
        """export без аргументов — сообщение."""
        repl_with_engine.do_export("")

        captured = capsys.readouterr()
        assert "Использование" in captured.out


class TestDoExit:
    """Тесты команды REPL: exit/quit/EOF."""

    def test_exit_stops_engine(self, repl_with_engine):
        """exit вызывает engine.stop() если engine запущен."""
        repl_with_engine._engine.is_running = True

        result = repl_with_engine.do_exit("")

        repl_with_engine._engine.stop.assert_awaited_once()
        assert result is True

    def test_exit_without_engine(self, repl):
        """exit без engine — просто True."""
        result = repl.do_exit("")

        assert result is True

    def test_quit_calls_exit(self, repl_with_engine):
        """quit вызывает do_exit."""
        repl_with_engine._engine.is_running = True

        result = repl_with_engine.do_quit("")

        assert result is True

    def test_eof_calls_exit(self, repl_with_engine):
        """EOF (Ctrl+D) вызывает do_exit."""
        repl_with_engine._engine.is_running = True

        result = repl_with_engine.do_EOF("")

        assert result is True


class TestEmptyLine:
    """Тесты пустой строки."""

    def test_emptyline_returns_false(self, repl):
        """emptyline возвращает False (не выходит)."""
        result = repl.emptyline()

        assert result is False
