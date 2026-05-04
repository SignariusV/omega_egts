import pytest
from unittest.mock import MagicMock, AsyncMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from gui.main import main
from gui.core.engine_wrapper import EngineWrapper
from gui.core.event_bridge import EventBridge


@pytest.fixture
def mock_engine():
    """Мок CoreEngine."""
    engine = MagicMock()
    engine.config = MagicMock()
    engine.bus = MagicMock()
    return engine


@pytest.mark.asyncio
async def test_main_window_starts(qtbot, monkeypatch):
    """Тест запуска главного окна (с замоканным движком)."""
    # Мокаем Config
    import core.config
    mock_config = MagicMock()
    monkeypatch.setattr(core.config.Config, "from_file", classmethod(lambda cls, path: mock_config))

    # Мокаем CoreEngine
    import core.engine
    mock_engine_instance = MagicMock()
    mock_engine_instance.bus = MagicMock()
    monkeypatch.setattr(core.engine.CoreEngine, "__init__", lambda self, config, bus=None: None)
    monkeypatch.setattr(core.engine.CoreEngine, "start", AsyncMock())
    monkeypatch.setattr(core.engine.CoreEngine, "stop", AsyncMock())

    # Мокаем EventBus
    import core.event_bus
    monkeypatch.setattr(core.event_bus.EventBus, "__init__", lambda self: None)
    monkeypatch.setattr(core.event_bus.EventBus, "on", MagicMock())

    # Запускаем main в отдельном потоке? Нет, просто проверим, что импорт работает
    # и создаётся окно без ошибок.
    from gui.main_window import MainWindow
    from gui.core.engine_wrapper import EngineWrapper
    from gui.core.event_bridge import EventBridge

    wrapper = EngineWrapper(mock_config)
    wrapper.engine = mock_engine_instance
    bridge = EventBridge(wrapper.engine.bus)
    window = MainWindow(wrapper, bridge)
    window.show()
    
    # Даём время на отрисовку
    QTimer.singleShot(100, QApplication.instance().quit)
    QApplication.instance().exec()

    assert window is not None
    window.close()
