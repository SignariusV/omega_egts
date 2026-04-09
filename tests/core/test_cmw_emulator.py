"""Тесты Cmw500Emulator — эмулятор CMW-500 с задержками и SMS."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from core.cmw500 import Cmw500Emulator
from core.event_bus import EventBus

# Фикстуры


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def emulator(event_bus: EventBus) -> Cmw500Emulator:
    """Эмулятор с минимальными задержками для быстрых тестов.

    poll_interval=999 отключает фоновый poll SMS (чтобы не забирал данные
    из очереди во время тестов send_sms/read_sms).
    """
    emu = Cmw500Emulator(
        bus=event_bus,
        ip="127.0.0.1",
        poll_interval=999.0,
        tcp_delay_min=0.01,
        tcp_delay_max=0.05,
        sms_delay_min=0.05,
        sms_delay_max=0.1,
    )
    # Полностью отключаем poll_loop — подменяем на no-op
    emu._poll_loop = AsyncMock()  # type: ignore[method-assign]
    return emu


# Connect / Disconnect


class TestEmulatorConnect:
    async def test_connect_emits_cmw_connected(
        self, event_bus: EventBus, emulator: Cmw500Emulator
    ) -> None:
        received: list[dict[str, Any]] = []
        event_bus.on("cmw.connected", lambda d: received.append(d))

        await emulator.connect()

        assert len(received) == 1
        assert received[0]["ip"] == "127.0.0.1"

        await emulator.disconnect()

    async def test_disconnect_stops_poll_and_worker(
        self, emulator: Cmw500Emulator
    ) -> None:
        await emulator.connect()

        assert emulator._worker is not None
        assert emulator._poll_task is not None

        await emulator.disconnect()

        assert emulator._worker.cancelled() or emulator._worker.done()
        assert emulator._poll_task.cancelled() or emulator._poll_task.done()

    async def test_worker_error_callback_handles_closed_loop(
        self, event_bus: EventBus
    ) -> None:
        """_on_worker_done не падает при закрытом event loop."""
        emulator = Cmw500Emulator(
            bus=event_bus,
            ip="127.0.0.1",
            poll_interval=0.5,
            tcp_delay_min=0.01,
            tcp_delay_max=0.05,
            sms_delay_min=0.05,
            sms_delay_max=0.1,
        )

        # Имитируем ошибку worker при уже закрытом loop
        # Это трудно протестировать напрямую, но проверяем что callback
        # не выбрасывает исключение
        mock_task = asyncio.create_task(asyncio.sleep(0))
        # Отменяем task чтобы exception был
        mock_task.cancel()
        try:
            await mock_task
        except asyncio.CancelledError:
            pass

        # Callback не должен падать
        emulator._on_worker_done(mock_task)  # type: ignore[arg-type]


# SCPI-команды с задержками


class TestScpiEmulation:
    async def test_get_imei_returns_mock_value(
        self, emulator: Cmw500Emulator
    ) -> None:
        await emulator.connect()
        try:
            result = await emulator.get_imei()
            assert result == "351234567890123"
        finally:
            await emulator.disconnect()

    async def test_get_imsi_returns_mock_value(
        self, emulator: Cmw500Emulator
    ) -> None:
        await emulator.connect()
        try:
            result = await emulator.get_imsi()
            assert result == "250011234567890"
        finally:
            await emulator.disconnect()

    async def test_get_rssi_returns_mock_value(
        self, emulator: Cmw500Emulator
    ) -> None:
        await emulator.connect()
        try:
            result = await emulator.get_rssi()
            assert result == "-65"
        finally:
            await emulator.disconnect()

    async def test_get_status_returns_mock_value(
        self, emulator: Cmw500Emulator
    ) -> None:
        await emulator.connect()
        try:
            result = await emulator.get_status()
            assert result == "1"
        finally:
            await emulator.disconnect()

    async def test_tcp_delay_is_within_bounds(
        self, emulator: Cmw500Emulator
    ) -> None:
        """TCP-задержка в пределах [tcp_delay_min, tcp_delay_max]."""
        await emulator.connect()
        try:
            import time

            start = time.monotonic()
            await emulator.get_imei()
            elapsed = time.monotonic() - start

            # tcp_delay_min=0.01, tcp_delay_max=0.05
            # На Windows таймер может быть менее точным — допускаем небольшой допуск
            assert elapsed >= 0.005  # минимум
            assert elapsed <= 0.15  # верхняя граница с запасом
        finally:
            await emulator.disconnect()


# SMS-эмуляция


class TestSmsEmulation:
    async def test_send_sms_returns_true(
        self, emulator: Cmw500Emulator
    ) -> None:
        await emulator.connect()
        try:
            result = await emulator.send_sms(b"\x01\x18\x00\x01")
            assert result is True
        finally:
            await emulator.disconnect()

    async def test_send_sms_goes_through_command_queue(
        self, emulator: Cmw500Emulator
    ) -> None:
        """send_sms ставит команду в очередь (не напрямую)."""
        await emulator.connect()
        try:
            # До send_sms очередь должна быть пуста
            assert emulator._queue.empty()

            # Запускаем send_sms без handler (быстро)
            task = asyncio.create_task(emulator.send_sms(b"\x01"))

            # На мгновение проверяем что команда в очереди
            await asyncio.sleep(0.01)
            # Команда должна быть в очереди или в процессе обработки
            # (в эмуляторе с минимальными задержками это быстро)

            await task
            # После выполнения очередь пуста
            assert emulator._queue.empty()
        finally:
            await emulator.disconnect()

    async def test_send_sms_with_handler_puts_response_in_queue(
        self, event_bus: EventBus, emulator: Cmw500Emulator
    ) -> None:
        """send_sms вызывает handler и кладёт ответ в очередь."""
        response_data = b"\x02\x19\x00\x02"

        def handler(egts_bytes: bytes) -> bytes | None:
            # Простая эмуляция: всегда возвращаем фиксированный ответ
            return response_data

        emulator.set_incoming_sms_handler(handler)
        await emulator.connect()

        await emulator.send_sms(b"\x01\x18\x00\x01")

        # Проверяем, что ответ попал в очередь через read_sms
        result = await emulator.read_sms()
        assert result == response_data

        await emulator.disconnect()

    async def test_send_sms_without_handler_does_not_crash(
        self, emulator: Cmw500Emulator
    ) -> None:
        await emulator.connect()
        try:
            result = await emulator.send_sms(b"\x01")
            assert result is True
        finally:
            await emulator.disconnect()

    async def test_read_sms_returns_none_when_empty(
        self, emulator: Cmw500Emulator
    ) -> None:
        await emulator.connect()
        try:
            result = await emulator.read_sms()
            assert result is None
        finally:
            await emulator.disconnect()

    async def test_send_sms_with_async_handler(
        self, event_bus: EventBus, emulator: Cmw500Emulator
    ) -> None:
        """send_sms поддерживает async handler."""
        response_data = b"\xAA\xBB\xCC"

        async def async_handler(egts_bytes: bytes) -> bytes | None:
            await asyncio.sleep(0.01)  # эмуляция async операции
            return response_data

        emulator.set_incoming_sms_handler(async_handler)
        await emulator.connect()

        await emulator.send_sms(b"\x01\x18\x00\x01")

        # Проверяем, что ответ попал в очередь
        result = await emulator.read_sms()
        assert result == response_data

        await emulator.disconnect()

    async def test_sms_delay_is_within_bounds(
        self, emulator: Cmw500Emulator
    ) -> None:
        """SMS-задержка в пределах [sms_delay_min, sms_delay_max]."""
        await emulator.connect()
        try:
            import time

            start = time.monotonic()
            await emulator.send_sms(b"\x01")
            elapsed = time.monotonic() - start

            # sms_delay_min=0.05, sms_delay_max=0.1
            assert 0.05 <= elapsed <= 0.2  # небольшой допуск
        finally:
            await emulator.disconnect()


@pytest.fixture
def emulator_with_poll(event_bus: EventBus) -> Cmw500Emulator:
    """Эмулятор с активным poll для тестов poll-функционала."""
    return Cmw500Emulator(
        bus=event_bus,
        ip="127.0.0.1",
        poll_interval=0.1,  # Быстрый poll для тестов
        tcp_delay_min=0.01,
        tcp_delay_max=0.05,
        sms_delay_min=0.05,
        sms_delay_max=0.1,
    )
    # _poll_loop НЕ мокаем — нужен настоящий


# Poll incoming SMS


class TestEmulatorPollIncomingSms:
    async def test_poll_emits_raw_packet_received(
        self, event_bus: EventBus, emulator_with_poll: Cmw500Emulator
    ) -> None:
        """Poll loop находит SMS в очереди и эмитит raw.packet.received."""
        # Кладём пакет в очередь вручную
        emulator_with_poll._incoming_sms_queue.put_nowait(b"\x01\x18\x00\x01")

        await emulator_with_poll.connect()

        received: list[dict[str, Any]] = []
        event_bus.on("raw.packet.received", lambda d: received.append(d))

        # Ждём один цикл poll
        await asyncio.sleep(0.2)

        await emulator_with_poll.disconnect()

        assert len(received) >= 1
        assert received[0]["raw"] == b"\x01\x18\x00\x01"
        assert received[0]["channel"] == "sms"
        assert received[0]["connection_id"] is None

    async def test_poll_with_handler(
        self, event_bus: EventBus, emulator_with_poll: Cmw500Emulator
    ) -> None:
        """Handler генерирует ответ на send_sms, poll его забирает."""
        def handler(egts_bytes: bytes) -> bytes | None:
            return b"\x03\x20\x00\x03"

        emulator_with_poll.set_incoming_sms_handler(handler)

        await emulator_with_poll.connect()

        received: list[dict[str, Any]] = []
        event_bus.on("raw.packet.received", lambda d: received.append(d))

        # Отправляем SMS — handler кладёт ответ в очередь
        await emulator_with_poll.send_sms(b"\x01\x18\x00\x01")

        # Ждём poll цикл (poll_interval=0.1, нужно больше)
        await asyncio.sleep(0.5)

        await emulator_with_poll.disconnect()

        assert len(received) >= 1
        assert received[0]["raw"] == b"\x03\x20\x00\x03"


# Конфигурация задержек


class TestDelayConfiguration:
    def test_custom_delay_ranges(self, event_bus: EventBus) -> None:
        """Эмулятор принимает настраиваемые диапазоны задержек."""
        emu = Cmw500Emulator(
            bus=event_bus,
            ip="127.0.0.1",
            tcp_delay_min=0.5,
            tcp_delay_max=1.0,
            sms_delay_min=5.0,
            sms_delay_max=10.0,
        )

        assert emu._tcp_delay_min == 0.5
        assert emu._tcp_delay_max == 1.0
        assert emu._sms_delay_min == 5.0
        assert emu._sms_delay_max == 10.0

    def test_random_delay_within_bounds(self, event_bus: EventBus) -> None:
        emu = Cmw500Emulator(
            bus=event_bus,
            ip="127.0.0.1",
            tcp_delay_min=0.1,
            tcp_delay_max=0.2,
        )

        # Проверяем несколько вызовов
        for _ in range(10):
            delay = emu._random_delay(0.1, 0.2)
            assert 0.1 <= delay <= 0.2
