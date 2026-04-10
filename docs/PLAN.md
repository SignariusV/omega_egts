# План реализации — Серверный тестер УСВ (ТЗ v7.0)

**Дата создания:** 06.04.2026
**Дата обновления:** 10.04.2026
**Версия ТЗ:** 7.0 (Объединённая)
**Методология:** TDD (Test-Driven Development)
**Качество кода:** ruff + mypy + pytest (покрытие ≥ 90%)
**Прогресс:** 39/39 задач выполнено (100%) ✅ **v1.0.0 RELEASED**

---

## Общие принципы разработки

1. **TDD:** Сначала тесты → потом код → рефакторинг → коммит
2. **Ветвление:** Каждая итерация в своей ветке, сложные задачи — в отдельных ветках
3. **Параллелизм:** Независимые задачи внутри итерации можно выполнять параллельно (несколько агентов)
4. **Review:** После каждой задачи — код-ревью, перед коммитом — ruff + mypy + pytest
5. **Согласование:** Перед написанием кода — краткое описание задачи и подход, код только после согласия пользователя

---

## Итерация 0: Инфраструктура проекта

**Ветка:** `iteration-0/infrastructure`  
**Цель:** Настроить проектную инфраструктуру, зависимости, CI-инструменты

### Задача 0.1: Настройка проекта и зависимостей

**Суть:** Создать базовую структуру проекта, настроить pyproject.toml, установить зависимости для разработки.

**Что делать:**
1. Создать структуру директорий согласно ТЗ (Раздел 2.4):
   ```
   core/, libs/egts_protocol/, cli/, scenarios/, config/, tests/
   ```
2. Настроить `pyproject.toml`:
   - Зависимости: asyncio, pytest, pytest-cov, ruff, mypy
   - Скрипты: `egts-tester = "cli.app:main"`
   - Настройки pytest, ruff, mypy
3. Создать `.gitignore` (проверить актуальность)
4. Создать `conftest.py` с фикстурами для тестов

**Тестирование:**
```bash
pytest --version
ruff --version
mypy --version
```

**Коммит:** `feat: initialize project structure and dev dependencies`

**Критерии выполнения:**
- ✅ Все директории созданы
- ✅ `pip install -e ".[dev]"` работает
- ✅ pytest, ruff, mypy запускаются без ошибок
- ✅ conftest.py содержит базовые фикстуры

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `df1b99a` | Ветка: `master`

---

### Задача 0.2: Настройка конфигурации и тестовых данных

**Суть:** Создать файлы конфигурации по умолчанию и подготовить тестовые данные.

**Что делать:**
1. Создать `config/settings.json` (ТЗ Раздел 6.1)
2. Создать `config/credentials.json` (шаблон с примером)
3. Создать `tests/conftest.py` с фикстурами:
   - `sample_config` — тестовая конфигурация
   - `mock_event_bus` — мок EventBus
   - `sample_egts_packet` — пример пакета ГОСТ 2015
4. Создать папку `scenarios/` с подпапками для будущих сценариев

**Тестирование:**
```bash
pytest tests/ -v  # Должен показать 0 тестов, но без ошибок
```

**Коммит:** `feat: add default config files and test fixtures`

**Критерии выполнения:**
- ✅ Все конфиги валидны (JSON)
- ✅ pytest запускается без ошибок
- ✅ Фикстуры доступны во всех тестах

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `c6531f1` | Ветка: `master`

---

## Итерация 1: Core Engine Foundation

**Ветка:** `iteration-1/core-engine`  
**Цель:** Реализовать ядро системы — EventBus, Config, CoreEngine

### Задача 1.1: EventBus (async с ordered/parallel)

**Суть:** Реализовать асинхронную шину событий с поддержкой ordered (последовательных) и parallel (параллельных) обработчиков.

**Основано на:** ТЗ Раздел 2.3, код EventBus

**Что делать:**
1. **Сначала написать тесты** (`tests/core/test_event_bus.py`):
   - Тест basic emit/subscribe
   - Тест ordered handlers (последовательное выполнение)
   - Тест parallel handlers (параллельное выполнение через asyncio.gather)
   - Тест unsubscribe
   - Тест обработки ошибок в handlers
   - Тест: ordered выполняются до parallel

2. **Реализовать** `core/event_bus.py`:
   - Класс `Event` (dataclass)
   - Класс `EventBus` с методами `on()`, `off()`, `emit()`
   - Поддержка sync и async handlers
   - Ordered handlers выполняются последовательно
   - Parallel handlers через `asyncio.gather(return_exceptions=True)`

3. **Проверки:**
   ```bash
   ruff check core/event_bus.py
   mypy core/event_bus.py
   pytest tests/core/test_event_bus.py -v --cov=core.event_bus
   ```

4. **Коммит:** `feat: implement EventBus with ordered/parallel handlers`

**Критерии выполнения:**
- ✅ Все тесты проходят (≥ 90% coverage)
- ✅ ruff без ошибок
- ✅ mypy без ошибок
- ✅ ordered handlers гарантируют порядок
- ✅ parallel handlers не блокируют друг друга

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: pending | Ветка: `iteration-1/core-engine` | 14 тестов, 100% coverage

---

### Задача 1.2: Config (загрузка из JSON + CLI)

**Суть:** Реализовать конфигурацию с приоритетами: CLI args > settings.json > defaults.

**Основано на:** ТЗ Раздел 6, код Config

**Что делать:**
1. **Тесты** (`tests/core/test_config.py`):
   - Config.from_file() загружает JSON с вложенной структурой
   - CLI args переопределяют значения из файла (поддержка dot-notation: `"cmw500.timeout": 10`)
   - Значения по умолчанию при отсутствии файла
   - Валидация: порт 1–65535, таймауты > 0, retries >= 0
   - Frozen dataclass (неизменяемость)
   - Вложенные dataclass'ы: CmwConfig, TimeoutsConfig, LogConfig

2. **Реализовать** `core/config.py`:
   - `@dataclass(frozen=True) CmwConfig` — настройки CMW-500
   - `@dataclass(frozen=True) TimeoutsConfig` — таймауты протокола
   - `@dataclass(frozen=True) LogConfig` — настройки логирования
   - `@dataclass(frozen=True) Config` — корневой конфиг с вложенными секциями
   - `from_file()` — загрузка JSON (структура 1:1 с settings.json)
   - `merge_with_cli()` — overlay CLI через dot-notation (`"cmw500.timeout": 10`)
   - `__post_init__` — валидация

3. **Проверки:**
   ```bash
   ruff check core/config.py && mypy core/config.py && pytest tests/core/test_config.py -v
   ```

4. **Коммит:** `feat: implement Config with nested dataclasses, JSON loading and CLI override`

**Критерии выполнения:**
- ✅ Все тесты проходят
- ✅ ruff + mypy чистые
- ✅ Приоритет настроек соблюдается

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: pending | Ветка: `iteration-1/core-engine` | 28 тестов, 91% coverage

---

### Задача 1.3: CoreEngine (координатор компонентов)

**Суть:** Создать главный класс, который инициализирует все компоненты и управляет жизненным циклом.

**Основано на:** ТЗ Раздел 2.2, код CoreEngine

**Что делать:**
1. **Тесты** (`tests/core/test_core_engine.py`):
   - Инициализация с минимальной конфигурацией
   - start() запускает все компоненты
   - stop() корректно останавливает
   - Все компоненты инициализированы

2. **Реализовать** `core/engine.py`:
   - Класс `CoreEngine`
   - Методы `start()`, `stop()`
   - Инициализация всех менеджеров через конструктор
   - EventBus передаётся всем компонентам

3. **Заглушки для менеджеров:** Временно создать пустые классы для TcpServerManager, Cmw500Controller и т.д.

4. **Проверки:**
   ```bash
   ruff check core/engine.py && mypy core/engine.py && pytest tests/core/test_core_engine.py -v
   ```

5. **Коммит:** `feat: implement CoreEngine as main coordinator`

