# OMEGA_EGTS GUI
import asyncio
import sys
import logging

import qasync
from PySide6.QtWidgets import QMainWindow, QStatusBar, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from gui.dashboard.container import DashboardContainer
from gui.dashboard.cards.system_status import SystemStatusCard
from gui.dashboard.cards.scenario_runner import ScenarioRunnerCard
from gui.dashboard.cards.live_packets import LivePacketsCard
from gui.dashboard.cards.system_logs import SystemLogsCard

from gui.bridge.engine_wrapper import EngineWrapper
from gui.bridge.event_bridge import EventBridge

from core.config import Config, CmwConfig, TimeoutsConfig, LogConfig
from core.event_bus import EventBus

logger = logging.getLogger(__name__)


def _global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = _global_exception_handler


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

        self._setup_shortcuts()

        self._shutdown_task = None

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for the main window."""
        # Ctrl+Q: Quit application
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.close)

        # Ctrl+R: Toggle server start/stop
        toggle_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        toggle_shortcut.activated.connect(self._on_toggle_server)

        # F5: Run selected scenario
        run_shortcut = QShortcut(QKeySequence("F5"), self)
        run_shortcut.activated.connect(self._on_run_scenario_shortcut)

        # Escape: Close any open overlay
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self._close_overlay_if_open)

        # Ctrl+1-4: Focus specific cards
        for i, card_name in enumerate(["_status_card", "_scenario_card", "_packets_card", "_logs_card"], 1):
            if hasattr(self, card_name):
                shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
                shortcut.activated.connect(lambda c=card_name: self._focus_card(c))

        # Set focus policy for keyboard navigation
        self.setFocusPolicy(Qt.StrongFocus)
        for card in [self._status_card, self._scenario_card, self._packets_card, self._logs_card]:
            card.setFocusPolicy(Qt.StrongFocus)

    def _on_toggle_server(self):
        """Toggle server start/stop via keyboard shortcut."""
        if self._status_card.is_server_running():
            asyncio.ensure_future(self._on_stop_requested())
        else:
            asyncio.ensure_future(self._on_start_requested())

    def _on_run_scenario_shortcut(self):
        """Run scenario via F5 shortcut."""
        self._scenario_card.on_run_clicked()

    def _close_overlay_if_open(self):
        """Close any open overlay dialog."""
        # Placeholder for overlay support
        pass

    def _focus_card(self, card_attr: str):
        """Focus a specific card by attribute name."""
        if hasattr(self, card_attr):
            card = getattr(self, card_attr)
            card.setFocus()
            card.show()

    def _create_cards(self):
        self._status_card = SystemStatusCard()
        self._scenario_card = ScenarioRunnerCard()
        self._packets_card = LivePacketsCard()
        self._logs_card = SystemLogsCard()

        # Cards in 8x8 grid, expanded size 4x4
        self._dashboard.add_card(self._status_card, row=0, col=0)  # Top-left
        self._dashboard.add_card(self._scenario_card, row=0, col=4)  # Top-right
        self._dashboard.add_card(self._packets_card, row=4, col=0)  # Bottom-left
        self._dashboard.add_card(self._logs_card, row=4, col=4)  # Bottom-right

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
        eb.command_error.connect(lambda data: self._status_bar.showMessage(f"Command Error: {data.get('error', data)}", 5000))

        self._status_card.start_requested.connect(self._on_start_requested)
        self._status_card.stop_requested.connect(self._on_stop_requested)
        self._scenario_card.run_requested.connect(self._on_run_scenario)

    @qasync.asyncSlot()
    async def _on_start_requested(self):
        try:
            await self._engine_wrapper.start()
            self._status_bar.showMessage("Server started", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start: {e}")

    @qasync.asyncSlot()
    async def _on_stop_requested(self):
        try:
            await self._engine_wrapper.stop()
            self._status_bar.showMessage("Server stopped", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop: {e}")

    @qasync.asyncSlot(str)
    async def _on_run_scenario(self, path):
        try:
            await self._engine_wrapper.run_scenario(path)
        except Exception as e:
            QMessageBox.critical(self, "Scenario Error", str(e))

    def closeEvent(self, event):
        """Handle window close - stop engine gracefully."""
        event.ignore()  # Don't close yet
        
        async def shutdown():
            try:
                await self._engine_wrapper.stop()
            except Exception:
                pass
            finally:
                self.close()  # Close after shutdown completes
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(shutdown())
            else:
                event.accept()
        except RuntimeError:
            event.accept()