# OMEGA_EGTS GUI
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QHideEvent
from gui.dashboard.cards.live_packets import LivePacketsCard
from gui.dashboard.cards.packet_detail import PacketDetailCard
from gui.widgets.packet_table import PacketTableModel
from gui.dashboard.card_base import DisplayState
from core.pipeline import PacketContext
from libs.egts.models import ParseResult, Packet, Record


def _make_processed_event(packet_id: int, channel: str = "EGTS") -> dict:
    """Build a realistic packet.processed event."""
    pkt = Packet(
        packet_id=packet_id,
        packet_type=1,
        records=[Record(record_id=1, service_type=1)],
    )
    ctx = PacketContext(
        raw=bytes([0x01, 0x18, 0x00, packet_id & 0xFF]),
        connection_id="test",
        channel=channel,
        parsed=ParseResult(packet=pkt),
        crc_valid=True,
        is_duplicate=False,
    )
    return {
        "ctx": ctx,
        "connection_id": "test",
        "channel": channel,
        "parsed": ctx.parsed,
        "crc_valid": True,
        "is_duplicate": False,
        "terminated": False,
    }


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
        card.set_display_state(DisplayState.COMPACT)
        assert card._stack.currentIndex() == 0
        assert card._compact_table is not None

    def test_expanded_mode_shows_full_table(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.set_display_state(DisplayState.EXPANDED)
        assert card._stack.currentIndex() == 1
        assert card._table is not None

    def test_packet_processed_updates_model(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.on_packet_processed(_make_processed_event(packet_id=123))
        qtbot.wait(150)
        assert card._packet_model.rowCount() == 1
        assert card._stats_label.text() != "Rx: 0 | Tx: 0"

    def test_packet_sent_updates_model(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.on_packet_sent({
            "packet_bytes": b"\x01\x18\x00\x01",
            "pid": 456,
            "channel": "SRTC",
        })
        qtbot.wait(150)
        assert card._packet_model.rowCount() == 1
        assert "Tx: 1" in card._stats_label.text()

    def test_filter(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.on_packet_processed(_make_processed_event(packet_id=123))
        card.on_packet_processed(_make_processed_event(packet_id=456))
        qtbot.wait(150)
        card._filter_input.setText("123")
        assert card._proxy.rowCount() == 1

    def test_clear_button(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        card.on_packet_processed(_make_processed_event(packet_id=999))
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


class TestPositionFloatingCard:
    """Regression for Б-11: cascade must wrap within main window, not collapse."""

    @pytest.fixture
    def packet_card(self, qtbot):
        card = LivePacketsCard()
        qtbot.addWidget(card)
        return card

    def test_cascade_wraps_within_main_window(self, packet_card, app, monkeypatch):
        """Offsets must wrap modulo (main_w - card_w) // stride, not collapse to (base_x, base_y)."""
        from PySide6.QtCore import QRect

        class MockMainWindow:
            def geometry(self):
                # 1000×800 main window: wrap_step = (1000-500)//30 = 16
                return QRect(0, 0, 1000, 800)

        monkeypatch.setattr(packet_card, "window", lambda: MockMainWindow())

        positions = []
        class FakeCard:
            def set_floating_position(self, x, y):
                positions.append((x, y))

        base_x, base_y = 250, 200
        stride = 30
        wrap_step = (1000 - 500) // 30  # 16

        # Mimic real call pattern: _position_floating_card is called BEFORE the
        # card is added to the dict. So the Nth call sees len = N-1.
        for i in range(18):
            packet_card._open_detail_cards = {f"pkt_{j}": object() for j in range(i)}
            packet_card._position_floating_card(FakeCard())

        # 1st call: len=0 → offset=0 → (250, 200)
        assert positions[0] == (base_x, base_y)
        # 2nd call: len=1 → offset=30 → (280, 230)
        assert positions[1] == (base_x + stride, base_y + stride)
        # 17th call: len=16 → 16%16=0 → wraps to (250, 200)
        assert positions[wrap_step] == (base_x, base_y)
        # 18th call: len=17 → 17%16=1 → (280, 230) again
        assert positions[wrap_step + 1] == (base_x + stride, base_y + stride)
        # All x values must be within the main window
        for x, y in positions:
            assert x >= base_x
            assert x <= base_x + wrap_step * stride

    def test_no_window_does_nothing(self, packet_card, app, monkeypatch):
        monkeypatch.setattr(packet_card, "window", lambda: None)
        # Should not raise
        packet_card._position_floating_card(object())