"""Tests for ExpectStep — ожидание пакета с проверкой и capture переменных."""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from core.event_bus import EventBus
from core.scenario import CheckResult, ExpectStep, ScenarioContext


class TestExpectStepCheck:
    """ExpectStep._check — детальная проверка пакетов."""

    def test_exact_value_match(self) -> None:
        """Exact value match — все passed=True."""
        step = ExpectStep(
            name="test",
            checks={"service": 1, "subrecord_type": 9},
        )
        parsed_data = {"service": 1, "subrecord_type": 9}
        results = step._check(parsed_data)
        assert len(results) == 2
        assert all(r.passed for r in results)
        assert results[0].check_type == "exact"

    def test_exact_value_mismatch(self) -> None:
        """Exact value mismatch — один failed."""
        step = ExpectStep(name="test", checks={"service": 2})
        parsed_data = {"service": 1}
        results = step._check(parsed_data)
        assert len(results) == 1
        assert not results[0].passed
        assert results[0].actual == 1
        assert results[0].expected == 2
        assert results[0].check_type == "exact"

    def test_range_match(self) -> None:
        """Range match (dict с min/max)."""
        step = ExpectStep(name="test", checks={"points_count": {"min": 1, "max": 100}})
        parsed_data = {"points_count": 50}
        results = step._check(parsed_data)
        assert results[0].passed
        assert results[0].check_type == "range"

    def test_range_below_min(self) -> None:
        """Range ниже min."""
        step = ExpectStep(name="test", checks={"points_count": {"min": 10, "max": 100}})
        parsed_data = {"points_count": 5}
        results = step._check(parsed_data)
        assert not results[0].passed
        assert results[0].check_type == "range"

    def test_range_above_max(self) -> None:
        """Range выше max."""
        step = ExpectStep(name="test", checks={"points_count": {"min": 1, "max": 10}})
        parsed_data = {"points_count": 50}
        results = step._check(parsed_data)
        assert not results[0].passed
        assert results[0].check_type == "range"

    def test_regex_match(self) -> None:
        """Regex match (явный формат {"regex": "..."})."""
        step = ExpectStep(name="test", checks={"imei": {"regex": r"^\d{15}$"}})
        parsed_data = {"imei": "123456789012345"}
        results = step._check(parsed_data)
        assert results[0].passed
        assert results[0].check_type == "regex"

    def test_regex_mismatch(self) -> None:
        """Regex mismatch."""
        step = ExpectStep(name="test", checks={"imei": {"regex": r"^\d{15}$"}})
        parsed_data = {"imei": "ABC"}
        results = step._check(parsed_data)
        assert not results[0].passed
        assert results[0].check_type == "regex"

    def test_missing_key(self) -> None:
        """Ключ отсутствует в пакете — check_type=missing."""
        step = ExpectStep(name="test", checks={"missing_field": 123})
        parsed_data = {"service": 1}
        results = step._check(parsed_data)
        assert not results[0].passed
        assert results[0].check_type == "missing"
        assert results[0].actual is None

    def test_multiple_checks_mixed(self) -> None:
        """Несколько checks разных типов — один падает."""
        step = ExpectStep(
            name="test",
            checks={"service": 1, "points": {"min": 0, "max": 100}, "extra": "data"},
        )
        parsed_data = {"service": 1, "points": 200, "extra": "data"}
        results = step._check(parsed_data)
        assert len(results) == 3
        assert results[0].passed  # service=1
        assert not results[1].passed  # points=200 > max=100
        assert results[1].check_type == "range"
        assert results[2].passed  # extra=data


