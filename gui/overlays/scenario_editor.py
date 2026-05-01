# OMEGA_EGTS GUI
import json
import re
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class JsonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []
        self._setup_rules()

    def _setup_rules(self):
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#9CDCFE"))
        self._rules.append((re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"\s*:'), key_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self._rules.append((re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"'), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self._rules.append((re.compile(r'\b\d+\.?\d*\b'), number_format))

        bracket_format = QTextCharFormat()
        bracket_format.setForeground(QColor("#FFD700"))
        self._rules.append((re.compile(r'[\[\]{}]'), bracket_format))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class ScenarioEditorOverlay(QDialog):
    def __init__(self, file_path: str = None, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._original_content = ""
        self._setup_ui()
        if file_path:
            self._load_file(file_path)

    def _setup_ui(self):
        self.setWindowTitle("Scenario Editor")
        self.resize(700, 500)
        layout = QVBoxLayout(self)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #808080;")
        layout.addWidget(self._status_label)

        self._text_edit = QPlainTextEdit()
        self._text_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        self._highlighter = JsonSyntaxHighlighter(self._text_edit.document())
        layout.addWidget(self._text_edit)

        buttons = QHBoxLayout()
        self._validate_btn = QPushButton("Validate")
        self._validate_btn.clicked.connect(self._on_validate)
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._validate_btn)
        buttons.addStretch()
        buttons.addWidget(self._save_btn)
        buttons.addWidget(self._cancel_btn)
        layout.addLayout(buttons)

    def _load_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._text_edit.setPlainText(content)
            self._original_content = content
            self._status_label.setText(f"Loaded: {path}")
        except Exception as e:
            self._status_label.setText(f"Error loading file: {e}")

    def _on_validate(self):
        content = self._text_edit.toPlainText()
        try:
            data = json.loads(content)
            errors, warnings = self._validate_scenario(data)
            if errors:
                self._status_label.setText(f"Errors: {', '.join(errors)}")
                self._status_label.setStyleSheet("color: #F44747;")
            elif warnings:
                self._status_label.setText(f"Warnings: {', '.join(warnings)}")
                self._status_label.setStyleSheet("color: #CE9178;")
            else:
                self._status_label.setText("Valid JSON")
                self._status_label.setStyleSheet("color: #4EC9B0;")
        except json.JSONDecodeError as e:
            self._status_label.setText(f"JSON Error: {e}")
            self._status_label.setStyleSheet("color: #F44747;")

    def _validate_scenario(self, data: dict) -> tuple[list[str], list[str]]:
        errors = []
        warnings = []
        if "name" not in data:
            errors.append("Missing 'name' field")
        if "version" not in data:
            warnings.append("Missing 'version' field")
        if "steps" in data:
            if not isinstance(data["steps"], list):
                errors.append("'steps' must be an array")
            else:
                for i, step in enumerate(data["steps"]):
                    if not isinstance(step, dict):
                        errors.append(f"Step {i} must be an object")
                    elif "type" not in step:
                        errors.append(f"Step {i} missing 'type'")
        return errors, warnings

    def _on_save(self):
        content = self._text_edit.toPlainText()
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Invalid JSON", f"Cannot save: {e}")
            return

        if self._file_path:
            try:
                with open(self._file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self._original_content = content
                self._status_label.setText("Saved successfully")
                self._status_label.setStyleSheet("color: #4EC9B0;")
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Scenario", "", "JSON (*.json)"
            )
            if path:
                self._file_path = path
                self._on_save()

    def get_content(self) -> str:
        return self._text_edit.toPlainText()