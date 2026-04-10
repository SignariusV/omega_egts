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
│  │  10 событий: raw.packet.received │ packet.processed │      │  │
│  │  command.send │ command.sent │ command.error │             │  │
│  │  connection.changed │ scenario.step │                      │  │
│  │  server.started │ server.stopped │ cmw.error               │  │
│  └───┬──────────┬──────────┬──────────┬──────────┬───────────┘  │
│      │          │          │          │          │              │
│ ┌────▼─────┐ ┌──▼──────┐ ┌─▼───────┐ ┌▼────────┐ ┌▼─────────┐ │
│ │TcpServer │ │Cmw500   │ │Session  │ │Scenario │ │Packet    │ │
│ │Manager   │ │Ctrl     │ │Manager  │ │Manager  │ │Pipeline  │ │
│ └────┬─────┘ └──┬──────┘ └─────────┘ └─────────┘ └──────────┘ │
│      │          │          ┌──────────────┐  ┌──────────────┐  │
│      │          │          │UsvConnection │  │Transaction   │  │
│      │          │          │+ FSM         │  │Manager       │  │
│      │          │          └──────────────┘  └──────────────┘  │
│ ┌────▼──────────▼─────┐  ┌──────────────┐  ┌──────────────┐   │
│ │PacketDispatcher     │  │Command       │  │ScenarioParser│   │
│ │(CRC→Parse→AutoResp→ │  │Dispatcher    │  │Factory + V1  │   │
│ │ Dedup→EventEmit)    │  │(TCP + SMS)   │  │+ Registry    │   │
│ └─────────────────────┘  └──────────────┘  └──────────────┘   │
│ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ ┌───────────┐  │
│ │LogManager   │ │Credentials  │ │ReplaySource│ │Export     │  │
│ │             │ │Repository   │ │            │ │(функции)  │  │
│ └─────────────┘ └─────────────┘ └────────────┘ └───────────┘  │
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

**Файл:** `core/tcp_server.py` | **Статус:** ✅ Реализован (итерация 5.1)

Asyncio TCP-сервер для приёма EGTS-пакетов от УСВ через WiFi CMW-500.

```python
class TcpServerManager:
    async def start(self, host: str, port: int) -> None
    async def stop(self) -> None
```

**Поведение:**
- Принимает входящие соединения (`asyncio.start_server`)
- Читает пакеты (длина заголовка + тело)
- Эмитит `raw.packet.received` с `channel="tcp"`, `connection_id`
- При подключении/отключении — эмитит `connection.changed`
- RESPONSE отправляется обратно через `writer.write()` (из CommandDispatcher/Pipeline)

---

### Cmw500Controller

**Файл:** `core/cmw500.py` | **Статус:** ✅ Реализован (итерация 5.2)

Контроллер CMW-500 (Rohde & Schwarz) через SCPI/VISA over LAN.

```python
@dataclass
class CmwCommand:
    name: str
    scpi_template: str
    timeout: float = 5.0
    retry_count: int = 3
    retry_delay: float = 1.0
    def format(self, *args: object, **kwargs: object) -> str

# Предопределённые команды:
GET_IMEI = CmwCommand("GET_IMEI", "CMW:GSM:SIGN:CONN:ID?")
GET_IMSI = CmwCommand("GET_IMSI", "CMW:GSM:SIGN:CONN:IMSI?")
GET_RSSI = CmwCommand("GET_RSSI", "CMW:GSM:SIGN:CONN:RSSI?")
GET_STATUS = CmwCommand("GET_STATUS", "CMW:GSM:SIGN:CONN:STAT?")
SEND_SMS  = CmwCommand("SEND_SMS", "CMW:GSM:SIGN:SMS:SEND '{egts_hex}'",
                       timeout=30.0)
READ_SMS  = CmwCommand("READ_SMS", "CMW:GSM:SIGN:SMS:READ?",
                       timeout=5.0, retry_count=0)


class Cmw500Controller:
    async def connect(self) -> None
    async def disconnect(self) -> None

    async def execute(self, command: CmwCommand, *args: object) -> str

    # Удобные обёртки:
    async def get_imei(self) -> str
    async def get_imsi(self) -> str
    async def get_rssi(self) -> str
    async def get_status(self) -> str

    # SMS:
    async def send_sms(self, egts_bytes: bytes) -> bool   # CMW-500 сам кодирует PDU
    async def read_sms(self) -> bytes | None               # CMW-500 сам декодирует PDU

    # Protected (для внутреннего использования):
    async def _send_scpi(self, scpi: str) -> str           # базовая отправка SCPI
    async def _poll_incoming_sms(self) -> None             # фоновый опрос → raw.packet.received
    async def _worker_loop(self) -> None                   # обработка очереди команд
    async def _execute_with_retry(self, command: CmwCommand, *args) -> str
```

