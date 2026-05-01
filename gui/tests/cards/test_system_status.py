# OMEGA_EGTS GUI
import pytest
from PySide6.QtWidgets import QApplication
from gui.dashboard.cards.system_status import SystemStatusCard
from gui.dashboard.card_base import DisplayState


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class TestSystemStatusCard:
    def test_initial_state(self, qtbot):
        card = SystemStatusCard()
        qtbot.addWidget(card)
        assert card.title == "System Status"
        assert card._server_running is False
        assert card._cmw_connected is False

    def test_compact_mode_shows_indicators(self, qtbot):
        card = SystemStatusCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.COMPACT)
        assert card._display_state == DisplayState.COMPACT
        assert card._current_widget == card._compact_widget
        assert card._compact_widget._server_indicator.get_color() == "#F44747"
        assert card._compact_widget._cmw_indicator.get_color() == "#F44747"

    def test_expanded_mode_shows_groups(self, qtbot):
        card = SystemStatusCard()
        qtbot.addWidget(card)
        card.resize(600, 400)
        qtbot.wait(50)
        assert card._display_state == DisplayState.EXPANDED
        assert card._current_widget == card._expanded_widget

    def test_cmw_status_signal_updates(self, qtbot):
        card = SystemStatusCard()
        qtbot.addWidget(card)
        card.resize(600, 400)
        qtbot.wait(50)
        card.on_cmw_connected({"imei": "123456789012345", "imsi": "250010000000000", "rssi": "-65", "ber": "0.1"})
        assert card._cmw_data.get("imei") == "123456789012345"
        assert card._cmw_data.get("rssi") == "-65"

    def test_server_start_stop(self, qtbot):
        card = SystemStatusCard()
        qtbot.addWidget(card)
        card.on_server_started({"port": 8090})
        assert card._server_running is True
        card.on_server_stopped()
        assert card._server_running is False

    def test_get_set_state(self, qtbot):
        card = SystemStatusCard()
        qtbot.addWidget(card)
        state = {"server_running": True, "server_port": 8090, "cmw_connected": True}
        card.set_state(state)
        assert card.get_state() == state

    def test_signals_emitted(self, qtbot, app):
        card = SystemStatusCard()
        qtbot.addWidget(card)
        started = []
        stopped = []
        card.start_requested.connect(lambda: started.append(True))
        card.stop_requested.connect(lambda: stopped.append(True))
        card._start_btn.click()
        assert len(started) == 1
        card.on_server_started({"port": 8090})
        card._stop_btn.setEnabled(True)
        card._stop_btn.click()
        assert len(stopped) == 1