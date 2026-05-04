# OMEGA_EGTS GUI
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, Qt
from gui.dashboard.card_base import BaseCard
from gui.dashboard.layout_engine import GRID_ROWS, GRID_COLS, GRID_GAP, cell_size, grid_position


class DashboardContainer(QWidget):
    cards_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = {}  # card_id -> (row, col, row_span, col_span)
        self.setAcceptDrops(True)

    def add_card(self, card: BaseCard, row: int = 0, col: int = 0, row_span: Optional[int] = None, col_span: Optional[int] = None):
        """Add a card to the dashboard at the specified grid position."""
        card_id = card.card_id
        
        if card_id in self._cards:
            self.move_card(card_id, row, col, row_span, col_span)
            return
        
        card.setParent(self)
        
        if row_span is None or col_span is None:
            row_span, col_span = card.grid_size
        
        self._cards[card_id] = (row, col, row_span, col_span)
        
        card.destroyed.connect(lambda: self._on_card_destroyed(card_id))
        card.drag_started.connect(lambda: self._on_drag_start(card))
        card.grid_size_changed.connect(lambda rs, cs: self._on_grid_size_changed(card, rs, cs))
        
        self._update_card_geometry(card)
        card.show()
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
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                card.setParent(None)
                break
        del self._cards[card_id]
        self.cards_changed.emit()

    def move_card(self, card_id: str, new_row: int, new_col: int, new_row_span: Optional[int] = None, new_col_span: Optional[int] = None):
        """Move a card to a new grid position."""
        if card_id not in self._cards:
            return
        
        old_row, old_col, old_row_span, old_col_span = self._cards[card_id]
        row_span = new_row_span if new_row_span is not None else old_row_span
        col_span = new_col_span if new_col_span is not None else old_col_span
        
        if not self._is_area_free(new_row, new_col, row_span, col_span, card_id):
            return
        
        self._cards[card_id] = (new_row, new_col, row_span, col_span)
        
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                self._update_card_geometry(card)
                break
        
        self.cards_changed.emit()

    def resize_card(self, card_id: str, row_span: int, col_span: int):
        """Resize a card in the grid."""
        if card_id not in self._cards:
            return
        row, col = self._cards[card_id][0], self._cards[card_id][1]
        
        if not self._is_area_free(row, col, row_span, col_span, card_id):
            return
        
        self._cards[card_id] = (row, col, row_span, col_span)
        
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                self._update_card_geometry(card)
                break
        
        self.cards_changed.emit()

    def _on_grid_size_changed(self, card: BaseCard, row_span: int, col_span: int):
        """Handle card grid size change."""
        card_id = card.card_id
        if card_id in self._cards:
            row, col = self._cards[card_id][0], self._cards[card_id][1]
            
            if not self._is_area_free(row, col, row_span, col_span, card_id):
                return
            
            self._cards[card_id] = (row, col, row_span, col_span)
            self._update_card_geometry(card)
            self.cards_changed.emit()

    def _on_drag_start(self, card: BaseCard):
        """Handle drag start."""
        pass

    def _is_area_free(self, row: int, col: int, row_span: int, col_span: int, exclude_card_id: str = None) -> bool:
        """Check if grid area is free (no overlap with other cards)."""
        for cid, (r, c, rs, cs) in self._cards.items():
            if cid == exclude_card_id:
                continue
            if not (col + col_span <= c or col >= c + cs or row + row_span <= r or row >= r + rs):
                return False
        return True

    def _update_card_geometry(self, card: BaseCard):
        """Update card geometry based on its grid position."""
        card_id = card.card_id
        if card_id not in self._cards:
            return
        
        row, col, row_span, col_span = self._cards[card_id]
        
        cell_w, cell_h = cell_size(self.width(), self.height())
        
        x = col * (cell_w + GRID_GAP)
        y = row * (cell_h + GRID_GAP)
        width = col_span * cell_w + (col_span - 1) * GRID_GAP
        height = row_span * cell_h + (row_span - 1) * GRID_GAP
        
        card.setGeometry(x, y, width, height)

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
            
            if card_id in self._cards:
                self.move_card(card_id, row, col, row_span, col_span)
        
        self.cards_changed.emit()

    def has_card(self, card_id: str) -> bool:
        """Check if a card exists in the container."""
        return card_id in self._cards

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for card in self.findChildren(BaseCard):
            self._update_card_geometry(card)

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
        
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                pos = event.position().toPoint()
                row, col = grid_position(pos.x(), pos.y(), self.width(), self.height())
                self.move_card(card_id, row, col)
                break
        event.acceptProposedAction()