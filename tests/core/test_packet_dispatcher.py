"""Тесты PacketDispatcher — координатор pipeline для TCP и SMS каналов."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.dispatcher import PacketDispatcher
from core.event_bus import EventBus
from core.pipeline import EventEmitMiddleware, PacketPipeline
from core.session import SessionManager
from libs.egts_protocol_iface import create_protocol

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def bus() -> EventBus:
    """Создать EventBus для каждого теста."""
    return EventBus()


@pytest.fixture
def protocol():
    """Создать экземпляр EGTS-протокола ГОСТ 2015."""
    return create_protocol("2015")


@pytest.fixture
def session_mgr(bus: EventBus, protocol):
    """Создать SessionManager."""
    return SessionManager(bus=bus, gost_version="2015")


@pytest.fixture
def pipeline(bus: EventBus) -> PacketPipeline:
    """Создать PacketPipeline с EventEmitMiddleware для тестов."""
    p = PacketPipeline()
    p.add("event", EventEmitMiddleware(bus), order=100)
    return p


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _build_min_egts_packet(pid: int = 1) -> bytes:
    """Минимальный EGTS-пакет для тестов (12 байт: 8 заголовок + 4 тело/CRC)."""
    header = bytearray(8)
    header[0] = 0x01  # PR=0, HL=1 (минимальный)
    header[1] = pid & 0xFF
    header[2] = (pid >> 8) & 0xFF
    header[3] = 0x00  # PN
    header[4] = 0x00  # RP
    header[5] = 0x00  # padding
    header[6] = 0x00  # padding
    header[7] = 0x00  # CRC-8 placeholder

    body = b"\x00\x00"  # 2 байта тела
    crc16 = b"\x00\x00"  # 2 байта CRC-16 placeholder

    return bytes(header) + body + crc16


# ---------------------------------------------------------------------------
# Тесты: создание и базовая функциональность
# ---------------------------------------------------------------------------


class TestPacketDispatcherCreation:
    """Тесты создания PacketDispatcher."""

    def test_create_with_minimal_args(self, bus: EventBus, session_mgr, pipeline) -> None:
        """Создание с обязательными параметрами."""
        dispatcher = PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
        )
        assert dispatcher.bus is bus
        assert dispatcher.session_mgr is session_mgr
        assert dispatcher.pipeline is pipeline

    def test_create_with_protocol(self, bus: EventBus, session_mgr, pipeline, protocol) -> None:
        """Создание с явным protocol для SMS-канала."""
        dispatcher = PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )
        assert dispatcher.protocol is protocol


# ---------------------------------------------------------------------------
# Тесты: подписка на raw.packet.received
# ---------------------------------------------------------------------------


class TestPacketDispatcherSubscription:
    """Тесты подписки на события."""

    def test_subscribes_on_raw_packet_received(self, bus: EventBus, session_mgr, pipeline) -> None:
        """Dispatcher подписывается на raw.packet.received при создании."""
        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
        )
        assert "raw.packet.received" in bus._handlers
        assert len(bus._handlers["raw.packet.received"]) >= 1

    def test_subscribes_on_packet_processed(self, bus: EventBus, session_mgr, pipeline) -> None:
        """Dispatcher подписывается на packet.processed для обработки RESPONSE."""
        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
        )
        assert "packet.processed" in bus._handlers
        assert len(bus._handlers["packet.processed"]) >= 1


# ---------------------------------------------------------------------------
# Тесты: обработка TCP-пакетов
# ---------------------------------------------------------------------------


class TestPacketDispatcherTcp:
    """Тесты обработки TCP-пакетов."""

    async def test_tcp_packet_calls_pipeline(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """TCP-пакет передаётся в pipeline с правильными параметрами."""
        pipeline_calls: list[dict] = []

        async def mock_process(ctx):
            pipeline_calls.append({
                "channel": ctx.channel,
                "connection_id": ctx.connection_id,
                "raw_len": len(ctx.raw),
            })
            return ctx

        pipeline.process = mock_process  # type: ignore[assignment]

        conn_id = "tcp-conn-1"
        session_mgr.create_session(connection_id=conn_id, protocol=protocol)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=42)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.05)

        assert len(pipeline_calls) >= 1
        call = pipeline_calls[0]
        assert call["channel"] == "tcp"
        assert call["connection_id"] == conn_id
        assert call["raw_len"] == len(raw_packet)

    async def test_tcp_packet_emits_processed(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """TCP-пакет эмитит packet.processed через EventEmitMiddleware."""
        processed: list[dict] = []

        async def capture(data: dict) -> None:
            processed.append(data)

        bus.on("packet.processed", capture)

        conn_id = "tcp-conn-2"
        session_mgr.create_session(connection_id=conn_id, protocol=protocol)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=10)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        assert len(processed) >= 1
        event = processed[0]
        assert event["channel"] == "tcp"
        assert event["connection_id"] == conn_id


# ---------------------------------------------------------------------------
# Тесты: обработка SMS-пакетов
# ---------------------------------------------------------------------------


class TestPacketDispatcherSms:
    """Тесты обработки SMS-пакетов."""

    async def test_sms_packet_with_none_connection_id_creates_session(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """SMS-пакет с connection_id=None создаёт сессию и обрабатывается."""
        pipeline_calls: list[dict] = []

        async def mock_process(ctx):
            pipeline_calls.append({
                "channel": ctx.channel,
                "connection_id": ctx.connection_id,
            })
            return ctx

        pipeline.process = mock_process  # type: ignore[assignment]

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=99)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "sms", "connection_id": None},
        )
        await asyncio.sleep(0.05)

        # Создана SMS-сессия с внутренним ID
        assert len(pipeline_calls) >= 1
        call = pipeline_calls[0]
        assert call["channel"] == "sms"
        # connection_id — строка (внутренний ID SMS-сессии)
        assert isinstance(call["connection_id"], str)
        # Сессия создана
        assert "packet_dispatcher_sms" in session_mgr.connections

    async def test_sms_packet_emits_processed(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """SMS-пакет эмитит packet.processed с channel='sms'."""
        processed: list[dict] = []

        async def capture(data: dict) -> None:
            processed.append(data)

        bus.on("packet.processed", capture)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=77)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "sms", "connection_id": None},
        )
        await asyncio.sleep(0.1)

        assert len(processed) >= 1
        event = processed[0]
        assert event["channel"] == "sms"


# ---------------------------------------------------------------------------
# Тесты: RESPONSE отправка
# ---------------------------------------------------------------------------


class TestPacketDispatcherResponse:
    """Тесты отправки RESPONSE после обработки."""

    async def test_response_sent_via_connection_writer(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """RESPONSE отправляется через writer подключения."""
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        conn_id = "tcp-conn-resp"
        conn = session_mgr.create_session(connection_id=conn_id, protocol=protocol)
        conn.writer = mock_writer  # type: ignore[assignment]

        # Middleware, формирующий RESPONSE
        async def response_middleware(ctx):
            ctx.response_data = b"\x01\x02\x03"  # type: ignore[attr-defined]
            return ctx

        pipeline.add("response", response_middleware, order=10)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=50)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        mock_writer.write.assert_called_once_with(b"\x01\x02\x03")
        mock_writer.drain.assert_called_once()

    async def test_no_response_when_ctx_response_data_none(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """RESPONSE не отправляется если response_data=None."""
        mock_writer = AsyncMock()
        mock_writer.is_closing.return_value = False

        conn_id = "tcp-conn-no-resp"
        conn = session_mgr.create_session(connection_id=conn_id, protocol=protocol)
        conn.writer = mock_writer  # type: ignore[assignment]

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=51)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        mock_writer.write.assert_not_called()

    async def test_no_response_for_sms_channel(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """Для SMS-канала RESPONSE не отправляется обратно."""
        # Для SMS создаём сессию с внутренним ID
        from core.dispatcher import _SMS_DEFAULT_CONNECTION_ID

        processed: list[dict] = []

        async def capture(data: dict) -> None:
            processed.append(data)

        bus.on("packet.processed", capture)

        # Middleware, формирующий RESPONSE
        async def response_middleware(ctx):
            ctx.response_data = b"\x10\x20\x30"  # type: ignore[attr-defined]
            return ctx

        pipeline.add("response", response_middleware, order=10)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        # SMS-пакет — connection_id=None, dispatcher создаёт SMS-сессию
        raw_packet = _build_min_egts_packet(pid=60)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "sms", "connection_id": None},
        )
        await asyncio.sleep(0.1)

        # packet.processed эмитился
        assert len(processed) >= 1
        event = processed[0]
        ctx = event.get("ctx")
        assert ctx is not None
        # RESPONSE есть в контексте
        assert ctx.response_data == b"\x10\x20\x30"
        # Но для SMS-канала writer не вызывается (это логика dispatcher)
        # Проверяем, что SMS-сессия существует и у неё нет writer
        sms_conn = session_mgr.connections.get(_SMS_DEFAULT_CONNECTION_ID)
        assert sms_conn is not None
        assert sms_conn.writer is None


# ---------------------------------------------------------------------------
# Тесты: интеграция с EventBus
# ---------------------------------------------------------------------------


class TestPacketDispatcherEventBus:
    """Тесты интеграции PacketDispatcher с EventBus."""

    async def test_emits_packet_processed_with_all_fields(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """packet.processed содержит все требуемые поля."""
        processed_events: list[dict] = []

        async def capture(data: dict) -> None:
            processed_events.append(data)

        bus.on("packet.processed", capture)

        conn_id = "tcp-conn-evt"
        session_mgr.create_session(connection_id=conn_id, protocol=protocol)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=60)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        assert len(processed_events) >= 1
        event = processed_events[0]
        assert "ctx" in event
        assert "connection_id" in event
        assert "channel" in event
        assert event["connection_id"] == conn_id
        assert event["channel"] == "tcp"

    async def test_multiple_packets_processed_independently(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """Несколько пакетов обрабатываются независимо."""
        processed: list[dict] = []

        async def capture(data: dict) -> None:
            processed.append(data)

        bus.on("packet.processed", capture)

        conn_id = "tcp-conn-multi"
        session_mgr.create_session(connection_id=conn_id, protocol=protocol)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        for pid in range(3):
            raw_packet = _build_min_egts_packet(pid=pid)
            await bus.emit(
                "raw.packet.received",
                {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
            )

        await asyncio.sleep(0.2)

        assert len(processed) >= 3


# ---------------------------------------------------------------------------
# Тесты: обработка ошибок
# ---------------------------------------------------------------------------


class TestPacketDispatcherErrors:
    """Тесты обработки ошибок."""

    async def test_pipeline_error_does_not_crash_dispatcher(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """Ошибка в pipeline не роняет dispatcher."""

        async def failing_middleware(ctx):
            raise RuntimeError("Pipeline failed")

        pipeline.add("failing", failing_middleware, order=10)

        conn_id = "tcp-conn-err"
        session_mgr.create_session(connection_id=conn_id, protocol=protocol)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=100)
        # Не должно выбросить
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        # Dispatcher должен продолжить работу
        processed: list[dict] = []
        async def capture(data: dict) -> None:
            processed.append(data)

        bus.on("packet.processed", capture)

        raw_packet2 = _build_min_egts_packet(pid=101)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet2, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        # EventEmitMiddleware всё равно эмитит событие
        assert len(processed) >= 1

    async def test_missing_connection_id_handled_gracefully(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """Отсутствие connection_id создаёт SMS-сессию."""
        processed: list[dict] = []

        async def capture(data: dict) -> None:
            processed.append(data)

        bus.on("packet.processed", capture)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=200)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp"},  # connection_id отсутствует
        )
        await asyncio.sleep(0.1)

        # Должно обработаться без ошибок (как SMS-сессия)
        assert len(processed) >= 1
        assert "packet_dispatcher_sms" in session_mgr.connections


# ---------------------------------------------------------------------------
# Тесты: stop() и пустой пакет
# ---------------------------------------------------------------------------


class TestPacketDispatcherStopAndEmpty:
    """Тесты stop() и обработки пустого пакета."""

    def test_stop_unsubscribes(self, bus: EventBus, session_mgr, pipeline) -> None:
        """stop() отписывает от обоих событий."""
        dispatcher = PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
        )
        assert "raw.packet.received" in bus._handlers
        assert "packet.processed" in bus._handlers

        dispatcher.stop()

        raw_handlers = bus._handlers.get("raw.packet.received", [])
        processed_handlers = bus._handlers.get("packet.processed", [])
        assert dispatcher._on_raw_packet not in raw_handlers
        assert dispatcher._on_packet_processed not in processed_handlers

    async def test_empty_packet_does_not_call_pipeline(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """Пустой пакет (b'') не передаётся в pipeline."""
        pipeline_calls: list[dict] = []

        async def mock_process(ctx):
            pipeline_calls.append({"raw_len": len(ctx.raw)})
            return ctx

        pipeline.process = mock_process  # type: ignore[assignment]

        conn_id = "tcp-conn-empty"
        session_mgr.create_session(connection_id=conn_id, protocol=protocol)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        # Пустой пакет
        await bus.emit(
            "raw.packet.received",
            {"raw": b"", "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.05)

        assert len(pipeline_calls) == 0


# ---------------------------------------------------------------------------
# Тесты: _send_response_tcp — ошибки
# ---------------------------------------------------------------------------


class TestPacketDispatcherResponseErrors:
    """Тесты ошибок отправки RESPONSE."""

    async def test_response_session_not_found(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """Сессия не найдена — RESPONSE не отправляется, предупреждение в лог."""
        conn_id = "nonexistent-session"

        async def response_middleware(ctx):
            ctx.response_data = b"\x01\x02"  # type: ignore[attr-defined]
            return ctx

        pipeline.add("response", response_middleware, order=10)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=70)
        # Не должно выбросить
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

    async def test_response_writer_none(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """writer=None — RESPONSE не отправляется."""
        conn_id = "tcp-no-writer"
        conn = session_mgr.create_session(connection_id=conn_id, protocol=protocol)
        conn.writer = None  # type: ignore[assignment]

        async def response_middleware(ctx):
            ctx.response_data = b"\x03\x04"  # type: ignore[attr-defined]
            return ctx

        pipeline.add("response", response_middleware, order=10)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=71)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

    async def test_response_is_closing_coroutine(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """is_closing() возвращает coroutine — writer считается активным."""
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        # is_closing возвращает coroutine (как mock в некоторых случаях)
        async def fake_closing():
            return False

        mock_writer.is_closing = fake_closing

        conn_id = "tcp-closing-coroutine"
        conn = session_mgr.create_session(connection_id=conn_id, protocol=protocol)
        conn.writer = mock_writer  # type: ignore[assignment]

        async def response_middleware(ctx):
            ctx.response_data = b"\x05\x06"  # type: ignore[attr-defined]
            return ctx

        pipeline.add("response", response_middleware, order=10)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=72)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        mock_writer.write.assert_called_once_with(b"\x05\x06")

    async def test_response_is_closing_true(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """is_closing()=True — RESPONSE не отправляется."""
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = True
        mock_writer.write = MagicMock()

        conn_id = "tcp-closing-true"
        conn = session_mgr.create_session(connection_id=conn_id, protocol=protocol)
        conn.writer = mock_writer  # type: ignore[assignment]

        async def response_middleware(ctx):
            ctx.response_data = b"\x07\x08"  # type: ignore[attr-defined]
            return ctx

        pipeline.add("response", response_middleware, order=10)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=73)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        mock_writer.write.assert_not_called()

    async def test_response_write_error(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """Ошибка writer.write/drain — не роняет dispatcher."""
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.write = MagicMock(side_effect=ConnectionResetError("lost"))
        mock_writer.drain = AsyncMock()

        conn_id = "tcp-write-error"
        conn = session_mgr.create_session(connection_id=conn_id, protocol=protocol)
        conn.writer = mock_writer  # type: ignore[assignment]

        async def response_middleware(ctx):
            ctx.response_data = b"\x09\x0A"  # type: ignore[attr-defined]
            return ctx

        pipeline.add("response", response_middleware, order=10)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=74)
        # Не должно выбросить
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# Тесты: _ensure_sms_session protocol=None
# ---------------------------------------------------------------------------


class TestPacketDispatcherSmsSessionFallback:
    """Тесты fallback создания SMS-сессии без protocol."""

    async def test_sms_session_without_protocol(
        self, bus: EventBus, session_mgr, pipeline
    ) -> None:
        """protocol=None — dispatcher создаёт сессию через create_protocol('2015')."""
        pipeline_calls: list[dict] = []

        async def mock_process(ctx):
            pipeline_calls.append({"channel": ctx.channel})
            return ctx

        pipeline.process = mock_process  # type: ignore[assignment]

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=None,  # Без явного протокола
        )

        raw_packet = _build_min_egts_packet(pid=80)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "sms", "connection_id": None},
        )
        await asyncio.sleep(0.05)

        assert len(pipeline_calls) >= 1
        assert "packet_dispatcher_sms" in session_mgr.connections
        # Сессия создана и у неё есть protocol
        sms_conn = session_mgr.connections["packet_dispatcher_sms"]
        assert sms_conn.protocol is not None


# ---------------------------------------------------------------------------
# Тесты: ctx=None в _on_packet_processed
# ---------------------------------------------------------------------------


class TestPacketDispatcherCtxNone:
    """Тесты обработки ctx=None."""

    async def test_on_packet_processed_with_none_ctx(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """packet.processed с ctx=None — не роняет dispatcher."""
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False

        conn_id = "tcp-ctx-none"
        conn = session_mgr.create_session(connection_id=conn_id, protocol=protocol)
        conn.writer = mock_writer  # type: ignore[assignment]

        # Middleware, который НЕ устанавливает response_data
        # (response_data по умолчанию None)
        async def no_response_middleware(ctx):
            return ctx

        pipeline.add("no_resp", no_response_middleware, order=10)

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        raw_packet = _build_min_egts_packet(pid=90)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw_packet, "channel": "tcp", "connection_id": conn_id},
        )
        await asyncio.sleep(0.1)

        # writer.write не вызван — response_data=None
        mock_writer.write.assert_not_called()


# ---------------------------------------------------------------------------
# Тесты: _ensure_sms_session — повторное использование
# ---------------------------------------------------------------------------


class TestPacketDispatcherSmsSessionReuse:
    """Тесты повторного использования SMS-сессии."""

    async def test_sms_session_reused_on_second_packet(
        self, bus: EventBus, session_mgr, pipeline, protocol
    ) -> None:
        """Второй SMS-пакет использует существующую сессию (не создаёт новую)."""
        pipeline_calls: list[dict] = []

        async def mock_process(ctx):
            pipeline_calls.append({"channel": ctx.channel})
            return ctx

        pipeline.process = mock_process  # type: ignore[assignment]

        PacketDispatcher(
            bus=bus,
            session_mgr=session_mgr,
            pipeline=pipeline,
            protocol=protocol,
        )

        # Первый пакет — создаёт сессию
        raw1 = _build_min_egts_packet(pid=101)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw1, "channel": "sms", "connection_id": None},
        )
        await asyncio.sleep(0.05)

        assert "packet_dispatcher_sms" in session_mgr.connections
        first_session = session_mgr.connections["packet_dispatcher_sms"]

        # Второй пакет — должен использовать ту же сессию
        raw2 = _build_min_egts_packet(pid=102)
        await bus.emit(
            "raw.packet.received",
            {"raw": raw2, "channel": "sms", "connection_id": None},
        )
        await asyncio.sleep(0.05)

        assert len(pipeline_calls) >= 2
        # Сессия та же самая
        assert session_mgr.connections["packet_dispatcher_sms"] is first_session
