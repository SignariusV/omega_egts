# Архитектура — OMEGA_EGTS

Детальное описание архитектуры серверного тестера УСВ.

---

## Принципы

1. **Единое ядро** — CLI/GUI тонкие обёртки поверх `core/`
2. **EventBus** — единственная шина коммуникации между компонентами (10 событий по ТЗ v7.0, ordered + parallel handlers)
3. **Разделение ответственности** — парсинг ≠ валидация ≠ бизнес-логика ≠ логирование ≠ интерфейс
4. **FSM тестируется изолированно** — без сети, CMW-500, EGTS-пакетов
5. **Автономность** — ядро работает без сценария: принимает пакеты, отправляет RESPONSE, ведёт FSM, логирует

---

## Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI / GUI (тонкие обёртки)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ команды / события UI
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CoreEngine (ядро)                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                       EventBus                             │  │
│  │  3 события: packet.received | connection.changed |         │  │
│  │           scenario.step                                   │  │
│  └────────┬──────────┬──────────┬──────────┬─────────┬───────┘  │
│           │          │          │          │         │          │
│  ┌────────▼────┐ ┌──▼──────┐ ┌─▼───────┐ ┌▼──────┐ ┌▼────────┐ │
│  │TcpServer    │ │Cmw500   │ │Session  │ │Scenario│ │Packet   │ │
│  │Manager      │ │Controller│ │Manager │ │Manager │ │Pipeline │ │
│  └─────────────┘ └─────────┘ └─────────┘ └────────┘ └─────────┘ │
│  ┌─────────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐            │
│  │LogManager   │ │Credentials│ │Export   │ │Config  │            │
│  │             │ │Repository │ │         │ │        │            │
│  └─────────────┘ └─────────┘ └──────────┘ └────────┘            │
└─────────────────────────────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    Внешние системы       │
              │  ┌──────────┐ ┌───────┐ │
              │  │ УСВ      │ │CMW-500│ │
              │  │ (тестер) │ │(железо)│ │
              │  └──────────┘ └───────┘ │
              └─────────────────────────┘
```

---

## Компоненты

### CoreEngine

**Файл:** `core/engine.py`

Точка входа. Инициализирует все компоненты, подписывает на события, запускает event-loop.

```python
class CoreEngine:
    async def start(self) -> None
    async def stop(self) -> None
```

**Жизненный цикл:**
1. Загрузка `config/settings.json`
2. Инициализация EventBus
3. Создание компонентов (TcpServer, Session, Pipeline, ...)
4. Подписка LogManager на `packet.received`, `connection.changed`, `scenario.step`
5. Запуск TCP-сервера
6. Ожидание подключений

---

### CoreEngine

**Файл:** `core/engine.py` | **Статус:** ✅ Реализован (итерация 1.3)

Главный координатор системы. Управляет жизненным циклом: инициализация, запуск, остановка.

```python
@dataclass
class CoreEngine:
    config: Config
    bus: EventBus
    _running: bool

    async def start(self) -> None  # Инициализация компонентов, emit("server.started")
    async def stop(self) -> None   # Остановка компонентов, emit("server.stopped")
```

**Использование:**
```python
engine = CoreEngine(config=config, bus=bus)
await engine.start()  # Запуск
await engine.stop()   # Остановка
```

**Особенности:**
- `start()` — idempotent (повторный вызов игнорируется)
- `stop()` без `start()` — не падает
- Компоненты инициализируются через конструкторы (ручной DI)
- События: `server.started` (port), `server.stopped` (reason)

---

### EventBus

**Файл:** `core/event_bus.py` | **Статус:** ✅ Реализован (итерация 1.1)

Асинхронная шина событий. Компоненты **не вызывают друг друга напрямую** — только через события.

```python
class EventBus:
    def on(self, event_name: str, handler: Callable, ordered: bool = False) -> None
    def off(self, event_name: str, handler: Callable) -> None
    async def emit(self, event_name: str, data: dict) -> None
