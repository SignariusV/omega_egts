# Known Issues — OMEGA_EGTS

Известные проблемы, ограничения и плановые задачи.

**Обновлено:** 18.04.2026 | **ТЗ:** v7.0 | **Итерации 1–14:** 1000+ тестов | **Аудит + исправления:** R-001–R-100

---

## 🔴 Критические

_Проект на стадии реализации. Ниже — архитектурные риски и подтверждённые проблемы из независимого аудита (10.04.2026)._

| ID | Описание | Риск | Планируемое решение |
|----|----------|------|---------------------|
| CR-008 | ~~**Сессии не получают protocol EGTS при TCP-подключении**~~ | ~~`tcp_server.py:_handle_connection()` вызывает `create_session()` без `protocol`~~ | **Решено (R-080)**: `SessionManager.create_session()` автоматически создаёт `protocol` через `create_protocol(self.gost_version)` если `protocol is None`. См. также KI-039 |
| CR-009 | ~~**Отсутствует AutoResponseMiddleware**~~ | ~~Нет middleware, формирующего `ctx.response_data` для корректных пакетов.~~ | **Решено (R-076)**: `AutoResponseMiddleware` добавлен в pipeline (order=3). Формирует RESPONSE для успешных пакетов, кеширует через `conn.add_pid_response()`. 12 тестов, 96% coverage pipeline.py |
| CR-010 | ~~**FSM не инициализируется при TCP-подключении**~~ | ~~`conn.fsm.on_connect()` не вызывается~~ | **Решено (R-081)**: `TcpServerManager._handle_connection()` вызывает `conn.fsm.on_connect()` после создания сессии |
| CR-011 | ~~**FSM не получает on_disconnect при разрыве**~~ | ~~`tcp_server.py:_on_disconnect()` удаляет сессию без `on_disconnect()`~~ | **Решено (R-082)**: `TcpServerManager._on_disconnect()` вызывает `conn.fsm.on_disconnect()` перед удалением сессии |
| CR-012 | ~~**FSM не обрабатывает RESPONSE-пакеты (RESULT_CODE)**~~ | ~~RESPONSE-пакеты не имеют `service` → FSM игнорирует~~ | **Решено (R-083)**: FSM теперь получает `result_code` через `on_result_code_sent()` из SessionManager при обработке RECORD_RESPONSE |
| CR-013 | **Дублирующее создание SMS-сессии** | `PacketDispatcher._ensure_sms_session()` и `CommandDispatcher._ensure_sms_session_for_txn()` создают сессию независимо → potential race condition при одновременном вызове. Протокол создаётся в двух местах через `create_egts_protocol("2015")`. | Вынести создание SMS-сессии в единую фабрику или передавать единый экземпляр протокола из `SessionManager` |
| ~~CR-014~~ | ~~**Неверный порядок middleware в `_build_pipeline()`**~~ | ~~AutoResponse(order=3) перед Dedup(order=4) → дубликаты~~ | **Решено (R-084)**: Порядок исправлен: CRC(1) → Parse(2) → Dedup(2.5) → AutoResponse(3) → EventEmit(5). Dedup проверяет кэш ДО того как AutoResponse его заполнит. Первый пакет больше не определяется как дубликат. |
| ~~CR-015~~ | ~~**Формат сценариев без версионирования**~~ | ~~Если захардкодить парсинг v1 в ScenarioManager — добавление v2 потребует переписывания монолитного кода~~ | ~~Решено в итерации 7.0: `IScenarioParser` (Protocol) + `ScenarioParserFactory` + `ScenarioParserRegistry`. Добавление новой версии = новый класс + `registry.register("2", V2) — без изменений в `ScenarioManager`~~ |
| CR-016 | ~~**`ParseResult.extra` пуст после `parse_packet()`**~~ | ~~`protocol.parse_packet()` не заполнял `extra: dict`. `ExpectStep._matches()` ищет `service`, `subrecord_type` именно в `extra` → сценарии зависали на шагах `expect`.~~ | **Решено**: `adapter.parse_packet()` заполняет `extra` из `packet.records[0]` (service, subrecord_type). 6 новых тестов. См. ISSUE-002 |
| CR-017 | ~~**FSM не переходит AUTHENTICATING → AUTHORIZED**~~ | ~~После успешной авторизации (RESULT_CODE отправлен) FSM остаётся в `authenticating`. Интеграционный тест FAIL: `assert "authorized" in states_lower`.~~ | **Решено**: 1) `CommandDispatcher._send_tcp()` извлекает pid/rn из packet_bytes если не переданы → регистрирует транзакцию. 2) `UsvStateMachine._handle_authenticating()` при RECORD_RESPONSE с CRN вызывает `on_result_code_sent(0)` → FSM переходит в AUTHORIZED. См. ISSUE-004 |
| CR-007 | **SMS-отправка делегируется CMW-500** | ТЗ предполагает PDU-упаковку на нашей стороне (`build_sms_pdu`/`parse_sms_pdu`). Решение: CMW-500 сам кодирует/декодирует PDU, мы передаём только сырые EGTS-байты. Это упрощает код, но создаёт зависимость от поведения прибора. | Задокументировано (09.04.2026). Если потребуется своя PDU-упаковка — см. `egts_protocol_gost2015/gost2015_impl/sms.py` |
| CR-006 | **Структура `libs/` отличается от ТЗ** | ТЗ (раздел 2.4) определяет `egts_protocol/base.py, v2015.py, v2023.py, sms.py`. Реализовано: `egts_protocol_iface/` + `egts_protocol_gost2015/gost2015_impl/`. Обоснование — dependency inversion: ядро зависит только от интерфейса. См. CHANGELOG.md | Задокументировано. Если потребуется строго по ТЗ — рефакторинг за 1–2 часа |
| CR-001 | Circular dependency: `PacketDispatcher` ↔ `SessionManager` | При реализации может возникнуть циклический импорт | Передача ссылок через конструктор, не через `import` |
| CR-002 | ~~Порядок логов при parallel-обработке EventBus~~ | Решено (R-077): LogManager сортирует записи по timestamp при flush() | — |
| CR-003 | Голосовой канал eCall — механизм не расписан в ТЗ | Сценарий №5 не будет полным без проверки тонового модема | Этап 6: интеграция с реальным CMW-500 |
| CR-004 | ~~`crcmod` — внешняя зависимость для CRC~~ | Решено: чистая Python-реализация в `crc.py` | — |
| CR-005 | Параллельные агенты перезаписывают `adapter.py` | Задачи 2.3 и 2.4 редактируют один файл — SMS-методы затираются | Координировать изменения; после завершения 2.3 зафиксировать SMS |

---

## 🟡 Известные ограничения

| ID | Описание | Статус | Планируемое решение |
|----|----------|--------|---------------------|
| ~~KI-060~~ | ~~**Некорректная реализация read_sms в Cmw500Controller**~~ | ~~Открыто~~ | **Решено**: `read_sms()` теперь возвращает `bytes | None` через `bytes.fromhex(hex_data)` (cmw500.py:488-490). |

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
| ~~KI-013~~ | ~~Дублирование `crc.py` — `_internal/crc.py` и `gost2015/crc.py` идентичны~~ | ~~Не применимо~~ | **Удалено**: Единый `libs/egts/_core/crc.py`, импортируется из `protocol.py`, `builder.py`, `parser.py`. |
| KI-014 | O(n²) конкатенация байтов в `to_bytes` (`packet.py`, `record.py`, `subrecord.py`) | `ppu_data += record.to_bytes()` в цикле создаёт новый объект на каждой итерации | Заменить на `b"".join([...])` или `bytearray` |
| ~~KI-015~~ | ~~`SMSReassembler` — неограниченный рост памяти~~ | ~~Не применимо~~ | **Удалено**: `SMSReassembler` не существует в текущей кодовой базе (net-to-be-determined). |
| KI-016 | ASN.1 eCall — отсутствует файл `msd.asn` | `create_msd_data()` и `decode_msd_data()` бросают `RuntimeError`; ASN.1-кодирование MSD не работает | Скопировать `msd.asn` из EGTS_GUI или задокументировать ограничение |
| ~~KI-019~~ | ~~`SMSReassembler` — нет TTL-очистки по времени~~ | ~~Не применимо~~ | **Удалено**: `SMSReassembler` не существует в текущей кодовой базе. |
| KI-020 | `parse_service_info` — нет валидации SST | SST принимает любые 0–255, по ГОСТ допустимы: 0, 128, 129, 130, 131 | Добавить проверку или enum `SERVICE_STATES` из `types.py` |
| KI-021 | `serialize_service_info` — смешение форматов в списке | Поддерживает int и dict в одном списке без проверки | Унифицировать формат или добавить валидацию |
| ~~KI-022~~ | ~~Нет тестов `auth.py`~~ | ~~Не применимо~~ | **Удалено**: Интеграционные тесты существуют (`tests/integration/test_auth_scenario.py`, `tests/core/test_fsm.py` с AUTH). |
| KI-037 | **PID=0 в RESPONSE при ошибке CRC-16** | При ошибке CRC-16 тела заголовок корректен и PID можно извлечь из `raw[4:6]` (little-endian). Сейчас используется `pid=0` → УСВ может не сопоставить RESPONSE с запросом. | При CRC-16 ошибке извлекать PID из заголовка: `struct.unpack('<H', raw[4:6])[0]`. При CRC-8 ошибке оставить `pid=0` (заголовок повреждён) |
| ~~KI-038~~ | ~~**Config не используется в компонентах**~~ | ~~Открыто~~ | **Решено**: `CoreEngine.start()` теперь извлекает значения из `self.config`: `tcp_host`, `tcp_port`, `gost_version`, `logging.dir` (engine.py:114-119, 87). |
| KI-039 | **Повторное создание SMS-сессии в двух местах** | Открыто | Дублирует CR-013. `PacketDispatcher._ensure_sms_session()` и `CommandDispatcher._ensure_sms_session_for_txn()` создают сессию независимо. |
| KI-040 | **Повторяющийся код получения connection/protocol в pipeline** | `CrcValidationMiddleware` и `ParseMiddleware` дублируют паттерн: `conn = self._session_mgr.get_session(ctx.connection_id)` → проверка `conn is None` → `protocol = conn.protocol` → проверка `protocol is None`. | Добавить метод `get_protocol(connection_id)` в `SessionManager` или вынести в общую утилиту |

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
| R-077 | CR-002: Порядок логов при parallel-обработке | Добавлен `LogManager` — буферизация + сортировка по timestamp при flush(), JSONL-файлы по дате. 23 теста, 93% coverage | 9.0 |
| R-078 | CR-007: Windows-защита `attrib +h` мешает записи | `save()` вызывает PermissionError после `attrib +h`. Исправлено: только лог ACL warning на Windows, chmod 600 на Unix. `save()` использует `creds.device_id` как ключ (устранение рассинхронизации). 25 тестов, 94% coverage | 9.0 |
| R-079 | CR-015: Формат сценариев без версионирования | `IScenarioParser` (Protocol) + `ScenarioParserV1` + `ScenarioParserRegistry` + `ScenarioParserFactory`. `ScenarioManager` работает только через factory, не знает о версиях. Добавление V2 = новый класс + `registry.register("2", V2)`. Валидация сценария до выполнения | 7.0 |
| R-080 | CR-008: Сессии не получают protocol EGTS | `SessionManager.create_session()` автоматически создаёт protocol через `create_protocol(self.gost_version)` если protocol не передан | 5.1 |
| R-081 | CR-010: FSM не инициализируется при TCP-подключении | `TcpServerManager._handle_connection()` вызывает `conn.fsm.on_connect()` после создания сессии | 5.1 |
| R-082 | CR-011: FSM не получает on_disconnect при разрыве | `TcpServerManager._on_disconnect()` вызывает `conn.fsm.on_disconnect()` перед удалением сессии | 5.1 |
| R-083 | CR-012: FSM не обрабатывает RESPONSE-пакеты | FSM получает `result_code` через `on_result_code_sent()` из SessionManager при обработке RECORD_RESPONSE | 5.1 |
| R-084 | CR-014: Неверный порядок middleware | Порядок исправлен: CRC(1) → Parse(2) → Dedup(2.5) → AutoResponse(3) → EventEmit(5). Dedup проверяет кэш ДО AutoResponse | 10.0 |
| R-085 | `connection_id: null` в логах FSM | `SessionManager._on_packet_processed()` теперь включает `connection_id` в событие `connection.changed` | 10.0 |
| R-086 | RESPONSE не логируется | `LogManager._on_packet_processed()` записывает `response_hex` из `ctx.response_data` | 10.0 |
| R-087 | Ложное определение дубликатов — первый пакет помечался как duplicate | Dedup перемещён на order=2.5 (перед AutoResponse). Первый пакет теперь `is_duplicate=false` | 10.0 |
| R-088 | RESPONSE без RECORD_RESPONSE (16 байт вместо 29) | Добавлена `ResponseRecord` модель, расширен `build_response()` параметром `records`. `AutoResponseMiddleware` формирует RECORD_RESPONSE для входящих записей. RESPONSE: 29 байт, RN, SST, SRT=0, CRN, RST=0, RSOD=1. 5 новых тестов, интеграционный тест обновлён | RECORD_RESPONSE |
| R-089 | CR-016: `ParseResult.extra` пуст после `parse_packet()` | `adapter.parse_packet()` заполняет `extra` из `packet.records[0]` (service, subrecord_type). +2 теста в `test_adapter.py`, переписан `test_cr016_parse_result_extra_empty.py` (4 теста PASS). | 11.0 |
| R-090 | `Record.from_bytes()` не парсит subrecords — `subrecords=[]` | Добавлен вызов `parse_subrecords()` в `Record.from_bytes()`. Все записи теперь имеют заполненные subrecords. +2 теста. | 12.0 |
| R-091 | `Subrecord.subrecord_type` — int, не `"EGTS_SR_TERM_IDENTITY"` | `_map_subrecord_to_iface()` конвертирует `int` → `"EGTS_SR_TERM_IDENTITY"` через `SubrecordType(srt).name`. ExpectStep теперь матчит по строке. | 12.0 |
| R-092 | `SendStep` не передаёт `connection_id` в `command.send` | Добавлен `emit_data["connection_id"] = conn_id` в `SendStep.execute()`. CommandDispatcher теперь получает connection_id для TCP. | 12.0 |
| R-093 | `extra` не содержит `rst_service_type` | Добавлен `extra["rst"] = rec.rst_service_type` в `adapter.parse_packet()`. **Обнаружена путаница**: `rst_service_type` (сервис-получатель) ≠ RECORD_RESPONSE.RST (статус обработки). Требуется `extra["record_status"]` из парсинга SRD подзаписи. | 12.0 |
| R-094 | CR-017: FSM не переходит AUTHENTICATING → AUTHORIZED | `CommandDispatcher._send_tcp()` извлекает pid/rn из packet_bytes если не переданы → `transaction_mgr.register()`. `UsvStateMachine._handle_authenticating()` при RECORD_RESPONSE с CRN вызывает `on_result_code_sent(0)` → AUTHORIZED. Интеграционный тест PASS. 18 новых тестов. | 13.0 |
| R-095 | `SubrecordType` сравнение int vs str в FSM | `UsvStateMachine._handle_authenticating()` сравнивает `subrecord_type` с `0x8000` (int) и `"EGTS_SR_RECORD_RESPONSE"` (str) — адаптер конвертирует enum в строку. Поддержка обоих форматов для обратной совместимости. | 13.0 |
| R-096 | Poll loop не перезапускался после `stop_poll()` | `stop_poll()` теперь очищает `_poll_task = None`, `start_poll()` проверяет `done()` перед созданием нового task. SMS-опрос корректно перезапускается после переконфигурации | 14.0 |
| R-097 | Class-level атрибуты кэша — shared state между инстансами | `_last_cs_state`, `_last_ps_state` и др. перенесены из class-level в `__init__` как instance attributes. Больше нет cross-test pollution | 14.0 |

---

## 🔵 Открытые (некритичные)

### По итогам code review engine.py (итерация 9.0, 10.04.2026)

| ID | Описание | Статус | Планируемое решение |
|----|----------|--------|---------------------|
| ~~KI-041~~ | ~~`LogManager.stop()` не вызывается в `_cleanup()`~~ | ~~Открыто~~ | **Решено**: `_cleanup()` теперь вызывает `await self.log_mgr.stop()` (engine.py:197-199). |
| KI-042 | `get_status()` — проверка `is not None` вместо реального состояния компонентов | Открыто | Использовать `self.tcp_server.is_running` и `self.cmw500._connected` вместо `is not None` |
| KI-043 | `replay()` — параметр `scenario_path` не используется | Открыто | Либо реализовать валидацию через сценарий, либо удалить параметр. Сейчас docstring честно предупреждает «пока игнорируется» |
| KI-044 | `replay()` — без pipeline (CRC, Parse, Dedup) | Открыто | Передать `pipeline=self.packet_dispatcher.pipeline` в `ReplaySource` при необходимости полной валидации. Сейчас — «быстрый режим», только эмит событий |
| KI-045 | Несоответствие обработки ошибок между CLI-методами | Открыто | `run_scenario`/`cmw_status` возвращают error-dict, `get_log_stats` — silently zeros, `replay`/`export` — raise. Унифицировать: либо все raise, либо все error-dict |
| KI-046 | `get_status()` — нет кэширования CMW-статуса | Открыто | При частом вызове в REPL каждая команда `status` делает SCPI-запрос (сетевой I/O + retry). Добавить TTL-кэш (2–5 с) |
| KI-047 | `ScenarioManager.execute()` не эмитит `scenario.step` в EventBus | Открыто | Добавить `await bus.emit("scenario.step", ...)` в `ScenarioManager.execute()` — иначе LogManager не логирует шаги сценариев |
| KI-048 | `get_status()` — redundant `and self.is_running` | Открыто | `_cleanup()` всегда ставит `cmw500 = None` до изменения `_started`. Проверка `cmw500 is not None` достаточна |
| KI-049 | `export()` — нет проверки существования директории логов | Открыто | Если `log_dir` не существует, `export_csv`/`export_json` создают пустой файл без явной ошибки. Добавить проверку и предупреждение |
| KI-050 | Относительный `log_dir` — риск при смене cwd | Открыто | `config.logging.dir` по умолчанию `"logs"` (относительный). Резолвить в абсолютный путь при создании `LogManager` |

### По итогам review commit 485728d..HEAD (14.04.2026)

| ID | Описание | Статус | Планируемое решение |
|----|----------|--------|---------------------|
| KI-051 | **FSM transition без проверки RESULT_CODE** (`session.py:338-341`) | Открыто | При любом CRN вызывается `on_result_code_sent(0)`. FSM может перейти в AUTHORIZED после подтверждения любого record, не только RESULT_CODE. Требуется трекинг `_expecting_result_code_response` и проверка совпадения CRN |
| KI-052 | **Transaction registration ПОСЛЕ отправки** (`dispatcher.py:436-444`) | Открыто | `writer.write()` + `drain()` происходит ДО регистрации транзакции. Если connection drop во время drain — transaction теряется. Переместить `transaction_mgr.register()` перед `writer.write()` |
| KI-053 | **ResponseRecord rn vs CRN путаница** (`pipeline.py:371-380`) | Открыто | `ResponseRecord(rn=rec.record_id)` — rn используется и как RN record'а, и как CRN в subrecord data. Нужна верификация против adapter.py, что сериализация корректна |
| KI-054 | **Unbounded buffer в LogManager** (`logger.py:103-117`) | Открыто | `_auto_flush_loop` flush раз в интервал, но буфер растёт быстрее при высокой нагрузке. Использовать `while` loop для полной очистки буфера |
| KI-055 | **Duplicate subscriber leak** (`event_bus.py:58-60`) | Открыто | `on()` не проверяет дубликаты — handler может быть добавлен дважды. Добавить `if handler not in handler_list: handler_list.append(handler)` |
| KI-056 | **No TCP framing для EGTS** (`tcp_server.py:157-164`) | Открыто | `reader.read(65536)` читает до 64KB, но EGTS packets могут быть fragmented или concatenated. Реализовать framing layer — accumulate + split по EGTS boundaries (PK, HL) |
| KI-057 | **Mixed int/str comparison для subrecord_type** (`session.py:327`) | Открыто | `subrecord_type == 0x8000 or subrecord_type == "EGTS_SR_RECORD_RESPONSE"` — один из ветвей dead code. Нормализовать к одному типу |
| KI-058 | **Mypy type errors (67 errors)** | Открыто | VISA объекты типизированы как `object`, нет narrowing. Добавить type stubs для RsCmwGsmSig или использовать `# type: ignore` с комментариями. `cmw500.py` (58), `adapter.py` (3), `dispatcher.py` (1), `engine.py` (1), `cli/app.py` (1) |
| KI-033 | ProtocolDetectionMiddleware — определение версии из PRV при первом пакете | Отложено | Добавить в пайплайн первым middleware: чтение `raw[0]`, `conn.protocol = create_protocol(version)`. См. NOTES.md |
| KI-024 | `ecall.py` — `_encode_era_additional_data()` заглушка | Простая 2-байтовая сериализация, не ASN.1 PER | Использовать ASN.1 тип `ERAAdditionalData` из `msd.asn` |
| KI-027 | `ecall.py` — нет `parse_service_info()` / `serialize_service_info()` для ST=10 | Отсутствуют функции сервиса eCall | Добавить по аналогии с `auth.py` |
| KI-028 | `ecall.py` — нет тестов `test_ecall.py` | 816 строк парсинга/сериализации без покрытия | Создать `test_ecall.py` с roundtrip-тестами |
| KI-029 | `parse_track_data` — TNDE=0 не пропускает LAT/LON/SPD/DIR | При TNDE=0 по ГОСТ все поля отсутствуют, но код пытается читать | Проверять TNDE перед чтением LAT, LONG, SPDL, DIR |
| KI-030 | `session.py` — магические числа (3, 0x8000, 1, 10) вместо констант | `subrecord_type == 3`, `0x8000`, `service == 1`, `service == 10` захардкожены | Вынести в именованные константы: `EGTS_SR_AUTH_INFO`, `EGTS_SR_RECORD_RESPONSE` и т.д. |
| KI-031 | `session.py` — нет логирования предупреждений при неожиданных пакетах | `_handle_connected` и др. молча возвращают `None` | Добавить `logger.warning` для unexpected packets |
| KI-032 | `session.py` — `packet: dict[str, Any]` без TypedDict | Пакет передаётся как plain dict, mypy не проверяет поля | Создать `EgtsPacket(TypedDict)` |
| KI-034 | `TcpServerManager` — `action: "connected"` вместо `"new_connection"` | Формальное несоответствие ТЗ (раздел 3.1) | Заменить при интеграции |
| KI-035 | `TcpServerManager` — нет `state: "ERROR"` при ошибке чтения | Сейчас только break, ТЗ требует emit с ERROR | Добавить в _read_loop except блок |
| KI-036 | `TcpServerManager` — нет framing (header→length→body) | `read(65536)` читает произвольный блок, EGTS-пакет может быть разбит | Добавить `_read_full_packet()` при интеграции с PacketDispatcher |

