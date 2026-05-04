# OMEGA_EGTS GUI
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication


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
    "font_main": "Segoe UI",
    "font_mono": "Consolas",
    "title_color": "#FFD700",
    "title_size": 13,
}


def generate_qss(theme: dict) -> str:
    font_main = theme.get("font_main", "Segoe UI")
    font_mono = theme.get("font_mono", "Consolas")
    title_color = theme.get("title_color", "#FFD700")
    title_size = theme.get("title_size", 13)
    return f"""
    QMainWindow {{
        background-color: {theme['bg']};
        color: {theme['text']};
        font-family: "{font_main}";
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
    QLabel {{
        color: {theme['text']};
        font-family: "{font_main}";
    }}
    QLabel[class="title"] {{
        color: {title_color};
        font-family: "{font_main}";
        font-size: {title_size}px;
        font-weight: bold;
    }}
    QPushButton {{
        background-color: {theme['accent']};
        color: white;
        border: none;
        border-radius: 3px;
        padding: 4px 12px;
        font-family: "{font_main}";
    }}
    QPushButton:hover {{
        background-color: {theme['accent_hover']};
    }}
    QTableWidget, QTableView {{
        background-color: {theme['card_bg']};
        gridline-color: {theme['border']};
        font-family: "{font_mono}";
    }}
    QHeaderView::section {{
        background-color: {theme['header_bg']};
        color: {theme['text']};
        border: none;
        font-family: "{font_main}";
    }}
    QGroupBox {{
        color: {theme['text']};
        border: 1px solid {theme['border']};
        margin-top: 10px;
        font-family: "{font_main}";
    }}
    QGroupBox::title {{
        color: {theme['text']};
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }}
    QComboBox {{
        background-color: {theme['input_bg']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
        padding: 2px 8px;
        border-radius: 3px;
        font-family: "{font_main}";
    }}
    QPlainTextEdit, QTextEdit {{
        background-color: {theme['input_bg']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
        border-radius: 3px;
        font-family: "{font_mono}";
    }}
    """


def apply_theme(app, theme_name: str = "vscode_dark"):
    """Apply theme to QApplication."""
    if theme_name == "vscode_dark":
        theme = THEME_VSCODE_DARK
    else:
        theme = THEME_VSCODE_DARK
    app.setStyleSheet(generate_qss(theme))
    _setup_fonts(app, theme)


def _setup_fonts(app, theme):
    """Setup application fonts."""
    font_main = QFont(theme.get("font_main", "Segoe UI"), 10)
    app.setFont(font_main)


def contrast_ratio(bg: str, fg: str) -> float:
    """Calculate contrast ratio between two colors (WCAG 2.0)."""
    bg_luminance = _relative_luminance(QColor(bg))
    fg_luminance = _relative_luminance(QColor(fg))
    lighter = max(bg_luminance, fg_luminance)
    darker = min(bg_luminance, fg_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(color: QColor) -> float:
    """Calculate relative luminance of a color."""
    r, g, b = color.redF(), color.greenF(), color.blueF()
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def validate_contrast(theme: dict) -> bool:
    """Validate that theme meets WCAG AA contrast requirements (4.5:1)."""
    bg = theme.get("bg", "#FFFFFF")
    text = theme.get("text", "#000000")
    ratio = contrast_ratio(bg, text)
    return ratio >= 4.5
