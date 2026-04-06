"""Тесты для CoreEngine — координатор компонентов."""

import pytest

from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus


async def _noop_coroutine() -> None:
    """Заглушка для async-методов."""


class TestCoreEngineStartStop:
    """Тесты запуска и остановки CoreEngine."""

    @pytest.mark.asyncio
    async def test_start_emits_server_started(self) -> None:
        """start() публикует событие server.started с портом и версией ГОСТ."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        received_events: list = []
        bus.on("server.started", lambda data: received_events.append(data))

        await engine.start()

        assert len(received_events) == 1
        assert received_events[0]["port"] == 8090
        assert received_events[0]["gost_version"] == "2015"

    @pytest.mark.asyncio
    async def test_stop_emits_server_stopped(self) -> None:
        """stop() публикует событие server.stopped с причиной."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        received_events: list = []
        bus.on("server.stopped", lambda data: received_events.append(data))

        await engine.start()
        await engine.stop()

        assert len(received_events) == 1
        assert received_events[0]["reason"] == "shutdown"

    @pytest.mark.asyncio
    async def test_stop_without_start_does_not_crash(self) -> None:
        """stop() без вызова start() не падает."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        await engine.stop()  # Должно пройти без исключений


class TestCoreEngineIdempotency:
    """Тесты идемпотентности и повторного запуска."""

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        """Повторный start() не дублирует событие server.started."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        received_events: list = []
        bus.on("server.started", lambda data: received_events.append(data))

        await engine.start()
        await engine.start()  # Второй вызов — игнорируется

        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_restart_after_stop(self) -> None:
        """После stop() можно снова вызвать start()."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        start_events: list = []
        bus.on("server.started", lambda data: start_events.append(data))

        await engine.start()
        await engine.stop()
        await engine.start()

        assert len(start_events) == 2  # Два start — два события


class TestCoreEngineState:
    """Тесты проверки состояния."""

    @pytest.mark.asyncio
    async def test_is_running_after_start(self) -> None:
        """is_running == True после start()."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        assert not engine.is_running
        await engine.start()
        assert engine.is_running

    @pytest.mark.asyncio
    async def test_is_running_after_stop(self) -> None:
        """is_running == False после stop()."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        await engine.start()
        await engine.stop()
        assert not engine.is_running


class TestCoreEngineCleanup:
    """Тесты корректной очистки при ошибке."""

    @pytest.mark.asyncio
    async def test_cleanup_on_start_failure(self) -> None:
        """Если компонент не запустился — остальные очищаются."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        # Создаём фейковый компонент с async stop()
        class FakeTcpServer:
            async def stop(self) -> None:
                pass

        engine.tcp_server = FakeTcpServer()

        # Тестируем _cleanup напрямую
        await engine._cleanup()
        assert engine.tcp_server is None
        assert engine.cmw500 is None
        assert engine.session_mgr is None
        assert engine.log_mgr is None

    @pytest.mark.asyncio
    async def test_cleanup_is_idempotent(self) -> None:
        """Многократный вызов _cleanup не падает."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        await engine._cleanup()
        await engine._cleanup()  # Второй вызов — без ошибок
        assert not engine._started


class TestCoreEngineStr:
    """Тесты строкового представления."""

    @pytest.mark.asyncio
    async def test_str_when_stopped(self) -> None:
        """__str__ показывает stopped, когда система не запущена."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        result = str(engine)
        assert "stopped" in result
        assert "port=8090" in result
        assert "cmw=disconnected" in result
        assert "gost=2015" in result

    @pytest.mark.asyncio
    async def test_str_when_running(self) -> None:
        """__str__ показывает running, когда система запущена."""
        bus = EventBus()
        config = Config()
        engine = CoreEngine(config=config, bus=bus)

        await engine.start()
        result = str(engine)
        assert "running" in result
        assert "cmw=disconnected" in result  # CMW ещё не подключён (заглушка)