**Критерии выполнения:**
- ✅ CoreEngine стартует и останавливается без ошибок
- ✅ Все зависимости передаются через конструктор
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: pending | Ветка: `iteration-1/core-engine` | 6 тестов, 100% coverage

---

## Итерация 2: EGTS Protocol Library

**Ветка:** `iteration-2/egts-protocol`
**Цель:** Реализовать библиотеку парсинга/сборки EGTS-пакетов ГОСТ 2015

> **⚠️ Отклонение от ТЗ (раздел 2.4):** Вместо единого пакета `libs/egts_protocol/` (`base.py`, `v2015.py`, `v2023.py`, `sms.py`) реализована **двухпакетная архитектура**:
> - `libs/egts_protocol_iface/` — абстрактный интерфейс `IEgtsProtocol`, модели, enums, константы
> - `libs/egts_protocol_gost2015/` — реализация ГОСТ 2015 с адаптером и `gost2015_impl/` (копии из EGTS_GUI)
>
> **Причина:** dependency inversion — ядро зависит только от интерфейса, что упрощает добавление ГОСТ 2023 и мокирование при тестировании. Подробности в KNOWN_ISSUES.md (CR-006).

### Задача 2.1: Базовые структуры данных EGTS

**Суть:** Создать dataclass'ы для пакетов, записей, сабрекордов.

**Основано на:** ТЗ Раздел 2.5, структура `libs/egts_protocol/base.py`

**Что делать:**
1. **Тесты** (`tests/libs/test_egts_base.py`):
   - Создание Packet dataclass
   - Создание Record dataclass
   - Создание Subrecord dataclass
   - Сериализация/десериализация полей

2. **Реализовать** `libs/egts_protocol/base.py`:
   - `@dataclass Packet`, `Record`, `Subrecord`
   - Все поля транспортного уровня (PR, HL, PID, PN, RP, CID)
   - Все поля сервисного уровня

3. **Проверки:** ruff + mypy + pytest

4. **Коммит:** `feat: add EGTS base data structures (Packet, Record, Subrecord)`

**Критерии выполнения:**
- ✅ Все dataclass'ы созданы и типизированы
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | `libs/egts_protocol_iface/` — Packet, Record, Subrecord, ParseResult

---

### Задача 2.2: IEgtsProtocol интерфейс + factory

**Суть:** Определить общий интерфейс для всех версий ГОСТ и factory для создания экземпляров.

**Основано на:** ТЗ Раздел 2.5, код IEgtsProtocol + create_protocol

**Что делать:**
1. **Тесты** (`tests/libs/test_egts_protocol.py`):
   - create_protocol("2015") возвращает экземпляр
   - create_protocol("2023") выбрасывает NotImplementedError (пока не реализован)
   - Проверка наличия всех методов интерфейса

2. **Реализовать** `libs/egts_protocol/__init__.py`:
   - Protocol-класс `IEgtsProtocol`
   - Функция `create_protocol(gost_version)`
   - stub для EgtsProtocol2015

3. **Коммит:** `feat: add IEgtsProtocol interface and factory`

**Критерии выполнения:**
- ✅ Factory создаёт протокол по версии
- ✅ Интерфейс определён через Protocol
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | `egts_protocol_iface/` — IEgtsProtocol, `create_protocol()`, 73 теста iface

---

### Задача 2.3: EgtsProtocol2015 — парсинг/сборка транспортных заголовков

**Суть:** Реализовать парсинг транспортного уровня EGTS по ГОСТ 2015.

**Основано на:** ТЗ Раздел 2.5, структура пакета (PR, HL, ADDR, CID, PN, RP, Body, CRC-16)

**Что делать:**
1. **Тесты** (`tests/libs/test_egts_2015.py`):
   - Парсинг валидного заголовка
   - Парсинг заголовка с опциональными полями (ADDR, CID)
   - Валидация CRC-8 заголовка
   - Валидация CRC-16 тела
   - Сборка RESPONSE пакета
   - Сборка RECORD_RESPONSE

2. **Реализовать** `libs/egts_protocol/v2015.py`:
   - Класс `EgtsProtocol2015`
   - Метод `parse_packet(data: bytes) -> Packet`
   - Метод `build_response(pid: int, result_code: int) -> bytes`
   - Метод `build_record_response(crn: int, rst: int) -> bytes`
   - Методы `validate_crc8()`, `validate_crc16()`
   - Расчёт CRC-8 и CRC-16 по ГОСТ

3. **Проверки:** ruff + mypy + pytest (покрытие ≥ 90%)

4. **Коммит:** `feat: implement EgtsProtocol2015 transport level parsing and validation`

**Критерии выполнения:**
- ✅ Парсинг корректно извлекает все поля
- ✅ CRC валидация работает
- ✅ RESPONSE собирается корректно
- ✅ Тесты проходят с покрытием ≥ 90%

**Статус:** ✅ **ВЫПОЛНЕНО** | `gost2015_impl/` — packet, record, subrecord, CRC-8/16, adapter.py, 59 тестов

---

### Задача 2.4: EgtsProtocol2015 — SMS PDU

**Суть:** Реализовать упаковку/распаковку EGTS-пакетов в SMS PDU (ГОСТ 5.7, таблица 8).

**Основано на:** ТЗ Раздел 2.5, SMS PDU

**Что делать:**
1. **Тесты** (`tests/libs/test_egts_sms.py`):
   - Упаковка EGTS в PDU
   - Распаковка PDU в EGTS
   - Конкатенация длинных SMS

2. **Реализовать** в `libs/egts_protocol/v2015.py`:
   - `build_sms_pdu(egts_packet_bytes, destination_number) -> bytes`
   - `parse_sms_pdu(pdu_bytes) -> bytes`

3. **Коммит:** `feat: implement SMS PDU encoding/decoding for EGTS`

**Критерии выполнения:**
- ✅ PDU упаковывается/распаковывается
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | `gost2015_impl/sms.py` — SMS PDU, конкатенация, SMSReassembler

---

## Итерация 3: Session Management и FSM

**Ветка:** `iteration-3/session-management`
**Цель:** Реализовать управление сессиями, FSM состояний, транзакции

### Задача 3.1: UsvStateMachine (FSM)

**Суть:** Реализовать конечный автомат состояний УСВ по ГОСТ 33465-2015.

**Основано на:** ТЗ Раздел 3.2.2, полная диаграмма состояний

**Что делать:**
1. **Тесты** (`tests/core/test_fsm.py`):
   - **Каждый переход FSM — отдельный тест:**
     - DISCONNECTED → CONNECTED (TCP connected)
     - CONNECTED → AUTHENTICATING (service=1)
     - CONNECTED → RUNNING (service=2 от авторизованного)
     - CONNECTED → DISCONNECTED (таймаут 6с)
     - AUTHENTICATING → CONFIGURING (result_code=153, TID=0)
     - AUTHENTICATING → AUTHORIZED (result_code=0)
     - AUTHENTICATING → DISCONNECTED (таймаут 6с)
     - AUTHENTICATING → ERROR (ошибка протокола)
     - CONFIGURING → AUTHENTICATING (TID > 0)
     - CONFIGURING → DISCONNECTED (таймаут 5с)
     - AUTHORIZED → RUNNING (service=2)
     - AUTHORIZED → AUTHENTICATING (service=1 повторная)
     - RUNNING → AUTHENTICATING (service=1 повторная)
     - RUNNING → DISCONNECTED (таймаут 5с)
     - RUNNING → ERROR (ошибка CRC)
     - ERROR → DISCONNECTED (соединение закрыто)
   - Тест on_timeout() для каждого состояния
   - Тест on_disconnect()
   - Тест: неожиданные пакеты логируются как WARNING

2. **Реализовать** `core/session.py` (класс UsvStateMachine):
   - STATES = 7 состояний
   - `on_packet(parsed: dict) -> str | None`
   - `on_timeout() -> str | None`
   - `on_disconnect() -> None`
   - Простой if/elif/else (без метаклассов)

