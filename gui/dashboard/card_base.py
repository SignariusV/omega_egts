# OMEGA_EGTS GUI
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QMimeData, QObject, QSize, QPoint, QRect
from PySide6.QtGui import QDrag
from enum import Enum


CARD_MIN_SIZE = QSize(240, 100)
RESIZE_THRESHOLD = QSize(5, 5)

TOP_LEFT = int(Qt.Corner.TopLeftCorner)
TOP_RIGHT = int(Qt.Corner.TopRightCorner)
BOTTOM_LEFT = int(Qt.Corner.BottomLeftCorner)
BOTTOM_RIGHT = int(Qt.Corner.BottomRightCorner)


class DisplayState(Enum):
    COMPACT = "compact"
    EXPANDED = "expanded"


class TitleBar(QFrame):
    title_pressed = Signal(object)
    title_double_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        self.title_pressed.emit(event)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.title_double_clicked.emit(event)
        super().mouseDoubleClickEvent(event)


class ResizeGrip(QFrame):
    grip_pressed = Signal(object)
    grip_moved = Signal(object)
    grip_released = Signal(object)

    def __init__(self, edge, parent=None):
        super().__init__(parent)
        self.edge = int(edge)  # store as int
        self.setFixedSize(8, 8)
        self.setStyleSheet("background: transparent;")
        if self.edge in (TOP_LEFT, BOTTOM_RIGHT):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)

    def mousePressEvent(self, event):
        self.grip_pressed.emit(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.grip_moved.emit(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.grip_released.emit(event)
        super().mouseReleaseEvent(event)


class BaseCard(QFrame):
    collapse_toggled = Signal(bool)
    drag_started = Signal()
    resize_started = Signal(int)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._collapsed = False
        self._display_state = DisplayState.EXPANDED
        self.setFrameStyle(QFrame.Box)
        self.setMinimumSize(240, 100)
        self._init_ui()
        self._anim = QPropertyAnimation(self._content, b"maximumHeight")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._title_bar = TitleBar()
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

        self._content = QFrame()
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)

        main_layout.addWidget(self._title_bar)
        main_layout.addWidget(self._content)

        self._title_bar.title_pressed.connect(self._on_title_press)
        self._title_bar.title_double_clicked.connect(self._on_title_double_click)

        self._grips = []
        for edge in [Qt.Corner.TopLeftCorner, Qt.Corner.TopRightCorner, Qt.Corner.BottomLeftCorner, Qt.Corner.BottomRightCorner]:
            grip = ResizeGrip(edge, self)
            grip.grip_pressed.connect(self._on_grip_press)
            grip.grip_moved.connect(self._on_grip_move)
            grip.grip_released.connect(self._on_grip_release)
            self._grips.append(grip)

        self._resize_start_geometry = None
        self._resize_start_pos = None
        self._resize_active = False

    def set_content_widget(self, widget):
        self._content_layout.addWidget(widget)

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value
        self._title_label.setText(value)

    def toggle_collapse(self):
        if self._collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        if not self._collapsed:
            self._anim.setStartValue(self._content.height())
            self._anim.setEndValue(0)
            self._anim.start()
            self._collapsed = True
            self._collapse_btn.setText("\u25B2")
            self.collapse_toggled.emit(True)

    def expand(self):
        if self._collapsed:
            hint = self._content.sizeHint().height()
            self._anim.setStartValue(0)
            self._anim.setEndValue(hint)
            self._anim.start()
            self._collapsed = False
            self._collapse_btn.setText("\u25BC")
            self.collapse_toggled.emit(False)

    def resizeEvent(self, event):
        w = event.size().width()
        if w < 320 and self._display_state != DisplayState.COMPACT:
            self._set_display_state(DisplayState.COMPACT)
        elif w >= 600 and self._display_state != DisplayState.EXPANDED:
            self._set_display_state(DisplayState.EXPANDED)
        super().resizeEvent(event)
        self._reposition_grips()

    def _set_display_state(self, state):
        self._display_state = state
        self.update_content_visibility(state)

    def update_content_visibility(self, state):
        pass

    def _reposition_grips(self):
        w = self.width()
        h = self.height()
        for grip in self._grips:
            if grip.edge == TOP_LEFT:
                grip.move(0, 0)
            elif grip.edge == TOP_RIGHT:
                grip.move(w - 8, 0)
            elif grip.edge == BOTTOM_LEFT:
                grip.move(0, h - 8)
            else:
                grip.move(w - 8, h - 8)

    def _on_title_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit()
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(id(self)))
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)

    def _on_title_double_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_collapse()

    def _on_grip_press(self, event):
        grip = self.sender()
        if isinstance(grip, ResizeGrip) and event.button() == Qt.MouseButton.LeftButton:
            self._resize_start_geometry = self.geometry()
            self._resize_start_pos = event.globalPosition().toPoint()
            self._resize_active = False
            # Clear any fixed size so resizing works
            self.setMinimumSize(240, 100)
            self.setMaximumSize(16777215, 16777215)  # Qt's QWIDGETSIZE_MAX
            self.resize_started.emit(grip.edge)

    def _on_grip_move(self, event):
        if self._resize_start_pos is not None:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            if not self._resize_active:
                if abs(delta.x()) < RESIZE_THRESHOLD.width() and abs(delta.y()) < RESIZE_THRESHOLD.height():
                    return
                self._resize_active = True
            grip = self.sender()
            if isinstance(grip, ResizeGrip):
                edge = grip.edge
                new_geo = QRect(self._resize_start_geometry)
                if edge in (TOP_LEFT, BOTTOM_LEFT):
                    new_left = max(CARD_MIN_SIZE.width(), new_geo.left() + delta.x())
                    new_geo.setLeft(new_left)
                if edge in (TOP_RIGHT, BOTTOM_RIGHT):
                    new_right = max(CARD_MIN_SIZE.width(), new_geo.right() + delta.x())
                    new_geo.setRight(new_right)
                if edge in (TOP_LEFT, TOP_RIGHT):
                    new_top = max(CARD_MIN_SIZE.height(), new_geo.top() + delta.y())
                    new_geo.setTop(new_top)
                if edge in (BOTTOM_LEFT, BOTTOM_RIGHT):
                    new_bottom = max(CARD_MIN_SIZE.height(), new_geo.bottom() + delta.y())
                    new_geo.setBottom(new_bottom)
                self.setGeometry(new_geo)
                # Fix the size so layout doesn't override
                new_size = new_geo.size()
                if edge in (TOP_LEFT, BOTTOM_LEFT, TOP_RIGHT, BOTTOM_RIGHT):
                    if edge in (TOP_LEFT, BOTTOM_LEFT, TOP_RIGHT, BOTTOM_RIGHT):
                        # Determine which dimensions changed
                        if edge in (TOP_LEFT, BOTTOM_LEFT, TOP_RIGHT, BOTTOM_RIGHT):
                            if edge in (TOP_LEFT, BOTTOM_LEFT, TOP_RIGHT, BOTTOM_RIGHT):
                                pass  # We'll set min/max for both dimensions for simplicity
                self.setMinimumSize(new_size)
                self.setMaximumSize(new_size)

    def _on_grip_release(self, event):
        self._resize_start_pos = None
        self._resize_active = False
        self._reposition_grips()
