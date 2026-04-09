# mypy: ignore-errors
"""Тесты ParseMiddleware.

Проверяют парсинг EGTS-пакетов через protocol,
обработку ошибок и edge cases (нет подключения, protocol=None).
"""

from unittest.mock import MagicMock

import pytest

from core.pipeline import PacketContext, ParseMiddleware
from core.session import SessionManager, UsvConnection
from libs.egts_protocol_iface import Packet, ParseResult

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_protocol():
    """Mock IEgtsProtocol."""
    proto = MagicMock()
    return proto


@pytest.fixture
def mock_session_mgr(mock_protocol):
    """SessionManager с моковым подключением."""
    mgr = MagicMock(spec=SessionManager)
    conn = UsvConnection(
        connection_id="test-conn",
        protocol=mock_protocol,
    )
    mgr.get_session.return_value = conn
    return mgr


@pytest.fixture
def mock_parse_result():
    """Mock ParseResult с успешным парсингом."""
    packet = Packet(packet_id=1, packet_type=1)
    result = ParseResult(packet=packet, raw_bytes=b"\x01\x00\x01\x00")
    return result


@pytest.fixture
def mock_parse_result_with_service():
    """ParseResult с service в extra (для FSM)."""
    packet = Packet(packet_id=1, packet_type=1)
    result = ParseResult(
        packet=packet,
        raw_bytes=b"\x01\x00\x01\x00",
        extra={"service": 1, "tid": 12345},
    )
    return result


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestParseMiddlewareSuccess:
    """Успешный парсинг — parsed заполнен, terminated=False."""

    @pytest.mark.asyncio
    async def test_successful_parsing(self, mock_session_mgr, mock_protocol, mock_parse_result):
        """Пакет успешно распарсен — parsed заполнен из ParseResult."""
        mock_protocol.parse_packet.return_value = mock_parse_result

        mw = ParseMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        await mw(ctx)

        assert ctx.parsed is not None
        assert ctx.terminated is False
        assert len(ctx.errors) == 0

        # parse_packet вызван с raw данными
        mock_protocol.parse_packet.assert_called_once_with(b"\x01\x00\x01\x00")

    @pytest.mark.asyncio
    async def test_parsed_contains_packet_info(self, mock_session_mgr, mock_protocol, mock_parse_result_with_service):
        """parsed содержит service, tid и другие данные из extra."""
        mock_protocol.parse_packet.return_value = mock_parse_result_with_service

        mw = ParseMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        await mw(ctx)

        assert ctx.parsed is not None
        assert isinstance(ctx.parsed, ParseResult)
        assert ctx.parsed.extra.get("service") == 1
        assert ctx.parsed.extra.get("tid") == 12345
        assert ctx.parsed.packet is not None
        assert isinstance(ctx.parsed.packet, Packet)


class TestParseMiddlewareErrors:
    """Ошибки парсинга — terminated=True, errors заполнены."""

    @pytest.mark.asyncio
    async def test_parse_error(self, mock_session_mgr, mock_protocol):
        """parse_packet вернул ParseResult с errors — terminated=True."""
        result = ParseResult(
            packet=None,
            errors=["Invalid packet structure"],
            raw_bytes=b"\xff\xff",
        )
        mock_protocol.parse_packet.return_value = result

        mw = ParseMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"\xff\xff", connection_id="test-conn")
        await mw(ctx)

        assert ctx.parsed is None
        assert ctx.terminated is True
        assert len(ctx.errors) > 0
        assert "Invalid packet structure" in str(ctx.errors)

    @pytest.mark.asyncio
    async def test_parse_partial_success(self, mock_session_mgr, mock_protocol):
        """Частичный успех (packet есть, но есть warnings) — terminated=False."""
        packet = Packet(packet_id=1, packet_type=1)
        result = ParseResult(
            packet=packet,
            warnings=["Unknown subrecord type"],
            raw_bytes=b"\x01\x00\x01\x00",
        )
        mock_protocol.parse_packet.return_value = result

        mw = ParseMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        await mw(ctx)

        # Частичный успех — пакет распарсен, warnings логируются
        assert ctx.parsed is not None
        assert ctx.terminated is False

    @pytest.mark.asyncio
    async def test_parse_exception(self, mock_session_mgr, mock_protocol):
        """parse_packet выбросил исключение — terminated=True, error записан."""
        mock_protocol.parse_packet.side_effect = ValueError("Unexpected byte sequence")

        mw = ParseMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        await mw(ctx)

        assert ctx.terminated is True
        assert len(ctx.errors) > 0
        assert "Unexpected byte sequence" in str(ctx.errors)