3. **Проверки:** ruff + mypy + pytest (100% покрытие переходов)

4. **Коммит:** `feat: implement UsvStateMachine with all state transitions per GOST`

**Критерии выполнения:**
- ✅ Все 16+ переходов протестированы
- ✅ Таймауты корректны (6с, 5с)
- ✅ Неожиданные пакеты обрабатываются
- ✅ Тесты проходят с покрытием 100% FSM

**Статус:** ✅ **ВЫПОЛНЕНО** | 27 тестов, все 18 переходов покрыты | Внешний аудит: 9.5/10

---

### Задача 3.2: TransactionManager

**Суть:** Реализовать отслеживание соответствий запрос-ответ (PID↔RPID, RN↔CRN).

**Основано на:** ТЗ Раздел 3.2.3, код TransactionManager

**Что делать:**
1. **Тесты** (`tests/core/test_transaction.py`):
   - register() с PID
   - register() с RN
   - match_response() находит по RPID
   - match_response() находит по CRN
   - match_response() возвращает None если нет транзакции
   - Timeout транзакций
   - Удаление после match

2. **Реализовать** `core/session.py` (класс TransactionManager):
   - `register(pid, rn, step_name, timeout)`
   - `match_response(rpid, crn) -> PendingTransaction | None`
   - PendingTransaction dataclass

3. **Коммит:** `feat: implement TransactionManager for PID/RN tracking`

**Критерии выполнения:**
- ✅ Все тесты проходят
- ✅ Транзакции корректно регистрируются и находятся

**Статус:** ✅ **ВЫПОЛНЕНО** | 14 тестов, cleanup orphan RN, _remove_txn helper

---

### Задача 3.3: UsvConnection

**Суть:** Реализовать класс подключения УСВ с LRU-кэшем для дубликатов.

**Основано на:** ТЗ Раздел 3.2.1, код UsvConnection

**Что делать:**
1. **Тесты** (`tests/core/test_connection.py`):
   - Создание подключения
   - add_pid_response() / get_response()
   - LRU eviction (MAX_SEEN_PIDS = 65536)
   - move_toEnd при повторном обращении
   - usv_id property (TID если есть, иначе connection_id)

2. **Реализовать** `core/session.py` (класс UsvConnection):
   - Все поля из ТЗ
   - `_seen_pids: OrderedDict`
   - LRU логика

3. **Коммит:** `feat: implement UsvConnection with LRU duplicate cache`

**Критерии выполнения:**
- ✅ LRU работает корректно
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 8 тестов, LRU eviction, usv_id

---

### Задача 3.4: SessionManager

**Суть:** Координировать подключения, обновлять FSM, хранить соединения.

**Основано на:** ТЗ Раздел 3.2.4, код SessionManager

**Что делать:**
1. **Тесты** (`tests/core/test_session_manager.py`):
   - Создание/получение подключения
   - Обработка packet.processed → обновление FSM
   - Emit connection.changed при смене состояния
   - Сохранение TID/IMEI/IMSI из parsed пакета

2. **Реализовать** `core/session.py` (класс SessionManager):
   - `connections: dict[str, UsvConnection]`
   - Подписка на `packet.processed` (ordered=True)
   - `_on_packet()` обновляет FSM

3. **Коммит:** `feat: implement SessionManager as FSM coordinator`

**Критерии выполнения:**
- ✅ FSM обновляется при каждом пакете
- ✅ События connection.changed эмитятся
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 12 тестов, async close_session, duplicate check, emit

---

## Итерация 4: Packet Processing Pipeline

**Ветка:** `iteration-4/pipeline`  
**Цель:** Реализовать middleware-конвейер обработки пакетов

### Задача 4.1: PacketPipeline + PacketContext

**Суть:** Создать базовый конвейер с контекстом пакета.

**Основано на:** ТЗ Раздел 3.3, PacketContext + PacketPipeline

**Что делать:**
1. **Тесты** (`tests/core/test_pipeline.py`):
   - Создание pipeline
   - Добавление middleware
   - Последовательное выполнение middleware
   - Прерывание при terminated=True
   - Прерывание при exception
   - PacketContext инициализация

2. **Реализовать** `core/pipeline.py`:
   - `@dataclass PacketContext`
   - `class PacketPipeline` с `add()` и `process()`
   - Обработка ошибок и terminated

3. **Коммит:** `feat: implement PacketPipeline with middleware chain`

**Критерии выполнения:**
- ✅ Middleware выполняются последовательно
- ✅ Прерывание работает
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `709fcdb` | Ветка: `iteration-4/pipeline` | 15 тестов, stable sort, exception handling

---

### Задача 4.2: CrcValidationMiddleware

**Суть:** Валидация CRC-8 и CRC-16 пакетов.

**Основано на:** ТЗ Раздел 3.4.1

**Что делать:**
1. **Тесты** (`tests/core/test_crc_middleware.py`):
   - Валидный CRC-8 и CRC-16
   - Невалидный CRC-8
   - Невалидный CRC-16
   - protocol из __init__ (не хардкод!)

2. **Реализовать** `core/pipeline.py`:
   - `CrcValidationMiddleware(protocol: IEgtsProtocol)`
   - Валидация и установка флагов в ctx

3. **Коммит:** `feat: add CrcValidationMiddleware with injectable protocol`

**Критерии выполнения:**
- ✅ CRC валидация работает
- ✅ Protocol не захардкожен
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `709fcdb` | 11 тестов, RESPONSE с EGTS_PC_HEADERCRC_ERROR/EGTS_PC_DATACRC_ERROR

---

### Задача 4.3: ParseMiddleware

**Суть:** Парсинг EGTS-пакетов через protocol.

**Основано на:** ТЗ Раздел 3.4.2

**Что делать:**
1. **Тесты** (`tests/core/test_parse_middleware.py`):
   - Успешный парсинг
   - Ошибка парсинга (битый пакет)
   - Отсутствие protocol у подключения

2. **Реализовать** `core/pipeline.py`:
   - `ParseMiddleware(session_mgr)`
   - Получение protocol из SessionManager

3. **Коммит:** `feat: add ParseMiddleware for EGTS packet parsing`

**Критерии выполнения:**
- ✅ Парсинг работает
- ✅ Ошибки обрабатываются
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `676a9ad` | 10 тестов, ParseResult (packet + errors + warnings + extra)

---

### Задача 4.4: DuplicateDetectionMiddleware

**Суть:** Обнаружение и отсев дубликатов PID.

**Основано на:** ТЗ Раздел 3.4.3

**Что делать:**
1. **Тесты** (`tests/core/test_duplicate_middleware.py`):
   - Первый пакет — не дубликат, RESPONSE отправлен
   - Повторный PID — дубликат, terminated=True
   - RESPONSE берётся из кэша, не пересоздаётся

2. **Реализовать** `core/pipeline.py`:
   - `DuplicateDetectionMiddleware(session_mgr)`
   - Проверка через `conn.get_response(pid)`
   - Отправка RESPONSE из кэша

3. **Коммит:** `feat: add DuplicateDetectionMiddleware with LRU cache`

**Критерии выполнения:**
- ✅ Дубликаты определяются
- ✅ RESPONSE не отправляется повторно
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `34903be` | 8 тестов, LRU-кэш, guards для crc_valid/parsed/is_duplicate

---

### Задача 4.5: EventEmitMiddleware

**Суть:** Публикация события packet.processed после обработки.

**Основано на:** ТЗ Раздел 2.7.1

**Что делать:**
1. **Тесты** (`tests/core/test_event_emit_middleware.py`):
   - Emit packet.processed с ctx
   - Проверка данных в событии

2. **Реализовать** `core/pipeline.py`:
   - `EventEmitMiddleware(bus)`
   - `await bus.emit("packet.processed", ...)`

3. **Коммит:** `feat: add EventEmitMiddleware for pipeline completion`

**Критерии выполнения:**
- ✅ Событие эмитится
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `676a9ad` | 10 тестов, всегда вызывается (даже при terminated=True), 100% логирование

