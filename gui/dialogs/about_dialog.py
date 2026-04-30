from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class AboutDialog(QDialog):
    """Диалог 'О программе'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setFixedSize(400, 300)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel("OMEGA_EGTS - Тестер УСВ")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Версия
        version_label = QLabel("Версия: 1.0.0 (GUI v1.0)")
        version_label.setStyleSheet("color: #CCCCCC;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        # Описание
        desc_group = QGroupBox("Описание")
        desc_group.setStyleSheet(self._group_style())
        desc_layout = QVBoxLayout(desc_group)

        desc = QLabel(
            "Графический интерфейс для управления серверным тестером "
            "устройств/систем вызова экстренных оперативных служб (УСВ).\n\n"
            "Предназначен для использования в испытательных лабораториях."
        )
        desc.setStyleSheet("color: #CCCCCC;")
        desc.setWordWrap(True)
        desc_layout.addWidget(desc)

        layout.addWidget(desc_group)

        # Разработчик
        dev_group = QGroupBox("Разработчик")
        dev_group.setStyleSheet(self._group_style())
        dev_layout = QVBoxLayout(dev_group)

        dev_label = QLabel("Команда разработки OMEGA_EGTS\n2026")
        dev_label.setStyleSheet("color: #CCCCCC;")
        dev_layout.addWidget(dev_label)

        layout.addWidget(dev_group)
        layout.addStretch()

        # Кнопка закрытия
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet(self._btn_style("#0078D7"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _group_style(self):
        return """
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """

    def _btn_style(self, bg_color):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: #FFFFFF;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #1E8FD9; }}
            QPushButton:pressed {{ background-color: #006CC1; }}
        """
