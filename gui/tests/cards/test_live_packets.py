# OMEGA_EGTS GUI
import pytest
from PySide6.QtWidgets import QApplication
from gui.dashboard.cards.live_packets import LivePacketsCard
from gui.widgets.packet_table import PacketTableModel
from gui.dashboard.card_base import DisplayState


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class TestPacketTableModel:
    def test_initial_row_count(self):
        model = PacketTableModel()
        assert model.rowCount() == 0

    def test_add_packet(self):
        model = PacketTableModel()
        model.add_packet({"pid": "123", "service": "EGTS", "length": "100", "channel": "EGTS"})
        model.flush()
        assert model.rowCount() == 1

    def test_buffer_limit(self):
        model = PacketTableModel()
        for i in range(6000):
            model.add_packet({"pid": str(i), "service": "EGTS", "length": "100"})
        model.flush()
        assert model.rowCount() == 5000
        assert model.get_rx_count() == 0

    def test_rx_tx_counts(self):
        model = PacketTableModel()
        model.add_packet({"direction": "rx"})
        model.add_packet({"direction": "rx"})
        model.add_packet({"direction": "tx"})
        model.flush()
        assert model.get_rx_count() == 2
        assert model.get_tx_count() == 1

    def test_clear(self):
        model = PacketTableModel()
        model.add_packet({"pid": "123"})
        model.flush()
        model.clear()
        assert model.rowCount() == 0
        assert model.get_rx_count() == 0

    def test_data_display(self):
        model = PacketTableModel()
        model.add_packet({"pid": "123", "service": "EGTS", "length": "100"})
        model.flush()
        idx = model.index(0, 1)
        assert model.data(idx) == "123"


class TestLivePacketsCard:
    def test_initial_state(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        assert card.title == "Live Packets"

    def test_compact_mode_shows_mini_table(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.COMPACT)
        assert card._current_widget == card._compact_widget
        assert card._mini_table is not None

    def test_expanded_mode_shows_full_table(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        assert card._current_widget == card._expanded_widget
        assert card._table is not None

    def test_packet_processed_updates_model(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        card.on_packet_processed({"pid": "123", "service": "EGTS", "length": "100", "channel": "EGTS"})
        qtbot.wait(150)
        assert card._model.rowCount() == 1
        assert card._stats_label.text() != "Rx: 0 | Tx: 0"

    def test_packet_sent_updates_model(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        card.on_packet_sent({"pid": "456", "service": "SRVC", "length": "50", "channel": "SRTC"})
        qtbot.wait(150)
        assert card._model.rowCount() == 1
        assert "Tx: 1" in card._stats_label.text()

    def test_filter(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        card.on_packet_processed({"pid": "123", "service": "EGTS", "length": "100", "channel": "EGTS"})
        card.on_packet_processed({"pid": "456", "service": "SRVC", "length": "50", "channel": "SRTC"})
        qtbot.wait(150)
        card._filter_input.setText("123")
        assert card._proxy.rowCount() == 1

    def test_clear_button(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        card.on_packet_processed({"pid": "123"})
        card._clear_btn.click()
        assert card._model.rowCount() == 0
        assert card._stats_label.text() == "Rx: 0 | Tx: 0"

    def test_get_set_state(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        state = card.get_state()
        assert "filter_text" in state
        card.set_state({"filter_text": "test", "channel": "EGTS"})
        assert card._filter_input.text() == "test"