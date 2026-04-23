# Отчёт о проверке файлов core/ и системы логирования

**Дата проверки:** 2024
**Объект проверки:** Все файлы директории `/workspace/core/` и система логирования
**Методы проверки:** Статический анализ кода, запуск тестов, проверка импортов, анализ покрытия

---

## 1. Общая статистика

### 1.1 Файлы в core/
| Файл | Строк | Статус |
|------|-------|--------|
| `__init__.py` | 3 | ✅ OK |
| `cmw500.py` | 937 | ✅ OK |
| `config.py` | 227 | ✅ OK |
| `credentials.py` | 152 | ✅ OK |
| `dispatcher.py` | 585 | ⚠️ Warning |
| `egts_adapter.py` | 74 | ✅ OK |
| `engine.py` | 430 | ✅ OK |
| `event_bus.py` | 100 | ✅ OK |
| `export.py` | 277 | ✅ OK |
| `logger.py` | 344 | ⚠️ Warning |
| `packet_source.py` | 179 | ✅ OK |
| `pipeline.py` | 581 | ✅ OK |
| `python_logger.py` | 124 | ❌ Critical |
| `scenario.py` | 710 | ✅ OK |
| `scenario_parser.py` | 338 | ✅ OK |
| `session.py` | 812 | ✅ OK |
| `tcp_server.py` | 277 | ✅ OK |
| **Итого** | **6150** | |

### 1.2 Результаты тестов
- **Всего тестов:** 483 passed, 1 skipped
- **Покрытие кода:** 82%
- **Критических ошибок:** 0
- **Предупреждения:** 19 ( RuntimeWarning о не-awaited coroutine)

---

## 2. Выявленные проблемы

### 2.1 КРИТИЧЕСКИЕ ПРОБЛЕМЫ

#### 🔴 CRITICAL-001: Неопределённая переменная `_log_dir` в `python_logger.py`

**Файл:** `core/python_logger.py`  
**Строка:** 96  
**Описание:** Функция `get_log_dir()` ссылается на глобальную переменную `_log_dir`, которая никогда не объявляется в модуле.

```python
def get_log_dir() -> Path:
    """Вернуть директорию логов."""
    return _log_dir  # NameError: name '_log_dir' is not defined
```

**Последствия:**
- Вызов `get_log_dir()` вызывает `NameError`
- Невозможно получить путь к директории логов извне
- Нарушается контракт API модуля

**Доказательство:**
```bash
$ python -c "from core.python_logger import get_log_dir; get_log_dir()"
NameError: name '_log_dir' is not defined
```

**Способ устранения:**

**Вариант A (рекомендуемый):** Добавить глобальную переменную и инициализировать её в `setup_python_logging()`:

```python
# В начале файла после строки 10
_log_dir: Path | None = None

# В функции setup_python_logging(), после строки 40
global _log_dir
_log_dir = log_dir

# В функции get_log_dir(), строка 94-96
def get_log_dir() -> Path:
    """Вернуть директорию логов."""
    if _log_dir is None:
        raise RuntimeError("Логирование не инициализировано. Вызовите setup_python_logging()")
    return _log_dir
```

**Вариант B (альтернативный):** Хранить `_log_dir` как атрибут функции:

```python
def get_log_dir() -> Path:
    """Вернуть директорию логов."""
    if not hasattr(setup_python_logging, '_log_dir'):
        raise RuntimeError("Логирование не инициализировано")
    return setup_python_logging._log_dir

def setup_python_logging(...) -> str:
    ...
    setup_python_logging._log_dir = log_dir
    return session_id
```

---

### 2.2 ПРЕДУПРЕЖДЕНИЯ СРЕДНЕЙ ВАЖНОСТИ

#### 🟡 WARNING-001: Отсутствие отписки от события `packet.sent` в `logger.py`

**Файл:** `core/logger.py`  
**Строки:** 114-120 (метод `stop()`)  
**Описание:** LogManager подписывается на событие `packet.sent` при инициализации (строка 79), но не отписывается от него при остановке.

```python
# Строка 78-81: Подписка
self._bus.on("packet.processed", self._on_packet_processed)
self._bus.on("packet.sent", self._on_packet_sent)  # ← Подписка есть
self._bus.on("connection.changed", self._on_connection_changed)
self._bus.off("scenario.step", self._on_scenario_step)

# Строки 114-118: Отписка (packet.sent отсутствует!)
self._bus.off("packet.processed", self._on_packet_processed)
self._bus.off("connection.changed", self._on_connection_changed)
self._bus.off("scenario.step", self._on_scenario_step)
# ← Нет: self._bus.off("packet.sent", self._on_packet_sent)
```

