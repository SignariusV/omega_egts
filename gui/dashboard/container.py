# OMEGA_EGTS GUI
from PySide6.QtWidgets import QWidget, QGridLayout
from PySide6.QtCore import Signal, Qt
from gui.dashboard.card_base import BaseCard


GRID_ROWS = 8
GRID_COLS = 8
GRID_GAP = 6


class DashboardContainer(QWidget):
    cards_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(GRID_GAP)
        self._cards = {}  # id -> (row, col, row_span, col_span)
        self.setAcceptDrops(True)

    def add_card(self, card: BaseCard, row: int = 0, col: int = 0, row_span: int = None, col_span: int = None):
        """Add a card to the dashboard at the specified grid position."""
        card.setParent(self)
        card.show()
        # Use card's grid size if not specified
        if row_span is None or col_span is None:
            row_span, col_span = card.grid_size
        card_id = id(card)
        self._grid.addWidget(card, row, col, row_span, col_span)
        self._cards[card_id] = (row, col, row_span, col_span)
        card.destroyed.connect(lambda: self.remove_card(card_id))
        card.drag_started.connect(lambda: self._on_drag_start(card))
        card.grid_size_changed.connect(lambda rs, cs: self._on_grid_size_changed(card, rs, cs))
        self.cards_changed.emit()

    def remove_card(self, card_id):
        """Remove a card from the dashboard."""
        if card_id not in self._cards:
            return
        # Find the card widget
        for card in self.findChildren(BaseCard):
            if id(card) == card_id:
                self._grid.removeWidget(card)
                card.setParent(None)
                break
        del self._cards[card_id]
        self.cards_changed.emit()

    def move_card(self, card_id, new_row, new_col):
        """Move a card to a new grid position."""
        if card_id not in self._cards:
            return
        # Find the card widget
        for card in self.findChildren(BaseCard):
            if id(card) == card_id:
                row_span, col_span = self._cards[card_id][2], self._cards[card_id][3]
                self._grid.removeWidget(card)
                self._grid.addWidget(card, new_row, new_col, row_span, col_span)
                self._cards[card_id] = (new_row, new_col, row_span, col_span)
                self.cards_changed.emit()
                break

    def _on_grid_size_changed(self, card, row_span, col_span):
        """Handle card grid size change."""
        card_id = id(card)
        if card_id in self._cards:
            row, col = self._cards[card_id][0], self._cards[card_id][1]
            self._grid.removeWidget(card)
            self._grid.addWidget(card, row, col, row_span, col_span)
            self._cards[card_id] = (row, col, row_span, col_span)
            self.cards_changed.emit()

    def _on_drag_start(self, card):
        """Handle drag start."""
        pass  # Placeholder for drag-and-drop

    def get_layout_snapshot(self):
        """Return the current layout as a list of dicts."""
        return [
            {"id": cid, "row": r, "col": c, "row_span": rs, "col_span": cs}
            for cid, (r, c, rs, cs) in self._cards.items()
        ]

    def load_layout(self, snapshot: list[dict]):
        """Load a layout from a snapshot."""
        # Clear current layout
        for card_id in list(self._cards.keys()):
            self.remove_card(card_id)

        # Load from snapshot
        for item in snapshot:
            card_id = item.get("id")
            row = item.get("row", 0)
            col = item.get("col", 0)
            row_span = item.get("row_span", 1)
            col_span = item.get("col_span", 1)

            # Find the card by id
            for card in self.findChildren(BaseCard):
                if id(card) == card_id:
                    card.setParent(self)
                    card.show()
                    self._grid.addWidget(card, row, col, row_span, col_span)
                    self._cards[card_id] = (row, col, row_span, col_span)
                    card.destroyed.connect(lambda cid=card_id: self.remove_card(cid))
                    card.drag_started.connect(lambda: self._on_drag_start(card))
                    card.grid_size_changed.connect(lambda rs, cs, c=card: self._on_grid_size_changed(c, rs, cs))
                    break

        self.cards_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)

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
        # Find the card and move it to the drop position
        for card in self.findChildren(BaseCard):
            if id(card) == card_id:
                pos = event.position().toPoint()
                # Calculate grid position from drop position
                col_width = self.width() // GRID_COLS
                row_height = self.height() // GRID_ROWS
                new_col = max(0, min(GRID_COLS - 1, pos.x() // col_width))
                new_row = max(0, min(GRID_ROWS - 1, pos.y() // row_height))
                self.move_card(card_id, new_row, new_col)
                break
        event.acceptProposedAction()
