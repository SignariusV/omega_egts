from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QCheckBox, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class SettingsDialog(QDialog):
    """Диалог 'Настройки' приложения."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumSize(500, 400)
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Внешний вид
        appearance_group = QGroupBox("Внешний вид")
        appearance_group.setStyleSheet(self._group_style())
        appearance_layout = QVBoxLayout(appearance_group)

        # Тема
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Тема:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Тёмная", "Светлая"])
        self.theme_combo.setStyleSheet(self._combo_style())
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        appearance_layout.addLayout(theme_layout)

        # Язык
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Язык:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Русский", "English"])
        self.lang_combo.setStyleSheet(self._combo_style())
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        appearance_layout.addLayout(lang_layout)

        # Автосохранение
        self.autosave_check = QCheckBox("Автосохранение черновиков")
        self.autosave_check.setStyleSheet("color: #CCCCCC;")
        appearance_layout.addWidget(self.autosave_check)

        layout.addWidget(appearance_group)

        # Сеть (заглушка)
        network_group = QGroupBox("Сеть")
        network_group.setStyleSheet(self._group_style())
        network_layout = QVBoxLayout(network_group)
        network_layout.addWidget(QLabel("Настройки сети пока недоступны"))
        layout.addWidget(network_group)

        layout.addStretch()

        # Кнопки
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setStyleSheet(self._btn_style("#00AA00"))
        self.save_btn.clicked.connect(self._on_save)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setStyleSheet(self._btn_style("#555555"))
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
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

    def _combo_style(self):
        return """
            QComboBox {
                background-color: #3C3C3C;
                color: #CCCCCC;
                border: 1px solid #555555;
                padding: 6px;
                border-radius: 3px;
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

    def _load_settings(self):
        """Загрузка настроек из QSettings."""
        from PySide6.QtCore import QSettings
        settings = QSettings("OMEGA_EGTS", "GUI")

        theme = settings.value("theme", "Тёмная")
        index = self.theme_combo.findText(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        language = settings.value("language", "Русский")
        index = self.lang_combo.findText(language)
        if index >= 0:
            self.lang_combo.setCurrentIndex(index)

        autosave = settings.value("autosave", True, type=bool)
        self.autosave_check.setChecked(autosave)

    def _on_save(self):
        """Сохранение настроек."""
        from PySide6.QtCore import QSettings
        settings = QSettings("OMEGA_EGTS", "GUI")

        settings.setValue("theme", self.theme_combo.currentText())
        settings.setValue("language", self.lang_combo.currentText())
        settings.setValue("autosave", self.autosave_check.isChecked())

        QMessageBox.information(self, "Настройки", "Настройки сохранены!")
        self.accept()
