"""
Базовые типы и константы протокола EGTS (ГОСТ 33465-2015)

Модуль содержит:
1. Константы (числовые значения, лимиты, таймауты)
2. Перечисления (enum.IntEnum для типов данных)

Структура раздела:
├── Константы (таймауты, размеры, лимиты)
│   ├── Параметры ПТУ (раздел 5)
│   ├── SMS параметры (раздел 5.7)
│   ├── Параметры ППУ (раздел 6)
│   ├── Временные параметры ПТУ (таблица 13)
│   ├── Временные параметры ППУ (таблица 39)
│   ├── Максимальные размеры пакетов
│   ├── Размеры полей FIRMWARE сервиса (таблицы 36-38)
│   ├── Словари описаний (VHT, VPST, RESULT_CODES)
│   ├── Команды ECALL (таблица 46)
│   └── Параметры УСВ (таблицы 34, 47)
└── Перечисления (enum.IntEnum)
    ├── PacketType (типы пакетов)
    ├── ServiceType (типы сервисов)
    ├── SubrecordType (типы подзаписей)
    ├── Priority (приоритеты)
    ├── EncryptionAlgorithm (шифрование)
    ├── SMS ТON, NPI, VPF, IEI
    ├── ModuleType, VehicleType (типы модулей и ТС)
    ├── ServiceState (состояния сервисов)
    ├── CommandType, ConfirmationType (команды и подтверждения)
    ├── Charset (кодировки)
    ├── CommandAction, CommandCode (действия и коды команд)
    ├── ObjectAttribute, ObjectType, TargetModuleType (FIRMWARE сервис)
    ├── RecordStatus (коды результатов)
    └── EcallCommand (команды ECALL)
"""

import enum

# =============================================================================
# РАЗДЕЛ 1: КОНСТАНТЫ (числовые значения, лимиты, таймауты, словари)
# =============================================================================

# -----------------------------------------------------------------------------
# Раздел 5: ПРОТОКОЛ ТРАНСПОРТНОГО УРОВНЯ (ПТУ)
# -----------------------------------------------------------------------------

# 5.6.1.3 Параметры заголовка пакета транспортного уровня (Таблица 4)
EGTS_PRV_VERSION = 0x01
"""PRV (Protocol Version): Версия структуры заголовка. Для данной версии должно быть 0x01."""

EGTS_PRF_PREFIX = 0x00
"""PRF (Prefix): Префикс заголовка. Для данной версии должно быть 00."""

# Значения для поля RTE (Route)
EGTS_RTE_NO_ROUTING = 0
"""RTE = 0: Дальнейшая маршрутизация не требуется, поля PRA, RCA, TTL отсутствуют."""

EGTS_RTE_ROUTING_NEEDED = 1
"""RTE = 1: Требуется маршрутизация, поля PRA, RCA, TTL присутствуют."""

# Значения для поля ENA (Encryption Algorithm)
EGTS_ENA_NO_ENCRYPTION = 0b00
"""ENA = 00: Данные не шифруются."""

# Значения для поля CMP (Compressed)
EGTS_CMP_NOT_COMPRESSED = 0
"""CMP = 0: Данные не сжаты."""

EGTS_CMP_COMPRESSED = 1
"""CMP = 1: Данные сжаты."""

# Значения для поля PR (Priority)
EGTS_PR_HIGHEST = 0b00
"""PR = 00: Наивысший приоритет."""

EGTS_PR_HIGH = 0b01
"""PR = 01: Высокий приоритет."""

EGTS_PR_MEDIUM = 0b10
"""PR = 10: Средний приоритет."""

EGTS_PR_LOWEST = 0b11
"""PR = 11: Низкий приоритет."""

# -----------------------------------------------------------------------------
# Битовые маски флагов заголовка пакета (Таблица 3 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_FLAGS_PRF_MASK = 0x80        # Бит 7: Prefix
EGTS_FLAGS_RTE_MASK = 0x40        # Бит 6: Route
EGTS_FLAGS_ENA_MASK = 0x20        # Бит 5: Encryption Algorithm
EGTS_FLAGS_CMP_MASK = 0x10        # Бит 4: Compressed
EGTS_FLAGS_PR_MASK = 0x0C         # Биты 3-2: Priority
EGTS_FLAGS_PR_SHIFT = 2           # Сдвиг для Priority

# -----------------------------------------------------------------------------
# Раздел 5.7: Описание структуры данных при использовании SMS
# -----------------------------------------------------------------------------

# 5.7.1.2 Поле TP_MTI (Message Type Indicator)
SMS_TP_MTI_VALUE = 0b01
"""TP_MTI (Message Type Indicator): Тип сообщения. Должен содержать бинарное значение 01."""

# 5.7.1.2 Поле TP_PID (Protocol Identifier)
SMS_TP_PID_VALUE = 0x00
"""TP_PID (Protocol Identifier): Должен содержать значение 00."""

# 5.7.1.2 Поле TP_DCS (Data Coding Schema)
SMS_TP_DCS_8BIT = 0x04
"""TP_DCS (Data Coding Schema): 8-битная кодировка сообщения, отсутствие компрессии."""

# 5.7.1.2 Поле TP_UDHI (User Data Header Indicator)
SMS_TP_UDHI_NO_HEADER = 0
"""TP_UDHI = 0: Заголовок пользовательских данных отсутствует."""

SMS_TP_UDHI_HEADER_PRESENT = 1
"""TP_UDHI = 1: Заголовок пользовательских данных присутствует."""

# 5.7.1.2 Поле TP_SRR (Status Report Request)
SMS_TP_SRR_NO_REPORT = 0
"""TP_SRR = 0: Подтверждение от SMSC не требуется."""

SMS_TP_SRR_REPORT_REQUESTED = 1
"""TP_SRR = 1: Требуется подтверждение от SMSC."""

# -----------------------------------------------------------------------------
# Раздел 6: ПРОТОКОЛ УРОВНЯ ПОДДЕРЖКИ УСЛУГ (ППУ)
# -----------------------------------------------------------------------------

# 6.6.2.2 Параметры заголовка записи ППУ (Таблица 14)
# Значения для поля SSOD (Source Service On Device)
EGTS_SSOD_ON_PLATFORM = 0
"""SSOD = 0: Сервис-отправитель расположен на телематической платформе."""

EGTS_SSOD_ON_DEVICE = 1
"""SSOD = 1: Сервис-отправитель расположен на стороне УСВ."""

# Значения для поля RSOD (Recipient Service On Device)
EGTS_RSOD_ON_PLATFORM = 0
"""RSOD = 0: Сервис-получатель расположен на телематической платформе."""

EGTS_RSOD_ON_DEVICE = 1
"""RSOD = 1: Сервис-получатель расположен на стороне УСВ."""

# 6.6.2.2 Поле TMFE (Time Field Exists)
EGTS_TMFE_ABSENT = 0
"""TMFE = 0: Поле ТМ отсутствует."""

EGTS_TMFE_PRESENT = 1
"""TMFE = 1: Поле ТМ присутствует."""

# 6.6.2.2 Поле EVFE (Event ID Field Exists)
EGTS_EVFE_ABSENT = 0
"""EVFE = 0: Поле EVID отсутствует."""

EGTS_EVFE_PRESENT = 1
"""EVFE = 1: Поле EVID присутствует."""

# 6.6.2.2 Поле OBFE (Object ID Field Exists)
EGTS_OBFE_ABSENT = 0
"""OBFE = 0: Поле OID отсутствует."""

EGTS_OBFE_PRESENT = 1
"""OBFE = 1: Поле OID присутствует."""

# 6.6.3 Тип подзаписи (SRT)
EGTS_SRT_RECORD_RESPONSE = 0
"""SRT = 0: Специальный тип, зарезервирован за подзаписью подтверждения данных для каждого сервиса."""

# -----------------------------------------------------------------------------
# Размеры полей подзаписи (Раздел 6.6.3 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

SRT_SIZE = 1  # Размер поля SRT (тип подзаписи), байт
SRL_SIZE = 2  # Размер поля SRL (длина подзаписи), байт
SUBRECORD_HEADER_SIZE = 3  # Размер заголовка подзаписи (SRT + SRL), байт

# -----------------------------------------------------------------------------
# Размеры полей записи (Раздел 6.6.2 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

RECORD_RL_SIZE = 2  # Размер поля RL (длина записи), байт
RECORD_RN_SIZE = 2  # Размер поля RN (номер записи), байт
RECORD_RFL_SIZE = 1  # Размер поля RFL (флаги), байт
RECORD_OID_SIZE = 4  # Размер поля OID (идентификатор объекта), байт
RECORD_EVID_SIZE = 4  # Размер поля EVID (идентификатор события), байт
RECORD_TM_SIZE = 4  # Размер поля TM (время), байт
RECORD_SST_SIZE = 1  # Размер поля SST (сервис-отправитель), байт
RECORD_RST_SIZE = 1  # Размер поля RST (сервис-получатель), байт

# Минимальный размер заголовка записи
RECORD_HEADER_SIZE = 5  # Размер заголовка без RL (RN+RFL+SST+RST), байт
RECORD_MIN_SIZE = 7  # Минимальный размер записи (RL+RN+RFL+SST+RST), байт

# -----------------------------------------------------------------------------
# Размеры полей пакета (Раздел 5.6.1, таблица 3 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

PACKET_PRV_SIZE = 1  # Размер поля PRV (версия протокола), байт
PACKET_SKID_SIZE = 1  # Размер поля SKID (идентификатор ключа), байт
PACKET_FLAGS_SIZE = 1  # Размер поля флагов, байт
PACKET_HL_SIZE = 1  # Размер поля HL (длина заголовка), байт
PACKET_HE_SIZE = 1  # Размер поля HE (зарезервировано), байт
PACKET_FDL_SIZE = 2  # Размер поля FDL (длина данных), байт
PACKET_PID_SIZE = 2  # Размер поля PID (идентификатор пакета), байт
PACKET_PT_SIZE = 1  # Размер поля PT (тип пакета), байт
PACKET_PRA_SIZE = 2  # Размер поля PRA (адрес отправителя), байт
PACKET_RCA_SIZE = 2  # Размер поля RCA (адрес получателя), байт
PACKET_TTL_SIZE = 1  # Размер поля TTL (время жизни), байт
PACKET_HCS_SIZE = 1  # Размер поля HCS (CRC-8 заголовка), байт
PACKET_SFRCS_SIZE = 2  # Размер поля SFRCS (CRC-16 данных), байт

# Размеры заголовка пакета
PACKET_HEADER_MIN_SIZE = 11  # Минимальный размер заголовка (без маршрутизации), байт
PACKET_HEADER_WITH_ROUTING_SIZE = 16  # Размер заголовка с маршрутизацией, байт

# Поля RESPONSE пакета (RPID + PR)
PACKET_RESPONSE_HEADER_SIZE = 3  # Размер RPID (2) + PR (1), байт

# Оффсетсы полей в заголовке пакета
PACKET_HL_OFFSET = 3  # Оффсет поля HL (PRV + SKID + FLAGS)
PACKET_FDL_OFFSET = 5  # Оффсет поля FDL (PRV + SKID + FLAGS + HL + HE)

