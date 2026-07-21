"""
Пример настройки DAU на CMW-500.
"""

import asyncio
import logging

from core.cmw500 import Cmw500Controller
from core.config import Config
from core.event_bus import EventBus

logger = logging.getLogger(__name__)


async def main() -> None:
    """Основная асинхронная функция для настройки DAU."""
    # Инициализация
    config = Config()
    bus = EventBus()
    controller = Cmw500Controller(bus=bus, ip=config.cmw500.ip)

    try:
        # Подключение к прибору
        await controller.connect()
        logger.info("Подключено к CMW-500 по адресу %s", config.cmw500.ip)

        # Выполнение настройки DAU
        await controller.configure_dau(
            dau_ip=config.cmw500.dau_ip,
            dau_mask=config.cmw500.dau_mask,
            dau_gateway=config.cmw500.dau_gateway,
            dau_mobile_ips=config.cmw500.dau_mobile_ips,
        )
        logger.info("Настройка DAU выполнена успешно: IP=%s", config.cmw500.dau_ip)

    except Exception as e:
        logger.error("Ошибка при работе с CMW-500: %s", e)
        raise

    finally:
        # Закрытие соединения
        await controller.disconnect()
        logger.info("Соединение с CMW-500 закрыто")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
