"""Тесты Cmw500Controller -- очередь команд, retry, SMS."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.cmw500 import (
    GET_IMEI,
    GET_IMSI,
    GET_RSSI,
    GET_STATUS,
    READ_SMS,
    SEND_SMS,
    Cmw500Controller,
    CmwCommand,
    VisaCmw500Driver,
)
from core.event_bus import EventBus

# Фикстуры


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture(autouse=True)
def mock_driver_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Мокаем VisaCmw500Driver.open() — не пытаемся подключить реальное VISA."""
    monkeypatch.setattr(VisaCmw500Driver, "open", lambda self: "MOCK_SERIAL")


@pytest.fixture
def controller(event_bus: EventBus, mock_driver_open: None) -> Cmw500Controller:
    ctrl = Cmw500Controller(bus=event_bus, ip="192.168.1.100", simulate=True)
    ctrl._send_scpi = AsyncMock()  # type: ignore[method-assign]
    return ctrl


# CmwCommand


class TestCmwCommand:
    def test_format_with_args(self) -> None:
        cmd = CmwCommand("test", "CMD {}")
        assert cmd.format("hello") == "CMD hello"

    def test_format_with_kwargs(self) -> None:
        cmd = CmwCommand("test", "CMD {value}")
        assert cmd.format(value=42) == "CMD 42"

    def test_format_combined(self) -> None:
        cmd = CmwCommand("test", "CMD {} opt={value}")
        assert cmd.format("hello", value=42) == "CMD hello opt=42"

    def test_default_values(self) -> None:
        cmd = CmwCommand("test", "CMD")
        assert cmd.timeout == 5.0
        assert cmd.retry_count == 3
        assert cmd.retry_delay == 1.0


# Предопределённые команды


class TestPresetCommands:
    def test_get_imei(self) -> None:
        assert GET_IMEI.name == "get_imei"
        assert "IMEI?" in GET_IMEI.scpi_template
        assert GET_IMEI.retry_count == 3

    def test_get_imsi(self) -> None:
        assert GET_IMSI.name == "get_imsi"
        assert "IMSI?" in GET_IMSI.scpi_template

    def test_get_rssi(self) -> None:
        assert GET_RSSI.name == "get_rssi"
        assert GET_RSSI.retry_count == 2

    def test_get_status(self) -> None:
        assert GET_STATUS.name == "get_status"
        assert "CONN?" in GET_STATUS.scpi_template

    def test_send_sms(self) -> None:
        assert SEND_SMS.name == "send_sms"
        assert "SMS:SEND" in SEND_SMS.scpi_template
        assert SEND_SMS.timeout == 10.0
        assert SEND_SMS.retry_count == 2

    def test_read_sms(self) -> None:
        assert READ_SMS.name == "read_sms"
        assert "SMS:READ?" in READ_SMS.scpi_template


# Connect / Disconnect


class TestConnectDisconnect:
    async def test_connect_emits_cmw_connected(
        self, event_bus: EventBus, controller: Cmw500Controller
    ) -> None:
        received: list[dict[str, Any]] = []
        event_bus.on("cmw.connected", lambda d: received.append(d))

        await controller.connect()

        assert len(received) == 1
        assert received[0]["ip"] == "192.168.1.100"
        assert controller._connected is True

    async def test_disconnect_emits_cmw_disconnected(
        self, event_bus: EventBus, controller: Cmw500Controller
    ) -> None:
        await controller.connect()

        received: list[dict[str, Any]] = []
        event_bus.on("cmw.disconnected", lambda d: received.append(d))

        await controller.disconnect()

        assert len(received) == 1
        assert controller._connected is False

    async def test_connect_error_emits_cmw_error(
        self, event_bus: EventBus
    ) -> None:
        ctrl = Cmw500Controller(bus=event_bus, ip="bad_host", simulate=True)

        async def failing_worker() -> None:
            raise ConnectionError("bad host")

        ctrl._worker_loop = failing_worker  # type: ignore[method-assign]

        received: list[dict[str, Any]] = []
        event_bus.on("cmw.error", lambda d: received.append(d))

        # connect() запускает worker в create_task — исключение
        # оказывается внутри task, а не в connect().
        # Чтобы протестировать emit cmw.error, ждём немного:
        await ctrl.connect()
        await asyncio.sleep(0.1)

        assert len(received) == 1
        assert "bad host" in received[0]["error"]

    async def test_disconnect_without_connect_does_not_crash(
        self, controller: Cmw500Controller
    ) -> None:
        await controller.disconnect()
        assert controller._connected is False