class TestExpectStepCheckWithVarSubstitution:
    """ExpectStep._check — подстановка {{var}} в checks (KI-074)."""

    def test_var_in_check_exact_match(self) -> None:
        """{{sent_cid}} подставляется и совпадает."""
        ctx = ScenarioContext()
        ctx.set("sent_cid", 0)
        step = ExpectStep(name="test", checks={"cid": "{{sent_cid}}"})
        results = step._check({"cid": 0}, ctx)
        assert len(results) == 1
        assert results[0].passed
        assert results[0].actual == 0

    def test_var_in_check_exact_mismatch(self) -> None:
        """{{sent_cid}} подставляется, но не совпадает."""
        ctx = ScenarioContext()
        ctx.set("sent_cid", 0)
        step = ExpectStep(name="test", checks={"cid": "{{sent_cid}}"})
        results = step._check({"cid": 1}, ctx)
        assert not results[0].passed
        assert results[0].expected == 0
        assert results[0].actual == 1

    def test_var_in_check_unresolved_keeps_literal(self) -> None:
        """Если переменной нет в контексте — {{var}} остаётся литералом."""
        ctx = ScenarioContext()
        step = ExpectStep(name="test", checks={"cid": "{{sent_cid}}"})
        results = step._check({"cid": "{{sent_cid}}"}, ctx)
        # Литерал "{{sent_cid}}" совпадает с actual "{{sent_cid}}" → passed
        assert results[0].passed

    def test_var_in_multiple_checks(self) -> None:
        """Смешанные checks: часть с {{var}}, часть без."""
        ctx = ScenarioContext()
        ctx.set("sent_cid", 5)
        step = ExpectStep(
            name="test",
            checks={"cid": "{{sent_cid}}", "ct": 1, "sid": "{{sent_sid}}"},
        )
        ctx.set("sent_sid", 0)
        results = step._check({"cid": 5, "ct": 1, "sid": 0}, ctx)
        assert all(r.passed for r in results)

    def test_var_in_range_check(self) -> None:
        """{{var}} подставляется в range check."""
        ctx = ScenarioContext()
        ctx.set("min_val", 10)
        ctx.set("max_val", 100)
        step = ExpectStep(name="test", checks={"count": {"min": "{{min_val}}", "max": "{{max_val}}"}})
        results = step._check({"count": 50}, ctx)
        assert results[0].passed

    def test_var_substitution_without_ctx(self) -> None:
        """Без ctx {{var}} остаётся литералом (обратная совместимость)."""
        step = ExpectStep(name="test", checks={"cid": "{{sent_cid}}"})
        results = step._check({"cid": "{{sent_cid}}"})
        assert results[0].passed
        results = step._check({"cid": 0})
        assert not results[0].passed


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

        bus = EventBus()

        async def emit_packet_later() -> None:
            await asyncio.sleep(0.05)
            from libs.egts.models import Packet, ParseResult, Record, Subrecord

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
        result, details = await step.execute(ctx, bus, timeout=2.0)
        await task

        assert result == "PASS"
        assert "check_results" in details
        assert details["check_results"][0]["passed"] is True

    @pytest.mark.asyncio
    async def test_expect_timeout(self) -> None:
        """Expect пакет не приходит — TIMEOUT."""
        ctx = ScenarioContext()
        step = ExpectStep(name="test", checks={"service": 1})
        bus = EventBus()

        result, details = await step.execute(ctx, bus, timeout=0.1)
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
        result, details = await step.execute(ctx, bus, timeout=2.0)
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
            from libs.egts.models import Packet, ParseResult, Record, Subrecord

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

    @pytest.mark.asyncio
    async def test_expect_check_fail_immediate(self) -> None:
        """Пакет пришёл с неверными checks — FAIL мгновенно, без таймаута."""
        ctx = ScenarioContext()
        step = ExpectStep(name="test", checks={"service": 99})
        bus = EventBus()

        async def emit_bad_packet() -> None:
            await asyncio.sleep(0.01)
            from libs.egts.models import Packet, ParseResult, Record, Subrecord

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

        task = asyncio.create_task(emit_bad_packet())
        # Таймаут 10s, но FAIL должен вернуться мгновенно (~0.01s)
        result, details = await step.execute(ctx, bus, timeout=10.0)
        await task

        assert result == "FAIL"
        assert "check_results" in details
        assert details["check_results"][0]["passed"] is False
        assert details["check_results"][0]["key"] == "service"
        assert details["check_results"][0]["actual"] == 1
        assert details["check_results"][0]["expected"] == 99

    @pytest.mark.asyncio
    async def test_expect_check_fail_with_var(self) -> None:
        """FAIL с {{var}} подстановкой — details содержит ожидаемое значение после подстановки."""
        ctx = ScenarioContext()
        ctx.set("sent_cid", 0)
        step = ExpectStep(name="test", checks={"cid": "{{sent_cid}}"})
        bus = EventBus()

        async def emit_bad_packet() -> None:
            await asyncio.sleep(0.01)
            from libs.egts.models import Packet, ParseResult, Record, Subrecord

            sub = Subrecord(subrecord_type=9, data={"cid": 999})
            rec = Record(record_id=1, service_type=1, subrecords=[sub])
            pkt = Packet(packet_id=1, packet_type=1, records=[rec])
            parsed_mock = ParseResult(packet=pkt)

            ctx_mock = MagicMock()
            ctx_mock.parsed = parsed_mock
            await bus.emit(
                "packet.processed",
                {"ctx": ctx_mock, "connection_id": "conn-1", "channel": "tcp"},
            )

        task = asyncio.create_task(emit_bad_packet())
        result, details = await step.execute(ctx, bus, timeout=10.0)
        await task

        assert result == "FAIL"
        assert details["check_results"][0]["expected"] == 0  # после подстановки
        assert details["check_results"][0]["actual"] == 999

    @pytest.mark.asyncio
    async def test_ki075_extra_contains_rpid_pr_record_id_subrecord_type(self) -> None:
        """KI-075: extra содержит response_packet_id, processing_result, record_id, subrecord_type."""
        from libs.egts.models import Packet, ParseResult, Record, Subrecord

        # APPDATA-пакет (PT=1)
        sub = Subrecord(subrecord_type=9, data={"rcd": 0})
        rec = Record(record_id=42, service_type=1, subrecords=[sub])
        pkt = Packet(packet_id=1, packet_type=1, records=[rec])
        parsed_mock = MagicMock()
        parsed_mock.parsed = ParseResult(packet=pkt)

        ctx = ScenarioContext()
        step = ExpectStep(name="test", checks={"record_id": 42, "subrecord_type": 9})

        bus = EventBus()
        async def emit() -> None:
            await asyncio.sleep(0.01)
            await bus.emit("packet.processed", {"ctx": parsed_mock, "connection_id": "c1", "channel": "tcp"})

        task = asyncio.create_task(emit())
        result, details = await step.execute(ctx, bus, timeout=2.0)
        await task
        assert result == "PASS"

    @pytest.mark.asyncio
    async def test_ki075_response_packet_extra_fields(self) -> None:
        """RESPONSE-пакет: extra содержит response_packet_id и processing_result."""
        from libs.egts.models import Packet, ParseResult, Record, Subrecord

        sub = Subrecord(subrecord_type=0, data={"crn": 1, "rst": 0})
        rec = Record(record_id=1, service_type=1, subrecords=[sub])
        pkt = Packet(
            packet_id=5, packet_type=0, records=[rec],
            response_packet_id=5, processing_result=0,
        )
        parsed_mock = MagicMock()
        parsed_mock.parsed = ParseResult(packet=pkt)

        ctx = ScenarioContext()
        step = ExpectStep(
            name="test",
            checks={"response_packet_id": 5, "processing_result": 0, "subrecord_type": 0},
        )
        bus = EventBus()
        async def emit() -> None:
            await asyncio.sleep(0.01)
            await bus.emit("packet.processed", {"ctx": parsed_mock, "connection_id": "c1", "channel": "tcp"})

        task = asyncio.create_task(emit())
        result, details = await step.execute(ctx, bus, timeout=2.0)
        await task
        assert result == "PASS"