---

### Задача 4.6: AutoResponseMiddleware

**Суть:** Формирование RESPONSE для успешно обработанных пакетов (CR-009).

**Основано на:** ТЗ Раздел 1.7 — «Ядро отправляет RESPONSE»

**Что делать:**
1. **Тесты** (`tests/core/test_auto_response_middleware.py`):
   - Успешный пакет → response_data заполнен
   - crc_valid=False → пропускает
   - parsed=None → пропускает
   - is_duplicate=True → пропускает
   - response_data уже заполнен → не перезаписывает
   - connection not found → пропускает
   - protocol=None → пропускает
   - add_pid_response вызывается
   - Интеграция: полный pipeline + дубликат из кэша

2. **Реализовать** `core/pipeline.py`:
   - `AutoResponseMiddleware(session_mgr)` — order=3
   - Формирует `protocol.build_response(pid, result_code=0)`
   - Кеширует через `conn.add_pid_response(pid, response)`

3. **Реализовать** `core/dispatcher.py`:
   - `PacketDispatcher._build_pipeline()` — добавляет AutoResponseMiddleware
   - `pipeline` параметр теперь Optional (по умолчанию создаётся через `_build_pipeline`)

4. **Коммит:** `fix: исправить CR-009 — AutoResponseMiddleware`

**Критерии выполнения:**
- ✅ RESPONSE формируется для каждого успешного пакета
- ✅ RESPONSE кешируется для дубликатов
- ✅ 12 тестов, 96% coverage pipeline.py
- ✅ ruff + mypy clean
- ✅ Все 118 существующих тестов проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 12 тестов, AutoResponseMiddleware order=3, _build_pipeline() в PacketDispatcher

---

## Итерация 5: Network и CMW-500

**Ветка:** `iteration-5/network-cmw`  
**Цель:** Реализовать TCP-сервер, контроллер CMW-500 и эмулятор

### Задача 5.1: TcpServerManager

**Суть:** Asyncio TCP-сервер для приёма EGTS-пакетов.

**Основано на:** ТЗ Раздел 3.1, код TcpServerManager

**Что делать:**
1. **Тесты** (`tests/core/test_tcp_server.py`):
   - start() запускает сервер на порту
   - stop() останавливает
   - Приём подключения клиента
   - Чтение данных и emit raw.packet.received
   - Обработка отключения клиента
   - Emit connection.changed при подключении/отключении
   - Обработка ошибки соединения

2. **Реализовать** `core/tcp_server.py`:
   - `asyncio.start_server`
   - `_handle_connection(reader, writer)`
   - Чтение пакетов (header + body)
   - Emit событий

3. **Проверки:** ruff + mypy + pytest (с интеграционными тестами)

4. **Коммит:** `feat: implement TcpServerManager with asyncio TCP server`

**Критерии выполнения:**
- ✅ Сервер запускается/останавливается
- ✅ Подключения обрабатываются
- ✅ События эмитятся
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 15 тестов, 97% coverage, ruff + mypy чистые

---

### Задача 5.2: Cmw500Controller с очередью команд

**Суть:** Контроллер CMW-500 через SCPI с retry и очередью. Поддержка SMS (отправка + приём).

**Основано на:** ТЗ Раздел 2.6.2, код Cmw500Controller

**Архитектурное решение по SMS (09.04.2026):**
CMW-500 сам кодирует/декодирует SMS PDU. Мы передаём только сырые EGTS-байты:
- **Отправка:** `send_sms(egts_bytes)` → SCPI `CMW:GSM:SIGN:SMS:SEND` → CMW-500 сам упаковывает в PDU
- **Приём:** `read_sms()` → SCPI `CMW:GSM:SIGN:SMS:READ?` → CMW-500 возвращает сырые EGTS-байты
- **Номер получателя не нужен** — CMW-500 шлёт тому УСВ, которое подключено к прибору

**Важно:** SMS имеет существенно бо́льшие задержки чем TCP:
- Отправка SMS: 3–30 с (vs ~200 мс TCP)
- Приём SMS: опрос `read_sms()` каждую 1–5 с (vs постоянный поток TCP)
- Таймаут транзакции для SMS: 30–60 с (vs 5–10 с TCP)

**Что делать:**
1. **Тесты** (`tests/core/test_cmw500.py`):
   - connect/disconnect
   - execute команды через очередь
   - Retry при ошибке (3 попытки)
   - Timeout команды
   - **send_sms** — отправка сырых EGTS-байт через SCPI
   - **read_sms** — приём сырых EGTS-байт из принятой SMS
   - **_poll_incoming_sms** — фоновый опрос, emit raw.packet.received
   - get_imei, get_status

2. **Реализовать** `core/cmw500.py`:
   - `CmwCommand` dataclass
   - `Cmw500Controller` с asyncio.Queue
   - `_worker_loop()`
   - `_execute_with_retry()`
   - Предопределённые команды (GET_IMEI, SEND_SMS, READ_SMS, ...)
   - `async send_sms(egts_bytes: bytes) -> bool` — обёртка над SEND_SMS (CMW-500 сам кодирует PDU)
   - `async read_sms() -> bytes | None` — читает принятую SMS, возвращает сырые EGTS-байты (CMW-500 сам декодирует PDU)
   - `async _poll_incoming_sms()` — фоновая задача: опрос READ_SMS каждую секунду, emit `raw.packet.received` с `channel="sms"`

3. **Коммит:** `feat: implement Cmw500Controller with command queue, retry, and SMS support`

**Критерии выполнения:**
- ✅ Команды выполняются через очередь
- ✅ Retry работает (3 попытки)
- ✅ SMS-отправка: сырые EGTS-байты → SCPI SEND
- ✅ SMS-приём: опрос READ_SMS → emit raw.packet.received
- ✅ Фоновый опрос SMS не блокирует другие команды
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 39 тестов, фоновый poll loop, fix orphan future, disconnect cleanup

---

### Задача 5.3: Cmw500Emulator

**Суть:** Эмулятор CMW-500 для разработки и тестов. Поддержка TCP и SMS.

**Основано на:** ТЗ Раздел 2.6.3, код Cmw500Emulator

**Архитектурное решение по SMS (09.04.2026):**
Эмулятор имитирует поведение реального CMW-500 по SMS:
- `send_sms(egts_bytes)` — «отправляет» пакет на подключённый УСВ (эмулирует задержку SMS)
- `read_sms()` — возвращает ответный пакет от «УСВ» (эмулирует принятую SMS)
- `_poll_incoming_sms()` — эмулирует входящие SMS с настраиваемой задержкой

**Что делать:**
1. **Тесты** (`tests/core/test_cmw_emulator.py`):
   - Ответы на SCPI-команды
   - Случайные задержки TCP: 100мс–2с
   - **Случайные задержки SMS: 3–30 с** (настраиваемый диапазон)
   - Эмуляция IMEI/IMSI/RSSI
   - **send_sms — имитация задержки, возврат OK**
   - **read_sms — возврат «ответного» пакета от УСВ**
   - **_poll_incoming_sms — эмуляция входящих SMS с интервалом 1–5 с**

2. **Реализовать** `core/cmw500.py`:
   - `Cmw500Emulator(Cmw500Controller)` — наследуется, переопределяет SCPI
   - `_send_scpi()` с random.sleep (настраиваемый диапазон)
   - **`send_sms(egts_bytes)` — случайная задержка 3–30 с, сохранение в очередь входящих**
   - **`read_sms() -> bytes | None` — возврат ответа из очереди «входящих SMS»**
   - **`set_incoming_sms_handler(handler)` — колбэк для эмуляции ответов УСВ**
   - Ответы на команды

3. **Коммит:** `feat: implement Cmw500Emulator with SMS support (delayed send, read, poll)`

**Критерии выполнения:**
- ✅ Эмулятор отвечает на команды
- ✅ Задержки TCP случайные (100мс–2с)
- ✅ **SMS-отправка эмулирует задержку 3–30 с**
- ✅ **SMS-приём возвращает ответ от «УСВ»**
- ✅ **Фоновый опрос SMS работает**
- ✅ Тесты проходит

