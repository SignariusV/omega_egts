import asyncio
from PySide6.QtCore import QObject
from core.engine import CoreEngine, Config
from core.event_bus import EventBus


class EngineWrapper(QObject):
    """Обёртка над CoreEngine для безопасного вызова из Qt."""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.engine: CoreEngine | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

    async def start_engine(self):
        """Запуск CoreEngine."""
        bus = EventBus()
        self.engine = CoreEngine(self.config, bus)
        await self.engine.start()

    async def stop_engine(self):
        """Остановка CoreEngine."""
        if self.engine:
            await self.engine.stop()

    def start_server(self):
        """Запуск сервера (вызывается из UI)."""
        if self.engine:
            asyncio.create_task(self.engine.start())

    def stop_server(self):
        """Остановка сервера."""
        if self.engine:
            asyncio.create_task(self.engine.stop())

    def run_scenario(self, scenario_path: str):
        """Запуск сценария."""
        if self.engine:
            asyncio.create_task(self.engine.run_scenario(scenario_path))
