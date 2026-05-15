# OMEGA_EGTS GUI
"""SettingsCard — карточка настроек приложения."""

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QWidget, QVBoxLayout,
)

from core.config import Config
from gui.dashboard.card_base import BaseCard
from gui.widgets.collapsible_group import CollapsibleGroupBox

THEME = {
    "bg": "#1E1E1E",
    "card_bg": "#252526",
    "border": "#3E3E42",
    "text": "#CCCCCC",
    "input_bg": "#3C3C3C",
    "header_bg": "#333333",
    "accent": "#007ACC",
}

# Проектный корень: от gui/dashboard/cards/settings.py 4 уровня вверх (cards -> dashboard -> gui -> OMEGA_EGTS)
# Используем resolve() для получения абсолютного пути
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# Для отладки: раскомментируйте следующую строку, чтобы увидеть путь
# print(f"DEBUG settings.py PROJECT_ROOT: {PROJECT_ROOT}").parent

logger = logging.getLogger(__name__)


class SettingsCard(BaseCard):
    """Карточка настроек с возможностью сворачивания групп."""

    settings_changed = Signal(dict)  # Сигнал с новыми настройками

    def __init__(self, card_id: str = "settings", config: Config | None = None, parent=None):
        self._config = config or Config()
        self._widgets: dict[str, Any] = {}
        super().__init__("Settings", card_id=card_id, parent=parent)
        # Абсолютный путь к иконке (чтобы грузилась из любой директории)
        self.icon_path = str(PROJECT_ROOT / "gui" / "resources" / "icons" / "settings.svg")
        self._build_widgets()
        self.finish_init()
        # Карточка будет скрыта после добавления в дашборд (через hide() в MainWindow)

    def _build_widgets(self):
        # Compact view
        self._compact_label = QLabel("Settings not loaded")
        self._update_compact_view()

        # Expanded view
        self._expanded_widget = QScrollArea()
        self._expanded_widget.setWidgetResizable(True)
        self._expanded_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._expanded_widget.setStyleSheet(f"""
            QScrollArea {{
                background-color: {THEME['card_bg']};
                border: none;
            }}
            QScrollArea > QWidget {{
                background-color: {THEME['card_bg']};
            }}
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {THEME['card_bg']};
                color: {THEME['text']};
            }}
        """)
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(10)

        # Создаем группы
        self._create_general_group(main_layout)
        self._create_cmw_group(main_layout)
        self._create_timeouts_group(main_layout)
        self._create_logging_group(main_layout)

        # Кнопка сохранения
        save_btn = QPushButton("Сохранить настройки")
        save_btn.setObjectName("saveSettingsButton")
        save_btn.setMinimumWidth(150)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1C97EA;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        save_btn.clicked.connect(self._on_save)
        main_layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addStretch()
        self._expanded_widget.setWidget(content_widget)

        self.set_views(self._compact_label, self._expanded_widget)

    def _create_general_group(self, parent_layout):
        group = CollapsibleGroupBox("Общие настройки")
        form = QFormLayout()
        form.setSpacing(8)

        # GOST Version
        cb_gost = QComboBox()
        cb_gost.addItems(["2015", "2023"])
        cb_gost.setCurrentText(self._config.gost_version)
        form.addRow("Версия ГОСТ:", cb_gost)
        self._widgets['gost_version'] = cb_gost

        # TCP Host
        le_host = QLineEdit(self._config.tcp_host)
        form.addRow("TCP Host:", le_host)
        self._widgets['tcp_host'] = le_host

        # TCP Port
        sb_port = QSpinBox()
        sb_port.setRange(1, 65535)
        sb_port.setValue(self._config.tcp_port)
        form.addRow("TCP Port:", sb_port)
        self._widgets['tcp_port'] = sb_port

        group.set_content_layout(form)
        parent_layout.addWidget(group)

    def _create_cmw_group(self, parent_layout):
        group = CollapsibleGroupBox("CMW-500")
        form = QFormLayout()
        form.setSpacing(8)

        # IP
        le_ip = QLineEdit(self._config.cmw500.ip or "")
        form.addRow("IP адрес:", le_ip)
        self._widgets['cmw500.ip'] = le_ip

        # Simulate
        cb_sim = QCheckBox()
        cb_sim.setChecked(self._config.cmw500.simulate)
        form.addRow("Симуляция:", cb_sim)
        self._widgets['cmw500.simulate'] = cb_sim

        # Timeout
        dsb = QDoubleSpinBox()
        dsb.setRange(0.1, 100.0)
        dsb.setValue(self._config.cmw500.timeout)
        dsb.setSuffix(" s")
        form.addRow("Таймаут:", dsb)
        self._widgets['cmw500.timeout'] = dsb

        # Retries
        sb = QSpinBox()
        sb.setRange(0, 10)
        sb.setValue(self._config.cmw500.retries)
        form.addRow("Повторы:", sb)
        self._widgets['cmw500.retries'] = sb

        # SMS Timeout
        dsb_sms = QDoubleSpinBox()
        dsb_sms.setRange(1.0, 60.0)
        dsb_sms.setValue(self._config.cmw500.sms_send_timeout)
        dsb_sms.setSuffix(" s")
        form.addRow("SMS Таймаут:", dsb_sms)
        self._widgets['cmw500.sms_send_timeout'] = dsb_sms

        # Status Poll Interval
        dsb_poll = QDoubleSpinBox()
        dsb_poll.setRange(0.5, 10.0)
        dsb_poll.setValue(self._config.cmw500.status_poll_interval)
        dsb_poll.setSuffix(" s")
        form.addRow("Интервал опроса:", dsb_poll)
        self._widgets['cmw500.status_poll_interval'] = dsb_poll

        # MCC
        sb_mcc = QSpinBox()
        sb_mcc.setRange(0, 999)
        sb_mcc.setValue(self._config.cmw500.mcc)
        form.addRow("MCC:", sb_mcc)
        self._widgets['cmw500.mcc'] = sb_mcc

        # MNC
        sb_mnc = QSpinBox()
        sb_mnc.setRange(0, 999)
        sb_mnc.setValue(self._config.cmw500.mnc)
        form.addRow("MNC:", sb_mnc)
        self._widgets['cmw500.mnc'] = sb_mnc

        # RF Level
        dsb_rf = QDoubleSpinBox()
        dsb_rf.setRange(-120.0, 0.0)
        dsb_rf.setValue(self._config.cmw500.rf_level_tch)
        dsb_rf.setSuffix(" dBm")
        form.addRow("RF Level:", dsb_rf)
        self._widgets['cmw500.rf_level_tch'] = dsb_rf

        # SMS Decoding
        cb_dc = QComboBox()
        cb_dc.addItems(["BIT8", "GSM7", "UCS2"])
        cb_dc.setCurrentText(self._config.cmw500.sms_dcoding)
        form.addRow("SMS Кодировка:", cb_dc)
        self._widgets['cmw500.sms_dcoding'] = cb_dc

        # SMS P-Identifier
        sb_pid = QSpinBox()
        sb_pid.setRange(0, 255)
        sb_pid.setValue(self._config.cmw500.sms_pidentifier)
        form.addRow("SMS P-Id:", sb_pid)
        self._widgets['cmw500.sms_pidentifier'] = sb_pid

        group.set_content_layout(form)
        parent_layout.addWidget(group)

    def _create_timeouts_group(self, parent_layout):
        group = CollapsibleGroupBox("Таймауты")
        form = QFormLayout()
        form.setSpacing(8)

        # TL Response Timeout
        dsb = QDoubleSpinBox()
        dsb.setRange(0.1, 60.0)
        dsb.setValue(self._config.timeouts.tl_response_to)
        dsb.setSuffix(" s")
        form.addRow("Ответ (TL):", dsb)
        self._widgets['timeouts.tl_response_to'] = dsb

        # Resend Attempts
        sb = QSpinBox()
        sb.setRange(1, 10)
        sb.setValue(self._config.timeouts.tl_resend_attempts)
        form.addRow("Попытки (TL):", sb)
        self._widgets['timeouts.tl_resend_attempts'] = sb

        # Reconnect Timeout
        dsb_rec = QDoubleSpinBox()
        dsb_rec.setRange(1.0, 300.0)
        dsb_rec.setValue(self._config.timeouts.tl_reconnect_to)
        dsb_rec.setSuffix(" s")
        form.addRow("Переподкл. (TL):", dsb_rec)
        self._widgets['timeouts.tl_reconnect_to'] = dsb_rec

        # EGTS Not Auth Timeout
        dsb_auth = QDoubleSpinBox()
        dsb_auth.setRange(1.0, 60.0)
        dsb_auth.setValue(self._config.timeouts.egts_sl_not_auth_to)
        dsb_auth.setSuffix(" s")
        form.addRow("Без авториз.:", dsb_auth)
        self._widgets['timeouts.egts_sl_not_auth_to'] = dsb_auth

        group.set_content_layout(form)
        parent_layout.addWidget(group)

    def _create_logging_group(self, parent_layout):
        group = CollapsibleGroupBox("Логирование")
        form = QFormLayout()
        form.setSpacing(8)

        # Level
        cb_level = QComboBox()
        cb_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        cb_level.setCurrentText(self._config.logging.level)
        form.addRow("Уровень:", cb_level)
        self._widgets['logging.level'] = cb_level

        # Dir
        dir_layout = QHBoxLayout()
        le_dir = QLineEdit(self._config.logging.dir)
        btn_dir = QPushButton("...")
        btn_dir.setFixedWidth(30)
        btn_dir.clicked.connect(lambda: self._on_select_dir(le_dir))
        dir_layout.addWidget(le_dir)
        dir_layout.addWidget(btn_dir)
        form.addRow("Директория:", dir_layout)
        self._widgets['logging.dir'] = le_dir

        # Max Size
        sb_size = QSpinBox()
        sb_size.setRange(1, 1000)
        sb_size.setValue(self._config.logging.max_size_mb)
        sb_size.setSuffix(" MB")
        form.addRow("Макс. размер:", sb_size)
        self._widgets['logging.max_size_mb'] = sb_size

        # Retention
        sb_ret = QSpinBox()
        sb_ret.setRange(0, 365)
        sb_ret.setValue(self._config.logging.retention_days)
        sb_ret.setSuffix(" дн.")
        form.addRow("Хранение:", sb_ret)
        self._widgets['logging.retention_days'] = sb_ret

        group.set_content_layout(form)
        parent_layout.addWidget(group)

    def _on_select_dir(self, line_edit: QLineEdit):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию логов")
        if dir_path:
            line_edit.setText(dir_path)

    def _collect_data(self) -> dict[str, Any]:
        """Собрать данные из виджетов в словарь."""
        data = {
            "gost_version": self._widgets['gost_version'].currentText(),
            "tcp_host": self._widgets['tcp_host'].text(),
            "tcp_port": self._widgets['tcp_port'].value(),
            "cmw500": {
                "ip": self._widgets['cmw500.ip'].text() or None,
                "simulate": self._widgets['cmw500.simulate'].isChecked(),
                "timeout": self._widgets['cmw500.timeout'].value(),
                "retries": self._widgets['cmw500.retries'].value(),
                "sms_send_timeout": self._widgets['cmw500.sms_send_timeout'].value(),
                "status_poll_interval": self._widgets['cmw500.status_poll_interval'].value(),
                "mcc": self._widgets['cmw500.mcc'].value(),
                "mnc": self._widgets['cmw500.mnc'].value(),
                "rf_level_tch": self._widgets['cmw500.rf_level_tch'].value(),
                "sms_dcoding": self._widgets['cmw500.sms_dcoding'].currentText(),
                "sms_pidentifier": self._widgets['cmw500.sms_pidentifier'].value(),
            },
            "timeouts": {
                "tl_response_to": self._widgets['timeouts.tl_response_to'].value(),
                "tl_resend_attempts": self._widgets['timeouts.tl_resend_attempts'].value(),
                "tl_reconnect_to": self._widgets['timeouts.tl_reconnect_to'].value(),
                "egts_sl_not_auth_to": self._widgets['timeouts.egts_sl_not_auth_to'].value(),
            },
            "logging": {
                "level": self._widgets['logging.level'].currentText(),
                "dir": self._widgets['logging.dir'].text(),
                "max_size_mb": self._widgets['logging.max_size_mb'].value(),
                "retention_days": self._widgets['logging.retention_days'].value(),
            }
        }
        return data

    @Slot()
    def _on_save(self):
        """Сохранить настройки в файл и уведомить."""
        data = self._collect_data()

        # Сохраняем в settings.json (относительно корня проекта)
        config_path = PROJECT_ROOT / "config" / "settings.json"
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Фильтруем None значения для IP (чтобы не писать "null" в JSON)
            if data["cmw500"]["ip"] is None:
                data["cmw500"]["ip"] = None  # Оставляем None, json.dumps обработает как null

            config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Settings saved to %s", config_path)

            self.settings_changed.emit(data)
            self._update_compact_view()

        except Exception as e:
            logger.error("Failed to save settings: %s", e)

    def _update_compact_view(self):
        port = self._widgets.get('tcp_port', QSpinBox()).value() if 'tcp_port' in self._widgets else self._config.tcp_port
        gost = self._widgets.get('gost_version', QComboBox()).currentText() if 'gost_version' in self._widgets else self._config.gost_version
        self._compact_label.setText(f"Port: {port}, GOST: {gost}")

    def get_state(self) -> dict:
        return {"visible": self.isVisible()}

    def set_state(self, state: dict):
        if state.get("visible", False):
            self.show()
        else:
            self.hide()
