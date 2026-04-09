# Known Issues — OMEGA_EGTS

Известные проблемы, ограничения и плановые задачи.

**Обновлено:** 08.04.2026 | **ТЗ:** v7.0 | **Итерация 3 завершена:** session.py (61 тест, 93%, внешний аудит 9.5/10)

---

## 🔴 Критические

_Проект на стадии проектирования — критических проблем в коде пока нет. Ниже — риски архитектуры, которые нужно контролировать при реализации._

| ID | Описание | Риск | Планируемое решение |
|----|----------|------|---------------------|
| CR-006 | **Структура `libs/` отличается от ТЗ** | ТЗ (раздел 2.4) определяет `egts_protocol/base.py, v2015.py, v2023.py, sms.py`. Реализовано: `egts_protocol_iface/` + `egts_protocol_gost2015/gost2015_impl/`. Обоснование — dependency inversion: ядро зависит только от интерфейса. См. CHANGELOG.md | Задокументировано. Если потребуется строго по ТЗ — рефакторинг за 1–2 часа |
| CR-001 | Circular dependency: `PacketDispatcher` ↔ `SessionManager` | При реализации может возникнуть циклический импорт | Передача ссылок через конструктор, не через `import` |
| CR-002 | Порядок логов при parallel-обработке EventBus | Parallel-хендлеры (`asyncio.gather`) не гарантируют порядок записи | LogManager — буферизация + сортировка по timestamp |
| CR-003 | Голосовой канал eCall — механизм не расписан в ТЗ | Сценарий №5 не будет полным без проверки тонового модема | Этап 6: интеграция с реальным CMW-500 |
| CR-004 | ~~`crcmod` — внешняя зависимость для CRC~~ | Решено: чистая Python-реализация в `crc.py` | — |
| CR-005 | Параллельные агенты перезаписывают `adapter.py` | Задачи 2.3 и 2.4 редактируют один файл — SMS-методы затираются | Координировать изменения; после завершения 2.3 зафиксировать SMS |

---

## 🟡 Известные ограничения

| ID | Описание | Статус | Планируемое решение |
|----|----------|--------|---------------------|
| KI-001 | Проект на стадии реализации — основная логика ещё не написана | Открыто | Этап 1: CLI MVP |
| KI-002 | Нет поддержки ГОСТ 33465-2023 — только редакция 2015 | Открыто | Этап 4 |
| KI-003 | Нет реального CMW-500 — используется эмулятор | Открыто | Этап 6: интеграция с реальным железом |
| KI-004 | Нет GUI — только CLI | Открыто | Этап 5: PyQt6/PySide6 |
| KI-005 | Нет готовых сценариев тестирования — только описание в ТЗ | Открыто | Этап 3 |
| KI-006 | `command.send` через EventBus — лишний уровень асинхронности | Сценарий не знает, отправился ли пакет или только запланирован | Мониторинг через `command.sent` + timeout |
| KI-007 | `credentials.json` на Windows — только `attrib +h` | Слабая защита, нет полноценного контроля доступа | Документировать рекомендацию ручного ограничения ACL |
| KI-008 | ~~`egts_protocol_gost2015/adapter.py` — заглушка~~ | Решено: парсинг/сборка + SMS PDU реализованы | — |
| KI-009 | ~~`Packet` iface: нет полей `header_length`, `connection_id`~~ | Решено: поля вычисляются при парсинге | — |
| KI-010 | ~~`MAX_PACKET_SIZE = 4096`~~ | Решено: используется значение из ГОСТ (65535) | — |
| KI-011 | ~~`parse_packet` — `crc8_valid` захардкожен~~ | Решено (R-024): явный `verify_crc8()` | — |
| KI-012 | `_map_record_to_internal` бросит `ValueError` при неизвестном `service_type` | Новые сервисы (ГОСТ 2023) не попадут в `InternalServiceType` enum | Добавить fallback-механизм |
| KI-013 | Дублирование `crc.py` — `_internal/crc.py` и `gost2015/crc.py` идентичны | При изменении одного нужно менять другой — риск рассинхронизации CRC | Сделать `crc.py` реэкспортом из `_internal/crc.py` |
| KI-014 | O(n²) конкатенация байтов в `to_bytes` (`packet.py`, `record.py`, `subrecord.py`) | `ppu_data += record.to_bytes()` в цикле создаёт новый объект на каждой итерации | Заменить на `b"".join([...])` или `bytearray` |
| KI-015 | `SMSReassembler` — неограниченный рост памяти | `_fragments` dict без TTL-очистки; до 8.7 МБ мусора в худшем случае | Добавить timestamp-based cleanup |
| KI-016 | ASN.1 eCall — отсутствует файл `msd.asn` | `create_msd_data()` и `decode_msd_data()` бросают `RuntimeError`; ASN.1-кодирование MSD не работает | Скопировать `msd.asn` из EGTS_GUI или задокументировать ограничение |
| KI-019 | `SMSReassembler` — нет TTL-очистки по времени | Незавершённые сообщения хранятся вечно при потере фрагментов | Добавить `time.monotonic` + TTL в `add_fragment()`; пока — Low, есть `remove_expired()` |
| KI-020 | `parse_service_info` — нет валидации SST | SST принимает любые 0–255, по ГОСТ допустимы: 0, 128, 129, 130, 131 | Добавить проверку или enum `SERVICE_STATES` из `types.py` |
| KI-021 | `serialize_service_info` — смешение форматов в списке | Поддерживает int и dict в одном списке без проверки | Унифицировать формат или добавить валидацию |
| KI-022 | Нет тестов `auth.py` | 1240 строк парсинга/сериализации 8 подзаписей без покрытия | Создать `test_auth.py` с roundtrip-тестами |

