"""Тесты AutoResponseMiddleware — формирование RESPONSE для успешных пакетов."""

from __future__ import annotations

import asyncio

import pytest

from core.event_bus import EventBus
from core.pipeline import (
    AutoResponseMiddleware,
    DuplicateDetectionMiddleware,
    EventEmitMiddleware,
    PacketContext,
    PacketPipeline,
)
from core.session import SessionManager
from libs.egts_protocol_iface import create_protocol
from libs.egts_protocol_iface.models import ParseResult

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def protocol():
    return create_protocol("2015")


@pytest.fixture
def session_mgr(bus: EventBus, protocol):
    return SessionManager(bus=bus, gost_version="2015")


@pytest.fixture
def middleware(session_mgr: SessionManager):
    return AutoResponseMiddleware(session_mgr=session_mgr)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _make_context(
    raw: bytes | None = None,
    connection_id: str = "conn1",
    crc_valid: bool = True,
    parsed: ParseResult | None = None,
    is_duplicate: bool = False,
    response_data: bytes | None = None,
) -> PacketContext:
    """Создать PacketContext с заданными параметрами."""
    ctx = PacketContext(raw=raw or b"\x00" * 12, connection_id=connection_id)
    ctx.crc_valid = crc_valid
    ctx.parsed = parsed
    ctx.is_duplicate = is_duplicate
    ctx.response_data = response_data
    return ctx


def _make_parse_result_with_pid(pid: int = 1):
    """Создать ParseResult с пакетом содержащим PID."""
    # Строим минимальный валидный пакет через протокол
    # Но для тестов проще сделать mock ParseResult
    from libs.egts_protocol_iface.models import Packet

    packet = Packet(
        packet_id=pid,
        packet_type=1,  # APPDATA
        priority=0,
        records=[],
    )
    return ParseResult(packet=packet, errors=[], warnings=[], raw_bytes=b"", extra={})


# ---------------------------------------------------------------------------
# Тесты: успешное формирование RESPONSE
# ---------------------------------------------------------------------------


class TestAutoResponseSuccess:
    """Тесты успешного формирования RESPONSE."""

    async def test_response_data_filled_for_valid_packet(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager, protocol
    ) -> None:
        """Для валидного пакета формируется RESPONSE."""
        session_mgr.create_session(connection_id="conn1", protocol=protocol)
        ctx = _make_context(parsed=_make_parse_result_with_pid(pid=42))

        await middleware(ctx)

        assert ctx.response_data is not None
        assert len(ctx.response_data) > 0

    async def test_add_pid_response_called(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager, protocol
    ) -> None:
        """RESPONSE кешируется через add_pid_response."""
        conn = session_mgr.create_session(connection_id="conn1", protocol=protocol)
        ctx = _make_context(parsed=_make_parse_result_with_pid(pid=99))

        await middleware(ctx)

        cached = conn.get_response(99)
        assert cached is not None
        assert cached == ctx.response_data

    async def test_response_not_overwritten(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager, protocol
    ) -> None:
        """Если response_data уже заполнен — не перезаписывает."""
        session_mgr.create_session(connection_id="conn1", protocol=protocol)
        existing_response = b"\x01\x02\x03"
        ctx = _make_context(
            parsed=_make_parse_result_with_pid(pid=10),
            response_data=existing_response,
        )

        await middleware(ctx)

        assert ctx.response_data is existing_response

    async def test_response_for_packet_without_records(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager, protocol
    ) -> None:
        """RESPONSE формируется даже для пакета без записей."""
        session_mgr.create_session(connection_id="conn1", protocol=protocol)
        # ParseResult с пустым records
        from libs.egts_protocol_iface.models import Packet

        packet = Packet(packet_id=5, packet_type=1, priority=0, records=[])
        parsed = ParseResult(packet=packet, errors=[], warnings=[], raw_bytes=b"", extra={})
        ctx = _make_context(parsed=parsed)

        await middleware(ctx)

        assert ctx.response_data is not None


# ---------------------------------------------------------------------------
# Тесты: пропуск (skip conditions)
# ---------------------------------------------------------------------------


