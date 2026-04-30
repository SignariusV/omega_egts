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
        self.bus: EventBus | None = None

    async def start_engine(self):
        """Запуск CoreEngine (вызывается один раз при старте GUI)."""
        if self.bus is None:
            self.bus = EventBus()
        self.engine = CoreEngine(self.config, self.bus)
        await self.engine.start()

    async def stop_engine(self):
        """Остановка CoreEngine (при закрытии GUI)."""
        if self.engine:
            await self.engine.stop()

    def stop_server(self):
        """Остановка сервера (вызывается из UI)."""
        if not self.engine:
            return

        async def _stop():
            try:
                await self.engine.stop()
            except Exception as e:
                print(f"Ошибка остановки сервера: {e}")

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

        QTimer.singleShot(0, lambda: asyncio.run(_run()))
