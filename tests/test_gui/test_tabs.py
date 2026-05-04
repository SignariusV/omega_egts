import pytest
from PySide6.QtWidgets import QApplication, QTreeWidgetItem
from PySide6.QtCore import Qt

from gui.tabs.editor_tab import EditorTab, JsonHighlighter
from gui.utils.validators import validate_json_string
from gui.tabs.logs_tab import LogsTab


@pytest.fixture
def editor_tab(qtbot, monkeypatch):
    """Экземпляр EditorTab с замоканным QMessageBox."""
    import PySide6.QtWidgets
    monkeypatch.setattr(PySide6.QtWidgets.QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(PySide6.QtWidgets.QMessageBox, "warning", lambda *args, **kwargs: None)
    tab = EditorTab()
    qtbot.addWidget(tab)
    return tab


@pytest.fixture
def logs_tab(qtbot):
    """Экземпляр LogsTab."""
    tab = LogsTab()
    qtbot.addWidget(tab)
    return tab


class TestEditorTab:
    """Тесты для EditorTab."""

    def test_initial_state(self, editor_tab):
        """Проверка начального состояния."""
        assert "Файл не выбран" in editor_tab.file_label.text()
        assert editor_tab.current_file is None
        assert editor_tab.editor.toPlainText() == ""

    def test_create_scenario(self, editor_tab):
        """Проверка создания нового сценария."""
        editor_tab._on_create_scenario()
        assert "Новый сценарий" in editor_tab.file_label.text()
        assert "name" in editor_tab.editor.toPlainText()

    def test_load_file(self, editor_tab, tmp_path):
        """Проверка загрузки файла."""
        import json
        test_file = tmp_path / "test_scenario.json"
        test_data = {"name": "Test", "version": "1", "steps": []}
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        editor_tab._load_file(str(test_file))
        assert "test_scenario.json" in editor_tab.file_label.text()
        assert "Test" in editor_tab.editor.toPlainText()

    def test_validate_valid(self, editor_tab):
        """Проверка валидации корректного сценария."""
        valid_json = '{"name": "Test", "version": "1", "steps": []}'
        editor_tab.editor.setPlainText(valid_json)
        is_valid, result = validate_json_string(valid_json)
        assert is_valid
        assert isinstance(result, dict)

    def test_validate_invalid(self, editor_tab):
        """Проверка валидации некорректного JSON."""
        invalid_json = '{"name": "Test", "version": "1",}'
        editor_tab.editor.setPlainText(invalid_json)
        is_valid, result = validate_json_string(invalid_json)
        assert not is_valid
        assert "Ошибка разбора JSON" in result


class TestLogsTab:
    """Тесты для LogsTab."""

    def test_initial_state(self, logs_tab):
        """Проверка начального состояния."""
        assert "Всего записей: 4" in logs_tab.info_label.text()
        assert logs_tab.log_table.rowCount() == 4

    def test_add_log(self, logs_tab):
        """Проверка добавления записи."""
        initial_count = logs_tab.log_table.rowCount()
        logs_tab.add_log("INFO", "test.source", "Test message")
        assert logs_tab.log_table.rowCount() == initial_count + 1
        assert "Test message" in logs_tab.log_table.item(initial_count, 3).text()

    def test_filter_level(self, logs_tab):
        """Проверка фильтра по уровню."""
        logs_tab.level_combo.setCurrentText("ERROR")
        # Должны остаться только ERROR
        for row in range(logs_tab.log_table.rowCount()):
            if not logs_tab.log_table.isRowHidden(row):
                item = logs_tab.log_table.item(row, 2)
                assert item.text() == "ERROR"

    def test_filter_text(self, logs_tab):
        """Проверка текстового поиска."""
        # Сначала сбрасываем фильтр уровня, чтобы видеть все записи
        logs_tab.level_combo.setCurrentText("ALL")
        logs_tab.search_edit.setText("timeout")
        # Должна найтись запись с "timeout"
        found = False
        for row in range(logs_tab.log_table.rowCount()):
            if not logs_tab.log_table.isRowHidden(row):
                found = True
                break
        assert found

    def test_clear_logs(self, logs_tab):
        """Проверка очистки логов."""
        initial_count = logs_tab.log_table.rowCount()
        assert initial_count > 0
        logs_tab._on_clear()
        assert logs_tab.log_table.rowCount() == 0
        assert "Всего записей: 0" in logs_tab.info_label.text()


class TestJsonHighlighter:
    """Тесты для подсветки синтаксиса."""

    def test_highlighter_exists(self, editor_tab):
        """Проверка создания подсветки."""
        assert editor_tab.highlighter is not None
        assert isinstance(editor_tab.highlighter, JsonHighlighter)
