import pytest
from PySide6.QtWidgets import QPushButton, QLabel
from PySide6.QtCore import Qt

from gui.dialogs.about_dialog import AboutDialog
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.packet_details import PacketDetailsDialog


@pytest.fixture
def about_dialog(qtbot):
    """Экземпляр AboutDialog."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    return dialog


@pytest.fixture
def settings_dialog(qtbot, monkeypatch):
    """Экземпляр SettingsDialog с моком QSettings."""
    class MockSettings:
        def __init__(self, *args, **kwargs):
            self.data = {}
        def value(self, key, default=None, type=None):
            return self.data.get(key, default)
        def setValue(self, key, value):
            self.data[key] = value

    import PySide6.QtCore
    monkeypatch.setattr(PySide6.QtCore, "QSettings", MockSettings)

    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    return dialog


@pytest.fixture
def packet_details_dialog(qtbot):
    """Экземпляр PacketDetailsDialog."""
    packet_data = {
        "time": "12:00:00.123",
        "direction": "▶ RX (входящий)",
        "size": "64 байт",
        "pid": "1",
        "rn": "1",
        "service": "TERM_IDENTITY",
        "raw": "01 00 01 00"
    }
    dialog = PacketDetailsDialog(packet_data)
    qtbot.addWidget(dialog)
    return dialog


class TestAboutDialog:
    """Тесты для AboutDialog."""

    def test_initial_state(self, about_dialog):
        """Проверка создания диалога."""
        assert "О программе" in about_dialog.windowTitle()
        # Проверяем, что размер зафиксирован
        assert about_dialog.minimumWidth() == about_dialog.maximumWidth()
        assert about_dialog.minimumHeight() == about_dialog.maximumHeight()

    def test_close_button(self, about_dialog):
        """Проверка закрытия по кнопке."""
        close_btn = None
        for child in about_dialog.findChildren(QPushButton):
            if "Закрыть" in child.text():
                close_btn = child
                break
        assert close_btn is not None


class TestSettingsDialog:
    """Тесты для SettingsDialog."""

    def test_initial_state(self, settings_dialog):
        """Проверка начального состояния."""
        assert "Настройки" in settings_dialog.windowTitle()
        assert settings_dialog.theme_combo.currentText() == "Тёмная"
        assert settings_dialog.lang_combo.currentText() == "Русский"
        assert settings_dialog.autosave_check.isChecked()

    def test_save_button_exists(self, settings_dialog):
        """Проверка наличия кнопки Сохранить."""
        save_btn = None
        for child in settings_dialog.findChildren(QPushButton):
            if "Сохранить" in child.text():
                save_btn = child
                break
        assert save_btn is not None


class TestPacketDetailsDialog:
    """Тесты для PacketDetailsDialog."""

    def test_initial_state(self, packet_details_dialog):
        """Проверка создания диалога."""
        assert "Детали пакета" in packet_details_dialog.windowTitle()

    def test_populate_data(self, packet_details_dialog):
        """Проверка заполнения данными."""
        found_time = False
        for child in packet_details_dialog.findChildren(QLabel):
            if "12:00:00" in child.text():
                found_time = True
                break
        assert found_time

    def test_hex_edit_exists(self, packet_details_dialog):
        """Проверка наличия поля HEX."""
        from PySide6.QtWidgets import QTextEdit
        hex_edits = packet_details_dialog.findChildren(QTextEdit)
        assert len(hex_edits) > 0