# -----------------------------------------------------------------------------
# Флаги записи RFL (Раздел 6.6.2.2, таблица 14 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_RFL_OBFE_MASK = 0x01       # Бит 0: Object ID Field Exists
EGTS_RFL_EVFE_MASK = 0x02       # Бит 1: Event ID Field Exists
EGTS_RFL_TMFE_MASK = 0x04       # Бит 2: Time Field Exists
EGTS_RFL_RPP_MASK = 0x38        # Биты 3-5: Record Processing Priority
EGTS_RFL_RPP_SHIFT = 3          # Сдвиг для RPP
EGTS_RFL_RSOD_MASK = 0x40       # Бит 6: Recipient Service On Device
EGTS_RFL_SSOD_MASK = 0x80       # Бит 7: Source Service On Device

# -----------------------------------------------------------------------------
# Временные параметры ПТУ (Раздел 5.8, таблица 13 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

TL_RESPONSE_TO = 5  # Время ожидания подтверждения пакета, сек
TL_RESEND_ATTEMPTS = 3  # Число повторных попыток отправки
TL_RECONNECT_TO = 30  # Время до повторной попытки установления соединения, сек

# -----------------------------------------------------------------------------
# Временные параметры ППУ (Раздел 6.8, таблица 39 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_SL_NOT_AUTH_TO = 6  # Время ожидания авторизации, сек
EGTS_SL_SERVICE_TO = 30  # Время ожидания сервиса, сек (расширение, не указано в ГОСТ)

# -----------------------------------------------------------------------------
# Максимальные размеры пакетов (Раздел 5.6, таблица 3 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

MAX_PACKET_SIZE = 65535  # Максимальный размер пакета ПТУ, байт
MAX_SFRD_SIZE = 65517  # Максимальный размер поля SFRD, байт
MAX_RECORD_SIZE = 65498  # Максимальный размер записи, байт
MAX_SUBRECORD_SIZE = 65495  # Максимальный размер подзаписи, байт

# Минимальные размеры
MIN_PACKET_SIZE = 11  # Минимальный размер пакета (заголовок без SFRD), байт
MIN_RECORD_SIZE = 7  # Минимальный размер записи (без RD), байт
MIN_SUBRECORD_SIZE = 3  # Минимальный размер подзаписи (SRT+SRL), байт

# -----------------------------------------------------------------------------
# CRC полиномы (Приложение Д ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

CRC8_POLY = 0x131  # Полином CRC-8 (с учётом старшего бита)
CRC8_INIT = 0xFF  # Начальное значение CRC-8

CRC16_POLY = 0x11021  # Полином CRC-16 CCITT (с учётом старшего бита)
CRC16_INIT = 0xFFFF  # Начальное значение CRC-16

# -----------------------------------------------------------------------------
# 6.7.2 Сервис EGTS_AUTH_SERVICE (Таблица 17)
# -----------------------------------------------------------------------------

# 6.7.2.2 Подзапись EGTS_SR_TERM_IDENTITY (Таблица 19)
# Флаги в поле Flags (ГОСТ 33465-2015, таблица 19)
EGTS_TID_HDIDE_MASK = 0x01  # Бит 0: HDID exists
EGTS_TID_IMEIE_MASK = 0x02  # Бит 1: IMEI exists
EGTS_TID_IMSIE_MASK = 0x04  # Бит 2: IMSI exists
EGTS_TID_LNGCE_MASK = 0x08  # Бит 3: Language Code exists
EGTS_TID_SSRA_MASK = 0x10   # Бит 4: Simple Service Request Algorithm
EGTS_TID_NIDE_MASK = 0x20   # Бит 5: Network ID exists
EGTS_TID_BSE_MASK = 0x40    # Бит 6: Buffer Size exists
EGTS_TID_MNE_MASK = 0x80    # Бит 7: MSISDN exists

EGTS_TID_SSRA_SIMPLE = 1
"""SSRA = 1: Используется «простой» алгоритм использования сервисов."""

EGTS_TID_SSRA_REQUEST = 0
"""SSRA = 0: Используется алгоритм «запросов» на использование сервисов."""

# -----------------------------------------------------------------------------
# Размеры полей TERM_IDENTITY (Раздел 6.7.2.2, таблица 19 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_TID_SIZE = 4  # Размер поля TID (Terminal ID), байт
EGTS_TID_FLAGS_SIZE = 1  # Размер поля флагов TERM_IDENTITY, байт
EGTS_TID_HDID_SIZE = 2  # Размер поля HDID (Hardware Device ID), байт
EGTS_TID_IMEI_SIZE = 15  # Размер поля IMEI, байт
EGTS_TID_IMSI_SIZE = 16  # Размер поля IMSI, байт
EGTS_TID_LNGC_SIZE = 3  # Размер поля LNGC (Language Code), байт
EGTS_TID_NID_SIZE = 3  # Размер поля NID (Network ID), байт
EGTS_TID_BS_SIZE = 2  # Размер поля BS (Buffer Size), байт
EGTS_TID_MSISDN_SIZE = 15  # Размер поля MSISDN, байт

# Минимальный размер TERM_IDENTITY (TID + Flags)
EGTS_TID_MIN_SIZE = 5

# -----------------------------------------------------------------------------
# Размеры полей MODULE_DATA (Раздел 6.7.2.3, таблица 21 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_MODULE_DATA_MIN_SIZE = 11  # Минимальный размер MODULE_DATA без SRN и DSCR, байт
EGTS_MODULE_MT_SIZE = 1  # Размер поля MT (Module Type), байт
EGTS_MODULE_VID_SIZE = 4  # Размер поля VID (Vendor ID), байт
EGTS_MODULE_FWV_SIZE = 2  # Размер поля FWV (Firmware Version), байт
EGTS_MODULE_SWV_SIZE = 2  # Размер поля SWV (Software Version), байт
EGTS_MODULE_MD_SIZE = 1  # Размер поля MD (Module Data), байт
EGTS_MODULE_ST_SIZE = 1  # Размер поля ST (Service Type), байт
EGTS_MODULE_MAX_SRN_SIZE = 32  # Максимальный размер SRN (Serial Number), байт
EGTS_MODULE_MAX_DSCR_SIZE = 32  # Максимальный размер DSCR (Description), байт

# -----------------------------------------------------------------------------
# Размеры полей VEHICLE_DATA (Раздел 6.7.2.4, таблица 22 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_VEHICLE_VIN_SIZE = 17  # Размер поля VIN, байт
EGTS_VEHICLE_VHT_SIZE = 4  # Размер поля VHT (Vehicle Type), байт
EGTS_VEHICLE_VPST_SIZE = 4  # Размер поля VPST (Propulsion Storage Type), байт
EGTS_VEHICLE_DATA_SIZE = 25  # Полный размер VEHICLE_DATA, байт

# -----------------------------------------------------------------------------
# Размеры полей RECORD_RESPONSE (Раздел 6.7.2.1, таблица 18 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_RECORD_RESPONSE_CRN_SIZE = 2  # Размер поля CRN (Record Number), байт
EGTS_RECORD_RESPONSE_RST_SIZE = 1  # Размер поля RST (Record Status), байт
EGTS_RECORD_RESPONSE_SIZE = 3  # Полный размер RECORD_RESPONSE, байт

# -----------------------------------------------------------------------------
# 6.7.2.3 Подзапись EGTS_SR_MODULE_DATA (Таблица 21)
# Поле ST (State) модуля
EGTS_MODULE_STATE_ON = 1
"""ST = 1: Модуль включен."""

EGTS_MODULE_STATE_OFF = 0
"""ST = 0: Модуль выключен."""
# Значения больше 127 - неисправность (коды см. Приложение В)

# 6.7.2.4 Подзапись EGTS_SR_VEHICLE_DATA (Таблица 22)
# Поле VPST (Vehicle Propulsion Storage Type) - битовое поле
EGTS_VPST_GASOLINE_MASK = 0x01       # Бит 0:1 — бензин
EGTS_VPST_DIESEL_MASK = 0x02         # Бит 1:1 — дизель
EGTS_VPST_LPG_MASK = 0x04            # Бит 2:1 — жидкий пропан (LPG)
EGTS_VPST_CNG_MASK = 0x08            # Бит 3:1 — сжиженный природный газ (CNG)
EGTS_VPST_ELECTRIC_MASK = 0x10       # Бит 4:1 — электричество (>42В и 100 А/ч)
EGTS_VPST_HYDROGEN_MASK = 0x20       # Бит 5:1 — водород

# 6.7.2.5 Подзапись EGTS_SR_AUTH_PARAMS (Таблица 23)
# Флаги поля FLG
EGTS_AUTH_PARAMS_EXE_MASK = 0x80  # Бит 7
EGTS_AUTH_PARAMS_SSE_MASK = 0x40  # Бит 6
EGTS_AUTH_PARAMS_MSE_MASK = 0x20  # Бит 5
EGTS_AUTH_PARAMS_ISLE_MASK = 0x10 # Бит 4
EGTS_AUTH_PARAMS_PKE_MASK = 0x08  # Бит 3
EGTS_AUTH_PARAMS_ENA_MASK = 0x07  # Биты 2-0 (алгоритм шифрования)

EGTS_AUTH_PARAMS_NO_FLAGS = 0x00
"""FLG = 0x00: Флаги параметров авторизации не установлены (шифрование не применяется)."""

EGTS_AUTH_PARAMS_ENA_NO_ENCRYPTION = 0x00
"""ENA = 00: Шифрование не применяется."""

# 6.7.2.7 Подзапись EGTS_SR_SERVICE_INFO (Таблица 25)
# Поле SRVA (Service Attribute) в составе SRVP
EGTS_SRVA_SUPPORTED = 0
"""SRVA = 0: Поддерживаемый сервис."""

EGTS_SRVA_REQUESTED = 1
"""SRVA = 1: Запрашиваемый сервис."""

# -----------------------------------------------------------------------------
# 6.7.3 Сервис EGTS_COMMANDS_SERVICE (Таблица 28)
# -----------------------------------------------------------------------------

# 6.7.3.1 Подзапись EGTS_SR_COMMAND_DATA (Таблица 29)
# Флаги поля Flags команды
EGTS_CMD_ACFE_MASK = 0x80  # Бит 7 (Authorization Code Field Exists)
EGTS_CMD_CHSFE_MASK = 0x40 # Бит 6 (Charset Field Exists)

# -----------------------------------------------------------------------------
# Размеры полей COMMAND_DATA (Раздел 6.7.3.1, таблица 29 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_COMMAND_DATA_MIN_SIZE = 10  # Минимальный размер COMMAND_DATA, байт
EGTS_COMMAND_CT_CCT_SIZE = 1  # Размер поля CT+CCT, байт
EGTS_COMMAND_CID_SIZE = 4  # Размер поля CID (Command ID), байт
EGTS_COMMAND_SID_SIZE = 4  # Размер поля SID (Sender ID), байт
EGTS_COMMAND_FLAGS_SIZE = 1  # Размер поля флагов COMMAND_DATA, байт
EGTS_COMMAND_CHS_SIZE = 1  # Размер поля CHS (Charset), байт
EGTS_COMMAND_ACL_SIZE = 1  # Размер поля ACL (Auth Code Length), байт

# Размеры полей CD (Command Data)
EGTS_COMMAND_ADR_SIZE = 2  # Размер поля ADR (Address), байт
EGTS_COMMAND_SZ_ACT_SIZE = 1  # Размер поля SZ+ACT, байт
EGTS_COMMAND_CCD_SIZE = 2  # Размер поля CCD (Command Code), байт
EGTS_COMMAND_SZ_MASK = 0x1F  # Маска для SZ (биты 7-3)
EGTS_COMMAND_SZ_SHIFT = 3  # Сдвиг для SZ
EGTS_COMMAND_ACT_MASK = 0x07  # Маска для ACT (биты 2-0)

