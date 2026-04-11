# Changelog — OMEGA_EGTS

Все значимые изменения проекта. Формат: [Keep a Changelog](https://keepachangelog.com/), версионирование: [SemVer](https://semver.org/).

---

## [Unreleased]

### RESPONSE с RECORD_RESPONSE (ГОСТ 33465-2015, раздел 6.7.2.1)

**Дата:** 11.04.2026

#### Проблема
RESPONSE на TERM_IDENTITY был **16 байт** (только RPID + PR) — без записи `RECORD_RESPONSE`.
По ГОСТ 33465-2015 (разделы 6.7.2.1, 6.8.1) RESPONSE должен содержать подтверждение записи
уровня поддержки услуг — `EGTS_SR_RECORD_RESPONSE`.

#### Architectural решение
Вместо создания отдельных методов (`build_response_with_record()`, `build_response_with_command()` и т.д.)
реализован **единый метод** `build_response()` с типизированным параметром `records`:

```python
@dataclass
class ResponseRecord:
    rn: int                       # Record Number подтверждаемой записи (CRN)
    service: int                  # SST — тип сервиса
    subrecords: list[Subrecord]   # подзаписи (RECORD_RESPONSE)
    rsod: bool = True             # RFL bit 6 — получатель на платформе

def build_response(
    self, pid: int, result_code: int,
    records: list[ResponseRecord] | None = None,
    **kwargs: object,
) -> bytes:
```

#### Изменения

| Файл | Что изменено |
|------|-------------|
| `libs/egts_protocol_iface/models.py` | + `ResponseRecord` dataclass |
| `libs/egts_protocol_iface/__init__.py` | Экспорт `ResponseRecord`, `records` параметр в `IEgtsProtocol.build_response()` |
| `libs/egts_protocol_gost2015/adapter.py` | Маппинг `ResponseRecord → InternalRecord`, fallback для unknown service → AUTH_SERVICE |
| `core/pipeline.py` | `AutoResponseMiddleware` извлекает записи из входящего пакета, формирует `ResponseRecord` с `EGTS_SR_RECORD_RESPONSE` |
| `tests/.../test_adapter.py` | + `TestBuildResponseWithRecords` (5 тестов) |
| `tests/integration/test_full_integration.py` | Проверка структуры RESPONSE через `Packet.from_bytes()` + `parse_records()` |

#### Результат

| Параметр | До | После |
|----------|-----|-------|
| Длина RESPONSE | 16 байт | **29 байт** |
| FDL | 3 | **16** (RPID + PR + RECORD) |
| Записи | ❌ | ✅ RN, SST=1, SRT=0, CRN, RST=0, RSOD=1 |
| Соответствие ГОСТ | ❌ Частичное | ✅ Полное (раздел 6.7.2.1) |
| Тесты | 921 | **926 passed** |

#### Обратная совместимость
`records=None` (по умолчанию) = старое поведение (минимальный RESPONSE без записей).

---

### Итерация 10: E2E интеграция и финальные проверки (завершена)

**Ветка:** `master` | **Коммит:** `7d7426b`

#### Added
- **E2E интеграционные тесты** — 10 тестов, покрывающих полный цикл:
  - CoreEngine + Cmw500Emulator + TcpServer
  - Полный сценарий авторизации (AUTH → pipeline → FSM → RESPONSE)
  - Множественные пакеты (AUTH → COMMAND)
  - Определение дубликатов в реальном времени
  - SMS-канал через эмулятор CMW-500
  - Логирование пакетов в файлы
  - Выполнение сценариев через ScenarioManager
  - Replay + Export end-to-end
  - API статуса (get_status, cmw_status)
- **Финальные проверки:**
  - ruff check: clean
  - mypy: clean для core/ (тесты без strict type hints — норма)
  - pytest: 921 тест, 89% coverage (ключевые модули 90%+)
  - Исправлен flaky test `test_sms_delay_is_within_bounds` (Windows timing)

#### Fixed
- **Ложное определение дубликатов в pipeline** — порядок middleware изменён:
  `CRC(1) → Parse(2) → Dedup(2.5) → AutoResponse(3) → EventEmit(5)`.
  Раньше AutoResponse добавлял PID в кэш _до_ Dedup, поэтому первый пакет
  определялся как дубликат (находил RESPONSE, который только что сам добавил).
  Теперь Dedup проверяет кэш _до_ того как AutoResponse его заполнит.
- **`connection_id: null` в логах FSM** — `SessionManager._on_packet_processed()`
  теперь включает `connection_id` в событие `connection.changed`.
- **RESPONSE не логируется** — `LogManager._on_packet_processed()` теперь записывает
  `response_hex` (hex RESPONSE-пакета) из `ctx.response_data`.

---

## [1.0.0] — 2026-04-10

### CLI MVP — Итерации 1–8

**Ветка:** `master` | **Тестов:** 870 | **Покрытие:** 90%+ | **ruff:** clean | **mypy:** clean

### Добавлено

#### Итерация 1: Core Engine Foundation
- **EventBus** — async шина с ordered/parallel handlers, 10 событий (14 тестов, 100%)
- **Config** — nested dataclass'ы, JSON загрузка, CLI merge с dot-notation, валидация (28 тестов, 91%)
- **CoreEngine** — координатор компонентов, start/stop lifecycle (6 тестов, 100%)

#### Итерация 2: EGTS Protocol Library
- **egts_protocol_iface** — IEgtsProtocol (Protocol), create_protocol factory, модели, enums, константы (73 теста, 100%)
- **egts_protocol_gost2015** — парсинг/сборка пакетов, CRC-8/16, SMS PDU, сервисы (59 тестов адаптера)

#### Итерация 3: Session Management и FSM
- **UsvStateMachine** — FSM с 7 состояниями и 18 переходами по ГОСТ 33465-2015 (27 тестов, 100% FSM)
- **TransactionManager** — PID↔RPID, RN↔CRN, cleanup_expired, _remove_txn helper (14 тестов)
- **UsvConnection** — LRU-кэш дубликатов (OrderedDict, MAX_SEEN_PIDS=65536), usv_id (8 тестов)
- **SessionManager** — координатор, async close_session, подписка на packet.processed ordered=True (12 тестов)

#### Итерация 4: Packet Processing Pipeline
- **PacketPipeline** — middleware-конвейер, PacketContext (15 тестов)
- **CrcValidationMiddleware** — CRC-8/CRC-16, RESPONSE с кодами ошибок (11 тестов)
- **ParseMiddleware** — парсинг через protocol, ParseResult с extra-полями (10 тестов)
- **DuplicateDetectionMiddleware** — обнаружение дубликатов PID через LRU-кэш (8 тестов)
- **AutoResponseMiddleware** — RESPONSE для успешных пакетов, кеш (12 тестов)
- **EventEmitMiddleware** — публикация packet.processed, всегда вызывается (10 тестов)
- **Интеграционные тесты** — 51 реальный EGTS-пакет, 11 тестов

#### Итерация 5: Network и CMW-500
- **TcpServerManager** — asyncio TCP-сервер, приём подключений, emit raw.packet.received (15 тестов, 97%)
- **Cmw500Controller** — очередь команд, retry, SMS send/read, фоновый poll (39 тестов, 91%)
- **Cmw500Emulator** — эмулятор CMW-500, TCP 0.1–2с, SMS 3–30с, handler ответов (19 тестов)
- **PacketDispatcher** — координатор pipeline, TCP + SMS каналы (24 теста, 95%)
- **CommandDispatcher** — отправка TCP/SMS, регистрация транзакций (23 теста, 95%)
- **Интеграционные тесты** — цепочка EventBus→Pipeline→SessionManager→CommandDispatcher (6 тестов)

#### Итерация 6: LogManager и Credentials
- **LogManager** — JSONL, буферизация + сортировка по timestamp, 5 подписок (23 теста, 93%)
- **CredentialsRepository** — JSON-хранилище, chmod 600, find_by_imei (25 тестов, 94%)

#### Итерация 7: Scenario Engine
- **IScenarioParser** — Protocol: load/validate/get_steps/get_metadata (29 тестов, 99%)
- **ScenarioContext** — переменные с TTL, {{var}} подстановка, history (21 тест, 98%)
- **ExpectStep** — exact/regex/range match, capture nested, in_response_to (22 теста)
- **SendStep** — file + build template, command.sent ожидание (18 тестов)
- **ScenarioManager** — parser_factory, StepFactory, общий timeout, per-step remaining (9 тестов)
- **10 сценариев**: auth, telemetry, track, accel, ecall, fw_update, commands, test_mode, sms_channel, passive_mode (7 рабочих + 4 stub)

#### Итерация 8: ReplaySource и Export
- **ReplaySource** — JSONL load, pipeline replay, skip_duplicates (21 тест, 98%)
- **Export** — export_csv, export_json, export_scenario_results_csv/json (18 тестов, 96%)

### Исправлено

- CR-002: Порядок логов при parallel — буферизация + сортировка (R-077)
- CR-007: Windows-защита — ACL warning вместо attrib +h (R-078)
- CR-008: Protocol создаётся автоматически в create_session() (R-080)
- CR-009: AutoResponseMiddleware добавлен в pipeline (R-076)
- CR-010: FSM on_connect() при TCP-подключении (R-081)
- CR-011: FSM on_disconnect() при разрыве (R-082)
- CR-012: FSM обрабатывает RESPONSE-пакеты (R-083)
- CR-014: Порядок middleware исправлен (R-084)
- CR-015: Версионирование сценариев — IScenarioParser (R-079)
- 80+ исправлений внешнего аудита (R-024–R-075, R-085–R-100)

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

## [0.0.0] — 2026-04-06

### Инициализация проекта
- Создание структуры проекта
- Техническое задание (`docs/ТЗ_тестер_УСВ.md`)
- Текст ГОСТ 33465-2015 (`docs/gost.md`)
- Тестовые данные (`docs/*.xlsx`)
- Навык `gost-compliance` для проверки соответствия ГОСТ
- Конвенции разработки и архитектурные принципы

[0.1.0]: https://github.com/your-org/OMEGA_EGTS/compare/v0.0.0...HEAD
[Unreleased]: https://github.com/your-org/OMEGA_EGTS/compare/v0.1.0...HEAD
