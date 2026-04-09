"""Тесты CommandDispatcher — координатор отправки команд через TCP и SMS."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.dispatcher import _SMS_DEFAULT_CONNECTION_ID, CommandDispatcher
from core.event_bus import EventBus
from core.session import SessionManager
from libs.egts_protocol_iface import create_protocol

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def protocol():
    return create_protocol("2015")


@pytest.fixture
def session_mgr(bus: EventBus, protocol):
    mgr = SessionManager(bus=bus, gost_version="2015")
    return mgr


# ---------------------------------------------------------------------------
# Тесты: создание
# ---------------------------------------------------------------------------


class TestCommandDispatcherCreation:
    """Тесты создания CommandDispatcher."""

    def test_create_with_minimal_args(self, bus: EventBus, session_mgr) -> None:
        dispatcher = CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )
        assert dispatcher.bus is bus
        assert dispatcher.session_mgr is session_mgr
        assert dispatcher.cmw is None

    def test_create_with_cmw(self, bus: EventBus, session_mgr) -> None:
        mock_cmw = AsyncMock()
        dispatcher = CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            cmw=mock_cmw,
        )
        assert dispatcher.cmw is mock_cmw

    def test_subscribes_on_command_send(self, bus: EventBus, session_mgr) -> None:
        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )
        assert "command.send" in bus._handlers


# ---------------------------------------------------------------------------
# Тесты: stop()
# ---------------------------------------------------------------------------


class TestCommandDispatcherStop:
    """Тесты метода stop()."""

    def test_stop_unsubscribes(self, bus: EventBus, session_mgr) -> None:
        dispatcher = CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )
        assert "command.send" in bus._handlers
        dispatcher.stop()
        # После отписки handlers должно быть пусто или не содержать наш handler
        handlers = bus._handlers.get("command.send", [])
        assert dispatcher._on_command not in handlers


# ---------------------------------------------------------------------------
# Тесты: TCP отправка
# ---------------------------------------------------------------------------


class TestCommandDispatcherTcp:
    """Тесты отправки команд через TCP."""

    async def test_tcp_send_writes_to_connection(
        self, bus: EventBus, session_mgr
    ) -> None:
        """Команда через TCP записывается в writer."""
        mock_writer = AsyncMock()
        mock_writer.is_closing.return_value = False

        conn_id = "tcp-cmd-1"
        conn = session_mgr.create_session(connection_id=conn_id)
        conn.writer = mock_writer  # type: ignore[assignment]

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        packet = b"\x01\x02\x03\x04"
        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": conn_id,
                "packet_bytes": packet,
                "step_name": "test_step",
                "pid": 10,
                "rn": None,
                "timeout": 15.0,
            },
        )
        await asyncio.sleep(0.1)

        mock_writer.write.assert_called_once_with(packet)
        mock_writer.drain.assert_called_once()

    async def test_tcp_send_emits_command_sent(
        self, bus: EventBus, session_mgr
    ) -> None:
        """Успешная отправка эмитит command.sent."""
        sent_events: list[dict] = []

        async def capture(data: dict) -> None:
            sent_events.append(data)

        bus.on("command.sent", capture)

        mock_writer = AsyncMock()
        mock_writer.is_closing.return_value = False

        conn_id = "tcp-cmd-2"
        conn = session_mgr.create_session(connection_id=conn_id)
        conn.writer = mock_writer  # type: ignore[assignment]

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        packet = b"\x10\x20\x30"
        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": conn_id,
                "packet_bytes": packet,
                "step_name": "step_a",
            },
        )
        await asyncio.sleep(0.1)

        assert len(sent_events) >= 1
        event = sent_events[0]
        assert event["connection_id"] == conn_id
        assert event["packet_bytes"] == packet
        assert event["channel"] == "tcp"

    async def test_tcp_send_registers_transaction(
        self, bus: EventBus, session_mgr
    ) -> None:
        """При наличии PID/RN регистрируется транзакция."""
        mock_writer = AsyncMock()
        mock_writer.is_closing.return_value = False

        conn_id = "tcp-cmd-txn"
        conn = session_mgr.create_session(connection_id=conn_id)
        conn.writer = mock_writer  # type: ignore[assignment]

        # Создаём TransactionManager
        from core.session import TransactionManager
        conn.transaction_mgr = TransactionManager()

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        packet = b"\xAA\xBB"
        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": conn_id,
                "packet_bytes": packet,
                "pid": 42,
                "rn": 5,
                "timeout": 20.0,
            },
        )
        await asyncio.sleep(0.1)

        # Транзакция зарегистрирована
        assert 42 in conn.transaction_mgr._by_pid
        assert 5 in conn.transaction_mgr._by_rn

    async def test_tcp_send_error_when_connection_not_found(
        self, bus: EventBus, session_mgr
    ) -> None:
        """Отправка в несуществующее соединение — command.error."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": "nonexistent",
                "packet_bytes": b"\x01",
            },
        )
        await asyncio.sleep(0.1)

        assert len(error_events) >= 1
        assert "not found" in error_events[0]["error"].lower()

    async def test_tcp_send_error_when_no_connection_id(
        self, bus: EventBus, session_mgr
    ) -> None:
        """TCP без connection_id — command.error."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "packet_bytes": b"\x01",
            },
        )
        await asyncio.sleep(0.1)

        assert len(error_events) >= 1
        assert "connection_id" in error_events[0]["error"].lower()

    async def test_tcp_send_error_when_writer_is_closing(
        self, bus: EventBus, session_mgr
    ) -> None:
        """Writer закрывается — command.error."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = True
        mock_writer.write = MagicMock()

        conn_id = "tcp-cmd-closing"
        conn = session_mgr.create_session(connection_id=conn_id)
        conn.writer = mock_writer  # type: ignore[assignment]

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": conn_id,
                "packet_bytes": b"\x01",
            },
        )
        await asyncio.sleep(0.1)

        assert len(error_events) >= 1
        assert "closing" in error_events[0]["error"].lower()


