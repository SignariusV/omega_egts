# OMEGA_EGTS GUI
import json
from pathlib import Path
from typing import Any

from core.engine import CoreEngine
from core.config import Config
from core.event_bus import EventBus


class EngineWrapper:
    def __init__(self, config: Config, bus: EventBus):
        self.engine = CoreEngine(config=config, bus=bus)
        self.bus = bus

    async def start(self):
        await self.engine.start()

    async def stop(self):
        await self.engine.stop()

    async def get_status(self) -> dict[str, Any]:
        return await self.engine.get_status()

    async def cmw_status(self) -> dict[str, Any]:
        return await self.engine.cmw_status()

    async def run_scenario(self, scenario_path: str, connection_id: str | None = None) -> dict[str, Any]:
        return await self.engine.run_scenario(scenario_path, connection_id)

    async def replay(self, log_path: str, scenario_path: str | None = None) -> dict[str, Any]:
        return await self.engine.replay(log_path, scenario_path)

    async def export(self, data_type: str, fmt: str, output_path: str) -> dict[str, Any]:
        return await self.engine.export(data_type, fmt, output_path)

    async def load_scenario_info(self, path: str) -> dict[str, Any]:
        from core.scenario_parser import (
            ScenarioParserFactory,
            ScenarioParserRegistry,
            ScenarioParserV1,
        )

        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry=registry)

        data = json.loads(Path(path).read_text())
        parser = factory.detect_and_create(data)
        errors, warnings = parser.validate(data)
        if errors:
            raise ValueError(f"Invalid scenario: {errors}")

        metadata = parser.load(data)
        steps = parser.get_steps()
        return {
            "name": metadata.name,
            "steps": [{"name": s.name, "type": s.type} for s in steps]
        }