```

**Поддерживаемые события (ТЗ v7.0, Раздел 2.3):**

| Событие | Данные | Кто публикует | Кто подписывается |
|---------|--------|---------------|-------------------|
| `raw.packet.received` | `raw, channel (tcp/sms), connection_id` | TcpServerManager, Cmw500Controller | PacketDispatcher |
| `packet.processed` | `ctx, connection_id, channel` | PacketDispatcher | SessionManager (ordered), LogManager, ScenarioManager |
| `command.send` | `connection_id, packet_bytes, step_name, pid, rn, timeout, channel` | ScenarioManager | CommandDispatcher |
| `command.sent` | `connection_id, channel, step_name, packet_bytes` | CommandDispatcher | ScenarioManager, LogManager |
| `command.error` | `error, step_name` | CommandDispatcher | ScenarioManager, LogManager |
| `connection.changed` | `usv_id, state, action, reason` | SessionManager | LogManager, CLI/GUI |
| `scenario.step` | `name, status, error` | ScenarioManager | LogManager, CLI/GUI |
| `server.started` | `port` | CoreEngine | CLI/GUI |
| `server.stopped` | `reason` | CoreEngine | CLI/GUI |
| `cmw.error` | `error, command` | Cmw500Controller | CLI/GUI |

**Каналы (`channel`):**
- `"tcp"` — пакет через WiFi CMW-500 (TCP-соединение, `connection_id` есть)
- `"sms"` — пакет через SMS CMW-500 (`connection_id = None`, бо́льшие задержки)

**Типы обработчиков:**

| Тип | Параметр `ordered` | Поведение | Для чего |
|-----|-------------------|----------|----------|
| Ordered | `True` | Последовательное выполнение, один за другим | FSM (SessionManager) |
| Parallel | `False` (по умолчанию) | Параллельно через `asyncio.gather(return_exceptions=True)` | LogManager, ScenarioManager |

**Порядок выполнения:** все ordered → все parallel. Ошибка в одном parallel-хендлере не блокирует остальные.

**Требования:**
- Async-совместимый — поддержка sync и async handlers
- Ordered handlers гарантируют порядок (критично для FSM)
- Parallel handlers не блокируют друг друга
- `return_exceptions=True` в `asyncio.gather` для изоляции ошибок

---

### TcpServerManager

**Файл:** `core/tcp_server.py`

Asyncio TCP-сервер для приёма EGTS-пакетов от УСВ через WiFi CMW-500.

```python
class TcpServerManager:
    async def start(self, host: str, port: int) -> None
    async def stop(self) -> None
    async def send(self, data: bytes) -> None
```

**Поведение:**
- Принимает входящие соединения
- Читает пакеты, передаёт в PacketPipeline
- Получает RESPONSE из Pipeline, отправляет клиенту
- При разрыве — эмитит `connection.changed`

---

### Cmw500Controller

**Файл:** `core/cmw500.py`

Контроллер CMW-500 (Rohde & Schwarz) через SCPI/VISA over LAN.

```python
class Cmw500Controller:
    async def connect(self, ip: str) -> None
    async def disconnect(self) -> None
    async def send_scpi(self, command: str) -> str
    async def setup_test_mode(self, ...) -> None
    async def send_sms(self, egts_bytes: bytes) -> bool        # CMW-500 сам кодирует PDU
    async def read_sms(self) -> bytes | None                    # CMW-500 сам декодирует PDU
    async def _poll_incoming_sms(self) -> None                  # фоновый опрос → raw.packet.received
```

**Особенности:**
- Асинхронная очередь команд (избегает блокировок VISA)
- Таймаут: `CMW_SCPI_TIMEOUT` = 5 с
- Повторы: `CMW_SCPI_RETRIES` = 3
- **SMS:** CMW-500 сам кодирует/декодирует PDU — мы передаём только сырые EGTS-байты
- **SMS-приём:** фоновый опрос `READ_SMS?` каждую 1–5 с, emit `raw.packet.received` с `channel="sms"`
- **SMS-задержки:** 3–30 с отправка, таймаут транзакции 30–60 с (vs 5–10 с TCP)
- На этапе 1 — **эмулятор** (mock), реальное железо на этапе 5

---

### SessionManager + UsvConnection + UsvStateMachine

**Файл:** `core/session.py`

Управление сессиями подключений и FSM (конечный автомат) состояния УСВ.

#### SessionManager

```python
class SessionManager:
    def create_session(self, connection_id: str) -> Session
    def get_session(self, connection_id: str) -> Session | None
    def close_session(self, connection_id: str) -> None