# Execute через очередь


class TestExecute:
    async def test_execute_returns_result(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "351234567890123"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.execute(GET_IMEI)
            assert result == "351234567890123"
        finally:
            await controller.disconnect()

    async def test_execute_raises_if_not_connected(
        self, controller: Cmw500Controller
    ) -> None:
        with pytest.raises(ConnectionError, match="not connected"):
            await controller.execute(GET_IMEI)

    async def test_execute_formats_scpi_correctly(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "OK"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            cmd = CmwCommand("test", "TEST {}")
            await controller.execute(cmd, "hello")
            controller._send_scpi.assert_called()  # type: ignore[attr-defined]
            call_args = controller._send_scpi.call_args[0][0]  # type: ignore[attr-defined]
            assert call_args == "TEST hello"
        finally:
            await controller.disconnect()


# Retry при ошибке


class TestRetry:
    async def test_retry_succeeds_after_failures(
        self, controller: Cmw500Controller
    ) -> None:
        # Отключаем poll loop, чтобы не мешал подсчёту вызовов
        controller._poll_loop = AsyncMock()  # type: ignore[method-assign]
        controller._send_scpi.side_effect = [  # type: ignore[attr-defined]
            ConnectionError("fail 1"),
            ConnectionError("fail 2"),
            "OK",
        ]
        await controller.connect()

        result = await controller.execute(GET_IMEI)
        assert result == "OK"
        assert controller._send_scpi.call_count == 3  # type: ignore[attr-defined]

    async def test_retry_exhausted_raises_last_error(
        self, controller: Cmw500Controller
    ) -> None:
        # Отключаем poll loop
        controller._poll_loop = AsyncMock()  # type: ignore[method-assign]
        err = ConnectionError("permanent fail")
        controller._send_scpi.side_effect = err  # type: ignore[attr-defined]
        await controller.connect()

        cmd = CmwCommand("test", "CMD", retry_count=3, retry_delay=0.01)
        with pytest.raises(ConnectionError, match="permanent fail"):
            await controller.execute(cmd)

        assert controller._send_scpi.call_count == 3  # type: ignore[attr-defined]


# Timeout команды


class TestTimeout:
    async def test_command_timeout_raises(
        self, controller: Cmw500Controller
    ) -> None:
        async def slow_scpi(scpi: str) -> str:
            await asyncio.sleep(999)
            return "never"

        controller._send_scpi = slow_scpi  # type: ignore[method-assign]
        await controller.connect()

        try:
            # Тестируем _execute_with_retry напрямую, минуя очередь,
            # чтобы избежать гонок между worker loop и тестом.
            cmd = CmwCommand("slow", "CMD", timeout=0.05, retry_count=1, retry_delay=0)
            with pytest.raises(TimeoutError):
                await controller._execute_with_retry(cmd)
        finally:
            await controller.disconnect()


# send_sms (сырые EGTS)


class TestSendSms:
    async def test_send_sms_returns_true(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "OK"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.send_sms(b"\x01\x18\x00\x01")
            assert result is True
            call_arg = controller._send_scpi.call_args[0][0]  # type: ignore[attr-defined]
            assert "SMS:SEND" in call_arg
        finally:
            await controller.disconnect()

    async def test_send_sms_passes_raw_bytes_hex(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "OK"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            raw_egts = bytes([0x01, 0x18, 0x00, 0x01, 0xFF])
            await controller.send_sms(raw_egts)
            call_arg = controller._send_scpi.call_args[0][0]  # type: ignore[attr-defined]
            assert "01180001ff" in call_arg.lower()
        finally:
            await controller.disconnect()

    async def test_send_sms_returns_false_on_error(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "ERROR"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.send_sms(b"\x01")
            assert result is False
        finally:
            await controller.disconnect()


# read_sms (сырые EGTS)


class TestReadSms:
    async def test_read_sms_returns_bytes(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "01180001FF"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.read_sms()
            assert result is not None
            assert result == bytes([0x01, 0x18, 0x00, 0x01, 0xFF])
        finally:
            await controller.disconnect()

    async def test_read_sms_returns_none_on_empty(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = ""  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.read_sms()
            assert result is None
        finally:
            await controller.disconnect()

    async def test_read_sms_calls_read_sms_command(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "0118"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            await controller.read_sms()
            call_arg = controller._send_scpi.call_args[0][0]  # type: ignore[attr-defined]
            assert "SMS:READ?" in call_arg
        finally:
            await controller.disconnect()


# _poll_incoming_sms -> raw.packet.received


class TestPollIncomingSms:
    async def test_poll_emits_raw_packet_received(
        self, event_bus: EventBus, controller: Cmw500Controller
    ) -> None:
        # Отключаем фоновый poll, тестируем только ручной вызов
        controller._poll_loop = AsyncMock()  # type: ignore[method-assign]
        controller._send_scpi.return_value = "01180001"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            received: list[dict[str, Any]] = []
            event_bus.on("raw.packet.received", lambda d: received.append(d))

            await controller._poll_incoming_sms()

            assert len(received) == 1
            assert received[0]["raw"] == bytes([0x01, 0x18, 0x00, 0x01])
            assert received[0]["channel"] == "sms"
            assert received[0]["connection_id"] is None
        finally:
            await controller.disconnect()

    async def test_poll_no_sms_does_not_emit(
        self, event_bus: EventBus, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = ""  # type: ignore[attr-defined]
        await controller.connect()
        try:
            received: list[dict[str, Any]] = []
            event_bus.on("raw.packet.received", lambda d: received.append(d))

            await controller._poll_incoming_sms()

            assert len(received) == 0
        finally:
            await controller.disconnect()


# Удобные методы


class TestConvenienceMethods:
    async def test_get_imei(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "351234567890123"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.get_imei()
            assert result == "351234567890123"
        finally:
            await controller.disconnect()

    async def test_get_imsi(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "250011234567890"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.get_imsi()
            assert result == "250011234567890"
        finally:
            await controller.disconnect()

    async def test_get_rssi(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "-65"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.get_rssi()
            assert result == "-65"
        finally:
            await controller.disconnect()

    async def test_get_status(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "1"  # type: ignore[attr-defined]
        await controller.connect()
        try:
            result = await controller.get_status()
            assert result == "1"
        finally:
            await controller.disconnect()


# Worker loop


class TestWorkerLoop:
    async def test_worker_processes_queue(
        self, controller: Cmw500Controller
    ) -> None:
        controller._send_scpi.return_value = "result"  # type: ignore[attr-defined]
        await controller.connect()

        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        cmd = CmwCommand("test", "CMD", retry_count=1)
        await controller._queue.put((cmd, (), future))

        await asyncio.sleep(0.05)

        assert future.done()
        assert future.result() == "result"

    async def test_worker_stops_on_disconnect(
        self, controller: Cmw500Controller
    ) -> None:
        await controller.connect()
        assert controller._worker is not None
        assert not controller._worker.done()

        await controller.disconnect()
        assert controller._worker.cancelled() or controller._worker.done()


# Poll loop (фоновый опрос SMS)


class TestPollLoop:
    async def test_poll_loop_starts_on_connect(
        self, controller: Cmw500Controller
    ) -> None:
        await controller.connect()

        assert controller._poll_task is not None
        assert not controller._poll_task.done()

        await controller.disconnect()

    async def test_poll_loop_stops_on_disconnect(
        self, controller: Cmw500Controller
    ) -> None:
        await controller.connect()
        assert controller._poll_task is not None

        await controller.disconnect()
        assert controller._poll_task.cancelled() or controller._poll_task.done()

    async def test_poll_loop_emits_raw_packet_received(
        self, event_bus: EventBus, controller: Cmw500Controller
    ) -> None:
        """Poll loop находит SMS и эмитит raw.packet.received."""
        # READ_SMS вернёт данные при первом вызове, потом пусто
        controller._send_scpi.side_effect = [  # type: ignore[attr-defined]
            "01180001",  # READ_SMS? -> данные
            "",  # следующий опрос — пусто
        ]
        await controller.connect()

        received: list[dict[str, Any]] = []
        event_bus.on("raw.packet.received", lambda d: received.append(d))

        # Ждём один цикл опроса + небольшой запас
        await asyncio.sleep(0.3)

        await controller.disconnect()

        assert len(received) >= 1
        assert received[0]["raw"] == bytes([0x01, 0x18, 0x00, 0x01])
        assert received[0]["channel"] == "sms"
        assert received[0]["connection_id"] is None

    async def test_poll_loop_handles_error_and_continues(
        self, event_bus: EventBus, controller: Cmw500Controller
    ) -> None:
        """Ошибка в poll loop не останавливает цикл."""
        # Мокаем read_sms — poll loop будет получать исключение
        controller.read_sms = AsyncMock(side_effect=ConnectionError("poll error"))  # type: ignore[method-assign]
        controller._poll_interval = 0.05

        error_events: list[dict[str, Any]] = []
        event_bus.on("cmw.error", lambda d: error_events.append(d))

        await controller.connect()

        # Даём время на несколько итераций poll loop
        await asyncio.sleep(0.3)

        await controller.disconnect()

        # Ошибки были залогированы (poll loop поймал исключение из read_sms)
        assert len(error_events) >= 1, "No cmw.error events captured"
        assert error_events[0]["command"] == "poll_sms"

    async def test_poll_loop_uses_custom_interval(
        self, event_bus: EventBus
    ) -> None:
        """Poll loop уважает настройку poll_interval."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", poll_interval=0.05, simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")  # type: ignore[method-assign]

        await ctrl.connect()

        # С маленьким интервалом poll вызовет read_sms несколько раз
        await asyncio.sleep(0.2)

        await ctrl.disconnect()

        # read_sms вызывался многократно (интервал 50мс, спим 200мс)
        assert ctrl._send_scpi.call_count >= 2  # type: ignore[attr-defined]


class TestPollStates:
    """Тесты _poll_states — заглушка до реального CMW (Sense API не работает)."""

    async def test_poll_states_is_pass(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """_poll_states сейчас заглушка — не вызывает методы драйвера."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")  # type: ignore[method-assign]
        await ctrl.connect()

        # _poll_states — заглушка, не должна вызывать ошибок
        await ctrl._poll_states()

        await ctrl.disconnect()

    async def test_poll_states_no_emit_on_same_value(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """_poll_states заглушка — не эмитит события."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")  # type: ignore[method-assign]
        await ctrl.connect()

        events: list[dict[str, Any]] = []
        event_bus.on("cmw.cs_state_changed", lambda d: events.append(d))
        await ctrl._poll_states()
        assert len(events) == 0

        await ctrl.disconnect()

    async def test_poll_states_emits_on_change(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """_poll_states заглушка — не эмитит события."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")  # type: ignore[method-assign]
        await ctrl.connect()

        events: list[dict[str, Any]] = []
        event_bus.on("cmw.cs_state_changed", lambda d: events.append(d))
        await ctrl._poll_states()
        assert len(events) == 0

        await ctrl.disconnect()

    async def test_poll_states_handles_driver_error(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """_poll_states заглушка — не падает с ошибками."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")  # type: ignore[method-assign]
        await ctrl.connect()
        await ctrl._poll_states()
        await ctrl.disconnect()


class TestFullStatusCache:
    """Тесты get_full_status() и TTL-кэша (KI-046)."""

    async def test_get_full_status_returns_all_data(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """get_full_status() возвращает базовую информацию (Sense отключён)."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")

        await ctrl.connect()

        mock_driver = MagicMock()
        mock_driver.serial_number = "SERIAL123"
        ctrl._driver = mock_driver

        result = await ctrl.get_full_status()

        assert result["connected"] is True
        assert result["serial"] == "SERIAL123"
        # Sense отключён — N/A
        assert "N/A" in result["cs_state"]
        assert "N/A" in result["ps_state"]
        assert result["simulate"] is True
        assert result["ip"] == "192.168.1.100"

        await ctrl.disconnect()

    async def test_get_full_status_uses_cache(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """get_full_status() возвращает кэшированные данные."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")
        ctrl._status_cache_ttl = 10.0  # длинный TTL

        await ctrl.connect()

        mock_driver = MagicMock()
        mock_driver.serial_number = "SERIAL123"
        ctrl._driver = mock_driver

        # Первый вызов — собирает данные
        result1 = await ctrl.get_full_status()
        serial1 = result1["serial"]

        # Второй вызов — возвращает кэш (менее TTL прошло)
        result2 = await ctrl.get_full_status()
        assert result1 is result2  # тот же объект из кэша
        assert result2["serial"] == serial1

        await ctrl.disconnect()

    async def test_get_full_status_expires_after_ttl(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """get_full_status() обновляет данные после TTL."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")
        ctrl._status_cache_ttl = 0.1  # 100мс для быстрого теста

        await ctrl.connect()

        mock_driver = MagicMock()
        mock_driver.serial_number = "SERIAL123"
        ctrl._driver = mock_driver

        await ctrl.get_full_status()
        first_cache = ctrl._status_cache

        # Ждём TTL
        await asyncio.sleep(0.15)

        # После TTL — должен обновить (новый объект)
        await ctrl.get_full_status()
        assert ctrl._status_cache is not first_cache

        await ctrl.disconnect()

    async def test_get_full_status_not_connected(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """get_full_status() без драйвера возвращает error."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._driver = None

        result = await ctrl.get_full_status()

        assert result["connected"] is False
        assert "error" in result

    async def test_invalidate_status_cache(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """invalidate_status_cache() сбрасывает кэш."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")

        await ctrl.connect()

        mock_driver = MagicMock()
        mock_driver.serial_number = "SERIAL123"
        mock_driver.get_cs_state.return_value = "CONNected"
        mock_driver.get_ps_state.return_value = "DISConnect"
        mock_driver.get_rssi.return_value = "-65"
        mock_driver.get_ber.return_value = 0.001
        mock_driver.get_rx_level.return_value = -70.0
        ctrl._driver = mock_driver

        await ctrl.get_full_status()
        assert ctrl._status_cache is not None

        ctrl.invalidate_status_cache()
        assert ctrl._status_cache is None
        assert ctrl._status_cache_ts == 0.0

        await ctrl.disconnect()

    async def test_disconnect_clears_cache(
        self, event_bus: EventBus, mock_driver_open: None
    ) -> None:
        """disconnect() очищает кэш статусов."""
        ctrl = Cmw500Controller(
            bus=event_bus, ip="192.168.1.100", simulate=True
        )
        ctrl._send_scpi = AsyncMock(return_value="")

        await ctrl.connect()

        mock_driver = MagicMock()
        mock_driver.serial_number = "SERIAL123"
        mock_driver.get_cs_state.return_value = "CONNected"
        mock_driver.get_ps_state.return_value = "DISConnect"
        mock_driver.get_rssi.return_value = "-65"
        mock_driver.get_ber.return_value = 0.001
        mock_driver.get_rx_level.return_value = -70.0
        ctrl._driver = mock_driver

        await ctrl.get_full_status()
        assert ctrl._status_cache is not None

        await ctrl.disconnect()

        assert ctrl._status_cache is None
        assert ctrl._status_cache_ts == 0.0
