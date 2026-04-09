"""Тесты для PacketPipeline и PacketContext."""

from __future__ import annotations

import time

import pytest

from core.pipeline import PacketContext, PacketPipeline

# =============================================================================
# PacketContext
# =============================================================================


class TestPacketContext:
    """Тесты инициализации PacketContext."""

    def test_context_init_minimal(self) -> None:
        """Минимальный контекст — только обязательные поля."""
        ctx = PacketContext(raw=b"\x01\x00\x00", connection_id="conn-1")

        assert ctx.raw == b"\x01\x00\x00"
        assert ctx.connection_id == "conn-1"
        assert ctx.channel == "tcp"
        assert ctx.parsed is None
        assert ctx.crc8_valid is False
        assert ctx.crc16_valid is False
        assert ctx.crc_valid is False
        assert ctx.is_duplicate is False
        assert ctx.response_data is None
        assert ctx.terminated is False
        assert ctx.errors == []
        assert isinstance(ctx.timestamp, float)

    def test_context_channel_sms(self) -> None:
        """Контекст для SMS-канала."""
        ctx = PacketContext(raw=b"", connection_id="c1", channel="sms")
        assert ctx.channel == "sms"

    def test_context_timestamp_is_current(self) -> None:
        """Timestamp близок к текущему monotonic времени."""
        before = time.monotonic()
        ctx = PacketContext(raw=b"", connection_id="c1")
        after = time.monotonic()

        assert before <= ctx.timestamp <= after

    def test_context_fields_mutable(self) -> None:
        """Поля контекста изменяемы (middleware меняют ctx)."""
        ctx = PacketContext(raw=b"", connection_id="c1")
        ctx.crc8_valid = True
        ctx.crc16_valid = True
        ctx.crc_valid = True
        ctx.terminated = True
        ctx.is_duplicate = True
        ctx.parsed = {"service": 1}
        ctx.response_data = b"\x01\x02\x03"
        ctx.errors.append("test error")

        assert ctx.crc8_valid is True
        assert ctx.crc16_valid is True
        assert ctx.crc_valid is True
        assert ctx.terminated is True
        assert ctx.is_duplicate is True
        assert ctx.parsed == {"service": 1}
        assert ctx.response_data == b"\x01\x02\x03"
        assert ctx.errors == ["test error"]


# =============================================================================
# PacketPipeline
# =============================================================================