# 6.7.3.2 Команды для УСВ (Таблица 32)
EGTS_CMD_CODE_SIZE = 2  # Размер поля CCD (Command Code), байт
EGTS_CMD_DATA_OFFSET = 5  # Оффсет данных команды в CD (CT+CCT+SZ+ACT+CCD)
EGTS_CMD_MIN_SIZE = 5  # Минимальный размер CD (CT+CCT+SZ+ACT+CCD), байт

EGTS_CMD_RAW_DATA = 0x0000
"""EGTS_RAW_DATA (0x0000): Команда для передачи произвольных данных."""

EGTS_CMD_TEST_MODE = 0x0001
"""EGTS_TEST_MODE (0x0001): Команда начала/окончания тестирования УСВ."""

EGTS_CMD_CONFIG_RESET = 0x0006
"""EGTS_CONFIG_RESET (0x0006): Возврат к заводским установкам."""

EGTS_CMD_SET_AUTH_CODE = 0x0007
"""EGTS_SET_AUTH_CODE (0x0007): Установка кода авторизации на стороне УСВ."""

EGTS_CMD_RESTART = 0x0008
"""EGTS_RESTART (0x0008): Перезапуск основного ПО УСВ."""

# 6.7.3.2 Подтверждения от УСВ (Таблица 33)
EGTS_CONF_TEST_MODE = 0x0001
"""EGTS_TEST_MODE (0x0001): Подтверждение на команду тестирования."""

# -----------------------------------------------------------------------------
# 7. СЕРВИС ЭКСТРЕННОГО РЕАГИРОВАНИЯ (EGTS_ECALL_SERVICE)
# -----------------------------------------------------------------------------

# 7.3.3 Подзапись EGTS_SR_RAW_MSD_DATA (Таблица 43)
# Поле FM (Format)
EGTS_MSD_FORMAT_UNKNOWN = 0
"""FM = 0: Формат неизвестен."""

EGTS_MSD_FORMAT_GOST_33464 = 1
"""FM = 1: Правила кодировки пакета в соответствии с ГОСТ 33464."""

# 7.3.4 (Таблица 45) Поля структуры TDS
# Флаги первого байта структуры TDS
EGTS_TDS_TNDE_MASK = 0x80      # Бит 7 (Track Node Data Exist)
EGTS_TDS_LOHS_MASK = 0x40      # Бит 6 (Longitude Hemisphere)
EGTS_TDS_LAHS_MASK = 0x20      # Бит 5 (Latitude Hemisphere)

EGTS_TDS_TNDE_NO_DATA = 0
"""TNDE = 0: Данные о точке не передаются (координаты невалидны)."""

EGTS_TDS_TNDE_DATA_EXISTS = 1
"""TNDE = 1: Данные о точке передаются (поля LAT, LONG и др. присутствуют)."""

EGTS_TDS_LOHS_EAST = 0
"""LOHS = 0: Восточная долгота."""

EGTS_TDS_LOHS_WEST = 1
"""LOHS = 1: Западная долгота."""

EGTS_TDS_LAHS_NORTH = 0
"""LAHS = 0: Северная широта."""

EGTS_TDS_LAHS_SOUTH = 1
"""LAHS = 1: Южная широта."""

# -----------------------------------------------------------------------------
# Размеры полей ACCEL_DATA (Раздел 7.3.1, таблица 41, 42 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_ACCEL_DATA_MIN_SIZE = 5  # Минимальный размер ACCEL_DATA (SA + ATM), байт
EGTS_ACCEL_SA_SIZE = 1  # Размер поля SA (количество измерений), байт
EGTS_ACCEL_ATM_SIZE = 4  # Размер поля ATM (абсолютное время), байт
EGTS_ACCEL_RTM_SIZE = 2  # Размер поля RTM (относительное время), байт
EGTS_ACCEL_XAAV_SIZE = 2  # Размер поля XAAV (ускорение X), байт
EGTS_ACCEL_YAAV_SIZE = 2  # Размер поля YAAV (ускорение Y), байт
EGTS_ACCEL_ZAAV_SIZE = 2  # Размер поля ZAAV (ускорение Z), байт
EGTS_ACCEL_MEASUREMENT_SIZE = 8  # Размер одного измерения (RTM+XAAV+YAAV+ZAAV), байт

# -----------------------------------------------------------------------------
# Размеры полей TRACK_DATA (Раздел 7.3.2, таблица 44, 45 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

EGTS_TRACK_DATA_MIN_SIZE = 5  # Минимальный размер TRACK_DATA (SA + ATM), байт
EGTS_TRACK_SA_SIZE = 1  # Размер поля SA (количество точек), байт
EGTS_TRACK_ATM_SIZE = 4  # Размер поля ATM (абсолютное время), байт
EGTS_TRACK_TDS_SIZE = 1  # Размер поля TDS (флаги точки), байт
EGTS_TRACK_LAT_SIZE = 4  # Размер поля LAT (широта), байт
EGTS_TRACK_LON_SIZE = 4  # Размер поля LON (долгота), байт
EGTS_TRACK_SPD_SIZE = 2  # Размер поля SPD (скорость), байт
EGTS_TRACK_DIR_SIZE = 1  # Размер поля DIR (направление), байт

# Диапазоны координат (ГОСТ 33465-2015, таблица 45)
# LAT/LON в миллисекундах дуги: ±324000000 (±90 градусов * 3600000)
EGTS_TRACK_LAT_MIN = -324000000  # Минимальная широта (90° южной широты)
EGTS_TRACK_LAT_MAX = 324000000   # Максимальная широта (90° северной широты)
EGTS_TRACK_LON_MIN = -648000000  # Минимальная долгота (180° западной долготы)
EGTS_TRACK_LON_MAX = 648000000   # Максимальная долгота (180° восточной долготы)

# 7.5.1 Команды УСВ для ECALL (Таблица 46)
# Параметры команды EGTS_ECALL_REQ
EGTS_ECALL_REQ_MANUAL = 0
"""Параметр = 0: ручной вызов."""

EGTS_ECALL_REQ_AUTO = 1
"""Параметр = 1: автоматический вызов."""

# Параметры команды EGTS_ECALL_MSD_REQ (поле TRANSPORT)
EGTS_ECALL_MSD_REQ_TRANSPORT_ANY = 0
"""TRANSPORT = 0: любой канал, на усмотрение УСВ."""

EGTS_ECALL_MSD_REQ_TRANSPORT_SMS = 2
"""TRANSPORT = 2: через SMS."""


# -----------------------------------------------------------------------------
# Команды ECALL (таблица 46 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

class EcallCommand(enum.IntEnum):
    """
    Команды ECALL сервиса (таблица 46 ГОСТ 33465-2015)

    SMS команды для экстренного вызова и передачи данных.
    Используются в COMMANDS сервисе.

    Attributes:
        ECALL_REQ (0x0112): Экстренный вызов (SMS)
        ECALL_MSD_REQ (0x0113): Повторная передача МНД (SMS)
        ACCEL_DATA (0x0114): Профиль ускорения (SMS)
        TRACK_DATA (0x0115): Траектория движения (SMS)
        ECALL_DEREGISTRATION (0x0116): Дерегистрация (SMS)
    """

    ECALL_REQ = 0x0112  # Экстренный вызов (SMS)
    ECALL_MSD_REQ = 0x0113  # Повторная передача МНД (SMS)
    ACCEL_DATA = 0x0114  # Профиль ускорения (SMS)
    TRACK_DATA = 0x0115  # Траектория движения (SMS)
    ECALL_DEREGISTRATION = 0x0116  # Дерегистрация (SMS)


# -----------------------------------------------------------------------------
# 8. ФОРМАТ СООБЩЕНИЯ AL-ACK (Таблица 48)
# -----------------------------------------------------------------------------

# Поле "Признак корректности полученных данных" (бит 2)
EGTS_ALACK_POSITIVE = 0
"""0: полученные данные корректны (Positive ACK)."""

EGTS_ALACK_CLEARDOWN = 1
"""1: завершение вызова (Cleardown)."""

# Поле "Версия формата данных" (бит 1)
EGTS_ALACK_VERSION_CURRENT = 0
"""0: текущий формат."""

EGTS_ALACK_VERSION_RESERVED = 1
"""1: зарезервировано для будущего использования."""

# -----------------------------------------------------------------------------
# Типы транспортных средств (VHT, таблица 22 ГОСТ 33464-2015)
# -----------------------------------------------------------------------------

VEHICLE_TYPES = {
    1: "M1 - Пассажирский, ≤8 мест",
    2: "M2 - Автобус, >8 мест, масса ≤5 тонн",
    3: "M3 - Автобус, >8 мест, масса >5 тонн",
    4: "N1 - Грузовой, масса ≤3.5 тонн",
    5: "N2 - Грузовой, масса 3.5-12 тонн",
    6: "N3 - Грузовой, масса >12 тонн",
    7: "L1e - Мопед, ≤50 см³",
    8: "L2e - Трехколесное, ≤50 см³",
    9: "L3e - Мотоцикл, >50 см³",
    10: "L4e - Мотоцикл с коляской",
    11: "L5e - Трехколесное, >50 см³",
    12: "L6e - Легкий квадрицикл",
    13: "L7e - Тяжелый квадрицикл",
}

# -----------------------------------------------------------------------------
# Типы топлива/двигателя (VPST, таблица 22 ГОСТ 33464-2015)
# -----------------------------------------------------------------------------

PROPULSION_TYPES = {
    0b000001: "Бензин",
    0b000010: "Дизель",
    0b000100: "CNG (сжиженный природный газ, метан)",
    0b001000: "LPG (жидкий пропан)",
    0b010000: "Электрический (>42В, 100Ач)",
    0b100000: "Водород",
}

# -----------------------------------------------------------------------------
# Коды результатов обработки (Приложение В, таблица В.1 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

RESULT_CODES = {
    # Успешные коды (0-127)
    0: "EGTS_PC_OK - Успешно обработано",
    1: "EGTS_PC_IN_PROGRESS - В процессе обработки",
    # Ошибки протокола (128-147)
    128: "EGTS_PC_UNS_PROTOCOL - Неподдерживаемый протокол",
    129: "EGTS_PC_DECRYPT_ERROR - Ошибка декодирования",
    130: "EGTS_PC_PROC_DENIED - Обработка запрещена",
    131: "EGTS_PC_INC_HEADERFORM - Неверный формат заголовка",
    132: "EGTS_PC_INC_DATAFORM - Неверный формат данных",
    133: "EGTS_PC_UNS_TYPE - Неподдерживаемый тип",
    134: "EGTS_PC_NOTEN_PARAMS - Неверное число параметров",
    135: "EGTS_PC_DBL_PROC - Попытка повторной обработки",
    136: "EGTS_PC_PROC_SRC_DENIED - Обработка данных от источника запрещена",
    137: "EGTS_PC_HEADERCRC_ERROR - Ошибка контрольной суммы заголовка",
    138: "EGTS_PC_DATACRC_ERROR - Ошибка контрольной суммы данных",
    139: "EGTS_PC_INVDATALEN - Некорректная длина данных",
    140: "EGTS_PC_ROUTE_NFOUND - Маршрут не найден",
    141: "EGTS_PC_ROUTE_CLOSED - Маршрут закрыт",
    142: "EGTS_PC_ROUTE_DENIED - Маршрутизация запрещена",
    143: "EGTS_PC_INVADDR - Неверный адрес",
    144: "EGTS_PC_TTLEXPIRED - Превышено число ретрансляции данных",
    145: "EGTS_PC_NO_ACK - Нет подтверждения",
    146: "EGTS_PC_OBJ_NFOUND - Объект не найден",
    147: "EGTS_PC_EVNT_NFOUND - Событие не найдено",
    # Ошибки сервиса (148-154)
    148: "EGTS_PC_SRVC_NFOUND - Сервис не найден",
    149: "EGTS_PC_SRVC_DENIED - Сервис запрещен",
    150: "EGTS_PC_SRVC_UNKN - Неизвестный тип сервиса",
    151: "EGTS_PC_AUTH_DENIED - Авторизация запрещена",
    152: "EGTS_PC_ALREADY_EXISTS - Объект уже существует",
    153: "EGTS_PC_ID_NFOUND - Идентификатор не найден",
    154: "EGTS_PC_INC_DATETIME - Неправильная дата и время",
}

