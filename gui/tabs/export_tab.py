from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QComboBox, QRadioButton, QCheckBox, QLineEdit,
    QPushButton, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ExportTab(QWidget):
    """Вкладка 'Экспорт' — выгрузка данных в файлы."""

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel("💾 ЭКСПОРТ ДАННЫХ")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title)

        # Тип данных
        data_group = QGroupBox("Тип данных")
        data_group.setStyleSheet(self._group_style())
        data_layout = QHBoxLayout(data_group)

        data_layout.addWidget(QLabel("Тип данных:"))
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["Пакеты", "Подключения", "Сценарии", "Логи"])
        self.data_type_combo.setStyleSheet(self._combo_style())
        self.data_type_combo.currentTextChanged.connect(self._update_file_extension)
        data_layout.addWidget(self.data_type_combo)
        data_layout.addStretch()

        layout.addWidget(data_group)

        # Формат
        format_group = QGroupBox("Формат")
        format_group.setStyleSheet(self._group_style())
        format_layout = QHBoxLayout(format_group)

        self.csv_radio = QRadioButton("CSV")
        self.csv_radio.setStyleSheet("color: #CCCCCC;")
        self.csv_radio.setChecked(True)
        format_layout.addWidget(self.csv_radio)

        self.json_radio = QRadioButton("JSON")
        self.json_radio.setStyleSheet("color: #CCCCCC;")
        format_layout.addWidget(self.json_radio)

        format_layout.addStretch()
        layout.addWidget(format_group)

        # Файл
        file_group = QGroupBox("Файл")
        file_group.setStyleSheet(self._group_style())
        file_layout = QHBoxLayout(file_group)

        file_layout.addWidget(QLabel("Файл:"))
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Путь к файлу...")
        self.file_edit.setStyleSheet(self._input_style())
        file_layout.addWidget(self.file_edit)

        self.browse_btn = QPushButton("Выбрать...")
        self.browse_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(self.browse_btn)

        layout.addWidget(file_group)

        # Параметры экспорта
        params_group = QGroupBox("Параметры экспорта")
        params_group.setStyleSheet(self._group_style())
        params_layout = QVBoxLayout(params_group)

        self.timestamp_check = QCheckBox("Включить временные метки")
        self.timestamp_check.setChecked(True)
        self.timestamp_check.setStyleSheet("color: #CCCCCC;")
        params_layout.addWidget(self.timestamp_check)

        self.errors_check = QCheckBox("Включить ошибки")
        self.errors_check.setChecked(True)
        self.errors_check.setStyleSheet("color: #CCCCCC;")
        params_layout.addWidget(self.errors_check)

        self.parsed_check = QCheckBox("Включить parsed данные")
        self.parsed_check.setChecked(True)
        self.parsed_check.setStyleSheet("color: #CCCCCC;")
        params_layout.addWidget(self.parsed_check)

        self.split_check = QCheckBox("Разделить по типам пакетов")
        self.split_check.setStyleSheet("color: #CCCCCC;")
        params_layout.addWidget(self.split_check)

        self.zip_check = QCheckBox("Сжимать результат (ZIP)")
        self.zip_check.setStyleSheet("color: #CCCCCC;")
        params_layout.addWidget(self.zip_check)

        layout.addWidget(params_group)

        # Фильтр (опционально)
        filter_group = QGroupBox("Фильтр (опционально)")
        filter_group.setStyleSheet(self._group_style())
        filter_layout = QGridLayout(filter_group)

        filter_layout.addWidget(QLabel("С:"), 0, 0)
        self.date_from = QLineEdit()
        self.date_from.setPlaceholderText("2024-04-30 00:00:00")
        self.date_from.setStyleSheet(self._input_style())
        filter_layout.addWidget(self.date_from, 0, 1)

        filter_layout.addWidget(QLabel("По:"), 0, 2)
        self.date_to = QLineEdit()
        self.date_to.setPlaceholderText("2024-04-30 23:59:59")
        self.date_to.setStyleSheet(self._input_style())
        filter_layout.addWidget(self.date_to, 0, 3)

        filter_layout.addWidget(QLabel("PID:"), 1, 0)
        self.pid_edit = QLineEdit()
        self.pid_edit.setPlaceholderText("например: 1")
        self.pid_edit.setStyleSheet(self._input_style())
        filter_layout.addWidget(self.pid_edit, 1, 1)

        filter_layout.addWidget(QLabel("Service:"), 1, 2)
        self.service_edit = QLineEdit()
        self.service_edit.setPlaceholderText("например: TERM_IDENTITY")
        self.service_edit.setStyleSheet(self._input_style())
        filter_layout.addWidget(self.service_edit, 1, 3)

        layout.addWidget(filter_group)
        layout.addStretch()

        # Кнопка экспорта
        self.export_btn = QPushButton("▶ ЭКСПОРТИРОВАТЬ")
        self.export_btn.setStyleSheet(self._btn_style("#00AA00"))
        self.export_btn.clicked.connect(self._on_export)
        layout.addWidget(self.export_btn)

        # Результат
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color: #00AA00;")
        layout.addWidget(self.result_label)

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

    def _input_style(self):
        return """
            QLineEdit {
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

    def _update_file_extension(self, text):
        """Обновление расширения файла при смене типа данных."""
        current = self.file_edit.text()
        if self.json_radio.isChecked():
            ext = ".json"
        else:
            ext = ".csv"

        if current:
            # Заменяем расширение
            import os
            base, _ = os.path.splitext(current)
            self.file_edit.setText(base + ext)
        else:
            # Генерируем имя по умолчанию
            data_type = self.data_type_combo.currentText().lower()
            self.file_edit.setText(f"{data_type}_{self._get_timestamp()}{ext}")

    def _get_timestamp(self):
        """Текущее время для имени файла."""
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _on_browse(self):
        """Выбор файла для сохранения."""
        if self.json_radio.isChecked():
            filter_str = "JSON Files (*.json);;All Files (*)"
        else:
            filter_str = "CSV Files (*.csv);;All Files (*)"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт данных", "", filter_str
        )
        if file_path:
            self.file_edit.setText(file_path)

    def _on_export(self):
        """Выполнение экспорта."""
        file_path = self.file_edit.text()
        if not file_path:
            QMessageBox.warning(self, "Предупреждение", "Выберите файл для сохранения")
            return

        # Заглушка экспорта
        data_type = self.data_type_combo.currentText()
        format_type = "JSON" if self.json_radio.isChecked() else "CSV"

        # В реальности здесь будет вызов export.export_data()
        QMessageBox.information(
            self, "Экспорт",
            f"Экспорт данных '{data_type}' в формате {format_type}.\n"
            f"Файл: {file_path}\n\n"
            f"Функция экспорта пока не реализована."
        )

        # Пример результата
        self.result_label.setText(
            f"Результат: Экспортировано X записей → {file_path}"
        )
