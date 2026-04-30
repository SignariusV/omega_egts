from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit,
    QPushButton, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QFileInfo
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor

from gui.utils.validators import validate_json_string


class JsonHighlighter(QSyntaxHighlighter):
    """Подсветка синтаксиса JSON."""

    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

        # Ключевые слова (ключи JSON)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))  # Синий
        self.highlighting_rules.append(('"[^"]*":', keyword_format))  # Ключи

        # Строковые значения
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))  # Оранжевый
        self.highlighting_rules.append(('"[^"]*"', string_format))

        # Числа
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))  # Зелёный
        self.highlighting_rules.append(("\\b\\d+\\b", number_format))

        # Ключевые слова true, false, null
        literal_format = QTextCharFormat()
        literal_format.setForeground(QColor("#569CD6"))
        self.highlighting_rules.append(("\\b(true|false|null)\\b", literal_format))

    def highlightBlock(self, text):
        import re
        for pattern, format in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class EditorTab(QWidget):
    """Вкладка 'Редактор сценариев' — создание и редактирование JSON-сценариев."""

    def __init__(self):
        super().__init__()
        self.current_file = None
        self._init_ui()
        self._load_templates()
        self._load_scenarios_tree()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel("✏️ РЕДАКТОР СЦЕНАРИЕВ")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title)

        # Главный горизонтальный лайаут
        main_layout = QHBoxLayout()

        # Левая панель
        left_panel = QVBoxLayout()

        # Дерево сценариев
        scenarios_group = QGroupBox("📁 СЦЕНАРИИ")
        scenarios_group.setStyleSheet(self._group_style())
        scenarios_layout = QVBoxLayout(scenarios_group)

        self.scenarios_tree = QTreeWidget()
        self.scenarios_tree.setHeaderLabels(["Сценарии"])
        self.scenarios_tree.setStyleSheet(self._tree_style())
        self.scenarios_tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        scenarios_layout.addWidget(self.scenarios_tree)

        # Кнопка создания
        self.create_btn = QPushButton("➕ Создать")
        self.create_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.create_btn.clicked.connect(self._on_create_scenario)
        scenarios_layout.addWidget(self.create_btn)

        left_panel.addWidget(scenarios_group)

        # Блок шаблонов
        templates_group = QGroupBox("ШАБЛОНЫ")
        templates_group.setStyleSheet(self._group_style())
        templates_layout = QVBoxLayout(templates_group)

        self.templates_list = QTreeWidget()
        self.templates_list.setHeaderLabels(["Шаблоны"])
        self.templates_list.setStyleSheet(self._tree_style())
        self.templates_list.itemDoubleClicked.connect(self._on_template_double_clicked)
        templates_layout.addWidget(self.templates_list)

        left_panel.addWidget(templates_group)
        main_layout.addLayout(left_panel)

        # Правая панель
        right_panel = QVBoxLayout()

        # Заголовок файла
        self.file_label = QLabel("Файл не выбран")
        self.file_label.setStyleSheet("color: #CCCCCC; font-style: italic;")
        right_panel.addWidget(self.file_label)

        # Редактор JSON
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 11))
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #3C3C3C;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 10px;
            }
        """)
        self.highlighter = JsonHighlighter(self.editor.document())
        right_panel.addWidget(self.editor)

        # Кнопки действий
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Сохранить")
        self.save_btn.setStyleSheet(self._btn_style("#00AA00"))
        self.save_btn.clicked.connect(self._on_save)

        self.check_btn = QPushButton("✅ Проверить")
        self.check_btn.setStyleSheet(self._btn_style("#0078D7"))
        self.check_btn.clicked.connect(self._on_check)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.check_btn)
        btn_layout.addStretch()
        right_panel.addLayout(btn_layout)

        main_layout.addLayout(right_panel)
        layout.addLayout(main_layout)

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

    def _tree_style(self):
        return """
            QTreeWidget {
                background-color: #3C3C3C;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
            QTreeWidget::item {
                padding: 5px;
                border-bottom: 1px solid #555555;
            }}
            QTreeWidget::item:selected {
                background-color: #3E5F8A;
            }}
        """

    def _load_scenarios_tree(self):
        """Загрузка дерева сценариев из папки scenarios/."""
        self.scenarios_tree.clear()
        scenarios_dir = Path("scenarios")
        if not scenarios_dir.exists():
            return

        for path in scenarios_dir.iterdir():
            if path.is_dir():
                item = QTreeWidgetItem(self.scenarios_tree, [path.name])
                item.setData(0, Qt.UserRole, str(path))

                # Добавляем подэлементы (файлы)
                scenario_file = path / "scenario.json"
                if scenario_file.exists():
                    child = QTreeWidgetItem(item, ["scenario.json"])
                    child.setData(0, Qt.UserRole, str(scenario_file))

    def _load_templates(self):
        """Загрузка списка шаблонов."""
        templates = ["Авторизация", "Телеметрия", "Траектория", "eCall", "Обновление ПО"]
        for name in templates:
            item = QTreeWidgetItem(self.templates_list, [name])

    def _on_tree_item_double_clicked(self, item, column):
        """Открытие файла сценария при двойном клике."""
        file_path = item.data(0, Qt.UserRole)
        if file_path and Path(file_path).is_file():
            self._load_file(file_path)

    def _on_template_double_clicked(self, item, column):
        """Создание сценария из шаблона."""
        template_name = item.text(0)
        QMessageBox.information(
            self, "Шаблон",
            f"Создание сценария из шаблона '{template_name}' пока не реализовано"
        )

    def _on_create_scenario(self):
        """Создание нового сценария."""
        self.current_file = None
        self.file_label.setText("Новый сценарий")
        self.editor.setPlainText('{\n    "name": "",\n    "version": "1",\n    "timeout": 60,\n    "steps": []\n}')
        QMessageBox.information(self, "Создание", "Создан новый пустой сценарий")

    def _load_file(self, file_path):
        """Загрузка файла в редактор."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.editor.setPlainText(content)
            self.current_file = file_path
            self.file_label.setText(f"Файл: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить файл: {e}")

    def _on_save(self):
        """Сохранение файла."""
        if not self.current_file:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить сценарий", "", "JSON Files (*.json)"
            )
            if not file_path:
                return
            self.current_file = file_path

        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.file_label.setText(f"Файл: {self.current_file}")
            QMessageBox.information(self, "Сохранение", "Файл успешно сохранён")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить файл: {e}")

    def _on_check(self):
        """Валидация сценария."""
        content = self.editor.toPlainText()
        is_valid, result = validate_json_string(content)

        if is_valid:
            QMessageBox.information(
                self, "Проверка",
                "Сценарий корректен!\n\n" + "\n".join(f"{k}: {v}" for k, v in result.items()) if isinstance(result, dict) else "OK"
            )
        else:
            error_msg = result if isinstance(result, str) else "\n".join(result)
            QMessageBox.warning(self, "Ошибка валидации", error_msg)