**Статус:** ✅ **ВЫПОЛНЕНО** | 19 тестов, внешний аудит исправлен (queue-based send_sms, async handler, task_done, RuntimeError protection)

---

### Задача 5.4: PacketDispatcher

**Суть:** Координатор pipeline, связывает raw packets → pipeline → packet.processed. Поддержка TCP и SMS каналов.

**Основано на:** ТЗ Раздел 2.7.1, код PacketDispatcher

**Архитектурное решение (09.04.2026):**
PacketDispatcher — **channel-агностик**. Он не различает TCP и SMS:
- `channel` передаётся из источника пакета в pipeline
- `connection_id` для SMS = `None` (нет постоянного соединения)
- Pipeline обрабатывает оба канала одинаково — различие только в контексте

**Что делать:**
1. **Тесты** (`tests/core/test_packet_dispatcher.py`):
   - Подписка на `raw.packet.received`
   - **TCP-канал:** `connection_id` передан → pipeline.process(raw, channel="tcp", connection_id="...")
   - **SMS-канал:** `connection_id=None` → pipeline.process(raw, channel="sms", connection_id=None)
   - Вызов pipeline.process()
   - Emit packet.processed с `channel` и `connection_id`
   - Pipeline собирается с правильным order middleware

2. **Реализовать** `core/dispatcher.py`:
   - `PacketDispatcher(bus, session_mgr, protocol)`
   - `_build_pipeline()` — добавляет все middleware в порядке
   - `_on_raw_packet(data: dict)`:
     ```python
     ctx = await self.pipeline.process(
         raw=data["raw"],
         channel=data["channel"],           # "tcp" или "sms"
         connection_id=data.get("connection_id")  # str или None
     )
     await self.bus.emit("packet.processed", {
         "ctx": ctx,
         "connection_id": data.get("connection_id"),
         "channel": data["channel"]
     })
     ```

3. **Коммит:** `feat: implement PacketDispatcher as pipeline coordinator (TCP + SMS agnostic)`

**Критерии выполнения:**
- ✅ Pipeline вызывается для каждого пакета (TCP и SMS)
- ✅ `connection_id=None` корректно передаётся для SMS
- ✅ `channel` корректно передаётся в packet.processed
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 24 теста, 95% coverage, ruff + mypy чистые

---

### Задача 5.5: CommandDispatcher + SMS-отправка

**Суть:** Отправка команд через TCP-подключение и через SMS (CMW-500), регистрация транзакций.

**Основано на:** ТЗ Раздел 2.7.2, код CommandDispatcher + Сценарий 9 (SMS-канал)

**Архитектурное решение (Вариант А — принят на 09.04.2026):**
CommandDispatcher единый для обоих каналов. Проверка `data.get("channel", "tcp")`:
- `"tcp"` (или отсутствует) → `conn.writer.write()` — напрямую в TCP-соединение
- `"sms"` → `cmw.send_sms(packet_bytes)` — сырые байты EGTS в CMW-500, он сам упаковывает в PDU и шлёт подключённому УСВ

**Важно:** CMW-500 знает, какое УСВ подключено — номер получателя не нужен. Мы передаём только сырые байты EGTS-пакета, CMW-500 сам кодирует PDU и отправляет SMS. Аналогично на приёме — CMW-500 возвращает сырые EGTS-байты из принятой SMS.

Это сохраняет единый интерфейс `command.send` для сценариев — им не нужно знать, какой диспетчер вызывать.

**Что делать:**
1. **Тесты** (`tests/core/test_command_dispatcher.py`):
   - Подписка на command.send
   - **TCP-канал:** запись данных в writer, регистрация транзакции, emit command.sent
   - **SMS-канал:** вызов `cmw.send_sms(packet_bytes)`, emit command.sent
   - Emit command.error при ошибке (оба канала)
   - Ошибка если connection_id не найден (только для TCP)
   - Ошибка если CMW-500 не подключён (для SMS)

2. **Реализовать** `core/dispatcher.py`:
   - `CommandDispatcher(bus, session_mgr, cmw=None)`
   - `_on_command()` — проверка `channel`, маршрутизация на TCP или SMS
   - `_send_tcp()` — запись в conn.writer, регистрация транзакции
   - `_send_sms()` — вызов `cmw.send_sms(packet_bytes)`, регистрация транзакции
   - `_handle_error()` — emit command.error

3. **Добавить в Cmw500Controller** (Задача 5.2):
   - `async send_sms(packet_bytes: bytes) -> bool` — обёртка над SEND_SMS командой (CMW-500 сам кодирует PDU)
   - `async read_sms() -> bytes | None` — читает принятую SMS, возвращает сырые EGTS-байты (CMW-500 сам декодирует PDU)

4. **Сценарий SMS (пример):**
   ```json
   {
     "type": "send",
     "channel": "sms",
     "build": { "service": 1, "fields": { "TID": 12345 } },
     "step_name": "auth_sms"
   }
   ```
   **Никакого `recipient` — CMW-500 шлёт тому УСВ, которое подключено к прибору.**

5. **Коммит:** `feat: implement CommandDispatcher with TCP and SMS channel support`

**Критерии выполнения:**
- ✅ TCP-отправка работает как раньше
- ✅ SMS-отправка: сырые EGTS-байты → `cmw.send_sms()`
- ✅ Приём SMS: `cmw.read_sms()` → сырые EGTS-байты → pipeline
- ✅ Сценарии указывают только `channel: "sms"`
- ✅ Транзакции регистрируются для обоих каналов
- ✅ Ошибки обрабатываются корректно
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 23 теста, 95% coverage (совместно с PacketDispatcher), ruff + mypy чистые

---

### Задача 5.6: Интеграционные тесты

**Суть:** Тесты взаимодействия всех реализованных компонентов — цепочка от EventBus до Pipeline, SessionManager, CommandDispatcher.

**Основано на:** ТЗ Раздел 3.10 (интеграционное тестирование), архитектура EventBus

**Что делать:**
1. **Тесты** (`tests/core/test_integration_chain.py`):
   - **TCP-пайплайн:** raw.packet.received → Pipeline (CRC→Parse→Dedup→Event) → packet.processed
   - **Дубликаты:** повторный PID определяется через DuplicateDetectionMiddleware
   - **SMS-канал:** channel="sms" сохраняется через pipeline
   - **CommandDispatcher TCP:** writer.write вызывается, command.sent эмитается
   - **CommandDispatcher SMS:** cmw.send_sms вызывается, command.sent эмитается
   - **EventBus ordered:** последовательное выполнение handlers

2. **Коммит:** `feat: add integration chain tests (pipeline + dispatchers + session)`

**Критерии выполнения:**
- ✅ Все 6 интеграционных тестов проходят
- ✅ Цепочка компонентов подтверждена: EventBus → Pipeline → SessionManager
- ✅ TCP и SMS каналы работают через CommandDispatcher

**Статус:** ✅ **ВЫПОЛНЕНО** | 6 тестов, интеграция EventBus→Pipeline→SessionManager→CommandDispatcher подтверждена

---

## Итерация 6: LogManager и Credentials

**Ветка:** `iteration-6/logging-credentials`  
**Цель:** Реализовать логирование и хранилище учётных данных

### Задача 6.1: LogManager

**Суть:** Подписчик на события, логирует 100% пакетов.

**Основано на:** ТЗ Раздел 3.6, код LogManager

**Что делать:**
1. **Тесты** (`tests/core/test_logger.py`):
   - Логирование packet.processed (hex + parsed)
   - Логирование connection.changed
   - Логирование scenario.step
   - Создание файлов логов
   - Буферизация + сортировка по timestamp (CR-002)

2. **Реализовать** `core/logger.py`:
   - `LogManager(bus, log_dir)`
   - Подписка на события
   - Запись в файлы
   - Буферизация с сортировкой