# -----------------------------------------------------------------------------
# Состояния сервиса (таблица 26 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

SERVICE_STATES = {
    0: "EGTS_SST_IN_SERVICE - Сервис активен",
    128: "EGTS_SST_OUT_OF_SERVICE - Сервис неактивен",
    129: "EGTS_SST_DENIED - Доступ к сервису запрещен",
    130: "EGTS_SST_NO_CONF - Сервис не сконфигурирован",
    131: "EGTS_SST_TEMP_UNAVAIL - Сервис временно недоступен",
}

# =============================================================================
# СЛОВАРИ ДЛЯ ДЕТАЛЬНОГО ПАРСИНГА (используются в parse_packet_full())
# =============================================================================

# -----------------------------------------------------------------------------
# Типы сервисов (ST, таблица 16 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

SERVICE_NAMES = {
    0: "EGTS_SR_RECORD_RESPONSE",
    1: "EGTS_AUTH_SERVICE",
    2: "EGTS_TELEDATA_SERVICE",
    4: "EGTS_COMMANDS_SERVICE",
    9: "EGTS_FIRMWARE_SERVICE",
    10: "EGTS_ECALL_SERVICE",
}

# -----------------------------------------------------------------------------
# Типы команд (CT, таблица 29 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

COMMAND_TYPES = {
    1: "COM",
    2: "MSGTO",
    3: "COMCONF",
    4: "MSGFROM",
    5: "EVENT",
    6: "POS",
    7: "ALARM",
    8: "CHAR",
}

# -----------------------------------------------------------------------------
# Типы подтверждений команд (CCT, таблица 29 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

CONFIRMATION_TYPES = {
    0: "CC_OK",
    1: "CC_ERROR",
    2: "CC_ILL",
    3: "CC_INPROG",
}

# -----------------------------------------------------------------------------
# Действия с параметрами (ACT, таблица 29 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

ACTION_TYPES = {
    0: "ACT_READ",
    2: "ACT_WRITE",
    3: "ACT_DELETE",
    4: "ACT_EXECUTE",
}

# -----------------------------------------------------------------------------
# Коды команд (CD, раздел 6.7.3.3 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

COMMAND_CODES = {
    0x0203: "EGTS_GPRS_APN",
    0x0204: "EGTS_SERVER_ADDRESS",
    0x0205: "EGTS_UNIT_ID",
    0x0206: "EGTS_AUTH_KEY",
    0x0207: "EGTS_SEND_TEST",
    0x0208: "EGTS_REPORT_TEST",
    0x0209: "EGTS_RESET_TEST",
    0x020A: "EGTS_ECALL_TEST",
    0x020B: "EGTS_ECALL_MSD_TEST",
    0x020C: "EGTS_ACCEL_DATA",
    0x020D: "EGTS_TRACK_DATA",
    0x020E: "EGTS_TIME_SYNC",
    0x020F: "EGTS_REBOOT",
    0x0210: "EGTS_GET_PARAMS",
    0x0211: "EGTS_SET_PARAMS",
    0x0212: "EGTS_PARAM_VALUE",
    0x0213: "EGTS_PARAM_RESULT",
    0x0214: "EGTS_ECALL_REQ",
    0x0215: "EGTS_ECALL_MSD_REQ",
    0x0216: "EGTS_ECALL_DEREGISTRATION",
}

# -----------------------------------------------------------------------------
# Типы ТС (VHT, таблица 22 ГОСТ 33464-2015) - дополнение
# -----------------------------------------------------------------------------

ENGINE_TYPES = {
    0: "Не определено",
    1: "Бензиновый",
    2: "Дизельный",
    3: "Газовый (CNG)",
    4: "Электрический",
    5: "Гибридный",
    6: "Водородный",
    7: "LPG (пропан)",
}

# -----------------------------------------------------------------------------
# Имена кодов результатов (для RESULT_CODES)
# -----------------------------------------------------------------------------

RESULT_CODE_NAMES = RESULT_CODES.copy()

# -----------------------------------------------------------------------------
# Имена статусов записей (RST, Приложение В ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

RECORD_STATUS_NAMES = {
    0: "RST_OK",
    1: "RST_IN_PROGRESS",
    137: "RST_HEADERCRC_ERROR",
    138: "RST_DATACRC_ERROR",
    139: "RST_INVDATALEN",
}

# -----------------------------------------------------------------------------
# Размеры полей TELEDATA сервис (расширение, не относится к ГОСТ 33465-2015)
# -----------------------------------------------------------------------------
# Примечание: Эти константы используются в сервисе teledata для совместимости

# POS_DATA
EGTS_POS_DATA_POSF_SIZE = 1  # Размер поля POSF (флаги), байт
EGTS_POS_DATA_LAT_SIZE = 4  # Размер поля LAT (широта), байт
EGTS_POS_DATA_LON_SIZE = 4  # Размер поля LON (долгота), байт
EGTS_POS_DATA_DIR_SIZE = 1  # Размер поля DIR (направление), байт
EGTS_POS_DATA_SPD_SIZE = 2  # Размер поля SPD (скорость), байт
EGTS_POS_DATA_SAT_SIZE = 1  # Размер поля SAT (спутники), байт
EGTS_POS_DATA_TM_SIZE = 4  # Размер поля TM (время), байт
EGTS_POS_DATA_MIN_SIZE = 11  # Минимальный размер POS_DATA, байт

# Диапазоны координат
EGTS_POS_DATA_LAT_MIN = -324000000  # Минимальная широта (90° южной широты)
EGTS_POS_DATA_LAT_MAX = 324000000   # Максимальная широта (90° северной широты)
EGTS_POS_DATA_LON_MIN = -648000000  # Минимальная долгота (180° западной долготы)
EGTS_POS_DATA_LON_MAX = 648000000   # Максимальная долгота (180° восточной долготы)

# DIGIT_DATA
EGTS_DIGIT_DATA_DIG_IN_SIZE = 2  # Размер поля DIG_IN, байт
EGTS_DIGIT_DATA_DIG_OUT_SIZE = 2  # Размер поля DIG_OUT, байт
EGTS_DIGIT_DATA_SIZE = 4  # Полный размер DIGIT_DATA, байт

# LEVEL_DATA
EGTS_LEVEL_DATA_ADC1_SIZE = 2  # Размер поля ADC1, байт
EGTS_LEVEL_DATA_ADC2_SIZE = 2  # Размер поля ADC2, байт
EGTS_LEVEL_DATA_ADC3_SIZE = 2  # Размер поля ADC3, байт
EGTS_LEVEL_DATA_SIZE = 6  # Полный размер LEVEL_DATA, байт

# COUNTER_DATA
EGTS_COUNTER_DATA_CNTR1_SIZE = 4  # Размер поля CNTR1, байт
EGTS_COUNTER_DATA_CNTR2_SIZE = 4  # Размер поля CNTR2, байт
EGTS_COUNTER_DATA_CNTR3_SIZE = 4  # Размер поля CNTR3, байт
EGTS_COUNTER_DATA_SIZE = 12  # Полный размер COUNTER_DATA, байт

# STATE_DATA
EGTS_STATE_DATA_SIZE = 4  # Размер поля STATE_FLAGS, байт

# SENSOR_DATA
EGTS_SENSOR_DATA_SENSN_SIZE = 1  # Размер поля SENSN (количество), байт
EGTS_SENSOR_DATA_SENS_ID_SIZE = 1  # Размер поля SENS_ID, байт
EGTS_SENSOR_DATA_SENS_VAL_SIZE = 2  # Размер поля SENS_VAL, байт
EGTS_SENSOR_DATA_SENSOR_SIZE = 3  # Размер одного датчика, байт
EGTS_SENSOR_DATA_MIN_SIZE = 4  # Минимальный размер SENSOR_DATA, байт

# GSM_DATA
EGTS_GSM_DATA_CSQ_SIZE = 1  # Размер поля CSQ, байт
EGTS_GSM_DATA_LAC_SIZE = 2  # Размер поля LAC, байт
EGTS_GSM_DATA_CELL_ID_SIZE = 4  # Размер поля CELL_ID, байт
EGTS_GSM_DATA_SIZE = 7  # Полный размер GSM_DATA, байт

# -----------------------------------------------------------------------------
# Размеры полей FIRMWARE сервис (Раздел 6.7.4, таблицы 36-38 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

# ODH (Object Data Header, таблица 37)
EGTS_ODH_OA_SIZE = 1  # Размер поля OA (Object Attribute), байт
EGTS_ODH_OT_MT_SIZE = 1  # Размер поля OT+MT, байт
EGTS_ODH_CMI_SIZE = 1  # Размер поля CMI (Component ID), байт
EGTS_ODH_VER_SIZE = 2  # Размер поля VER (Version), байт
EGTS_ODH_WOS_SIZE = 2  # Размер поля WOS (Whole Object Signature), байт
EGTS_ODH_D_SIZE = 1  # Размер поля D (разделитель), байт
EGTS_ODH_MIN_SIZE = 7  # Минимальный размер ODH без FN, байт
EGTS_ODH_MAX_FN_SIZE = 64  # Максимальный размер FN (File Name), байт
EGTS_ODH_MAX_SIZE = 71  # Максимальный размер ODH с FN, байт

# SERVICE_FULL_DATA (таблица 38)
EGTS_SERVICE_FULL_DATA_MIN_SIZE = 8  # Минимальный размер (ODH + 1 байт OD), байт
EGTS_MAX_OBJECT_DATA_SIZE = 65400  # Максимальный размер данных объекта, байт

# SERVICE_PART_DATA (таблица 36)
EGTS_SERVICE_PART_ID_SIZE = 2  # Размер поля ID (Entity ID), байт
EGTS_SERVICE_PART_PN_SIZE = 2  # Размер поля PN (Part Number), байт
EGTS_SERVICE_PART_EPQ_SIZE = 2  # Размер поля EPQ (Expected Parts Quantity), байт
EGTS_SERVICE_PART_HEADER_SIZE = 6  # Размер заголовка PART_DATA (ID+PN+EPQ), байт
EGTS_SERVICE_PART_MIN_SIZE = 7  # Минимальный размер PART_DATA, байт
EGTS_MAX_PARTS = 65535  # Максимальное количество частей

# =============================================================================
# РАЗДЕЛ 2: ПЕРЕЧИСЛЕНИЯ (enum.IntEnum для типов данных)
# =============================================================================


class PacketType(enum.IntEnum):
    """
    Типы пакетов транспортного уровня (таблица 4 ГОСТ 33465-2015)

    Attributes:
        EGTS_PT_RESPONSE (0): Подтверждение пакета
        EGTS_PT_APPDATA (1): Данные приложения
        EGTS_PT_SIGNED_APPDATA (2): Подписанные данные приложения
    """

    EGTS_PT_RESPONSE = 0
    EGTS_PT_APPDATA = 1
    EGTS_PT_SIGNED_APPDATA = 2