---

## ✅ Решено в итерации 5

| ID | Описание | Решение |
|----|----------|---------|
| R-085 | `Cmw500Emulator.send_sms()` минуется очередь команд | Перенесено в `_handle_send_sms()` → `_send_scpi()`, теперь идёт через worker_queue |
| R-086 | `_incoming_sms_queue.task_done()` без `join()` | Убран из эмулятора — `task_done()` не нужен без `join()` |
| R-087 | Fire-and-forget `create_task()` при закрытом event loop | Обёрнуто в `try/except RuntimeError` в `_on_worker_done` и `_on_poll_done` |
| R-088 | Async handler кладёт coroutine object в очередь вместо bytes | Исправлено: `handler_result = await handler_result` сохраняет результат |
| R-089 | PacketDispatcher без тестов | 24 теста, 95% coverage |
| R-090 | CommandDispatcher без тестов | 23 теста, 95% coverage (совместно с PacketDispatcher) |
| R-091 | `SessionManager._on_packet_processed` — ParseResult → `parsed = {}`, FSM теряет `service` | Исправлено: извлечение `service_type` из `packet.records[0]` и данных из `subrecords[].data` |
| R-092 | `CommandDispatcher._send_sms` — SMS-транзакция не регистрировалась без существующей сессии | Добавлен `_ensure_sms_session_for_txn()` — создаёт сессию при необходимости |
| R-093 | `Cmw500Controller.execute()` — future мог зависнуть при отключении worker | `asyncio.get_event_loop()` заменён на `get_running_loop()`; таймаут через `wait_for` отложен (конфликт с тестами retry) |
| R-094 | `TcpServerManager.stop()` — race condition: задачи отменялись до закрытия сервера | Исправлено: snapshot задач `list(self._tasks)` + порядок cancel→gather→close→wait_closed |
| R-095 | `asyncio.get_event_loop()` — deprecated в Python 3.12+ | Заменено на `asyncio.get_running_loop()` в `_on_worker_done` и `_on_poll_done` |
| R-096 | `_execute_with_retry` — `retry_count=0` вызывал `TypeError: raise None` | Добавлена проверка `if last_error is not None` |
| R-097 | Дублирование логики `is_closing` в dispatcher.py | Вынесено в утилиту `_is_writer_closing(writer)` |
| R-098 | Lazy import `create_protocol` внутри методов dispatcher | Перенесён на верхний уровень модуля |
| R-099 | `_default_protocol` в тестах — мёртвый код | Удалено — SessionManager создаёт protocol из `gost_version` |
| R-100 | `test_start_emits_server_started` — не проверял событие | Теперь подписывается на `server.started` и верифицирует порт |

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
- **core/cmw500.py**: Реализован (итерация 5.2–5.3). Cmw500Controller (очередь команд, retry, SMS, poll loop) + Cmw500Emulator (TCP/SMS задержки, handler). 58 тестов, 91% coverage. Внешний аудит: 4 проблемы исправлены.
- **core/tcp_server.py**: Реализован (итерация 5.1). asyncio TCP-сервер, приём подключений, чтение пакетов. 15 тестов, 97% coverage.
- **core/dispatcher.py**: Реализован (итерация 5.4–5.5). PacketDispatcher + CommandDispatcher, TCP и SMS каналы, транзакции. 47 тестов, 95% coverage.
- **ГОСТ Compliance (итерация 5)**: Все таймауты соответствуют ТЗ, логирование 100% пакетов, EventBus-архитектура без прямых вызовов. 1 замечание: RESPONSE для SMS не отправляется обратно (управляется CMW-500).

---

## 🐛 Сообщить о проблеме

Если вы обнаружили проблему, не описанную здесь:

1. Проверьте, нет ли дубликата в этом файле
2. Опишите шаги воспроизведения
3. Укажите окружение (Python, ОС, версия CMW-500 если применимо)
4. Приложите логи и hex-дампы пакетов (если есть)
