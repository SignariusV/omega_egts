"""
Пример настройки SMS на CMW-500.
"""

import asyncio
import logging

from core.cmw500 import Cmw500Controller
from core.config import Config
from core.event_bus import EventBus


async def main() -> None:
    """Основная асинхронная функция для настройки SMS."""
    # Инициализация
    config = Config()
    bus = EventBus()
    controller = Cmw500Controller(bus=bus, ip=config.cmw500.ip)

    try:
        # Подключение к прибору
        await controller.connect()
        print(f"Подключено к CMW-500 по адресу {config.cmw500.ip}")

        # Выполнение настройки SMS с заданными параметрами
        await controller.configure_sms(dcoding="BIT8", pid=1)
        print("Настройка SMS выполнена успешно")

    except Exception as e:
        print(f"Ошибка при работе с CMW-500: {e}")
        raise

    finally:
        # Закрытие соединения
        await controller.disconnect()
        print("Соединение с CMW-500 закрыто")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