3. **Коммит:** `feat: implement LogManager with 100% packet logging`

**Критерии выполнения:**
- ✅ 100% пакетов логируется
- ✅ Файлы создаются
- ✅ Порядок логов сохранён
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 23 теста, 93% coverage, JSONL + буферизация + сортировка

---

### Задача 6.2: CredentialsRepository

**Суть:** JSON-хранилище учётных данных с защитой файла.

**Основано на:** ТЗ Раздел 3.7, код CredentialsRepository

**Что делать:**
1. **Тесты** (`tests/core/test_credentials.py`):
   - Загрузка из JSON
   - Поиск по IMEI
   - Защита файла (chmod 600 на Linux, документированное ограничение на Windows)
   - Сохранение новых данных (ключ = creds.device_id)

2. **Реализовать** `core/credentials.py`:
   - `Credentials` dataclass с to_dict()/from_dict()
   - `CredentialsRepository` — find_by_imei(), get(), save(), list_all()
   - `_secure_file()` — chmod 600 (Unix), ACL warning (Windows)

3. **Исправлено по внешнему аудиту:**
   - Убран параметр `device_id` из `save()` — ключ из `creds.device_id`
   - Логи предупреждений на английском

**Коммит:** `feat: реализовать CredentialsRepository с защитой файла (итерация 6.2)`

**Критерии выполнения:**
- ✅ Поиск работает (find_by_imei, get)
- ✅ Файл защищён (chmod 600 / ACL warning)
- ✅ save() без рассинхронизации
- ✅ 25 тестов, 94% покрытие, ruff + mypy clean

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `3d12953` | Ветка: `iteration-6/logging-credentials`

---

## Итерация 7: Scenario Engine

**Ветка:** `iteration-7/scenarios`
**Цель:** Реализовать систему сценариев — парсеры версий, шаги, контекст, выполнение

> **Архитектурное решение (версионирование сценариев):**
> Аналогично EGTS-протоколу (`IEgtsProtocol` → `EgtsProtocol2015`/`EgtsProtocol2023`),
> формат сценариев абстрагирован через `IScenarioParser`. Это позволяет добавлять новые
> версии формата сценариев без изменения ядра `ScenarioManager`.
>
> При добавлении V2 — только `ScenarioParserV2` + `registry.register("2", V2)`.
> Старые сценарии продолжают работать. Подробности в `ARCHITECTURE.md`.

### Задача 7.0: ScenarioParser Abstraction (версионирование форматов)

**Суть:** Абстракция над форматом сценариев — Protocol + Factory + Registry.

**Основано на:** Идея из NOTES.md — «предусмотреть возможность разных обработчиков для разных версий сценариев»

**Проблема:** Сценарии будут эволюционировать. Если захардкодить парсинг v1 в `ScenarioManager`, добавление v2 потребует переписывания монолитного кода.

**Решение:** Pattern, аналогичный `IEgtsProtocol`:
```
IScenarioParser (Protocol)
    ├── ScenarioParserV1   ← текущий формат: type, channel, checks, capture, packet_file
    ├── ScenarioParserV2   ← будущий: loops, conditions, parallel_steps
    └── ScenarioParserV3

ScenarioParserRegistry → register("1", V1) → get("1")
ScenarioParserFactory   → читает scenario_version → создаёт парсер
ScenarioManager         → работает только с IScenarioParser
```

**Что делать:**
1. **Тесты** (`tests/core/test_scenario_parser.py`):
   - **IScenarioParser Protocol** — все методы определены
   - **ScenarioParserV1 — валидация:**
     - Валидный scenario.json — 0 ошибок
     - Missing `steps` — ошибка
     - Step без `type` — ошибка
     - Invalid `type` (не send/expect/wait/check) — ошибка
     - Invalid `channel` (не tcp/sms) — ошибка
     - Missing `timeout` — warning (дефолт)
     - Duplicate step names — warning
   - **ScenarioParserV1 — парсинг:**
     - Извлечение metadata: name, gost_version, timeout, description, channels
     - Парсинг steps: type, name, channel, checks, capture, packet_file, build
     - Capture paths: `records[0].fields.RN` → валидный nested path
   - **ScenarioParserRegistry:**
     - register("1", ScenarioParserV1) → get("1") возвращает экземпляр
     - get("99") → KeyError
     - Итерация по всем версиям
   - **ScenarioParserFactory:**
     - create("1") → ScenarioParserV1
     - create("2") → NotImplementedError (пока не реализован)
     - detect_and_create(data) — читает `data["scenario_version"]` → create()
2. **Реализовать** `core/scenario_parser.py`:
   ```python
   @runtime_checkable
   class IScenarioParser(Protocol):
       def load(self, data: dict) -> ScenarioMetadata: ...
       def validate(self, data: dict) -> list[str]: ...
       def get_steps(self) -> list[StepDefinition]: ...
       def get_metadata(self) -> ScenarioMetadata: ...

   @dataclass
   class ScenarioMetadata:
       name: str
       version: str
       gost_version: str | None
       timeout: float
       description: str | None
       channels: list[str]

   @dataclass
   class StepDefinition:
       name: str
       type: str  # send, expect, wait, check
       channel: str | None  # tcp, sms, None
       timeout: float | None
       checks: dict[str, Any]  # V1: field → expected_value
       capture: dict[str, str]  # V1: var_name → nested_path
       packet_file: str | None  # V1: путь к HEX-файлу
       build: dict[str, Any] | None  # V1: template для генерации
       extra: dict[str, Any]  # дополнительные поля версии

   class ScenarioParserV1:
       def validate(self, data: dict) -> list[str]:
           # Проверки: steps exists, type ∈ {send,expect,wait,check},
           # channel ∈ {tcp,sms,None}, capture paths valid
       def load(self, data: dict) -> ScenarioMetadata:
           # Извлечение metadata + парсинг steps
       def get_steps(self) -> list[StepDefinition]: ...
       def get_metadata(self) -> ScenarioMetadata: ...

   class ScenarioParserRegistry:
       def register(self, version: str, parser_cls: type[IScenarioParser]) -> None
       def get(self, version: str) -> type[IScenarioParser]
       def __iter__(self) -> Iterator[tuple[str, type[IScenarioParser]]]

   class ScenarioParserFactory:
       def __init__(self, registry: ScenarioParserRegistry): ...
       def create(self, version: str) -> IScenarioParser: ...
       def detect_and_create(self, data: dict) -> IScenarioParser: ...
   ```
3. **Проверки:**
   ```bash
   ruff check core/scenario_parser.py && mypy core/scenario_parser.py
   pytest tests/core/test_scenario_parser.py -v --cov=core.scenario_parser
   ```
4. **Коммит:** `feat: implement ScenarioParser abstraction with versioned format parsers`

**Критерии выполнения:**
- ✅ IScenarioParser определён как Protocol (@runtime_checkable)
- ✅ ScenarioParserV1 валидирует и парсит текущий формат
- ✅ Registry расширяем без изменений в Factory
- ✅ Factory создаёт парсер по версии
- ✅ detect_and_create() читает scenario_version из данных
- ✅ 20+ тестов, ≥ 90% coverage
- ✅ ruff + mypy чистые

**Статус:** ✅ **ВЫПОЛНЕНО** | 29 тестов, 99% coverage, IScenarioParser + V1 + Registry + Factory

---

### Задача 7.1: ScenarioContext

**Суть:** Контекст выполнения сценария с переменными и автоопределением connection_id.

**Основано на:** ТЗ Раздел 3.5.1, код ScenarioContext

**Изменения с учётом Задачи 7.0:**
- Добавить поле `scenario_version: str` — версия формата (из metadata)
- Добавить поле `parser: IScenarioParser | None` — ссылка на парсер (для introspection)
- `ScenarioContext` создаётся **после** парсинга — `ScenarioParserFactory` уже определил версию

**Что делать:**
1. **Тесты** (`tests/core/test_scenario_context.py`):
   - set/get переменных
   - TTL переменных (is_expired)
   - substitute шаблонов {{var}}
   - _resolve_connection_id()
   - history

