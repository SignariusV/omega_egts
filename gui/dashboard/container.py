# OMEGA_EGTS GUI
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, Qt
from gui.dashboard.card_base import BaseCard
from gui.dashboard.layout_engine import GRID_ROWS, GRID_COLS, GRID_GAP, cell_size, grid_position


class DashboardContainer(QWidget):
    cards_changed = Signal()
    card_visibility_changed = Signal(str, bool)   # card_id, visible

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = {}  # card_id -> (row, col, row_span, col_span) for visible cards
        self._hidden_cards = {}  # card_id -> (row, col, row_span, col_span) for hidden cards
        self._processing = False
        self.setAcceptDrops(True)

    def _is_within_grid(self, row: int, col: int, row_span: int, col_span: int) -> bool:
        """Check if position and size are within grid bounds."""
        return (0 <= row < GRID_ROWS and 
                0 <= col < GRID_COLS and 
                row + row_span <= GRID_ROWS and 
                col + col_span <= GRID_COLS)

    def add_card(self, card: BaseCard, row: int = 0, col: int = 0, row_span: Optional[int] = None, col_span: Optional[int] = None):
        """Add a card to the dashboard at the specified grid position."""
        card_id = card.card_id
        
        if card_id in self._hidden_cards:
            # Card is hidden - show it first, then move
            self.show_card(card_id)
            self.move_card(card_id, row, col, row_span, col_span)
            return
        
        if card_id in self._cards:
            self.move_card(card_id, row, col, row_span, col_span)
            return
        
        # First determine real sizes, then check bounds
        if row_span is None or col_span is None:
            row_span, col_span = card.grid_size
        
        if not self._is_within_grid(row, col, row_span, col_span):
            row, col = 0, 0
        
        card.setParent(self)        
        self._cards[card_id] = (row, col, row_span, col_span)
        card.set_grid_position(row, col)        
        card.destroyed.connect(lambda: self._on_card_destroyed(card_id))
        card.drag_started.connect(lambda: self._on_drag_start(card))
        card.grid_size_changed.connect(lambda rs, cs: self._on_grid_size_changed(card, rs, cs))
        card.grid_geometry_changed.connect(lambda r, c, rs, cs: self._on_grid_geometry_changed(card, r, c, rs, cs))
        card.card_visibility_changed.connect(
            lambda visible, cid=card_id: self._on_card_visibility_changed(cid, visible)
        )        
        self._update_card_geometry(card)
        card.setVisible(True)  # Don't trigger card.show/hide methods
        self.card_visibility_changed.emit(card_id, True)
        self.cards_changed.emit()

    def _on_card_destroyed(self, card_id: str):
        """Handle card destruction."""
        if card_id in self._cards:
            del self._cards[card_id]
            self.cards_changed.emit()
        elif card_id in self._hidden_cards:
            del self._hidden_cards[card_id]
            self.cards_changed.emit()

    def remove_card(self, card_id: str):
        """Remove a card from the dashboard."""
        if card_id in self._cards:
            for card in self.findChildren(BaseCard):
                if card.card_id == card_id:
                    card.setParent(None)
                    break
            del self._cards[card_id]
            self.cards_changed.emit()
        elif card_id in self._hidden_cards:
            del self._hidden_cards[card_id]
            self.cards_changed.emit()

    def move_card(self, card_id: str, new_row: int, new_col: int, new_row_span: Optional[int] = None, new_col_span: Optional[int] = None):
        """Move a card to a new grid position."""
        if card_id not in self._cards:
            return
        
        old_row, old_col, old_row_span, old_col_span = self._cards[card_id]
        row_span = new_row_span if new_row_span is not None else old_row_span
        col_span = new_col_span if new_col_span is not None else old_col_span
        
        if not self._is_within_grid(new_row, new_col, row_span, col_span):
            return
        
        if not self._is_area_free(new_row, new_col, row_span, col_span, card_id):
            return
        
        self._cards[card_id] = (new_row, new_col, row_span, col_span)
        
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                card.set_grid_position(new_row, new_col)
                self._update_card_geometry(card)
                break
        
        self.cards_changed.emit()

    def resize_card(self, card_id: str, row_span: int, col_span: int):
        """Resize a card in the grid."""
        if card_id not in self._cards:
            return
        row, col = self._cards[card_id][0], self._cards[card_id][1]
        
        if not self._is_within_grid(row, col, row_span, col_span):
            return
        
        if not self._is_area_free(row, col, row_span, col_span, card_id):
            return
        
        self._cards[card_id] = (row, col, row_span, col_span)
        
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                card.set_grid_position(row, col)
                self._update_card_geometry(card)
                break
        
        self.cards_changed.emit()

    def _on_grid_size_changed(self, card: BaseCard, row_span: int, col_span: int):
        """Handle card grid size change - with sync protection."""
        if self._processing:
            return
        
        card_id = card.card_id
        if card_id not in self._cards:
            return
        
        old_row, old_col, old_row_span, old_col_span = self._cards[card_id]
        
        if not self._is_within_grid(old_row, old_col, row_span, col_span):
            self._revert_card_size(card, old_row_span, old_col_span)
            return
        
        if not self._is_area_free(old_row, old_col, row_span, col_span, card_id):
            self._revert_card_size(card, old_row_span, old_col_span)
            return
        
        self._cards[card_id] = (old_row, old_col, row_span, col_span)
        self._update_card_geometry(card)
        self.cards_changed.emit()

    def _revert_card_size(self, card: BaseCard, row_span: int, col_span: int):
        """Revert card size to previous value."""
        self._processing = True
        card.set_grid_size(row_span, col_span)
        self._processing = False

    def _on_grid_geometry_changed(self, card: BaseCard, row: int, col: int, row_span: int, col_span: int):
        """Handle card grid geometry change (position + size)."""
        if self._processing:
            return
        
        card_id = card.card_id
        if card_id not in self._cards:
            return
        
        if not self._is_within_grid(row, col, row_span, col_span):
            self._revert_card_geometry(card)
            return
        
        if not self._is_area_free(row, col, row_span, col_span, card_id):
            self._revert_card_geometry(card)
            return
        
        self._cards[card_id] = (row, col, row_span, col_span)
        card.set_grid_position(row, col)
        self._update_card_geometry(card)
        self.cards_changed.emit()

    def _revert_card_geometry(self, card: BaseCard):
        """Revert card geometry to previous values."""
        card_id = card.card_id
        if card_id not in self._cards:
            return
        row, col, row_span, col_span = self._cards[card_id]
        self._processing = True
        card.set_grid_position(row, col)
        card.set_grid_size(row_span, col_span)
        self._processing = False

    def _on_drag_start(self, card: BaseCard):
        """Handle drag start - placeholder for future visual feedback."""
        pass

    def _is_area_free(self, row: int, col: int, row_span: int, col_span: int, exclude_card_id: str = None) -> bool:
        """Check if grid area is free (no overlap with other visible cards)."""
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

    def _hide_card(self, card_id: str) -> bool:
        """Hide card and free its grid space."""
        if card_id not in self._cards:
            return False
        # Remember coordinates before removing
        self._hidden_cards[card_id] = self._cards.pop(card_id)
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                card.setVisible(False)  # Don't trigger card.show/hide methods
                break
        self.cards_changed.emit()
        return True

    def _show_card(self, card_id: str) -> bool:
        """Show card and restore to grid (old position or find free spot)."""
        if card_id not in self._hidden_cards:
            return False
        old_row, old_col, row_span, col_span = self._hidden_cards.pop(card_id)
        # Check if old position is free
        if self._is_within_grid(old_row, old_col, row_span, col_span) and \
           self._is_area_free(old_row, old_col, row_span, col_span):
            row, col = old_row, old_col
        else:
            free_spot = self._find_free_spot(row_span, col_span)
            if free_spot is None:
                # No space - put back to hidden
                self._hidden_cards[card_id] = (old_row, old_col, row_span, col_span)
                return False
            row, col = free_spot
        self._cards[card_id] = (row, col, row_span, col_span)
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                card.set_grid_position(row, col)
                card.set_grid_size(row_span, col_span)
                card.setVisible(True)  # Don't trigger card.show/hide methods
                self._update_card_geometry(card)
                break
        self.cards_changed.emit()
        return True

    def _find_free_spot(self, row_span: int, col_span: int) -> tuple[int, int] | None:
        """Find first free rectangle in grid. Returns None if no space."""
        for r in range(GRID_ROWS - row_span + 1):
            for c in range(GRID_COLS - col_span + 1):
                if self._is_area_free(r, c, row_span, col_span):
                    return r, c
        return None

    def _on_card_visibility_changed(self, card_id: str, visible: bool):
        """Handle card visibility change from card's show/hide methods (user action).
        Updates internal state and notifies listeners."""
        if visible:
            # Card was shown by user (context menu) - move from hidden to visible
            if card_id in self._hidden_cards:
                self.show_card(card_id)
        else:
            # Card was hidden by user (context menu) - move from visible to hidden
            if card_id in self._cards:
                self.hide_card(card_id)

    def is_card_visible(self, card_id: str) -> bool:
        """Check if a card is visible."""
        return card_id in self._cards

    def has_card(self, card_id: str) -> bool:
        """Check if a card exists in the container (visible or hidden)."""
        return card_id in self._cards or card_id in self._hidden_cards

    def show_card(self, card_id: str):
        """Show a specific card by ID."""
        if self._show_card(card_id):
            self.card_visibility_changed.emit(card_id, True)

    def hide_card(self, card_id: str):
        """Hide a specific card by ID."""
        if self._hide_card(card_id):
            self.card_visibility_changed.emit(card_id, False)

    def toggle_card_visibility(self, card_id: str):
        """Toggle visibility of a specific card by ID."""
        if card_id in self._hidden_cards:
            self.show_card(card_id)
        elif card_id in self._cards:
            self.hide_card(card_id)

    def get_layout_snapshot(self):
        """Return the current layout as a list of dicts with card_id."""
        return [
            {"card_id": cid, "row": r, "col": c, "row_span": rs, "col_span": cs}
            for cid, (r, c, rs, cs) in self._cards.items()
        ]

    def get_hidden_snapshot(self):
        """Return hidden cards with their stored positions."""
        return [
            {"card_id": cid, "row": r, "col": c, "row_span": rs, "col_span": cs}
            for cid, (r, c, rs, cs) in self._hidden_cards.items()
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
        
        card_id = event.mimeData().text()
        
        for card in self.findChildren(BaseCard):
            if card.card_id == card_id:
                pos = event.position().toPoint()
                row, col = grid_position(pos.x(), pos.y(), self.width(), self.height())
                self.move_card(card_id, row, col)
                break
        event.acceptProposedAction()
