"""
Пример настройки DAU на CMW-500.
"""

import asyncio
import logging

from core.cmw500 import Cmw500Controller
from core.config import Config
from core.event_bus import EventBus


async def main() -> None:
    """Основная асинхронная функция для настройки DAU."""
    # Инициализация
    config = Config()
    bus = EventBus()
    controller = Cmw500Controller(bus=bus, ip=config.cmw500.ip)

    try:
        # Подключение к прибору
        await controller.connect()
        print(f"Подключено к CMW-500 по адресу {config.cmw500.ip}")

        # Выполнение настройки DAU
        await controller.configure_dau(
            dau_ip=config.cmw500.dau_ip,
            dau_mask=config.cmw500.dau_mask,
            dau_gateway=config.cmw500.dau_gateway,
            dau_mobile_ips=config.cmw500.dau_mobile_ips,
        )
        print(f"Настройка DAU выполнена успешно: IP={config.cmw500.dau_ip}")

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
