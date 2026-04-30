from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QTextEdit, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette


class PacketDetailsDialog(QDialog):
    """Диалог детального просмотра структуры EGTS-пакета."""

    def __init__(self, packet_data: dict, parent=None):
        super().__init__(parent)
        self.packet = packet_data
        self.setWindowTitle("📦 Детали пакета")
        self.setMinimumSize(800, 700)
        self._init_ui()
        self._populate_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Основная информация
        self.info_group = QGroupBox("ОСНОВНАЯ ИНФОРМАЦИЯ")
        self.info_group.setStyleSheet(self._group_style())
        info_layout = QGridLayout(self.info_group)
        layout.addWidget(self.info_group)

        # Заголовок EGTS
        self.header_group = QGroupBox("ЗАГОЛОВОК EGTS")
        self.header_group.setStyleSheet(self._group_style())
        header_layout = QGridLayout(self.header_group)
        layout.addWidget(self.header_group)

        # Records
        self.records_group = QGroupBox("RECORDS")
        self.records_group.setStyleSheet(self._group_style())
        records_layout = QVBoxLayout(self.records_group)
        layout.addWidget(self.records_group)

        # HEX-дамп
        self.hex_group = QGroupBox("HEX ДАМП")
        self.hex_group.setStyleSheet(self._group_style())
        hex_layout = QVBoxLayout(self.hex_group)

        self.hex_edit = QTextEdit()
        self.hex_edit.setReadOnly(True)
        self.hex_edit.setFont(QFont("Consolas", 11))
        self.hex_edit.setStyleSheet("""
            QTextEdit {
                background-color: #3C3C3C;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 3px;
            }
        """)
        hex_layout.addWidget(self.hex_edit)

        hex_btn_layout = QHBoxLayout()
        self.copy_hex_btn = QPushButton("📋 Копировать HEX")
        self.copy_hex_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.copy_hex_btn.clicked.connect(self._on_copy_hex)

        self.save_hex_btn = QPushButton("💾 Сохранить")
        self.save_hex_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.save_hex_btn.clicked.connect(self._on_save_hex)

        hex_btn_layout.addWidget(self.copy_hex_btn)
        hex_btn_layout.addWidget(self.save_hex_btn)
        hex_btn_layout.addStretch()
        hex_layout.addLayout(hex_btn_layout)

        layout.addWidget(self.hex_group)

        # Кнопки диалога
        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.setStyleSheet(self._btn_style("#555555"))
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _populate_data(self):
        """Заполнение данными пакета."""
        # Основная информация
        info_layout = self.info_group.layout()

        # Время
        time_label = QLabel("Время:")
        time_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        info_layout.addWidget(time_label, 0, 0)
        time_value = QLabel(self.packet.get("time", "-"))
        info_layout.addWidget(time_value, 0, 1)

        # Направление
        dir_label = QLabel("Направление:")
        dir_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        info_layout.addWidget(dir_label, 1, 0)
        direction = self.packet.get("direction", "-")
        dir_text = f"▶ RX (входящий)" if "RX" in direction else f"◀ TX (исходящий)"
        dir_value = QLabel(dir_text)
        info_layout.addWidget(dir_value, 1, 1)

        # Размер
        size_label = QLabel("Размер:")
        size_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        info_layout.addWidget(size_label, 2, 0)
        size_value = QLabel(f"{self.packet.get('size', '-')} байт")
        info_layout.addWidget(size_value, 2, 1)

        # CRC8 и CRC16 (заглушки)
        crc8_label = QLabel("CRC8:")
        crc8_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        info_layout.addWidget(crc8_label, 3, 0)
        crc8_value = QLabel("✅ OK")
        crc8_value.setStyleSheet("color: #00AA00;")
        info_layout.addWidget(crc8_value, 3, 1)

        crc16_label = QLabel("CRC16:")
        crc16_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        info_layout.addWidget(crc16_label, 4, 0)
        crc16_value = QLabel("✅ OK")
        crc16_value.setStyleSheet("color: #00AA00;")
        info_layout.addWidget(crc16_value, 4, 1)

        # Connection ID (если есть)
        if "connection_id" in self.packet:
            conn_label = QLabel("Connection ID:")
            conn_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
            info_layout.addWidget(conn_label, 5, 0)
            conn_value = QLabel(self.packet["connection_id"])
            info_layout.addWidget(conn_value, 5, 1)

        # Заголовок EGTS (заглушка)
        header_layout = self.header_group.layout()
        headers = ["PID", "RPID", "RN", "CRN", "TID", "Length", "Protocol Ver"]
        for i, header in enumerate(headers):
            label = QLabel(f"{header}:")
            label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
            header_layout.addWidget(label, i, 0)
            value = QLabel(str(self.packet.get(header.lower(), "-")))
            header_layout.addWidget(value, i, 1)

        # Records (заглушка)
        # В реальности здесь будет динамическое создание полей

        # HEX-дамп
        raw_hex = self.packet.get("raw", "")
        if raw_hex:
            # Форматирование: XX XX XX XX ...
            hex_str = " ".join(raw_hex[i:i+2] for i in range(0, len(raw_hex), 2))
            self.hex_edit.setPlainText(hex_str)
        else:
            self.hex_edit.setPlainText("Нет данных")

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

    def _on_copy_hex(self):
        """Копирование HEX в буфер обмена."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.hex_edit.toPlainText())

    def _on_save_hex(self):
        """Сохранение HEX в файл."""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить HEX", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.hex_edit.toPlainText())
