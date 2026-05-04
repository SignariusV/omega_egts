# OMEGA_EGTS GUI
from PySide6.QtGui import QColor


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
    "input_bg": "#3C3C3C"
}


def generate_qss(theme: dict) -> str:
    return f"""
    QMainWindow {{
        background-color: {theme['bg']};
        color: {theme['text']};
    }}
    QFrame {{
        border: 1px solid {theme['border']};
        border-radius: 4px;
    }}
    QFrame[class="CardWidget"] {{
        background-color: {theme['card_bg']};
        border: 1px solid {theme['border']};
        border-radius: 6px;
    }}
    QFrame[class="TitleBar"] {{
        background-color: {theme['title_bg']};
        border-bottom: 1px solid {theme['border']};
    }}
    QPushButton {{
        background-color: {theme['accent']};
        color: white;
        border: none;
        border-radius: 3px;
        padding: 4px 12px;
    }}
    QPushButton:hover {{
        background-color: {theme['accent_hover']};
    }}
    QTableWidget, QTableView {{
        background-color: {theme['card_bg']};
        gridline-color: {theme['border']};
    }}
    QHeaderView::section {{
        background-color: {theme['header_bg']};
        color: {theme['text']};
        border: none;
    }}
    QGroupBox {{
        color: {theme['text']};
        border: 1px solid {theme['border']};
        margin-top: 10px;
    }}
    QGroupBox::title {{
        color: {theme['text']};
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }}
    QLabel {{
        color: {theme['text']};
    }}
    QComboBox {{
        background-color: {theme['input_bg']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
        padding: 2px 8px;
        border-radius: 3px;
    }}
    QPlainTextEdit, QTextEdit {{
        background-color: {theme['input_bg']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
        border-radius: 3px;
    }}
    """


def apply_theme(app, theme_name: str = "vscode_dark"):
    """Apply theme to QApplication."""
    if theme_name == "vscode_dark":
        theme = THEME_VSCODE_DARK
    else:
        theme = THEME_VSCODE_DARK
    app.setStyleSheet(generate_qss(theme))
