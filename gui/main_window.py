# OMEGA_EGTS GUI
from PySide6.QtWidgets import QMainWindow, QStatusBar

from gui.dashboard.container import DashboardContainer
from gui.dashboard.cards.system_status import SystemStatusCard
from gui.dashboard.cards.scenario_runner import ScenarioRunnerCard
from gui.dashboard.cards.live_packets import LivePacketsCard
from gui.dashboard.cards.system_logs import SystemLogsCard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OMEGA_EGTS Tester")
        self.resize(1024, 768)

        self._dashboard = DashboardContainer()
        self.setCentralWidget(self._dashboard)

        self._status_card = SystemStatusCard()
        self._scenario_card = ScenarioRunnerCard()
        self._packets_card = LivePacketsCard()
        self._logs_card = SystemLogsCard()

        self._dashboard.add_card(self._status_card, 0, 0)
        self._dashboard.add_card(self._scenario_card, 0, 1)
        self._dashboard.add_card(self._packets_card, 1, 0)
        self._dashboard.add_card(self._logs_card, 1, 1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)