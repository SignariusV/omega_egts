# OMEGA_EGTS GUI
"""CollapsibleGroupBox — кастомный виджет с заголовком и стрелочкой для сворачивания."""

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class CollapsibleGroupBox(QWidget):
    """Виджет с заголовком и кнопкой-стрелочкой для сворачивания содержимого."""

    toggled = Signal(bool)  # True если развернули

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("class", "CollapsibleGroupBox")
        self._title = title
        self._collapsed = False
        self._content_widget: QWidget | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(5)

        # Заголовок с кнопкой
        header_widget = QWidget()
        header_widget.setProperty("class", "CollapsibleGroupHeader")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)

        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setProperty("class", "CollapsibleToggle")
        self._toggle_btn.setFixedSize(20, 20)
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._on_toggle)

        self._title_label = QLabel(self._title)
        font = self._title_label.font()
        font.setBold(True)
        self._title_label.setFont(font)

        header_layout.addWidget(self._toggle_btn)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        self._main_layout.addWidget(header_widget)

        # Контейнер для содержимого
        self._content_container = QWidget()
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(10, 5, 5, 5)
        self._main_layout.addWidget(self._content_container)

    def set_content_layout(self, layout) -> None:
        """Установить лейаут содержимого."""
        # Удаляем старый лейаут, если есть
        old_layout = self._content_container.layout()
        if old_layout is not None:
            # Удаляем все элементы из старого лейаута
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item is not None and item.widget() is not None:
                    item.widget().deleteLater()
            # Удаляем старый лейаут
            QWidget().setLayout(old_layout)

        # Устанавливаем новый лейаут
        self._content_container.setLayout(layout)
        self._content_widget = self._content_container

    def set_content_widget(self, widget: QWidget) -> None:
        """Установить виджет содержимого (внутри создается QVBoxLayout)."""
        # Создаем новый лейаут
        new_layout = QVBoxLayout()
        new_layout.setContentsMargins(10, 5, 5, 5)
        new_layout.addWidget(widget)
        # Устанавливаем через set_content_layout
        self.set_content_layout(new_layout)
        self._content_widget = widget

    @Slot()
    def _on_toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._content_container.setVisible(not self._collapsed)
        self._toggle_btn.setText("▶" if self._collapsed else "▼")
        self.toggled.emit(not self._collapsed)
        # Обновляем размеры
        if self.parentWidget() and self.parentWidget().layout():
            self.parentWidget().layout().activate()

    def set_collapsed(self, collapsed: bool) -> None:
        """Установить состояние сворачивания."""
        if self._collapsed != collapsed:
            self._on_toggle()

    def is_collapsed(self) -> bool:
        """Возвращает True если группа свернута."""
        return self._collapsed
