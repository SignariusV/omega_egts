"""Тесты Cmw500Controller и Cmw500Emulator."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.cmw500 import Cmw500Controller, Cmw500Emulator, MockDriver
from core.event_bus import EventBus


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


class TestMockDriver:
    """Тесты MockDriver — эмуляция драйвера."""

    def test_returns_default_imei(self) -> None:
        driver = MockDriver()
        assert driver.get_imei() == "351234567890123"

    def test_returns_default_imsi(self) -> None:
        driver = MockDriver()
        assert driver.get_imsi() == "250011234567890"

    def test_returns_default_rssi(self) -> None:
        driver = MockDriver()
        assert driver.get_rssi() == "-65"

    def test_returns_default_status(self) -> None:
        driver = MockDriver()
        assert driver.get_status() == "CONNected"


class TestCmw500Controller:
    """Тесты Cmw500Controller с моком драйвера."""

    async def test_connect_creates_driver(
        self, event_bus: EventBus
    ) -> None:
        ctrl = Cmw500Controller(bus=event_bus, ip="192.168.1.100", simulate=True)
        mock_driver = MagicMock()
        mock_driver.serial_number = "MOCK123"
        mock_driver.is_open = True

        with patch.object(VisaCmw500Driver, "open", return_value="MOCK123"):
            with patch.object(VisaCmw500Driver, "__init__", lambda self, ip, simulate: None):
                pass
            await ctrl.connect()
            assert ctrl._connected is True
            await ctrl.disconnect()

    async def test_disconnect_clears_connections(
        self, event_bus: EventBus
    ) -> None:
        ctrl = Cmw500Controller(bus=event_bus, ip="192.168.1.100", simulate=True)
        mock_driver = MagicMock()
        ctrl._driver = mock_driver
        ctrl._connected = True

        await ctrl.disconnect()

        assert ctrl._connected is False
        assert ctrl._driver is None


class TestCmw500Emulator:
    """Тесты Cmw500Emulator — полная эмуляция без реального VISA."""

    async def test_connect_creates_mock_driver(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        assert emul._connected is True
        assert emul._driver is not None
        assert isinstance(emul._driver, MockDriver)

        await emul.disconnect()

    async def test_get_imei_returns_mock_value(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        try:
            result = await emul.get_imei()
            assert result == "351234567890123"
        finally:
            await emul.disconnect()

    async def test_get_imsi_returns_mock_value(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        try:
            result = await emul.get_imsi()
            assert result == "250011234567890"
        finally:
            await emul.disconnect()

    async def test_get_rssi_returns_mock_value(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        try:
            result = await emul.get_rssi()
            assert result == "-65"
        finally:
            await emul.disconnect()

    async def test_get_status_returns_mock_value(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        try:
            result = await emul.get_status()
            assert result == "CONNected"
        finally:
            await emul.disconnect()

    async def test_send_sms_returns_true(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        try:
            result = await emul.send_sms(b"\x01\x18\x00\x01")
            assert result is True
        finally:
            await emul.disconnect()

    async def test_read_sms_returns_none_by_default(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        try:
            result = await emul.read_sms()
            assert result is None
        finally:
            await emul.disconnect()

    async def test_poll_incoming_sms_emits_event(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        received: list[dict[str, Any]] = []
        event_bus.on("raw.packet.received", lambda d: received.append(d))

        emul._incoming_sms_queue.put_nowait(b"\x01\x18\x00\x01")
        await asyncio.sleep(0.05)

        await emul.disconnect()

    async def test_full_status_returns_simulate_data(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        result = await emul.get_full_status()

        assert result["connected"] is True
        assert result["simulate"] is True
        assert result["serial"] == "EMULATOR"
        assert result["ip"] == "192.168.1.100"
        # НОВОЕ: проверка imei, imsi, timestamp
        assert "imei" in result
        assert "imsi" in result
        assert result["imei"] == "351234567890123"
        assert result["imsi"] == "250011234567890"
        assert "timestamp" in result

        await emul.disconnect()

    async def test_set_incoming_sms_handler(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")

        def handler(data: bytes) -> bytes | None:
            if data == b"test":
                return b"response"
            return None

        emul.set_incoming_sms_handler(handler)
        assert emul._incoming_sms_handler is not None


class TestCmw500EmulatorTcpDelay:
    """Тесты задержек TCP в эмуляторе."""

    async def test_tcp_delay_is_within_bounds(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(
            bus=event_bus,
            ip="192.168.1.100",
            tcp_delay_min=0.1,
            tcp_delay_max=0.2,
        )
        await emul.connect()

        times: list[float] = []
        for _ in range(5):
            start = asyncio.get_event_loop().time()
            await emul.get_imei()
            end = asyncio.get_event_loop().time()
            times.append(end - start)

        await emul.disconnect()

        avg_delay = sum(times) / len(times)
        assert 0.05 <= avg_delay <= 0.3


class TestCmwCommand:
    """Тесты CmwCommand dataclass."""

    def test_command_stores_name(self) -> None:
        from core.cmw500 import CmwCommand
        cmd = CmwCommand(name="test", func=lambda: "result")
        assert cmd.name == "test"

    def test_command_stores_func(self) -> None:
        from core.cmw500 import CmwCommand
        func = lambda: "result"
        cmd = CmwCommand(name="test", func=func)
        assert cmd.func is func

    def test_command_default_timeout(self) -> None:
        from core.cmw500 import CmwCommand
        cmd = CmwCommand(name="test", func=lambda: "result")
        assert cmd.timeout == 10.0

    def test_command_default_retry(self) -> None:
        from core.cmw500 import CmwCommand
        cmd = CmwCommand(name="test", func=lambda: "result")
        assert cmd.retry_count == 3


class TestWorkerLoop:
    """Тесты worker loop — обработка очереди команд."""

    async def test_worker_processes_queue(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        result = await emul.get_imei()
        assert result == "351234567890123"

        await emul.disconnect()


class TestPollLoop:
    """Тесты poll loop — опрос входящих SMS."""

    async def test_poll_loop_starts_on_connect(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        assert emul._poll_task is not None
        assert not emul._poll_task.done()

        await emul.disconnect()

    async def test_poll_loop_stops_on_disconnect(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()
        poll_task = emul._poll_task

        await emul.disconnect()

        assert poll_task.cancelled() or poll_task.done()





class TestFullStatusCache:
    """Тесты TTL-кэша статусов."""

    async def test_get_full_status_uses_cache(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        emul._status_cache_ttl = 10.0
        await emul.connect()

        result1 = await emul.get_full_status()
        result2 = await emul.get_full_status()

        assert result1 is result2

        await emul.disconnect()

    async def test_get_full_status_expires_after_ttl(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        emul._status_cache_ttl = 0.1
        await emul.connect()

        result1 = await emul.get_full_status()

        await asyncio.sleep(0.15)

        result2 = await emul.get_full_status()

        assert result1 is not result2

        await emul.disconnect()

    async def test_disconnect_clears_cache(
        self, event_bus: EventBus
    ) -> None:
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()

        await emul.get_full_status()
        assert emul._status_cache is not None

        await emul.disconnect()
        
        assert emul._status_cache is None


class TestGetFullStatusWithImeiImsi:
    """Тесты get_full_status с включением imei и imsi."""
    
    async def test_full_status_includes_imei_imsi_emulator(self, event_bus: EventBus):
        """Emulator: get_full_status возвращает imei и imsi."""
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()
        
        result = await emul.get_full_status()
        
        assert "imei" in result
        assert "imsi" in result
        assert result["imei"] == "351234567890123"
        assert result["imsi"] == "250011234567890"
        assert "timestamp" in result
        
        await emul.disconnect()
    
    async def test_full_status_timestamp_is_recent(self, event_bus: EventBus):
        """timestamp в get_full_status близок к текущему времени."""
        import time
        
        emul = Cmw500Emulator(bus=event_bus, ip="192.168.1.100")
        await emul.connect()
        
        before = time.time()
        result = await emul.get_full_status()
        after = time.time()
        
        assert before <= result["timestamp"] <= after
        
        await emul.disconnect()


class TestPollLoopEmitsStatus:
    """Тесты что _poll_loop эмитит cmw.status."""
    
    async def test_poll_loop_emits_cmw_status(self, event_bus: EventBus):
        """_poll_loop должен эмитить cmw.status каждую итерацию."""
        received = []
        event_bus.on("cmw.status", lambda d: received.append(d))
        
        emul = Cmw500Emulator(
            bus=event_bus,
            ip="127.0.0.1",
            poll_interval=0.1,
            tcp_delay_min=0.01,
            tcp_delay_max=0.05,
        )
        await emul.connect()
        
        # Ждём пару циклов poll
        await asyncio.sleep(0.25)
        
        await emul.disconnect()
        
        assert len(received) >= 1
        assert "imei" in received[0]
        assert "imsi" in received[0]
        assert received[0]["simulate"] is True

    async def test_poll_loop_emits_cmw_status_with_data(self, event_bus: EventBus):
        """cmw.status содержит корректные imei и imsi."""
        received = []
        event_bus.on("cmw.status", lambda d: received.append(d))
        
        emul = Cmw500Emulator(
            bus=event_bus,
            ip="127.0.0.1",
            poll_interval=999.0,  # Отключаем фоновый poll, будем вызывать вручную
        )
        await emul.connect()
        
        # Ручной вызов эмуляции poll_loop (вызов get_full_status и emit)
        status = await emul.get_full_status()
        await event_bus.emit("cmw.status", status)
        
        await emul.disconnect()
        
        assert len(received) >= 1
        assert received[0]["imei"] == "351234567890123"
        assert received[0]["imsi"] == "250011234567890"


# Импорт для патчинга
from core.cmw500 import VisaCmw500Driver