class ServiceType(enum.IntEnum):
    """
    Типы сервисов уровня поддержки услуг (таблица 16 ГОСТ 33465-2015)

    Attributes:
        EGTS_AUTH_SERVICE (1): Аутентификация УСВ
        EGTS_TELEDATA_SERVICE (2): Телематические данные
        EGTS_COMMANDS_SERVICE (4): Команды и сообщения
        EGTS_FIRMWARE_SERVICE (9): Обновление ПО
        EGTS_ECALL_SERVICE (10): Экстренное реагирование
    """

    EGTS_AUTH_SERVICE = 1
    EGTS_TELEDATA_SERVICE = 2
    EGTS_COMMANDS_SERVICE = 4
    EGTS_FIRMWARE_SERVICE = 9
    EGTS_ECALL_SERVICE = 10


class SubrecordType(enum.IntEnum):
    """
    Типы подзаписей уровня поддержки услуг

    Базовые типы для всех сервисов.
    Специфичные типы подзаписей определяются в сервисах.

    Attributes:
        EGTS_SR_RECORD_RESPONSE (0): Подтверждение записи
        EGTS_SR_TERM_IDENTITY (1): Идентификатор терминала
        EGTS_SR_MODULE_DATA (2): Данные модулей
        EGTS_SR_VEHICLE_DATA (3): Данные транспортного средства
        EGTS_SR_AUTH_PARAMS (6): Параметры авторизации
        EGTS_SR_AUTH_INFO (7): Информация для авторизации
        EGTS_SR_SERVICE_INFO (8): Информация о сервисах
        EGTS_SR_RESULT_CODE (9): Результат авторизации
        EGTS_SR_COMMAND_DATA (0x33): Команды и сообщения
        EGTS_SR_ACCEL_DATA (20): Данные профиля ускорения
        EGTS_SR_RAW_MSD_DATA (21): Минимальный набор данных (МНД)
        EGTS_SR_TRACK_DATA (62): Данные траектории движения
        UNKNOWN (0xFF): Неизвестный тип
    """

    EGTS_SR_RECORD_RESPONSE = 0   # Подтверждение записи
    EGTS_SR_TERM_IDENTITY = 1     # Идентификатор терминала
    EGTS_SR_MODULE_DATA = 2       # Данные модулей
    EGTS_SR_VEHICLE_DATA = 3      # Данные транспортного средства
    EGTS_SR_AUTH_PARAMS = 6       # Параметры авторизации
    EGTS_SR_AUTH_INFO = 7         # Информация для авторизации
    EGTS_SR_SERVICE_INFO = 8      # Информация о сервисах
    EGTS_SR_RESULT_CODE = 9       # Результат авторизации
    EGTS_SR_COMMAND_DATA = 0x33   # Команды и сообщения (51)
    EGTS_SR_ACCEL_DATA = 20       # Данные профиля ускорения
    EGTS_SR_RAW_MSD_DATA = 21     # Минимальный набор данных (МНД)
    EGTS_SR_TRACK_DATA = 0x3E     # Данные траектории движения (62)
    EGTS_SR_SERVICE_PART_DATA = 0x21  # Данные по частям (33)
    EGTS_SR_SERVICE_FULL_DATA = 0x22  # Данные одним пакетом (34)
    UNKNOWN = 0xFF                # Неизвестный тип


class Priority(enum.IntEnum):
    """
    Приоритет пакета (таблица 3 ГОСТ 33465-2015)

    Биты 3-2 поля флагов заголовка ПТУ.

    Attributes:
        HIGHEST (0b00): Наивысший приоритет
        HIGH (0b01): Высокий приоритет
        MEDIUM (0b10): Средний приоритет
        LOW (0b11): Низкий приоритет
    """

    HIGHEST = 0b00
    HIGH = 0b01
    MEDIUM = 0b10
    LOW = 0b11


class EncryptionAlgorithm(enum.IntEnum):
    """
    Алгоритм шифрования данных ППУ (таблица 3 ГОСТ 33465-2015)

    Бит 5 поля флагов заголовка ПТУ.

    Attributes:
        NO_ENCRYPTION (0b00): Без шифрования
    """

    NO_ENCRYPTION = 0b00


# -----------------------------------------------------------------------------
# SMS перечисления (Раздел 5.7.1.2)
# -----------------------------------------------------------------------------

class SMS_TON(enum.IntEnum):
    """
    TON (Type Of Number) — тип номера адреса (Раздел 5.7.1.2)

    Attributes:
        UNKNOWN (0b000): Неизвестный
        INTERNATIONAL (0b001): Международный формат
        NATIONAL (0b010): Национальный формат
        NETWORK_SPECIFIC (0b011): Специальный номер, определяемый сетью
        SUBSCRIBER (0b100): Номер абонента
        ALPHANUMERIC (0b101): Буквенно-цифровой код
        ABBREVIATED (0b110): Укороченный
        RESERVED (0b111): Зарезервировано
    """

    UNKNOWN = 0b000
    INTERNATIONAL = 0b001
    NATIONAL = 0b010
    NETWORK_SPECIFIC = 0b011
    SUBSCRIBER = 0b100
    ALPHANUMERIC = 0b101
    ABBREVIATED = 0b110
    RESERVED = 0b111


class SMS_NPI(enum.IntEnum):
    """
    NPI (Number Plan Identification) — тип плана нумерации (Раздел 5.7.1.2)

    Attributes:
        UNKNOWN (0b0000): Неизвестный
        ISDN (0b0001): План нумерации ISDN телефонии
        DATA (0b0011): План нумерации при передаче данных
        TELEX (0b0100): Телеграф
        NATIONAL (0b1000): Национальный
        PRIVATE (0b1001): Частный
        RESERVED (0b1111): Зарезервировано
    """

    UNKNOWN = 0b0000
    ISDN = 0b0001
    DATA = 0b0011
    TELEX = 0b0100
    NATIONAL = 0b1000
    PRIVATE = 0b1001
    RESERVED = 0b1111


class SMS_TP_VPF(enum.IntEnum):
    """
    TP_VPF (Validity Period Format) — формат параметра TP_VP (Раздел 5.7.1.2)

    Attributes:
        NO_FIELD (0b00): Поле TP_VP не передается
        RELATIVE (0b10): Формат «относительное время» (1 байт)
        ENHANCED (0b01): Формат «расширенное время» (7 байт)
        ABSOLUTE (0b11): Формат «абсолютное время» (7 байт)
    """

    NO_FIELD = 0b00
    RELATIVE = 0b10
    ENHANCED = 0b01
    ABSOLUTE = 0b11


class SMS_IEI(enum.IntEnum):
    """
    IEI (Information-Element-Identifier) — идентификатор информационного элемента (Раздел 5.7.1.2)

    Attributes:
        CONCATENATED_SMS (0x00): Часть конкатенируемого SMS-сообщения
        SPECIAL_MSG_INDICATOR (0x01): Индикатор специального SMS-сообщения
    """

    CONCATENATED_SMS = 0x00
    SPECIAL_MSG_INDICATOR = 0x01


# -----------------------------------------------------------------------------
# Перечисления для флагов ПТУ (Раздел 5.6.1.3, таблица 3 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

class RouteFlag(enum.IntEnum):
    """
    RTE (Route) — флаг маршрутизации (Таблица 3 ГОСТ 33465-2015)

    Бит 6 поля флагов заголовка ПТУ.

    Attributes:
        NO_ROUTING (0): Дальнейшая маршрутизация не требуется
        ROUTING_NEEDED (1): Требуется маршрутизация
    """

    NO_ROUTING = 0
    ROUTING_NEEDED = 1


class CompressionFlag(enum.IntEnum):
    """
    CMP (Compressed) — флаг сжатия данных (Таблица 3 ГОСТ 33465-2015)

    Бит 4 поля флагов заголовка ПТУ.

    Attributes:
        NOT_COMPRESSED (0): Данные не сжаты
        COMPRESSED (1): Данные сжаты
    """

    NOT_COMPRESSED = 0
    COMPRESSED = 1


# -----------------------------------------------------------------------------
# Перечисления для флагов ППУ (Раздел 6.6.2.2, таблица 14 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

class ServiceLocation(enum.IntEnum):
    """
    SSOD/RSOD (Source/Recipient Service On Device) — расположение сервиса (Таблица 14 ГОСТ 33465-2015)

    Биты 6-7 поля RFL (Record Flags) заголовка записи ППУ.

    Attributes:
        ON_PLATFORM (0): Сервис расположен на телематической платформе
        ON_DEVICE (1): Сервис расположен на стороне УСВ
    """

    ON_PLATFORM = 0
    ON_DEVICE = 1


class FieldPresence(enum.IntEnum):
    """
    TMFE/EVFE/OBFE (Time/Event/Object Field Exists) — наличие полей (Таблица 14 ГОСТ 33465-2015)

    Биты 0-2 поля RFL (Record Flags) заголовка записи ППУ.

    Attributes:
        ABSENT (0): Поле отсутствует
        PRESENT (1): Поле присутствует
    """

    ABSENT = 0
    PRESENT = 1


# Псевдонимы для обратной совместимости
EGTS_RTE_NO_ROUTING = RouteFlag.NO_ROUTING.value
EGTS_RTE_ROUTING_NEEDED = RouteFlag.ROUTING_NEEDED.value

EGTS_CMP_NOT_COMPRESSED = CompressionFlag.NOT_COMPRESSED.value
EGTS_CMP_COMPRESSED = CompressionFlag.COMPRESSED.value

EGTS_SSOD_ON_PLATFORM = ServiceLocation.ON_PLATFORM.value
EGTS_SSOD_ON_DEVICE = ServiceLocation.ON_DEVICE.value

EGTS_RSOD_ON_PLATFORM = ServiceLocation.ON_PLATFORM.value
EGTS_RSOD_ON_DEVICE = ServiceLocation.ON_DEVICE.value

EGTS_TMFE_ABSENT = FieldPresence.ABSENT.value
EGTS_TMFE_PRESENT = FieldPresence.PRESENT.value

EGTS_EVFE_ABSENT = FieldPresence.ABSENT.value
EGTS_EVFE_PRESENT = FieldPresence.PRESENT.value

EGTS_OBFE_ABSENT = FieldPresence.ABSENT.value
EGTS_OBFE_PRESENT = FieldPresence.PRESENT.value


# -----------------------------------------------------------------------------
# AUTH сервис перечисления (Раздел 6.7.2)
# -----------------------------------------------------------------------------

class EGTS_MODULE_TYPE(enum.IntEnum):
    """
    MT (Module Type) — тип модуля (Таблица 21 ГОСТ 33465-2015)

    Attributes:
        MAIN (1): Основной модуль
        IO (2): Модуль ввода вывода
        GNSS (3): Модуль навигационного приемника
        WIRELESS (4): Модуль беспроводной связи
    """

    MAIN = 1
    IO = 2
    GNSS = 3
    WIRELESS = 4


