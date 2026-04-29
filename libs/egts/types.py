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
    TTLEXPIRED = 144      # TTL истёк
    NO_ACK = 145          # Нет подтверждения
    OBJ_NFOUND = 146      # Объект не найден
    EVNT_NFOUND = 147     # Событие не найдено
    SRVC_NFOUND = 148     # Сервис не найден
    SRVC_DENIED = 149     # Обработка сервисом запрещена
    SRVC_UNKN = 150       # Неизвестный сервис
    AUTH_DENIED = 151     # Авторизация запрещена
    ALREADY_EXISTS = 152   # Объект уже существует
    ID_NFOUND = 153       # Идентификатор не найден
    INC_DATETIME = 154    # Неверная дата/время


class CommandType(IntEnum):
    """Типы команд (CT) для EGTS_SR_COMMAND_DATA (ГОСТ таблица 29)."""
    COMCONF = 0x1   # Подтверждение о приёме/обработке команды
    MSGCONF = 0x2   # Подтверждение о приёме сообщения
    MSGFROM = 0x3   # Информационное сообщение от УСВ
    MSGTO = 0x4     # Информационное сообщение для ТС
    COM = 0x5       # Команда для выполнения на ТС
    DELCOM = 0x6     # Удаление команды из очереди
    SUBREQ = 0x7     # Дополнительный подзапрос
    DELIV = 0x8      # Подтверждение о доставке


class ConfirmationType(IntEnum):
    """Типы подтверждения (CCT) для EGTS_SR_COMMAND_DATA (ГОСТ таблица 29)."""
    OK = 0x0       # Успешное выполнение, положительный ответ
    ERROR = 0x1     # Обработка завершилась ошибкой
    ILL = 0x2       # Команда не может быть выполнена
    DEL = 0x3        # Команда успешно удалена
    NFOUND = 0x4     # Команда для удаления не найдена
    NCONF = 0x5      # Успешное выполнение, отрицательный ответ
    INPROG = 0x6     # Команда передана на обработку, результат неизвестен


class ActionType(IntEnum):
    """Типы действий (ACT) для команд CT_COM (ГОСТ таблица 30)."""
    PARAMS = 0x0    # Параметры команды
    QUERY = 0x1     # Запрос значения
    SET = 0x2       # Установка значения
    ADD = 0x3       # Добавление нового параметра
    DELETE = 0x4    # Удаление параметра


class Charset(IntEnum):
    """Кодировки (CHS) для EGTS_SR_COMMAND_DATA (ГОСТ таблица 29)."""
    CP1251 = 0      # CP-1251
    ASCII = 1        # IA5 (CCITT T.50)/ASCII
    BINARY = 2       # Бинарные данные
    LATIN1 = 3       # Latin 1
    BINARY2 = 4      # Бинарные данные (alt)
    JIS = 5          # JIS (X 0208-1990)
    CYRILLIC = 6      # Cyrillic
    LATIN_HEBREW = 7  # Latin/Hebrew
    UCS2 = 8         # UCS2


# Словарь кодов команд (CCD) из таблицы 32 ГОСТ 33465-2015
COMMAND_CODES = {
    0x0000: "EGTS_RAW_DATA",
    0x0001: "EGTS_TEST_MODE",
    0x0006: "EGTS_CONFIG_RESET",
    0x0007: "EGTS_SET_AUTH_CODE",
    0x0008: "EGTS_RESTART",
    0x0101: "EGTS_GPRS_APN",
    0x0102: "EGTS_SERVER_ADDRESS",
    0x0103: "EGTS_SIM_PIN",
    0x0104: "EGTS_AUTOMATIC_REGISTRATION",
    0x0105: "EGTS_REGISTRATION_ATTEMPTS",
    0x0106: "EGTS_REGISTRATION_TIMEOUT",
    0x0107: "EGTS_GPRS_CONNECTION_ATTEMPTS",
    0x0108: "EGTS_GPRS_CONNECTION_TIMEOUT",
    0x0109: "EGTS_TCP_CONNECTION_ATTEMPTS",
    0x010A: "EGTS_TCP_CONNECTION_TIMEOUT",
    0x010B: "EGTS_INACTIVITY_TIMEOUT",
    0x010C: "EGTS_SERVICE_ENABLE",
    0x010D: "EGTS_NETWORK_SEARCH_PERIOD",
    0x0113: "EGTS_ECALL_MSD_REQ",
    0x0114: "EGTS_ACCEL_DATA",
    0x0115: "EGTS_TRACK_DATA",
    0x0116: "EGTS_ECALL_DEREGISTRATION",
    0x0203: "EGTS_SET_GPRS_APN",  # CCD=515
    0x0204: "EGTS_SET_SERVER_ADDRESS",  # CCD=516
    0x020D: "EGTS_ECALL_TEST_NUMBER",
    0x0404: "EGTS_UNIT_ID",
    0x0405: "EGTS_UNIT_IMEI",
}

# Множество значений CommandType для быстрой проверки
COMMAND_TYPE_VALUES = {e.value for e in CommandType}
CONFIRMATION_TYPE_VALUES = {e.value for e in ConfirmationType}
ACTION_TYPE_VALUES = {e.value for e in ActionType}
