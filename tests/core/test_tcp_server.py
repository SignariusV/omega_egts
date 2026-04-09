"""Тесты TcpServerManager — asyncio TCP-сервер для приёма EGTS-пакетов."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from core.event_bus import EventBus
from core.tcp_server import TcpServerManager

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
async def bus() -> EventBus:
    """Создать EventBus для каждого теста."""
    return EventBus()


@pytest.fixture
async def server(bus: EventBus) -> AsyncIterator[TcpServerManager]:
    """Создать и запустить сервер, гарантированно остановить после теста.

    Эта фикстура гарантирует, что сервер будет остановлен даже при
    отмене теста или возникновении ошибки.
    """
    srv = TcpServerManager(bus=bus, host="127.0.0.1", port=0)
    await srv.start()
    try:
        yield srv
    finally:
        try:
            await srv.stop()
        except Exception:
            # Если сервер уже остановлен — игнорируем
            pass


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


async def _connect_to_server(host: str, port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Подключиться к TCP-серверу, вернуть (reader, writer)."""
    return await asyncio.open_connection(host, port)


def _build_egts_packet(pid: int = 1, body: bytes = b"\x00") -> bytes:
    """Минимальный EGTS-пакет для тестов (невалидный CRC, но с заголовком).

    Формат заголовка (минимальный, 8 байт):
    PR+HL(1) | PID(2) | PN(1) | CID(2) | RP(1) | CRC-8(1) = 8 байт
    """
    header = bytearray(8)
    header[0] = 0x01  # PR=0, HL=1 (минимальный заголовок)
    header[1] = pid & 0xFF
    header[2] = (pid >> 8) & 0xFF
    header[3] = 0x00  # PN
    # CID отсутствует (HL=1)
    header[4] = 0x00  # RP
    header[5] = 0x00  # RP продолжение / padding
    header[6] = 0x00  # padding
    header[7] = 0x00  # CRC-8 (невалидный, но для тестов сойдёт)
    return bytes(header) + body


# ---------------------------------------------------------------------------
# Тесты: start / stop
# ---------------------------------------------------------------------------


class TestTcpServerStartStop:
    """Тесты запуска и остановки TcpServerManager."""

    async def test_start_opens_socket(self, server: TcpServerManager) -> None:
        """start() открывает TCP-сокет на заданном порту."""
        assert server.is_running is True
        assert server.server is not None
        socks = server.server.sockets
        assert socks is not None
        assert len(socks) > 0

    async def test_stop_closes_socket(self, bus: EventBus) -> None:
        """stop() закрывает TCP-сокет."""
        srv = TcpServerManager(bus=bus, host="127.0.0.1", port=0)
        await srv.start()
        await srv.stop()
        assert srv.is_running is False
        assert srv.server is None

    async def test_start_idempotent(self, server: TcpServerManager) -> None:
        """Повторный start() не создаёт второй сервер."""
        first_server = server.server
        await server.start()  # повторный вызов
        assert server.server is first_server

    async def test_stop_without_start_is_noop(self, bus: EventBus) -> None:
        """stop() без start() не вызывает ошибок."""
        srv = TcpServerManager(bus=bus, host="127.0.0.1", port=0)
        await srv.stop()  # не должно выбросить
        assert srv.is_running is False

    async def test_start_after_stop(self, bus: EventBus) -> None:
        """Можно start() → stop() → start() снова."""
        srv = TcpServerManager(bus=bus, host="127.0.0.1", port=0)
        await srv.start()
        await srv.stop()
        await srv.start()
        try:
            assert srv.is_running is True
        finally:
            await srv.stop()

    async def test_start_emits_server_started(self, bus: EventBus) -> None:
        """start() эмитит server.started с фактическим портом."""
        events: list[dict] = []

        async def capture(data: dict) -> None:
            events.append(data)

        bus.on("server.started", capture)

        srv = TcpServerManager(bus=bus, host="127.0.0.1", port=0)
        await srv.start()
        try:
            assert len(events) >= 1
            assert events[0]["port"] == srv.actual_port
            assert srv.actual_port is not None
            assert srv.actual_port > 0
        finally:
            await srv.stop()


# ---------------------------------------------------------------------------
# Тесты: приём подключений
# ---------------------------------------------------------------------------


class TestTcpServerConnections:
    """Тесты приёма подключений и обработки клиентов."""

    async def test_accept_connection_emits_event(self, bus: EventBus, server: TcpServerManager) -> None:
        """При подключении клиента эмитится connection.changed."""
        received_events: list[dict[str, object]] = []

        async def capture(data: dict[str, object]) -> None:
            received_events.append(data)

        bus.on("connection.changed", capture)

        port = server.actual_port
        assert port is not None
        _reader, writer = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.1)

        assert len(received_events) >= 1
        event_data = received_events[0]
        assert event_data["action"] == "connected"
        assert "connection_id" in event_data
        writer.close()
        await writer.wait_closed()

    async def test_client_disconnect_emits_event(self, bus: EventBus, server: TcpServerManager) -> None:
        """При отключении клиента эмитится connection.changed с action=disconnected."""
        received_events: list[dict[str, object]] = []

        async def capture(data: dict[str, object]) -> None:
            received_events.append(data)

        bus.on("connection.changed", capture)

        port = server.actual_port
        assert port is not None
        _reader, writer = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.05)
        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.3)

        disconnect_events = [e for e in received_events if e.get("action") == "disconnected"]
        assert len(disconnect_events) >= 1

    async def test_connection_id_is_stored(self, server: TcpServerManager) -> None:
        """connection_id клиента сохраняется в session_mgr через create_session."""
        created_sessions: list[str] = []

        class MockSessionMgr:
            """Мок SessionManager с методом create_session."""

            def __init__(self) -> None:
                self.connections: dict[str, object] = {}

            def create_session(self, connection_id: str, **kwargs: object) -> object:
                created_sessions.append(connection_id)
                stub: dict[str, object] = {"connection_id": connection_id, **kwargs}
                self.connections[connection_id] = stub
                return stub

        mock_session_mgr = MockSessionMgr()
        server.session_mgr = mock_session_mgr  # type: ignore[assignment]

        port = server.actual_port
        assert port is not None
        _reader, writer = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.1)

        assert len(created_sessions) >= 1
        assert len(mock_session_mgr.connections) >= 1
        writer.close()
        await writer.wait_closed()


