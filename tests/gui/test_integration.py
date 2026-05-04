# OMEGA_EGTS GUI
import asyncio
import pytest

from core.config import Config, CmwConfig, TimeoutsConfig, LogConfig
from gui.main_window import MainWindow


@pytest.mark.asyncio
async def test_engine_start_stop(qtbot):
    """Проверить запуск и остановку движка."""
    config = Config(
        tcp_host="0.0.0.0",
        tcp_port=8091,
        cmw500=CmwConfig(ip="192.168.2.2", simulate=True),
        timeouts=TimeoutsConfig(),
        logging=LogConfig(),
    )

    window = MainWindow()
    window._config = config
    qtbot.addWidget(window)
    window.show()

    await window._engine_wrapper.start()
    status = await window._engine_wrapper.get_status()
    assert status.get("running") is True

    await window._engine_wrapper.stop()
    status = await window._engine_wrapper.get_status()
    assert status.get("running") is False


@pytest.mark.asyncio
async def test_cmw_status_updates_status_card(qtbot):
    """Проверить что cmw_status обновляет карточку."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    await window._engine_wrapper.start()

    window._event_bridge.cmw_status.emit({
        "rssi": "-65",
        "imsi": "12345",
        "imei": "123456789012345",
        "ber": "0.5",
        "cs_state": "GPRS",
        "ps_state": "CONNECTED"
    })

    await asyncio.sleep(0.2)

    await window._engine_wrapper.stop()


@pytest.mark.asyncio
async def test_scenario_step_updates_card(qtbot):
    """Проверить что сигнал scenario_step вызывает обновление."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    await window._engine_wrapper.start()

    window._event_bridge.scenario_step.emit({
        "step": "auth",
        "status": "passed",
        "duration": 1.5
    })

    await asyncio.sleep(0.2)

    await window._engine_wrapper.stop()