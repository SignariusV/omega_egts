# OMEGA_EGTS GUI
import json
import pytest
import tempfile
from pathlib import Path

from core.config import Config, CmwConfig, TimeoutsConfig, LogConfig
from core.event_bus import EventBus
from gui.bridge.engine_wrapper import EngineWrapper


@pytest.fixture
def config():
    return Config(
        tcp_port=8090,
        cmw500=CmwConfig(simulate=True),
        timeouts=TimeoutsConfig(),
        logging=LogConfig(),
    )


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_start_and_status(config, bus):
    wrapper = EngineWrapper(config, bus)
    await wrapper.start()
    status = await wrapper.get_status()
    assert status["running"] is True
    await wrapper.stop()
    status = await wrapper.get_status()
    assert status["running"] is False


@pytest.mark.asyncio
async def test_cmw_status(config, bus):
    wrapper = EngineWrapper(config, bus)
    await wrapper.start()
    status = await wrapper.cmw_status()
    assert "connected" in status
    await wrapper.stop()


@pytest.mark.asyncio
async def test_run_scenario_invalid_path(config, bus):
    wrapper = EngineWrapper(config, bus)
    await wrapper.start()
    result = await wrapper.run_scenario("nonexistent")
    assert "error" in result
    await wrapper.stop()


@pytest.mark.asyncio
async def test_load_scenario_info_valid(tmp_path, config, bus):
    scenario_dir = tmp_path / "test_scenario"
    scenario_dir.mkdir()
    scenario_file = scenario_dir / "scenario.json"
    scenario_file.write_text(json.dumps({
        "version": "1",
        "name": "Test Scenario",
        "steps": [
            {"name": "step1", "type": "check"}
        ]
    }))

    wrapper = EngineWrapper(config, bus)
    info = await wrapper.load_scenario_info(str(scenario_file))
    assert info["name"] == "Test Scenario"
    assert len(info["steps"]) == 1
    assert info["steps"][0]["name"] == "step1"


@pytest.mark.asyncio
async def test_load_scenario_info_invalid(config, bus):
    wrapper = EngineWrapper(config, bus)
    with pytest.raises(Exception):
        await wrapper.load_scenario_info("nonexistent.json")


@pytest.mark.asyncio
async def test_load_scenario_info_invalid_json(tmp_path, config, bus):
    scenario_file = tmp_path / "invalid.json"
    scenario_file.write_text("not valid json")

    wrapper = EngineWrapper(config, bus)
    with pytest.raises(Exception):
        await wrapper.load_scenario_info(str(scenario_file))