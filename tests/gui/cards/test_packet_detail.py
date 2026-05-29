# Tests for PacketDetailCard
import pytest
from PySide6.QtWidgets import QApplication, QTreeWidget, QSplitter
from PySide6.QtCore import Qt

from gui.dashboard.cards.packet_detail import PacketDetailCard
from gui.utils.hex_viewer import HexDumpWidget


def _crc8(data: bytes) -> int:
    poly = 0x31; crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80: crc = (crc << 1) ^ poly
            else: crc <<= 1
            crc &= 0xFF
    return crc


def _crc16(data: bytes) -> int:
    poly = 0x1021; crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000: crc = (crc << 1) ^ poly
            else: crc <<= 1
            crc &= 0xFFFF
    return crc


def _valid_appdata_hex(pid: int = 27) -> str:
    """Build a valid minimal APPDATA hex with TERM_IDENTITY (TID=12345).

    TID=12345 = 0x00003039, stored as LE: 39 30 00 00
    """
    hdr = bytes([0x01, 0x00, 0x00, 0x0B, 0x00, 0x0E, 0x00,
                 pid & 0xFF, (pid >> 8) & 0xFF, 0x01])
    hcs = _crc8(hdr)
    tid_le = (12345).to_bytes(4, 'little')  # 39 30 00 00
    records = bytes([0x07, 0x00, 0x01, 0x00, 0x00, 0x01, 0x01,
                     0x01, 0x04, 0x00]) + tid_le
    sfrcs = _crc16(records)
    return (hdr + bytes([hcs]) + records + sfrcs.to_bytes(2, 'little')).hex()


@pytest.fixture
def sample_packet():
    """Sample packet data for testing."""
    return {
        "timestamp": "2026-05-08T14:32:01.123",
        "pid": "27",
        "service": "1",
        "length": 27,
        "channel": "tcp",
        "crc": "OK",
        "duplicate": "No",
        "hex": _valid_appdata_hex(),
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
        assert "CRC Invalid" in summary
        assert "Duplicate" in summary
        assert "No Parse" in summary


class TestPacketDetailCardExpandedView:
    def test_has_two_tabs(self, packet_detail_card):
        packet_detail_card.show()
        packet_detail_card.expand()
        assert hasattr(packet_detail_card, '_tabs')
        assert packet_detail_card._tabs.count() == 2

    def test_tab_names(self, packet_detail_card):
        packet_detail_card.show()
        packet_detail_card.expand()
        tab_names = [
            packet_detail_card._tabs.tabText(i)
            for i in range(packet_detail_card._tabs.count())
        ]
        assert "Protocol" in tab_names
        assert "Metadata" in tab_names

    def test_protocol_tab_has_splitter_with_tree_and_hex(self, packet_detail_card):
        packet_detail_card.show()
        packet_detail_card.expand()
        protocol_widget = packet_detail_card._tabs.widget(0)
        splitter = protocol_widget.findChild(QSplitter)
        assert splitter is not None
        assert splitter.findChild(QTreeWidget) is not None
        assert splitter.findChild(HexDumpWidget) is not None

    def test_protocol_tree_has_columns(self, packet_detail_card):
        packet_detail_card.show()
        packet_detail_card.expand()
        protocol_widget = packet_detail_card._tabs.widget(0)
        tree = protocol_widget.findChild(QTreeWidget)
        assert tree is not None
        assert tree.headerItem().text(0) == "Offset"
        assert tree.headerItem().text(1) == "Field → Value"
        assert tree.headerItem().text(2) == "Hex"

    def test_protocol_tree_contains_packet_sections(self, packet_detail_card):
        packet_detail_card.show()
        packet_detail_card.expand()
        protocol_widget = packet_detail_card._tabs.widget(0)
        tree = protocol_widget.findChild(QTreeWidget)
        root_items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        field_strs = [item.text(1) for item in root_items]
        assert any("Transport Header" in s for s in field_strs)


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


class TestPacketDetailCardState:
    def test_get_state_returns_empty(self, packet_detail_card):
        state = packet_detail_card.get_state()
        assert state == {}

    def test_set_state_does_nothing(self, packet_detail_card):
        packet_detail_card.set_state({"some": "data"})
