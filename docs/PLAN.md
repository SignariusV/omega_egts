# План реализации — Серверный тестер УСВ (ТЗ v7.0)

**Дата создания:** 06.04.2026
**Дата обновления:** 09.04.2026
**Версия ТЗ:** 7.0 (Объединённая)
**Методология:** TDD (Test-Driven Development)
**Качество кода:** ruff + mypy + pytest (покрытие ≥ 90%)
**Прогресс:** 27/36 задач выполнено (75%)

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

**Статус:** ✅ **ВЫПОЛНЕНО** | 15 тестов, stable sort by order, exception handling, context passthrough

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

**Статус:** ✅ **ВЫПОЛНЕНО** | 11 тестов, RESPONSE с EGTS_PC_HEADERCRC_ERROR/EGTS_PC_DATACRC_ERROR

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

**Статус:** ✅ **ВЫПОЛНЕНО** | 10 тестов, ParseResult с extra-полями (service, tid, imei, imsi)

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

**Статус:** ✅ **ВЫПОЛНЕНО** | 8 тестов, dict access ctx.parsed["packet"], guards для crc_valid/parsed

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

**Статус:** ✅ **ВЫПОЛНЕНО** | 10 тестов, всегда вызывается (даже при terminated=True), 100% логирование

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

---

### Задача 5.2: Cmw500Controller с очередью команд

**Суть:** Контроллер CMW-500 через SCPI с retry и очередью.

**Основано на:** ТЗ Раздел 2.6.2, код Cmw500Controller

**Что делать:**
1. **Тесты** (`tests/core/test_cmw500.py`):
   - connect/disconnect
   - execute команды через очередь
   - Retry при ошибке (3 попытки)
   - Timeout команды
   - send_sms, get_imei, get_status

2. **Реализовать** `core/cmw500.py`:
   - `CmwCommand` dataclass
   - `Cmw500Controller` с asyncio.Queue
   - `_worker_loop()`
   - `_execute_with_retry()`
   - Предопределённые команды (GET_IMEI, SEND_SMS, ...)

3. **Коммит:** `feat: implement Cmw500Controller with command queue and retry`

**Критерии выполнения:**
- ✅ Команды выполняются через очередь
- ✅ Retry работает
- ✅ Тесты проходят

---

### Задача 5.3: Cmw500Emulator

**Суть:** Эмулятор CMW-500 для разработки и тестов.

**Основано на:** ТЗ Раздел 2.6.3, код Cmw500Emulator

**Что делать:**
1. **Тесты** (`tests/core/test_cmw_emulator.py`):
   - Ответы на SCPI-команды
   - Случайные задержки (100мс-2с)
   - Эмуляция IMEI/IMSI/RSSI

2. **Реализовать** `core/cmw500.py`:
   - `Cmw500Emulator(Cmw500Controller)`
   - `_send_scpi()` с random.sleep
   - Ответы на команды

3. **Коммит:** `feat: implement Cmw500Emulator for development testing`

**Критерии выполнения:**
- ✅ Эмулятор отвечает на команды
- ✅ Задержки случайные
- ✅ Тесты проходят

---

### Задача 5.4: PacketDispatcher

**Суть:** Координатор pipeline, связывает raw packets → pipeline → packet.processed.

**Основано на:** ТЗ Раздел 2.7.1, код PacketDispatcher

**Что делать:**
1. **Тесты** (`tests/core/test_packet_dispatcher.py`):
   - Подписка на raw.packet.received
   - Вызов pipeline.process()
   - Emit packet.processed
   - Pipeline собирается с правильным order middleware

2. **Реализовать** `core/dispatcher.py`:
   - `PacketDispatcher`
   - `_build_pipeline()` — добавляет все middleware в порядке
   - `_on_raw_packet()`

3. **Коммит:** `feat: implement PacketDispatcher as pipeline coordinator`

**Критерии выполнения:**
- ✅ Pipeline вызывается для каждого пакета
- ✅ Тесты проходят

---

### Задача 5.5: CommandDispatcher

**Суть:** Отправка команд через подключение, регистрация транзакций.

**Основано на:** ТЗ Раздел 2.7.2, код CommandDispatcher

**Что делать:**
1. **Тесты** (`tests/core/test_command_dispatcher.py`):
   - Подписка на command.send
   - Запись данных в writer
   - Регистрация транзакции
   - Emit command.sent
   - Emit command.error при ошибке
   - Ошибка если connection_id не найден

2. **Реализовать** `core/dispatcher.py`:
   - `CommandDispatcher`
   - `_on_command()` с try/except