class EGTS_VEHICLE_TYPE(enum.IntEnum):
    """
    VHT (Vehicle Type) — тип транспортного средства (Таблица 22 ГОСТ 33464-2015)

    Attributes:
        PASSENGER_M1 (0b00001): Пассажирский (Class M1)
        BUS_M2 (0b00010): Автобус (Class M2)
        BUS_M3 (0b00011): Автобус (Class M3)
        LIGHT_TRUCK_N1 (0b00100): Легкая грузовая машина (Class N1)
        HEAVY_TRUCK_N2 (0b00101): Тяжелая грузовая машина (Class N2)
        HEAVY_TRUCK_N3 (0b00110): Тяжелая грузовая машина (Class N3)
        MOTORCYCLE_L1E (0b00111): Мотоцикл (Class L1e)
        MOTORCYCLE_L2E (0b01000): Мотоцикл (Class L2e)
        MOTORCYCLE_L3E (0b01001): Мотоцикл (Class L3e)
        MOTORCYCLE_L4E (0b01010): Мотоцикл (Class L4e)
        MOTORCYCLE_L5E (0b01011): Мотоцикл (Class L5e)
        MOTORCYCLE_L6E (0b01100): Мотоцикл (Class L6e)
        MOTORCYCLE_L7E (0b01101): Мотоцикл (Class L7e)
    """

    PASSENGER_M1 = 0b00001
    BUS_M2 = 0b00010
    BUS_M3 = 0b00011
    LIGHT_TRUCK_N1 = 0b00100
    HEAVY_TRUCK_N2 = 0b00101
    HEAVY_TRUCK_N3 = 0b00110
    MOTORCYCLE_L1E = 0b00111
    MOTORCYCLE_L2E = 0b01000
    MOTORCYCLE_L3E = 0b01001
    MOTORCYCLE_L4E = 0b01010
    MOTORCYCLE_L5E = 0b01011
    MOTORCYCLE_L6E = 0b01100
    MOTORCYCLE_L7E = 0b01101


class EGTS_SRVRP(enum.IntEnum):
    """
    SRVRP (Service Routing Priority) — приоритет с точки зрения трансляции данных (Таблица 25)

    Attributes:
        HIGHEST (0b00): Наивысший
        HIGH (0b01): Высокий
        MEDIUM (0b10): Средний
        LOWEST (0b11): Низкий
    """

    HIGHEST = 0b00
    HIGH = 0b01
    MEDIUM = 0b10
    LOWEST = 0b11


class EGTS_SERVICE_STATE(enum.IntEnum):
    """
    SST (Service Statement) — состояние сервиса (Таблица 26 ГОСТ 33465-2015)

    Attributes:
        IN_SERVICE (0): В рабочем состоянии, разрешен
        OUT_OF_SERVICE (128): В нерабочем состоянии (выключен)
        DENIED (129): Запрещен для использования
        NO_CONF (130): Не настроен
        TEMP_UNAVAIL (131): Временно недоступен
    """

    IN_SERVICE = 0
    OUT_OF_SERVICE = 128
    DENIED = 129
    NO_CONF = 130
    TEMP_UNAVAIL = 131


# Константы для состояний сервиса (для обратной совместимости)
EGTS_SST_IN_SERVICE = 0
EGTS_SST_OUT_OF_SERVICE = 128
EGTS_SST_DENIED = 129
EGTS_SST_NO_CONF = 130
EGTS_SST_TEMP_UNAVAIL = 131


# -----------------------------------------------------------------------------
# COMMANDS сервис перечисления (Раздел 6.7.3)
# -----------------------------------------------------------------------------

class EGTS_COMMAND_TYPE(enum.IntEnum):
    """
    CT (Command Type) — тип команды/сообщения (Таблица 29 ГОСТ 33465-2015)

    Биты 7-4 поля CT.

    Attributes:
        COMCONF (0b0001): Подтверждение о приеме/выполнении команды
        MSGCONF (0b0010): Подтверждение о приеме сообщения
        MSGFROM (0b0011): Информационное сообщение от УСВ
        MSGTO (0b0100): Сообщение для вывода на устройство ТС
        COM (0b0101): Команда для выполнения на ТС
        DELCOM (0b0110): Удаление команды из очереди
        SUBREQ (0b0111): Дополнительный подзапрос к команде
        DELIV (0b1000): Подтверждение о доставке
    """

    COMCONF = 0b0001
    MSGCONF = 0b0010
    MSGFROM = 0b0011
    MSGTO = 0b0100
    COM = 0b0101
    DELCOM = 0b0110
    SUBREQ = 0b0111
    DELIV = 0b1000


# Константы для типов команд (для обратной совместимости)
EGTS_CT_COMCONF = 0b0001
EGTS_CT_MSGCONF = 0b0010
EGTS_CT_MSGFROM = 0b0011
EGTS_CT_MSGTO = 0b0100
EGTS_CT_COM = 0b0101
EGTS_CT_DELCOM = 0b0110
EGTS_CT_SUBREQ = 0b0111
EGTS_CT_DELIV = 0b1000


class EGTS_CONFIRMATION_TYPE(enum.IntEnum):
    """
    CCT (Command Confirmation Type) — тип подтверждения (Таблица 29 ГОСТ 33465-2015)

    Биты 3-0 поля CT+CCT.

    Attributes:
        OK (0b0000): Успешное выполнение, положительный ответ
        ERROR (0b0001): Обработка завершилась ошибкой
        ILL (0b0010): Команда запрещена или не разрешена
        DEL (0b0011): Команда успешно удалена
        NFOUND (0b0100): Команда для удаления не найдена
        NCONF (0b0101): Успешное выполнение, отрицательный ответ
        INPROG (0b0110): Команда в обработке (длительное выполнение)
    """

    OK = 0b0000
    ERROR = 0b0001
    ILL = 0b0010
    DEL = 0b0011
    NFOUND = 0b0100
    NCONF = 0b0101
    INPROG = 0b0110


# Константы для типов подтверждений (для обратной совместимости)
EGTS_CC_OK = 0b0000
EGTS_CC_ERROR = 0b0001
EGTS_CC_ILL = 0b0010
EGTS_CC_DEL = 0b0011
EGTS_CC_NFOUND = 0b0100
EGTS_CC_NCONF = 0b0101
EGTS_CC_INPROG = 0b0110


class EGTS_CHARSET(enum.IntEnum):
    """
    CHS (Charset) — кодировка символов в поле CD (Таблица 29 ГОСТ 33465-2015)

    Attributes:
        CP1251 (0): CP-1251
        ASCII (1): IA5 (CCITT T.50)/ASCII (ANSI X3.4)
        BINARY_ALT (2): Бинарные данные
        LATIN1 (3): Latin 1
        BINARY (4): Бинарные данные
        JIS (5): JIS (X 0208-1990)
        CYRILLIC (6): Cyrillic
        LATIN_HEBREW (7): Latin/Hebrew
        UCS2 (8): UCS2
    """

    CP1251 = 0
    ASCII = 1
    BINARY_ALT = 2
    LATIN1 = 3
    BINARY = 4
    JIS = 5
    CYRILLIC = 6
    LATIN_HEBREW = 7
    UCS2 = 8


# Константы для кодировок (для обратной совместимости)
EGTS_CHS_CP1251 = 0
EGTS_CHS_ASCII = 1
EGTS_CHS_BINARY_ALT = 2
EGTS_CHS_LATIN1 = 3
EGTS_CHS_BINARY = 4
EGTS_CHS_JIS = 5
EGTS_CHS_CYRILLIC = 6
EGTS_CHS_LATIN_HEBREW = 7
EGTS_CHS_UCS2 = 8


class EGTS_PARAM_ACTION(enum.IntEnum):
    """
    ACT (Action) — действие над параметром (Таблица 30 ГОСТ 33465-2015)

    Биты 2-0 поля SZ+ACT.

    Attributes:
        PARAMS (0): Параметры команды
        GET (1): Запрос значения
        SET (2): Установка значения
        ADD (3): Добавление нового параметра
        DELETE (4): Удаление параметра
    """

    PARAMS = 0
    GET = 1
    SET = 2
    ADD = 3
    DELETE = 4


# Константы для действий (для обратной совместимости)
EGTS_ACT_PARAMS = 0
EGTS_ACT_GET = 1
EGTS_ACT_SET = 2
EGTS_ACT_ADD = 3
EGTS_ACT_DELETE = 4


# -----------------------------------------------------------------------------
# FIRMWARE сервис перечисления (Раздел 6.7.4)
# -----------------------------------------------------------------------------

# 6.7.4.1 Поле OA (Object Attribute) - атрибут объекта
EGTS_OA_STANDARD = 0x00
"""OA = 0x00: Стандартное обновление."""

EGTS_OA_CRITICAL = 0x01
"""OA = 0x01: Критическое обновление."""

EGTS_OA_CONFIG = 0x02
"""OA = 0x02: Конфигурация."""


class EGTS_OBJECT_ATTRIBUTE(enum.IntEnum):
    """
    OA (Object Attribute) — атрибут объекта (Таблица 37 ГОСТ 33465-2015)

    Attributes:
        STANDARD (0x00): Стандартное обновление
        CRITICAL (0x01): Критическое обновление
        CONFIG (0x02): Конфигурация
    """

    STANDARD = 0x00
    CRITICAL = 0x01
    CONFIG = 0x02


class EGTS_OBJECT_TYPE(enum.IntEnum):
    """
    OT (Object Type) — тип сущности по содержанию (Таблица 37 ГОСТ 33465-2015)

    Attributes:
        FIRMWARE (0x00): Данные внутреннего ПО («прошивка»)
        CONFIG (0x01): Блок конфигурационных параметров
    """

    FIRMWARE = 0x00
    CONFIG = 0x01


class EGTS_TARGET_MODULE_TYPE(enum.IntEnum):
    """
    MT (Module Type) в ODH — тип модуля, для которого предназначена сущность (Таблица 37)

    Attributes:
        PERIPHERAL (0x00): Периферийное оборудование
        MAIN_DEVICE (0x01): УСВ
    """

    PERIPHERAL = 0x00
    MAIN_DEVICE = 0x01


# -----------------------------------------------------------------------------
# 6.7.3.2 Команды для УСВ (Таблица 32 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

# Псевдонимы для обратной совместимости (использовать EcallCommand enum)
EGTS_CMD_ECALL_REQ = EcallCommand.ECALL_REQ.value
EGTS_CMD_ECALL_MSD_REQ = EcallCommand.ECALL_MSD_REQ.value
EGTS_CMD_ACCEL_DATA = EcallCommand.ACCEL_DATA.value
EGTS_CMD_TRACK_DATA = EcallCommand.TRACK_DATA.value
EGTS_CMD_ECALL_DEREGISTRATION = EcallCommand.ECALL_DEREGISTRATION.value


# -----------------------------------------------------------------------------
# 6.7.3.2 / 7.5.1 Параметры УСВ (Таблица 34, 47 ГОСТ 33465-2015)
# -----------------------------------------------------------------------------

# Параметры передачи данных
EGTS_PARAM_GPRS_APN = 0x0101
"""EGTS_GPRS_APN (0x0101): Точка доступа GPRS."""

EGTS_PARAM_SERVER_ADDRESS = 0x0102
"""EGTS_SERVER_ADDRESS (0x0102): Адрес сервера (IP:port или domain:port)."""

EGTS_PARAM_SIM_PIN = 0x0103
"""EGTS_SIM_PIN (0x0103): PIN-код SIM-карты."""

EGTS_PARAM_AUTOMATIC_REGISTRATION = 0x0104
"""EGTS_AUTOMATIC_REGISTRATION (0x0104): Автоматическая регистрация в сети."""

EGTS_PARAM_REGISTRATION_ATTEMPTS = 0x0105
"""EGTS_REGISTRATION_ATTEMPTS (0x0105): Число попыток регистрации."""

