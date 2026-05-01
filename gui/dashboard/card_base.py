# OMEGA_EGTS GUI
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from enum import Enum


class DisplayState(Enum):
    COMPACT = "compact"
    EXPANDED = "expanded"


class BaseCard(QFrame):
    collapse_toggled = Signal(bool)
    drag_started = Signal()
    resize_started = Signal(Qt.Edge)

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

        self._content = QFrame()
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)

        main_layout.addWidget(self._title_bar)
        main_layout.addWidget(self._content)

        self._grips = []
        for edge in [Qt.Corner.TopLeftCorner, Qt.Corner.TopRightCorner, Qt.Corner.BottomLeftCorner, Qt.Corner.BottomRightCorner]:
            grip = QFrame(self)
            grip.setFixedSize(8, 8)
            grip.setStyleSheet("background: transparent;")
            grip.setCursor(Qt.CursorShape.SizeFDiagCursor if edge in (Qt.Corner.TopLeftCorner, Qt.Corner.BottomRightCorner) else Qt.CursorShape.SizeBDiagCursor)
            grip.edge = edge
            grip.mousePressEvent = self._grip_mouse_press
            grip.mouseMoveEvent = self._grip_mouse_move
            self._grips.append(grip)

        self._title_bar.mousePressEvent = self._title_mouse_press
        self._title_bar.mouseMoveEvent = self._title_mouse_move

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
            if grip.edge == Qt.Corner.TopLeftCorner:
                grip.move(0, 0)
            elif grip.edge == Qt.Corner.TopRightCorner:
                grip.move(w - 8, 0)
            elif grip.edge == Qt.Corner.BottomLeftCorner:
                grip.move(0, h - 8)
            else:
                grip.move(w - 8, h - 8)

    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self.drag_started.emit()

    def _title_mouse_move(self, event):
        pass

    def _grip_mouse_press(self, event):
        self._resize_start_geometry = self.geometry()
        self._resize_start_pos = event.globalPosition().toPoint()
        self.resize_started.emit(event.widget().edge)

    def _grip_mouse_move(self, event):
        if hasattr(self, '_resize_start_pos'):
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            edge = event.widget().edge
            new_geo = self._resize_start_geometry
            if edge in (Qt.Corner.TopLeftCorner, Qt.Corner.BottomLeftCorner):
                new_geo.setLeft(new_geo.left() + delta.x())
            if edge in (Qt.Corner.TopRightCorner, Qt.Corner.BottomRightCorner):
                new_geo.setRight(new_geo.right() + delta.x())
            if edge in (Qt.Corner.TopLeftCorner, Qt.Corner.TopRightCorner):
                new_geo.setTop(new_geo.top() + delta.y())
            if edge in (Qt.Corner.BottomLeftCorner, Qt.Corner.BottomRightCorner):
                new_geo.setBottom(new_geo.bottom() + delta.y())
            self.setGeometry(new_geo)