3. **Коммит:** `feat: implement CommandDispatcher for sending EGTS commands`

**Критерии выполнения:**
- ✅ Команды отправляются
- ✅ Ошибки обрабатываются
- ✅ Тесты проходят

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

---

### Задача 6.2: CredentialsRepository

**Суть:** JSON-хранилище учётных данных с защитой файла.

**Основано на:** ТЗ Раздел 3.7, код CredentialsRepository

**Что делать:**
1. **Тесты** (`tests/core/test_credentials.py`):
   - Загрузка из JSON
   - Поиск по IMEI
   - Защита файла (attrib +h на Windows, chmod 600 на Linux)
   - Сохранение новых данных

2. **Реализовать** `core/credentials.py`:
   - `CredentialsRepository`
   - `_secure_file()`
   - `find_by_imei()`, `save()`

3. **Коммит:** `feat: implement CredentialsRepository with file protection`

**Критерии выполнения:**
- ✅ Поиск работает
- ✅ Файл защищён
- ✅ Тесты проходят

---

## Итерация 7: Scenario Engine

**Ветка:** `iteration-7/scenarios`  
**Цель:** Реализовать систему сценариев — шаги, контекст, выполнение

### Задача 7.1: ScenarioContext

**Суть:** Контекст выполнения сценария с переменными и автоопределением connection_id.

**Основано на:** ТЗ Раздел 3.5.1, код ScenarioContext

**Что делать:**
1. **Тесты** (`tests/core/test_scenario_context.py`):
   - set/get переменных
   - TTL переменных (is_expired)
   - substitute шаблонов {{var}}
   - _resolve_connection_id()
   - history

2. **Реализовать** `core/scenario.py`:
   - `Variable` dataclass
   - `ScenarioContext`
   - Все методы

3. **Коммит:** `feat: implement ScenarioContext with variables and TTL`

**Критерии выполнения:**
- ✅ Переменные сохраняются/получаются
- ✅ TTL работает
- ✅ Тесты проходят

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

---

### Задача 7.4: ScenarioManager

**Суть:** Загрузка и выполнение сценариев из scenario.json.

**Основано на:** ТЗ Раздел 3.5, 4.1-4.3

**Что делать:**
1. **Тесты** (`tests/core/test_scenario_manager.py`):
   - Загрузка scenario.json
   - Выполнение шагов (expect + send)
   - StepFactory создаёт правильные типы шагов
   - Обработка ошибок шагов
   - Результат сценария (PASS/FAIL/TIMEOUT)

2. **Реализовать** `core/scenario.py`:
   - `ScenarioManager`
   - `load()`, `execute()`
   - StepFactory

3. **Коммит:** `feat: implement ScenarioManager for scenario execution`

**Критерии выполнения:**
- ✅ Сценарии загружаются и выполняются
- ✅ Результаты корректны
- ✅ Тесты проходят

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

---

## Итерация 10: Интеграция и приёмка

**Ветка:** `iteration-10/integration`  
**Цель:** Полная интеграция, финальные тесты, документация

### Задача 10.1: Интеграционные тесты

**Суть:** End-to-end тесты с эмулятором CMW-500.

**Что делать:**
1. **Тесты** (`tests/integration/test_full_cycle.py`):
   - Запуск CoreEngine
   - Подключение клиента (mock)
   - Авторизация (полный цикл)
   - Отправка телеметрии
   - Запуск сценария
   - Остановка

2. **Коммит:** `test: add integration tests for full lifecycle`

**Критерии выполнения:**
- ✅ Все интеграционные тесты проходят
- ✅ Покрытие ≥ 90%

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
| 4 | Pipeline | `iteration-4/pipeline` | 5 | Итерация 2, 3 | 4.2+4.3, затем 4.4+4.5 |
| 5 | Network/CMW | `iteration-5/network-cmw` | 5 | Итерация 3, 4 | 5.1 и 5.2+5.3 параллельно |
| 6 | Logging/Creds | `iteration-6/logging-credentials` | 2 | Итерация 5 | 6.1 и 6.2 параллельно |
| 7 | Scenarios | `iteration-7/scenarios` | 5 | Итерация 5 | 7.2+7.3, затем 7.4, 7.5 отдельно |
| 8 | Replay/Export | `iteration-8/replay-export` | 2 | Итерация 7 | 8.1 и 8.2 параллельно |
| 9 | CLI | `iteration-9/cli` | 1 | Итерация 7 | Нет |
| 10 | Интеграция | `iteration-10/integration` | 3 | Все предыдущие | Нет |

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