```

#### UsvConnection

Состояние одного подключения:

```python
@dataclass
class UsvConnection:
    connection_id: str
    is_authenticated: bool = False
    term_code: str | None = None
    session_code: str | None = None
    last_packet_time: datetime | None = None
    transaction_map: dict[int, int] = field(default_factory=dict)  # PID → RPID
```

#### UsvStateMachine (FSM)

Конечный автомат состояний — **простой if/elif/else, без метаклассов/дескрипторов**.

```
                    ┌─────────────┐
                    │  NOT_AUTH   │  ← начальное
                    └──────┬──────┘
                           │ TERM_IDENTITY
                           ▼
                    ┌─────────────┐
                    │ AUTH_PENDING │
                    └──────┬──────┘
                           │ AUTH_INFO (успех)
                           ▼
                    ┌─────────────┐
                    │  AUTHORIZED │
                    └──────┬──────┘
                           │ disconnect / timeout
                           ▼
                    ┌─────────────┐
                    │  NOT_AUTH   │  ← сброс
                    └─────────────┘
```

**Переходы:**

| Из | В | Триггер | Проверка |
|----|---|---------|----------|
| `NOT_AUTH` | `AUTH_PENDING` | Получен TERM_IDENTITY | TERM_CODE не пуст |
| `AUTH_PENDING` | `AUTHORIZED` | AUTH_INFO валиден | Учётные данные верны |
| `AUTH_PENDING` | `NOT_AUTH` | AUTH_INFO неверен / таймаут 6с | — |
| `AUTHORIZED` | `NOT_AUTH` | Разрыв / таймаут / TEST_MODE_OFF | — |

**Требования:**
- FSM тестируется изолированно (без сети, CMW-500, EGTS)
- Покрыты все переходы (pytest)

---

### TransactionManager

**Файл:** `core/session.py` (или отдельный `core/transaction.py`)

Отслеживание соответствий запрос-ответ в EGTS.

```python
class TransactionManager:
    def register(self, packet_id: int) -> int  # возвращает RPID
    def confirm(self, rpid: int) -> bool
    def is_pending(self, packet_id: int) -> bool
```

**Соответствия:**
- `PID` (Packet ID) ↔ `RPID` (Response Packet ID)
- `RN` (Record Number) ↔ `CRN` (Confirm Record Number)

**Таймауты:**
- `TL_RESPONSE_TO` = 5 с — ожидание RESPONSE
- `TL_RESEND_ATTEMPTS` = 3 — повторные отправки
- `TL_RECONNECT_TO` = 30 с — переподключение

---

### ScenarioParserFactory + IScenarioParser

**Файл:** `core/scenario_parser.py`

Абстракция над форматом сценариев — аналог `IEgtsProtocol` для ГОСТ.

```python
@runtime_checkable
class IScenarioParser(Protocol):
    def load(self, data: dict) -> ScenarioMetadata: ...
    def validate(self, data: dict) -> list[str]: ...
    def get_steps(self) -> list[StepDefinition]: ...
    def get_metadata(self) -> ScenarioMetadata: ...
```

**Зачем:** Сценарии эволюционируют. V1 — `type`, `channel`, `checks`, `capture`. V2 может добавить `loops`, `conditions`, `parallel_steps`. Без абстракции добавление V2 потребует переписывания `ScenarioManager`.

**Архитектура:**

```
IScenarioParser (Protocol)
    ├── ScenarioParserV1   ← текущий формат (scenario_version: "1")
    ├── ScenarioParserV2   ← будущий формат (loops, conditions)
    └── ScenarioParserV3

ScenarioParserRegistry → register("1", V1), get("1")
ScenarioParserFactory   → читает scenario_version → создаёт парсер
ScenarioManager         → работает только с IScenarioParser
```

**ScenarioParserV1** — парсинг текущего формата:

```python
class ScenarioParserV1:
    def validate(self, data: dict) -> list[str]:
        # steps exists, type ∈ {send,expect,wait,check},
        # channel ∈ {tcp,sms,None}, capture paths valid
    def load(self, data: dict) -> ScenarioMetadata:
        # name, version, gost_version, timeout, description, channels
    def get_steps(self) -> list[StepDefinition]:
        # type, name, channel, timeout, checks, capture, packet_file, build
```

**ScenarioMetadata** — метаданные сценария:
```python
@dataclass
class ScenarioMetadata:
    name: str
    version: str          # "1", "2", ...
    gost_version: str     # "2015", "2023"
    timeout: float        # общий таймаут
    description: str | None
    channels: list[str]   # ["tcp", "sms"]