# ---------------------------------------------------------------------------
# Тесты: SMS отправка
# ---------------------------------------------------------------------------


class TestCommandDispatcherSms:
    """Тесты отправки команд через SMS."""

    async def test_sms_send_via_cmw(self, bus: EventBus, session_mgr) -> None:
        """SMS-отправка через CMW-500."""
        mock_cmw = AsyncMock()
        mock_cmw.send_sms.return_value = True

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            cmw=mock_cmw,
        )

        packet = b"\xDE\xAD"
        await bus.emit(
            "command.send",
            {
                "channel": "sms",
                "packet_bytes": packet,
                "step_name": "sms_step",
            },
        )
        await asyncio.sleep(0.1)

        mock_cmw.send_sms.assert_called_once_with(packet)

    async def test_sms_emits_command_sent(self, bus: EventBus, session_mgr) -> None:
        """Успешная SMS-отправка эмитит command.sent."""
        sent_events: list[dict] = []

        async def capture(data: dict) -> None:
            sent_events.append(data)

        bus.on("command.sent", capture)

        mock_cmw = AsyncMock()
        mock_cmw.send_sms.return_value = True

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            cmw=mock_cmw,
        )

        packet = b"\xBE\xEF"
        await bus.emit(
            "command.send",
            {
                "channel": "sms",
                "packet_bytes": packet,
                "step_name": "sms_step",
            },
        )
        await asyncio.sleep(0.1)

        assert len(sent_events) >= 1
        event = sent_events[0]
        assert event["channel"] == "sms"
        assert event["packet_bytes"] == packet
        assert event["connection_id"] == _SMS_DEFAULT_CONNECTION_ID

    async def test_sms_error_when_cmw_not_connected(
        self, bus: EventBus, session_mgr
    ) -> None:
        """SMS без CMW-500 — command.error."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        await bus.emit(
            "command.send",
            {
                "channel": "sms",
                "packet_bytes": b"\x01",
            },
        )
        await asyncio.sleep(0.1)

        assert len(error_events) >= 1
        assert "cmw" in error_events[0]["error"].lower() or "контроллер" in error_events[0]["error"].lower()

    async def test_sms_error_when_send_returns_false(
        self, bus: EventBus, session_mgr
    ) -> None:
        """CMW send_sms=False — command.error."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        mock_cmw = AsyncMock()
        mock_cmw.send_sms.return_value = False

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            cmw=mock_cmw,
        )

        await bus.emit(
            "command.send",
            {
                "channel": "sms",
                "packet_bytes": b"\x01",
            },
        )
        await asyncio.sleep(0.1)

        assert len(error_events) >= 1

    async def test_sms_registers_transaction(
        self, bus: EventBus, session_mgr
    ) -> None:
        """При наличии PID/RN регистрируется транзакция в SMS-сессии."""
        # Создаём SMS-сессию заранее с transaction_mgr
        from core.dispatcher import _SMS_DEFAULT_CONNECTION_ID
        from core.session import TransactionManager
        from libs.egts_protocol_iface import create_protocol

        protocol = create_protocol("2015")
        conn = session_mgr.create_session(
            connection_id=_SMS_DEFAULT_CONNECTION_ID, protocol=protocol
        )
        conn.transaction_mgr = TransactionManager()

        sent_events: list[dict] = []

        async def capture(data: dict) -> None:
            sent_events.append(data)

        bus.on("command.sent", capture)

        mock_cmw = AsyncMock()
        mock_cmw.send_sms.return_value = True

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            cmw=mock_cmw,
        )

        packet = b"\x01\x02\x03"
        await bus.emit(
            "command.send",
            {
                "channel": "sms",
                "packet_bytes": packet,
                "pid": 42,
                "rn": 7,
                "step_name": "sms_txn_step",
                "timeout": 25.0,
            },
        )
        await asyncio.sleep(0.1)

        # Транзакция зарегистрирована в SMS-сессии
        assert 42 in conn.transaction_mgr._by_pid
        assert 7 in conn.transaction_mgr._by_rn

        # command.sent эмитирован
        assert len(sent_events) >= 1
        assert sent_events[0]["channel"] == "sms"


# ---------------------------------------------------------------------------
# Тесты: дополнительные ошибки CommandDispatcher
# ---------------------------------------------------------------------------


