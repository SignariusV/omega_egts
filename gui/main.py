import sys
import os
import signal
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

import asyncio
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

from core.engine import Config
from core.config import CmwConfig
from gui.core.engine_wrapper import EngineWrapper
from gui.core.event_bridge import EventBridge
from gui.main_window import MainWindow


async def main():
    """Главная асинхронная функция."""
    print("Запуск GUI...")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Загрузка конфигурации
    config = None
    try:
        config = Config.from_file("config/settings.json")
        print(f"Конфигурация загружена: tcp_port={config.tcp_port}")
    except Exception as e:
        print(f"Создание конфигурации: {e}")
        cmw = CmwConfig(ip="192.168.1.100", simulate=True)
        config = Config(cmw500=cmw)

    # Создаём EventBus и EventBridge ДО запуска движка
    from core.event_bus import EventBus
    bus = EventBus()
    bridge = EventBridge(bus)

    # Создание обёртки над движком
    wrapper = EngineWrapper(config)
    wrapper.bus = bus

    try:
        await wrapper.start_engine()
        print("CoreEngine запущен")
    except Exception as e:
        import traceback
        print(f"CoreEngine недоступен: {e}")
        traceback.print_exc()
        wrapper.engine = None

    window = MainWindow(wrapper, bridge)
    window.show()

    # Показываем предупреждение если без движка
    if not wrapper.engine:
        QMessageBox.warning(
            None, "Режим офлайн",
            "CoreEngine не запущен. GUI работает в ограниченном режиме."
        )

    # Запускаем Qt цикл
    result = app.exec()

    # Корректная остановка
    if wrapper.engine:
        try:
            await wrapper.stop_engine()
        except:
            pass

    return result


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        print("GUI закрыт")
    except Exception as e:
        print(f"Ошибка: {e}")