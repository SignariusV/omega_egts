# OMEGA_EGTS GUI
from __future__ import annotations

from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, Signal, QMimeData, QEvent, QObject
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy, QMenu, QStackedWidget

from gui.dashboard.layout_engine import GRID_COLS, GRID_ROWS, GRID_GAP, cell_size

COMPACT_GRID_SIZE = (1, 2)
EXPANDED_GRID_SIZE = (4, 4)
COMPACT_THRESHOLD = 320
EXPANDED_THRESHOLD = 600


class DisplayState(Enum):
    COMPACT = "compact"
    EXPANDED = "expanded"


class _TitleBarEventFilter(QObject):
    def __init__(self, card: BaseCard):
        super().__init__(card)
        self._card = card

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.LeftButton:
                self._card._title_mouse_press(event)
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.LeftButton:
                self._card._title_double_click(event)
        return super().eventFilter(obj, event)


class _GripEventFilter(QObject):
    def __init__(self, card: BaseCard, grip: QFrame):
        super().__init__(grip)
        self._card = card
        self._grip = grip

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            assert isinstance(event, QMouseEvent)
            self._card._grip_mouse_press(event, self._grip)
        elif event.type() == QEvent.Type.MouseMove:
            assert isinstance(event, QMouseEvent)
            self._card._grip_mouse_move(event, self._grip)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            assert isinstance(event, QMouseEvent)
            self._card._grip_mouse_release(event, self._grip)
        return super().eventFilter(obj, event)


_GRIP_POSITIONS = {
    Qt.Corner.TopLeftCorner: lambda w, h, gw, gh: (0, 0),
    Qt.Corner.TopRightCorner: lambda w, h, gw, gh: (w - gw, 0),
    Qt.Corner.BottomLeftCorner: lambda w, h, gw, gh: (0, h - gh),
    Qt.Corner.BottomRightCorner: lambda w, h, gw, gh: (w - gw, h - gh),
}