**Особенности:**
- **Очередь команд:** `asyncio.Queue` — все команды выполняются последовательно через worker-цикл
- **Retry:** `_execute_with_retry` — экспоненциальная задержка, `CMW_SCPI_RETRIES = 3`
- **Таймауты:** `CMW_SCPI_TIMEOUT = 5 с`, SMS-команды — 30 с
- **SMS-отправка:** CMW-500 сам кодирует PDU — мы передаём только сырые EGTS-байты
- **SMS-приём:** фоновый опрос `READ_SMS?` каждую 1–5 с, emit `raw.packet.received` с `channel="sms"`
- **SMS-задержки:** 3–30 с отправка, таймаут транзакции 30–60 с (vs 5–10 с TCP)
- На этапе 1 — **эмулятор** (`Cmw500Emulator`), реальное железо на этапе 5

---

### SessionManager + UsvConnection + UsvStateMachine

**Файл:** `core/session.py` | **Статус:** ✅ Реализован (итерация 3.1–3.4)

Управление сессиями подключений и FSM (конечный автомат) состояния УСВ.

#### SessionManager

```python
class SessionManager:
    def __init__(self, bus: EventBus, gost_version: str = "2015") -> None

    def create_session(self, connection_id: str, remote_ip: str,
                       remote_port: int, reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter, protocol: IEgtsProtocol,
                       is_std_usv: bool = True) -> UsvConnection

    def get_session(self, connection_id: str) -> UsvConnection | None
    async def close_session(self, connection_id: str) -> None
    # Подписка: bus.on("packet.processed", self._on_packet_processed, ordered=True)
```

**`_on_packet_processed`:** Обновляет FSM (`on_packet`), сохраняет TID/IMEI/IMSI из parsed пакета, эмитит `connection.changed` при смене состояния.

#### UsvConnection

Состояние одного подключения:

```python
@dataclass
class UsvConnection:
    connection_id: str                # Уникальный ID подключения
    remote_ip: str                    # IP клиента
    remote_port: int                  # Порт клиента
    reader: asyncio.StreamReader | None
    writer: asyncio.StreamWriter | None
    fsm: UsvStateMachine | None       # Конечный автомат
    protocol: IEgtsProtocol | None    # EGTS-протокол
    transaction_mgr: TransactionManager | None
    tid: int | None                   # Terminal ID
    imei: str | None                  # IMEI устройства
    imsi: str | None                  # IMSI SIM-карты
    next_pid: int = 0                 # Следующий Packet ID
    next_rn: int = 0                  # Следующий Record Number
    _seen_pids: OrderedDict[int, bytes]  # LRU-кэш дубликатов (MAX=65536)

    def add_pid_response(self, pid: int, response: bytes) -> None  # кешировать RESPONSE
    def get_response(self, pid: int) -> bytes | None               # получить из кэша
    @property
    def usv_id(self) -> str  # str(tid) если есть, иначе connection_id
```

**LRU-кэш дубликатов:** `OrderedDict` с eviction по `MAX_SEEN_PIDS = 65536`. При повторном обращении PID перемещается в конец (MRU).

#### UsvStateMachine (FSM)

Конечный автомат состояний — **простой if/elif/else, без метаклассов/дескрипторов**.

**7 состояний:**

