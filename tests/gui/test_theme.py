# OMEGA_EGTS GUI
import pytest
from gui.utils.theme import (
    THEME_VSCODE_DARK,
    generate_qss,
    contrast_ratio,
    validate_contrast
)


def test_contrast_meets_aa():
    """Test that theme meets WCAG AA contrast requirements (4.5:1)."""
    ratio = contrast_ratio("#1E1E1E", "#CCCCCC")
    assert ratio >= 4.5, f"Text contrast ratio {ratio:.2f} is below WCAG AA threshold of 4.5"


def test_contrast_edge_cases():
    """Test contrast ratio calculation with edge cases."""
    # White on black
    ratio = contrast_ratio("#000000", "#FFFFFF")
    assert ratio >= 4.5

    # Same color (should be 1.0)
    ratio = contrast_ratio("#FF0000", "#FF0000")
    assert ratio == 1.0


def test_validate_contrast_function():
    """Test the validate_contrast function."""
    assert validate_contrast(THEME_VSCODE_DARK) is True


def test_qss_contains_colors():
    """Test that generated QSS contains expected color values."""
    qss = generate_qss(THEME_VSCODE_DARK)
    assert "#1E1E1E" in qss
    assert "#CCCCCC" in qss
    assert "#007ACC" in qss


def test_qss_contains_fonts():
    """Test that generated QSS contains font-family settings."""
    qss = generate_qss(THEME_VSCODE_DARK)
    assert "Segoe UI" in qss
    assert "Consolas" in qss


def test_qss_dark_theme_structure():
    """Test that QSS has proper structure for dark theme."""
    qss = generate_qss(THEME_VSCODE_DARK)
    assert "QMainWindow" in qss
    assert "QPushButton" in qss
    assert "QTableWidget" in qss
    assert "QGroupBox" in qss
