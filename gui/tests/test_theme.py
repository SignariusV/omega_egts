# OMEGA_EGTS GUI
import pytest
from gui.utils.theme import (
    THEME_VSCODE_DARK,
    generate_qss,
    contrast_ratio,
    validate_contrast,
    load_base_qss,
    apply_theme,
    DEFAULT_THEME,
)


class TestContrastRatio:
    def test_white_on_black(self):
        ratio = contrast_ratio("#000000", "#FFFFFF")
        assert ratio == 21.0

    def test_black_on_white(self):
        ratio = contrast_ratio("#FFFFFF", "#000000")
        assert ratio == 21.0

    def test_same_colors(self):
        ratio = contrast_ratio("#CCCCCC", "#CCCCCC")
        assert ratio == 1.0

    def test_vscode_dark_text_on_bg(self):
        ratio = contrast_ratio(THEME_VSCODE_DARK["bg"], THEME_VSCODE_DARK["text"])
        assert ratio >= 4.5


class TestValidateContrast:
    def test_valid_theme(self):
        assert validate_contrast(THEME_VSCODE_DARK) is True

    def test_invalid_theme_low_contrast(self):
        bad_theme = {"bg": "#FFFFFF", "text": "#DDDDDD"}
        assert validate_contrast(bad_theme, min_ratio=4.5) is False

    def test_custom_min_ratio(self):
        assert validate_contrast(THEME_VSCODE_DARK, min_ratio=3.0) is True


class TestGenerateQSS:
    def test_contains_background(self):
        qss = generate_qss(THEME_VSCODE_DARK)
        assert "#1E1E1E" in qss

    def test_contains_card_background(self):
        qss = generate_qss(THEME_VSCODE_DARK)
        assert "#252526" in qss

    def test_contains_accent_color(self):
        qss = generate_qss(THEME_VSCODE_DARK)
        assert "#007ACC" in qss

    def test_contains_text_color(self):
        qss = generate_qss(THEME_VSCODE_DARK)
        assert "#CCCCCC" in qss

    def test_contains_QMainWindow(self):
        qss = generate_qss(THEME_VSCODE_DARK)
        assert "QMainWindow" in qss

    def test_contains_QPushButton(self):
        qss = generate_qss(THEME_VSCODE_DARK)
        assert "QPushButton" in qss

    def test_contains_QTableWidget(self):
        qss = generate_qss(THEME_VSCODE_DARK)
        assert "QTableWidget" in qss

    def test_default_theme_used(self):
        qss = generate_qss()
        assert "#1E1E1E" in qss


class TestLoadBaseQSS:
    def test_returns_string(self):
        qss = load_base_qss()
        assert isinstance(qss, str)

    def test_returns_empty_for_missing_file(self, monkeypatch):
        import gui.utils.theme as theme_module
        original_read_text = None

        def mock_read_text(self, encoding=None):
            return ""

        import pathlib
        monkeypatch.setattr(pathlib.Path, "read_text", mock_read_text)
        qss = load_base_qss()
        assert qss == ""


class TestApplyTheme:
    def test_apply_theme_sets_stylesheet(self, qtbot):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        apply_theme(app)
        assert len(app.styleSheet()) > 0