# OMEGA_EGTS GUI
import asyncio

from PySide6.QtWidgets import QMainWindow, QStatusBar, QMessageBox
from PySide6.QtCore import QTimer

from gui.dashboard.container import DashboardContainer
from gui.dashboard.cards.system_status import SystemStatusCard
from gui.dashboard.cards.scenario_runner import ScenarioRunnerCard
from gui.dashboard.cards.live_packets import LivePacketsCard
from gui.dashboard.cards.system_logs import SystemLogsCard

from gui.bridge.engine_wrapper import EngineWrapper
from gui.bridge.event_bridge import EventBridge

from core.config import Config, CmwConfig, TimeoutsConfig, LogConfig
from core.event_bus import EventBus


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OMEGA_EGTS Tester")
        self.resize(1024, 768)

        self._config = Config(
            tcp_host="0.0.0.0",
            tcp_port=8090,
            cmw500=CmwConfig(ip="192.168.2.2", simulate=True),
            timeouts=TimeoutsConfig(),
            logging=LogConfig(),
        )
        self._bus = EventBus()
        self._engine_wrapper = EngineWrapper(self._config, self._bus)
        self._event_bridge = EventBridge(self._bus)

        self._dashboard = DashboardContainer()
        self.setCentralWidget(self._dashboard)

        self._create_cards()
        self._connect_signals()

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._shutdown_task = None

    def _create_cards(self):
        self._status_card = SystemStatusCard()
        self._scenario_card = ScenarioRunnerCard()
        self._packets_card = LivePacketsCard()
        self._logs_card = SystemLogsCard()

        self._dashboard.add_card(self._status_card, 0, 0)
        self._dashboard.add_card(self._scenario_card, 0, 1)
        self._dashboard.add_card(self._packets_card, 1, 0)
        self._dashboard.add_card(self._logs_card, 1, 1)

    def _connect_signals(self):
        eb = self._event_bridge

        eb.cmw_status.connect(self._status_card.on_cmw_status)
        eb.server_started.connect(self._status_card.on_server_started)
        eb.server_stopped.connect(self._status_card.on_server_stopped)
        eb.cmw_connected.connect(self._status_card.on_cmw_connected)
        eb.cmw_disconnected.connect(self._status_card.on_cmw_disconnected)

        eb.packet_processed.connect(self._packets_card.on_packet_processed)
        eb.packet_sent.connect(self._packets_card.on_packet_sent)

        eb.scenario_step.connect(self._scenario_card.on_scenario_step)
        eb.command_error.connect(self._scenario_card.on_command_error)

        eb.cmw_error.connect(lambda msg: self._status_bar.showMessage(f"CMW Error: {msg}", 5000))
        eb.command_error.connect(lambda data: self._status_bar.showMessage(f"Command Error: {data}", 5000))

        self._status_card.start_requested.connect(self._on_start_requested)
        self._status_card.stop_requested.connect(self._on_stop_requested)
        self._scenario_card.run_requested.connect(self._on_run_scenario)

    async def _on_start_requested(self):
        try:
            await self._engine_wrapper.start()
            self._status_bar.showMessage("Server started", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start: {e}")

    async def _on_stop_requested(self):
        try:
            await self._engine_wrapper.stop()
            self._status_bar.showMessage("Server stopped", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop: {e}")

    async def _on_run_scenario(self, path):
        try:
            await self._engine_wrapper.run_scenario(path)
        except Exception as e:
            QMessageBox.critical(self, "Scenario Error", str(e))

    def closeEvent(self, event):
        async def shutdown():
            try:
                await self._engine_wrapper.stop()
            except Exception:
                pass

        asyncio.get_event_loop().run_until_complete(shutdown())
        event.accept()