from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QStackedWidget, QStatusBar, QLabel, QFrame,
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtGui import QFont

from gui.dialogs.about_dialog import AboutDialog
from gui.dialogs.settings_dialog import SettingsDialog

from gui.tabs.connection_tab import ConnectionTab
from gui.tabs.scenarios_tab import ScenariosTab
from gui.tabs.editor_tab import EditorTab
from gui.tabs.logs_tab import LogsTab
from gui.tabs.export_tab import ExportTab


class MainWindow(QMainWindow):
    """Главное окно приложения OMEGA_EGTS."""

    def __init__(self, engine_wrapper, event_bridge):
        super().__init__()
        self.engine_wrapper = engine_wrapper
        self.event_bridge = event_bridge
        self.tabs = {}
        self._load_styles()
        self._init_ui()
        self._connect_signals()
        self._start_clock()

    def _load_styles(self):
        """Загрузка QSS стилей."""
        style_path = Path(__file__).parent / "resources" / "styles.qss"
        if style_path.exists():
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            print(f"WARNING: Stylesheet not found at {style_path}")

    def _init_ui(self):
        self.setWindowTitle("OMEGA_EGTS - Тестер УСВ")
        self.setMinimumSize(1200, 800)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Общий вертикальный лайаут
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Верхняя панель (top bar)
        self._init_top_bar(central_layout)

        # Главный горизонтальный лайаут
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_layout.addLayout(main_layout)

        # Боковое меню
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(120)
        self.sidebar.setStyleSheet("""
            QListWidget {
                background-color: #3C3C3C;
                border: none;
                color: #CCCCCC;
                font-size: 12pt;
            }
            QListWidget::item {
                padding: 15px;
                border-bottom: 1px solid #555555;
            }
            QListWidget::item:selected {
                background-color: #2B2B2B;
                color: #FFFFFF;
                border-left: 3px solid #0078D7;
            }
        """)

        # Добавляем пункты меню
        items = [
            ("🔌", "Подключение"),
            ("📝", "Сценарии"),
            ("✏️", "Редактор"),
            ("📋", "Логи"),
            ("💾", "Экспорт")
        ]
        for icon, text in items:
            self.sidebar.addItem(f"{icon}\n{text}")

        main_layout.addWidget(self.sidebar)

        # Разделительная линия
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet("color: #555555;")
        main_layout.addWidget(line)

        # Область контента (вкладки)
        self.stack = QStackedWidget()

        # Создаем вкладки
        self.connection_tab = ConnectionTab(self.engine_wrapper, self.event_bridge)
        self.stack.addWidget(self.connection_tab)

        # Вкладка "Сценарии"
        self.scenarios_tab = ScenariosTab(self.engine_wrapper, self.event_bridge)
        self.stack.addWidget(self.scenarios_tab)

        # Вкладка "Редактор"
        self.editor_tab = EditorTab()
        self.stack.addWidget(self.editor_tab)

        # Вкладка "Логи"
        self.logs_tab = LogsTab()
        self.stack.addWidget(self.logs_tab)

        # Вкладка "Экспорт"
        self.export_tab = ExportTab()
        self.stack.addWidget(self.export_tab)

        main_layout.addWidget(self.stack)

        # Подключаем сигнал выбора пункта меню
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        # Инициализация строки состояния
        self._init_status_bar()

    def _init_top_bar(self, central_layout):
        """Инициализация верхней панели с кнопками."""
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(10, 10, 10, 10)

        # Логотип / название
        title = QLabel("☰  OMEGA_EGTS - Тестер УСВ")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        top_layout.addWidget(title)
        top_layout.addStretch()

        # Кнопки справа
        self.lang_btn = QPushButton("🌐 RU")
        self.lang_btn.setStyleSheet(self._small_btn_style())
        self.lang_btn.clicked.connect(self._on_lang_clicked)
        top_layout.addWidget(self.lang_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setStyleSheet(self._small_btn_style())
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        top_layout.addWidget(self.settings_btn)

        self.help_btn = QPushButton("❓")
        self.help_btn.setStyleSheet(self._small_btn_style())
        self.help_btn.clicked.connect(self._on_help_clicked)
        top_layout.addWidget(self.help_btn)

        top_layout.addWidget(QLabel("─"))  # Разделитель

        self.min_btn = QPushButton("─")
        self.min_btn.setStyleSheet(self._small_btn_style())
        self.min_btn.clicked.connect(self.showMinimized)
        top_layout.addWidget(self.min_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setStyleSheet(self._small_btn_style("#FF5555"))
        self.close_btn.clicked.connect(self.close)
        top_layout.addWidget(self.close_btn)

        central_layout.addLayout(top_layout)

    def _small_btn_style(self, bg_color="#3C3C3C"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: #CCCCCC;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ background-color: #555555; }}
        """

    def _on_lang_clicked(self):
        """Переключение языка (заглушка)."""
        QMessageBox.information(self, "Язык", "Переключение языка пока не реализовано")

    def _on_settings_clicked(self):
        """Открытие диалога настроек."""
        dialog = SettingsDialog(self)
        dialog.exec()

    def _on_help_clicked(self):
        """Открытие диалога 'О программе'."""
        dialog = AboutDialog(self)
        dialog.exec()

    def _init_status_bar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #323232;
                color: #CCCCCC;
                border-top: 1px solid #555555;
            }
        """)

        # Статус сервера
        self.server_status_label = QLabel("🔴 Остановлен")
        self.status_bar.addWidget(self.server_status_label)

        # Количество подключений
        self.connections_label = QLabel("Подключений: 0")
        self.connections_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.connections_label)

        # Количество пакетов
        self.packets_label = QLabel("Пакетов: 0")
        self.packets_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.packets_label)

        # Время
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignRight)
        self.status_bar.addPermanentWidget(self.time_label)

        self.setStatusBar(self.status_bar)

    def _start_clock(self):
        """Обновление часов в статусбаре."""
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_clock)
        self.timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        current_time = QTime.currentTime().toString("HH:mm:ss")
        self.time_label.setText(current_time)

    def _connect_signals(self):
        """Подключение сигналов EventBridge."""
        self.event_bridge.server_started.connect(self._on_server_started)
        self.event_bridge.server_stopped.connect(self._on_server_stopped)

    def _on_server_started(self, data: dict):
        self.server_status_label.setText("🟢 Активен")

    def _on_server_stopped(self, data: dict):
        self.server_status_label.setText("🔴 Остановлен")
