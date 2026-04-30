from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QGridLayout, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class ConnectionTab(QWidget):
    """Вкладка 'Подключение' — управление сервером и CMW-500."""

    def __init__(self, engine_wrapper, event_bridge):
        super().__init__()
        self.engine_wrapper = engine_wrapper
        self.event_bridge = event_bridge
        self.is_server_running = False
        self._init_ui()
        self._connect_signals()

        # Обновляем статус если движок уже запущен
        if self.engine_wrapper.engine and self.engine_wrapper.engine._started:
            self._on_server_started({"port": 3001})

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Заголовок
        title = QLabel("🔌 ПОДКЛЮЧЕНИЕ И УПРАВЛЕНИЕ СЕРВЕРОМ")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF; font-size: 18px; padding: 10px;")
        layout.addWidget(title)

        # Статус панель (верхняя)
        self.status_panel = QGroupBox()
        self.status_panel.setStyleSheet(self._group_style())
        status_layout = QHBoxLayout(self.status_panel)

        self.server_status_label = QLabel("🔴 СЕРВЕР ОСТАНОВЛЕН")
        self.server_status_label.setStyleSheet("color: #FF5555; font-weight: bold;")
        status_layout.addWidget(self.server_status_label)

        self.cmw_status_label = QLabel("🔴 CMW-500: ОТКЛЮЧЕН")
        self.cmw_status_label.setStyleSheet("color: #FF5555; font-weight: bold;")
        status_layout.addWidget(self.cmw_status_label)

        status_layout.addStretch()

        self.uptime_label = QLabel("Uptime: 00:00:00")
        status_layout.addWidget(self.uptime_label)

        layout.addWidget(self.status_panel)

        # Нижняя часть: конфигурация и настройки
        bottom_layout = QHBoxLayout()

        # Левая колонка - Конфигурация сервера
        server_group = QGroupBox("КОНФИГУРАЦИЯ СЕРВЕРА")
        server_group.setStyleSheet(self._group_style())
        server_layout = QGridLayout(server_group)

        server_layout.addWidget(QLabel("Порт TCP:"), 0, 0)
        self.port_input = QLineEdit("3001")
        self.port_input.setStyleSheet(self._input_style())
        server_layout.addWidget(self.port_input, 0, 1)

        server_layout.addWidget(QLabel("ГОСТ:"), 1, 0)
        self.gost_combo = QComboBox()
        self.gost_combo.addItems(["2015", "2023"])
        self.gost_combo.setStyleSheet(self._input_style())
        server_layout.addWidget(self.gost_combo, 1, 1)

        server_layout.addWidget(QLabel("Логирование:"), 2, 0)
        self.log_combo = QComboBox()
        self.log_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_combo.setCurrentText("INFO")
        self.log_combo.setStyleSheet(self._input_style())
        server_layout.addWidget(self.log_combo, 2, 1)

        self.emu_checkbox = QCheckBox("Эмуляция CMW")
        self.emu_checkbox.setStyleSheet("color: #CCCCCC;")
        server_layout.addWidget(self.emu_checkbox, 3, 0, 1, 2)

        # Кнопки сервера
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ ЗАПУСТИТЬ")
        self.start_btn.setObjectName("btnStart")
        self.start_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.start_btn.clicked.connect(self._on_start_clicked)

        self.stop_btn = QPushButton("⏹ СТОП")
        self.stop_btn.setObjectName("btnStop")
        self.stop_btn.setStyleSheet(self._btn_style("#555555"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        server_layout.addLayout(btn_layout, 4, 0, 1, 2)

        bottom_layout.addWidget(server_group)

        # Правая колонка - CMW-500 настройки
        cmw_group = QGroupBox("CMW-500 НАСТРОЙКИ")
        cmw_group.setStyleSheet(self._group_style())
        cmw_layout = QGridLayout(cmw_group)

        cmw_layout.addWidget(QLabel("IP адрес:"), 0, 0)
        self.cmw_ip_input = QLineEdit("192.168.1.100")
        self.cmw_ip_input.setStyleSheet(self._input_style())
        cmw_layout.addWidget(self.cmw_ip_input, 0, 1)

        cmw_layout.addWidget(QLabel("Режим:"), 1, 0)
        self.cmw_mode_combo = QComboBox()
        self.cmw_mode_combo.addItems(["Сеть", "SMS", "Эмуляция"])
        self.cmw_mode_combo.setStyleSheet(self._input_style())
        cmw_layout.addWidget(self.cmw_mode_combo, 1, 1)

        self.auto_connect_checkbox = QCheckBox("Автостарт")
        self.auto_connect_checkbox.setStyleSheet("color: #CCCCCC;")
        cmw_layout.addWidget(self.auto_connect_checkbox, 2, 0, 1, 2)

        # Кнопка переподключения
        self.reconnect_btn = QPushButton("🔄 ПЕРЕПОДКЛЮЧИТЬ")
        self.reconnect_btn.setStyleSheet(self._btn_style("#0078D7"))
        cmw_layout.addWidget(self.reconnect_btn, 3, 0, 1, 2)

        bottom_layout.addWidget(cmw_group)
        layout.addLayout(bottom_layout)

        # Статус компонентов
        components_group = QGroupBox("СТАТУС КОМПОНЕНТОВ")
        components_group.setStyleSheet(self._group_style())
        comp_layout = QHBoxLayout(components_group)

        self.component_labels = {}
        for name in ["TCP Server", "CMW-500", "SessionMgr", "ScenarioMgr"]:
            label = QLabel(f"{name}\n🔴")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #CCCCCC; padding: 10px;")
            self.component_labels[name] = label
            comp_layout.addWidget(label)

        layout.addWidget(components_group)
        layout.addStretch()

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

    def _input_style(self):
        return """
            QLineEdit, QComboBox {
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
            QPushButton:hover {{
                background-color: #1E8FD9;
            }}
            QPushButton:pressed {{
                background-color: #006CC1;
            }}
            QPushButton:disabled {{
                background-color: #555555;
                color: #888888;
            }}
        """

    def _connect_signals(self):
        """Подключение сигналов EventBridge."""
        self.event_bridge.server_started.connect(self._on_server_started)
        self.event_bridge.server_stopped.connect(self._on_server_stopped)
        self.event_bridge.cmw_connected.connect(self._on_cmw_connected)
        self.event_bridge.cmw_disconnected.connect(self._on_cmw_disconnected)

    def _on_start_clicked(self):
        """Запуск сервера."""
        try:
            port = int(self.port_input.text())
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Порт должен быть числом")
            return

        # Блокируем поля конфигурации
        self._set_config_enabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        # Обновляем конфигурацию (если есть доступ)
        # Примечание: Config frozen, изменение не поддерживается

        # Запускаем сервер
        self.engine_wrapper.start_server()

    def _on_stop_clicked(self):
        """Остановка сервера."""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Остановить сервер?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.engine_wrapper.stop_server()

    def _set_config_enabled(self, enabled):
        """Блокировка/разблокировка полей конфигурации."""
        self.port_input.setEnabled(enabled)
        self.gost_combo.setEnabled(enabled)
        self.log_combo.setEnabled(enabled)
        self.emu_checkbox.setEnabled(enabled)
        self.cmw_ip_input.setEnabled(enabled)
        self.cmw_mode_combo.setEnabled(enabled)
        self.auto_connect_checkbox.setEnabled(enabled)

    def _on_server_started(self, data: dict):
        """Обработчик события server.started."""
        self.is_server_running = True
        self.server_status_label.setText("🟢 СЕРВЕР ЗАПУЩЕН")
        self.server_status_label.setStyleSheet("color: #00AA00; font-weight: bold;")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_config_enabled(False)

    def _on_server_stopped(self, data: dict):
        """Обработчик события server.stopped."""
        self.is_server_running = False
        self.server_status_label.setText("🔴 СЕРВЕР ОСТАНОВЛЕН")
        self.server_status_label.setStyleSheet("color: #FF5555; font-weight: bold;")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_config_enabled(True)

    def _on_cmw_connected(self, data: dict):
        """Обработчик события cmw.connected."""
        self.cmw_status_label.setText("🟢 CMW-500: ПОДКЛЮЧЕН")
        self.cmw_status_label.setStyleSheet("color: #00AA00; font-weight: bold;")

    def _on_cmw_disconnected(self, data: dict):
        """Обработчик события cmw.disconnected."""
        self.cmw_status_label.setText("🔴 CMW-500: ОТКЛЮЧЕН")
        self.cmw_status_label.setStyleSheet("color: #FF5555; font-weight: bold;")