2. **Реализовать** `core/scenario.py`:
   - `Variable` dataclass
   - `ScenarioContext` с полями: `scenario_version: str`, `parser: IScenarioParser | None`
   - Все методы

3. **Коммит:** `feat: implement ScenarioContext with variables and TTL`

**Критерии выполнения:**
- ✅ Переменные сохраняются/получаются
- ✅ TTL работает
- ✅ scenario_version установлен из metadata
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 21 тест, 98% coverage, Variable с TTL, substitute {{var}}, _resolve_connection_id

---

### Задача 7.2: ExpectStep

**Суть:** Ожидание пакета от УСВ с проверкой полей и capture переменных.

**Основано на:** ТЗ Раздел 3.5.2, код ExpectStep

**Что делать:**
1. **Тесты** (`tests/core/test_expect_step.py`):
   - Ожидание пакета (PASS)
   - Timeout (TIMEOUT)
   - Disconnect (ERROR)
   - match по точному значению
   - match по regex
   - match по диапазону
   - capture переменных из вложенных путей (`records[0].fields.RN`)
   - in_response_to (проверка RPID/CRN)

2. **Реализовать** `core/scenario.py`:
   - `ExpectStep`
   - `_matches()`, `_get_nested()`, `_match_criterion()`
   - Подписка на packet.processed + connection.changed
   - asyncio.Event + wait_for

3. **Коммит:** `feat: implement ExpectStep with pattern matching and capture`

**Критерии выполнения:**
- ✅ Ожидание работает
- ✅ Все типы match поддерживаются
- ✅ Capture извлекает переменные
- ✅ Disconnect обрабатывается сразу (не timeout)
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 22 теста, match (exact/regex/range), capture nested paths, in_response_to

---

### Задача 7.3: SendStep

**Суть:** Отправка пакета (из файла или динамически).

**Основано на:** ТЗ Раздел 3.5.3, код SendStep

**Что делать:**
1. **Тесты** (`tests/core/test_send_step.py`):
   - Отправка из файла
   - Отправка из build template
   - Автоопределение connection_id
   - Регистрация транзакции _txn_{step_name}
   - Timeout отправки
   - Ошибка при отсутствии подключения

2. **Реализовать** `core/scenario.py`:
   - `SendStep`
   - `_build_packet()` (файл + template)
   - `_build_from_template()`
   - Emit command.send + ожидание command.sent

3. **Коммит:** `feat: implement SendStep with file loading and template building`

**Критерии выполнения:**
- ✅ Пакеты отправляются
- ✅ Файлы загружаются
- ✅ Шаблоны работают
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 18 тестов, file + build template, _txn_{step_name}, command.sent ожидание

---

### Задача 7.4: ScenarioManager

**Суть:** Загрузка и выполнение сценариев из scenario.json через `ScenarioParserFactory`.

**Основано на:** ТЗ Раздел 3.5, 4.1-4.3

**Архитектурное решение (09.04.2026):**
`ScenarioManager` **не парсит JSON напрямую**. Он делегирует парсинг `ScenarioParserFactory`,
которая читает `scenario_version` и создаёт нужный парсер (V1, V2, ...).
Это позволяет добавлять новые версии формата без изменения `ScenarioManager`.

```python
def load(self, path: Path) -> None:
    data = json.loads(path.read_text())
    parser = self._parser_factory.detect_and_create(data)
    errors = parser.validate(data)
    if errors:
        raise ScenarioValidationError(errors)
    self._metadata = parser.load(data)
    self._steps = parser.get_steps()
    self._context = ScenarioContext(
        scenario_version=self._metadata.version,
        gost_version=self._metadata.gost_version,
    )
```

**Что делать:**
1. **Тесты** (`tests/core/test_scenario_manager.py`):
   - Загрузка scenario.json через parser_factory (V1)
   - Ошибка валидации → ScenarioValidationError
   - Неподдерживаемая версия → ValueError
   - Выполнение шагов (expect + send)
   - StepFactory создаёт правильные типы шагов
   - Обработка ошибок шагов
   - Результат сценария (PASS/FAIL/TIMEOUT)

2. **Реализовать** `core/scenario.py`:
   - `ScenarioManager` — зависит от `ScenarioParserFactory`, не от конкретного парсера
   - `load()` — делегирует парсинг factory
   - `execute()` — выполняет шаги через StepFactory
   - `StepFactory` — создаёт ExpectStep/SendStep по типу из StepDefinition

3. **Коммит:** `feat: implement ScenarioManager with versioned parser support`

**Критерии выполнения:**
- ✅ Сценарии загружаются через parser_factory (не напрямую)
- ✅ Валидация выполняется до выполнения
- ✅ Результаты корректны
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 9 тестов, StepFactory (ExpectStep/SendStep), общий timeout, remaining timeout

---

### Задача 7.5: Готовые сценарии (10 штук)

**Суть:** Создать папки с scenario.json для всех 10 сценариев.

**Основано на:** ТЗ Раздел 4.4, 10 сценариев

**Что делать:**
1. Создать сценарии:
   - `scenarios/auth/scenario.json` — Авторизация
   - `scenarios/telemetry/scenario.json` — Телеметрия
   - `scenarios/track/scenario.json` — Траектория
   - `scenarios/accel/scenario.json` — Профиль ускорения
   - `scenarios/ecall/scenario.json` — eCall
   - `scenarios/fw_update/scenario.json` — Обновление ПО
   - `scenarios/commands/scenario.json` — Команды
   - `scenarios/test_mode/scenario.json` — Режим тестирования
   - `scenarios/sms_channel/scenario.json` — SMS-канал
   - `scenarios/passive_mode/scenario.json` — Пассивный режим

2. Для каждого — scenario.json с шагами

3. **Коммит:** `feat: add all 10 ready-made scenarios per ТЗ`

**Критерии выполнения:**
- ✅ Все 10 сценариев созданы
- ✅ JSON валиден
- ✅ Шаги соответствуют ТЗ

**Статус:** ✅ **ВЫПОЛНЕНО** | 10 сценариев (auth, telemetry, track, accel, ecall, fw_update, commands, test_mode, sms_channel, passive_mode)

---

## Итерация 8: Replay и Export

**Ветка:** `iteration-8/replay-export`  
**Цель:** Реализовать replay-режим и выгрузку данных

### Задача 8.1: ReplaySource

**Суть:** Загрузка лога пакетов и повторная обработка.

**Основано на:** ТЗ Раздел 3.8, код ReplaySource

**Что делать:**
1. **Тесты** (`tests/core/test_replay.py`):
   - Загрузка лога из JSON
   - Replay с pipeline (полная обработка)
   - Replay без pipeline (быстрый)
   - skip_duplicates фильтрация
   - Эмит packet.processed

2. **Реализовать** `core/packet_source.py`:
   - `ReplaySource`
   - `replay()` метод
   - Фильтрация дубликатов

3. **Коммит:** `feat: implement ReplaySource for offline analysis`

**Критерии выполнения:**
- ✅ Replay работает
- ✅ Дубликаты фильтруются
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 21 тест, 98% coverage, JSONL load + pipeline + emit packet.processed

---

### Задача 8.2: Export (CSV/JSON/DER)

**Суть:** Выгрузка результатов тестирования.

**Основано на:** ТЗ Раздел 2.4 (export.py)

**Что делать:**
1. **Тесты** (`tests/core/test_export.py`):
   - Export CSV
   - Export JSON
   - Экспорт результатов сценария

2. **Реализовать** `core/export.py`:
   - `export_csv()`, `export_json()`
   - Форматирование результатов

3. **Коммит:** `feat: implement Export for test results (CSV/JSON)`

**Критерии выполнения:**
- ✅ Файлы экспорта валидны
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | 18 тестов, 96% coverage, export_csv/json + scenario_results

---

## Итерация 9: CLI Application

