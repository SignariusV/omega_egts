# Integration tests for Packet Detail Card feature
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QHideEvent

from gui.dashboard.cards.live_packets import LivePacketsCard
from gui.dashboard.cards.packet_detail import PacketDetailCard
from gui.widgets.packet_table import PacketTableModel


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def live_packets_card(qtbot):
    """Create LivePacketsCard for integration testing."""
    card = LivePacketsCard()
    qtbot.addWidget(card)
    return card


@pytest.fixture
def sample_packet():
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


class TestLivePacketsToDetailIntegration:
    """Integration tests for LivePacketsCard -> PacketDetailCard workflow."""

    def test_open_detail_cards_dict_exists(self, live_packets_card):
        """Test that the card has _open_detail_cards dict."""
        assert hasattr(live_packets_card, '_open_detail_cards')
        assert isinstance(live_packets_card._open_detail_cards, dict)

    def test_close_detail_card_removes_from_dict(self, live_packets_card):
        """Test that closing detail card removes it from tracking dict."""
        class MockDetailCard:
            def __init__(self, cid):
                self.card_id = cid

        live_packets_card._open_detail_cards = {
            "pkt_1": MockDetailCard("pkt_1"),
            "pkt_2": MockDetailCard("pkt_2"),
        }

        live_packets_card._on_detail_card_closed("pkt_1")

        assert "pkt_1" not in live_packets_card._open_detail_cards
        assert "pkt_2" in live_packets_card._open_detail_cards

    def test_close_all_detail_cards(self, live_packets_card):
        """Test closing all detail cards."""
        closed_cards = []

        class MockDetailCard:
            def __init__(self, cid):
                self.card_id = cid
            def close(self):
                closed_cards.append(self.card_id)

        live_packets_card._open_detail_cards = {
            f"pkt_test_{i}": MockDetailCard(f"pkt_test_{i}")
            for i in range(3)
        }

        live_packets_card._close_all_detail_cards()

        assert len(live_packets_card._open_detail_cards) == 0
        assert len(closed_cards) == 3

    def test_hide_live_packets_closes_all_detail_cards(self, live_packets_card):
        """Test that hiding LivePacketsCard closes all detail cards."""
        closed_cards = []

        class MockDetailCard:
            def __init__(self, cid):
                self.card_id = cid
            def close(self):
                closed_cards.append(self.card_id)

        live_packets_card._open_detail_cards = {
            f"pkt_test_{i}": MockDetailCard(f"pkt_test_{i}")
            for i in range(3)
        }

        # Call hideEvent
        event = QHideEvent()
        live_packets_card.hideEvent(event)

        assert len(live_packets_card._open_detail_cards) == 0
        assert len(closed_cards) == 3

    def test_max_detail_cards_constant(self, live_packets_card):
        """Test that max 6 detail cards are allowed."""
        assert live_packets_card.MAX_DETAIL_CARDS == 6


class TestPacketDetailCardWorkflow:
    """Integration tests for PacketDetailCard workflow."""

    def test_card_shows_compact_view_first(self, qtbot, sample_packet):
        """Test that card shows compact view by default."""
        card = PacketDetailCard(sample_packet, card_id="test_pkt")
        qtbot.addWidget(card)
        card.show()
        assert card._stack.currentIndex() == 0  # Compact view

    def test_expand_shows_tabs(self, qtbot, sample_packet):
        """Test that expanded view shows tab widget."""
        card = PacketDetailCard(sample_packet, card_id="test_pkt")
        qtbot.addWidget(card)
        card.show()
        # Switch to expanded view (card might be in compact due to resizeEvent)
        card.expand()
        assert card._stack.currentIndex() == 1  # Expanded view
        assert hasattr(card, '_tabs')
        assert card._tabs.count() == 4

    def test_toggle_floating_mode(self, qtbot, sample_packet):
        """Test toggling floating mode."""
        card = PacketDetailCard(sample_packet, card_id="test_pkt")
        qtbot.addWidget(card)

        # Initially not floating
        assert card._floating == False

        # Toggle to floating
        card.toggle_floating()
        assert card._floating == True

        # Toggle back
        card.toggle_floating()
        assert card._floating == False

    def test_closed_signal_emitted(self, qtbot, sample_packet):
        """Test that closed signal is emitted when card is closed."""
        card = PacketDetailCard(sample_packet, card_id="test_pkt")
        qtbot.addWidget(card)

        signal_received = False
        received_id = None

        def on_closed(cid):
            nonlocal signal_received, received_id
            signal_received = True
            received_id = cid

        card.closed.connect(on_closed)
        card.close()

        assert signal_received == True
        assert received_id == "test_pkt"
