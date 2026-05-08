# OMEGA_EGTS GUI
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QHideEvent
from gui.dashboard.cards.live_packets import LivePacketsCard
from gui.dashboard.cards.packet_detail import PacketDetailCard
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
        assert card._stack.currentIndex() == 0
        assert card._compact_table is not None

    def test_expanded_mode_shows_full_table(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card._set_display_state(DisplayState.EXPANDED)
        assert card._stack.currentIndex() == 1
        assert card._table is not None

    def test_packet_processed_updates_model(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.on_packet_processed({"pid": "123", "service": "EGTS", "length": "100", "channel": "EGTS"})
        qtbot.wait(150)
        assert card._packet_model.rowCount() == 1
        assert card._stats_label.text() != "Rx: 0 | Tx: 0"

    def test_packet_sent_updates_model(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.on_packet_sent({"pid": "456", "service": "SRVC", "length": "50", "channel": "SRTC"})
        qtbot.wait(150)
        assert card._packet_model.rowCount() == 1
        assert "Tx: 1" in card._stats_label.text()

    def test_filter(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.on_packet_processed({"pid": "123", "service": "EGTS", "length": "100", "channel": "EGTS"})
        card.on_packet_processed({"pid": "456", "service": "SRVC", "length": "50", "channel": "SRTC"})
        qtbot.wait(150)
        card._filter_input.setText("123")
        assert card._proxy.rowCount() == 1

    def test_clear_button(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.on_packet_processed({"pid": "123"})
        card._clear_btn.click()
        assert card._packet_model.rowCount() == 0
        assert card._stats_label.text() == "Rx: 0 | Tx: 0"

    def test_get_set_state(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        state = card.get_state()
        assert "filter_text" in state
        card.set_state({"filter_text": "test", "channel": "EGTS"})


class TestLivePacketsDetailCards:
    """Tests for packet detail card functionality."""

    @pytest.fixture
    def packet_card(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        return card

    @pytest.fixture
    def sample_packet_data(self):
        return {
            "timestamp": "2026-05-08T14:32:01.123",
            "pid": "27",
            "service": "1",
            "length": 64,
            "channel": "tcp",
            "crc": "OK",
            "duplicate": "No",
            "hex": "0100000B0021001B0001321A00",
            "parsed": {"packet_id": 27, "service": 1},
            "direction": "rx"
        }

    def test_max_detail_cards_constant(self, packet_card):
        assert packet_card.MAX_DETAIL_CARDS == 6

    def test_open_detail_cards_dict_exists(self, packet_card):
        """Test that the card has _open_detail_cards dict."""
        assert hasattr(packet_card, '_open_detail_cards')
        assert isinstance(packet_card._open_detail_cards, dict)

    def test_close_all_detail_cards(self, packet_card):
        """Test closing all detail cards."""
        closed_cards = []

        class MockDetailCard:
            def __init__(self, cid):
                self.card_id = cid
            def close(self):
                closed_cards.append(self.card_id)

        packet_card._open_detail_cards = {
            f"pkt_test_{i}": MockDetailCard(f"pkt_test_{i}")
            for i in range(3)
        }

        packet_card._close_all_detail_cards()

        assert len(packet_card._open_detail_cards) == 0
        assert len(closed_cards) == 3

    def test_on_detail_card_closed(self, packet_card):
        """Test that _on_detail_card_closed removes card from dict."""
        class MockDetailCard:
            def __init__(self, cid):
                self.card_id = cid

        packet_card._open_detail_cards = {
            "pkt_1": MockDetailCard("pkt_1"),
            "pkt_2": MockDetailCard("pkt_2"),
        }

        packet_card._on_detail_card_closed("pkt_1")

        assert "pkt_1" not in packet_card._open_detail_cards
        assert "pkt_2" in packet_card._open_detail_cards

    def test_hide_closes_detail_cards(self, packet_card):
        """Test that hiding LivePacketsCard closes detail cards."""
        closed = False

        class MockDetailCard:
            def close(self):
                nonlocal closed
                closed = True

        packet_card._open_detail_cards = {"test": MockDetailCard()}

        # Call hideEvent
        event = QHideEvent()
        packet_card.hideEvent(event)

        assert closed == True
        assert len(packet_card._open_detail_cards) == 0