class TestPacketPipeline:
    """Тесты конвейера обработки пакетов."""

    def _make_ctx(self) -> PacketContext:
        return PacketContext(raw=b"\x01\x02\x03", connection_id="conn-1")

    # ---------- add + process ----------

    @pytest.mark.asyncio
    async def test_pipeline_executes_middleware_in_order(self) -> None:
        """Middleware выполняются строго по порядку добавления."""
        pipeline = PacketPipeline()
        calls: list[str] = []

        async def mw_a(ctx: PacketContext) -> None:
            calls.append("A")

        async def mw_b(ctx: PacketContext) -> None:
            calls.append("B")

        async def mw_c(ctx: PacketContext) -> None:
            calls.append("C")

        pipeline.add("a", mw_a, order=1)
        pipeline.add("b", mw_b, order=2)
        pipeline.add("c", mw_c, order=3)

        ctx = self._make_ctx()
        await pipeline.process(ctx)

        assert calls == ["A", "B", "C"]

    @pytest.mark.asyncio
    async def test_pipeline_respects_order_parameter(self) -> None:
        """Параметр order определяет порядок выполнения."""
        pipeline = PacketPipeline()
        calls: list[str] = []

        async def mw_a(ctx: PacketContext) -> None:
            calls.append("A")

        async def mw_b(ctx: PacketContext) -> None:
            calls.append("B")

        # Добавляем в обратном порядке, но с правильными order
        pipeline.add("b", mw_b, order=2)
        pipeline.add("a", mw_a, order=1)

        ctx = self._make_ctx()
        await pipeline.process(ctx)

        assert calls == ["A", "B"]

    @pytest.mark.asyncio
    async def test_pipeline_same_order_addition_order(self) -> None:
        """При одинаковом order — порядок добавления."""
        pipeline = PacketPipeline()
        calls: list[str] = []

        async def mw_a(ctx: PacketContext) -> None:
            calls.append("A")

        async def mw_b(ctx: PacketContext) -> None:
            calls.append("B")

        pipeline.add("a", mw_a, order=1)
        pipeline.add("b", mw_b, order=1)

        ctx = self._make_ctx()
        await pipeline.process(ctx)

        assert calls == ["A", "B"]

    # ---------- terminated ----------

    @pytest.mark.asyncio
    async def test_pipeline_stops_on_terminated(self) -> None:
        """Прерывание цепочки при terminated=True."""
        pipeline = PacketPipeline()
        calls: list[str] = []

        async def mw_a(ctx: PacketContext) -> None:
            calls.append("A")
            ctx.terminated = True

        async def mw_b(ctx: PacketContext) -> None:
            calls.append("B")

        async def mw_c(ctx: PacketContext) -> None:
            calls.append("C")

        pipeline.add("a", mw_a, order=1)
        pipeline.add("b", mw_b, order=2)
        pipeline.add("c", mw_c, order=3)

        ctx = self._make_ctx()
        await pipeline.process(ctx)

        assert calls == ["A"]
        assert ctx.terminated is True

    @pytest.mark.asyncio
    async def test_pipeline_skips_if_already_terminated(self) -> None:
        """Если ctx.terminated=True ДО pipeline — ничего не выполняется."""
        pipeline = PacketPipeline()
        calls: list[str] = []

        async def mw_a(ctx: PacketContext) -> None:
            calls.append("A")

        pipeline.add("a", mw_a, order=1)

        ctx = self._make_ctx()
        ctx.terminated = True
        await pipeline.process(ctx)

        assert calls == []

    # ---------- exception handling ----------

    @pytest.mark.asyncio
    async def test_pipeline_catches_exception(self) -> None:
        """Исключение записывается в ctx.errors, цепочка прерывается."""
        pipeline = PacketPipeline()
        calls: list[str] = []

        async def mw_a(ctx: PacketContext) -> None:
            calls.append("A")

        async def mw_b(ctx: PacketContext) -> None:
            calls.append("B")
            raise RuntimeError("boom")

        async def mw_c(ctx: PacketContext) -> None:
            calls.append("C")

        pipeline.add("a", mw_a, order=1)
        pipeline.add("b", mw_b, order=2)
        pipeline.add("c", mw_c, order=3)

        ctx = self._make_ctx()
        # Исключение НЕ пробрасывается — записывается в errors
        result = await pipeline.process(ctx)

        assert calls == ["A", "B"]
        assert len(ctx.errors) == 1
        assert "b: boom" in ctx.errors[0]
        assert ctx.terminated is True
        assert result is ctx

    # ---------- context passthrough ----------

    @pytest.mark.asyncio
    async def test_pipeline_context_passes_through(self) -> None:
        """Один и тот же ctx передаётся всем middleware."""
        pipeline = PacketPipeline()
        ids: list[int] = []

        async def mw_a(ctx: PacketContext) -> None:
            ids.append(id(ctx))
            ctx.parsed = {"step": "A"}

        async def mw_b(ctx: PacketContext) -> None:
            ids.append(id(ctx))
            assert ctx.parsed == {"step": "A"}  # видит изменения mw_a
            ctx.parsed["step"] = "B"

        async def mw_c(ctx: PacketContext) -> None:
            ids.append(id(ctx))
            assert ctx.parsed == {"step": "B"}  # видит изменения mw_b

        pipeline.add("a", mw_a, order=1)
        pipeline.add("b", mw_b, order=2)
        pipeline.add("c", mw_c, order=3)

        ctx = self._make_ctx()
        result = await pipeline.process(ctx)

        assert result is ctx  # возвращается тот же объект
        assert len(set(ids)) == 1  # все видели один и тот же ctx

    # ---------- empty pipeline ----------

    @pytest.mark.asyncio
    async def test_empty_pipeline_returns_ctx(self) -> None:
        """Пустой pipeline просто возвращает ctx."""
        pipeline = PacketPipeline()
        ctx = self._make_ctx()
        result = await pipeline.process(ctx)

        assert result is ctx
        assert result.terminated is False

    # ---------- middleware list ----------

    def test_pipeline_add_multiple(self) -> None:
        """Можно добавить сколько угодно middleware."""
        pipeline = PacketPipeline()

        async def mw(ctx: PacketContext) -> None:
            pass

        pipeline.add("a", mw, order=1)
        pipeline.add("b", mw, order=2)
        pipeline.add("c", mw, order=3)

        assert len(pipeline._middlewares) == 3

    # ---------- response_data ----------

    @pytest.mark.asyncio
    async def test_response_data_set_by_middleware(self) -> None:
        """Middleware может установить response_data."""
        pipeline = PacketPipeline()

        async def mw_response(ctx: PacketContext) -> None:
            ctx.response_data = b"\x01\x00\x02"

        pipeline.add("resp", mw_response, order=1)

        ctx = self._make_ctx()
        await pipeline.process(ctx)

        assert ctx.response_data == b"\x01\x00\x02"

    # ---------- errors accumulation ----------

    @pytest.mark.asyncio
    async def test_errors_list_populated_on_exception(self) -> None:
        """ctx.errors заполняется при исключении."""
        pipeline = PacketPipeline()

        async def mw_ok(ctx: PacketContext) -> None:
            pass

        async def mw_fail(ctx: PacketContext) -> None:
            raise ValueError("bad crc")

        pipeline.add("ok", mw_ok, order=1)
        pipeline.add("fail", mw_fail, order=2)

        ctx = self._make_ctx()
        await pipeline.process(ctx)

        assert len(ctx.errors) == 1
        assert "fail: bad crc" in ctx.errors[0]
