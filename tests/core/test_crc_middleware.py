# mypy: ignore-errors
"""Тесты CrcValidationMiddleware.

Проверяют валидацию CRC-8/CRC-16 через injectable protocol,
обработку ошибок и edge cases (нет подключения, protocol=None).
"""

from unittest.mock import MagicMock

import pytest

from core.pipeline import CrcValidationMiddleware, PacketContext
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
    """Минимальный валидный EGTS-пакет с корректными CRC.

    Структура: PRV(1) + SKID(1) + Flags(1) + HL(1) + HE(1) + FDL(2) + PID(2) + PT(1) + HCS(1) + body + CRC16(2)
    HL = 11 (без маршрутизации)
    """
    from libs.egts_protocol_gost2015.gost2015_impl.crc import crc8, crc16

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

    return header + body + sfcs


@pytest.fixture
def packet_with_bad_crc8():
    """Пакет с невалидным CRC-8 заголовка."""
    from libs.egts_protocol_gost2015.gost2015_impl.crc import crc16

    header_base = bytearray([
        0x01,  # PRV
        0x00,  # SKID
        0x00,  # Flags
        11,    # HL
        0x00,  # HE
        0x00, 0x00,  # FDL
        0x01, 0x00,  # PID
        0x01,  # PT
    ])
    # Неправильный HCS
    header = header_base + bytes([0xFF])

    body = b""
    sfcs = crc16(body).to_bytes(2, "little")

    return header + body + sfcs


@pytest.fixture
def packet_with_bad_crc16():
    """Пакет с невалидным CRC-16 данных."""
    from libs.egts_protocol_gost2015.gost2015_impl.crc import crc8

    header_base = bytearray([
        0x01,  # PRV
        0x00,  # SKID
        0x00,  # Flags
        11,    # HL
        0x00,  # HE
        0x00, 0x00,  # FDL
        0x01, 0x00,  # PID
        0x01,  # PT
    ])
    hcs = crc8(bytes(header_base))
    header = header_base + bytes([hcs])

    body = b"\x01\x00\x00\x05\x00"  # какие-то данные
    # Неправильный CRC-16
    sfcs = b"\xFF\xFF"

    return header + body + sfcs


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestCrcValidationValid:
    """Валидные CRC — crc_valid=True, terminated=False."""

    @pytest.mark.asyncio
    async def test_valid_crc8_and_crc16(self, mock_session_mgr, valid_egts_packet):
        """Оба CRC корректны — crc_valid=True, crc8_valid=True, crc16_valid=True."""
        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=valid_egts_packet, connection_id="test-conn")
        await mw(ctx)

        assert ctx.crc_valid is True
        assert ctx.crc8_valid is True
        assert ctx.crc16_valid is True
        assert ctx.terminated is False
        assert ctx.response_data is None

    @pytest.mark.asyncio
    async def test_protocol_validate_called(self, mock_session_mgr, mock_protocol, valid_egts_packet):
        """validate_crc8 и validate_crc16 вызываются с правильными аргументами."""
        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=valid_egts_packet, connection_id="test-conn")
        await mw(ctx)

        mock_protocol.validate_crc8.assert_called_once()
        mock_protocol.validate_crc16.assert_called_once()


class TestCrcValidationInvalid:
    """Невалидный CRC — crc_valid=False, terminated=True, response_data=RESPONSE."""

    @pytest.mark.asyncio
    async def test_bad_crc8(self, mock_session_mgr, mock_protocol, packet_with_bad_crc8):
        """CRC-8 заголовка невалиден → crc8_valid=False, result_code=137."""
        mock_protocol.validate_crc8.return_value = False

        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=packet_with_bad_crc8, connection_id="test-conn")
        await mw(ctx)

        assert ctx.crc_valid is False
        assert ctx.crc8_valid is False
        assert ctx.crc16_valid is False  # CRC-16 не проверялся
        assert ctx.terminated is True
        assert ctx.response_data is not None

        # build_response вызван с result_code=137 (HEADER_CRC_ERROR)
        mock_protocol.build_response.assert_called_once()
        call_kwargs = mock_protocol.build_response.call_args
        assert call_kwargs.kwargs.get("result_code") == 137

    @pytest.mark.asyncio
    async def test_bad_crc16(self, mock_session_mgr, mock_protocol, packet_with_bad_crc16):
        """CRC-16 данных невалиден → crc16_valid=False, result_code=138."""
        mock_protocol.validate_crc16.return_value = False

        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=packet_with_bad_crc16, connection_id="test-conn")
        await mw(ctx)

        assert ctx.crc_valid is False
        assert ctx.crc8_valid is True  # CRC-8 прошёл
        assert ctx.crc16_valid is False
        assert ctx.terminated is True
        assert ctx.response_data is not None

        # build_response вызван с result_code=138 (DATA_CRC_ERROR)
        mock_protocol.build_response.assert_called_once()
        call_kwargs = mock_protocol.build_response.call_args
        assert call_kwargs.kwargs.get("result_code") == 138


