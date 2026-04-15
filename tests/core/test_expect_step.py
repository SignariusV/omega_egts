"""Tests for ExpectStep — ожидание пакета с проверкой и capture переменных."""

import asyncio
from unittest.mock import MagicMock, call

import pytest

from core.event_bus import EventBus
from core.scenario import ExpectStep, ScenarioContext


class TestExpectStepMatch:
    """ExpectStep — matching пакетов."""

    def test_exact_value_match(self) -> None:
        """Exact value match проходит."""
        step = ExpectStep(
            name="test",
            checks={"service": 1, "subrecord_type": "EGTS_SR_TERM_IDENTITY"},
        )
        parsed_data = {"service": 1, "subrecord_type": "EGTS_SR_TERM_IDENTITY"}
        assert step._matches(parsed_data) is True

    def test_exact_value_mismatch(self) -> None:
        """Exact value mismatch."""
        step = ExpectStep(name="test", checks={"service": 2})
        parsed_data = {"service": 1}
        assert step._matches(parsed_data) is False

    def test_range_match(self) -> None:
        """Range match (dict с min/max)."""
        step = ExpectStep(name="test", checks={"points_count": {"min": 1, "max": 100}})
        parsed_data = {"points_count": 50}
        assert step._matches(parsed_data) is True

    def test_range_below_min(self) -> None:
        """Range ниже min."""
        step = ExpectStep(name="test", checks={"points_count": {"min": 10, "max": 100}})
        parsed_data = {"points_count": 5}
        assert step._matches(parsed_data) is False

    def test_range_above_max(self) -> None:
        """Range выше max."""
        step = ExpectStep(name="test", checks={"points_count": {"min": 1, "max": 10}})
        parsed_data = {"points_count": 50}
        assert step._matches(parsed_data) is False

    def test_regex_match(self) -> None:
        """Regex match (явный формат {\"regex\": \"...\"})."""
        step = ExpectStep(name="test", checks={"imei": {"regex": r"^\d{15}$"}})
        parsed_data = {"imei": "123456789012345"}
        assert step._matches(parsed_data) is True

    def test_regex_mismatch(self) -> None:
        """Regex mismatch."""
        step = ExpectStep(name="test", checks={"imei": {"regex": r"^\d{15}$"}})
        parsed_data = {"imei": "ABC"}
        assert step._matches(parsed_data) is False

    def test_regex_non_string_value(self) -> None:
        """Regex на non-str — mismatch."""
        step = ExpectStep(name="test", checks={"count": {"regex": r"^\d+$"}})
        parsed_data = {"count": 42}
        assert step._matches(parsed_data) is False

    def test_string_without_regex_is_exact(self) -> None:
        """Строка без {\"regex\": } — exact match."""
        step = ExpectStep(name="test", checks={"type": "EGTS_SR_TERM_IDENTITY"})
        parsed_data = {"type": "EGTS_SR_TERM_IDENTITY"}
        assert step._matches(parsed_data) is True

    def test_string_exact_mismatch(self) -> None:
        """Exact string mismatch."""
        step = ExpectStep(name="test", checks={"type": "EGTS_SR_TERM_IDENTITY"})
        parsed_data = {"type": "EGTS_SR_OTHER"}
        assert step._matches(parsed_data) is False

    def test_nested_path_match(self) -> None:
        """Nested path через _get_nested."""
        step = ExpectStep(name="test")
        data = {"records": [{"fields": {"RN": 42}}]}
        assert step._get_nested(data, "records[0].fields.RN") == 42

    def test_nested_path_missing_key(self) -> None:
        """Nested path — ключ не найден."""
        step = ExpectStep(name="test")
        data = {"records": [{"fields": {"RN": 42}}]}
        assert step._get_nested(data, "records[1].fields.RN") is None

    def test_multiple_checks_all_pass(self) -> None:
        """Multiple checks — все должны пройти."""
        step = ExpectStep(
            name="test",
            checks={"service": 1, "subrecord_type": "AUTH", "data.TID": 12345},
        )
        parsed_data = {
            "service": 1,
            "subrecord_type": "AUTH",
            "data": {"TID": 12345},
        }
        assert step._matches(parsed_data) is True

    def test_multiple_checks_one_fails(self) -> None:
        """Multiple checks — один не проходит."""
        step = ExpectStep(name="test", checks={"service": 1, "subrecord_type": "AUTH"})
        parsed_data = {"service": 1, "subrecord_type": "OTHER"}
        assert step._matches(parsed_data) is False