```

**StepDefinition** — нормализованное определение шага:
```python
@dataclass
class StepDefinition:
    name: str
    type: str             # send, expect, wait, check
    channel: str | None   # tcp, sms, None
    timeout: float | None
    checks: dict[str, Any]  # field → expected_value
    capture: dict[str, str]  # var_name → nested_path
    packet_file: str | None
    build: dict[str, Any] | None
    extra: dict[str, Any]   # доп. поля версии
```

**ScenarioParserRegistry** — реестр версий:
```python
class ScenarioParserRegistry:
    def register(self, version: str, parser_cls: type[IScenarioParser]) -> None
    def get(self, version: str) -> type[IScenarioParser]
    # Расширение без изменений в Factory:
    #   registry.register("2", ScenarioParserV2)
```

**ScenarioParserFactory** — создание по версии:
```python
class ScenarioParserFactory:
    def __init__(self, registry: ScenarioParserRegistry): ...
    def create(self, version: str) -> IScenarioParser: ...
    def detect_and_create(self, data: dict) -> IScenarioParser:
        # Читает data["scenario_version"] → create(version)
```

---

### ScenarioManager

**Файл:** `core/scenario.py`

Загрузка и выполнение сценариев из scenario.json через `ScenarioParserFactory`.

**Важно:** `ScenarioManager` **не парсит JSON напрямую**. Он делегирует парсинг factory:

```python
class ScenarioManager:
    def __init__(self, bus: EventBus, parser_factory: ScenarioParserFactory,
                 step_factory: StepFactory): ...

    def load(self, path: Path) -> None:
        data = json.loads(path.read_text())
        parser = self._parser_factory.detect_and_create(data)
        errors = parser.validate(data)
        if errors:
            raise ScenarioValidationError(errors)
        self._metadata = parser.load(data)
        self._steps = parser.get_steps()

    async def execute(self) -> ScenarioResult: ...
```

**Структура сценария (V1, JSON):**

```json
{
  "name": "Передача профиля ускорения",
  "scenario_version": "1",
  "gost_version": "ГОСТ 33465-2015",
  "timeout": 60,
  "description": "Платформа запрашивает профиль ускорения через SMS",
  "channels": ["tcp", "sms"],
  "steps": [
    {
      "name": "SMS-запрос профиля ускорения",
      "type": "send",
      "channel": "sms",
      "packet_file": "packets/platform/accel_data_request.hex",
      "timeout": 10
    },
    {
      "name": "Данные профиля ускорения",
      "type": "expect",
      "channel": "tcp",
      "checks": {"service": 2, "subrecord_type": "EGTS_SR_ACCEL_DATA"},
      "capture": {"accel_points_count": "data.points_count"},
      "timeout": 30
    }
  ]
}
```

**StepFactory:**

```python
class StepFactory:
    def create_step(self, step_def: StepDefinition) -> Step:
        # type="send" → SendStep
        # type="expect" → ExpectStep
        # type="wait" → WaitStep
        # type="check" → CheckStep
```

**Добавление новой версии формата (V2):**
1. Создать `ScenarioParserV2(IScenarioParser)`
2. `registry.register("2", ScenarioParserV2)`
3. **Никаких изменений в ScenarioManager**

---

### PacketPipeline

**Файл:** `core/pipeline.py`

Middleware-конвейер обработки входящих пакетов (TCP и SMS).

```
Входящий байт-поток (raw)
        │
        ▼
┌──────────────┐
│ CRC Check    │  → проверка CRC-8 заголовка + CRC-16 тела
└──────┬───────┘
       ▼
┌──────────────┐
│ Parse        │  → десериализация EGTS-пакета → ParseResult
└──────┬───────┘
       ▼
┌──────────────┐
│ AutoResponse │  → RESPONSE для успешных пакетов (order=3)
└──────┬───────┘
       ▼
┌──────────────┐
│ Duplicate    │  → отсев дубликатов (по PID из UsvConnection)
└──────┬───────┘
       ▼
┌──────────────┐
│ Transaction  │  → PID↔RPID, RN↔CRN маппинг
└──────┬───────┘
       ▼