EGTS_PARAM_REGISTRATION_TIMEOUT = 0x0106
"""EGTS_REGISTRATION_TIMEOUT (0x0106): Таймаут регистрации, сек."""

EGTS_PARAM_GPRS_CONNECTION_ATTEMPTS = 0x0107
"""EGTS_GPRS_CONNECTION_ATTEMPTS (0x0107): Число попыток установки GPRS-сессии."""

EGTS_PARAM_GPRS_CONNECTION_TIMEOUT = 0x0108
"""EGTS_GPRS_CONNECTION_TIMEOUT (0x0108): Таймаут установки GPRS-сессии, сек."""

EGTS_PARAM_TCP_CONNECTION_ATTEMPTS = 0x0109
"""EGTS_TCP_CONNECTION_ATTEMPTS (0x0109): Число попыток установки TCP/IP-соединения."""

EGTS_PARAM_TCP_CONNECTION_TIMEOUT = 0x010A
"""EGTS_TCP_CONNECTION_TIMEOUT (0x010A): Таймаут установки TCP/IP-соединения, сек."""

EGTS_PARAM_INACTIVITY_TIMEOUT = 0x010B
"""EGTS_INACTIVITY_TIMEOUT (0x010B): Время неактивности до разрыва соединения, мин."""

EGTS_PARAM_SERVICE_ENABLE = 0x010C
"""EGTS_SERVICE_ENABLE (0x010C): Разрешение использования сервисов."""

EGTS_PARAM_NETWORK_SEARCH_PERIOD = 0x010D
"""EGTS_NETWORK_SEARCH_PERIOD (0x010D): Период поиска сети при потере, сек."""

# Параметры внутрипамятного хранения
EGTS_PARAM_INT_MEM_ENABLE = 0x0118
"""EGTS_INT_MEM_ENABLE (0x0118): Использование внутренней памяти."""

EGTS_PARAM_INT_MEM_TRANSMIT_INTERVAL = 0x0119
"""EGTS_INT_MEM_TRANSMIT_INTERVAL (0x0119): Интервал отправки из памяти, сек."""

EGTS_PARAM_INT_MEM_TRANSMIT_ATTEMPTS = 0x011A
"""EGTS_INT_MEM_TRANSMIT_ATTEMPTS (0x011A): Число попыток отправки из памяти."""

EGTS_PARAM_INT_MEM_RECORD_AMOUNT = 0x011B
"""EGTS_INT_MEM_RECORD_AMOUNT (0x011B): Максимальное число записей в памяти."""

EGTS_PARAM_INT_MEM_FULL_BEHAVIOR = 0x011C
"""EGTS_INT_MEM_FULL_BEHAVIOR (0x011C): Поведение при переполнении (0=циклически, 1=блокировка)."""

# Параметры для тестирования
EGTS_PARAM_TEST_REGISTRATION_PERIOD = 0x0201
"""EGTS_TEST_REGISTRATION_PERIOD (0x0201): Период тестового пакета регистрации, сек."""

EGTS_PARAM_TEST_MODE_ON = 0x0202
"""EGTS_TEST_MODE_ON (0x0202): Режим тестирования включен."""

EGTS_PARAM_TEST_MODE_START_TIME = 0x0203
"""EGTS_TEST_MODE_START_TIME (0x0203): Время начала тестирования."""

EGTS_PARAM_TEST_MODE_END_TIME = 0x0204
"""EGTS_TEST_MODE_END_TIME (0x0204): Время окончания тестирования."""

EGTS_PARAM_TEST_MODE_END_DISTANCE = 0x020A
"""EGTS_TEST_MODE_END_DISTANCE (0x020A): Дистанция выключения тестирования, м."""

# Режим «Автосервис»
EGTS_PARAM_GARAGE_MODE_END_DISTANCE = 0x020B
"""EGTS_GARAGE_MODE_END_DISTANCE (0x020B): Дистанция выключения автосервиса, м."""

EGTS_PARAM_GARAGE_MODE_PIN = 0x020C
"""EGTS_GARAGE_MODE_PIN (0x020C): Линия сигнала режима «Автосервис»."""

# Прочие параметры
EGTS_PARAM_GNSS_POWER_OFF_TIME = 0x0301
"""EGTS_GNSS_POWER_OFF_TIME (0x0301): Время отключения питания ГНСС после зажигания, мс."""

EGTS_PARAM_GNSS_DATA_RATE = 0x0302
"""EGTS_GNSS_DATA_RATE (0x0302): Темп выдачи данных ГНСС, Гц."""

EGTS_PARAM_GNSS_MIN_ELEVATION = 0x0303
"""EGTS_GNSS_MIN_ELEVATION (0x0303): Минимальный угол возвышения спутников, град."""

# Параметры устройства
EGTS_PARAM_UNIT_ID = 0x0404
"""EGTS_UNIT_ID (0x0404): Уникальный идентификатор УСВ."""

EGTS_PARAM_UNIT_IMEI = 0x0405
"""EGTS_UNIT_IMEI (0x0405): IMEI устройства."""

EGTS_PARAM_UNIT_RS485_BAUD_RATE = 0x0406
"""EGTS_UNIT_RS485_BAUD_RATE (0x0406): Скорость порта RS485, бит/с."""

EGTS_PARAM_UNIT_RS485_STOP_BITS = 0x0407
"""EGTS_UNIT_RS485_STOP_BITS (0x0407): Число стоп-битов RS485."""

EGTS_PARAM_UNIT_RS485_PARITY = 0x0408
"""EGTS_UNIT_RS485_PARITY (0x0408): Проверка четности RS485 (0=нет, 1=чет, 2=нечет)."""

EGTS_PARAM_UNIT_HOME_DISPATCHER_ID = 0x0409
"""EGTS_UNIT_HOME_DISPATCHER_ID (0x0409): Идентификатор домашней ТП."""

EGTS_PARAM_SERVICE_AUTH_METHOD = 0x0410
"""EGTS_SERVICE_AUTH_METHOD (0x0410): Метод использования сервисов (0=простой, 1=запросный)."""

EGTS_PARAM_SERVICE_CHECK_IN_PERIOD = 0x0411
"""EGTS_SERVICE_CHECK_IN_PERIOD (0x0411): Период сервисных проверочных пакетов, сек."""

EGTS_PARAM_SERVICE_CHECK_IN_ATTEMPTS = 0x0412
"""EGTS_SERVICE_CHECK_IN_ATTEMPTS (0x0412): Число попыток отправки проверочных пакетов."""

EGTS_PARAM_SERVICE_PACKET_TOUT = 0x0413
"""EGTS_SERVICE_PACKET_TOUT (0x0413): Таймаут ожидания подтверждения сервисного пакета, сек."""

EGTS_PARAM_SERVICE_PACKET_RETRANSMIT_ATTEMPTS = 0x0414
"""EGTS_SERVICE_PACKET_RETRANSMIT_ATTEMPTS (0x0414): Число попыток повторной отправки сервисного пакета."""

EGTS_PARAM_UNIT_MIC_LEVEL = 0x0501
"""EGTS_UNIT_MIC_LEVEL (0x0501): Уровень чувствительности микрофона."""

EGTS_PARAM_UNIT_SPK_LEVEL = 0x0502
"""EGTS_UNIT_SPK_LEVEL (0x0502): Уровень громкости динамика."""

# Параметры ECALL (Таблица 47)
EGTS_PARAM_ECALL_TEST_NUMBER = 0x020D
"""EGTS_ECALL_TEST_NUMBER (0x020D): Телефонный номер для тестовых звонков."""

EGTS_PARAM_ECALL_ON = 0x0210
"""EGTS_ECALL_ON (0x0210): Возможность осуществления экстренного вызова."""

EGTS_PARAM_ECALL_CRASH_SIGNAL_INTERNAL = 0x0211
"""EGTS_ECALL_CRASH_SIGNAL_INTERNAL (0x0211): Встроенный датчик аварии."""

EGTS_PARAM_ECALL_CRASH_SIGNAL_EXTERNAL = 0x0212
"""EGTS_ECALL_CRASH_SIGNAL_EXTERNAL (0x0212): Внешний датчик аварии."""

EGTS_PARAM_ECALL_SOS_BUTTON_TIME = 0x0213
"""EGTS_ECALL_SOS_BUTTON_TIME (0x0213): Длительность нажатия кнопки «Экстренный вызов», мс."""

EGTS_PARAM_ECALL_NO_AUTOMATIC_TRIGGERING = 0x0214
"""EGTS_ECALL_NO_AUTOMATIC_TRIGGERING (0x0214): Отключение автоматического вызова."""

EGTS_PARAM_ASI15_TRESHOLD = 0x0215
"""EGTS_ASI15_TRESHOLD (0x0215): Порог срабатывания датчика ДТП (ASI15)."""

EGTS_PARAM_ECALL_MODE_PIN = 0x0216
"""EGTS_ECALL_MODE_PIN (0x0216): Линия сигнала режима «ЭРА»."""

EGTS_PARAM_ECALL_CCFT = 0x0217
"""EGTS_ECALL_CCFT (0x0217): Длительность счетчика автоматического прекращения звонка, мин."""

EGTS_PARAM_ECALL_INVITATION_SIGNAL_DURATION = 0x0218
"""EGTS_ECALL_INVITATION_SIGNAL_DURATION (0x0218): Длительность сигнала INVITATION, мс."""

EGTS_PARAM_ECALL_SEND_MSG_PERIOD = 0x0219
"""EGTS_ECALL_SEND_MSG_PERIOD (0x0219): Период сообщения SEND MSG, мс."""

EGTS_PARAM_ECALL_AL_ACK_PERIOD = 0x021A
"""EGTS_ECALL_AL_ACK_PERIOD (0x021A): Период AL-ACK, мс."""

EGTS_PARAM_ECALL_MSD_MAX_TRANSMISSION_TIME = 0x021B
"""EGTS_ECALL_MSD_MAX_TRANSMISSION_TIME (0x021B): Максимальная длительность передачи МНД, сек."""

EGTS_PARAM_ECALL_NAD_DEREGISTRATION_TIMER = 0x021D
"""EGTS_ECALL_NAD_DEREGISTRATION_TIMER (0x021D): Таймер дерегистрации GSM/UMTS модуля, ч."""

EGTS_PARAM_ECALL_DIAL_DURATION = 0x021E
"""EGTS_ECALL_DIAL_DURATION (0x021E): Длительность дозвона, сек."""

EGTS_PARAM_ECALL_AUTO_DIAL_ATTEMPTS = 0x021F
"""EGTS_ECALL_AUTO_DIAL_ATTEMPTS (0x021F): Количество попыток дозвона при автоматическом вызове."""

EGTS_PARAM_ECALL_MANUAL_DIAL_ATTEMPTS = 0x0220
"""EGTS_ECALL_MANUAL_DIAL_ATTEMPTS (0x0220): Количество попыток дозвона при ручном вызове."""

EGTS_PARAM_ECALL_MANUAL_CAN_CANCEL = 0x0221
"""EGTS_ECALL_MANUAL_CAN_CANCEL (0x0221): Признак возможности отмены ручного вызова."""

EGTS_PARAM_ECALL_SMS_FALLBACK_NUMBER = 0x0222
"""EGTS_ECALL_SMS_FALLBACK_NUMBER (0x0222): Номер SMS-центра для отправки МНД."""

# Запись профиля ускорения при ДТП
EGTS_PARAM_CRASH_RECORD_TIME = 0x0224
"""EGTS_CRASH_RECORD_TIME (0x0224): Время записи профиля ускорения, сек."""