class TestCrcValidationEdgeCases:
    """Edge cases: нет подключения, protocol=None, пустой пакет."""

    @pytest.mark.asyncio
    async def test_connection_not_found(self, mock_session_mgr, valid_egts_packet):
        """connection_id нет в session_mgr → terminated."""
        mock_session_mgr.get_session.return_value = None

        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=valid_egts_packet, connection_id="nonexistent-conn")
        await mw(ctx)

        assert ctx.crc_valid is False
        assert ctx.terminated is True

    @pytest.mark.asyncio
    async def test_protocol_is_none(self, valid_egts_packet):
        """connection найден, но protocol=None → terminated."""
        mgr = MagicMock(spec=SessionManager)
        conn = UsvConnection(connection_id="test-conn", protocol=None)
        mgr.get_session.return_value = conn

        mw = CrcValidationMiddleware(mgr)
        ctx = PacketContext(raw=valid_egts_packet, connection_id="test-conn")
        await mw(ctx)

        assert ctx.crc_valid is False
        assert ctx.terminated is True

    @pytest.mark.asyncio
    async def test_empty_packet(self, mock_session_mgr, mock_protocol):
        """Пустой raw → crc_valid=False, terminated=True."""
        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"", connection_id="test-conn")
        await mw(ctx)

        assert ctx.crc_valid is False
        assert ctx.terminated is True

    @pytest.mark.asyncio
    async def test_invalid_header_length(self, mock_session_mgr, mock_protocol):
        """HL < 11 (минимальный размер заголовка) → crc_valid=False, terminated=True."""
        # raw >= 4 байта, но raw[3] = 5 < PACKET_HEADER_MIN_SIZE (11)
        raw = bytes([0x01, 0x00, 0x00, 5, 0x00, 0x00])
        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=raw, connection_id="test-conn")
        await mw(ctx)

        assert ctx.crc_valid is False
        assert ctx.terminated is True

    @pytest.mark.asyncio
    async def test_packet_too_short(self, mock_session_mgr, mock_protocol):
        """raw < 4 байта (нет HL) → crc_valid=False, terminated=True."""
        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=b"\x01\x00\x00", connection_id="test-conn")
        await mw(ctx)

        assert ctx.crc_valid is False
        assert ctx.terminated is True

    @pytest.mark.asyncio
    async def test_body_too_short_for_crc16(self, mock_session_mgr, mock_protocol):
        """body < 2 байт (нет места для CRC-16) → crc_valid=False, terminated=True."""
        from libs.egts_protocol_gost2015.gost2015_impl.crc import crc8

        # HL=11, header корректный, но body = 1 байт (нужно минимум 2 для CRC-16)
        header_base = bytearray([
            0x01,  # PRV
            0x00,  # SKID
            0x00,  # Flags
            11,    # HL
            0x00,  # HE
            0x00, 0x00,  # FDL
            0x01, 0x00,  # PID
            0x01,  # PT
        ])
        hcs = crc8(bytes(header_base))
        header = header_base + bytes([hcs])

        # Body = 1 байт (меньше 2, нужных для CRC-16)
        raw = header + b"\x00"

        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=raw, connection_id="test-conn")
        await mw(ctx)

        assert ctx.crc_valid is False
        assert ctx.terminated is True

    @pytest.mark.asyncio
    async def test_protocol_not_hardcoded(self):
        """protocol берётся из conn.protocol, НЕ хардкод create_protocol()."""
        custom_proto = MagicMock()
        custom_proto.validate_crc8.return_value = True
        custom_proto.validate_crc16.return_value = True

        mgr = MagicMock(spec=SessionManager)
        conn = UsvConnection(connection_id="test-conn", protocol=custom_proto)
        mgr.get_session.return_value = conn

        # Минимальный пакет
        from libs.egts_protocol_gost2015.gost2015_impl.crc import crc8, crc16

        header_base = bytearray([0x01, 0x00, 0x00, 11, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01])
        header = header_base + bytes([crc8(bytes(header_base))])
        sfcs = crc16(b"").to_bytes(2, "little")
        raw = header + sfcs

        mw = CrcValidationMiddleware(mgr)
        ctx = PacketContext(raw=raw, connection_id="test-conn")
        await mw(ctx)

        # Убедимся что вызван именно custom_proto, не create_protocol
        custom_proto.validate_crc8.assert_called_once()
        custom_proto.validate_crc16.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_data_contains_build_response_result(
        self, mock_session_mgr, mock_protocol, packet_with_bad_crc8
    ):
        """response_data — результат protocol.build_response()."""
        mock_protocol.validate_crc8.return_value = False
        mock_protocol.build_response.return_value = b"\x01\x02\x03\x04"

        mw = CrcValidationMiddleware(mock_session_mgr)
        ctx = PacketContext(raw=packet_with_bad_crc8, connection_id="test-conn")
        await mw(ctx)

        assert ctx.response_data == b"\x01\x02\x03\x04"


class TestCrcValidationIntegration:
    """Интеграция CrcValidationMiddleware с PacketPipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_with_crc_middleware_valid(
        self, mock_session_mgr, valid_egts_packet
    ):
        """PacketPipeline + CrcValidationMiddleware: валидный пакет проходит."""
        from core.pipeline import PacketPipeline

        pipeline = PacketPipeline()
        pipeline.add("crc", CrcValidationMiddleware(mock_session_mgr), order=1)

        ctx = PacketContext(raw=valid_egts_packet, connection_id="test-conn")
        result = await pipeline.process(ctx)

        assert result.crc_valid is True
        assert result.terminated is False

    @pytest.mark.asyncio
    async def test_pipeline_with_crc_middleware_invalid(
        self, mock_session_mgr, mock_protocol, packet_with_bad_crc8
    ):
        """PacketPipeline + CrcValidationMiddleware: невалидный CRC прерывает цепочку."""
        from core.pipeline import PacketPipeline

        mock_protocol.validate_crc8.return_value = False

        pipeline = PacketPipeline()
        pipeline.add("crc", CrcValidationMiddleware(mock_session_mgr), order=1)

        ctx = PacketContext(raw=packet_with_bad_crc8, connection_id="test-conn")
        result = await pipeline.process(ctx)

        assert result.crc_valid is False
        assert result.terminated is True
        assert result.response_data is not None
