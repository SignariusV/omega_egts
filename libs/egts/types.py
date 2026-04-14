"""Типы и перечисления EGTS (общие для всех версий ГОСТ)."""

from enum import IntEnum


class PacketType(IntEnum):
    """Типы пакетов транспортного уровня (ГОСТ таблица 3)."""
    RESPONSE = 0          # EGTS_PT_RESPONSE
    APPDATA = 1           # EGTS_PT_APPDATA
    SIGNED_APPDATA = 2    # EGTS_PT_SIGNED_APPDATA


class ServiceType(IntEnum):
    """Типы сервисов уровня поддержки услуг."""
    AUTH = 1              # Авторизация
    TELEDATA = 2          # Телеметрия
    COMMANDS = 4          # Команды и параметры
    FIRMWARE = 9          # Обновление ПО
    ECALL = 10            # eCall


class SubrecordType(IntEnum):
    """Типы подзаписей уровня поддержки услуг (ГОСТ 33465-2015)."""
    RECORD_RESPONSE = 0   # Подтверждение записи
    TERM_IDENTITY = 1     # Идентификация терминала
    MODULE_DATA = 2       # Данные модуля
    VEHICLE_DATA = 3      # Данные ТС
    AUTH_PARAMS = 6       # Параметры авторизации
    AUTH_INFO = 7         # Информация для авторизации
    SERVICE_INFO = 8      # Информация о сервисах
    RESULT_CODE = 9       # Код результата
    ACCEL_DATA = 20       # Профиль ускорения
    SERVICE_PART_DATA = 33        # Частичная передача данных ПО
    SERVICE_FULL_DATA = 34        # Полная передача данных ПО
    COMMAND_DATA = 51     # Команда
    RAW_MSD_DATA = 62     # Данные MSD (eCall)
    TRACK_DATA = 63       # Траектория


class ResultCode(IntEnum):
    """Коды результатов обработки (ГОСТ приложение В).
    
    0, 1, 128-154 — всего 29 кодов.
    """
    OK = 0                # Обработка успешна
    IN_PROGRESS = 1       # Обработка в процессе
    UNS_PROTOCOL = 128    # Не поддерживаемая версия протокола
    DECRYPT_ERROR = 129   # Ошибка расшифрования
    PROC_DENIED = 130     # Обработка запрещена
    INC_HEADERFORM = 131  # Неверный формат заголовка
    INC_DATAFORM = 132    # Неверный формат данных
    UNS_TYPE = 133        # Не поддерживаемый тип пакета
    NOTEN_PARAMS = 134    # Недостаточность полномочий
    DBL_PROC = 135        # Повторная обработка
    PROC_SRC_DENIED = 136 # Обработка запрещена по источнику
    HEADERCRC_ERROR = 137 # Ошибка CRC заголовка
    DATACRC_ERROR = 138   # Ошибка CRC данных
    INVDATALEN = 139      # Неверная длина данных
    ROUTE_NFOUND = 140    # Маршрут не найден
    ROUTE_CLOSED = 141    # Маршрут закрыт
    ROUTE_DENIED = 142    # Обработка по маршруту запрещена
    INVADDR = 143         # Неверный адрес
    TTLEXPIRED = 144      # TTL истеёк
    NO_ACK = 145          # Нет подтверждения
    OBJ_NFOUND = 146      # Объект не найден
    EVNT_NFOUND = 147     # Событие не найдено
    SRVC_NFOUND = 148     # Сервис не найден
    SRVC_DENIED = 149     # Обработка сервисом запрещена
    SRVC_UNKN = 150       # Неизвестный сервис
    AUTH_DENIED = 151     # Авторизация запрещена
    ALREADY_EXISTS = 152  # Объект уже существует
    ID_NFOUND = 153       # Идентификатор не найден
    INC_DATETIME = 154    # Неверная дата/время
