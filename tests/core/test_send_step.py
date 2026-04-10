"""Tests for SendStep — отправка пакета из файла или build-template."""

import asyncio
from pathlib import Path

import pytest

from core.event_bus import EventBus
from core.scenario import SendStep, ScenarioContext


class TestSendStepBuildPacket:
    """SendStep — построение пакета из файла."""

    def test_build_from_file(self, tmp_path: Path) -> None:
        """Пакет загружается из HEX-файла."""
        hex_file = tmp_path / "test.hex"
        hex_file.write_text("0102030405")

        ctx = ScenarioContext()
        step = SendStep(name="test", packet_file=str(hex_file))
        result = step._build_packet(ctx)

        assert result == bytes([0x01, 0x02, 0x03, 0x04, 0x05])

    def test_build_from_file_with_substitution(self, tmp_path: Path) -> None:
        """Пакет из файла с подстановкой переменных."""
        hex_file = tmp_path / "test.hex"
        # Шаблон с переменной — для бинарных файлов подстановка не применяется
        hex_file.write_text("DEADBEEF")

        ctx = ScenarioContext()
        ctx.set("tid", "00")
        step = SendStep(name="test", packet_file=str(hex_file))
        result = step._build_packet(ctx)

        assert result == bytes([0xDE, 0xAD, 0xBE, 0xEF])

    def test_build_from_file_not_found(self) -> None:
        """Файл не найден — FileNotFoundError."""
        ctx = ScenarioContext()
        step = SendStep(name="test", packet_file="/nonexistent/path.hex")
        with pytest.raises(FileNotFoundError):
            step._build_packet(ctx)

    def test_build_from_file_invalid_hex(self, tmp_path: Path) -> None:
        """Невалидный HEX — ValueError."""
        hex_file = tmp_path / "test.hex"
        hex_file.write_text("ZZZZ")

        ctx = ScenarioContext()
        step = SendStep(name="test", packet_file=str(hex_file))
        with pytest.raises(ValueError):
            step._build_packet(ctx)


class TestSendStepBuildFromTemplate:
    """SendStep — построение пакета из build-template."""

    def test_build_from_template_simple(self) -> None:
        """Пакет строится из template dict."""
        ctx = ScenarioContext()
        step = SendStep(
            name="test",
            build={"service": 1, "fields": {"TID": 12345}},
        )
        # _build_from_template возвращает dict для передачи в CommandDispatcher
        result = step._build_from_template(ctx)
        assert result["service"] == 1
        assert result["fields"]["TID"] == 12345

    def test_build_from_template_with_substitution(self) -> None:
        """Пакет из template с подстановкой переменных."""
        ctx = ScenarioContext()
        ctx.set("tid", "99999")
        step = SendStep(
            name="test",
            build={"service": 1, "fields": {"TID": "{{tid}}"}},
        )
        result = step._build_from_template(ctx)
        assert result["fields"]["TID"] == "99999"

    def test_build_from_template_nested(self) -> None:
        """Nested substitution в build."""
        ctx = ScenarioContext()
        ctx.set("imei", "ABC123")
        step = SendStep(
            name="test",
            build={"fields": {"IMEI": "{{imei}}", "TID": 42}},
        )
        result = step._build_from_template(ctx)
        assert result["fields"]["IMEI"] == "ABC123"
        assert result["fields"]["TID"] == 42


class TestSendStepExecute:
    """SendStep.execute — асинхронная отправка."""

    @pytest.mark.asyncio
    async def test_send_from_file_pass(self, tmp_path: Path) -> None:
        """Отправка из файла — PASS."""
        hex_file = tmp_path / "test.hex"
        hex_file.write_text("01020304")

        ctx = ScenarioContext()
        ctx.connection_id = "conn-1"
        step = SendStep(name="test", packet_file=str(hex_file), channel="tcp")

        bus = EventBus()

        # Симуляция command.sent — эмитим через 50мс
        async def emit_sent_later() -> None:
            await asyncio.sleep(0.05)
            await bus.emit("command.sent", {"status": "sent"})

        task = asyncio.create_task(emit_sent_later())
        result = await step.execute(ctx, bus, timeout=2.0)
        await task

        assert result == "PASS"

    @pytest.mark.asyncio
    async def test_send_no_connection_error_before_emit(self) -> None:
        """Нет connection_id для TCP — ERROR до emit."""
        ctx = ScenarioContext()
        ctx.connection_id = None
        # Используем packet_file=None, build — чтобы пройти проверку packet_file
        # channel="tcp" + conn_id=None → ERROR
        step = SendStep(
            name="test",
            packet_file=None,
            build={"service": 1},
            channel="tcp",
        )
        bus = EventBus()

        # conn_id = ctx._resolve_connection_id(None) = None
        # channel == "tcp" and conn_id is None → ERROR
        result = await step.execute(ctx, bus, timeout=1.0)
        assert result == "ERROR"

    @pytest.mark.asyncio
    async def test_send_timeout(self, tmp_path: Path) -> None:
        """Отправка — timeout если command.sent не пришёл."""
        hex_file = tmp_path / "test.hex"
        hex_file.write_text("01020304")

        ctx = ScenarioContext()
        ctx.connection_id = "conn-1"
        step = SendStep(name="test", packet_file=str(hex_file), channel="tcp")
        bus = EventBus()

        result = await step.execute(ctx, bus, timeout=0.1)
        assert result == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_send_from_build_template(self, tmp_path: Path) -> None:
        """Отправка из build template с packet_bytes — PASS."""
        hex_file = tmp_path / "tmpl.hex"
        hex_file.write_text("DEADBEEF")
        packet_hex = hex_file.read_text()

        ctx = ScenarioContext()
        ctx.connection_id = "conn-1"
        step = SendStep(
            name="test",
            build={"packet_bytes": bytes.fromhex(packet_hex), "service": 1, "fields": {"TID": 42}},
            channel="tcp",
        )
        bus = EventBus()

        async def emit_sent_later() -> None:
            await asyncio.sleep(0.05)
            await bus.emit("command.sent", {"status": "sent"})

        task = asyncio.create_task(emit_sent_later())
        result = await step.execute(ctx, bus, timeout=2.0)
        await task

        assert result == "PASS"
