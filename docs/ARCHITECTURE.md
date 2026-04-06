# Архитектура — OMEGA_EGTS

Детальное описание архитектуры серверного тестера УСВ.

---

## Принципы

1. **Единое ядро** — CLI/GUI тонкие обёртки поверх `core/`
2. **EventBus** — единственная шина коммуникации между компонентами (3 типа событий)
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
    async def run_scenario(self, scenario_id: str) -> None
```

**Жизненный цикл:**
1. Загрузка `config/settings.json`
2. Инициализация EventBus
3. Создание компонентов (TcpServer, Session, Pipeline, ...)
4. Подписка LogManager на `packet.received`, `connection.changed`, `scenario.step`
5. Запуск TCP-сервера
6. Ожидание подключений

---

### EventBus

**Файл:** `core/event_bus.py`

Асинхронная шина событий. Компоненты **не вызывают друг друга напрямую** — только через события.

```python
class EventBus:
    async def subscribe(self, event_type: str, handler: Callable) -> None
    async def unsubscribe(self, event_type: str, handler: Callable) -> None
    async def emit(self, event_type: str, data: dict) -> None
```

**Типы событий (строго 3):**

| Событие | Когда | Данные |
|---------|-------|--------|
| `packet.received` | Получен EGTS-пакет | `{"hex": "...", "parsed": {...}, "source": "tcp\|sms", "timestamp": "..."}` |
| `connection.changed` | Изменение состояния соединения | `{"state": "connected\|disconnected\|reconnecting", "details": "..."}` |
| `scenario.step` | Шаг сценария выполнен/провален | `{"step_id": "...", "status": "pass\|fail\|skip", "result": {...}}` |

**Требования:**
- Async-совместимый — IO-подписчики должны быть async-функциями
- Неблокирующий emit — события уходят в очередь
- Подписчики не знают друг о друге

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
    async def send_sms(self, recipient: str, data: bytes) -> None
```

**Особенности:**
- Асинхронная очередь команд (избегает блокировок VISA)
- Таймаут: `CMW_SCPI_TIMEOUT` = 5 с
- Повторы: `CMW_SCPI_RETRIES` = 3
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

### ScenarioManager

**Файл:** `core/scenario.py`

Загрузка и выполнение сценариев из JSON.

```python
class ScenarioManager:
    def load(self, path: str) -> None
    def get_scenario(self, scenario_id: str) -> Scenario
    async def execute(self, scenario_id: str) -> ScenarioResult
```

**Структура сценария (JSON):**

```json
{
  "id": "auth_v1",
  "name": "Авторизация v1",
  "steps": [
    {
      "id": "step_1",
      "action": "send",
      "packet_type": "TERM_IDENTITY",
      "data": {"term_code": "TEST001"},
      "expect": {
        "packet_type": "AUTH_PARAMS",
        "timeout": 5
      }
    },
    {
      "id": "step_2",
      "action": "send",
      "packet_type": "AUTH_INFO",
      "data": {"auth_data": "..."},
      "expect": {
        "packet_type": "RESULT_CODE",
        "result": "success",
        "timeout": 5
      }
    }
  ]
}
```

**StepFactory:**

```python
class StepFactory:
    def create_step(self, step_def: dict) -> Step
    # Типы шагов: send, expect, wait, check, log
```

---

### PacketPipeline

**Файл:** `core/pipeline.py`

Middleware-конвейер обработки входящих пакетов.

```
Входящий байт-поток
        │
        ▼
┌──────────────┐
│ CRC Check    │  → проверка CRC-16, отбраковка битых
└──────┬───────┘
       ▼
┌──────────────┐
│ Parse        │  → десериализация EGTS-пакета
└──────┬───────┘
       ▼
┌──────────────┐
│ Duplicate    │  → отсев дубликатов (по PN/CID)
└──────┬───────┘
       ▼
┌──────────────┐
│ Transaction  │  → PID↔RPID, RN↔CRN маппинг
└──────┬───────┘
       ▼
┌──────────────┐
│ Event Emit   │  → packet.received в EventBus
└──────────────┘
        │
        ▼
  RESPONSE (если требуется)
```

**Middleware:**

```python
class Middleware(Protocol):
    async def process(self, packet: RawPacket, next: Callable) -> ProcessedPacket | None

class PacketPipeline:
    def add_middleware(self, mw: Middleware) -> None
    async def process(self, raw: bytes) -> None
```

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

Загрузка и валидация конфигурации.

```python
@dataclass(frozen=True)
class Config:
    tcp_host: str = "0.0.0.0"
    tcp_port: int = 8090
    cmw_ip: str | None = None
    cmw_scpi_timeout: float = 5.0
    cmw_scpi_retries: int = 3
    tl_response_to: float = 5.0
    tl_reconnect_to: float = 30.0
    tl_resend_attempts: int = 3
    egts_sl_not_auth_to: float = 6.0
    log_dir: str = "logs"
    credentials_path: str = "config/credentials.json"

    @classmethod
    def from_file(cls, path: str) -> Config
```

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
│   ├── scenario.py                # ScenarioManager + StepFactory
│   ├── packet_source.py           # Загрузка/генерация пакетов
│   ├── pipeline.py                # PacketPipeline + Middleware
│   ├── logger.py                  # LogManager
│   ├── credentials.py             # CredentialsRepository
│   └── export.py                  # Выгрузка данных
├── libs/egts_protocol/            # Библиотеки EGTS (2015, 2023)
├── cli/app.py                     # CLI приложение
├── scenarios/                     # Готовые сценарии (JSON + HEX)
├── config/                        # settings.json, credentials.json
└── tests/                         # pytest
    ├── conftest.py
    ├── core/
    │   ├── test_event_bus.py
    │   ├── test_fsm.py
    │   ├── test_pipeline.py
    │   └── ...
    └── integration/
        └── ...
```