| Состояние | Значение | Описание | Таймаут |
|-----------|----------|----------|---------|
| `DISCONNECTED` | `"disconnected"` | Нет TCP-соединения | — |
| `CONNECTED` | `"connected"` | TCP установлен, ждём первый пакет | 6 с (`EGTS_SL_NOT_AUTH_TO`) |
| `AUTHENTICATING` | `"authenticating"` | Получен TERM_IDENTITY, идёт авторизация | 5 с × 3 (`TL_RESPONSE_TO`) |
| `CONFIGURING` | `"configuring"` | TID=0, ждём повторную авторизацию | 5 с × 3 (`TL_RESPONSE_TO`) |
| `AUTHORIZED` | `"authorized"` | RESULT_CODE(0) отправлен, ждём данные | 5 с × 3 (`TL_RESPONSE_TO`) |
| `RUNNING` | `"running"` | Основной режим — обмен данными | 5 с × 3 (`TL_RESPONSE_TO`) |
| `ERROR` | `"error"` | Критическая ошибка протокола | — |

```
                     on_connect()
                  ┌────────────────────┐
                  │                    │
                  ▼                    │
┌──────────────────────────┐           │
│      DISCONNECTED        │◄──────────┤ on_disconnect() / timeout / error
│   (нет соединения)       │           │
└────────────┬─────────────┘           │
             │ service=1               │
             ▼                         │
┌──────────────────────────┐           │
│       CONNECTED          │           │
│  (ждём первый пакет)     │           │
└──────┬───────┬───────────┘           │
       │       │ service=10            │
       │       │ is_std_usv            │
       │       ▼                       │
       │  ┌──────────────────┐         │
       │  │    RUNNING       │◄────────┤ service!=1
       │  └──────┬───────────┘         │
       │         │ service=1           │
       │         ▼                     │
       │  ┌──────────────────┐         │
       └─►│  AUTHENTICATING  │         │
          │  (TERM_IDENTITY) │         │
          └──┬────┬────┬─────┘         │
             │    │    │               │
        RC=0 │ RC=153│ RST≠0          │
             │    │    │               │
             ▼    ▼    ▼               │
      ┌──────────┬──────────┐          │
      │AUTHORIZED│CONFIGURING│───┐     │
      └─────┬────┴───────────┘   │     │
            │ service=1          │     │
            ▼   service=1        │     │
      ┌──────────────────┐       │     │
      │   AUTHENTICATING │───────┘     │
      └──────────────────┘             │
                                       │
            on_error() ───────────────►┌──────────────┐
            (из любого)                │    ERROR     │
                                       └──────┬───────┘
                                              │ on_disconnect()
                                              ▼
                                       ┌──────────────┐
                                       │ DISCONNECTED │
                                       └──────────────┘
```

**Все 18 переходов:**

| # | Из | В | Триггер | Условие |
|---|----|---|---------|---------|
| 1 | `DISCONNECTED` | `CONNECTED` | `on_connect()` | TCP-соединение установлено |
| 2 | `CONNECTED` | `AUTHENTICATING` | `on_packet` | `service == 1` (TERM_IDENTITY) |
| 3 | `CONNECTED` | `RUNNING` | `on_packet` | `service == 10` и `is_std_usv` |
| 4 | `CONNECTED` | `DISCONNECTED` | `on_timeout` | 6 с без TERM_IDENTITY |
| 5 | `AUTHENTICATING` | `AUTHORIZED` | `on_result_code_sent(0)` | Авторизация успешна |
| 6 | `AUTHENTICATING` | `CONFIGURING` | `on_result_code_sent(153)` | TID=0, режим конфигурирования |
| 7 | `AUTHENTICATING` | `DISCONNECTED` | `on_result_code_sent(!0, !153)` | Ошибка авторизации |
| 8 | `AUTHENTICATING` | `DISCONNECTED` | `on_packet` | RECORD_RESPONSE, RST≠0 |
| 9 | `AUTHENTICATING` | `DISCONNECTED` | `on_timeout` | 5 с × 3 попыток |
| 10 | `CONFIGURING` | `AUTHENTICATING` | `on_packet` | `service == 1` и `TID > 0` |
| 11 | `CONFIGURING` | `DISCONNECTED` | `on_timeout` | 5 с × 3 попыток |
| 12 | `AUTHORIZED` | `RUNNING` | `on_packet` | `service != 1` |
| 13 | `AUTHORIZED` | `AUTHENTICATING` | `on_packet` | `service == 1` (переавторизация) |
| 14 | `AUTHORIZED` | `DISCONNECTED` | `on_timeout` | 5 с × 3 попыток |
| 15 | `RUNNING` | `AUTHENTICATING` | `on_packet` | `service == 1` (переавторизация) |
| 16 | `RUNNING` | `DISCONNECTED` | `on_timeout` | 5 с × 3 попыток |
| 17 | Любое (кроме `DISCONNECTED`) | `ERROR` | `on_error()` / `on_operator_command` | Критическая ошибка |
| 18 | Любое | `DISCONNECTED` | `on_disconnect()` | TCP разорван |