class TestCommandDispatcherAdditionalErrors:
    """Дополнительные тесты непокрытых веток."""

    async def test_tcp_send_without_transaction_mgr(
        self, bus: EventBus, session_mgr
    ) -> None:
        """TCP отправка без transaction_mgr — предупреждение, но отправка."""
        sent_events: list[dict] = []

        async def capture(data: dict) -> None:
            sent_events.append(data)

        bus.on("command.sent", capture)

        mock_writer = AsyncMock()
        mock_writer.is_closing.return_value = False

        conn_id = "tcp-no-txn-mgr"
        conn = session_mgr.create_session(connection_id=conn_id)
        conn.writer = mock_writer  # type: ignore[assignment]
        conn.transaction_mgr = None  # type: ignore[assignment]

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        packet = b"\xCC\xDD"
        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": conn_id,
                "packet_bytes": packet,
                "pid": 10,
            },
        )
        await asyncio.sleep(0.1)

        # Отправка всё равно прошла
        assert len(sent_events) >= 1
        mock_writer.write.assert_called_once_with(packet)

    async def test_tcp_send_is_closing_returns_coroutine(
        self, bus: EventBus, session_mgr
    ) -> None:
        """is_closing() возвращает coroutine — writer считается активным."""
        sent_events: list[dict] = []

        async def capture(data: dict) -> None:
            sent_events.append(data)

        bus.on("command.sent", capture)

        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        async def fake_closing():
            return False

        mock_writer.is_closing = fake_closing

        conn_id = "tcp-closing-coroutine"
        conn = session_mgr.create_session(connection_id=conn_id)
        conn.writer = mock_writer  # type: ignore[assignment]

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        packet = b"\xEE\xFF"
        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": conn_id,
                "packet_bytes": packet,
            },
        )
        await asyncio.sleep(0.1)

        mock_writer.write.assert_called_once_with(packet)
        assert len(sent_events) >= 1

    async def test_tcp_send_no_writer_attribute(
        self, bus: EventBus, session_mgr
    ) -> None:
        """У сессии нет атрибута writer — command.error."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        # Создаём сессию без writer
        conn_id = "tcp-no-writer-attr"
        session_mgr.create_session(connection_id=conn_id)
        # Не устанавливаем writer — остаётся None по умолчанию

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": conn_id,
                "packet_bytes": b"\x01",
            },
        )
        await asyncio.sleep(0.1)

        assert len(error_events) >= 1
        assert "writer" in error_events[0]["error"].lower() or "not found" in error_events[0]["error"].lower()

    async def test_sms_send_without_transaction_mgr(
        self, bus: EventBus, session_mgr
    ) -> None:
        """SMS отправка без SMS-сессии — warning, но отправка."""
        sent_events: list[dict] = []

        async def capture(data: dict) -> None:
            sent_events.append(data)

        bus.on("command.sent", capture)

        mock_cmw = AsyncMock()
        mock_cmw.send_sms.return_value = True

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            cmw=mock_cmw,
        )

        packet = b"\xAB\xCD"
        await bus.emit(
            "command.send",
            {
                "channel": "sms",
                "packet_bytes": packet,
                "pid": 99,
            },
        )
        await asyncio.sleep(0.1)

        # Отправка прошла
        mock_cmw.send_sms.assert_called_once_with(packet)
        assert len(sent_events) >= 1


# ---------------------------------------------------------------------------
# Тесты: общие ошибки
# ---------------------------------------------------------------------------


class TestCommandDispatcherErrors:
    """Тесты обработки ошибок."""

    async def test_empty_packet_emits_error(
        self, bus: EventBus, session_mgr
    ) -> None:
        """Пустой пакет — command.error."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        await bus.emit(
            "command.send",
            {
                "channel": "tcp",
                "connection_id": "conn1",
                "packet_bytes": b"",
            },
        )
        await asyncio.sleep(0.1)

        assert len(error_events) >= 1
        assert "empty" in error_events[0]["error"].lower()

    async def test_unknown_channel_emits_error(
        self, bus: EventBus, session_mgr
    ) -> None:
        """Неизвестный канал — command.error."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        await bus.emit(
            "command.send",
            {
                "channel": "udp",
                "connection_id": "conn1",
                "packet_bytes": b"\x01",
            },
        )
        await asyncio.sleep(0.1)

        assert len(error_events) >= 1
        assert "udp" in error_events[0]["error"].lower()

    async def test_default_channel_is_tcp(self, bus: EventBus, session_mgr) -> None:
        """По умолчанию channel='tcp'."""
        error_events: list[dict] = []

        async def capture(data: dict) -> None:
            error_events.append(data)

        bus.on("command.error", capture)

        CommandDispatcher(
            bus=bus,
            session_mgr=session_mgr,
        )

        # Без channel — должно трактоваться как TCP без connection_id
        await bus.emit(
            "command.send",
            {
                "packet_bytes": b"\x01",
            },
        )
        await asyncio.sleep(0.1)

        # Ошибка "requires connection_id" подтверждает, что channel=tcp
        assert len(error_events) >= 1
        assert "connection_id" in error_events[0]["error"].lower()
