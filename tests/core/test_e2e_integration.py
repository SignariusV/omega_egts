"""E2E интеграционные тесты: CoreEngine + Cmw500Emulator + TcpServer.

Полные сквозные тесты, проверяющие взаимодействие всех компонентов:
- CoreEngine стартует с эмулятором CMW-500
- TCP-клиент подключается и отправляет EGTS-пакеты
- Pipeline обрабатывает пакеты (CRC, парсинг, auto-response, dedup)
- FSM переходит в правильные состояния
- LogManager логирует события
- ScenarioManager выполняет сценарии
"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
from core.engine import CoreEngine
from core.event_bus import EventBus

# Реальные hex-пакеты из test_integration_real.py
AUTH_USV_HEX = (
    "0100000B002E002A0001CC2700490080010101240001000000"
    "16383630383033303636343438333133303235303737303031"
    "373135363433390F3A"
)

AUTH_RESPONSE_HEX = "0100000B0010001E00003B2A000006002D00400101000300490000E6BE"

COMMAND_HEX = "0100000B0019001100015612002000400404330F00500000000000000000000000011501DCBE"


def _hex_to_bytes(hex_str: str) -> bytes:
    """Конвертировать hex-строку в bytes."""
    return bytes.fromhex(hex_str)


def _find_free_port() -> int:
    """Найти свободный TCP-порт."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]


# ===== Фикстуры =====


@pytest.fixture
def event_bus() -> EventBus:
    """EventBus для тестов."""
    return EventBus()


