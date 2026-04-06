"""Tests for EventBus — async event bus with ordered/parallel handlers."""

import asyncio

import pytest

from core.event_bus import Event, EventBus

_HandlerData = dict[str, object]

# --- Basic emit/subscribe ---


class TestBasicEmit:
    """Basic emit and subscribe functionality."""

    @pytest.mark.asyncio
    async def test_sync_handler_receives_data(self) -> None:
        """Sync handler receives emitted data."""
        bus = EventBus()
        received: list[_HandlerData] = []

        def handler(data: _HandlerData) -> None:
            received.append(data)

        bus.on("test.event", handler)
        await bus.emit("test.event", {"key": "value"})

        assert received == [{"key": "value"}]

    @pytest.mark.asyncio
    async def test_async_handler_receives_data(self) -> None:
        """Async handler receives emitted data."""
        bus = EventBus()
        received: list[_HandlerData] = []

        async def handler(data: _HandlerData) -> None:
            received.append(data)

        bus.on("test.event", handler)
        await bus.emit("test.event", {"key": "value"})

        assert received == [{"key": "value"}]

    @pytest.mark.asyncio
    async def test_multiple_handlers_receive_same_event(self) -> None:
        """Multiple handlers all receive the same event."""
        bus = EventBus()
        results: list[str] = []

        async def handler_a(data: _HandlerData) -> None:
            results.append("a:" + str(data.get("val")))

        async def handler_b(data: _HandlerData) -> None:
            results.append("b:" + str(data.get("val")))

        bus.on("test.event", handler_a)
        bus.on("test.event", handler_b)
        await bus.emit("test.event", {"val": 42})

        assert len(results) == 2
        assert "a:42" in results
        assert "b:42" in results

    @pytest.mark.asyncio
    async def test_emit_to_no_subscribers_no_error(self) -> None:
        """Emitting to an event with no subscribers does not raise."""
        bus = EventBus()
        await bus.emit("test.event", {"data": "nobody cares"})
        # No assertion needed — just no crash


# --- Ordered handlers ---


class TestOrderedHandlers:
    """Ordered handlers execute sequentially in registration order."""

    @pytest.mark.asyncio
    async def test_ordered_handlers_execute_sequentially(self) -> None:
        """Ordered handlers run one after another, not in parallel."""
        bus = EventBus()
        order: list[str] = []

        async def handler_1(data: _HandlerData) -> None:
            order.append("1_start")
            await asyncio.sleep(0.05)
            order.append("1_end")

        async def handler_2(data: _HandlerData) -> None:
            order.append("2_start")
            await asyncio.sleep(0.01)
            order.append("2_end")

        bus.on("test.event", handler_1, ordered=True)
        bus.on("test.event", handler_2, ordered=True)
        await bus.emit("test.event", {})

        # handler_2 must start after handler_1 ends
        assert order == ["1_start", "1_end", "2_start", "2_end"]

    @pytest.mark.asyncio
    async def test_ordered_handlers_share_state(self) -> None:
        """Ordered handlers can safely mutate shared state."""
        bus = EventBus()
        counter = {"value": 0}

        async def increment(data: _HandlerData) -> None:
            counter["value"] += 1

        bus.on("test.event", increment, ordered=True)
        bus.on("test.event", increment, ordered=True)
        bus.on("test.event", increment, ordered=True)
        await bus.emit("test.event", {})

        assert counter["value"] == 3


# --- Parallel handlers ---