**Ветка:** `iteration-9/cli`  
**Цель:** Создать CLI приложение — тонкую обёртку над Core Engine

### Задача 9.1: CLI команды (argparse)

**Суть:** Реализовать все команды CLI из ТЗ Раздел 5.1.

**Основано на:** ТЗ Раздел 5.1-5.2

**Что делать:**
1. **Тесты** (`tests/cli/test_cli.py`):
   - Парсинг аргументов для каждой команды
   - start, stop, replay, run-scenario, batch, status, export, monitor

2. **Реализовать** `cli/app.py`:
   - argparse с подкомандами
   - Вызов методов CoreEngine
   - Форматирование вывода
   - REPL режим (cmd)

3. **Проверки:** ruff + mypy + интеграционные тесты

4. **Коммит:** `feat: implement CLI with all commands from ТЗ`

**Критерии выполнения:**
- ✅ Все команды работают
- ✅ REPL режим функционален
- ✅ Тесты проходят

**Статус:** ✅ **ВЫПОЛНЕНО** | Коммит: `6d18c47` | Ветка: `iteration-9/cli` | 43 теста CLI

---

## Итерация 10: Интеграция и приёмка

**Ветка:** `iteration-10/integration`  
**Цель:** Полная интеграция, финальные тесты, документация

### Задача 10.1: Интеграционные тесты

**Суть:** End-to-end тесты с эмулятором CMW-500.

**Что делать:**
1. **Тесты** (`tests/core/test_e2e_integration.py`):
   - CoreEngine + Cmw500Emulator + TcpServer полный цикл
   - Полный сценарий авторизации (AUTH → pipeline → FSM → RESPONSE)
   - Множественные пакеты (AUTH → COMMAND)
   - Определение дубликатов в реальном времени
   - SMS-канал через эмулятор CMW-500
   - Логирование пакетов в файлы
   - Выполнение сценариев через ScenarioManager
   - Replay + Export end-to-end
   - API статуса (get_status, cmw_status)

2. **Коммит:** `feat: итерация 10.1 — E2E интеграционные тесты (10 тестов)`

**Критерии выполнения:**
- ✅ Все интеграционные тесты проходят
- ✅ ruff check clean
- ✅ Покрытие ключевых модулей ≥ 90%

**Статус:** ✅ **ВЫПОЛНЕНО** | 10 тестов, 921 total, 89% coverage, ruff clean | Коммит: `e76c19d`

---

### Задача 10.2: Финальные проверки и документация

**Суть:** Обновить всю документацию, проверить качество кода.

**Что делать:**
1. **Проверки:**
   ```bash
   ruff check . && ruff format .
   mypy core/ libs/ cli/
   pytest --cov=core --cov=libs --cov=cli --cov-report=term-missing
   ```

2. **Обновить документацию:**
   - `KNOWN_ISSUES.md` — переместить решённые issues, добавить новые
   - `docs/ARCHITECTURE.md` — актуализировать схему
   - `CHANGELOG.md` — добавить все изменения
   - `README.md` — обновить статус и быстрый старт

3. **Коммит:** `docs: update all documentation for v1.0.0`

**Критерии выполнения:**
- ✅ ruff + mypy чистые
- ✅ pytest покрытие ≥ 90%
- ✅ Документация актуальна

**Статус:** ✅ **ВЫПОЛНЕНО** | ruff clean, 921 тест, 89% coverage, вся документация обновлена

---

### Задача 10.3: Финальный релиз

**Суть:** Тегирование версии, проверка критериев приёмки.

**Что делать:**
1. Проверить все критерии приёмки из ТЗ Раздел 9:
   - Функциональные (9 пунктов)
   - Нефункциональные (5 пунктов)

2. Создать тег `v1.0.0`

3. **Коммит:** `release: v1.0.0 — CLI MVP ready`

**Критерии выполнения:**
- ✅ Все критерии приёмки выполнены
- ✅ Тег создан

**Статус:** ✅ **ВЫПОЛНЕНО** | Тег `v1.0.0` создан на коммите `485728d` | 2026-04-10

---

## Параллельные задачи (можно запускать несколько агентов)

### Внутри итерации 2 (EGTS Protocol):
- **Агент A:** Задача 2.1 (базовые структуры)
- **Агент B:** Задача 2.2 (интерфейс + factory)

### Внутри итерации 4 (Pipeline):
- **Агент A:** Задача 4.2 (CrcValidationMiddleware)
- **Агент B:** Задача 4.3 (ParseMiddleware)
- **Агент A (после 4.2):** Задача 4.4 (DuplicateDetectionMiddleware)
- **Агент B (после 4.3):** Задача 4.5 (EventEmitMiddleware)

### Внутри итерации 5 (Network):
- **Агент A:** Задача 5.1 (TcpServerManager)
- **Агент B:** Задача 5.2 (Cmw500Controller) + 5.3 (Emulator)

### Внутри итерации 7 (Scenarios):
- **Агент A:** Задача 7.2 (ExpectStep)
- **Агент B:** Задача 7.3 (SendStep)
- **После A+B:** Задача 7.4 (ScenarioManager)
- **Параллельно:** Задача 7.5 (10 сценариев) — можно разделить по 2 на агента

### Внутри итерации 8 (Replay/Export):
- **Агент A:** Задача 8.1 (ReplaySource)
- **Агент B:** Задача 8.2 (Export)

---

## Сводная таблица итераций

| # | Итерация | Ветка | Задач | Зависимости | Можно параллельно |
|---|----------|-------|-------|-------------|-------------------|
| 0 | Инфраструктура | `iteration-0/infrastructure` | 2 | — | Нет |
| 1 | Core Engine | `iteration-1/core-engine` | 3 | Итерация 0 | 1.1 и 1.2 параллельно |
| 2 | EGTS Protocol | `iteration-2/egts-protocol` | 4 | Итерация 1 | 2.1 и 2.2 параллельно |
| 3 | Session/FSM | `iteration-3/session-fsm` | 4 | Итерация 1 | 3.1, 3.2, 3.3 параллельно |
| 4 | Pipeline | `iteration-4/pipeline` | 6 | Итерация 2, 3 | 4.2+4.3, затем 4.4+4.5 |
| 5 | Network/CMW | `iteration-5/network-cmw` | 6 | Итерация 3, 4 | 5.1 и 5.2+5.3 параллельно |
| 6 | Logging/Creds | `iteration-6/logging-credentials` | 2 | Итерация 5 | 6.1 и 6.2 параллельно |
| 7 | Scenarios | `iteration-7/scenarios` | 6 | Итерация 5 | 7.2+7.3, затем 7.4, 7.5 отдельно |
| 8 | Replay/Export | `iteration-8/replay-export` | 2 | Итерация 6 | 8.1 и 8.2 параллельно |
| 9 | CLI | `iteration-9/cli` | 1 | Итерация 8 | Нет |
| 10 | Интеграция | `master` | 3 | Все предыдущие | Нет |
| | **ИТОГО** | | **39** | | **✅ 100%** |

---

## Правила работы для каждой задачи

1. **Перед началом:** Описать суть задачи и подход → ждать согласия пользователя
2. **TDD:**
   - Написать тесты (pytest)
   - Убедиться, что тесты падают
   - Реализовать код
   - Убедиться, что тесты проходят
3. **Проверки:** `ruff check` → `mypy` → `pytest --cov`
4. **Review:** После реализации — review кода
5. **Коммит:** После review и проверок — коммит с понятным сообщением
6. **Документация:** Обновлять CHANGELOG.md и KNOWN_ISSUES.md при необходимости

---

## Критерии готовности каждой задачи (общие)

- ✅ Все тесты написаны и проходят
- ✅ Покрытие ≥ 90% для нового кода
- ✅ `ruff check` без ошибок
- ✅ `mypy` без ошибок
- ✅ Код-ревью выполнен
- ✅ Коммит с описанием
- ✅ Документация обновлена (если требуется)

---

**Конец плана**

*Создано на основе ТЗ v7.0, 06.04.2026*
