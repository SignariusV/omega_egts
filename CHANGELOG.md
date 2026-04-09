# Changelog — OMEGA_EGTS

Все значимые изменения проекта. Формат: [Keep a Changelog](https://keepachangelog.com/), версионирование: [SemVer](https://semver.org/).

---

## [Unreleased]

### Этап 1: CLI MVP (в разработке)
- [x] EventBus — async шина с ordered/parallel handlers (итерация 1.1)
- [x] Config — nested dataclass'ы, JSON загрузка, CLI merge, валидация (итерация 1.2)
- [x] CoreEngine — координатор компонентов (итерация 1.3)
- [x] FSM авторизации — UsvStateMachine (7 сост., 18 переходов), TransactionManager, UsvConnection, SessionManager (итерация 3)
- [ ] asyncio TCP-сервер для приёма EGTS-пакетов
- [ ] Поддержка ГОСТ 33465-2015 (транспортный уровень)
- [ ] Эмулятор CMW-500 для тестирования
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

## [0.0.0] — 2026-04-06

### Инициализация проекта
- Создание структуры проекта
- Техническое задание (`docs/ТЗ_тестер_УСВ.md`)
- Текст ГОСТ 33465-2015 (`docs/gost.md`)
- Тестовые данные (`docs/*.xlsx`)
- Навык `gost-compliance` для проверки соответствия ГОСТ
- Конвенции разработки и архитектурные принципы

[Unreleased]: https://github.com/your-org/OMEGA_EGTS/compare/v0.0.0...HEAD