class TestParallelHandlers:
    """Parallel handlers execute concurrently via asyncio.gather."""

    @pytest.mark.asyncio
    async def test_parallel_handlers_run_concurrently(self) -> None:
        """Parallel handlers start at approximately the same time."""
        bus = EventBus()
        timestamps: list[float] = []

        async def handler(data: _HandlerData) -> None:
            timestamps.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)

        bus.on("test.event", handler)
        bus.on("test.event", handler)
        bus.on("test.event", handler)

        start = asyncio.get_event_loop().time()
        await bus.emit("test.event", {})
        elapsed = asyncio.get_event_loop().time() - start

        # If parallel, total time ≈ 0.1s; if sequential, ≈ 0.3s
        assert elapsed < 0.25
        assert len(timestamps) == 3

    @pytest.mark.asyncio
    async def test_parallel_handlers_error_doesnt_block_others(self) -> None:
        """One parallel handler raising exception doesn't stop others."""
        bus = EventBus()
        results: list[str] = []

        async def failing_handler(data: _HandlerData) -> None:
            results.append("failing")
            raise ValueError("intentional error")

        async def ok_handler(data: _HandlerData) -> None:
            await asyncio.sleep(0.05)
            results.append("ok")

        bus.on("test.event", failing_handler)
        bus.on("test.event", ok_handler)

        # Should not raise — errors are caught by gather(return_exceptions=True)
        await bus.emit("test.event", {})

        assert "failing" in results
        assert "ok" in results


# --- Ordered before Parallel ---


class TestOrderedBeforeParallel:
    """Ordered handlers complete before parallel handlers start."""

    @pytest.mark.asyncio
    async def test_ordered_completes_before_parallel_starts(self) -> None:
        """All ordered handlers finish before any parallel handler begins."""
        bus = EventBus()
        order: list[str] = []

        async def ordered_handler(data: _HandlerData) -> None:
            order.append("ordered_start")
            await asyncio.sleep(0.05)
            order.append("ordered_end")

        async def parallel_handler(data: _HandlerData) -> None:
            order.append("parallel")

        bus.on("test.event", ordered_handler, ordered=True)
        bus.on("test.event", parallel_handler, ordered=False)
        await bus.emit("test.event", {})

        # Parallel must not start until ordered is done
        parallel_idx = order.index("parallel")
        ordered_end_idx = order.index("ordered_end")
        assert parallel_idx > ordered_end_idx


# --- Unsubscribe ---


class TestUnsubscribe:
    """off() removes handler from subscribers."""

    @pytest.mark.asyncio
    async def test_off_removes_sync_handler(self) -> None:
        """off() removes a sync handler."""
        bus = EventBus()
        calls: list[int] = []

        def handler(data: _HandlerData) -> None:
            calls.append(1)

        bus.on("test.event", handler)
        await bus.emit("test.event", {})
        assert calls == [1]

        bus.off("test.event", handler)
        await bus.emit("test.event", {})
        assert calls == [1]  # No additional call

    @pytest.mark.asyncio
    async def test_off_removes_async_handler(self) -> None:
        """off() removes an async handler."""
        bus = EventBus()
        calls: list[int] = []

        async def handler(data: _HandlerData) -> None:
            calls.append(1)

        bus.on("test.event", handler)
        await bus.emit("test.event", {})
        assert calls == [1]

        bus.off("test.event", handler)
        await bus.emit("test.event", {})
        assert calls == [1]

    @pytest.mark.asyncio
    async def test_off_ordered_handler(self) -> None:
        """off() removes an ordered handler."""
        bus = EventBus()
        calls: list[int] = []

        async def handler(data: _HandlerData) -> None:
            calls.append(1)

        bus.on("test.event", handler, ordered=True)
        await bus.emit("test.event", {})
        assert calls == [1]

        bus.off("test.event", handler)
        await bus.emit("test.event", {})
        assert calls == [1]

    @pytest.mark.asyncio
    async def test_off_nonexistent_handler_no_error(self) -> None:
        """off() on a handler that was never added does not raise."""
        bus = EventBus()

        async def handler(data: _HandlerData) -> None:
            pass

        bus.off("test.event", handler)
        # No crash


# --- Event dataclass ---


class TestEvent:
    """Event dataclass."""

    def test_event_creation(self) -> None:
        """Event can be created with name and data."""
        event = Event(name="test.event", data={"key": "value"})
        assert event.name == "test.event"
        assert event.data == {"key": "value"}
