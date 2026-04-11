"""Тест подтверждения решения ISSUE-004-B: CommandDispatcher извлекает pid/rn из packet_bytes

CommandDispatcher._send_tcp() теперь извлекает pid/rn из packet_bytes если они не переданы.
Это позволяет регистрировать транзакции для hex-файлов без build-template.
"""

from unittest.mock import MagicMock, AsyncMock

import pytest

from core.dispatcher import CommandDispatcher
from core.event_bus import EventBus


# RESULT_CODE hex (PT=1, PID=32, RN=47)
RESULT_CODE_HEX = bytes.fromhex("0100000B000B002000012604002F0040010109010000BA4C")


class TestIssue004B_PidRnExtraction:
    """CommandDispatcher извлекает pid/rn из packet_bytes"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    def _make_session_mgr(self, protocol_mock):
        mgr = MagicMock()
        conn = MagicMock()
        conn.writer = AsyncMock()
        conn.writer.is_closing.return_value = False
        conn.writer.write = MagicMock()
        conn.writer.drain = AsyncMock()
        conn.transaction_mgr = MagicMock()
        conn.protocol = protocol_mock
        mgr.get_session.return_value = conn
        mgr.connections = {"test_conn": conn}
        return mgr

    @pytest.mark.asyncio
    async def test_send_tcp_extracts_pid_rn_from_hex(self, event_bus):
        """_send_tcp(pid=None, rn=None) → извлекает pid/rn из packet_bytes"""
        # Мокаем parse_packet
        mock_parsed = MagicMock()
        mock_parsed.packet.packet_id = 32
        mock_parsed.packet.records = [MagicMock(record_id=47)]

        mock_protocol = MagicMock()
        mock_protocol.parse_packet.return_value = mock_parsed

        session_mgr = self._make_session_mgr(mock_protocol)
        dispatcher = CommandDispatcher(event_bus, session_mgr)

        await dispatcher._send_tcp(
            connection_id="test_conn",
            packet_bytes=RESULT_CODE_HEX,
            step_name="Результат аутентификации",
            pid=None,  # ← Не переданы
            rn=None,   # ← Не переданы
            timeout=5.0,
        )

        # parse_packet вызван
        mock_protocol.parse_packet.assert_called_once_with(RESULT_CODE_HEX)

        # register вызван с извлечёнными pid/rn
        conn = session_mgr.get_session("test_conn")
        conn.transaction_mgr.register.assert_called_once_with(
            pid=32,
            rn=47,
            step_name="Результат аутентификации",
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_send_tcp_uses_explicit_pid_rn(self, event_bus):
        """_send_tcp(pid=32, rn=47) → НЕ парсит, использует переданные"""
        mock_protocol = MagicMock()

        session_mgr = self._make_session_mgr(mock_protocol)
        dispatcher = CommandDispatcher(event_bus, session_mgr)

        await dispatcher._send_tcp(
            connection_id="test_conn",
            packet_bytes=RESULT_CODE_HEX,
            step_name="Результат аутентификации",
            pid=32,  # ← Переданы явно
            rn=47,
            timeout=5.0,
        )

        # parse_packet НЕ вызван (pid/rn уже есть)
        mock_protocol.parse_packet.assert_not_called()

        # register вызван с переданными pid/rn
        conn = session_mgr.get_session("test_conn")
        conn.transaction_mgr.register.assert_called_once_with(
            pid=32,
            rn=47,
            step_name="Результат аутентификации",
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_send_tcp_partial_pid_rn(self, event_bus):
        """_send_tcp(pid=32, rn=None) → парсит только rn"""
        mock_parsed = MagicMock()
        mock_parsed.packet.packet_id = 99  # Игнорируется
        mock_parsed.packet.records = [MagicMock(record_id=47)]

        mock_protocol = MagicMock()
        mock_protocol.parse_packet.return_value = mock_parsed

        session_mgr = self._make_session_mgr(mock_protocol)
        dispatcher = CommandDispatcher(event_bus, session_mgr)

        await dispatcher._send_tcp(
            connection_id="test_conn",
            packet_bytes=RESULT_CODE_HEX,
            step_name="Результат аутентификации",
            pid=32,  # ← Есть
            rn=None,  # ← Нет
            timeout=5.0,
        )

        # parse_packet вызван (нужен rn)
        mock_protocol.parse_packet.assert_called_once()

        # register: pid=32 (явный), rn=47 (из пакета)
        conn = session_mgr.get_session("test_conn")
        call_args = conn.transaction_mgr.register.call_args
        assert call_args.kwargs["pid"] == 32
        assert call_args.kwargs["rn"] == 47

    @pytest.mark.asyncio
    async def test_send_tcp_no_protocol(self, event_bus):
        """_send_tcp без protocol → register НЕ вызывается"""
        session_mgr = self._make_session_mgr(None)
        # Убираем protocol из conn
        conn = session_mgr.get_session("test_conn")
        del conn.protocol

        dispatcher = CommandDispatcher(event_bus, session_mgr)

        await dispatcher._send_tcp(
            connection_id="test_conn",
            packet_bytes=RESULT_CODE_HEX,
            step_name="Результат аутентификации",
            pid=None,
            rn=None,
            timeout=5.0,
        )

        # register НЕ вызван (не удалось извлечь pid/rn)
        conn.transaction_mgr.register.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_tcp_parse_error(self, event_bus):
        """_send_tcp с невалидным пакетом → register НЕ вызывается"""
        mock_protocol = MagicMock()
        mock_protocol.parse_packet.side_effect = ValueError("Invalid packet")

        session_mgr = self._make_session_mgr(mock_protocol)
        dispatcher = CommandDispatcher(event_bus, session_mgr)

        await dispatcher._send_tcp(
            connection_id="test_conn",
            packet_bytes=b"\xff\xfe\xfd",  # Невалидный пакет
            step_name="Тест",
            pid=None,
            rn=None,
            timeout=5.0,
        )

        # register НЕ вызван (ошибка парсинга)
        conn = session_mgr.get_session("test_conn")
        conn.transaction_mgr.register.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_tcp_no_records(self, event_bus):
        """_send_tcp: пакет без записей → rn=None, только pid"""
        mock_parsed = MagicMock()
        mock_parsed.packet.packet_id = 32
        mock_parsed.packet.records = []  # Нет записей

        mock_protocol = MagicMock()
        mock_protocol.parse_packet.return_value = mock_parsed

        session_mgr = self._make_session_mgr(mock_protocol)
        dispatcher = CommandDispatcher(event_bus, session_mgr)

        await dispatcher._send_tcp(
            connection_id="test_conn",
            packet_bytes=RESULT_CODE_HEX,
            step_name="Тест",
            pid=None,
            rn=None,
            timeout=5.0,
        )

        # register вызван только с pid
        conn = session_mgr.get_session("test_conn")
        conn.transaction_mgr.register.assert_called_once_with(
            pid=32,
            rn=None,
            step_name="Тест",
            timeout=5.0,
        )
