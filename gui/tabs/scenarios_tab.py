from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QComboBox, QLineEdit, QCheckBox, QTableWidget, QTableWidgetItem,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from gui.widgets.packet_table import PacketTable
from gui.widgets.scenario_progress import ScenarioProgress
from gui.widgets.step_list import StepList
from gui.dialogs.packet_details import PacketDetailsDialog


class ScenariosTab(QWidget):
    """Вкладка 'Сценарии' — выполнение сценариев (ОСНОВНОЕ ОКНО)."""

    def __init__(self, engine_wrapper, event_bridge):
        super().__init__()
        self.engine_wrapper = engine_wrapper
        self.event_bridge = event_bridge
        self.current_scenario = None
        self.scenario_dir = Path("scenarios")
        self.packets = []
        self._init_ui()
        self._connect_signals()
        self._load_scenarios()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel("📝 ВЫПОЛНЕНИЕ СЦЕНАРИЕВ")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title)

        # Верхняя часть: выбор сценария и управление
        top_layout = QHBoxLayout()

        # Левая панель - выбор сценария
        scenario_group = QGroupBox("ВЫБОР СЦЕНАРИЯ")
        scenario_group.setStyleSheet(self._group_style())
        scenario_layout = QVBoxLayout(scenario_group)

        self.scenario_list = QListWidget()
        self.scenario_list.setStyleSheet(self._list_style())
        self.scenario_list.itemClicked.connect(self._on_scenario_selected)
        scenario_layout.addWidget(self.scenario_list)

        # Кнопки управления сценариями
        btn_layout = QHBoxLayout()
        self.open_folder_btn = QPushButton("📂 Открыть папку")
        self.open_folder_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.open_folder_btn.clicked.connect(self._on_open_folder)

        self.save_as_btn = QPushButton("💾 Сохранить как...")
        self.save_as_btn.setStyleSheet(self._btn_style("#555555"))
        self.save_as_btn.clicked.connect(self._on_save_as)

        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addWidget(self.save_as_btn)
        scenario_layout.addLayout(btn_layout)

        top_layout.addWidget(scenario_group)

        # Правая панель - управление
        control_group = QGroupBox("УПРАВЛЕНИЕ")
        control_group.setStyleSheet(self._group_style())
        control_layout = QVBoxLayout(control_group)

        self.run_btn = QPushButton("▶ ЗАПУСТИТЬ СЦЕНАРИЙ")
        self.run_btn.setStyleSheet(self._btn_style("#00AA00"))
        self.run_btn.clicked.connect(self._on_run_scenario)

        self.stop_btn = QPushButton("⏹ ОСТАНОВИТЬ")
        self.stop_btn.setStyleSheet(self._btn_style("#FF5555"))
        self.stop_btn.clicked.connect(self._on_stop_scenario)
        self.stop_btn.setEnabled(False)

        self.pause_btn = QPushButton("⏸ ПАУЗА")
        self.pause_btn.setStyleSheet(self._btn_style("#FFAA00"))
        self.pause_btn.setEnabled(False)

        self.restart_btn = QPushButton("🔁 ПЕРЕЗАПУСТИТЬ")
        self.restart_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.restart_btn.setEnabled(False)

        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.restart_btn)

        # Информация о текущем сценарии
        self.current_scenario_label = QLabel("Текущий сценарий: Не выбран")
        self.current_scenario_label.setStyleSheet("color: #CCCCCC;")
        control_layout.addWidget(self.current_scenario_label)

        self.steps_count_label = QLabel("Шагов: 0")
        self.steps_count_label.setStyleSheet("color: #CCCCCC;")
        control_layout.addWidget(self.steps_count_label)

        control_layout.addStretch()
        top_layout.addWidget(control_group)
        layout.addLayout(top_layout)

        # Прогресс выполнения
        self.progress_widget = ScenarioProgress()
        layout.addWidget(self.progress_widget)

        # Список шагов
        steps_group = QGroupBox("📋 ШАГИ СЦЕНАРИЯ")
        steps_group.setStyleSheet(self._group_style())
        steps_layout = QVBoxLayout(steps_group)
        self.step_list = StepList()
        steps_layout.addWidget(self.step_list)
        layout.addWidget(steps_group)

        # Таблица пакетов
        packets_group = QGroupBox("📡 ПАКЕТЫ (входящие/исходящие)")
        packets_group.setStyleSheet(self._group_style())
        packets_layout = QVBoxLayout(packets_group)

        # Фильтры
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Фильтр:"))

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все", "RX", "TX"])
        self.filter_combo.setStyleSheet(self._combo_style())
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_combo)

        self.rx_check = QCheckBox("RX")
        self.rx_check.setChecked(True)
        self.rx_check.setStyleSheet("color: #CCCCCC;")
        filter_layout.addWidget(self.rx_check)

        self.tx_check = QCheckBox("TX")
        self.tx_check.setChecked(True)
        self.tx_check.setStyleSheet("color: #CCCCCC;")
        filter_layout.addWidget(self.tx_check)

        filter_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск...")
        self.search_edit.setStyleSheet(self._input_style())
        self.search_edit.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_edit)

        filter_layout.addStretch()

        self.export_packets_btn = QPushButton("📥 Экспорт")
        self.export_packets_btn.setStyleSheet(self._btn_style("#0078D7"))
        filter_layout.addWidget(self.export_packets_btn)

        packets_layout.addLayout(filter_layout)

        self.packet_table = PacketTable()
        self.packet_table.packet_selected.connect(self._on_packet_selected)
        packets_layout.addWidget(self.packet_table)

        self.packets_info_label = QLabel("Всего: 0 пакетов | Выбрано: 0")
        self.packets_info_label.setStyleSheet("color: #CCCCCC;")
        packets_layout.addWidget(self.packets_info_label)

        layout.addWidget(packets_group)

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
            QPushButton:disabled {{ background-color: #555555; color: #888888; }}
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

    def _list_style(self):
        return """
            QListWidget {
                background-color: #3C3C3C;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #555555;
            }
            QListWidget::item:selected {
                background-color: #3E5F8A;
            }
        """

    def _load_scenarios(self):
        """Загрузка списка сценариев из папки."""
        self.scenario_list.clear()
        if not self.scenario_dir.exists():
            return
        for path in self.scenario_dir.iterdir():
            if path.is_dir():
                item = QListWidgetItem(f"📁 {path.name}")
                item.setData(Qt.UserRole, str(path))
                self.scenario_list.addItem(item)

    def _connect_signals(self):
        """Подключение сигналов EventBridge."""
        self.event_bridge.packet_processed.connect(self._on_packet)
        self.event_bridge.scenario_step.connect(self._on_scenario_step)
        self.event_bridge.scenario_started.connect(self._on_scenario_started)
        self.event_bridge.scenario_finished.connect(self._on_scenario_finished)

    def _on_scenario_selected(self, item):
        """Выбор сценария из списка."""
        scenario_path = item.data(Qt.UserRole)
        if scenario_path:
            self.current_scenario = scenario_path
            self.current_scenario_label.setText(f"Текущий сценарий: {Path(scenario_path).name}")
            # Загрузка шагов (заглушка, пока нет парсера)
            # В реальности нужно загрузить scenario.json
            self.steps_count_label.setText("Шагов: (неизвестно)")
            self.step_list.setRowCount(0)  # Очистка

    def _on_run_scenario(self):
        """Запуск выбранного сценария."""
        if not self.current_scenario:
            QMessageBox.warning(self, "Предупреждение", "Выберите сценарий")
            return
        self.engine_wrapper.run_scenario(self.current_scenario)

    def _on_stop_scenario(self):
        """Остановка сценария."""
        self.engine_wrapper.stop_server()  # Заглушка

    def _on_open_folder(self):
        """Выбор папки со сценариями."""
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку со сценариями",
            str(self.scenario_dir)
        )
        if folder:
            self.scenario_dir = Path(folder)
            self._load_scenarios()

    def _on_save_as(self):
        """Сохранение сценария как..."""
        # Заглушка
        QMessageBox.information(self, "Информация", "Функция сохранения пока не реализована")

    def _on_packet(self, data: dict):
        """Обработка нового пакета."""
        # Преобразование данных из EventBus в формат для таблицы
        ctx = data.get("ctx")
        if not ctx:
            return

        packet_info = {
            "time": ctx.get("timestamp", "") if isinstance(ctx, dict) else "",
            "direction": "RX" if data.get("direction") == "rx" else "TX",
            "pid": ctx.get("PID", "-") if isinstance(ctx, dict) else "-",
            "rn": ctx.get("RN", "-") if isinstance(ctx, dict) else "-",
            "size": len(ctx.get("raw", b"")) if isinstance(ctx, dict) else 0,
            "service": ctx.get("service", "-") if isinstance(ctx, dict) else "-",
        }
        self.packets.append(packet_info)
        self.packet_table.add_packet(packet_info)
        self.packets_info_label.setText(f"Всего: {len(self.packets)} пакетов | Выбрано: 0")

    def _on_scenario_step(self, data: dict):
        """Обновление статуса шага сценария."""
        step_name = data.get("step", "")
        status = data.get("status", "")
        self.step_list.update_step_status(step_name, status)

    def _on_scenario_started(self, data: dict):
        """Начало выполнения сценария."""
        scenario_name = data.get("name", "Неизвестно")
        total_steps = data.get("total_steps", 0)
        self.progress_widget.set_scenario(scenario_name, total_steps)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _on_scenario_finished(self, data: dict):
        """Завершение выполнения сценария."""
        status = data.get("status", "PENDING")
        self.progress_widget.set_status(status)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_packet_selected(self, packet_data: dict):
        """Открытие диалога деталей пакета."""
        dialog = PacketDetailsDialog(packet_data, self)
        dialog.exec()

    def _on_filter_changed(self, text):
        """Изменение фильтра направления."""
        self.packet_table.set_filter(direction=text)

    def _on_search_changed(self, text):
        """Изменение текста поиска."""
        self.packet_table.set_filter(text=text)