**Последствия:**
- Утечка памяти: обработчик остаётся в EventBus после остановки LogManager
- Возможны ошибки при повторной инициализации LogManager
- Нарушается принцип симметричности ресурсного менеджмента (acquire/release)

**Способ устранения:**

Добавить отписку в метод `stop()`:

```python
async def stop(self) -> None:
    """Остановить LogManager: сбросить буфер и отписаться от событий."""
    # ... существующий код ...
    
    # Отписаться от событий (строки 114-119)
    try:
        self._bus.off("packet.processed", self._on_packet_processed)
        self._bus.off("packet.sent", self._on_packet_sent)  # ← ДОБАВИТЬ
        self._bus.off("connection.changed", self._on_connection_changed)
        self._bus.off("scenario.step", self._on_scenario_step)
    except Exception as e:
        logger.debug("Ошибка отписки при закрытии: %s", e)
```

---

#### 🟡 WARNING-002: Hardcoded logging.basicConfig в `dispatcher.py`

**Файл:** `core/dispatcher.py`  
**Строка:** 38  
**Описание:** Присутствует закомментированный вызов `logging.basicConfig()` с комментарием `#fixme`.

```python
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.CRITICAL)   #fixme
```

**Последствия:**
- `basicConfig()` должен вызываться один раз при старте приложения, не в модуле
- Может конфликтовать с настройками из `python_logger.py`
- Признак незавершённой разработки

**Способ устранения:**

Удалить строку 38 полностью:

```python
logger = logging.getLogger(__name__)
# Строка 38 удалена
```

Настройка логирования должна выполняться централизованно через `core.python_logger.setup_python_logging()`.

---

#### 🟡 WARNING-003: RuntimeWarning о не-awaited coroutine `_auto_flush_loop`

**Файл:** `core/logger.py`  
**Строки:** 84-85  
**Описание:** При создании LogManager фоновая задача `_auto_flush_loop()` запускается через `asyncio.create_task()`, но в тестах mock-объекты могут приводить к предупреждениям.

```
RuntimeWarning: coroutine 'LogManager._auto_flush_loop' was never awaited
```

**Последствия:**
- Загромождение вывода тестов предупреждениями
- Потенциальная утечка задач при неправильном mock'ировании

**Способ устранения:**

Это предупреждение возникает в тестах при использовании MagicMock. Рекомендуется:
1. В тестах явно mock'ировать `_flush_task`
2. Или добавить проверку на mock перед созданием задачи

Пример исправления в тестах (не в production коде):
```python
# В тестах использовать:
with patch.object(LogManager, '_flush_task', new_callable=lambda: None):
    lm = LogManager(...)
```

---

### 2.3 РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ

#### 🟢 INFO-001: Низкое покрытие `python_logger.py`

**Статистика:** 25% coverage (39 из 52 строк не покрыты)

**Непокрытые области:**
- Функция `setup_python_logging()` (основная логика)
- Функция `_cleanup_old_logs()`
- Функция `_str_to_level()`

**Рекомендация:** Добавить тесты для:
1. Инициализации логирования с разными параметрами
2. Ротации логов
3. Функции `get_session_id()` и `get_log_dir()` (после исправления CRITICAL-001)

---

#### 🟢 INFO-002: Дублирование логики работы с SMS-сессиями

**Файлы:** `core/dispatcher.py`  
**Строки:** 248-268 (`PacketDispatcher._ensure_sms_session()`)  
**Строки:** 310-324 (`CommandDispatcher._ensure_sms_session_for_txn()`)

**Описание:** Оба диспетчера имеют собственные методы создания SMS-сессии с дублирующейся логикой.

**Рекомендация:** Вынести общую логику в отдельный сервис или базовый класс:

```python
# Новый файл: core/sms_session.py
class SmsSessionService:
    SMS_DEFAULT_CONNECTION_ID = "packet_dispatcher_sms"
    
    @classmethod
    def ensure_session(cls, session_mgr, protocol=None) -> str:
        if cls.SMS_DEFAULT_CONNECTION_ID in session_mgr.connections:
            return cls.SMS_DEFAULT_CONNECTION_ID
        
        if protocol is None:
            from core.egts_adapter import create_protocol
            protocol = create_protocol("2015")
        
        session_mgr.create_session(
            connection_id=cls.SMS_DEFAULT_CONNECTION_ID,
            protocol=protocol,
        )
        return cls.SMS_DEFAULT_CONNECTION_ID
```

