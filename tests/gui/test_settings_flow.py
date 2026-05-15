# OMEGA_EGTS GUI Tests
"""Simple test: save settings, restart, verify."""

import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QSpinBox

from gui.main import MainWindow
from core.config import Config


def test_full_settings_flow(qtbot, tmp_path, monkeypatch):
    """Test: save settings -> restart -> verify loaded."""
    
    # 1. Подготавливаем: мокаем PROJECT_ROOT в settings.py
    import gui.dashboard.cards.settings as settings_module
    original_root = settings_module.PROJECT_ROOT
    
    try:
        # Устанавливаем tmp_path как корень проекта
        settings_module.PROJECT_ROOT = tmp_path
        
        # 2. Создаём главное окно (эмуляция запуска)
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        QApplication.processEvents()
        
        # Проверяем, что загрузился конфиг (по умолчанию)
        assert window._config is not None, "Config not loaded"
        
        # 3. Открываем настройки (клик по кнопке в сайдбаре)
        sidebar = window._sidebar
        btn = sidebar._buttons.get("settings")
        assert btn is not None, "Settings button not found"
        
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        settings_card = window._settings_card
        assert settings_card.isVisible(), "Settings card should be visible"
        
        # 4. Меняем порт на 9999
        port_widget = settings_card._widgets.get('tcp_port')
        assert port_widget is not None, "TCP port widget not found"
        port_widget.setValue(9999)
        QApplication.processEvents()
        
        # 5. Нажимаем "Сохранить"
        save_btn = None
        buttons = settings_card.findChildren(QPushButton)
        for b in buttons:
            if "Сохранить" in b.text():
                save_btn = b
                break
        
        assert save_btn is not None, "Save button not found"
        qtbot.mouseClick(save_btn, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        
        # 6. Проверяем, что файл записался
        settings_file = tmp_path / "config" / "settings.json"
        assert settings_file.exists(), f"Settings file not found at {settings_file}"
        
        saved_data = json.loads(settings_file.read_text())
        assert saved_data['tcp_port'] == 9999, \
            f"Port not saved correctly: {saved_data.get('tcp_port')}"
        
        print(f"✓ Настройки сохранены в {settings_file}")
        print(f"✓ Порт сохранён: {saved_data['tcp_port']}")
        
        # 7. Эмулируем перезапуск: создаём новое окно
        # MainWindow.__init__() загрузит конфиг из settings_file
        new_window = MainWindow()
        qtbot.addWidget(new_window)
        new_window.show()
        QApplication.processEvents()
        
        # 8. Проверяем, что новый конфиг загрузился с правильным портом
        assert new_window._config.tcp_port == 9999, \
            f"After restart, port should be 9999, got: {new_window._config.tcp_port}"
        
        print(f"✓ После перезапуска порт загрузился: {new_window._config.tcp_port}")
        print("✓ УСПЕХ: Полный цикл работы настроек!")
        
    finally:
        # Восстанавливаем оригинальный PROJECT_ROOT
        settings_module.PROJECT_ROOT = original_root


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