┌──────────────┐
│ Event Emit   │  → packet.processed в EventBus (ВСЕГДА, даже terminated)
└──────────────┘
        │
        ▼
  EventBus.emit("packet.processed")
```

**Middleware:**

```python
class Middleware(Protocol):
    async def process(self, ctx: PacketContext, next: Callable) -> None

class PacketPipeline:
    def add(self, mw: Middleware, order: int) -> None
    async def process(self, raw: bytes, channel: str, connection_id: str | None) -> PacketContext
```

**Channel-агностицизм:** Pipeline обрабатывает TCP и SMS одинаково — различие только в `channel` и `connection_id` в контексте.

---

### LogManager

**Файл:** `core/logger.py`

Подписчик на события EventBus. Логирует **100% пакетов**.

```python
class LogManager:
    def __init__(self, event_bus: EventBus, log_dir: str) -> None
    # Подписка: event_bus.subscribe("packet.received", self.on_packet)
```

**Формат записи:**

```
[2026-04-06 14:32:01.123] PACKET RECEIVED
  Source: tcp
  Hex:    0102030405...
  Parsed: {PR: 0x10, HL: 0x00, PID: 1, PN: 5, ...}
  CRC:    OK
  Session: auth_pending
```

**Требования:**
- 100% пакетов (включая CRC-ошибки)
- Hex + parsed представление
- Раздельные логи по сессиям
- Вывод в файл + консоль (опционально)

---

### CredentialsRepository

**Файл:** `core/credentials.py`

JSON-хранилище учётных данных (TERM_CODE, пароли, сертификаты).

```python
class CredentialsRepository:
    def __init__(self, path: str) -> None  # config/credentials.json
    def get(self, device_id: str) -> Credentials | None
    def save(self, device_id: str, creds: Credentials) -> None
    def list_all(self) -> dict[str, Credentials]
```

**Без ORM** — прямой JSON-файл.

---

### Export

**Файл:** `core/export.py`

Выгрузка результатов тестирования.

```python
class ExportManager:
    async def export_csv(self, results: list[TestResult], path: str) -> None
    async def export_json(self, results: list[TestResult], path: str) -> None
    async def export_der(self, results: list[TestResult], path: str) -> None
```

**Форматы:**
- CSV — таблица шагов (step, status, время, детали)
- JSON — полный результат с пакетами
- DER — ASN.1-отчёт (для eCall/MSD)

---

### Config

**Файл:** `core/config.py`

Загрузка и валидация конфигурации. Структура **вложенная** (nested dataclass'ы) — 1:1 с `settings.json`.

```python
@dataclass(frozen=True)
class CmwConfig:
    ip: str | None = None
    timeout: float = 5.0
    retries: int = 3
    sms_send_timeout: float = 10.0
    status_poll_interval: float = 2.0

@dataclass(frozen=True)
class TimeoutsConfig:
    tl_response_to: float = 5.0
    tl_resend_attempts: int = 3
    tl_reconnect_to: float = 30.0
    egts_sl_not_auth_to: float = 6.0

@dataclass(frozen=True)
class LogConfig:
    level: str = "INFO"
    dir: str = "logs"
    rotation: str = "daily"
    max_size_mb: int = 100
    retention_days: int = 30

@dataclass(frozen=True)
class Config:
    gost_version: str = "2015"
    tcp_host: str = "0.0.0.0"
    tcp_port: int = 8090
    cmw500: CmwConfig = field(default_factory=CmwConfig)
    timeouts: TimeoutsConfig = field(default_factory=TimeoutsConfig)
    logging: LogConfig = field(default_factory=LogConfig)
    credentials_path: str = "config/credentials.json"

    @classmethod
    def from_file(cls, path: str) -> Config: ...
    def merge_with_cli(self, cli_args: dict[str, Any]) -> Config: ...
```

**Использование:**
```python
config = Config.from_file("config/settings.json")
config = config.merge_with_cli({"tcp_port": 9090})
print(config.cmw500.timeout)       # 5.0
print(config.timeouts.tl_response_to)  # 5.0
```

**Приоритеты:** CLI args > settings.json > defaults.
**CLI merge:** dot-notation — `"cmw500.timeout": 10` → `config.cmw500.timeout = 10`.
**Валидация:** `__post_init__` — порт 1–65535, таймауты > 0, retries >= 0.

---

## Пакет EGTS — структура

### Транспортный уровень (TL)

```
┌─────┬─────┬──────────┬──────────┬──────────┬──────────┬──────┐
│ PR  │ HL  │ ADDR(опц)│ CID(опц) │ PN(опц)  │ RP(опц)  │ Body │
└─────┴─────┴──────────┴──────────┴──────────┴──────────┴──────┘
                                                              │
                                                          CRC-16