EGTS_PARAM_CRASH_RECORD_RESOLUTION = 0x0225
"""EGTS_CRASH_RECORD_RESOLUTION (0x0225): Разрешение по времени записи профиля ускорения, мс."""

EGTS_PARAM_CRASH_PRE_RECORD_TIME = 0x0226
"""EGTS_CRASH_PRE_RECORD_TIME (0x0226): Время предыстории записи профиля ускорения, сек."""

EGTS_PARAM_CRASH_PRE_RECORD_RESOLUTION = 0x0227
"""EGTS_CRASH_PRE_RECORD_RESOLUTION (0x0227): Разрешение предыстории профиля ускорения, мс."""

# Запись траектории движения при ДТП
EGTS_PARAM_TRACK_RECORD_TIME = 0x0228
"""EGTS_TRACK_RECORD_TIME (0x0228): Время записи траектории после события, сек."""

EGTS_PARAM_TRACK_RECORD_RESOLUTION = 0x0229
"""EGTS_TRACK_RECORD_RESOLUTION (0x0229): Разрешение записи траектории после события, мс."""

EGTS_PARAM_TRACK_PRE_RECORD_TIME = 0x022A
"""EGTS_TRACK_PRE_RECORD_TIME (0x022A): Время записи предыстории траектории, сек."""

# Параметры ТС
EGTS_PARAM_VEHICLE_VIN = 0x0230
"""EGTS_VEHICLE_VIN (0x0230): VIN-код транспортного средства."""

EGTS_PARAM_VEHICLE_TYPE = 0x0231
"""EGTS_VEHICLE_TYPE (0x0231): Тип транспортного средства."""

EGTS_PARAM_VEHICLE_PROPULSION_STORAGE_TYPE = 0x0232
"""EGTS_VEHICLE_PROPULSION_STORAGE_TYPE (0x0232): Тип энергоносителя ТС."""


# =============================================================================
# Коды результатов обработки (Приложение В, таблица В.1 ГОСТ 33465-2015)
# =============================================================================

class RecordStatus(enum.IntEnum):
    """
    Коды результатов обработки записи (Приложение В, таблица В.1 ГОСТ 33465-2015)

    Используется в подзаписи EGTS_SR_RESULT_CODE.

    0-127: Успешные коды
    128-255: Коды ошибок

    Attributes:
        EGTS_PC_OK (0): Успешно обработано
        EGTS_PC_IN_PROGRESS (1): В процессе обработки
        EGTS_PC_UNS_PROTOCOL (128): Неподдерживаемый протокол
        EGTS_PC_DECRYPT_ERROR (129): Ошибка декодирования
        EGTS_PC_PROC_DENIED (130): Обработка запрещена
        EGTS_PC_INC_HEADERFORM (131): Неверный формат заголовка
        EGTS_PC_INC_DATAFORM (132): Неверный формат данных
        EGTS_PC_UNS_TYPE (133): Неподдерживаемый тип
        EGTS_PC_NOTEN_PARAMS (134): Неверное число параметров
        EGTS_PC_DBL_PROC (135): Попытка повторной обработки
        EGTS_PC_PROC_SRC_DENIED (136): Обработка данных от источника запрещена
        EGTS_PC_HEADERCRC_ERROR (137): Ошибка контрольной суммы заголовка
        EGTS_PC_DATACRC_ERROR (138): Ошибка контрольной суммы данных
        EGTS_PC_INVDATALEN (139): Некорректная длина данных
        EGTS_PC_ROUTE_NFOUND (140): Маршрут не найден
        EGTS_PC_ROUTE_CLOSED (141): Маршрут закрыт
        EGTS_PC_ROUTE_DENIED (142): Маршрутизация запрещена
        EGTS_PC_INVADDR (143): Неверный адрес
        EGTS_PC_TTLEXPIRED (144): Превышено число ретрансляции данных
        EGTS_PC_NO_ACK (145): Нет подтверждения
        EGTS_PC_OBJ_NFOUND (146): Объект не найден
        EGTS_PC_EVNT_NFOUND (147): Событие не найдено
        EGTS_PC_SRVC_NFOUND (148): Сервис не найден
        EGTS_PC_SRVC_DENIED (149): Сервис запрещен
        EGTS_PC_SRVC_UNKN (150): Неизвестный тип сервиса
        EGTS_PC_AUTH_DENIED (151): Авторизация запрещена
        EGTS_PC_ALREADY_EXISTS (152): Объект уже существует
        EGTS_PC_ID_NFOUND (153): Идентификатор не найден
        EGTS_PC_INC_DATETIME (154): Неправильная дата и время
    """

    # Успешные коды (0-127)
    EGTS_PC_OK = 0  # Успешно обработано
    EGTS_PC_IN_PROGRESS = 1  # В процессе обработки

    # Ошибки протокола (128-147)
    EGTS_PC_UNS_PROTOCOL = 128  # Неподдерживаемый протокол
    EGTS_PC_DECRYPT_ERROR = 129  # Ошибка декодирования
    EGTS_PC_PROC_DENIED = 130  # Обработка запрещена
    EGTS_PC_INC_HEADERFORM = 131  # Неверный формат заголовка
    EGTS_PC_INC_DATAFORM = 132  # Неверный формат данных
    EGTS_PC_UNS_TYPE = 133  # Неподдерживаемый тип
    EGTS_PC_NOTEN_PARAMS = 134  # Неверное число параметров
    EGTS_PC_DBL_PROC = 135  # Попытка повторной обработки
    EGTS_PC_PROC_SRC_DENIED = 136  # Обработка данных от источника запрещена
    EGTS_PC_HEADERCRC_ERROR = 137  # Ошибка контрольной суммы заголовка
    EGTS_PC_DATACRC_ERROR = 138  # Ошибка контрольной суммы данных
    EGTS_PC_INVDATALEN = 139  # Некорректная длина данных
    EGTS_PC_ROUTE_NFOUND = 140  # Маршрут не найден
    EGTS_PC_ROUTE_CLOSED = 141  # Маршрут закрыт
    EGTS_PC_ROUTE_DENIED = 142  # Маршрутизация запрещена
    EGTS_PC_INVADDR = 143  # Неверный адрес
    EGTS_PC_TTLEXPIRED = 144  # Превышено число ретрансляции данных
    EGTS_PC_NO_ACK = 145  # Нет подтверждения
    EGTS_PC_OBJ_NFOUND = 146  # Объект не найден
    EGTS_PC_EVNT_NFOUND = 147  # Событие не найдено

    # Ошибки сервиса (148-154)
    EGTS_PC_SRVC_NFOUND = 148  # Сервис не найден
    EGTS_PC_SRVC_DENIED = 149  # Сервис запрещен
    EGTS_PC_SRVC_UNKN = 150  # Неизвестный тип сервиса
    EGTS_PC_AUTH_DENIED = 151  # Авторизация запрещена
    EGTS_PC_ALREADY_EXISTS = 152  # Объект уже существует
    EGTS_PC_ID_NFOUND = 153  # Идентификатор не найден
    EGTS_PC_INC_DATETIME = 154  # Неправильная дата и время


# =============================================================================
# Перечисления из оригинального types.py (удалены из-за дублирования)
# =============================================================================

# CommandType удален - использовать EGTS_COMMAND_TYPE
# Восстановлен для обратной совместимости с префиксами CT_
class CommandType(enum.IntEnum):
    """Устарело. Использовать EGTS_COMMAND_TYPE"""
    CT_COMCONF = 0x01
    CT_MSGCONF = 0x02
    CT_MSGFROM = 0x03
    CT_MSGTO = 0x04
    CT_COM = 0x05
    CT_DELCOM = 0x06
    CT_SUBREQ = 0x07
    CT_DELIV = 0x08

# CommandAction удален - использовать EGTS_PARAM_ACTION
CommandAction = EGTS_PARAM_ACTION

# ConfirmationType удален - использовать EGTS_CONFIRMATION_TYPE
# Восстановлен для обратной совместимости с префиксами CC_
class ConfirmationType(enum.IntEnum):
    """Устарело. Использовать EGTS_CONFIRMATION_TYPE"""
    CC_OK = 0x00
    CC_ERROR = 0x01
    CC_ILL = 0x02
    CC_DEL = 0x03
    CC_NFOUND = 0x04
    CC_NCONF = 0x05
    CC_INPROG = 0x06

# ServiceState удален - использовать EGTS_SERVICE_STATE
ServiceState = EGTS_SERVICE_STATE

# CommandCode удален - использовать константы EGTS_PARAM_*
# Псевдонимы для наиболее используемых
EGTS_GET_VERSION = 0x0001
EGTS_SET_VERSION = 0x0002
EGTS_RESET = 0x0003
EGTS_GET_PARAMS = 0x0004
EGTS_SET_PARAMS = 0x0005

# CommandCode как псевдоним для обратной совместимости
class CommandCode(enum.IntEnum):
    """Устарело. Использовать константы EGTS_PARAM_*"""
    EGTS_GET_VERSION = 0x0001
    EGTS_SET_VERSION = 0x0002
    EGTS_RESET = 0x0003
    EGTS_GET_PARAMS = 0x0004
    EGTS_SET_PARAMS = 0x0005


# =============================================================================
# КОНСТАНТЫ ДЛЯ RESPONSE (ГОСТ 33465-2015, раздел 5.6.1.3)
# =============================================================================

# Позиции полей в транспортном пакете RESPONSE
RESPONSE_PRV_OFFSET = 0      # Байт 0: PRV (Protocol Version)
RESPONSE_SKID_OFFSET = 1     # Байт 1: SKID (Security Key ID)
RESPONSE_FLAGS_OFFSET = 2    # Байт 2: Flags
RESPONSE_HL_OFFSET = 3       # Байт 3: HL (Header Length)
RESPONSE_HE_OFFSET = 4       # Байт 4: HE (Header Extension)
RESPONSE_FDL_OFFSET = 5      # Байт 5-6: FDL (Frame Data Length)
RESPONSE_PID_OFFSET = 7      # Байт 7-8: PID (Packet Identifier)
RESPONSE_PT_OFFSET = 9       # Байт 9: PT (Packet Type)
RESPONSE_HCS_OFFSET = 10     # Байт 10: HCS (Header Check Sum)

# Позиции полей в записи RESPONSE
RESPONSE_RECORD_RL_OFFSET = 0   # Байт 0-1: RL (Record Length)
RESPONSE_RECORD_RN_OFFSET = 2   # Байт 2-3: RN (Record Number)
RESPONSE_RECORD_RFL_OFFSET = 4  # Байт 4: RFL (Record Flags)
RESPONSE_RECORD_RST_OFFSET = 5  # Байт 5: RST (Result Service Type)

# Размеры полей RESPONSE
RESPONSE_HEADER_SIZE = 11    # Размер заголовка RESPONSE (10 байт + HCS)
RESPONSE_RECORD_SIZE = 6     # Размер записи подтверждения (RL + RN + RFL + RST)
RESPONSE_DATA_CRC_SIZE = 2   # Размер CRC-16 данных
RESPONSE_TOTAL_SIZE = 19    # Общий размер минимального RESPONSE (10 + 1 + 6 + 2)

# Коды ошибок RESULT CODE (Приложение В)
EGTS_PC_HEADERCRC_ERROR = 137  # Ошибка CRC-8 заголовка
EGTS_PC_DATACRC_ERROR = 138    # Ошибка CRC-16 данных
EGTS_PC_INVDATALEN = 139       # Некорректная длина данных