---

## 🟢 Решённые

| ID | Описание | Решение | Версия ТЗ |
|----|----------|---------|-----------|
| R-024 | `parse_packet` — `crc8_valid` захардкожен | Явный вызов `verify_crc8()`, сохранение статуса в iface-модель | 7.0 |
| R-023 | Нет SMS PDU в адаптере | `build_sms_pdu` / `parse_sms_pdu` через `sms.py`, 32 теста | 7.0 |
| R-022 | Нет уровня абстракции для EGTS-протокола | `egts_protocol_iface/` — `IEgtsProtocol` (`@runtime_checkable` Protocol), `create_protocol()` factory | 7.0 |
| R-021 | Нет моделей данных EGTS (Packet, Record, Subrecord) | Dataclass-контракты с `extra: dict`, `parse_error`, `raw_bytes`, методами `pr_flags()`/`rf_flags()` | 7.0 |
| R-020 | Config — нет реализации | Nested dataclass'ы, JSON загрузка, CLI merge с dot-notation, валидация, __str__ | 7.0 |
| R-019 | EventBus — нет реализации | `Event`, `EventBus` с `on()`/`off()`/`emit()`, ordered + parallel handlers | 7.0 |
| R-001 | Разрыв TcpServerManager → Pipeline — кто вызывает `process()` | Добавлен `PacketDispatcher` — единственный компонент, знающий о Pipeline | 6.0 |
| R-002 | Нет события для отправки команд из сценария | Добавлено `command.send` + `CommandDispatcher` | 6.0 |
| R-003 | EventBus — последовательный, блокирует подписчиков | `ordered` (FSM) + `parallel` (`asyncio.gather`) для остальных | 6.0 |
| R-004 | `_cleanup_seen_pids` — не LRU, удаляет случайные записи | `OrderedDict` с `move_to_end` при каждом обращении | 6.0 |
| R-005 | `chmod 600` не работает на Windows | Windows: `attrib +h` + предупреждение; Linux: `chmod 600` | 6.0 |
| R-006 | ExpectStep — не описан механизм ожидания | `asyncio.Event` + подписка на `packet.processed` + `wait_for` | 6.1 |
| R-007 | Нет replay-режима (офлайн-анализ) | `ReplaySource` — загрузка лога, эмит событий, фильтр дубликатов | 6.1 |
| R-008 | CMW-500 без обработки ошибок | `cmw.error` событие + retry в воркере очереди | 6.0 |
| R-009 | `context` в ExpectStep — замыкание, не определён | `self._context` — поле класса, устанавливается в `execute()` | 6.1 |
| R-010 | `_matches()` и `_get_nested()` не реализованы | Полная реализация: regex, диапазон, вложенные пути (`records[0].fields.RN`) | 6.1 |
| R-011 | Сценарий ждёт timeout при отключении УСВ | Подписка на `connection.changed` → возврат `ERROR` сразу | 6.1 |
| R-012 | `current_connection_id` — кто выставляет | Автоопределение через `_resolve_connection_id()` | 6.1 |
| R-013 | SendStep без `_build_packet()` — неясна загрузка | Реализовано: файл (относительно папки сценария) + шаблон с подстановкой | 6.1 |
| R-014 | ReplaySource обходит Pipeline → дубликаты дублируются | Фильтрация по PID + опция `pipeline=` для полного прохождения | 6.1 |
| R-015 | FSM молча игнорирует неожиданные пакеты | Добавлены переходы: CONNECTED→RUNNING, RUNNING→AUTHENTICATING | 6.1 |
| R-016 | `CrcValidationMiddleware` — хардкод `create_protocol("2015")` | `protocol` через `__init__` из конфига | 6.1 |
| R-017 | `command.error` не в таблице EventBus, нет обработки | Добавлено в таблицу + `try/except` в CommandDispatcher | 6.1 |
| R-018 | ScenarioContext без `gost_version`, `scenario_dir` | Добавлены поля + `_session_mgr` для автоопределения connection_id | 6.1 |
| R-025 | `create_sms_pdu` — нет проверки длины user_data | `ValueError` при user_data > 140 байт без `concatenated=True` | 7.0 |
| R-026 | `parse_sms_pdu` — нет валидации TP-MTI и TP-DCS | `ValueError` при MTI ∉ {0, 1} или DCS ≠ 0x04 | 7.0 |
| R-027 | `split_for_sms_concatenation` — недетерминированный `concat_ref` | Добавлен параметр `concat_ref: int | None = None` | 7.0 |
| R-028 | `auth.py` — сломанный импорт `.._internal.types` | Исправлен на `..types`, добавлен импорт `RESULT_CODES` из `types.py` | 7.0 |
| R-029 | `parse_result_code` — неполный словарь кодов (16 вместо 22+) | Использует `RESULT_CODES` из `types.py` (Приложение В ГОСТ) | 7.0 |
| R-030 | `parse_vehicle_data` — прямой `.decode("cp1251")` без StringEncoder | Заменён на `StringEncoder.decode()` | 7.0 |
| R-031 | `serialize_record_response` — mypy `no-any-return` | Переписан через `bytearray`, убран `type: ignore` | 7.0 |
| R-032 | `ecall.py` — сломанный импорт `.._internal.types` | Исправлен на `..types` | 7.0 |
| R-033 | `ecall.py` — `type: ignore` в 4 функциях сериализации | Переписаны через `bytearray`, убраны все `type: ignore` | 7.0 |
| R-034 | `ecall.py` — `create_msd_data()` без валидации параметров | Добавлена валидация latitude, longitude, direction, vehicle_type, crash_severity, num_occupants | 7.0 |
| R-035 | `ecall.py` — `parse_track_data` DIR извлекался всегда, игнорируя SDFE | Исправлен: DIR только при SDFE=1 (ГОСТ 33465 таблица 45) | 7.0 |
| R-036 | `ecall.py` — скорость парсилась как UINT16, игнорируя SPDH/DIRH | Исправлен: SPDL (14 бит) + SPDH (1 бит) = 15 бит, DIRH/SPDH байт, 9-битный DIR | 7.0 |
| R-037 | `ecall.py` — `serialize_accel_data` теряла точность (int вместо round) | Заменён `int(x / 0.1)` → `round(x / 0.1)` | 7.0 |
| R-038 | `ecall.py` — `asn1tools` не опционален — модуль не загружался без него | `try/except ImportError`, `_MSD_CODEC = None` если нет asn1tools | 7.0 |
| R-039 | `ecall.py` — `create_track_point` без конвертации градусов направления | Добавлена конвертация: градусы → 9-битное значение (0-359 → 0-511) | 7.0 |
| R-040 | `ecall.py` — LAT/LON парсились как INT32 со знаком, по ГОСТ — UINT32 по модулю | Исправлен парсинг: UINT32 + LAHS/LOHS для знака | 7.0 |
| R-041 | `ecall.py` — `create_track_point` без ограничения UINT32 для LAT/LON | Добавлен `min(val, 0xFFFFFFFF)` | 7.0 |
| R-042 | `ecall.py` — `serialize_track_data` сериализовал LAT/LON как INT32 | Исправлен: `abs()` + UINT32 LE, знак в LAHS/LOHS | 7.0 |
| R-043 | Создан `msd.asn` — ASN.1 спецификация MSD (ГОСТ 33464 Приложение А) | Файл `services/msd.asn` с MSDStructure, ERAAdditionalData | 7.0 |
| R-044 | `asn1tools` не в зависимостях | Добавлен `[project.optional-dependencies] asn1` в pyproject.toml | 7.0 |
| R-045 | `commands.py` — `_value2member_map_` — внутренний атрибут Enum | Заменён на `try/except ValueError` для `EGTS_COMMAND_TYPE` и `EGTS_CONFIRMATION_TYPE` | 7.0 |
| R-046 | `commands.py` — `EGTS_COMMAND_SZ_ACT_SIZE` не использовался | Убран из импорта, в `parse_command_details` заменён на `+ 1` | 7.0 |
| R-047 | `commands.py` — нет SZ-валидации для ACT=2 | Добавлена проверка `len(data) == 2**sz` только для ACT=2 (установка значения) | 7.0 |
| R-048 | `commands.py` — `create_message` тихо использовала CP1251 для BINARY | Добавлен `raise ValueError` для CHS=2/4, комментарий UCS2 ⊂ UTF-16 | 7.0 |
| R-049 | `commands.py` — `action` только `EGTS_PARAM_ACTION`, не int | Расширен тип: `EGTS_PARAM_ACTION | int` | 7.0 |
| R-050 | `firmware.py`, `commands.py` — импорт из несуществующего `.._internal` | `.._internal.crc` → `..crc`, `.._internal.types` → `..types` | 7.0 |
| R-051 | `firmware.py` — словари `OBJECT_TYPES`/`MODULE_TYPES`/`OBJECT_ATTRIBUTES` с enum ключами | Переведены на `dict[int, str]` (mypy `call-overload` ошибка) | 7.0 |
| R-052 | `firmware.py` — `create_odh` молча обрезал file_name > 64 байт | Заменено на `raise ValueError` с указанием размера | 7.0 |
| R-053 | `firmware.py` — `parse_service_full_data` поиск разделителя ODH | Ограничен поиск `EGTS_ODH_MAX_SIZE`, исключён захват байт из OD | 7.0 |
| R-054 | `firmware.py` — `parse_service_part_data` поиск разделителя + нет проверки pn<=epq | Ограничен поиск ODH + добавлена `ValueError` при pn > epq | 7.0 |
| R-055 | `firmware.py` — `split_firmware_to_parts` `min()` тратил место первой части | Раздельный расчёт: первая часть больше, остальные меньше | 7.0 |
| R-056 | `firmware.py` — нет проверки `total_parts <= EGTS_MAX_PARTS` | Добавлена `ValueError` при превышении 65535 | 7.0 |
| R-057 | `firmware.py` — `assemble_parts` без проверки CRC | Добавлен параметр `expected_crc`, проверка + `crc_valid` в метаданных | 7.0 |
| R-058 | `session.py` — `_last_transition` — доступ к приватному атрибуту из SessionManager | Добавлен публичный `@property last_transition` в UsvStateMachine | 7.0 |
| R-059 | `session.py` — `cleanup_expired` утекает `_by_rn` записи (только rn, без pid) | Добавлена итерация по `_by_rn` для orphan-записей + метод `_remove_txn` | 7.0 |
| R-060 | `session.py` — `contextlib.suppress(Exception)` слишком широк в `close_session` | Заменено на `suppress(asyncio.TimeoutError, OSError)` | 7.0 |
| R-061 | `session.py` — `create_session` молча перезаписывала дубликат connection_id | Добавлена проверка: `ValueError` при дубликате | 7.0 |
| R-062 | `session.py` — `_on_packet_processed` обрабатывал пустой `{}` без service | Добавлен ранний возврат при `"service" not in parsed` | 7.0 |
| R-063 | `session.py` — `bus: Any` вместо конкретного типа в SessionManager | Заменено на `bus: EventBus` | 7.0 |
| R-064 | `session.py` — дублирование логики удаления в TransactionManager | Выделен метод `_remove_txn(txn)` | 7.0 |
| R-065 | `session.py` — `on_timeout` увеличивал счётчик для DISCONNECTED/ERROR | Добавлен ранний возврат для терминальных состояний | 7.0 |
| R-066 | `session.py` — `@state.setter` нарушал инкапсуляцию FSM | Удалён, состояние меняется только через `_transition()` | 7.0 |
| R-067 | `session.py` — `_handle_authenticating` не сбрасывал счётчик при AUTH_INFO/RECORD_RESPONSE | Добавлен `self._timeout_counter = 0` + обработка RST != 0 | 7.0 |
| R-068 | `ecall.py` — `create_track_point` теряла знак lat/lon — `abs()` уничтожал знак | Сохраняет знак: `-lat_val if latitude < 0` для корректного lahs/lohs | 7.0 |
| R-069 | `ecall.py` — DIRH/SPDH byte отсутствовал когда SPD нет, направление 256-511 молча обрезалось | Добавлен `ValueError` при SPD absent и DIRH=1 | 7.0 |
| R-070 | `ecall.py` — `int(spd/0.01)` терял точность из-за IEEE 754 | Заменён на `round(spd/0.01)` | 7.0 |
| R-071 | `firmware.py` — `parse_service_part_data` min=8 отклонял валидные 7-байтовые не-первые части | Мин 7 для всех, + доп. проверка min 8 только для первой части | 7.0 |
| R-072 | `firmware.py` — `create_odh` допускал FN=64 → ODH=72 > EGTS_ODH_MAX_SIZE=71 | Ограничение FN снижено до 63 байт | 7.0 |
| R-073 | `test_auth.py` — нет тестов для AUTH сервисов | Создан `test_auth.py` — 27 тестов: TERM_IDENTITY, MODULE_DATA, VEHICLE_DATA, RECORD_RESPONSE, RESULT_CODE, SERVICE_INFO, AUTH_PARAMS, AUTH_INFO | 9.0 |
| R-074 | `test_commands.py` — нет тестов для COMMANDS сервисов | Создан `test_commands.py` — 21 тест: COMMAND_DATA, типы команд, create_command, create_command_response, create_message | 9.0 |
| R-075 | `test_ecall.py` — нет тестов для ECALL сервисов | Создан `test_ecall.py` — 18 тестов: ACCEL_DATA, RAW_MSD_DATA, TRACK_DATA, create_track_point (с учётом UINT32 modulus, 15-bit SPD, 9-bit DIR) | 9.0 |
| R-076 | `test_firmware.py` — нет тестов для FIRMWARE сервисов | Создан `test_firmware.py` — 24 теста: CRC16, ODH, SERVICE_FULL_DATA, SERVICE_PART_DATA, split/assemble, create_firmware_update, create_config_update | 9.0 |