```

| Поле | Размер | Описание |
|------|--------|----------|
| PR | 1 байт | Признаки обработки (prio, archive, compress, reroute, ack, reply) |
| HL | 1 байт | Длина дополнительного заголовка |
| ADDR | вар. | Адрес (тип + значение) |
| CID | 2 байта | Идентификатор соединения |
| PN | 2 байта | Номер пакета |
| RP | 2 байта | Номер подтверждаемого пакета |
| Body | вар. | Сервисные данные |
| CRC-16 | 2 байта | Контрольная сумма |

### Сервисный уровень (SL)

| Тип сообщения | Код | Описание |
|---------------|-----|----------|
| TERM_IDENTITY | 1 | Идентификация терминала |
| AUTH_PARAMS | 2 | Запрос параметров аутентификации |
| AUTH_INFO | 3 | Данные аутентификации |
| RESULT_CODE | 4 | Результат авторизации |
| NAV_DATA | 10 | Навигационные данные |
| TRACK_DATA | 11 | Данные траектории |
| ACCEL_DATA | 12 | Профиль ускорения |
| RAW_MSD_DATA | 13 | MSD (eCall) |
| SERVICE_PART_DATA | 20 | Часть ПО |
| SERVICE_FULL_DATA | 21 | Полный образ ПО |
| COMMAND_DATA | 30 | Команда |
| TEST_MODE_ON | 40 | Включить режим тестирования |
| TEST_MODE_OFF | 41 | Выключить режим тестирования |

---

## Связи компонентов

```
TcpServerManager  ──emit──► EventBus ◄──emit── Cmw500Controller
        │                          │                     │
     пакет в                   packet.received        sms_event
        │                          │
        ▼                          ▼
  PacketPipeline            SessionManager
        │                          │
     processed                  FSM transition
        │                          │
        ▼                          ▼
     emit event              UsvConnection (обновление)
                                      │
                                      ▼
                                LogManager (подписан на все)
```

**Запрещено:**
- TcpServer → Session (напрямую)
- Pipeline → LogManager (напрямую)
- Scenario → TcpServer (напрямую)

**Разрешено:**
- Только через EventBus.emit() / EventBus.subscribe()

---

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Язык | Python >= 3.12 |
| Асинхронность | asyncio |
| TCP | asyncio.start_server |
| CMW-500 | PyVISA (SCPI/VISA over LAN) |
| CLI | argparse + cmd (REPL) |
| GUI (потом) | PyQt6 или PySide6 |
| Тесты | pytest |
| Линтер | ruff |
| Типизация | mypy |
| Покрытие | pytest-cov, ≥ 90% |

---

## Библиотека EGTS-протокола

### Общая схема

```
libs/
├── egts_protocol_iface/           ← Абстрактный интерфейс (ядро зависит только от этого)
│   ├── __init__.py                │  IEgtsProtocol (Protocol), create_protocol()
│   ├── models.py                  │  Packet, Record, Subrecord, ParseResult (dataclass)
│   └── types.py                   │  Enums, константы (таймауты, CRC, размеры)
│
└── egts_protocol_gost2015/        ← Реализация ГОСТ 33465-2015
    ├── __init__.py                │  Публичный API: EgtsProtocol2015, crc8/16
    ├── adapter.py                 │  Маппинг gost2015_impl ↔ iface (IEgtsProtocol)
    └── gost2015_impl/             │  Внутренняя реализация (копии из EGTS_GUI)
        ├── crc.py                 │  CRC-8/CRC-16 (чистый Python, без зависимостей)
        ├── sms.py                 │  SMS PDU: create/parse, конкатенация, SMSReassembler
        ├── packet.py              │  Парсинг/сборка транспортного пакета
        ├── record.py              │  Парсинг/сборка записей ППУ
        ├── subrecord.py           │  Парсинг/сборка подзаписей
        ├── types.py               │  Все enums и константы ГОСТ
        └── services/              │  Сервисная логика
            ├── auth.py            │  Авторизация: TERM_IDENTITY, RESULT_CODE, ...
            ├── commands.py        │  Команды: COMMAND_DATA, подтверждения
            ├── ecall.py           │  eCall: RAW_MSD_DATA, TRACK_DATA, ACCEL_DATA
            └── firmware.py        │  Обновление ПО: SERVICE_PART_DATA, ODH
