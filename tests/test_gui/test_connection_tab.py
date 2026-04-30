import pytest
from unittest.mock import MagicMock, AsyncMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from gui.tabs.connection_tab import ConnectionTab


@pytest.fixture
def engine_wrapper():
    """Мок EngineWrapper."""
    wrapper = MagicMock()
    wrapper.engine = MagicMock()
    wrapper.engine.config = MagicMock()
    wrapper.engine._started = False  # По умолчанию не запущен
    return wrapper


@pytest.fixture
def event_bridge():
    """Мок EventBridge."""
    bridge = MagicMock()
    bridge.server_started = MagicMock()
    bridge.server_stopped = MagicMock()
    bridge.cmw_connected = MagicMock()
    bridge.cmw_disconnected = MagicMock()
    return bridge


@pytest.fixture
def connection_tab(qtbot, engine_wrapper, event_bridge):
    """Экземпляр ConnectionTab."""
    tab = ConnectionTab(engine_wrapper, event_bridge)
    qtbot.addWidget(tab)
    return tab


def test_connection_tab_initial_state(engine_wrapper, event_bridge, qtbot):
    """Проверка начального состояния вкладки."""
    # Тест 1: движок не запущен - кнопка Start активна
    engine_wrapper.engine._started = False
    tab = ConnectionTab(engine_wrapper, event_bridge)
    qtbot.addWidget(tab)

    assert tab.is_server_running == False
    assert tab.start_btn.isEnabled() == True
    assert tab.stop_btn.isEnabled() == False
    assert tab.port_input.text() == "3001"

    # Тест 2: движок запущен - кнопка Start отключена
    engine_wrapper.engine._started = True
    tab2 = ConnectionTab(engine_wrapper, event_bridge)
    qtbot.addWidget(tab2)

    assert tab2.is_server_running == True
    assert tab2.start_btn.isEnabled() == False
    assert tab2.stop_btn.isEnabled() == True


def test_start_button_disabled_when_engine_started(connection_tab):
    """Кнопка Start отключена если движок уже запущен."""
    # Если engine уже запущен - start_btn отключена
    connection_tab.is_server_running = True
    connection_tab._on_server_started({"port": 3001})
    assert connection_tab.start_btn.isEnabled() == False
    assert connection_tab.stop_btn.isEnabled() == True


def test_stop_button_click(connection_tab, qtbot, monkeypatch):
    """Проверка нажатия кнопки Стоп."""
    from PySide6.QtWidgets import QMessageBox
    # Устанавливаем состояние сервера - запущен
    connection_tab.is_server_running = True
    connection_tab.stop_btn.setEnabled(True)
    # Мокаем QMessageBox.question, чтобы вернуть QMessageBox.Yes
    monkeypatch.setattr(
        "gui.tabs.connection_tab.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.Yes
    )
    # Нажимаем кнопку
    qtbot.mouseClick(connection_tab.stop_btn, Qt.LeftButton)
    # Проверяем, что вызвался метод stop_server
    connection_tab.engine_wrapper.stop_server.assert_called_once()


def test_server_started_signal(connection_tab, event_bridge):
    """Проверка обработки сигнала server.started."""
    # Имитируем сигнал
    connection_tab._on_server_started({"port": 3001})
    assert connection_tab.is_server_running == True
    assert connection_tab.start_btn.isEnabled() == False
    assert connection_tab.stop_btn.isEnabled() == True
    assert "ЗАПУЩЕН" in connection_tab.server_status_label.text()


def test_server_stopped_signal(connection_tab, event_bridge):
    """Проверка обработки сигнала server.stopped."""
    # Сначала установим состояние "запущен"
    connection_tab.is_server_running = True
    connection_tab.start_btn.setEnabled(False)
    connection_tab.stop_btn.setEnabled(True)
    # Имитируем сигнал
    connection_tab._on_server_stopped({})
    assert connection_tab.is_server_running == False
    assert connection_tab.start_btn.isEnabled() == True
    assert connection_tab.stop_btn.isEnabled() == False
    assert "ОСТАНОВЛЕН" in connection_tab.server_status_label.text()