**Требования:**
- FSM тестируется изолированно (без сети, CMW-500, EGTS)
- Покрыты все 18 переходов (pytest)

---

### TransactionManager

**Файл:** `core/session.py` | **Статус:** ✅ Реализован (итерация 3.2)

Отслеживание соответствий запрос-ответ в EGTS.

```python
@dataclass
class PendingTransaction:
    pid: int | None           # Packet ID запроса
    rn: int | None            # Record Number запроса
    step_name: str            # Имя шага сценария
    timeout: float            # Таймаут (по умолчанию TL_RESPONSE_TO = 5 с)
    created_at: float         # Время создания (time.time)

    @property
    def is_expired(self) -> bool: ...  # (time.time() - created_at) > timeout


class TransactionManager:
    def __init__(self) -> None
    def register(self, pid: int | None = None, rn: int | None = None,
                 step_name: str = "", timeout: float = TL_RESPONSE_TO) -> None
    def match_response(self, rpid: int | None = None,
                       crn: int | None = None) -> PendingTransaction | None
    def cleanup_expired(self) -> list[PendingTransaction]
```

**Соответствия:**
- `PID` (Packet ID) ↔ `RPID` (Response Packet ID)
- `RN` (Record Number) ↔ `CRN` (Confirm Record Number)

**Алгоритм `match_response`:** Сначала ищет по `rpid` в `_by_pid`, затем по `crn` в `_by_rn`. Найденную транзакцию удаляет из обоих словарей.

**`cleanup_expired`:** Удаляет все транзакции с `is_expired == True`, чистит оба словаря. Вызывается из сценариев перед ожиданием.

**Таймауты:**
- `TL_RESPONSE_TO` = 5 с — ожидание RESPONSE
- `TL_RESEND_ATTEMPTS` = 3 — повторные отправки
- `TL_RECONNECT_TO` = 30 с — переподключение

---

### ScenarioParserFactory + IScenarioParser

**Файл:** `core/scenario_parser.py` | **Статус:** ✅ Реализован (итерация 7.0)

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

**Файл:** `core/scenario.py` | **Статус:** ✅ Реализован (итерация 7.1–7.4)

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

**Файл:** `core/pipeline.py` | **Статус:** ✅ Реализован (итерация 4.1–4.5)

Middleware-конвейер обработки входящих пакетов (TCP и SMS).

```
Входящий байт-поток (raw)
        │
        ▼
┌──────────────┐
│ CRC Check    │  order=1 → проверка CRC-8 заголовка + CRC-16 тела
└──────┬───────┘
       ▼
┌──────────────┐
│ Parse        │  order=2 → десериализация EGTS → ParseResult
└──────┬───────┘
       ▼
┌──────────────┐
│ Dedup        │  order=2.5 → отсев дубликатов по PID из кэша UsvConnection
└──────┬───────┘
       ▼
┌──────────────┐
│ AutoResponse │  order=3 → RESPONSE для успешных + кеш в UsvConnection
└──────┬───────┘
       ▼
┌──────────────┐
│ Event Emit   │  order=5 → packet.processed в EventBus (ВСЕГДА, даже terminated)
└──────────────┘
        │
        ▼
  EventBus.emit("packet.processed")
```

**Порядок в `_build_pipeline()` (dispatcher.py):**

