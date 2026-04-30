import sys
import os
import signal
import logging
from pathlib import Path

# Настраиваем логирование в файл
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/gui_startup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    logger.info("=== Запуск GUI ===")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    logger.info("QApplication created")

    # Загрузка конфигурации
    config = None
    try:
        config = Config.from_file("config/settings.json")
        logger.info(f"Конфигурация загружена: tcp_port={config.tcp_port}")
    except Exception as e:
        logger.warning(f"Ошибка загрузки конфигурации: {e}, создаю по умолчанию")
        cmw = CmwConfig(ip="192.168.1.100", simulate=True)
        config = Config(cmw500=cmw)

    # Создаём EventBus и EventBridge ДО запуска движка
    from core.event_bus import EventBus
    bus = EventBus()
    logger.info("EventBus created")
    bridge = EventBridge(bus)
    logger.info("EventBridge created")

    # Создание обёртки над движком
    wrapper = EngineWrapper(config)
    wrapper.bus = bus
    logger.info("EngineWrapper created")

    try:
        logger.info("Starting engine...")
        await wrapper.start_engine()
        logger.info("CoreEngine запущен!")
    except Exception as e:
        import traceback
        logger.error(f"CoreEngine недоступен: {e}")
        traceback.print_exc()
        wrapper.engine = None

    logger.info("Creating MainWindow...")
    window = MainWindow(wrapper, bridge)
    window.show()
    logger.info("MainWindow shown")

    # Показываем предупреждение если без движка
    if not wrapper.engine:
        logger.warning("CoreEngine не запущен - режим офлайн")
        QMessageBox.warning(
            None, "Режим офлайн",
            "CoreEngine не запущен. GUI работает в ограниченном режиме."
        )

    # Запускаем Qt цикл
    logger.info("Entering Qt event loop...")
    result = app.exec()

    # Корректная остановка
    if wrapper.engine:
        try:
            await wrapper.stop_engine()
        except:
            pass

    logger.info("=== GUI closed ===")
    return result


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        logger.info("GUI closed by user")
    except Exception as e:
        logger.exception(f"Critical error: {e}")