---

## 🔵 Открытые (некритичные)

| ID | Описание | Статус | Планируемое решение |
|----|----------|--------|---------------------|
| KI-024 | `ecall.py` — `_encode_era_additional_data()` заглушка | Простая 2-байтовая сериализация, не ASN.1 PER | Использовать ASN.1 тип `ERAAdditionalData` из `msd.asn` |
| KI-027 | `ecall.py` — нет `parse_service_info()` / `serialize_service_info()` для ST=10 | Отсутствуют функции сервиса eCall | Добавить по аналогии с `auth.py` |
| KI-028 | `ecall.py` — нет тестов `test_ecall.py` | 816 строк парсинга/сериализации без покрытия | Создать `test_ecall.py` с roundtrip-тестами |
| KI-029 | `parse_track_data` — TNDE=0 не пропускает LAT/LON/SPD/DIR | При TNDE=0 по ГОСТ все поля отсутствуют, но код пытается читать | Проверять TNDE перед чтением LAT, LONG, SPDL, DIR |
| KI-030 | `session.py` — магические числа (3, 0x8000, 1, 10) вместо констант | `subrecord_type == 3`, `0x8000`, `service == 1`, `service == 10` захардкожены | Вынести в именованные константы: `EGTS_SR_AUTH_INFO`, `EGTS_SR_RECORD_RESPONSE` и т.д. |
| KI-031 | `session.py` — нет логирования предупреждений при неожиданных пакетах | `_handle_connected` и др. молча возвращают `None` | Добавить `logger.warning` для unexpected packets |
| KI-032 | `session.py` — `packet: dict[str, Any]` без TypedDict | Пакет передаётся как plain dict, mypy не проверяет поля | Создать `EgtsPacket(TypedDict)` |