```python
def _build_pipeline(self) -> PacketPipeline:
    p = PacketPipeline()
    p.add("crc",      CrcValidationMiddleware(session_mgr),   order=1)
    p.add("parse",    ParseMiddleware(session_mgr),            order=2)
    p.add("dedup",    DuplicateDetectionMiddleware(session_mgr), order=2.5)
    p.add("auto_resp", AutoResponseMiddleware(session_mgr),   order=3)
    p.add("emit",     EventEmitMiddleware(bus),                order=5)
    return p
```

**Почему Dedup перед AutoResponse:** AutoResponse формирует RESPONSE и добавляет
PID в кэш `_seen_pids`. Если Dedup идёт после — он находит этот же PID и помечает
первый пакет как дубликат. Dedup должен проверить кэш _до_ того как AutoResponse
его заполнит.

**PacketContext (данные конвейера):**

```python
@dataclass
class PacketContext:
    raw: bytes                      # Сырые байты (не изменяется)
    connection_id: str              # ID подключения (None для SMS)
    channel: str = "tcp"            # "tcp" или "sms"
    parsed: ParseResult | None = None
    crc8_valid: bool = False
    crc16_valid: bool = False
    crc_valid: bool = False         # crc8_valid and crc16_valid
    is_duplicate: bool = False
    response_data: bytes | None = None  # RESPONSE для отправки
    terminated: bool = False        # Прервать цепочку
    errors: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.monotonic)
```

**Middleware (Protocol):**

```python
class Middleware(Protocol):
    async def __call__(self, ctx: PacketContext) -> None

class PacketPipeline:
    def add(self, name: str, mw: Middleware, order: int) -> None
    async def process(self, raw: bytes, channel: str,
                      connection_id: str | None = None) -> PacketContext
```

**Особенности:**
- **AutoResponse (order=3)** не ставит `terminated` — обработка продолжается
- **Dedup (order=4)** ставит `terminated=True` при обнаружении дубликата
- **EventEmit (order=5)** вызывается **всегда** — даже при `terminated=True` (100% логирование)
- TransactionManager **не является middleware** — транзакции регистрируются в CommandDispatcher
- **Channel-агностицизм:** Pipeline обрабатывает TCP и SMS одинаково

**Таблица middleware:**

| # | Middleware | Order | terminated при ошибке | Описание |
|---|-----------|-------|----------------------|----------|
| 1 | `CrcValidationMiddleware` | 1 | Да (CRC mismatch) | Проверка CRC-8 + CRC-16 |
| 2 | `ParseMiddleware` | 2 | Да (ошибка парсинга) | Десериализация EGTS |
| 3 | `AutoResponseMiddleware` | 3 | Нет | Формирует RESPONSE, кеширует |
| 4 | `DuplicateDetectionMiddleware` | 4 | Да (дубликат) | Сверяет PID с кэшем |
| 5 | `EventEmitMiddleware` | 5 | Нет | Emit `packet.processed` (всегда) |

---

### LogManager

**Файл:** `core/logger.py` | **Статус:** ✅ Реализован (итерация 6.1)

Подписчик на события EventBus. Логирует **100% пакетов** в JSONL.

```python
class LogManager:
    def __init__(self, bus: EventBus, log_dir: str) -> None
    # Подписки:
    #   bus.on("packet.processed", self._on_packet, ordered=False)
    #   bus.on("connection.changed", self._on_connection, ordered=False)
    #   bus.on("scenario.step", self._on_scenario_step, ordered=False)
    #   bus.on("command.sent", self._on_command, ordered=False)
    #   bus.on("command.error", self._on_command_error, ordered=False)
```

**Формат записи (JSONL):**
```json
{"timestamp": "2026-04-10T14:32:01.123", "log_type": "packet",
 "crc_valid": true, "is_duplicate": false, "hex": "010000...",
 "parsed": {"packet_id": 27, "service": 1}, "channel": "tcp"}
```

**Особенности:**
- 100% пакетов (включая CRC-ошибки, дубликаты)
- JSONL формат (по одному JSON-объекту на строку)
- Daily rotation — один файл в день: `logs/2026-04-10.jsonl`
- Буферизация + сортировка по timestamp (CR-002)

---

### CredentialsRepository

**Файл:** `core/credentials.py` | **Статус:** ✅ Реализован (итерация 6.2)

JSON-хранилище учётных данных (TERM_CODE, пароли, сертификаты).