```

### Принципы

1. **Ядро зависит только от `egts_protocol_iface/`** — не знает о реализации
2. **Адаптер** (`adapter.py`) маппит внутренние модели → iface-модели
3. **`gost2015_impl/`** — копии из EGTS_GUI, адаптированные под архитектуру OMEGA_EGTS
4. **CRC** — чистая Python-реализация, без внешних зависимостей (`crcmod` не нужен)
5. **SMS PDU** — полный стек: создание, парсинг, конкатенация, сборка фрагментов

### IEgtsProtocol — интерфейс

```python
class IEgtsProtocol(Protocol):
    def parse_packet(self, data: bytes, **kwargs) -> ParseResult: ...
    def build_response(self, pid: int, result_code: int, **kwargs) -> bytes: ...
    def build_record_response(self, crn: int, rst: int, **kwargs) -> bytes: ...
    def build_packet(self, packet: Packet, **kwargs) -> bytes: ...
    def build_sms_pdu(self, egts_bytes: bytes, destination: str, **kwargs) -> bytes: ...
    def parse_sms_pdu(self, pdu: bytes, **kwargs) -> bytes: ...
    def validate_crc8(self, header: bytes, expected: int, **kwargs) -> bool: ...
    def validate_crc16(self, data: bytes, expected: int, **kwargs) -> bool: ...
    def calculate_crc8(self, data: bytes, **kwargs) -> int: ...
    def calculate_crc16(self, data: bytes, **kwargs) -> int: ...
    @property
    def version(self) -> str: ...
    @property
    def capabilities(self) -> set[str]: ...
```

**`**kwargs`** — для расширяемости. Новые версии ГОСТ (2023) добавляют параметры без изменения сигнатуры.

### Factory

```python
from libs.egts_protocol_iface import create_protocol

protocol = create_protocol("2015")   # EgtsProtocol2015
protocol = create_protocol("2023")   # NotImplementedError (будет позже)
```

---

## Структура кода

```
egts-tester/
├── pyproject.toml
├── core/                          # ЕДИНОЕ ЯДРО
│   ├── engine.py                  # CoreEngine
│   ├── config.py                  # Config
│   ├── event_bus.py               # EventBus
│   ├── tcp_server.py              # TcpServerManager
│   ├── cmw500.py                  # Cmw500Controller
│   ├── session.py                 # SessionManager + UsvConnection + FSM + TransactionManager
│   ├── scenario.py                # ScenarioManager + StepFactory + ExpectStep + SendStep
│   ├── scenario_parser.py         # IScenarioParser + V1 + Registry + Factory
│   ├── packet_source.py           # Загрузка/генерация пакетов
│   ├── pipeline.py                # PacketPipeline + Middleware
│   ├── logger.py                  # LogManager
│   ├── credentials.py             # CredentialsRepository
│   └── export.py                  # Выгрузка данных
├── libs/
│   ├── egts_protocol_iface/       # Абстрактный интерфейс (IEgtsProtocol)
│   └── egts_protocol_gost2015/    # Реализация ГОСТ 33465-2015
│       ├── adapter.py             # Маппинг gost2015_impl ↔ iface
│       └── gost2015_impl/         # Парсер, сборщик, CRC, SMS, сервисы
├── cli/app.py                     # CLI приложение
├── scenarios/                     # Готовые сценарии (JSON + HEX)
├── config/                        # settings.json, credentials.json
└── tests/                         # pytest
    ├── conftest.py                # Shared fixtures
    ├── core/
    │   ├── test_event_bus.py      # ✅ EventBus (14 тестов, 100% coverage)
    │   ├── test_config.py         # ✅ Config (28 тестов, 91% coverage)
    │   ├── test_engine.py         # ✅ CoreEngine (6 тестов, 100% coverage)
    │   └── ...
    └── libs/
        ├── egts_protocol_iface/   # ✅ iface (73 теста, 100% coverage)
        └── egts_protocol_gost2015/ # ✅ адаптер (59 тестов)
```
