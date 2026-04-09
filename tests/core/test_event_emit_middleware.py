# mypy: ignore-errors
"""Тесты EventEmitMiddleware.

Проверяют публикацию события packet.processed после обработки пакета
в конвейере, а также корректность передаваемых данных.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.pipeline import EventEmitMiddleware, PacketContext

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bus():
    """Mock EventBus."""
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def sample_ctx():
    """Базовый PacketContext для тестов."""
    return PacketContext(
        raw=b"\x01\x00\x01\x00",
        connection_id="test-conn",
        channel="tcp",
        parsed={"packet": None, "service": 1, "tid": 12345},
        crc8_valid=True,
        crc16_valid=True,
        crc_valid=True,
        is_duplicate=False,
        response_data=None,
        terminated=False,
        errors=[],
    )


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestEventEmitMiddlewareSuccess:
    """Успешная публикация события packet.processed."""

    @pytest.mark.asyncio
    async def test_emit_packet_processed(self, mock_bus, sample_ctx):
        """EventEmitMiddleware вызывает bus.emit с событием packet.processed."""
        mw = EventEmitMiddleware(mock_bus)
        await mw(sample_ctx)

        mock_bus.emit.assert_called_once()
        call_args = mock_bus.emit.call_args

        # Первый позиционный аргумент — имя события
        assert call_args[0][0] == "packet.processed"

    @pytest.mark.asyncio
    async def test_emit_data_contains_ctx(self, mock_bus, sample_ctx):
        """Данные события содержат ctx."""
        mw = EventEmitMiddleware(mock_bus)
        await mw(sample_ctx)

        call_args = mock_bus.emit.call_args
        event_data = call_args[0][1]

        assert "ctx" in event_data
        assert event_data["ctx"] is sample_ctx

    @pytest.mark.asyncio
    async def test_emit_data_contains_connection_id(self, mock_bus, sample_ctx):
        """Данные события содержат connection_id."""
        mw = EventEmitMiddleware(mock_bus)
        await mw(sample_ctx)

        call_args = mock_bus.emit.call_args
        event_data = call_args[0][1]

        assert "connection_id" in event_data
        assert event_data["connection_id"] == "test-conn"

    @pytest.mark.asyncio
    async def test_emit_data_complete(self, mock_bus, sample_ctx):
        """Данные события содержат все необходимые поля."""
        mw = EventEmitMiddleware(mock_bus)
        await mw(sample_ctx)

        call_args = mock_bus.emit.call_args
        event_data = call_args[0][1]

        # Все ключевые поля присутствуют
        assert "ctx" in event_data
        assert "connection_id" in event_data
        assert "channel" in event_data
        assert "parsed" in event_data
        assert "crc_valid" in event_data
        assert "is_duplicate" in event_data
        assert "terminated" in event_data

        # Проверка значений
        assert event_data["connection_id"] == "test-conn"
        assert event_data["channel"] == "tcp"
        assert event_data["crc_valid"] is True
        assert event_data["is_duplicate"] is False
        assert event_data["terminated"] is False


class TestEventEmitMiddlewareEdgeCases:
    """Edge cases: terminated=True, ошибки, разные каналы."""

    @pytest.mark.asyncio
    async def test_emit_on_terminated(self, mock_bus):
        """Событие эмитится даже при terminated=True (для логирования)."""
        ctx = PacketContext(
            raw=b"\xff\xff",
            connection_id="error-conn",
            channel="tcp",
            parsed=None,
            crc_valid=False,
            terminated=True,
            errors=["Parse error"],
        )

        mw = EventEmitMiddleware(mock_bus)
        await mw(ctx)

        # Событие всё равно эмитится
        mock_bus.emit.assert_called_once()
        call_args = mock_bus.emit.call_args
        event_data = call_args[0][1]

        assert event_data["terminated"] is True
        assert event_data["crc_valid"] is False
        assert event_data["connection_id"] == "error-conn"

    @pytest.mark.asyncio
    async def test_emit_with_errors(self, mock_bus):
        """Событие эмитится с ошибками в ctx.errors."""
        ctx = PacketContext(
            raw=b"\xff\xff",
            connection_id="error-conn",
            channel="sms",
            parsed=None,
            crc_valid=False,
            terminated=True,
            errors=["CRC-8 mismatch", "Parse failed"],
        )

        mw = EventEmitMiddleware(mock_bus)
        await mw(ctx)

        call_args = mock_bus.emit.call_args
        event_data = call_args[0][1]

        assert len(event_data["ctx"].errors) == 2
        assert event_data["channel"] == "sms"

    @pytest.mark.asyncio
    async def test_emit_on_duplicate(self, mock_bus):
        """Событие эмитится для дубликата (для статистики)."""
        ctx = PacketContext(
            raw=b"\x01\x00\x01\x00",
            connection_id="dup-conn",
            channel="tcp",
            parsed={"packet": None},
            crc_valid=True,
            is_duplicate=True,
            response_data=b"\x00\x00\x01\x00",
        )

        mw = EventEmitMiddleware(mock_bus)
        await mw(ctx)

        call_args = mock_bus.emit.call_args
        event_data = call_args[0][1]

        assert event_data["is_duplicate"] is True
        assert event_data["ctx"].response_data == b"\x00\x00\x01\x00"


class TestEventEmitMiddlewareIntegration:
    """Интеграция EventEmitMiddleware с PacketPipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_emits_event(self, mock_bus):
        """PacketPipeline + EventEmitMiddleware: событие эмитится после обработки."""
        from core.pipeline import PacketPipeline

        pipeline = PacketPipeline()
        pipeline.add("event", EventEmitMiddleware(mock_bus), order=1)

        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        await pipeline.process(ctx)

        mock_bus.emit.assert_called_once()
        call_args = mock_bus.emit.call_args
        event_data = call_args[0][1]

        assert event_data["connection_id"] == "test-conn"
        assert event_data["ctx"].raw == b"\x01\x00\x01\x00"

    @pytest.mark.asyncio
    async def test_pipeline_emits_after_all_middleware(self, mock_bus):
        """Событие эмитится ПОСЛЕ всех middleware (последним в цепочке)."""
        from core.pipeline import PacketPipeline

        call_order = []

        async def tracking_mw(ctx):
            call_order.append("tracking")

        pipeline = PacketPipeline()
        pipeline.add("tracking", tracking_mw, order=1)
        pipeline.add("event", EventEmitMiddleware(mock_bus), order=2)

        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        await pipeline.process(ctx)

        # tracking выполнил до event
        assert call_order == ["tracking"]
        # Событие эмитилось
        mock_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_terminated_still_emits(self, mock_bus):
        """Событие эмитится даже если pipeline прерван (для логирования)."""
        from core.pipeline import PacketPipeline

        async def terminating_mw(ctx):
            ctx.terminated = True
            ctx.errors.append("Test error")

        pipeline = PacketPipeline()
        pipeline.add("terminator", terminating_mw, order=1)
        pipeline.add("event", EventEmitMiddleware(mock_bus), order=2)

        ctx = PacketContext(raw=b"\x01\x00\x01\x00", connection_id="test-conn")
        await pipeline.process(ctx)

        # Событие всё равно эмитится
        mock_bus.emit.assert_called_once()
        call_args = mock_bus.emit.call_args
        event_data = call_args[0][1]

        assert event_data["terminated"] is True
        assert len(event_data["ctx"].errors) == 1