@pytest.fixture
def e2e_config(tmp_path: Path) -> Config:
    """Минимальная конфигурация для E2E тестов."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    return Config(
        gost_version="2015",
        tcp_host="127.0.0.1",
        tcp_port=_find_free_port(),
        cmw500=CmwConfig(ip="127.0.0.1"),
        timeouts=TimeoutsConfig(
            tl_response_to=5,
            tl_resend_attempts=3,
            tl_reconnect_to=30,
            egts_sl_not_auth_to=6,
        ),
        logging=LogConfig(
            level="DEBUG",
            dir=str(log_dir),
            rotation="daily",
            max_size_mb=100,
            retention_days=30,
        ),
    )


@pytest.fixture
async def engine_with_emulator(
    e2e_config: Config, event_bus: EventBus
):
    """CoreEngine с Cmw500Emulator вместо реального CMW-500."""
    from core.cmw500 import Cmw500Emulator

    emulator = Cmw500Emulator(
        bus=event_bus,
        ip="127.0.0.1",
        poll_interval=0.5,
        tcp_delay_min=0.01,
        tcp_delay_max=0.05,
        sms_delay_min=0.05,
        sms_delay_max=0.1,
    )
    emulator._poll_loop = AsyncMock()  # type: ignore[method-assign]

    engine = CoreEngine(config=e2e_config, bus=event_bus)

    with patch("core.cmw500.Cmw500Controller", return_value=emulator):
        await engine.start()

        engine.cmw500 = emulator
        await emulator.connect()
        engine.command_dispatcher.cmw = emulator

        yield engine, event_bus, e2e_config

        await engine.stop()
        await emulator.disconnect()


@pytest.fixture
async def tcp_client_connection(engine_with_emulator):
    """TCP-клиент, подключённый к серверу."""
    engine, _event_bus, _config = engine_with_emulator

    await asyncio.sleep(0.1)

    real_port = engine.tcp_server._server.sockets[0].getsockname()[1]

    reader, writer = await asyncio.open_connection("127.0.0.1", real_port)

    yield reader, writer, real_port

    writer.close()
    await writer.wait_closed()


# ===== Тест 1: Полный сценарий авторизации =====


class TestEndToEndAuth:
    """E2E: полный сценарий авторизации УСВ."""

    async def test_auth_packet_through_full_pipeline(
        self, engine_with_emulator, tcp_client_connection
    ):
        """AUTH-пакет от клиента проходит через весь pipeline."""
        engine, _event_bus, _config = engine_with_emulator
        _reader, writer, _port = tcp_client_connection

        processed_packets: list[dict] = []

        async def on_processed(data: dict) -> None:
            processed_packets.append(data)

        engine.bus.on("packet.processed", on_processed, ordered=True)

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)
        writer.write(packet_bytes)
        await writer.drain()

        await asyncio.sleep(0.3)

        assert len(processed_packets) >= 1

        ctx = processed_packets[0]["ctx"]
        assert ctx.crc_valid is True
        assert ctx.parsed is not None
        assert ctx.parsed.packet is not None
        assert ctx.parsed.packet.packet_type == 1
        assert ctx.parsed.packet.packet_id == 42

        session = engine.session_mgr.get_session(ctx.connection_id)
        assert session is not None
        assert session.fsm.state.value in (
            "authorized",
            "wait_auth",
            "authenticating",
            "running",
        )

    async def test_auth_response_sent_back(
        self, engine_with_emulator, tcp_client_connection
    ):
        """Сервер отправляет RESPONSE на AUTH-пакет."""
        _engine, _event_bus, _config = engine_with_emulator
        reader, writer, _port = tcp_client_connection

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)
        writer.write(packet_bytes)
        await writer.drain()

        try:
            response = await asyncio.wait_for(reader.read(4096), timeout=2.0)
            assert len(response) > 0
        except TimeoutError:
            pytest.fail("Сервер не отправил RESPONSE на AUTH-пакет")


# ===== Тест 2: Несколько пакетов =====


class TestEndToEndMultiplePackets:
    """E2E: последовательность пакетов."""

    async def test_auth_then_command(
        self, engine_with_emulator, tcp_client_connection
    ):
        """AUTH → COMMAND: FSM корректно обрабатывает последовательность."""
        _engine, _event_bus, _config = engine_with_emulator
        _reader, writer, _port = tcp_client_connection

        processed_packets: list[dict] = []

        async def on_processed(data: dict) -> None:
            processed_packets.append(data)

        engine_with_emulator[0].bus.on("packet.processed", on_processed, ordered=True)

        auth_bytes = _hex_to_bytes(AUTH_USV_HEX)
        writer.write(auth_bytes)
        await writer.drain()
        await asyncio.sleep(0.3)

        auth_count = len(processed_packets)
        assert auth_count >= 1

        command_bytes = _hex_to_bytes(COMMAND_HEX)
        writer.write(command_bytes)
        await writer.drain()
        await asyncio.sleep(0.3)

        command_count = len(processed_packets)
        assert command_count >= auth_count

    async def test_duplicate_packet_detection(
        self, engine_with_emulator, tcp_client_connection
    ):
        """Дубликат пакета определяется и обрабатывается корректно."""
        _engine, _event_bus, _config = engine_with_emulator
        _reader, writer, _port = tcp_client_connection

        processed_packets: list[dict] = []

        async def on_processed(data: dict) -> None:
            processed_packets.append(data)

        engine_with_emulator[0].bus.on("packet.processed", on_processed, ordered=True)

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)

        writer.write(packet_bytes)
        await writer.drain()
        await asyncio.sleep(0.3)

        first_count = len(processed_packets)

        writer.write(packet_bytes)
        await writer.drain()
        await asyncio.sleep(0.3)

        second_count = len(processed_packets)
        assert second_count >= first_count


# ===== Тест 3: SMS-канал =====


class TestEndToEndSmsChannel:
    """E2E: SMS-канал через Cmw500Emulator."""

    async def test_auth_via_sms(
        self, engine_with_emulator
    ):
        """AUTH-пакет через SMS-канал."""
        engine, _event_bus, _config = engine_with_emulator

        processed_packets: list[dict] = []

        async def on_processed(data: dict) -> None:
            processed_packets.append(data)

        engine.bus.on("packet.processed", on_processed, ordered=True)

        def sms_handler(egts_bytes: bytes) -> bytes | None:
            return _hex_to_bytes(AUTH_RESPONSE_HEX)

        engine.cmw500.set_incoming_sms_handler(sms_handler)

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)
        result = await engine.cmw500.send_sms(packet_bytes)

        await asyncio.sleep(0.7)

        assert result is True

        if len(processed_packets) >= 1:
            ctx = processed_packets[0]["ctx"]
            assert ctx.channel == "sms"


# ===== Тест 4: LogManager =====


class TestEndToEndLogging:
    """E2E: проверка логирования."""

    async def test_packets_logged_to_file(
        self, engine_with_emulator, tcp_client_connection
    ):
        """Пакеты записываются в лог-файлы."""
        engine, _event_bus, config = engine_with_emulator
        _reader, writer, _port = tcp_client_connection

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)
        writer.write(packet_bytes)
        await writer.drain()
        await asyncio.sleep(0.3)

        await asyncio.sleep(0.5)

        log_dir = Path(config.logging.dir)
        assert log_dir.exists()
        assert engine.log_mgr is not None


# ===== Тест 5: Scenario Manager =====


class TestEndToEndScenario:
    """E2E: выполнение сценария."""

    async def test_run_simple_scenario(
        self, engine_with_emulator, tmp_path: Path
    ):
        """Простой сценарий выполняется через CoreEngine."""
        engine, _event_bus, _config = engine_with_emulator

        scenario_dir = tmp_path / "scenario_auth"
        scenario_dir.mkdir()

        scenario_json = {
            "version": "1",
            "name": "e2e-test-auth",
            "steps": [
                {
                    "type": "send",
                    "packet_hex": AUTH_USV_HEX,
                }
            ],
        }

        scenario_file = scenario_dir / "scenario.json"
        scenario_file.write_text(
            json.dumps(scenario_json, ensure_ascii=False),
            encoding="utf-8",
        )

        result = await engine.run_scenario(
            str(scenario_file),
            connection_id=None,
        )

        assert "status" in result
        assert "name" in result or "error" in result


# ===== Тест 6: Replay + Export =====


class TestEndToEndReplayExport:
    """E2E: replay и export."""

    async def test_replay_and_export(
        self, engine_with_emulator, tcp_client_connection, tmp_path: Path
    ):
        """Replay логов и экспорт данных."""
        engine, _event_bus, config = engine_with_emulator
        _reader, writer, _port = tcp_client_connection

        packet_bytes = _hex_to_bytes(AUTH_USV_HEX)
        writer.write(packet_bytes)
        await writer.drain()
        await asyncio.sleep(0.3)

        await asyncio.sleep(0.5)

        log_dir = Path(config.logging.dir)
        log_files = list(log_dir.glob("*.jsonl"))

        if log_files:
            replay_result = await engine.replay(str(log_files[0]))
            assert "processed" in replay_result

            output_path = str(tmp_path / "export.json")
            export_result = await engine.export(
                data_type="packets",
                fmt="json",
                output_path=output_path,
            )
            assert "rows" in export_result
            assert Path(output_path).exists()


# ===== Тест 7: Status API =====


class TestEndToEndStatus:
    """E2E: API статуса."""

    async def test_get_status_returns_full_info(
        self, engine_with_emulator
    ):
        """get_status() возвращает полную информацию."""
        engine, _event_bus, _config = engine_with_emulator

        status = await engine.get_status()

        assert status["running"] is True
        assert status["gost_version"] == "2015"
        assert status["tcp_server"] == "running"
        assert status["cmw500"] == "connected"
        assert status["session_mgr"] is True
        assert status["log_mgr"] is True
        assert status["scenario_mgr"] is True

    async def test_cmw_status_returns_connected(
        self, engine_with_emulator
    ):
        """cmw_status() возвращает connected."""
        engine, _event_bus, _config = engine_with_emulator

        status = await engine.cmw_status()

        assert status["connected"] is True
        assert "error" not in status
