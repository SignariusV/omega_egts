# Tests for PacketDetailCard
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from gui.dashboard.cards.packet_detail import PacketDetailCard


@pytest.fixture
def sample_packet():
    """Sample packet data for testing."""
    return {
        "timestamp": "2026-05-08T14:32:01.123",
        "pid": "27",
        "service": "1",
        "length": 64,
        "channel": "tcp",
        "crc": "OK",
        "duplicate": "No",
        "hex": "0100000B0021001B0001321A00",
        "parsed": {
            "packet_id": 27,
            "packet_type": 1,
            "service": 1,
            "header_length": 11,
            "records_count": 1,
            "priority": "normal",
            "compression": "none",
            "records": [
                {
                    "record_id": 1,
                    "service_type": 1,
                    "subrecords": [
                        {"subrecord_type": "TERM_IDENTITY", "data": {"tid": 12345}}
                    ]
                }
            ]
        },
        "direction": "rx"
    }


@pytest.fixture
def error_packet():
    """Packet with errors for testing."""
    return {
        "timestamp": "2026-05-08T14:33:01.456",
        "pid": "28",
        "service": "?",
        "length": 32,
        "channel": "tcp",
        "crc": "FAIL",
        "duplicate": "Yes",
        "hex": "0100000B0021001C0001321A00",
        "parsed": {},
        "direction": "rx"
    }


@pytest.fixture
def packet_detail_card(qtbot, sample_packet):
    """Create PacketDetailCard for testing."""
    card = PacketDetailCard(sample_packet, card_id="test_pkt_1")
    qtbot.addWidget(card)
    return card


class TestPacketDetailCardInit:
    def test_init_creates_card(self, qtbot, sample_packet):
        card = PacketDetailCard(sample_packet, card_id="pkt_1")
        qtbot.addWidget(card)
        assert card.card_id == "pkt_1"
        assert card._packet == sample_packet
        assert card._floating == False

    def test_title_contains_pid(self, packet_detail_card, sample_packet):
        assert "27" in packet_detail_card.title


class TestPacketDetailCardCompactView:
    def test_compact_view_shows_ok_for_good_packet(self, qtbot, sample_packet):
        card = PacketDetailCard(sample_packet, card_id="pkt_ok")
        qtbot.addWidget(card)
        card.show()
        assert card._is_packet_ok() == True

    def test_compact_view_shows_error_for_bad_packet(self, qtbot, error_packet):
        card = PacketDetailCard(error_packet, card_id="pkt_err")
        qtbot.addWidget(card)
        card.show()
        assert card._is_packet_ok() == False

    def test_error_summary(self, qtbot, error_packet):
        card = PacketDetailCard(error_packet, card_id="pkt_err2")
        qtbot.addWidget(card)
        summary = card._get_error_summary()
        assert "CRC FAIL" in summary
        assert "DUP" in summary
        assert "NO PARSE" in summary


class TestPacketDetailCardExpandedView:
    def test_has_four_tabs(self, packet_detail_card):
        packet_detail_card.show()
        packet_detail_card.expand()
        assert hasattr(packet_detail_card, '_tabs')
        assert packet_detail_card._tabs.count() == 4

    def test_tab_names(self, packet_detail_card):
        packet_detail_card.show()
        packet_detail_card.expand()
        tab_names = [
            packet_detail_card._tabs.tabText(i)
            for i in range(packet_detail_card._tabs.count())
        ]
        assert "Raw Data" in tab_names
        assert "Transport" in tab_names
        assert "Service" in tab_names
        assert "Metadata" in tab_names


class TestPacketDetailCardFloatingMode:
    def test_toggle_floating(self, qtbot, sample_packet):
        card = PacketDetailCard(sample_packet, card_id="pkt_float")
        qtbot.addWidget(card)
        assert card._floating == False
        card.toggle_floating()
        assert card._floating == True

    def test_closed_signal(self, qtbot, sample_packet):
        card = PacketDetailCard(sample_packet, card_id="pkt_signal")
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
        assert received_id == "pkt_signal"


class TestPacketDetailCardHexFormat:
    def test_format_hex_dump(self, packet_detail_card):
        hex_str = "0100000B0021001B0001321A00"
        result = packet_detail_card._format_hex_dump(hex_str)
        assert "01 00" in result
        assert len(result) > 0

    def test_format_empty_hex(self, packet_detail_card):
        result = packet_detail_card._format_hex_dump("")
        assert result == "(empty)"


class TestPacketDetailCardState:
    def test_get_state_returns_empty(self, packet_detail_card):
        state = packet_detail_card.get_state()
        assert state == {}

    def test_set_state_does_nothing(self, packet_detail_card):
        packet_detail_card.set_state({"some": "data"})