class BaseCard(QFrame):
    """Base class for dashboard cards with compact/expanded views."""

    collapse_toggled = Signal(bool)
    drag_started = Signal()
    grid_size_changed = Signal(int, int)
    grid_geometry_changed = Signal(int, int, int, int)
    card_visibility_changed = Signal(bool)

    def __init__(self, title: str, card_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._card_id = card_id or title.lower().replace(" ", "_")
        self._collapsed = False
        self._display_state = DisplayState.EXPANDED
        self._row_span = EXPANDED_GRID_SIZE[0]
        self._col_span = EXPANDED_GRID_SIZE[1]
        self._grid_row = 0
        self._grid_col = 0
        self._in_state_change = False
        self._resizing = False
        self._stack: Optional[QStackedWidget] = None
        self.setProperty("class", "CardWidget")
        self.setMinimumSize(240, 100)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._title_bar = QFrame()
        self._title_bar.setProperty("class", "TitleBar")
        self._title_bar.setFixedHeight(32)
        self._title_bar.setCursor(Qt.CursorShape.OpenHandCursor)
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(16, 4, 16, 4)
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("titleLabel")
        title_layout.addWidget(self._title_label)
        title_layout.addStretch()
        self._collapse_btn = QToolButton()
        self._collapse_btn.setObjectName("collapseButton")
        self._collapse_btn.setText("\u25BC")
        self._collapse_btn.setFixedSize(20, 20)
        self._collapse_btn.clicked.connect(self.toggle_collapse)
        title_layout.addWidget(self._collapse_btn)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout.addWidget(self._title_bar)
        main_layout.addWidget(self._stack)

        self._grips: list[QFrame] = []
        for edge in [Qt.Corner.TopLeftCorner, Qt.Corner.TopRightCorner,
                     Qt.Corner.BottomLeftCorner, Qt.Corner.BottomRightCorner]:
            grip = QFrame(self)
            grip.setObjectName("resizeGrip")
            grip.setFixedSize(10, 10)
            is_diag = edge in (Qt.Corner.TopLeftCorner, Qt.Corner.BottomRightCorner)
            grip.setCursor(Qt.CursorShape.SizeFDiagCursor if is_diag else Qt.CursorShape.SizeBDiagCursor)
            grip.edge = edge
            grip.setToolTip("Drag to resize card")
            grip.raise_()
            grip.installEventFilter(_GripEventFilter(self, grip))
            self._grips.append(grip)

        self._reposition_grips()

        self._title_bar.installEventFilter(_TitleBarEventFilter(self))

    def finish_init(self):
        """Call after subclass has created all content widgets."""
        self.update_content_visibility(self._display_state)

    def set_views(self, compact_widget, expanded_widget):
        """Set both compact and expanded widgets."""
        while self._stack.count():
            self._stack.removeWidget(self._stack.widget(0))
        self._stack.addWidget(compact_widget)
        self._stack.addWidget(expanded_widget)

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str):
        self._title = value
        self._title_label.setText(value)

    @property
    def card_id(self) -> str:
        return self._card_id

    @property
    def grid_size(self) -> tuple[int, int]:
        return (self._row_span, self._col_span)

    @property
    def grid_position(self) -> tuple[int, int]:
        return (self._grid_row, self._grid_col)

    def set_grid_position(self, row: int, col: int):
        self._grid_row = row
        self._grid_col = col

    def set_grid_size(self, row_span: int, col_span: int):
        self._row_span = max(1, row_span)
        self._col_span = max(1, col_span)
        self.grid_size_changed.emit(self._row_span, self._col_span)

    def toggle_collapse(self):
        if self._collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        self._apply_collapse_state(
            collapsed=True,
            state=DisplayState.COMPACT,
            grid_size=COMPACT_GRID_SIZE,
            arrow="\u25B2",
        )

    def expand(self):
        self._apply_collapse_state(
            collapsed=False,
            state=DisplayState.EXPANDED,
            grid_size=EXPANDED_GRID_SIZE,
            arrow="\u25BC",
        )

    def set_display_state(self, state: DisplayState):
        """Set display state without triggering collapse/expand side effects."""
        self._display_state = state
        self._collapsed = state == DisplayState.COMPACT
        self.update_content_visibility(state)

    def _apply_collapse_state(self, collapsed: bool, state: DisplayState,
                              grid_size: tuple[int, int], arrow: str):
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._display_state = state
        self.update_content_visibility(state)
        self._collapse_btn.setText(arrow)
        self.collapse_toggled.emit(collapsed)
        self.set_grid_size(*grid_size)

    def update_content_visibility(self, state: DisplayState):
        """Switch stack index based on display state."""
        self._display_state = state
        self._collapsed = state == DisplayState.COMPACT
        self._stack.setCurrentIndex(0 if state == DisplayState.COMPACT else 1)

    def _title_mouse_press(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit()
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self._card_id)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)

    def _title_double_click(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_collapse()

    def resizeEvent(self, event):
        w = event.size().width()
        if self._in_state_change:
            super().resizeEvent(event)
            self._reposition_grips()
            return

        if w < COMPACT_THRESHOLD and self._display_state != DisplayState.COMPACT:
            self._in_state_change = True
            self._apply_collapse_state(
                collapsed=True,
                state=DisplayState.COMPACT,
                grid_size=COMPACT_GRID_SIZE,
                arrow="\u25B2",
            )
            self._in_state_change = False
        elif w >= EXPANDED_THRESHOLD and self._display_state != DisplayState.EXPANDED:
            self._in_state_change = True
            self._apply_collapse_state(
                collapsed=False,
                state=DisplayState.EXPANDED,
                grid_size=EXPANDED_GRID_SIZE,
                arrow="\u25BC",
            )
            self._in_state_change = False

        super().resizeEvent(event)
        self._reposition_grips()

    def _reposition_grips(self):
        """Reposition resize grips at card corners."""
        w = self.width()
        h = self.height()
        for grip in self._grips:
            gw, gh = grip.width(), grip.height()
            pos_fn = _GRIP_POSITIONS.get(grip.edge)
            if pos_fn:
                grip.move(*pos_fn(w, h, gw, gh))

    def _grip_mouse_press(self, event: QMouseEvent, grip: QFrame):
        if event.button() == Qt.MouseButton.LeftButton:
            self._resize_start_pos = event.globalPosition().toPoint()
            self._resize_edge = grip.edge
            self._resize_start_row_span = self._row_span
            self._resize_start_col_span = self._col_span
            self._resize_start_row = self._grid_row
            self._resize_start_col = self._grid_col
            self._resizing = True
            grip.grabMouse()

    def _grip_mouse_move(self, event: QMouseEvent, grip: QFrame):
        if not self._resizing:
            return

        parent = self.parent()
        if not parent:
            return

        cell_w, cell_h = cell_size(parent.width(), parent.height())
        delta = event.globalPosition().toPoint() - self._resize_start_pos
        edge = self._resize_edge

        delta_cols = round(delta.x() / (cell_w + GRID_GAP))
        delta_rows = round(delta.y() / (cell_h + GRID_GAP))

        new_col_span = self._resize_start_col_span
        new_row_span = self._resize_start_row_span
        new_col = self._resize_start_col
        new_row = self._resize_start_row

        if edge == Qt.Corner.BottomRightCorner:
            new_col_span += delta_cols
            new_row_span += delta_rows
        elif edge == Qt.Corner.TopRightCorner:
            new_col_span += delta_cols
            new_row_span -= delta_rows
            new_row += delta_rows
        elif edge == Qt.Corner.BottomLeftCorner:
            new_col_span -= delta_cols
            new_col += delta_cols
            new_row_span += delta_rows
        elif edge == Qt.Corner.TopLeftCorner:
            new_col_span -= delta_cols
            new_col += delta_cols
            new_row_span -= delta_rows
            new_row += delta_rows

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

    def _grip_mouse_release(self, event: QMouseEvent, grip: QFrame):
        grip.releaseMouse()
        self._resizing = False
        for attr in ('_resize_start_pos', '_resize_edge',
                     '_resize_start_row_span', '_resize_start_col_span',
                     '_resize_start_row', '_resize_start_col'):
            if hasattr(self, attr):
                delattr(self, attr)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        action_text = "Expand" if self._collapsed else "Collapse"
        action_handler = self.expand if self._collapsed else self.collapse
        action_tooltip = "Expand card to show full content" if self._collapsed else "Collapse card to compact view"
        self._add_menu_action(menu, action_text, action_handler, action_tooltip)

        menu.addSeparator()
        self._add_menu_action(menu, "Reset Settings", self._on_reset_settings,
                              "Reset card to default state")

        menu.addSeparator()
        self._add_menu_action(menu, "Close", self.hide, "Hide this card")

        menu.exec(self.mapToGlobal(pos))

    @staticmethod
    def _add_menu_action(menu: QMenu, text: str, handler, tooltip: str):
        action = menu.addAction(text)
        action.triggered.connect(handler)
        action.setToolTip(tooltip)

    def _on_reset_settings(self):
        """Reset card to default state. Override in subclasses."""
        self.expand()

    def setVisible(self, visible: bool):
        super().setVisible(visible)
        self.card_visibility_changed.emit(visible)

    def show(self):
        super().show()

    def hide(self):
        super().hide()