class TestParseMiddlewareEdgeCases:
    """Edge cases: нет подключения, protocol=None."""

    @pytest.mark.asyncio
    async def test_connection_not_found(self, mock_session_mgr):
        """connection_id нет в session_mgr → terminated."""
        mock_session_mgr.get_session.return_value = None

        mw = ParseMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="nonexistent-conn")
        await mw(ctx)

        assert ctx.parsed is None
        assert ctx.terminated is True
        assert len(ctx.errors) > 0

    @pytest.mark.asyncio
    async def test_protocol_is_none(self):
        """connection найден, но protocol=None → terminated."""
        mgr = MagicMock(spec=SessionManager)
        conn = UsvConnection(connection_id="test-conn", protocol=None)
        mgr.get_session.return_value = conn

        mw = ParseMiddleware(mgr)
        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        await mw(ctx)

        assert ctx.parsed is None
        assert ctx.terminated is True
        assert len(ctx.errors) > 0

    @pytest.mark.asyncio
    async def test_empty_packet(self, mock_session_mgr, mock_protocol):
        """Пустой raw → parse_packet вызван (protocol сам обработает)."""
        result = ParseResult(packet=None, errors=["Empty packet"], raw_bytes=b"")
        mock_protocol.parse_packet.return_value = result

        mw = ParseMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"", connection_id="test-conn")
        await mw(ctx)

        # parse_packet всё равно вызван — protocol сам решит что делать
        mock_protocol.parse_packet.assert_called_once_with(b"")
        assert ctx.terminated is True


class TestParseMiddlewareIntegration:
    """Интеграция ParseMiddleware с PacketPipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_with_parse_middleware(
        self, mock_session_mgr, mock_protocol, mock_parse_result_with_service
    ):
        """PacketPipeline + ParseMiddleware: пакет распарсен, parsed доступен."""
        from core.pipeline import PacketPipeline

        mock_protocol.parse_packet.return_value = mock_parse_result_with_service

        pipeline = PacketPipeline()
        pipeline.add("parse", ParseMiddleware(mock_session_mgr), order=1)

        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        result = await pipeline.process(ctx)

        assert result.parsed is not None
        assert isinstance(result.parsed, ParseResult)
        assert result.parsed.extra.get("service") == 1
        assert result.terminated is False

    @pytest.mark.asyncio
    async def test_pipeline_parse_then_crc(
        self, mock_session_mgr, mock_protocol, mock_parse_result
    ):
        """PacketPipeline: ParseMiddleware → CrcValidationMiddleware."""
        from core.pipeline import CrcValidationMiddleware, PacketPipeline
        from libs.egts_protocol_gost2015.gost2015_impl.crc import crc8, crc16

        # Создаём полноценный валидный пакет для CRC проверки
        header_base = bytearray([
            0x01,  # PRV = 1
            0x00,  # SKID = 0
            0x00,  # Flags
            11,    # HL = 11
            0x00,  # HE
            0x00, 0x00,  # FDL = 0 (нет записей)
            0x01, 0x00,  # PID = 1
            0x01,  # PT = 1 (service)
        ])
        hcs = crc8(bytes(header_base))
        header = header_base + bytes([hcs])
        body = b""
        sfcs = crc16(body).to_bytes(2, "little")
        valid_packet = header + body + sfcs

        # Packet распарсен успешно
        packet = Packet(packet_id=1, packet_type=1)
        parse_result = ParseResult(packet=packet, raw_bytes=valid_packet)
        mock_protocol.parse_packet.return_value = parse_result
        mock_protocol.validate_crc8.return_value = True
        mock_protocol.validate_crc16.return_value = True

        pipeline = PacketPipeline()
        pipeline.add("parse", ParseMiddleware(mock_session_mgr), order=1)
        pipeline.add("crc", CrcValidationMiddleware(mock_session_mgr), order=2)

        ctx = PacketContext(raw=valid_packet, connection_id="test-conn")
        result = await pipeline.process(ctx)

        # Parse успешен
        assert result.parsed is not None
        # CRC валидация прошла
        assert result.crc_valid is True
        assert result.terminated is False
