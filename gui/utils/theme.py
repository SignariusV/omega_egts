# OMEGA_EGTS GUI
import os
from pathlib import Path
from typing import Optional

THEME_VSCODE_DARK = {
    "bg": "#1E1E1E",
    "card_bg": "#252526",
    "border": "#3E3E42",
    "text": "#CCCCCC",
    "accent": "#007ACC",
    "accent_hover": "#1C97EA",
    "success": "#4EC9B0",
    "warning": "#CE9178",
    "error": "#F44747",
    "title_bg": "#2D2D30",
    "header_bg": "#333333",
    "input_bg": "#3C3C3C",
}

THEMES = {
    "vscode_dark": THEME_VSCODE_DARK,
}

DEFAULT_THEME = THEME_VSCODE_DARK


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _luminance(r: int, g: int, b: int) -> float:
    rs = r / 255.0
    gs = g / 255.0
    bs = b / 255.0
    rs = rs / 12.92 if rs <= 0.03928 else ((rs + 0.055) / 1.055) ** 2.4
    gs = gs / 12.92 if gs <= 0.03928 else ((gs + 0.055) / 1.055) ** 2.4
    bs = bs / 12.92 if bs <= 0.03928 else ((bs + 0.055) / 1.055) ** 2.4
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs


def contrast_ratio(bg: str, fg: str) -> float:
    bg_rgb = _hex_to_rgb(bg)
    fg_rgb = _hex_to_rgb(fg)
    l1 = _luminance(*bg_rgb)
    l2 = _luminance(*fg_rgb)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def validate_contrast(theme: dict, min_ratio: float = 4.5) -> bool:
    return contrast_ratio(theme['bg'], theme['text']) >= min_ratio


def load_base_qss() -> str:
    base_path = Path(__file__).parent.parent / "resources" / "styles" / "base.qss"
    if base_path.exists():
        return base_path.read_text(encoding='utf-8')
    return ""


def generate_qss(theme: Optional[dict] = None) -> str:
    if theme is None:
        theme = DEFAULT_THEME

    return f"""
    QMainWindow {{
        background-color: {theme['bg']};
        color: {theme['text']};
    }}
    QWidget {{
        background-color: {theme['bg']};
        color: {theme['text']};
    }}
    QFrame {{
        border: 1px solid {theme['border']};
        border-radius: 4px;
    }}
    .CardWidget {{
        background-color: {theme['card_bg']};
        border: 1px solid {theme['border']};
        border-radius: 6px;
    }}
    .TitleBar {{
        background-color: {theme['title_bg']};
        border-bottom: 1px solid {theme['border']};
    }}
    QLabel {{
        color: {theme['text']};
        background-color: transparent;
    }}
    QPushButton {{
        background-color: {theme['accent']};
        color: white;
        border: none;
        border-radius: 3px;
        padding: 4px 12px;
        font-family: "Segoe UI", sans-serif;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {theme['accent_hover']};
    }}
    QPushButton:pressed {{
        background-color: {theme['accent']};
        padding: 5px 11px 3px 13px;
    }}
    QPushButton:disabled {{
        background-color: {theme['input_bg']};
        color: {theme['border']};
    }}
    QToolButton {{
        background-color: transparent;
        color: {theme['text']};
        border: none;
        border-radius: 2px;
        padding: 2px;
    }}
    QToolButton:hover {{
        background-color: {theme['input_bg']};
    }}
    QComboBox {{
        background-color: {theme['input_bg']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
        border-radius: 3px;
        padding: 4px 8px;
    }}
    QComboBox:hover {{
        border: 1px solid {theme['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid {theme['text']};
        margin-right: 4px;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {theme['input_bg']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
        border-radius: 3px;
        padding: 4px;
        font-family: "Consolas", monospace;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {theme['accent']};
    }}
    QTableWidget, QTableView {{
        background-color: {theme['card_bg']};
        color: {theme['text']};
        gridline-color: {theme['border']};
        border: 1px solid {theme['border']};
        font-family: "Consolas", monospace;
        font-size: 11px;
    }}
    QHeaderView::section {{
        background-color: {theme['header_bg']};
        color: {theme['text']};
        border: none;
        border-right: 1px solid {theme['border']};
        border-bottom: 1px solid {theme['border']};
        padding: 4px 8px;
        font-weight: bold;
    }}
    QScrollBar:vertical {{
        background-color: {theme['bg']};
        width: 12px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background-color: {theme['border']};
        border-radius: 6px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {theme['text']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: {theme['bg']};
        height: 12px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {theme['border']};
        border-radius: 6px;
        min-width: 20px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {theme['text']};
    }}
    QStatusBar {{
        background-color: {theme['title_bg']};
        color: {theme['text']};
        border-top: 1px solid {theme['border']};
    }}
    QMenuBar {{
        background-color: {theme['title_bg']};
        color: {theme['text']};
        border-bottom: 1px solid {theme['border']};
    }}
    QMenuBar::item:selected {{
        background-color: {theme['accent']};
    }}
    QMenu {{
        background-color: {theme['card_bg']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
    }}
    QMenu::item:selected {{
        background-color: {theme['accent']};
    }}
    QGroupBox {{
        border: 1px solid {theme['border']};
        border-radius: 4px;
        margin-top: 8px;
        font-weight: bold;
        color: {theme['text']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 4px;
    }}
    QProgressBar {{
        background-color: {theme['input_bg']};
        border: 1px solid {theme['border']};
        border-radius: 4px;
        text-align: center;
        color: {theme['text']};
    }}
    QProgressBar::chunk {{
        background-color: {theme['accent']};
        border-radius: 3px;
    }}
    QCheckBox {{
        color: {theme['text']};
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {theme['border']};
        border-radius: 3px;
        background-color: {theme['input_bg']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {theme['accent']};
        border-color: {theme['accent']};
    }}
    QRadioButton {{
        color: {theme['text']};
    }}
    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {theme['border']};
        border-radius: 8px;
        background-color: {theme['input_bg']};
    }}
    QRadioButton::indicator:checked {{
        border: 4px solid {theme['accent']};
    }}
    QTabWidget::pane {{
        border: 1px solid {theme['border']};
        background-color: {theme['card_bg']};
    }}
    QTabBar::tab {{
        background-color: {theme['title_bg']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
        padding: 6px 12px;
    }}
    QTabBar::tab:selected {{
        background-color: {theme['card_bg']};
        border-bottom: 2px solid {theme['accent']};
    }}
    """


def apply_theme(app, theme: Optional[dict] = None) -> None:
    base = load_base_qss()
    dynamic = generate_qss(theme)
    app.setStyleSheet(base + dynamic)