```python
@dataclass
class Credentials:
    device_id: str        # IMEI или уникальный идентификатор
    term_code: str        # Код терминала
    # ... дополнительные поля

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> Credentials: ...


class CredentialsRepository:
    def __init__(self, path: Path | str) -> None
    def find_by_imei(self, imei: str) -> Credentials | None
    def get(self, device_id: str) -> Credentials | None
    def save(self, creds: Credentials) -> None  # ключ = creds.device_id
    def list_all(self) -> dict[str, Credentials]
```

**Особенности:**
- Без ORM — прямой JSON-файл (`config/credentials.json`)
- Защита файла: `chmod 600` на Unix, ACL warning на Windows
- `save()` использует `creds.device_id` как ключ (без рассинхронизации)

---

### Export

**Файл:** `core/export.py` | **Статус:** ✅ Реализован (итерация 8.2)

Выгрузка результатов тестирования — **standalone-функции** (без классов).

```python
def export_csv(log_dir: Path | str, output_path: Path | str,
               *, log_type_filter: str | None = None,
               scenario_name_filter: str | None = None) -> dict[str, Any]:
    """Экспорт всех JSONL-логов в CSV-таблицу. Возвращает {"exported": int, "output": str}."""

def export_json(log_dir: Path | str, output_path: Path | str,
                *, log_type_filter: str | None = None,
                scenario_name_filter: str | None = None) -> dict[str, Any]:
    """Экспорт логов в JSON со сводкой (total, by_type)."""

def export_scenario_results_csv(result: dict[str, Any],
                                output_path: Path | str) -> int:
    """Экспорт шагов сценария в CSV. Возвращает кол-во шагов."""

def export_scenario_results_json(result: dict[str, Any],
                                 output_path: Path | str) -> None:
    """Экспорт результатов сценария в JSON."""
```

**Форматы:**
- CSV — таблица шагов (step, status, время, детали)
- JSON — полный результат с пакетами + сводка
- ~~DER~~ — не реализован (ASN.1-отчёт для eCall/MSD отложен)

---

### ReplaySource

**Файл:** `core/packet_source.py` | **Статус:** ✅ Реализован (итерация 8.1)

Загрузка лога пакетов и повторная обработка (offline-анализ).

```python
class ReplaySource:
    def __init__(self, bus: EventBus, log_file: Path | str,
                 pipeline: PacketPipeline | None = None,
                 skip_duplicates: bool = True) -> None

    async def load(self) -> list[dict[str, Any]]
    async def replay(self) -> dict[str, Any]
```

**Как работает `replay()`:**
1. Загружает JSONL-файл, отбирает записи с `log_type='packet'`
2. Пропускает дубликаты если `skip_duplicates=True` и `is_duplicate=True`
3. Конвертирует hex → bytes, создаёт `PacketContext`
4. Прогоняет через `pipeline.process()` (если pipeline задан)
5. Эмитит `packet.processed` для каждого пакета
6. Возвращает `{"processed": int, "skipped_duplicates": int, "errors": [...]}`

**Использование:** Offline-анализ сохранённых логов, воспроизведение багов, регрессионное тестирование.

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
TcpServerManager ──emit──► EventBus ◄──emit── Cmw500Controller
   (raw.packet.received)           (raw.packet.received, cmw.error)
        │                                  │
        │ channel="tcp"                    │ channel="sms"
        │ connection_id="..."              │ connection_id=None
        ▼                                  ▼
  ┌─────────────────────────────────────────────────┐
  │            PacketDispatcher                     │
  │  _build_pipeline():                             │
  │    CRC → Parse → AutoResponse → Dedup → EventEmit│
  └────────────────────┬────────────────────────────┘
                       │ emit("packet.processed")
                       ▼
              ┌────────────────────┐
              │  SessionManager    │◄─── CommandDispatcher
              │  (ordered handler) │     (command.send → TCP/SMS)
              │  FSM transition    │     emit(command.sent / command.error)
              └────────┬──────────┘
                       │ emit("connection.changed")
                       ▼
         ┌─────────────────────────────┐
         │ LogManager (подписан на     │
         │ packet.processed,           │
         │ connection.changed,         │
         │ scenario.step, command.*)   │
         └─────────────────────────────┘
