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
        self._grid.addWidget(card, row, col, row_span, col_span)
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
        card_widget = None
        for i in range(self._grid.count()):
            item = self._grid.itemAt(i)
            if item and item.widget() and id(item.widget()) == card_id:
                card_widget = item.widget()
                self._grid.removeItem(item)
                break
        if card_widget:
            self._grid.addWidget(card_widget, new_row, new_col, new_row_span, new_col_span)
            self._cards[card_id] = (new_row, new_col, new_row_span, new_col_span)
            self.cards_changed.emit()

    def find_card_by_id(self, card_id: int) -> QWidget | None:
        for i in range(self._grid.count()):
            item = self._grid.itemAt(i)
            if item and item.widget() and id(item.widget()) == card_id:
                return item.widget()
        return None

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not event.mimeData().hasText():
            return
        try:
            card_id = int(event.mimeData().text())
        except ValueError:
            return
        pos = event.position().toPoint()
        new_row = pos.y() // 100
        new_col = pos.x() // 200
        self.move_card(card_id, new_row, new_col)
        event.acceptProposedAction()