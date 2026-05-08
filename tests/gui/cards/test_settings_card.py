# OMEGA_EGTS GUI Tests
"""Tests for SettingsCard."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from core.config import Config, CmwConfig, TimeoutsConfig, LogConfig
from gui.dashboard.cards.settings import SettingsCard


def test_settings_card_creation(qtbot):
    """Test that SettingsCard initializes correctly and is hidden by default."""
    config = Config(
        gost_version="2015",
        tcp_port=3001,
        cmw500=CmwConfig(ip="192.168.2.2", simulate=True),
        timeouts=TimeoutsConfig(),
        logging=LogConfig(),
    )
    card = SettingsCard(config=config, parent=None)
    qtbot.addWidget(card)

    # Card should be hidden initially
    assert not card.isVisible()
    assert card.card_id == "settings"
    assert card._config is not None


def test_settings_card_widgets_populated(qtbot):
    """Test that widgets are populated with config values."""
    config = Config(
        gost_version="2023",
        tcp_port=8090,
        cmw500=CmwConfig(ip="10.0.0.1", simulate=False),
        timeouts=TimeoutsConfig(tl_response_to=10.0),
        logging=LogConfig(level="DEBUG"),
    )
    card = SettingsCard(config=config, parent=None)
    qtbot.addWidget(card)

    # Check a few widget values
    assert card._widgets['gost_version'].currentText() == "2023"
    assert card._widgets['tcp_port'].value() == 8090
    assert card._widgets['cmw500.ip'].text() == "10.0.0.1"
    assert card._widgets['cmw500.simulate'].isChecked() is False
    assert card._widgets['timeouts.tl_response_to'].value() == 10.0
    assert card._widgets['logging.level'].currentText() == "DEBUG"


def test_settings_card_collect_data(qtbot):
    """Test that _collect_data returns correct dictionary."""
    config = Config()
    card = SettingsCard(config=config, parent=None)
    qtbot.addWidget(card)

    # Modify some values
    card._widgets['tcp_port'].setValue(1234)
    card._widgets['cmw500.timeout'].setValue(99.9)
    card._widgets['logging.level'].setCurrentText("WARNING")

    data = card._collect_data()

    assert isinstance(data, dict)
    assert data['tcp_port'] == 1234
    assert data['cmw500']['timeout'] == 99.9
    assert data['logging']['level'] == "WARNING"
    assert 'timeouts' in data
    assert 'cmw500' in data


def test_settings_card_save_emits_signal(qtbot, tmp_path, monkeypatch):
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
    saved_data = json.loads(settings_file.read_text())
    assert saved_data['tcp_port'] == 1111


def test_settings_card_icon_path(qtbot):
    """Test that icon_path is set for sidebar."""
    config = Config()
    card = SettingsCard(config=config, parent=None)
    qtbot.addWidget(card)

    assert hasattr(card, 'icon_path')
    assert "settings.svg" in card.icon_path
