# OMEGA_EGTS GUI
import asyncio
import sys
import logging
from pathlib import Path

import qasync
from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar, QMessageBox, QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from gui.dashboard.container import DashboardContainer
from gui.dashboard.sidebar import CardSidebar
from gui.dashboard.cards.system_status import SystemStatusCard
from gui.dashboard.cards.scenario_runner import ScenarioRunnerCard
from gui.dashboard.cards.live_packets import LivePacketsCard
from gui.dashboard.cards.system_logs import SystemLogsCard
from gui.dashboard.persistence import PersistenceManager

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

        # Persistence manager for layout/state
        self._persistence = PersistenceManager(Path.cwd())

        self._dashboard = DashboardContainer()
        self._sidebar = CardSidebar(self._dashboard)

        # Use horizontal layout instead of splitter so hiding sidebar frees space
        central_widget = QWidget()
        central_layout = QHBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._sidebar)
        central_layout.addWidget(self._dashboard, 1)  # dashboard stretches

        self.setCentralWidget(central_widget)

        self._create_cards()
        self._connect_signals()
        self._load_layout()

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Restore button for sidebar (hidden initially, shown when sidebar hidden)
        self._restore_sidebar_btn = QPushButton(">")
        self._restore_sidebar_btn.setFixedSize(15, 15)
        self._restore_sidebar_btn.setFlat(True)
        self._restore_sidebar_btn.setToolTip("Show sidebar")
        self._restore_sidebar_btn.clicked.connect(self._sidebar.show)
        self._restore_sidebar_btn.hide()
        self._status_bar.addWidget(self._restore_sidebar_btn)

        # Connect sidebar visibility signals
        self._sidebar.sidebar_hidden.connect(self._restore_sidebar_btn.show)
        self._sidebar.sidebar_shown.connect(self._restore_sidebar_btn.hide)

        self._setup_shortcuts()

        self._closing = False

    def _load_layout(self):
        """Load saved layout and state from persistence."""
        try:
            snapshot = self._persistence.load_layout()
            if snapshot:
                self._dashboard.apply_layout_snapshot(snapshot)
                logger.info("Loaded layout with %d cards", len(snapshot))
        except Exception as e:
            logger.warning("Could not load layout: %s", e)
        
        try:
            state = self._persistence.load_state()
            if state:
                self._status_card.set_state(state.get("status_card", {}))
                self._scenario_card.set_state(state.get("scenario_card", {}))
                self._packets_card.set_state(state.get("packets_card", {}))
                self._logs_card.set_state(state.get("logs_card", {}))
                logger.info("Loaded card states")
        except Exception as e:
            logger.warning("Could not load state: %s", e)

    def _save_layout(self):
        """Save current layout and state to persistence."""
        try:
            snapshot = self._dashboard.get_layout_snapshot()
            self._persistence.save_layout(snapshot)
        except Exception as e:
            logger.error("Could not save layout: %s", e)
        
        try:
            state = {
                "status_card": self._status_card.get_state(),
                "scenario_card": self._scenario_card.get_state(),
                "packets_card": self._packets_card.get_state(),
                "logs_card": self._logs_card.get_state(),
            }
            self._persistence.save_state(state)
        except Exception as e:
            logger.error("Could not save state: %s", e)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for the main window."""
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.close)

        toggle_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        toggle_shortcut.activated.connect(self._on_toggle_server)

        run_shortcut = QShortcut(QKeySequence("F5"), self)
        run_shortcut.activated.connect(self._on_run_scenario_shortcut)

        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self._close_overlay_if_open)

        for i, card_name in enumerate(["_status_card", "_scenario_card", "_packets_card", "_logs_card"], 1):
            if hasattr(self, card_name):
                shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
                shortcut.activated.connect(lambda c=card_name: self._focus_card(c))

        # Shortcut to toggle sidebar
        sidebar_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        sidebar_shortcut.activated.connect(
            lambda: self._sidebar.hide() if self._sidebar.isVisible() else self._sidebar.show()
        )

        self.setFocusPolicy(Qt.StrongFocus)
        for card in [self._status_card, self._scenario_card, self._packets_card, self._logs_card]:
            card.setFocusPolicy(Qt.StrongFocus)

    @qasync.asyncSlot()
    async def _on_toggle_server(self):
        """Toggle server start/stop."""
        if self._status_card.is_server_running():
            try:
                await self._engine_wrapper.stop()
                self._status_bar.showMessage("Server stopped", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to stop: {e}")
        else:
            try:
                await self._engine_wrapper.start()
                self._status_bar.showMessage("Server started", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start: {e}")

    def _on_run_scenario_shortcut(self):
        """Run scenario via F5 shortcut."""
        self._scenario_card.on_run_clicked()

    def _close_overlay_if_open(self):
        """Close any open overlay dialog."""
        pass

    def _focus_card(self, card_attr: str):
        """Focus a specific card by attribute name."""
        if hasattr(self, card_attr):
            card = getattr(self, card_attr)
            card.setFocus()
            card.show()

    def _create_cards(self):
        cmw_ip = self._config.cmw500.ip or ""
        self._status_card = SystemStatusCard(card_id="system_status", cmw_ip=cmw_ip)
        self._scenario_card = ScenarioRunnerCard(card_id="scenario_runner")
        self._packets_card = LivePacketsCard(card_id="live_packets")
        self._logs_card = SystemLogsCard(card_id="system_logs", event_bridge=self._event_bridge)

        self._dashboard.add_card(self._status_card, row=0, col=0)
        self._dashboard.add_card(self._scenario_card, row=0, col=4)
        self._dashboard.add_card(self._packets_card, row=4, col=0)
        self._dashboard.add_card(self._logs_card, row=4, col=4)

        self._dashboard.cards_changed.connect(self._save_layout)

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

        self._status_card.toggle_server_requested.connect(self._on_toggle_server)
        self._scenario_card.run_requested.connect(self._on_run_scenario)
        self._scenario_card.stop_requested.connect(self._on_stop_scenario)

    @qasync.asyncSlot(str)
    async def _on_run_scenario(self, path):
        try:
            status = await self._engine_wrapper.get_status()
            if not status.get("running"):
                await self._engine_wrapper.start()
            await self._engine_wrapper.run_scenario(path)
        except Exception as e:
            QMessageBox.critical(self, "Scenario Error", str(e))
            self._scenario_card.on_scenario_stopped()

    @qasync.asyncSlot()
    async def _on_stop_scenario(self):
        """Stop running scenario."""
        try:
            await self._engine_wrapper.stop_scenario()
        except Exception as e:
            logger.warning("Could not stop scenario: %s", e)
        finally:
            self._scenario_card.on_scenario_stopped()

    def closeEvent(self, event):
        """Handle window close - save state and stop engine gracefully."""
        if self._closing:
            event.accept()
            return
        
        self._closing = True
        self._save_layout()
        event.ignore()
        
        async def shutdown():
            try:
                await self._engine_wrapper.stop()
            except Exception:
                pass
            finally:
                QApplication.instance().quit()
        
        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(shutdown())
        except RuntimeError:
            # No event loop running, just quit
            event.accept()