```

**Запрещено:**
- TcpServer → Session (напрямую)
- Pipeline → LogManager (напрямую)
- Scenario → TcpServer (напрямую)
- CommandDispatcher → Session (напрямую — только через EventBus)

**Разрешено:**
- Через EventBus.emit() / EventBus.on()
- Через конструкторы (DI) — SessionManager → Cmw500Controller (для SMS), ScenarioManager → StepFactory

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
│   ├── config.py                  # Config (nested dataclass, JSON + CLI merge)
│   ├── event_bus.py               # EventBus (ordered + parallel handlers)
│   ├── tcp_server.py              # TcpServerManager (asyncio TCP)
│   ├── cmw500.py                  # Cmw500Controller + Cmw500Emulator
│   ├── session.py                 # SessionManager + UsvConnection + FSM + TransactionManager
│   ├── scenario.py                # ScenarioManager + StepFactory + ExpectStep + SendStep
│   ├── scenario_parser.py         # IScenarioParser + V1 + Registry + Factory
│   ├── packet_source.py           # ReplaySource (offline-анализ)
│   ├── pipeline.py                # PacketPipeline + 5 Middleware
│   ├── dispatcher.py              # PacketDispatcher + CommandDispatcher
│   ├── logger.py                  # LogManager (JSONL, буферизация, сортировка)
│   ├── credentials.py             # CredentialsRepository (JSON, chmod 600)
│   └── export.py                  # export_csv/json/scenario_results (функции)
├── libs/
│   ├── egts_protocol_iface/       # Абстрактный интерфейс (IEgtsProtocol)
│   └── egts_protocol_gost2015/    # Реализация ГОСТ 33465-2015
│       ├── adapter.py             # Маппинг gost2015_impl ↔ iface
│       └── gost2015_impl/         # Парсер, сборщик, CRC, SMS, сервисы
├── cli/app.py                     # CLI приложение (9 команд + REPL cmd.Cmd)
├── scenarios/                     # 10 готовых сценариев (JSON + HEX)
├── config/                        # settings.json, credentials.json
├── data/                          # Тестовые данные (траектории, профили, MSD)
├── logs/                          # JSONL-логи (daily rotation)
└── tests/                         # pytest (841 тест, 90%+ coverage)
    ├── conftest.py                # Shared fixtures
    ├── core/                      # Тесты ядра
    │   ├── test_event_bus.py      # ✅ 14 тестов, 100%
    │   ├── test_config.py         # ✅ 28 тестов, 91%
    │   ├── test_engine.py         # ✅ 6 тестов, 100%
    │   ├── test_session.py        # ✅ 61 тест, 100% FSM
    │   ├── test_pipeline.py       # ✅ 54 теста, 95%+
    │   ├── test_tcp_server.py     # ✅ 15 тестов, 97%
    │   ├── test_cmw500.py         # ✅ 39 тестов, 91%
    │   ├── test_cmw_emulator.py   # ✅ 19 тестов
    │   ├── test_dispatcher.py     # ✅ 47 тестов, 95%
    │   ├── test_logger.py         # ✅ 23 теста
    │   ├── test_credentials.py    # ✅ 25 тестов, 94%
    │   ├── test_scenario_parser.py# ✅ 29 тестов
    │   ├── test_scenario_context.py# ✅ 21 тест
    │   ├── test_expect_step.py    # ✅ 22 теста
    │   ├── test_send_step.py      # ✅ 18 тестов
    │   ├── test_scenario_manager.py# ✅ 9 тестов
    │   ├── test_replay.py         # ✅ 21 тест, 98%
    │   ├── test_export.py         # ✅ 18 тестов, 96%
    │   └── test_integration_chain.py # ✅ 6 интеграционных
    ├── cli/
    │   └── test_cli.py            # ✅ 43 теста, ruff + mypy clean
    └── libs/
        ├── egts_protocol_iface/   # ✅ 73 теста, 100%
        └── egts_protocol_gost2015/ # ✅ 59 тестов (адаптер)
```

**Итого:** 884 теста, 90%+ coverage, 0 failing
