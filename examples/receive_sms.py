"""
Пример приёма SMS с EGTS-пакетом от CMW-500.
"""

import asyncio
import logging

from core.cmw500 import Cmw500Controller
from core.config import Config
from core.event_bus import EventBus


async def main() -> None:
    """Основная асинхронная функция для приёма SMS с EGTS-пакетом."""
    # Инициализация
    config = Config()
    bus = EventBus()
    controller = Cmw500Controller(bus=bus, ip=config.cmw500.ip)

    async def on_sms_received(sms_data: bytes) -> None:
        """Обработчик события прихода SMS."""
        print(f"Получен SMS с данными: {sms_data}")

    try:
        # Подключение к прибору
        await controller.connect()
        print(f"Подключено к CMW-500 по адресу {config.cmw500.ip}")

        # Настройка SMS
        await controller.configure_sms(dcoding="BIT8", pid=1)
        print("SMS сконфигурирован: DCODing=BIT8, PID=1")

        # Подписка на событие получения сырого пакета
        bus.on("raw.packet.received", lambda data: on_sms_received(data["raw"]), ordered=True)

        # Сразу считываем SMS
        print("Чтение SMS...")
        sms_data = await controller.read_sms()
        if sms_data is not None:
            await on_sms_received(sms_data)
        else:
            print("SMS не найдено")

    except asyncio.CancelledError:
        print("Приложение остановлено")
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
