# Changelog — OMEGA_EGTS

Все значимые изменения проекта. Формат: [Keep a Changelog](https://keepachangelog.com/), версионирование: [SemVer](https://semver.org/).

---

## [Unreleased]

### Итерация 6: LogManager и Credentials (10.04.2026)

**Ветка:** `iteration-6/logging-credentials` | **Задач выполнено:** 2/2 | **Тестов:** 48 | **Покрытие:** 93–94%

#### Добавлено (6.1 — LogManager)
- **LogManager** — подписчик на 3 события EventBus: `packet.processed`, `connection.changed`, `scenario.step`
- **Буферизация + сортировка по timestamp** — решает CR-002 (нарушение порядка логов при parallel-обработке)
- **JSONL-файлы** — одна записи на строку, именование по дате `YYYY-MM-DD.jsonl`
- **Логирование пакетов** — hex + parsed данные + crc_valid + is_duplicate + terminated + errors
- **flush()** — сброс буфера на диск, сортировка, очистка буфера

#### Добавлено (6.2 — CredentialsRepository)
- **Credentials** — dataclass (imei, imsi, term_code, auth_key, device_id, description) с to_dict()/from_dict()
- **CredentialsRepository** — JSON-хранилище: find_by_imei(), get(), save(), list_all()
- **save()** использует creds.device_id как ключ (fallback на IMEI) — устранена рассинхронизация
- **Защита файла**: chmod 600 (Unix), документированное ограничение ACL (Windows)
- **Устойчивость** к отсутствию/битому JSON-файлу, некорректным записям
- **25 тестов**, 94% покрытие credentials.py, ruff + mypy clean

#### Исправлено (внешний аудит credentials.py)
- Убран избыточный параметр `device_id` из `save()` — ключ теперь берётся из `creds.device_id`
- Windows-защита: `attrib +h` не вызывается (мешает записи), ограничение ACL документировано
- Логи предупреждений переведены на английский для единообразия

### Итерация 5: Network и CMW-500 (09.04.2026)

**Ветка:** `iteration-5/network-cmw` | **Задач выполнено:** 6/6 | **Тестов:** 132 | **Покрытие:** 91–97%

#### Добавлено
- **AutoResponseMiddleware** — формирует RESPONSE (`build_response(pid, result_code=0)`) для успешно обработанных пакетов, кеширует через `conn.add_pid_response()` для обработки дубликатов (12 тестов)
- **PacketDispatcher._build_pipeline()** — автоматическое создание pipeline со всеми middleware: CRC → Parse → AutoResponse → Dedup → EventEmit. PacketDispatcher теперь создаёт pipeline по умолчанию если не передан явно
- **Исправление CR-008** — `SessionManager.create_session()` автоматически создаёт `protocol` через `create_protocol(self.gost_version)` если protocol не передан
- **Исправление CR-010** — `TcpServerManager._handle_connection()` вызывает `conn.fsm.on_connect()` после создания сессии
- **Исправление CR-011** — `TcpServerManager._on_disconnect()` вызывает `conn.fsm.on_disconnect()` перед удалением сессии

#### Исправлено (внешний аудит)
- **TcpServerManager** — asyncio TCP-сервер, приём подключений, чтение пакетов, emit `raw.packet.received` и `connection.changed` (15 тестов, 97%)
- **Cmw500Controller** — асинхронная очередь команд, retry с экспоненциальной задержкой, SMS send/read, фоновый poll входящих SMS (39 тестов, 91%)
- **Cmw500Emulator** — эмулятор CMW-500 с настраиваемыми задержками TCP (0.1–2с) и SMS (3–30с), handler для генерации ответов УСВ (19 тестов)
- **PacketDispatcher** — координатор pipeline, обработка TCP и SMS пакетов, создание SMS-сессий, отправка RESPONSE (24 теста, 95%)
- **CommandDispatcher** — отправка команд через TCP и SMS, регистрация транзакций, обработка ошибок (23 теста, 95%)

#### Исправлено (внешний аудит)
- `send_sms()` эмулятора больше не минует очередь команд — теперь проходит через `_send_scpi()` → `_handle_send_sms()`
- `task_done()` без `join()` удалён из `_send_scpi()` эмулятора
- Fire-and-forget `create_task()` обёрнут в `try/except RuntimeError` для защиты при закрытом event loop
- Async handler: `handler_result = await handler_result` — теперь результат await сохраняется, а не coroutine object

#### Качество кода
- ruff: 0 ошибок
- mypy: 0 ошибок
- Все 120 тестов итерации 5 проходят

### Этап 1: CLI MVP (в разработке)
- [x] EventBus — async шина с ordered/parallel handlers (итерация 1.1)
- [x] Config — nested dataclass'ы, JSON загрузка, CLI merge, валидация (итерация 1.2)
- [x] CoreEngine — координатор компонентов (итерация 1.3)
- [x] FSM авторизации — UsvStateMachine (7 сост., 18 переходов), TransactionManager, UsvConnection, SessionManager (итерация 3)
- [x] PacketPipeline — middleware-конвейер обработки пакетов (итерация 4)
- [x] asyncio TCP-сервер для приёма EGTS-пакетов (итерация 5.1)
- [x] Cmw500Controller — очередь команд, retry, SMS (итерация 5.2)
- [x] Cmw500Emulator — эмулятор CMW-500, TCP/SMS задержки (итерация 5.3)
- [x] PacketDispatcher — координатор pipeline, TCP + SMS (итерация 5.4)
- [x] CommandDispatcher — отправка команд TCP/SMS, транзакции (итерация 5.5)
- [ ] Поддержка ГОСТ 33465-2015 (транспортный уровень — парсинг/валидация)
- [ ] CLI (REPL на cmd)
- [ ] Базовое логирование пакетов (hex + parsed)
- [ ] pytest, покрытие ≥ 90%

### Этап 2: Библиотека EGTS (в разработке)

> **⚠️ Отклонение от ТЗ (раздел 2.4):** ТЗ определяет структуру `libs/egts_protocol/` с файлами `base.py`, `v2015.py`, `v2023.py`, `sms.py`. Реализована **другая структура** — два пакета: `egts_protocol_iface/` (абстрактный интерфейс, dependency inversion) и `egts_protocol_gost2015/` (реализация с внутренней папкой `gost2015_impl/`). Обоснование: ядро зависит только от интерфейса, не от конкретной реализации. Это упрощает добавление ГОСТ 2023 и тестирование.

- [x] egts_protocol_iface — IEgtsProtocol (Protocol), create_protocol factory (итерация 2.1–2.2)
- [x] Модели: Packet, Record, Subrecord, ParseResult (dataclass-контракты с extra, parse_error, crc_valid)
- [x] Enums: PacketType, ServiceType, SubrecordType, RecordStatus, ResultCode + константы
- [x] Методы сборки: pr_flags(), rf_flags() для флагов PR/RF
- [x] Заглушка egts_protocol_gost2015/adapter.py (EgtsProtocol2015)
- [x] EgtsProtocol2015 — парсинг/сборка пакетов (итерация 2.3)
  - Полная реализация parse_packet, build_response, build_record_response, build_packet
  - Чистая реализация CRC-8/CRC-16 на Python (без crcmod)
  - Маппинг между internal-моделями (EGTS_GUI) и iface-моделями
  - 27 новых тестов адаптера
- [ ] SMS PDU — полная интеграция в адаптере (итерация 2.4, параллельный агент)
- [ ] Реэкспорт crc.py из _internal (устранение дублирования KI-013)
- [ ] Оптимизация to_bytes: b"".join вместо += (KI-014)

### Этап 3: Сценарии (планируется)
- [ ] Все 10 сценариев (авторизация, телеметрия, траектория, ускорение, eCall, обновление ПО, команды, тестирование, SMS, пассивный режим)
- [ ] Загрузка/генерация HEX-файлов
- [ ] Export (CSV/JSON/DER)
- [ ] CredentialsRepository (JSON-хранилище)

### Этап 4: ГОСТ 2023 (планируется)
- [ ] Поддержка ГОСТ 33465-2023

### Этап 5: GUI (планируется)
- [ ] Графический интерфейс оператора (PyQt6/PySide6)

### Этап 6: Реальное CMW-500 (планируется)
- [ ] Интеграция с реальным оборудованием CMW-500 (PyVISA/SCPI)

---

## [Unreleased] — Архитектурные решения

### SMS-канал: делегирование PDU-кодирования CMW-500 (09.04.2026)

**Проблема:** ТЗ предполагает PDU-упаковку на нашей стороне (`build_sms_pdu`/`parse_sms_pdu` в протокольной библиотеке).

**Решение:** CMW-500 сам кодирует/декодирует SMS PDU. Мы передаём только сырые EGTS-байты:
- `send_sms(egts_bytes)` — CMW-500 упаковывает в PDU и шлёт подключённому УСВ
- `read_sms()` — CMW-500 возвращает сырые EGTS-байты из принятой SMS
- Номер получателя не нужен — CMW-500 знает, какое УСВ подключено

**Последствия:**
- `CommandDispatcher` единый для TCP и SMS — проверка `channel`, два способа отправки
- Сценарии указывают только `channel: "sms"` (никакого `recipient`)
- `Cmw500Controller` добавляет методы `send_sms()` и `read_sms()`
- SMS-задержки: 3–30 с отправка, опрос `read_sms()` каждую 1–5 с
- Таймаут транзакции SMS: 30–60 с (vs 5–10 с TCP)

**Документация:** PLAN.md Задача 5.2, 5.5 | KNOWN_ISSUES.md CR-007

---

## [Unreleased]

### Итерация 3: Session Management и FSM (08.04.2026)

#### Добавлено
- `core/session.py` — единый модуль с 4 компонентами:
  - **UsvStateMachine** — FSM с 7 состояниями и 18 переходами по ГОСТ 33465-2015
  - **TransactionManager** — отслеживание PID↔RPID, RN↔CRN с `_remove_txn` helper
  - **UsvConnection** — данные подключения с LRU-кэшем дубликатов (OrderedDict, MAX_SEEN_PIDS=65536)
  - **SessionManager** — координатор с async `close_session()`, подпиской на `packet.processed` (ordered=True)
- `tests/core/test_fsm.py` — 27 тестов: все 18 переходов, таймауты, std USV, сброс счётчика, терминальные состояния
- `tests/core/test_transaction.py` — 14 тестов: PID/RN, cleanup, orphan RN, duplicate detection, `_remove_txn`
- `tests/core/test_connection.py` — 8 тестов: LRU eviction, usv_id, TTL
- `tests/core/test_session_manager.py` — 12 тестов: создание, async close_session, duplicate check, FSM update, emit

#### Исправлено (code review)
- R-050: `_last_transition` → публичный `@property last_transition`
- R-051: `cleanup_expired` утечка `_by_rn` → итерация по оболям словарям
- R-052: `suppress(Exception)` → `suppress(TimeoutError, OSError)`
- R-053: `create_session` дубликат → `ValueError`
- R-054: `_on_packet_processed` пустой `{}` → ранний возврат при отсутствии service
- R-055: `bus: Any` → `bus: EventBus`
- R-056: Дублирование удаления → `_remove_txn(txn)` helper
- R-057: `on_timeout` для DISCONNECTED/ERROR → ранний возврат
- R-058: `@state.setter` нарушал инкапсуляцию → удалён
- R-059: `_handle_authenticating` не сбрасывал счётчик → добавлен сброс + обработка RST != 0

#### Изменено
- `pyproject.toml` — добавлен `SIM105` в ruff ignore (false positive для async)
- `KNOWN_ISSUES.md` — добавлены KI-030–KI-032 (опциональные улучшения)

#### Метрики
- 61 тест в итерации 3
- 93% покрытие session.py
- ruff clean, mypy clean
- Внешний аудит: 9.5/10

---

### Итерация 4: Packet Processing Pipeline (09.04.2026)

#### Добавлено
- `core/pipeline.py` — PacketPipeline + PacketContext + 4 middleware:
  - **CrcValidationMiddleware** — валидация CRC-8/CRC-16, RESPONSE с кодами ошибок
  - **ParseMiddleware** — парсинг через protocol, ParseResult с extra-полями (service, tid, imei, imsi)
  - **DuplicateDetectionMiddleware** — обнаружение дубликатов PID через LRU-кэш UsvConnection
  - **EventEmitMiddleware** — публикация `packet.processed`, ВСЕГДА вызывается (100% логирование)
- `tests/core/test_pipeline.py` — 15 тестов: порядок, terminated, exception handling, context passthrough
- `tests/core/test_crc_middleware.py` — 11 тестов: валидный/невалидный CRC, protocol из UsvConnection
- `tests/core/test_parse_middleware.py` — 10 тестов: успешный парсинг, ошибки, отсутствие protocol
- `tests/core/test_event_emit_middleware.py` — 10 тестов: emit события, данные события
- `tests/core/test_pipeline_integration.py` — 11 интеграционных тестов с реальными EGTS-пакетами:
  - Прогон 51 пакета из `data/packets/all_packets_correct_20260406_190414.json`
  - CRC-валидация всех пакетов
  - 100% emit событий (гарантия логирования)
  - Duplicate detection на реальных пакетах
  - RESPONSE и APPDATA типы пакетов
  - Error handling: невалидный CRC, пустой пакет, короткий пакет, неизвестный connection_id

#### Исправлено (в процессе разработки)
- ctx.parsed тип изменён с `ParseResult | None` на `dict[str, Any] | None` (согласовано с ТЗ)
- DuplicateDetectionMiddleware использует dict access `ctx.parsed["packet"]`
- PacketPipeline.process() гарантирует вызов EventEmitMiddleware даже при terminated=True
- ParseResult.extra поле для метаданных (service, tid, imei, imsi)

#### Метрики
- **60 тестов** в итерации 4 (43 unit + 6 integration + 11 integration с реальными пакетами)
- **81%** покрытие pipeline.py
- ruff clean, mypy clean
- **51 реальный EGTS-пакет** успешно обработан конвейером

---

## [0.0.0] — 2026-04-06

### Инициализация проекта
- Создание структуры проекта
- Техническое задание (`docs/ТЗ_тестер_УСВ.md`)
- Текст ГОСТ 33465-2015 (`docs/gost.md`)
- Тестовые данные (`docs/*.xlsx`)
- Навык `gost-compliance` для проверки соответствия ГОСТ
- Конвенции разработки и архитектурные принципы

[Unreleased]: https://github.com/your-org/OMEGA_EGTS/compare/v0.0.0...HEAD
