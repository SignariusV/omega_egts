# OMEGA_EGTS GUI
from typing import Optional
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
        self._cards = {}  # card_id -> (row, col, row_span, col_span)
        self.setAcceptDrops(True)

    def add_card(self, card: BaseCard, row: int = 0, col: int = 0, row_span: Optional[int] = None, col_span: Optional[int] = None):
        """Add a card to the dashboard at the specified grid position."""
        card_id = card.card_id
        
        # Check if card already exists
        if card_id in self._cards:
            # Just move to new position
            self.move_card(card_id, row, col, row_span, col_span)
            return
        
        card.setParent(self)
        card.show()
        
        # Use card's grid size if not specified
        if row_span is None or col_span is None:
            row_span, col_span = card.grid_size
        
        self._grid.addWidget(card, row, col, row_span, col_span)
        self._cards[card_id] = (row, col, row_span, col_span)
        
        card.destroyed.connect(lambda: self._on_card_destroyed(card_id))
        card.drag_started.connect(lambda: self._on_drag_start(card))
        card.grid_size_changed.connect(lambda rs, cs: self._on_grid_size_changed(card, rs, cs))
        
        self.cards_changed.emit()

    def _on_card_destroyed(self, card_id: str):
        """Handle card destruction."""
        if card_id in self._cards:
            del self._cards[card_id]
            self.cards_changed.emit()

    def remove_card(self, card_id: str):
        """Remove a card from the dashboard."""
        if card_id not in self._cards:
            return
        # Find the card widget
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                self._grid.removeWidget(card)
                card.setParent(None)
                break
        del self._cards[card_id]
        self.cards_changed.emit()

    def move_card(self, card_id: str, new_row: int, new_col: int, new_row_span: Optional[int] = None, new_col_span: Optional[int] = None):
        """Move a card to a new grid position."""
        if card_id not in self._cards:
            return
        # Find the card widget
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                old_row_span, old_col_span = self._cards[card_id][2], self._cards[card_id][3]
                row_span = new_row_span if new_row_span is not None else old_row_span
                col_span = new_col_span if new_col_span is not None else old_col_span
                self._grid.removeWidget(card)
                self._grid.addWidget(card, new_row, new_col, row_span, col_span)
                self._cards[card_id] = (new_row, new_col, row_span, col_span)
                self.cards_changed.emit()
                break

    def resize_card(self, card_id: str, row_span: int, col_span: int):
        """Resize a card in the grid."""
        if card_id not in self._cards:
            return
        row, col = self._cards[card_id][0], self._cards[card_id][1]
        # Find the card widget
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                self._grid.removeWidget(card)
                self._grid.addWidget(card, row, col, row_span, col_span)
                self._cards[card_id] = (row, col, row_span, col_span)
                self.cards_changed.emit()
                break

    def _on_grid_size_changed(self, card: BaseCard, row_span: int, col_span: int):
        """Handle card grid size change."""
        card_id = card.card_id
        if card_id in self._cards:
            row, col = self._cards[card_id][0], self._cards[card_id][1]
            self._grid.removeWidget(card)
            self._grid.addWidget(card, row, col, row_span, col_span)
            self._cards[card_id] = (row, col, row_span, col_span)
            self.cards_changed.emit()

    def _on_drag_start(self, card: BaseCard):
        """Handle drag start."""
        pass

    def get_layout_snapshot(self):
        """Return the current layout as a list of dicts with card_id."""
        return [
            {"card_id": cid, "row": r, "col": c, "row_span": rs, "col_span": cs}
            for cid, (r, c, rs, cs) in self._cards.items()
        ]

    def apply_layout_snapshot(self, snapshot: list[dict]):
        """Apply a layout snapshot without removing existing cards."""
        for item in snapshot:
            card_id = item.get("card_id")
            if card_id is None:
                continue
            row = item.get("row", 0)
            col = item.get("col", 0)
            row_span = item.get("row_span", 1)
            col_span = item.get("col_span", 1)
            
            # Find and update existing card
            if card_id in self._cards:
                self.move_card(card_id, row, col, row_span, col_span)
            # Otherwise card will be added at default position by caller
        
        self.cards_changed.emit()

    def has_card(self, card_id: str) -> bool:
        """Check if a card exists in the container."""
        return card_id in self._cards

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
            card_id = event.mimeData().text()
        except ValueError:
            return
        
        # Find the card and move it to the drop position
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                pos = event.position().toPoint()
                # Calculate grid position accounting for gaps
                cell_width = (self.width() - (GRID_COLS - 1) * GRID_GAP) / GRID_COLS
                cell_height = (self.height() - (GRID_ROWS - 1) * GRID_GAP) / GRID_ROWS
                new_col = max(0, min(GRID_COLS - 1, int(pos.x() / cell_width)))
                new_row = max(0, min(GRID_ROWS - 1, int(pos.y() / cell_height)))
                self.move_card(card_id, new_row, new_col)
                break
        event.acceptProposedAction()