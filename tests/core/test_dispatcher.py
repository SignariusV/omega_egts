"""Tests for PacketDispatcher and CommandDispatcher."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from core.dispatcher import (
    CommandDispatcher,
    PacketDispatcher,
    _is_writer_closing,
)


# =============================================================================
# Helpers
# =============================================================================


class TestIsWriterClosing:
    """Tests for module-level _is_writer_closing."""

    def test_is_closing_false(self):
        writer = MagicMock()
        writer.is_closing.return_value = False
        assert _is_writer_closing(writer) is False

    def test_is_closing_true(self):
        writer = MagicMock()
        writer.is_closing.return_value = True
        assert _is_writer_closing(writer) is True

    def test_is_closing_coroutine_mock(self):
        """is_closing вернул coroutine — считаем активным."""
        async def _dummy_coro():
            return True

        writer = MagicMock()
        writer.is_closing.return_value = _dummy_coro()
        assert _is_writer_closing(writer) is False

    def test_no_is_closing_attr(self):
        writer = object()
        assert _is_writer_closing(writer) is False

    def test_is_closing_raises(self):
        writer = MagicMock()
        writer.is_closing.side_effect = RuntimeError("boom")
        assert _is_writer_closing(writer) is False


# =============================================================================
# PacketDispatcher
# =============================================================================


@pytest.fixture
def mock_bus():
    bus = MagicMock()
    bus.on = MagicMock()
    bus.off = MagicMock()
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def mock_session_mgr():
    mgr = MagicMock()
    mgr.get_session = MagicMock()
    mgr.ensure_sms_session = MagicMock()
    return mgr


@pytest.fixture
def mock_pipeline():
    pipeline = AsyncMock()
    pipeline.process = AsyncMock()
    return pipeline


@pytest.fixture
def packet_dispatcher(mock_bus, mock_session_mgr, mock_pipeline):
    return PacketDispatcher(
        bus=mock_bus,
        session_mgr=mock_session_mgr,
        pipeline=mock_pipeline,
    )


class TestPacketDispatcher:
    """PacketDispatcher lifecycle and event handling."""

    def test_init_subscribes_to_events(self, mock_bus, mock_session_mgr):
        PacketDispatcher(bus=mock_bus, session_mgr=mock_session_mgr)
        mock_bus.on.assert_any_call("raw.packet.received", ANY)
        mock_bus.on.assert_any_call("packet.processed", ANY)

    def test_stop_unsubscribes(self, packet_dispatcher, mock_bus):
        packet_dispatcher.stop()
        mock_bus.off.assert_any_call("raw.packet.received", ANY)
        mock_bus.off.assert_any_call("packet.processed", ANY)

    def test_build_pipeline(self, packet_dispatcher):
        p = packet_dispatcher._build_pipeline()
        assert p is not None

    @pytest.mark.asyncio
    async def test_on_raw_packet_empty(self, packet_dispatcher):
        await packet_dispatcher._on_raw_packet({"raw": b""})
        packet_dispatcher.pipeline.process.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_raw_packet_tcp(self, packet_dispatcher, mock_session_mgr):
        mock_session_mgr.get_session.return_value = MagicMock()
        await packet_dispatcher._on_raw_packet({
            "raw": b"\x01\x02\x03",
            "channel": "tcp",
            "connection_id": "conn-1",
        })
        packet_dispatcher.pipeline.process.assert_awaited_once()
        ctx = packet_dispatcher.pipeline.process.call_args[0][0]
        assert ctx.raw == b"\x01\x02\x03"
        assert ctx.channel == "tcp"
        assert ctx.connection_id == "conn-1"

    @pytest.mark.asyncio
    async def test_on_raw_packet_sms_no_connection_id(
        self, packet_dispatcher, mock_session_mgr,
    ):
        await packet_dispatcher._on_raw_packet({
            "raw": b"\x01\x02\x03",
            "channel": "sms",
            "connection_id": None,
        })
        mock_session_mgr.ensure_sms_session.assert_called_once()
        packet_dispatcher.pipeline.process.assert_awaited_once()
        ctx = packet_dispatcher.pipeline.process.call_args[0][0]
        assert ctx.connection_id == "packet_dispatcher_sms"

    @pytest.mark.asyncio
    async def test_on_raw_packet_pipeline_error(
        self, packet_dispatcher,
    ):
        packet_dispatcher.pipeline.process.side_effect = RuntimeError("pipeline boom")
        await packet_dispatcher._on_raw_packet({
            "raw": b"\x01",
            "channel": "tcp",
            "connection_id": "conn-1",
        })
        # Error logged, no exception propagated

    @pytest.mark.asyncio
    async def test_on_packet_processed_no_ctx(self, packet_dispatcher, mock_bus):
        await packet_dispatcher._on_packet_processed({})
        mock_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_packet_processed_no_response(
        self, packet_dispatcher, mock_bus,
    ):
        ctx = MagicMock()
        ctx.response_data = None
        await packet_dispatcher._on_packet_processed({"ctx": ctx})
        mock_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_packet_processed_sms(self, packet_dispatcher, mock_bus):
        ctx = MagicMock()
        ctx.response_data = b"\x00\x01"
        await packet_dispatcher._on_packet_processed({
            "ctx": ctx,
            "channel": "sms",
        })
        mock_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_response_tcp_success(
        self, packet_dispatcher, mock_session_mgr,
    ):
        writer = AsyncMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        conn = MagicMock()
        conn.writer = writer
        mock_session_mgr.get_session.return_value = conn

        await packet_dispatcher._send_response_tcp("conn-1", b"\x00\x01")
        writer.write.assert_called_once_with(b"\x00\x01")
        writer.drain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_response_tcp_no_session(
        self, packet_dispatcher, mock_session_mgr,
    ):
        mock_session_mgr.get_session.return_value = None
        await packet_dispatcher._send_response_tcp("conn-1", b"\x00\x01")


# =============================================================================
# CommandDispatcher
# =============================================================================


@pytest.fixture
def mock_cmw():
    cmw = MagicMock()
    cmw.send_sms = AsyncMock(return_value=True)
    return cmw


@pytest.fixture
def command_dispatcher(mock_bus, mock_session_mgr):
    return CommandDispatcher(
        bus=mock_bus,
        session_mgr=mock_session_mgr,
    )


@pytest.fixture
def cmd_dispatcher_with_cmw(mock_bus, mock_session_mgr, mock_cmw):
    return CommandDispatcher(
        bus=mock_bus,
        session_mgr=mock_session_mgr,
        cmw=mock_cmw,
    )


class TestCommandDispatcherInit:
    """CommandDispatcher lifecycle."""

    def test_init_subscribes(self, mock_bus, mock_session_mgr):
        CommandDispatcher(bus=mock_bus, session_mgr=mock_session_mgr)
        mock_bus.on.assert_called_once_with("command.send", ANY)

    def test_stop_unsubscribes(self, command_dispatcher, mock_bus):
        command_dispatcher.stop()
        mock_bus.off.assert_called_once_with("command.send", ANY)


class TestCommandDispatcherOnCommand:
    """Routing logic in _on_command."""

    @pytest.mark.asyncio
    async def test_empty_packet_bytes(self, command_dispatcher, mock_bus):
        await command_dispatcher._on_command({
            "packet_bytes": b"",
        })
        mock_bus.emit.assert_awaited_once_with(
            "command.error",
            {"error": "empty packet_bytes", "step_name": None},
        )

    @pytest.mark.asyncio
    async def test_unknown_channel(self, command_dispatcher, mock_bus):
        with patch.object(command_dispatcher, "_send_tcp", AsyncMock()):
            with patch.object(command_dispatcher, "_send_sms", AsyncMock()):
                await command_dispatcher._on_command({
                    "packet_bytes": b"\x01",
                    "channel": "unknown",
                })
        mock_bus.emit.assert_awaited_once()
        assert mock_bus.emit.call_args[0][0] == "command.error"

    @pytest.mark.asyncio
    async def test_routes_to_tcp(self, command_dispatcher):
        with patch.object(command_dispatcher, "_send_tcp", AsyncMock()) as mock_tcp:
            await command_dispatcher._on_command({
                "packet_bytes": b"\x01",
                "channel": "tcp",
                "connection_id": "conn-1",
            })
            mock_tcp.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_routes_to_sms(self, cmd_dispatcher_with_cmw):
        with patch.object(cmd_dispatcher_with_cmw, "_send_sms", AsyncMock()) as mock_sms:
            await cmd_dispatcher_with_cmw._on_command({
                "packet_bytes": b"\x01",
                "channel": "sms",
            })
            mock_sms.assert_awaited_once()


class TestCommandDispatcherSendTcp:
    """TCP sending path."""

    @pytest.mark.asyncio
    async def test_no_connection_id(self, command_dispatcher):
        with pytest.raises(ValueError, match="requires connection_id"):
            await command_dispatcher._send_tcp(
                connection_id=None,
                packet_bytes=b"\x01",
                step_name=None,
                pid=None,
                rn=None,
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_session_not_found(self, command_dispatcher, mock_session_mgr):
        mock_session_mgr.get_session.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await command_dispatcher._send_tcp(
                connection_id="conn-1",
                packet_bytes=b"\x01",
                step_name=None,
                pid=None,
                rn=None,
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_no_writer(self, command_dispatcher, mock_session_mgr):
        conn = MagicMock()
        conn.writer = None
        mock_session_mgr.get_session.return_value = conn
        with pytest.raises(ValueError, match="no writer"):
            await command_dispatcher._send_tcp(
                connection_id="conn-1",
                packet_bytes=b"\x01",
                step_name=None,
                pid=None,
                rn=None,
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_writer_closing(self, command_dispatcher, mock_session_mgr):
        writer = MagicMock()
        writer.is_closing.return_value = True
        conn = MagicMock()
        conn.writer = writer
        mock_session_mgr.get_session.return_value = conn
        with pytest.raises(ConnectionError, match="is closing"):
            await command_dispatcher._send_tcp(
                connection_id="conn-1",
                packet_bytes=b"\x01",
                step_name=None,
                pid=None,
                rn=None,
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_sends_and_emits(self, command_dispatcher, mock_session_mgr, mock_bus):
        writer = AsyncMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        conn = MagicMock()
        conn.writer = writer
        conn.transaction_mgr = MagicMock()
        mock_session_mgr.get_session.return_value = conn

        with patch.object(
            command_dispatcher, "_parse_packet_bytes",
            return_value={"packet_id": 42, "record_id": 7},
        ):
            await command_dispatcher._send_tcp(
                connection_id="conn-1",
                packet_bytes=b"\x01\x02",
                step_name="step-1",
                pid=None,
                rn=None,
                timeout=15.0,
            )

        writer.write.assert_called_once_with(b"\x01\x02")
        writer.drain.assert_awaited_once()
        conn.transaction_mgr.register.assert_called_once_with(
            pid=42, rn=7, step_name="step-1", timeout=15.0,
        )
        mock_bus.emit.assert_any_await("packet.sent", ANY)
        mock_bus.emit.assert_any_await("command.sent", ANY)

    @pytest.mark.asyncio
    async def test_register_before_write(self, command_dispatcher, mock_session_mgr):
        """Transaction регистрируется ДО writer.write()."""
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.is_closing.return_value = False
        conn = MagicMock()
        conn.writer = writer
        conn.transaction_mgr = MagicMock()
        mock_session_mgr.get_session.return_value = conn

        call_order = []
        conn.transaction_mgr.register = MagicMock(side_effect=lambda **kw: call_order.append("register"))
        writer.write = MagicMock(side_effect=lambda x: call_order.append("write"))

        with patch.object(
            command_dispatcher, "_parse_packet_bytes",
            return_value={"packet_id": 1, "record_id": 2},
        ):
            await command_dispatcher._send_tcp(
                connection_id="conn-1", packet_bytes=b"\x01",
                step_name=None, pid=None, rn=None, timeout=30.0,
            )

        assert call_order == ["register", "write"]


class TestCommandDispatcherSendSms:
    """SMS sending path."""

    @pytest.mark.asyncio
    async def test_no_cmw(self, command_dispatcher):
        with pytest.raises(RuntimeError, match="не подключён"):
            await command_dispatcher._send_sms(
                packet_bytes=b"\x01",
                step_name=None,
                pid=None,
                rn=None,
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_no_sms_session(self, cmd_dispatcher_with_cmw, mock_session_mgr):
        mock_session_mgr.ensure_sms_session.return_value = None
        with pytest.raises(RuntimeError, match="недоступна"):
            await cmd_dispatcher_with_cmw._send_sms(
                packet_bytes=b"\x01",
                step_name=None,
                pid=None,
                rn=None,
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_send_sms_fails(self, cmd_dispatcher_with_cmw, mock_session_mgr, mock_cmw):
        conn = MagicMock()
        conn.transaction_mgr = MagicMock()
        mock_session_mgr.ensure_sms_session.return_value = conn
        mock_cmw.send_sms.return_value = False

        with pytest.raises(RuntimeError, match="вернул False"):
            await cmd_dispatcher_with_cmw._send_sms(
                packet_bytes=b"\x01",
                step_name=None,
                pid=None,
                rn=None,
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_register_before_send(self, cmd_dispatcher_with_cmw, mock_session_mgr, mock_cmw):
        """Transaction регистрируется ДО send_sms() — race condition fix."""
        conn = MagicMock()
        conn.transaction_mgr = MagicMock()
        mock_session_mgr.ensure_sms_session.return_value = conn

        call_order = []
        conn.transaction_mgr.register = MagicMock(side_effect=lambda **kw: call_order.append("register"))
        mock_cmw.send_sms = AsyncMock(side_effect=lambda x: call_order.append("send_sms") or True)

        with patch.object(
            cmd_dispatcher_with_cmw, "_parse_packet_bytes",
            return_value={"packet_id": 1, "record_id": 2},
        ):
            await cmd_dispatcher_with_cmw._send_sms(
                packet_bytes=b"\x01",
                step_name=None,
                pid=None,
                rn=None,
                timeout=30.0,
            )

        assert call_order == ["register", "send_sms"]

    @pytest.mark.asyncio
    async def test_ensure_sms_called_once(self, cmd_dispatcher_with_cmw, mock_session_mgr, mock_cmw):
        """ensure_sms_session вызывается ТОЛЬКО один раз."""
        conn = MagicMock()
        conn.transaction_mgr = MagicMock()
        mock_session_mgr.ensure_sms_session.return_value = conn

        with patch.object(cmd_dispatcher_with_cmw, "_parse_packet_bytes", return_value=None):
            await cmd_dispatcher_with_cmw._send_sms(
                packet_bytes=b"\x01",
                step_name="step-1",
                pid=None,
                rn=None,
                timeout=30.0,
            )

        mock_session_mgr.ensure_sms_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_and_emits(self, cmd_dispatcher_with_cmw, mock_session_mgr, mock_cmw, mock_bus):
        conn = MagicMock()
        conn.transaction_mgr = MagicMock()
        mock_session_mgr.ensure_sms_session.return_value = conn

        with patch.object(
            cmd_dispatcher_with_cmw, "_parse_packet_bytes",
            return_value={"packet_id": 42, "record_id": 7},
        ):
            await cmd_dispatcher_with_cmw._send_sms(
                packet_bytes=b"\x01\x02",
                step_name="step-1",
                pid=None,
                rn=None,
                timeout=15.0,
            )

        mock_cmw.send_sms.assert_awaited_once_with(b"\x01\x02")
        mock_bus.emit.assert_any_await("packet.sent", ANY)
        mock_bus.emit.assert_any_await("command.sent", ANY)


class TestCommandDispatcherHelpers:
    """_resolve_pid_rn, _register_transaction, _emit_sent_events."""

    def test_resolve_pid_rn_both_provided(self, command_dispatcher):
        pid, rn = command_dispatcher._resolve_pid_rn(
            MagicMock(), b"\x01", 100, 200,
        )
        assert pid == 100
        assert rn == 200

    def test_resolve_pid_rn_parse_fallback(self, command_dispatcher):
        conn = MagicMock()
        with patch.object(
            command_dispatcher, "_parse_packet_bytes",
            return_value={"packet_id": 10, "record_id": 20},
        ):
            pid, rn = command_dispatcher._resolve_pid_rn(
                conn, b"\x01", None, None,
            )
        assert pid == 10
        assert rn == 20

    def test_resolve_pid_rn_parse_returns_none(self, command_dispatcher):
        with patch.object(
            command_dispatcher, "_parse_packet_bytes",
            return_value=None,
        ):
            pid, rn = command_dispatcher._resolve_pid_rn(
                MagicMock(), b"\x01", None, None,
            )
        assert pid is None
        assert rn is None

    def test_resolve_pid_rn_partial(self, command_dispatcher):
        conn = MagicMock()
        with patch.object(
            command_dispatcher, "_parse_packet_bytes",
            return_value={"packet_id": 10, "record_id": 20},
        ):
            # pid provided, rn missing
            pid, rn = command_dispatcher._resolve_pid_rn(
                conn, b"\x01", 99, None,
            )
        assert pid == 99  # unchanged
        assert rn == 20  # parsed

    def test_register_transaction(self, command_dispatcher):
        conn = MagicMock()
        conn.transaction_mgr = MagicMock()
        command_dispatcher._register_transaction(conn, 1, 2, "step", 30.0)
        conn.transaction_mgr.register.assert_called_once_with(
            pid=1, rn=2, step_name="step", timeout=30.0,
        )

    def test_register_transaction_no_pid_rn(self, command_dispatcher):
        conn = MagicMock()
        command_dispatcher._register_transaction(conn, None, None, "step", 30.0)
        conn.transaction_mgr.register.assert_not_called()

    def test_register_transaction_no_txn_mgr(self, command_dispatcher):
        conn = MagicMock(spec=[])  # no transaction_mgr attr
        command_dispatcher._register_transaction(conn, 1, 2, "step", 30.0)
        # no error, just warning logged

    @pytest.mark.asyncio
    async def test_emit_sent_events(self, command_dispatcher, mock_bus):
        await command_dispatcher._emit_sent_events(
            connection_id="conn-1",
            step_name="step-1",
            packet_bytes=b"\x01",
            channel="tcp",
            pid=42,
            rn=7,
        )
        mock_bus.emit.assert_any_await("packet.sent", {
            "connection_id": "conn-1",
            "step_name": "step-1",
            "packet_bytes": b"\x01",
            "channel": "tcp",
            "pid": 42,
            "rn": 7,
        })
        mock_bus.emit.assert_any_await("command.sent", {
            "connection_id": "conn-1",
            "step_name": "step-1",
            "packet_bytes": b"\x01",
            "channel": "tcp",
        })