class TestAutoResponseSkip:
    """Тесты пропуска формирования RESPONSE."""

    async def test_skip_when_crc_invalid(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager, protocol
    ) -> None:
        """crc_valid=False — пропускает."""
        session_mgr.create_session(connection_id="conn1", protocol=protocol)
        ctx = _make_context(crc_valid=False, parsed=_make_parse_result_with_pid(pid=1))

        await middleware(ctx)

        assert ctx.response_data is None

    async def test_skip_when_parsed_none(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager, protocol
    ) -> None:
        """parsed=None — пропускает."""
        session_mgr.create_session(connection_id="conn1", protocol=protocol)
        ctx = _make_context(parsed=None)

        await middleware(ctx)

        assert ctx.response_data is None

    async def test_skip_when_parsed_packet_none(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager, protocol
    ) -> None:
        """parsed.packet=None — пропускает."""
        session_mgr.create_session(connection_id="conn1", protocol=protocol)
        parsed = ParseResult(packet=None, errors=[], warnings=[], raw_bytes=b"", extra={})
        ctx = _make_context(parsed=parsed)

        await middleware(ctx)

        assert ctx.response_data is None

    async def test_skip_when_is_duplicate(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager, protocol
    ) -> None:
        """is_duplicate=True — пропускает."""
        session_mgr.create_session(connection_id="conn1", protocol=protocol)
        ctx = _make_context(
            parsed=_make_parse_result_with_pid(pid=1),
            is_duplicate=True,
        )

        await middleware(ctx)

        assert ctx.response_data is None

    async def test_skip_when_connection_not_found(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager
    ) -> None:
        """Connection не найден — пропускает."""
        ctx = _make_context(connection_id="nonexistent")

        await middleware(ctx)

        assert ctx.response_data is None

    async def test_skip_when_protocol_none(
        self, middleware: AutoResponseMiddleware, session_mgr: SessionManager
    ) -> None:
        """protocol=None в сессии — пропускает."""
        # Создаём UsvConnection напрямую с protocol=None (минуя авто-создание CR-008)
        from core.session import TransactionManager, UsvConnection, UsvStateMachine

        conn = UsvConnection(
            connection_id="conn1",
            remote_ip="",
            remote_port=0,
            reader=None,
            writer=None,
            fsm=UsvStateMachine(),
            protocol=None,  # намеренно None
            transaction_mgr=TransactionManager(),
        )
        session_mgr.connections["conn1"] = conn
        ctx = _make_context(parsed=_make_parse_result_with_pid(pid=1))

        await middleware(ctx)

        assert ctx.response_data is None


# ---------------------------------------------------------------------------
# Тесты: интеграция с полным pipeline
# ---------------------------------------------------------------------------


class TestAutoResponseIntegration:
    """Интеграционные тесты AutoResponseMiddleware с полным pipeline."""

    async def test_full_pipeline_forms_response(
        self, bus: EventBus, session_mgr: SessionManager, protocol
    ) -> None:
        """Полный pipeline: CRC → Parse → AutoResponse → Dedup → EventEmit.
        RESPONSE формируется для первого пакета.
        """
        conn = session_mgr.create_session(connection_id="conn1", protocol=protocol)

        pipe = PacketPipeline()
        # Заглушки CRC и Parse (тестируем именно AutoResponse)
        async def crc_ok(ctx: PacketContext) -> None:
            ctx.crc_valid = True

        async def parse_stub(ctx: PacketContext) -> None:
            from libs.egts_protocol_iface.models import Packet

            ctx.parsed = ParseResult(
                packet=Packet(packet_id=10, packet_type=1, priority=0, records=[]),
                errors=[],
                warnings=[],
                raw_bytes=ctx.raw,
                extra={},
            )

        pipe.add("crc_stub", crc_ok, order=1)
        pipe.add("parse_stub", parse_stub, order=2)
        pipe.add("auto_resp", AutoResponseMiddleware(session_mgr), order=3)
        pipe.add("dedup", DuplicateDetectionMiddleware(session_mgr), order=4)

        raw = b"\x00" * 12
        ctx = PacketContext(raw=raw, connection_id="conn1")
        await pipe.process(ctx)

        assert ctx.response_data is not None
        assert len(ctx.response_data) > 0
        # RESPONSE кеширован
        assert conn.get_response(10) is not None

    async def test_duplicate_gets_cached_response(
        self, bus: EventBus, session_mgr: SessionManager, protocol
    ) -> None:
        """Первый пакет формирует RESPONSE, дубликат получает из кэша."""
        session_mgr.create_session(connection_id="conn1", protocol=protocol)

        processed: list[PacketContext] = []

        async def capture(ctx_data: dict) -> None:
            processed.append(ctx_data["ctx"])

        bus.on("packet.processed", capture)

        pipe = PacketPipeline()

        async def crc_ok(ctx: PacketContext) -> None:
            ctx.crc_valid = True

        async def parse_stub(ctx: PacketContext) -> None:
            from libs.egts_protocol_iface.models import Packet

            ctx.parsed = ParseResult(
                packet=Packet(packet_id=20, packet_type=1, priority=0, records=[]),
                errors=[],
                warnings=[],
                raw_bytes=ctx.raw,
                extra={},
            )

        pipe.add("crc_stub", crc_ok, order=1)
        pipe.add("parse_stub", parse_stub, order=2)
        pipe.add("auto_resp", AutoResponseMiddleware(session_mgr), order=3)
        pipe.add("dedup", DuplicateDetectionMiddleware(session_mgr), order=4)
        pipe.add("emit", EventEmitMiddleware(bus), order=5)

        raw = b"\x00" * 12

        # Первый пакет
        ctx1 = PacketContext(raw=raw, connection_id="conn1")
        await pipe.process(ctx1)
        assert ctx1.response_data is not None

        # Дубликат
        ctx2 = PacketContext(raw=raw, connection_id="conn1")
        await pipe.process(ctx2)
        assert ctx2.is_duplicate is True
        assert ctx2.response_data is not None
        # RESPONSE тот же (из кэша)
        assert ctx2.response_data == ctx1.response_data

        await asyncio.sleep(0.05)
        # Оба события эмитились
        assert len(processed) == 2