---

#### 🟢 INFO-003: Магические числа в конфигурации

**Файл:** `core/config.py`  
**Строки:** 38-46 (списки по умолчанию для `ps_dl_carrier` и `ps_dl_cscheme`)

**Описание:** Хардкоженные значения конфигурации CMW-500 разбросаны по коду.

**Рекомендация:** Вынести в константы или внешний конфиг:

```python
# Константы в начале файла
DEFAULT_PS_DL_CARRIER = ["OFF", "OFF", "OFF", "ON", "ON", "OFF", "OFF", "OFF"]
DEFAULT_PS_DL_CSCHEME = ["MC9"] * 8

# Использование в dataclass
ps_dl_carrier: list[str] = field(default_factory=lambda: DEFAULT_PS_DL_CARRIER.copy())
ps_dl_cscheme: list[str] = field(default_factory=lambda: DEFAULT_PS_DL_CSCHEME.copy())
```

---

## 3. Положительные находки

### ✅ Хорошо реализовано:

1. **EventBus** — чёткое разделение ordered/parallel обработчиков
2. **PacketPipeline** — модульная архитектура middleware с правильным порядком выполнения
3. **SessionManager** — корректная реализация FSM с 18 переходами по ГОСТ
4. **LogManager** — буферизация с сортировкой по timestamp (решение проблемы CR-002)
5. **Типизация** — активное использование type hints и Protocol
6. **Документация** — подробные docstring с примерами использования

### ✅ Покрытие тестами:

| Компонент | Coverage | Оценка |
|-----------|----------|--------|
| `event_bus.py` | 100% | Отлично |
| `engine.py` | 99% | Отлично |
| `tcp_server.py` | 97% | Отлично |
| `session.py` | 93% | Отлично |
| `config.py` | 93% | Отлично |
| `credentials.py` | 94% | Отлично |
| `scenario.py` | 89% | Хорошо |
| `logger.py` | 89% | Хорошо |
| `pipeline.py` | 71% | Удовл. |
| `cmw500.py` | 62% | Требует улучшения |
| `python_logger.py` | 25% | ❌ Критично |

---

## 4. План исправлений

### Приоритет 1 (Критично)

| ID | Проблема | Файл | Оценка времени |
|----|----------|------|----------------|
| CRITICAL-001 | Неопределённая `_log_dir` | `python_logger.py` | 15 мин |

### Приоритет 2 (Важно)

| ID | Проблема | Файл | Оценка времени |
|----|----------|------|----------------|
| WARNING-001 | Утечка обработчика `packet.sent` | `logger.py` | 5 мин |
| WARNING-002 | Hardcoded `basicConfig` | `dispatcher.py` | 2 мин |

### Приоритет 3 (Рекомендации)

| ID | Проблема | Файл | Оценка времени |
|----|----------|------|----------------|
| INFO-001 | Низкое покрытие тестами | `python_logger.py` | 2 часа |
| INFO-002 | Дублирование SMS-логики | `dispatcher.py` | 1 час |
| INFO-003 | Магические числа | `config.py` | 30 мин |

---

## 5. Заключение

### Общая оценка: **ХОРОШО** (с критическими замечаниями)

**Сильные стороны:**
- Архитектурно грамотная модульная структура
- Высокое покрытие тестами большинства компонентов (82% общее)
- Следование best practices (type hints, docstrings, async/await)
- Реализация сложных требований ГОСТ 33465-2015

**Требует немедленного исправления:**
1. Критическая ошибка в `python_logger.get_log_dir()` — блокирует использование API
2. Утечка обработчика событий в `LogManager.stop()`

**Рекомендуется улучшить:**
- Покрытие тестами `python_logger.py`
- Рефакторинг дублирующегося кода
- Централизация конфигурации

---

## Приложение A: Команды для воспроизведения проблем

```bash
# CRITICAL-001: Проверка NameError
python -c "from core.python_logger import get_log_dir; get_log_dir()"

# WARNING-001: Проверка утечки (визуальный анализ кода)
grep -A 10 "async def stop" core/logger.py | grep "packet.sent"

# WARNING-002: Проверка hardcoded logging
grep -n "basicConfig" core/dispatcher.py

# Запуск всех тестов
python -m pytest tests/ -v --tb=short

# Проверка покрытия
python -m pytest tests/ --cov=core --cov-report=term-missing
```

---

*Отчёт сгенерирован автоматически на основе статического анализа и результатов тестирования.*