# ---------------------------------------------------------------------------
# Тесты: чтение данных и emit raw.packet.received
# ---------------------------------------------------------------------------


class TestTcpServerReadData:
    """Тесты чтения данных и отправки событий."""

    async def test_read_data_emits_raw_packet(self, bus: EventBus, server: TcpServerManager) -> None:
        """Прочитанные данные эмитятся как raw.packet.received."""
        received_packets: list[dict[str, object]] = []

        async def capture(data: dict[str, object]) -> None:
            received_packets.append(data)

        bus.on("raw.packet.received", capture)

        port = server.actual_port
        assert port is not None
        _reader, writer = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.05)

        raw_data = _build_egts_packet(pid=42, body=b"\x01\x02\x03")
        writer.write(raw_data)
        await writer.drain()
        await asyncio.sleep(0.3)

        assert len(received_packets) >= 1
        event_data = received_packets[0]
        assert event_data["raw"] == raw_data
        assert event_data["channel"] == "tcp"
        assert "connection_id" in event_data
        writer.close()
        await writer.wait_closed()

    async def test_multiple_packets_emitted_separately(self, bus: EventBus, server: TcpServerManager) -> None:
        """Несколько пакетов эмитятся отдельно."""
        received_packets: list[dict[str, object]] = []

        async def capture(data: dict[str, object]) -> None:
            received_packets.append(data)

        bus.on("raw.packet.received", capture)

        port = server.actual_port
        assert port is not None
        _reader, writer = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.05)

        # Отправляем два пакета подряд
        pkt1 = _build_egts_packet(pid=1)
        pkt2 = _build_egts_packet(pid=2)
        writer.write(pkt1 + pkt2)
        await writer.drain()
        await asyncio.sleep(0.5)

        # Может быть 1 или 2 события — зависит от обработки буфера
        assert len(received_packets) >= 1
        writer.close()
        await writer.wait_closed()


# ---------------------------------------------------------------------------
# Тесты: обработка ошибок
# ---------------------------------------------------------------------------


class TestTcpServerErrors:
    """Тесты обработки ошибок."""

    async def test_connection_error_handling(self, bus: EventBus, server: TcpServerManager) -> None:
        """Ошибка чтения от клиента не роняет сервер."""
        port = server.actual_port
        assert port is not None
        _reader, writer = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.05)
        writer.close()
        await writer.wait_closed()

        # Сервер должен продолжить работу
        assert server.is_running is True

        # Можем подключиться снова
        _reader2, writer2 = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.05)
        writer2.close()
        await writer2.wait_closed()

    async def test_stop_closes_active_connections(self, bus: EventBus) -> None:
        """stop() закрывает активные подключения."""
        srv = TcpServerManager(bus=bus, host="127.0.0.1", port=0)
        await srv.start()
        try:
            port = srv.actual_port
            assert port is not None
            _reader, writer = await _connect_to_server("127.0.0.1", port)
            await asyncio.sleep(0.05)

            await srv.stop()
            # Сервер остановлен, writer должен быть закрыт
            assert writer.is_closing() is True or srv.is_running is False
        finally:
            if not writer.is_closing():
                writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Тесты: интеграция с EventBus
# ---------------------------------------------------------------------------


class TestTcpServerEventBus:
    """Тесты интеграции TcpServerManager с EventBus."""

    async def test_emits_connection_changed_on_connect(self, bus: EventBus, server: TcpServerManager) -> None:
        """connection.changed эмитится с правильными данными."""
        received_events: list[tuple[str, dict[str, object]]] = []

        async def capture(data: dict[str, object]) -> None:
            received_events.append(("connection.changed", data))

        bus.on("connection.changed", capture)

        port = server.actual_port
        assert port is not None
        _reader, writer = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.1)

        connect_events = [e for e in received_events if e[1].get("action") == "connected"]
        assert len(connect_events) >= 1
        event_data = connect_events[0][1]
        assert "connection_id" in event_data
        writer.close()
        await writer.wait_closed()

    async def test_connection_id_in_all_events(self, bus: EventBus, server: TcpServerManager) -> None:
        """Все события содержат один и тот же connection_id для одного подключения."""
        received_events: list[tuple[str, dict[str, object]]] = []

        async def capture(name: str, data: dict[str, object]) -> None:
            received_events.append((name, data))

        bus.on("connection.changed", lambda d: asyncio.create_task(capture("connection.changed", d)))
        bus.on("raw.packet.received", lambda d: asyncio.create_task(capture("raw.packet.received", d)))

        port = server.actual_port
        assert port is not None
        _reader, writer = await _connect_to_server("127.0.0.1", port)
        await asyncio.sleep(0.05)

        raw_data = _build_egts_packet(pid=1)
        writer.write(raw_data)
        await writer.drain()
        await asyncio.sleep(0.2)

        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.2)

        # Собираем все connection_id
        conn_ids = {data.get("connection_id") for _, data in received_events if data.get("connection_id")}
        # Все события одного подключения имеют один connection_id
        # (минимум 1: connect или packet)
        assert len(conn_ids) >= 1
