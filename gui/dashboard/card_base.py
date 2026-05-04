# OMEGA_EGTS GUI
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QMimeData, QObject, QSize, QRect
from PySide6.QtGui import QDrag
from enum import Enum


class DisplayState(Enum):
    COMPACT = "compact"
    EXPANDED = "expanded"


class BaseCard(QFrame):
    collapse_toggled = Signal(bool)
    drag_started = Signal()
    grid_size_changed = Signal(int, int)  # row_span, col_span

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._collapsed = False
        self._display_state = DisplayState.EXPANDED
        self._row_span = 4  # Default expanded size: 4x4
        self._col_span = 4
        self.setFrameStyle(QFrame.Box)
        self.setMinimumSize(100, 60)
        self._init_ui()
        # Animation removed - use grid size change for visual feedback

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # TitleBar
        self._title_bar = QFrame()
        self._title_bar.setFixedHeight(32)
        self._title_bar.setCursor(Qt.CursorShape.OpenHandCursor)
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(8, 4, 8, 4)
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet("font-weight: bold;")
        title_layout.addWidget(self._title_label)
        title_layout.addStretch()
        self._collapse_btn = QToolButton()
        self._collapse_btn.setText("\u25BC")
        self._collapse_btn.setFixedSize(20, 20)
        self._collapse_btn.clicked.connect(self.toggle_collapse)
        title_layout.addWidget(self._collapse_btn)

        # Content area
        self._content = QFrame()
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)

        main_layout.addWidget(self._title_bar)
        main_layout.addWidget(self._content)

        # Drag support
        self._title_bar.mousePressEvent = self._title_mouse_press
        self._title_bar.mouseDoubleClickEvent = self._title_double_click

    def finish_init(self):
        """Call after subclass has created all content widgets."""
        self.update_content_visibility(self._display_state)

    def set_content_widget(self, widget):
        self._content_layout.addWidget(widget)

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value
        self._title_label.setText(value)

    @property
    def grid_size(self):
        return (self._row_span, self._col_span)

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
            # Collapsed: 2x1 in grid
            self.set_grid_size(2, 1)

    def expand(self):
        if self._collapsed:
            self._collapsed = False
            self.update_content_visibility(DisplayState.EXPANDED)
            self._collapse_btn.setText("\u25BC")
            self.collapse_toggled.emit(False)
            # Expanded: 4x4 in grid
            self.set_grid_size(4, 4)

    def resizeEvent(self, event):
        w = event.size().width()
        if w < 320 and self._display_state != DisplayState.COMPACT:
            self._set_display_state(DisplayState.COMPACT)
        elif w >= 600 and self._display_state != DisplayState.EXPANDED:
            self._set_display_state(DisplayState.EXPANDED)
        super().resizeEvent(event)

    def _set_display_state(self, state):
        self._display_state = state
        self.update_content_visibility(state)

    def update_content_visibility(self, state):
        """Update content based on display state. Override in child classes."""
        pass

    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit()
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(id(self)))
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)

    def _title_double_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_collapse()
