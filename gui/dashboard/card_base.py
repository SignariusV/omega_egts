# OMEGA_EGTS GUI
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy, QMenu, QStackedWidget, QWidget
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag
from enum import Enum

from gui.dashboard.layout_engine import GRID_COLS, GRID_ROWS, GRID_GAP, cell_size

# Grid constants - now imported from layout_engine


class DisplayState(Enum):
    COMPACT = "compact"
    EXPANDED = "expanded"


class BaseCard(QFrame):
    """Base class for dashboard cards with compact/expanded views."""
    
    collapse_toggled = Signal(bool)
    drag_started = Signal()
    grid_size_changed = Signal(int, int)  # row_span, col_span
    grid_geometry_changed = Signal(int, int, int, int)  # row, col, row_span, col_span

    def __init__(self, title: str, card_id: str = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._card_id = card_id or title.lower().replace(" ", "_")
        self._collapsed = False
        self._display_state = DisplayState.EXPANDED
        self._row_span = 4  # Default expanded size: 4x4
        self._col_span = 4
        self._grid_row = 0
        self._grid_col = 0
        self._in_state_change = False
        self._stack = None
        self.setFrameStyle(QFrame.Box)
        self.setMinimumSize(240, 100)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # TitleBar
        self._title_bar = QFrame()
        self._title_bar.setFixedHeight(32)
        self._title_bar.setCursor(Qt.CursorShape.OpenHandCursor)
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(8, 4, 8, 4)
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("title")
        self._title_label.setStyleSheet("font-weight: bold;")
        title_layout.addWidget(self._title_label)
        title_layout.addStretch()
        self._collapse_btn = QToolButton()
        self._collapse_btn.setText("\u25BC")
        self._collapse_btn.setFixedSize(20, 20)
        self._collapse_btn.clicked.connect(self.toggle_collapse)
        title_layout.addWidget(self._collapse_btn)

        # Stacked widget for compact/expanded views
        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout.addWidget(self._title_bar)
        main_layout.addWidget(self._stack)

        # Resize handles (4 corners)
        self._grips = []
        for edge in [Qt.Corner.TopLeftCorner, Qt.Corner.TopRightCorner, Qt.Corner.BottomLeftCorner, Qt.Corner.BottomRightCorner]:
            grip = QFrame(self)
            grip.setFixedSize(10, 10)
            grip.setStyleSheet("""
                QFrame {
                    background-color: rgba(0, 120, 215, 30);
                    border: 1px solid rgba(0, 120, 215, 100);
                    border-radius: 2px;
                }
                QFrame:hover {
                    background-color: rgba(0, 120, 215, 80);
                }
            """)
            grip.setCursor(Qt.CursorShape.SizeFDiagCursor if edge in (Qt.Corner.TopLeftCorner, Qt.Corner.BottomRightCorner) else Qt.CursorShape.SizeBDiagCursor)
            grip.edge = edge
            grip.mousePressEvent = lambda event, g=grip: self._grip_mouse_press(event, g)
            grip.mouseMoveEvent = lambda event, g=grip: self._grip_mouse_move(event, g)
            grip.mouseReleaseEvent = lambda event, g=grip: self._grip_mouse_release(event, g)
            grip.setToolTip("Drag to resize card")
            grip.raise_()
            self._grips.append(grip)

        # Initial positioning of grips
        self._reposition_grips()

        # Drag support
        self._title_bar.mousePressEvent = self._title_mouse_press
        self._title_bar.mouseDoubleClickEvent = self._title_double_click

    def finish_init(self):
        """Call after subclass has created all content widgets."""
        self.update_content_visibility(self._display_state)

    def set_views(self, compact_widget, expanded_widget):
        """Set both compact and expanded widgets.
        
        Clears the stack and inserts widgets at indices 0 (compact) and 1 (expanded).
        
        Args:
            compact_widget: QWidget to show in compact mode (index 0)
            expanded_widget: QWidget to show in expanded mode (index 1)
        """
        while self._stack.count() > 0:
            widget = self._stack.widget(0)
            self._stack.removeWidget(widget)
            widget.setParent(None)
        self._stack.insertWidget(0, compact_widget)
        self._stack.insertWidget(1, expanded_widget)

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value
        self._title_label.setText(value)

    @property
    def card_id(self) -> str:
        """Unique identifier for this card (used for layout persistence)."""
        return self._card_id

    @property
    def grid_size(self):
        return (self._row_span, self._col_span)

    @property
    def grid_position(self):
        return (self._grid_row, self._grid_col)

    def set_grid_position(self, row: int, col: int):
        """Set the card position in grid cells."""
        self._grid_row = row
        self._grid_col = col

    def set_grid_size(self, row_span: int, col_span: int):
        """Set the card size in grid cells."""
        self._row_span = max(1, row_span)
        self._col_span = max(1, col_span)
        self.grid_size_changed.emit(self._row_span, self._col_span)

    def toggle_collapse(self):
        if self._collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        if not self._collapsed:
            self._collapsed = True
            self.update_content_visibility(DisplayState.COMPACT)
            self._collapse_btn.setText("\u25B2")
            self.collapse_toggled.emit(True)
            self.set_grid_size(1, 2)

    def expand(self):
        if self._collapsed:
            self._collapsed = False
            self.update_content_visibility(DisplayState.EXPANDED)
            self._collapse_btn.setText("\u25BC")
            self.collapse_toggled.emit(False)
            self.set_grid_size(4, 4)

    def _set_display_state(self, state):
        self._display_state = state
        self.update_content_visibility(state)

    def update_content_visibility(self, state):
        """Switch stack index based on display state."""
        if state == DisplayState.COMPACT:
            self._stack.setCurrentIndex(0)
        else:
            self._stack.setCurrentIndex(1)

    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit()
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self._card_id)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)

    def _title_double_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_collapse()

    def resizeEvent(self, event):
        if self._in_state_change:
            super().resizeEvent(event)
            self._reposition_grips()
            return

        w = event.size().width()
        if w < 320 and self._display_state != DisplayState.COMPACT:
            self._in_state_change = True
            self._set_display_state(DisplayState.COMPACT)
            self._in_state_change = False
        elif w >= 600 and self._display_state != DisplayState.EXPANDED:
            self._in_state_change = True
            self._set_display_state(DisplayState.EXPANDED)
            self._in_state_change = False
        super().resizeEvent(event)
        self._reposition_grips()

    def _reposition_grips(self):
        """Reposition resize grips at card corners."""
        w = self.width()
        h = self.height()
        for grip in self._grips:
            if grip.edge == Qt.Corner.TopLeftCorner:
                grip.move(0, 0)
            elif grip.edge == Qt.Corner.TopRightCorner:
                grip.move(w - 8, 0)
            elif grip.edge == Qt.Corner.BottomLeftCorner:
                grip.move(0, h - 8)
            else:  # BottomRightCorner
                grip.move(w - 8, h - 8)

    def _grip_mouse_press(self, event, grip):
        """Handle mouse press on resize grip."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._resize_start_geometry = self.geometry()
            self._resize_start_pos = event.globalPosition().toPoint()
            self._resize_edge = grip.edge
            self._resize_start_row_span = self._row_span
            self._resize_start_col_span = self._col_span
            self._resize_start_row = self._grid_row
            self._resize_start_col = self._grid_col
            grip.grabMouse()

    def _grip_mouse_move(self, event, grip):
        """Handle mouse move on resize grip - snap to grid cells."""
        if not hasattr(self, '_resize_start_pos') or not hasattr(self, '_resize_edge'):
            return

        parent = self.parent()
        if not parent:
            return

        cell_w, cell_h = cell_size(parent.width(), parent.height())

        delta = event.globalPosition().toPoint() - self._resize_start_pos
        edge = self._resize_edge

        new_col_span = self._resize_start_col_span
        new_row_span = self._resize_start_row_span
        new_col = self._resize_start_col
        new_row = self._resize_start_row

        delta_cols = round(delta.x() / (cell_w + GRID_GAP))
        delta_rows = round(delta.y() / (cell_h + GRID_GAP))

        if edge == Qt.Corner.BottomRightCorner:
            new_col_span = self._resize_start_col_span + delta_cols
            new_row_span = self._resize_start_row_span + delta_rows

        elif edge == Qt.Corner.TopRightCorner:
            new_col_span = self._resize_start_col_span + delta_cols
            new_row_span = self._resize_start_row_span - delta_rows
            new_row = self._resize_start_row + delta_rows

        elif edge == Qt.Corner.BottomLeftCorner:
            new_col_span = self._resize_start_col_span - delta_cols
            new_col = self._resize_start_col + delta_cols
            new_row_span = self._resize_start_row_span + delta_rows

        elif edge == Qt.Corner.TopLeftCorner:
            new_col_span = self._resize_start_col_span - delta_cols
            new_col = self._resize_start_col + delta_cols
            new_row_span = self._resize_start_row_span - delta_rows
            new_row = self._resize_start_row + delta_rows

        new_row = max(0, min(new_row, GRID_ROWS - 1))
        new_col = max(0, min(new_col, GRID_COLS - 1))
        new_row_span = max(1, min(GRID_ROWS - new_row, new_row_span))
        new_col_span = max(1, min(GRID_COLS - new_col, new_col_span))

        if (new_row, new_col, new_row_span, new_col_span) != \
           (self._grid_row, self._grid_col, self._row_span, self._col_span):
            self._row_span = new_row_span
            self._col_span = new_col_span
            self._grid_row = new_row
            self._grid_col = new_col
            self.grid_geometry_changed.emit(new_row, new_col, new_row_span, new_col_span)

    def _grip_mouse_release(self, event, grip):
        """Handle mouse release on resize grip - clear state."""
        grip.releaseMouse()
        attrs_to_clear = ['_resize_start_pos', '_resize_edge', '_resize_start_geometry',
                         '_resize_start_row_span', '_resize_start_col_span',
                         '_resize_start_row', '_resize_start_col']
        for attr in attrs_to_clear:
            if hasattr(self, attr):
                delattr(self, attr)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        if self._collapsed:
            expand_action = menu.addAction("Expand")
            expand_action.triggered.connect(self.expand)
            expand_action.setToolTip("Expand card to show full content")
        else:
            collapse_action = menu.addAction("Collapse")
            collapse_action.triggered.connect(self.collapse)
            collapse_action.setToolTip("Collapse card to compact view")
        menu.addSeparator()
        reset_action = menu.addAction("Reset Settings")
        reset_action.triggered.connect(self._on_reset_settings)
        reset_action.setToolTip("Reset card to default state")
        menu.addSeparator()
        close_action = menu.addAction("Close")
        close_action.triggered.connect(self.hide)
        close_action.setToolTip("Hide this card")
        menu.exec(self.mapToGlobal(pos))

    def _on_reset_settings(self):
        """Reset card to default state. Override in subclasses."""
        self.expand()
        self.set_grid_size(4, 4)