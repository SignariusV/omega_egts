# OMEGA_EGTS GUI
import collections
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer
from datetime import datetime


class PacketTableModel(QAbstractTableModel):
    HEADERS = ["Timestamp", "PID", "Service", "Length", "Channel", "CRC", "Duplicate"]
    MAX_ROWS = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffer = collections.deque(maxlen=self.MAX_ROWS)
        self._pending = []
        self._rx_count = 0
        self._tx_count = 0
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self.flush)
        self._flush_timer.start(100)

    def add_packet(self, packet: dict):
        packet.setdefault("timestamp", datetime.now().strftime("%H:%M:%S.%f")[:-3])
        self._pending.append(packet)
        direction = packet.get("direction", "").lower()
        if direction == "rx":
            self._rx_count += 1
        elif direction == "tx":
            self._tx_count += 1

    def flush(self):
        if not self._pending:
            return
        rows_to_insert = min(len(self._pending), self.MAX_ROWS - len(self._buffer))
        if rows_to_insert <= 0:
            self._pending = []
            return
        self.beginInsertRows(QModelIndex(), 0, rows_to_insert - 1)
        for pkt in self._pending[:rows_to_insert]:
            self._buffer.appendleft(pkt)
        self._pending = []
        self.endInsertRows()

    def rowCount(self, parent=QModelIndex()):
        return len(self._buffer)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = list(self._buffer)[index.row()]
        col = index.column()
        key = self.HEADERS[col].lower()
        return row.get(key, "")

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def get_rx_count(self) -> int:
        return self._rx_count

    def get_tx_count(self) -> int:
        return self._tx_count

    def clear(self):
        self.beginResetModel()
        self._buffer.clear()
        self._pending.clear()
        self._rx_count = 0
        self._tx_count = 0
        self.endResetModel()