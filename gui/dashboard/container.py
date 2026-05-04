# OMEGA_EGTS GUI
from PySide6.QtWidgets import QWidget, QFrame
from PySide6.QtCore import Signal, Qt, QRect, QPoint
from gui.dashboard.card_base import BaseCard


GRID_ROWS = 8
GRID_COLS = 8
GRID_GAP = 6


class DashboardContainer(QWidget):
    cards_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = []  # list of (card: BaseCard, row: int, col: int, row_span: int, col_span: int)
        self._drag_card = None
        self._drag_start_pos = None
        self._drag_start_geometry = None
        self.setAcceptDrops(True)

    def add_card(self, card: BaseCard, row: int = 0, col: int = 0, row_span: int = None, col_span: int = None):
        """Add a card to the dashboard at the specified grid position."""
        card.setParent(self)
        card.show()
        # Use card's grid size if not specified
        if row_span is None or col_span is None:
            row_span, col_span = card.grid_size
        self._cards.append((card, row, col, row_span, col_span))
        card.destroyed.connect(lambda: self._on_card_destroyed(card))
        card.drag_started.connect(lambda: self._on_drag_start(card))
        card.grid_size_changed.connect(lambda rs, cs: self._on_grid_size_changed(card, rs, cs))
        self._position_card(card, row, col, row_span, col_span)
        self.cards_changed.emit()

    def _on_card_destroyed(self, card):
        self._cards = [(c, r, col, rs, cs) for c, r, col, rs, cs in self._cards if c != card]
        self.cards_changed.emit()

    def _on_drag_start(self, card):
        self._drag_card = card
        self._drag_start_pos = card.pos()
        self._drag_start_geometry = card.geometry()

    def _on_grid_size_changed(self, card, row_span, col_span):
        for i, (c, r, col, rs, cs) in enumerate(self._cards):
            if c == card:
                self._cards[i] = (c, r, col, row_span, col_span)
                self._position_card(c, r, col, row_span, col_span)
                self.cards_changed.emit()
                break

    def _position_card(self, card, row, col, row_span, col_span):
        """Position a card at the specified grid cell with given spans."""
        cell_w = (self.width() - GRID_GAP * (GRID_COLS + 1)) // GRID_COLS
        cell_h = (self.height() - GRID_GAP * (GRID_ROWS + 1)) // GRID_ROWS
        x = GRID_GAP + col * (cell_w + GRID_GAP)
        y = GRID_GAP + row * (cell_h + GRID_GAP)
        w = col_span * cell_w + (col_span - 1) * GRID_GAP
        h = row_span * cell_h + (row_span - 1) * GRID_GAP
        card.setGeometry(QRect(x, y, w, h))

    def _snap_to_grid(self, pos: QPoint) -> tuple:
        """Snap a position to the nearest grid cell."""
        cell_w = (self.width() - GRID_GAP * (GRID_COLS + 1)) // GRID_COLS
        cell_h = (self.height() - GRID_GAP * (GRID_ROWS + 1)) // GRID_ROWS
        col = max(0, min(GRID_COLS - 1, (pos.x() - GRID_GAP) // (cell_w + GRID_GAP)))
        row = max(0, min(GRID_ROWS - 1, (pos.y() - GRID_GAP) // (cell_h + GRID_GAP)))
        return (row, col)

    def _grid_pos_to_point(self, row, col) -> QPoint:
        """Convert grid position to widget point."""
        cell_w = (self.width() - GRID_GAP * (GRID_COLS + 1)) // GRID_COLS
        cell_h = (self.height() - GRID_GAP * (GRID_ROWS + 1)) // GRID_ROWS
        x = GRID_GAP + col * (cell_w + GRID_GAP)
        y = GRID_GAP + row * (cell_h + GRID_GAP)
        return QPoint(x, y)

    def move_card(self, card, new_row, new_col):
        """Move a card to a new grid position."""
        for i, (c, r, col, rs, cs) in enumerate(self._cards):
            if c == card:
                self._cards[i] = (c, new_row, new_col, rs, cs)
                self._position_card(c, new_row, new_col, rs, cs)
                self.cards_changed.emit()
                break

    def get_layout_snapshot(self):
        """Return the current layout as a list of dicts."""
        return [
            {"id": id(c), "row": r, "col": col, "row_span": rs, "col_span": cs}
            for c, r, col, rs, cs in self._cards
        ]

    def find_card_by_id(self, card_id: int):
        """Find a card by its id."""
        for c, r, col, rs, cs in self._cards:
            if id(c) == card_id:
                return c
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reposition all cards
        for card, row, col, row_span, col_span in self._cards:
            self._position_card(card, row, col, row_span, col_span)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and self._drag_card:
            pos = event.position().toPoint()
            row, col = self._snap_to_grid(pos)
            # Show preview position - could add visual feedback here
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not event.mimeData().hasText():
            return
        try:
            card_id = int(event.mimeData().text())
        except ValueError:
            return
        card = self.find_card_by_id(card_id)
        if not card:
            return
        pos = event.position().toPoint()
        row, col = self._snap_to_grid(pos)
        self.move_card(card, row, col)
        event.acceptProposedAction()
