# OMEGA_EGTS GUI Tests
"""Integration tests for SettingsCard in the dashboard."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton
from gui.main_window import MainWindow
from gui.dashboard.cards.settings import SettingsCard
from core.config import Config


def test_settings_button_in_sidebar(qtbot):
    """Test that settings card button appears in sidebar."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    sidebar = window._sidebar

    # Check that button for settings exists
    assert "settings" in sidebar._buttons

    btn = sidebar._buttons["settings"]
    assert btn is not None
    assert btn.isCheckable()


def test_settings_card_creation(qtbot):
    """Test that SettingsCard initializes correctly and is hidden by default."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    card = window._settings_card
    # Card should be hidden initially (by hide() in MainWindow after add_card)
    # Since we called hide() after add_card, it should be in hidden_cards
    container = window._dashboard
    assert "settings" not in container._cards
    assert "settings" in container._hidden_cards


def test_settings_save_emits_signal(qtbot, tmp_path, monkeypatch):
    """Test that clicking save button emits settings_changed signal."""
    config = Config()
    card = SettingsCard(config=config, parent=None)
    qtbot.addWidget(card)

    # Create config directory in tmp_path
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Mock the PROJECT_ROOT to point to tmp_path
    monkeypatch.setattr("gui.dashboard.cards.settings.PROJECT_ROOT", tmp_path)

    signals = []
    card.settings_changed.connect(lambda d: signals.append(d))

    # Find and click the save button
    save_btn = card.findChild(QPushButton, "saveSettingsButton")
    if save_btn is None:
        # If objectName not set, find by text
        buttons = card.findChildren(QPushButton)
        save_btn = next((b for b in buttons if "Сохранить" in b.text()), None)

    assert save_btn is not None, "Save button not found"

    # Change something to ensure data is different
    card._widgets['tcp_port'].setValue(1111)

    qtbot.mouseClick(save_btn, Qt.MouseButton.LeftButton)

    # Check signal emitted
    assert len(signals) == 1
    assert signals[0]['tcp_port'] == 1111

    # Check file written
    settings_file = config_dir / "settings.json"
    assert settings_file.exists()
    import json
    saved_data = json.loads(settings_file.read_text())
    assert saved_data['tcp_port'] == 1111
