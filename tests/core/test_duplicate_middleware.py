# mypy: ignore-errors
"""Тесты DuplicateDetectionMiddleware.

Проверяют обнаружение дубликатов PID через LRU-кэш UsvConnection:
- Первый пакет — не дубликат, RESPONSE НЕ формируется
- Повторный PID — дубликат, terminated=True, response_data из кэша
- Отсутствие подключения — terminated без ошибки
- Отсутствие parsed — пропускает (ждёт ParseMiddleware)
"""

from unittest.mock import MagicMock

import pytest

from core.pipeline import (
    CrcValidationMiddleware,
    DuplicateDetectionMiddleware,
    PacketContext,
    PacketPipeline,
)
from core.session import SessionManager, UsvConnection

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_protocol():
    """Mock IEgtsProtocol."""
    proto = MagicMock()
    proto.validate_crc8.return_value = True
    proto.validate_crc16.return_value = True
    proto.build_response.return_value = b"\x00\x00\x01\x00"
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
def valid_egts_packet():
    """Минимальный валидный EGTS-пакет с корректными CRC."""
    from libs.egts_protocol_gost2015.gost2015_impl.crc import crc8, crc16

    header_base = bytearray([
        0x01,  # PRV = 1
        0x00,  # SKID = 0
        0x00,  # Flags
        11,    # HL = 11
        0x00,  # HE
        0x00, 0x00,  # FDL = 0
        0x01, 0x00,  # PID = 1
        0x01,  # PT = 1
    ])
    hcs = crc8(bytes(header_base))
    header = header_base + bytes([hcs])

    body = b""
    sfcs = crc16(body).to_bytes(2, "little")

    return header + body + sfcs


@pytest.fixture
def parsed_ctx():
    """PacketContext с уже распарсенным пакетом (PID=42)."""
    from libs.egts_protocol_iface.models import Packet, ParseResult

    packet = Packet(packet_id=42, packet_type=1)
    parsed = ParseResult(packet=packet)

    ctx = PacketContext(raw=b"\x01" * 20, connection_id="test-conn")
    ctx.crc_valid = True
    ctx.parsed = parsed

    return ctx


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestDuplicateDetectionFirstPacket:
    """Первый пакет с таким PID — не дубликат."""

    @pytest.mark.asyncio
    async def test_first_packet_not_duplicate(self, mock_session_mgr, parsed_ctx):
        """PID впервые виден — is_duplicate=False, terminated=False."""
        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(parsed_ctx)

        assert parsed_ctx.is_duplicate is False
        assert parsed_ctx.terminated is False
        assert parsed_ctx.response_data is None

    @pytest.mark.asyncio
    async def test_first_packet_not_cached(self, mock_session_mgr, parsed_ctx):
        """Первый пакет НЕ сохраняется в кэш — RESPONSE формируется позже."""
        conn = mock_session_mgr.get_session("test-conn")
        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(parsed_ctx)

        # PID=42 НЕ в кэше — Dedup только обнаруживает, не кеширует
        assert conn.get_response(42) is None


class TestDuplicateDetectionDuplicate:
    """Повторный PID — дубликат, отправка RESPONSE из кэша."""

    @pytest.mark.asyncio
    async def test_duplicate_detected(self, mock_session_mgr, parsed_ctx):
        """Повторный PID — is_duplicate=True, terminated=True."""
        conn = mock_session_mgr.get_session("test-conn")
        # Предварительно добавим PID=42 в кэш с RESPONSE
        conn.add_pid_response(42, b"\x00\x00\x01\x00")

        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(parsed_ctx)

        assert parsed_ctx.is_duplicate is True
        assert parsed_ctx.terminated is True
        assert parsed_ctx.response_data == b"\x00\x00\x01\x00"

    @pytest.mark.asyncio
    async def test_response_from_cache_not_rebuilt(
        self, mock_session_mgr, mock_protocol, parsed_ctx
    ):
        """RESPONSE берётся из кэша, build_response НЕ вызывается."""
        conn = mock_session_mgr.get_session("test-conn")
        cached_response = b"\xAA\xBB\xCC\xDD"
        conn.add_pid_response(42, cached_response)

        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(parsed_ctx)

        mock_protocol.build_response.assert_not_called()
        assert parsed_ctx.response_data == cached_response


    @pytest.mark.asyncio
    async def test_already_marked_duplicate_skips(self, mock_session_mgr, parsed_ctx):
        """ctx.is_duplicate=True — пропускает без повторной проверки."""
        parsed_ctx.is_duplicate = True

        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(parsed_ctx)

        # Не должен менять terminated
        assert parsed_ctx.terminated is False
        assert parsed_ctx.is_duplicate is True
        assert parsed_ctx.response_data is None


