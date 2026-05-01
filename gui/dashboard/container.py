# OMEGA_EGTS GUI
from PySide6.QtWidgets import QWidget, QGridLayout, QFrame
from PySide6.QtCore import Signal, Qt
from gui.dashboard.card_base import BaseCard


class DashboardContainer(QWidget):
    cards_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(6)
        self._cards = {}
        self.setAcceptDrops(True)

    def add_card(self, card: BaseCard, row: int, col: int, row_span: int = 1, col_span: int = 1):
        card_id = id(card)
        self._grid.addWidget(card, row, col)
        self._grid.setColumnStretch(col, 1)
        self._grid.setRowStretch(row, 1)
        self._cards[card_id] = (row, col, row_span, col_span)
        card.destroyed.connect(lambda cid=card_id: self._on_card_destroyed(cid))
        self.cards_changed.emit()

    def _on_card_destroyed(self, card_id):
        if card_id in self._cards:
            del self._cards[card_id]
            self.cards_changed.emit()

    def remove_card(self, card_id: int):
        if card_id not in self._cards:
            return
        for i in range(self._grid.count()):
            item = self._grid.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if id(widget) == card_id:
                    self._grid.removeWidget(widget)
                    widget.deleteLater()
                    break
        del self._cards[card_id]
        self.cards_changed.emit()

    def get_layout_snapshot(self):
        return [
            {"id": cid, "row": r, "col": c, "row_span": rs, "col_span": cs}
            for cid, (r, c, rs, cs) in self._cards.items()
        ]

    def move_card(self, card_id: int, new_row: int, new_col: int, new_row_span: int = 1, new_col_span: int = 1):
        if card_id not in self._cards:
            return
        old_row, old_col, old_rs, old_cs = self._cards[card_id]
        for i in range(self._grid.count()):
            item = self._grid.itemAt(i)
            if item and item.widget() and id(item.widget()) == card_id:
                self._grid.removeWidget(item.widget())
                break
        self._grid.addWidget(self.findChild(BaseCard, str(card_id)), new_row, new_col, new_row_span, new_col_span)
        self._cards[card_id] = (new_row, new_col, new_row_span, new_col_span)
        self.cards_changed.emit()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        card_id = int(event.mimeData().text())
        pos = event.position().toPoint()
        new_row = max(0, pos.y() // 150)
        new_col = max(0, pos.x() // 200)
        self.move_card(card_id, new_row, new_col)
        event.acceptProposedAction()