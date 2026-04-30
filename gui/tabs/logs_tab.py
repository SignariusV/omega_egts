from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QLabel, QComboBox,
    QLineEdit, QPushButton, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor


class LogsTab(QWidget):
    """Вкладка 'Логи' — просмотр системных логов Python."""

    def __init__(self):
        super().__init__()
        self.logs = []
        self._init_ui()
        self._start_auto_scroll()
        self._load_logs()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel("📋 СИСТЕМНЫЕ ЛОГИ")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title)

        # Фильтры
        filter_layout = QHBoxLayout()

        # Тип логов (заглушка)
        filter_layout.addWidget(QLabel("Тип:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Python", "JSONL"])
        self.type_combo.setStyleSheet(self._combo_style())
        filter_layout.addWidget(self.type_combo)

        # Уровень
        filter_layout.addWidget(QLabel("Уровень:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setCurrentText("INFO")
        self.level_combo.setStyleSheet(self._combo_style())
        self.level_combo.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.level_combo)

        # Поиск
        filter_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по тексту...")
        self.search_edit.setStyleSheet(self._input_style())
        self.search_edit.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_edit)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Таблица логов
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(4)
        self.log_table.setHorizontalHeaderLabels(["Время", "Источник", "Уровень", "Сообщение"])
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # Сообщение
        self.log_table.setStyleSheet(self._table_style())
        layout.addWidget(self.log_table)

        # Информация и кнопки
        bottom_layout = QHBoxLayout()

        self.info_label = QLabel("Всего записей: 0")
        self.info_label.setStyleSheet("color: #CCCCCC;")
        bottom_layout.addWidget(self.info_label)

        bottom_layout.addStretch()

        self.clear_btn = QPushButton("🗑 Очистить")
        self.clear_btn.setStyleSheet(self._btn_style("#555555"))
        self.clear_btn.clicked.connect(self._on_clear)
        bottom_layout.addWidget(self.clear_btn)

        self.export_btn = QPushButton("💾 Экспорт")
        self.export_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.export_btn.clicked.connect(self._on_export)
        bottom_layout.addWidget(self.export_btn)

        layout.addLayout(bottom_layout)

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

    def _table_style(self):
        return """
            QTableWidget {
                background-color: #3C3C3C;
                color: #CCCCCC;
                border: 1px solid #555555;
                gridline-color: #555555;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #3E5F8A;
            }
            QHeaderView::section {
                background-color: #323232;
                color: #FFFFFF;
                padding: 6px;
                border: 1px solid #555555;
                font-weight: bold;
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

    def _load_logs(self):
        """Загрузка логов (заглушка)."""
        # В реальности логи должны поступать через EventBridge или Python logging
        # Пока добавим тестовые записи
        import datetime
        self.add_log("INFO", "gui.main", "GUI application started")
        self.add_log("DEBUG", "gui.tabs", "ConnectionTab initialized")
        self.add_log("WARNING", "core.engine", "Config file not found, using defaults")
        self.add_log("ERROR", "core.cmw500", "Connection failed: timeout")

    def add_log(self, level: str, source: str, message: str):
        """Добавление записи в таблицу."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

        row = self.log_table.rowCount()
        self.log_table.insertRow(row)

        # Время
        time_item = QTableWidgetItem(timestamp)
        time_item.setForeground(QColor("#CCCCCC"))
        self.log_table.setItem(row, 0, time_item)

        # Источник
        source_item = QTableWidgetItem(source)
        source_item.setForeground(QColor("#CCCCCC"))
        self.log_table.setItem(row, 1, source_item)

        # Уровень
        level_item = QTableWidgetItem(level)
        color = self._get_level_color(level)
        level_item.setForeground(color)
        level_item.setTextAlignment(Qt.AlignCenter)
        self.log_table.setItem(row, 2, level_item)

        # Сообщение
        msg_item = QTableWidgetItem(message)
        msg_item.setForeground(QColor("#CCCCCC"))
        self.log_table.setItem(row, 3, msg_item)

        # Сохраняем в список
        self.logs.append({
            "time": timestamp,
            "level": level,
            "source": source,
            "message": message
        })

        # Обновляем информацию
        self.info_label.setText(f"Всего записей: {len(self.logs)}")

        # Автопрокрутка
        if self.auto_scroll:
            self.log_table.scrollToBottom()

    def _get_level_color(self, level):
        """Цвет текста в зависимости от уровня."""
        if level == "DEBUG":
            return QColor("#888888")  # Серый
        elif level == "INFO":
            return QColor("#FFFFFF")  # Белый
        elif level == "WARNING":
            return QColor("#FFAA00")  # Жёлтый
        elif level == "ERROR":
            return QColor("#FF5555")  # Красный
        return QColor("#CCCCCC")

    def _apply_filters(self):
        """Применение фильтров."""
        level_filter = self.level_combo.currentText()
        search_text = self.search_edit.text().lower()

        for row in range(self.log_table.rowCount()):
            show = True

            # Фильтр по уровню
            if level_filter != "ALL":
                level_item = self.log_table.item(row, 2)
                if level_item and level_item.text() != level_filter:
                    show = False

            # Текстовый поиск
            if search_text:
                row_text = " ".join(
                    self.log_table.item(row, col).text().lower()
                    for col in range(4)
                    if self.log_table.item(row, col)
                )
                if search_text not in row_text:
                    show = False

            self.log_table.setRowHidden(row, not show)

    def _start_auto_scroll(self):
        """Включение автопрокрутки."""
        self.auto_scroll = True
        # В реальном приложении здесь может быть чекбокс

    def _on_clear(self):
        """Очистка отображения (не файла)."""
        self.log_table.setRowCount(0)
        self.logs.clear()
        self.info_label.setText("Всего записей: 0")

    def _on_export(self):
        """Экспорт логов в файл."""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт логов", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                for log in self.logs:
                    f.write(f"[{log['time']}] {log['source']:<20} {log['level']:<8} {log['message']}\n")