class TestDuplicateDetectionEdgeCases:
    """Edge cases: нет подключения, нет parsed, crc невалиден."""

    @pytest.mark.asyncio
    async def test_no_connection(self, mock_session_mgr, parsed_ctx):
        """connection_id не найден — пропускает без ошибки."""
        mock_session_mgr.get_session = MagicMock(return_value=None)

        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(parsed_ctx)

        assert parsed_ctx.terminated is False
        assert parsed_ctx.is_duplicate is False

    @pytest.mark.asyncio
    async def test_no_parsed_packet(self, mock_session_mgr):
        """parsed=None — пропускает (ждёт ParseMiddleware)."""
        ctx = PacketContext(raw=b"\x01" * 20, connection_id="test-conn")
        ctx.crc_valid = True  # CRC уже проверен

        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(ctx)

        assert ctx.terminated is False
        assert ctx.is_duplicate is False

    @pytest.mark.asyncio
    async def test_crc_invalid_skips_dedup(self, mock_session_mgr, parsed_ctx):
        """crc_valid=False — пропускает (пакет с ошибкой CRC не дубликат)."""
        parsed_ctx.crc_valid = False

        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(parsed_ctx)

        assert parsed_ctx.terminated is False
        assert parsed_ctx.is_duplicate is False

    @pytest.mark.asyncio
    async def test_parsed_packet_is_none(self, mock_session_mgr):
        """parsed.packet=None — пропускает."""
        from libs.egts_protocol_iface.models import ParseResult

        ctx = PacketContext(raw=b"\x01" * 20, connection_id="test-conn")
        ctx.crc_valid = True
        ctx.parsed = ParseResult(packet=None)

        mw = DuplicateDetectionMiddleware(mock_session_mgr)
        await mw(ctx)

        assert ctx.terminated is False
        assert ctx.is_duplicate is False


class TestDuplicateDetectionIntegration:
    """Интеграция с полным pipeline: CRC → Dedup."""

    @pytest.mark.asyncio
    async def test_pipeline_crc_then_dedup_first_packet(
        self, mock_session_mgr, valid_egts_packet
    ):
        """Первый валидный пакет проходит CRC и Dedup."""
        pipeline = PacketPipeline()
        pipeline.add("crc", CrcValidationMiddleware(mock_session_mgr), order=10)
        pipeline.add("dedup", DuplicateDetectionMiddleware(mock_session_mgr), order=20)

        ctx = PacketContext(raw=valid_egts_packet, connection_id="test-conn")
        # Для Dedup нужен parsed — имитируем что ParseMiddleware уже отработал
        from libs.egts_protocol_iface.models import Packet, ParseResult

        # В реальности это делает ParseMiddleware, здесь — вручную для теста
        ctx.crc_valid = True  # CRC прошёл
        ctx.parsed = ParseResult(packet=Packet(packet_id=1, packet_type=1))

        result = await pipeline.process(ctx)

        assert result.crc_valid is True
        assert result.is_duplicate is False
        assert result.terminated is False

    @pytest.mark.asyncio
    async def test_pipeline_dedup_caches_response(
        self, mock_session_mgr, valid_egts_packet
    ):
        """Два одинаковых пакета — второй определяется как дубликат."""
        pipeline = PacketPipeline()
        pipeline.add("dedup", DuplicateDetectionMiddleware(mock_session_mgr), order=10)

        from libs.egts_protocol_iface.models import Packet, ParseResult

        # Первый пакет
        ctx1 = PacketContext(raw=valid_egts_packet, connection_id="test-conn")
        ctx1.crc_valid = True
        ctx1.parsed = ParseResult(packet=Packet(packet_id=99, packet_type=1))
        await pipeline.process(ctx1)
        assert ctx1.is_duplicate is False

        # Вручную добавим PID=99 в кэш (это делает уровень сервисной обработки)
        conn = mock_session_mgr.get_session("test-conn")
        conn.add_pid_response(99, b"\x00\x00\x01\x00")

        # Второй пакет (тот же PID=99)
        ctx2 = PacketContext(raw=valid_egts_packet, connection_id="test-conn")
        ctx2.crc_valid = True
        ctx2.parsed = ParseResult(packet=Packet(packet_id=99, packet_type=1))
        await pipeline.process(ctx2)

        assert ctx2.is_duplicate is True
        assert ctx2.terminated is True
        assert ctx2.response_data is not None
