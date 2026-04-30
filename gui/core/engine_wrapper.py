import asyncio
from PySide6.QtCore import QObject, QTimer
from core.engine import CoreEngine, Config
from core.event_bus import EventBus


class EngineWrapper(QObject):
    """Обёртка над CoreEngine для безопасного вызова из Qt."""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.engine: CoreEngine | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.bus: EventBus | None = None

    async def start_engine(self):
        """Запуск CoreEngine."""
        if self.bus is None:
            self.bus = EventBus()
        self.engine = CoreEngine(self.config, self.bus)
        await self.engine.start()

    async def stop_engine(self):
        """Остановка CoreEngine."""
        if self.engine:
            await self.engine.stop()

    def start_server(self):
        """Запуск сервера (вызывается из UI)."""
        print(f"[DEBUG] start_server called, engine={self.engine}")
        if not self.engine:
            print("[DEBUG] No engine, cannot start")
            return

        async def _start():
            try:
                print("[DEBUG] Starting engine...")
                await self.engine.start()
                print("[DEBUG] Engine started successfully")
            except Exception as e:
                import traceback
                print(f"Ошибка запуска сервера: {e}")
                traceback.print_exc()

        if self.loop:
            print(f"[DEBUG] Using existing loop: {self.loop}")
            asyncio.run_coroutine_threadsafe(_start(), self.loop)
        else:
            print("[DEBUG] No loop, using QTimer.singleShot")
            QTimer.singleShot(0, lambda: asyncio.run(_start()))

    def stop_server(self):
        """Остановка сервера."""
        if not self.engine:
            return

        async def _stop():
            try:
                await self.engine.stop()
            except Exception as e:
                print(f"Ошибка остановки сервера: {e}")

        if self.loop:
            asyncio.run_coroutine_threadsafe(_stop(), self.loop)
        else:
            QTimer.singleShot(0, lambda: asyncio.run(_stop()))

    def run_scenario(self, scenario_path: str):
        """Запуск сценария."""
        if not self.engine:
            return

        async def _run():
            try:
                await self.engine.run_scenario(scenario_path)
            except Exception as e:
                print(f"Ошибка запуска сценария: {e}")

        if self.loop:
            asyncio.run_coroutine_threadsafe(_run(), self.loop)
        else:
            QTimer.singleShot(0, lambda: asyncio.run(_run()))
