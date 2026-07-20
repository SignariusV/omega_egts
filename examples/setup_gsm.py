"""
Пример настройки GSM сигнализации на CMW-500.
"""

import asyncio
import logging

from core.cmw500 import Cmw500Controller
from core.config import Config
from core.event_bus import EventBus


async def main() -> None:
    """Основная асинхронная функция для настройки GSM сигнализации."""
    # Инициализация
    config = Config()
    bus = EventBus()
    controller = Cmw500Controller(bus=bus, ip=config.cmw500.ip)

    try:
        # Подключение к прибору
        await controller.connect()
        print(f"Подключено к CMW-500 по адресу {config.cmw500.ip}")

        # Выполнение настройки GSM сигнализации
        await controller.configure_gsm_signaling(
            mcc=config.cmw500.mcc,
            mnc=config.cmw500.mnc,
            rf_level_dbm=config.cmw500.rf_level_tch,
            ps_service=config.cmw500.ps_service,
            ps_tlevel=config.cmw500.ps_tlevel,
            ps_cscheme_ul=config.cmw500.ps_cscheme_ul,
            ps_dl_carrier=",".join(config.cmw500.ps_dl_carrier),
            ps_dl_cscheme=",".join(config.cmw500.ps_dl_cscheme),
        )
        print("Настройка GSM сигнализации выполнена успешно")

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