class TestExpectStepCapture:
    """ExpectStep — capture переменных."""

    def test_capture_variables(self) -> None:
        """Capture извлекает переменные в контекст."""
        ctx = ScenarioContext()
        step = ExpectStep(
            name="test",
            capture={"tid": "data.TID", "imei": "data.IMEI"},
        )
        parsed_data = {"data": {"TID": 12345, "IMEI": "ABC123"}}
        step._capture(ctx, parsed_data)
        assert ctx.get("tid") == 12345
        assert ctx.get("imei") == "ABC123"

    def test_capture_nested(self) -> None:
        """Capture из nested path."""
        ctx = ScenarioContext()
        step = ExpectStep(
            name="test",
            capture={"rn": "records[0].fields.RN"},
        )
        parsed_data = {"records": [{"fields": {"RN": 42}}]}
        step._capture(ctx, parsed_data)
        assert ctx.get("rn") == 42

    def test_capture_missing_path(self) -> None:
        """Capture не найден — не падает."""
        ctx = ScenarioContext()
        step = ExpectStep(name="test", capture={"tid": "data.TID"})
        parsed_data = {"data": {}}
        step._capture(ctx, parsed_data)
        assert ctx.get("tid") is None


class TestExpectStepExecute:
    """ExpectStep.execute — асинхронное ожидание пакета."""

    @pytest.mark.asyncio
    async def test_expect_pass(self) -> None:
        """Expect пакет приходит вовремя — PASS."""
        ctx = ScenarioContext()
        step = ExpectStep(name="test", checks={"service": 1})

        # Создаём реальный EventBus
        bus = EventBus()

        # Симуляция: через 50мс эмитим packet.processed
        async def emit_packet_later() -> None:
            await asyncio.sleep(0.05)
            # Создаём мок для ParseResult
            from libs.egts.models import ParseResult, Packet, Record, Subrecord

            sub = Subrecord(subrecord_type=9, data={"rcd": 0})
            rec = Record(record_id=1, service_type=1, subrecords=[sub])
            pkt = Packet(packet_id=1, packet_type=1, records=[rec])
            parsed_mock = ParseResult(packet=pkt)

            ctx_mock = MagicMock()
            ctx_mock.parsed = parsed_mock
            await bus.emit(
                "packet.processed",
                {"ctx": ctx_mock, "connection_id": "conn-1", "channel": "tcp"},
            )

        task = asyncio.create_task(emit_packet_later())
        result = await step.execute(ctx, bus, timeout=2.0)
        await task

        assert result == "PASS"

    @pytest.mark.asyncio
    async def test_expect_timeout(self) -> None:
        """Expect пакет не приходит — TIMEOUT."""
        ctx = ScenarioContext()
        step = ExpectStep(name="test", checks={"service": 1})
        bus = EventBus()

        result = await step.execute(ctx, bus, timeout=0.1)
        assert result == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_expect_disconnect(self) -> None:
        """Disconnect во время ожидания — ERROR."""
        ctx = ScenarioContext()
        step = ExpectStep(name="test", checks={"service": 1})
        bus = EventBus()

        async def emit_disconnect_later() -> None:
            await asyncio.sleep(0.05)
            await bus.emit(
                "connection.changed",
                {"connection_id": "conn-1", "state": "disconnected"},
            )

        task = asyncio.create_task(emit_disconnect_later())
        result = await step.execute(ctx, bus, timeout=2.0)
        await task

        assert result == "ERROR"

    @pytest.mark.asyncio
    async def test_expect_with_capture(self) -> None:
        """Expect с capture — переменные извлекаются."""
        ctx = ScenarioContext()
        step = ExpectStep(
            name="test",
            checks={"service": 1},
            capture={"tid": "tid"},
        )
        bus = EventBus()

        async def emit_packet_later() -> None:
            await asyncio.sleep(0.05)
            from libs.egts.models import ParseResult, Packet, Record, Subrecord

            sub = Subrecord(subrecord_type=1, data={"tid": 99999})
            rec = Record(record_id=1, service_type=1, subrecords=[sub])
            pkt = Packet(packet_id=1, packet_type=1, records=[rec])
            parsed_mock = ParseResult(packet=pkt)

            ctx_mock = MagicMock()
            ctx_mock.parsed = parsed_mock
            await bus.emit(
                "packet.processed",
                {"ctx": ctx_mock, "connection_id": "conn-1", "channel": "tcp"},
            )

        task = asyncio.create_task(emit_packet_later())
        await step.execute(ctx, bus, timeout=2.0)
        await task

        assert ctx.get("tid") == 99999