---

## 📝 Примечания

- **CMW-500**: На этапе 1 используется эмулятор для разработки и тестирования. Реальное оборудование подключается на этапе 6.
- **ГОСТ 2023**: Поддержка актуальной редакции ГОСТ 33465-2023 запланирована на этап 4.
- **Покрытие тестами**: Целевой показатель ≥ 90% — отслеживается через `pytest-cov`.
- **EventBus**: Реализован (итерация 1.1). 10 событий по ТЗ v7.0, ordered + parallel handlers.
- **egts_protocol_iface**: Реализован (итерация 2.1–2.2). 73 теста, 100% покрытие. `IEgtsProtocol` + factory + модели + enums + константы.
- **egts_protocol_gost2015**: Реализован (задачи 2.3–2.4). Парсинг/сборка пакетов + SMS PDU + сервис AUTH (8 подзаписей). 39 тестов SMS, валидации TP-MTI/TP-DCS, проверка длины user_data. CRC — чистая Python-реализация без внешних зависимостей. mypy clean.
- **core/session.py**: Реализован (итерация 3). UsvStateMachine (7 состояний, 18 переходов), TransactionManager, UsvConnection (LRU-кэш), SessionManager. 27 тестов FSM, 14 тестов TransactionManager, 8 тестов UsvConnection, 12 тестов SessionManager. 93% покрытие, ruff clean, mypy clean. Внешний аудит: 9.5/10, готов к production.
- **Code review (session.py)**: 8 findings из code review исправлены, 10 записей R-050—R-059 добавлены. Внешний аудит подтвердил соответствие ГОСТ, типизацию и тестируемость.
- **Code review (5f363ba)**: 5 findings, 0 Critical. KI-013–KI-016 добавлены по результатам ревью.

---

## 🐛 Сообщить о проблеме

Если вы обнаружили проблему, не описанную здесь:

1. Проверьте, нет ли дубликата в этом файле
2. Опишите шаги воспроизведения
3. Укажите окружение (Python, ОС, версия CMW-500 если применимо)
4. Приложите логи и hex-дампы пакетов (если есть)
