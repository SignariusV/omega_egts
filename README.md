# OMEGA_EGTS — Серверный тестер УСВ

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-v1.0.0-green.svg)](.)

**Серверный тестер устройств/систем вызова экстренных оперативных служб (УСВ)** — программный комплекс для испытаний УСВ на соответствие требованиям **ГОСТ 33465** (редакции 2015, 2023) и **ГОСТ 33464**.

---

## Назначение

- Приём и анализ EGTS-пакетов от тестируемого УСВ через **CMW-500** (Rohde & Schwarz)
- Два канала связи: **TCP/IP** (через WiFi CMW-500) и **SMS** (через LAN/SCPI)
- Валидация протокола: авторизация, телеметрия, траектория, профиль ускорения, eCall, обновление ПО
- Протоколирование всех этапов испытаний — каждый пакет логируется (hex + parsed)
- Загрузка/выгрузка данных: работа с HEX-файлами и динамическая генерация пакетов

## Статус

> 🎉 **v1.0.0 RELEASED!** Все 12 итераций завершены.
>
> **921 тест** | **89% покрытие** | **ruff clean** | **mypy clean** | **0 failing**
>
> Реализованы: Core Engine, EGTS Protocol ГОСТ 2015, FSM (18 переходов),
> Packet Pipeline (5 middleware), TCP-сервер, CMW-500 контроллер + эмулятор,
> LogManager, CredentialsRepository, Scenario Engine (10 сценариев),
> Replay/Export, CLI (9 команд + REPL), E2E интеграционные тесты (10 тестов).

## Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone https://github.com/your-org/OMEGA_EGTS.git
cd OMEGA_EGTS

# 2. Создать виртуальное окружение
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# 3. Установить зависимости
pip install -e .

# 4. Запустить (когда будет готово)
omega-egts
```

## Поддерживаемые сценарии

| # | Сценарий | Ключевые сообщения |
|---|----------|-------------------|
| 1 | Авторизация | TERM_IDENTITY → AUTH_PARAMS → AUTH_INFO → RESULT_CODE |
| 2 | Телеметрия | NAV_DATA, координаты, скорость |
| 3 | Траектория | TRACK_DATA, последовательность точек |
| 4 | Профиль ускорения | ACCEL_DATA, ≤ 0.01G, ASI15 |
| 5 | eCall | RAW_MSD_DATA (ASN.1), МНД |
| 6 | Обновление ПО | SERVICE_PART_DATA, SERVICE_FULL_DATA, ODH |
| 7 | Команды и параметры | COMMAND_DATA, запрос/установка параметров |
| 8 | Режим тестирования | TEST_MODE_ON/OFF, проверочные пакеты |
| 9 | SMS-канал | Приём/отправка EGTS через SMS, конкатенация |
| 10 | Пассивный режим | TID=0, SMS с учётными данными, повторная авторизация |

## Архитектура

```
Core Engine (единое ядро)
    ├── EventBus (3 события: packet.received, connection.changed, scenario.step)
    ├── TcpServerManager (asyncio TCP-сервер)
    ├── Cmw500Controller (SCPI/VISA, асинхронная очередь команд)
    ├── SessionManager + UsvConnection + UsvStateMachine (FSM)
    ├── TransactionManager (PID↔RPID, RN↔CRN)
    ├── ScenarioManager (загрузка/выполнение сценариев из JSON)
    ├── PacketPipeline (middleware-конвейер: CRC → Parse → Duplicate → Transaction → Event)
    ├── LogManager (подписчик на события)
    ├── CredentialsRepository (JSON-хранилище)
    └── Export (CSV/JSON/DER выгрузка)
```

📖 Подробная архитектура: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Ключевые параметры протокола

| Параметр | Значение | Описание |
|----------|----------|----------|
| `TL_RESPONSE_TO` | 5 с | Ожидание подтверждения |
| `TL_RESEND_ATTEMPTS` | 3 | Повторные попытки |
| `TL_RECONNECT_TO` | 30 с | Повторное соединение |
| `EGTS_SL_NOT_AUTH_TO` | 6 с | Таймаут авторизации |
| `CMW_SCPI_TIMEOUT` | 5 с | Таймаут SCPI-команды |
| `CMW_SCPI_RETRIES` | 3 | Повторные попытки SCPI |

## Дорожная карта

| Этап | Результат | Статус |
|------|-----------|--------|
| **1. Core Engine** | EventBus + Config + CoreEngine + FSM + SessionManager | ✅ Готово (100%) |
| **2. Библиотека EGTS** | egts_protocol_iface + EgtsProtocol2015 (парсинг/сборка/SMS) | ✅ Готово (100%) |
| **3. FSM и сессии** | UsvStateMachine (18 переходов) + TransactionManager + UsvConnection | ✅ Готово (100%) |
| **4. Pipeline** | PacketPipeline + 5 middleware + интеграционные тесты | ✅ Готово (100%) |
| **5. Network + CMW** | TCP-сервер + Cmw500Controller + эмулятор + Dispatchers | ✅ Готово (100%) |
| **6. Logging + Creds** | LogManager + CredentialsRepository | ✅ Готово (100%) |
| **7. Scenario Engine** | ScenarioParser + Context + Steps + Manager + 10 сценариев | ✅ Готово (100%) |
| **8. Replay + Export** | ReplaySource + Export (CSV/JSON) | ✅ Готово (100%) |
| **9. CLI** | CLI Application (9 команд + REPL) | ✅ Готово (100%) |
| **10. E2E + Релиз** | Интеграционные тесты + финальные проверки + v1.0.0 | ✅ Готово (100%) |

### Планируемое развитие

| Этап | Результат | Статус |
|------|-----------|--------|
| **11. ГОСТ 2023** | Поддержка актуальной редакции | ⬜ Запланировано |
| **12. GUI** | Графический интерфейс оператора | ⬜ Запланировано |
| **13. Реальное CMW-500** | Интеграция с реальным оборудованием | ⬜ Запланировано |

## Структура проекта

```
OMEGA_EGTS/
├── core/                          # ЕДИНОЕ ЯДРО
│   ├── engine.py                  # CoreEngine
│   ├── config.py                  # Config
│   ├── event_bus.py               # EventBus
│   ├── tcp_server.py              # TcpServerManager
│   ├── cmw500.py                  # Cmw500Controller + Cmw500Emulator
│   ├── session.py                 # SessionManager + FSM + TransactionManager
│   ├── dispatcher.py              # PacketDispatcher + CommandDispatcher
│   ├── pipeline.py                # PacketPipeline + 5 Middleware
│   ├── scenario_parser.py         # IScenarioParser, V1, Registry, Factory
│   ├── scenario.py                # ScenarioContext, Steps, ScenarioManager
│   ├── packet_source.py           # ReplaySource
│   ├── logger.py                  # LogManager
│   ├── credentials.py             # CredentialsRepository
│   └── export.py                  # Выгрузка данных (CSV/JSON)
├── libs/                          # Библиотеки EGTS
│   ├── egts_protocol_iface/       # Интерфейс: IEgtsProtocol, модели, enums
│   └── egts_protocol_gost2015/    # Реализация ГОСТ 2015 (адаптер + _internal)
├── cli/app.py                     # CLI приложение (запланировано)
├── scenarios/                     # Готовые сценарии (JSON + HEX)
├── config/                        # settings.json, credentials.json
├── docs/                          # Документация
│   ├── ТЗ_тестер_УСВ.md           # Техническое задание
│   ├── gost.md                    # ГОСТ 33465-2015
│   ├── ARCHITECTURE.md            # Архитектура
│   └── *.xlsx                     # Тестовые данные
├── tests/                         # pytest (921 тест)
├── CHANGELOG.md                   # История изменений
├── KNOWN_ISSUES.md                # Известные проблемы
└── pyproject.toml                 # Зависимости и скрипты
```

## Разработка

### Требования

- Python >= 3.12
- venv или uv

### Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### Тесты

```bash
pytest
pytest --cov=core --cov-report=term-missing
```

### Линтер

```bash
ruff check .
ruff format .
mypy core/
```

### Конвенции

- Каждый модуль — отдельный файл, без смешивания логики
- Компоненты не вызывают друг друга напрямую — только через EventBus
- Парсинг ≠ валидация ≠ бизнес-логика ≠ логирование ≠ интерфейс
- FSM тестируется изолированно, покрыты все переходы
- 100% пакетов логируется (включая CRC-ошибки)

📖 Подробнее: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Документация

| Документ | Описание |
|----------|----------|
| [`docs/ТЗ_тестер_УСВ.md`](docs/ТЗ_тестер_УСВ.md) | Полное техническое задание (1840 строк) |
| [`docs/gost.md`](docs/gost.md) | Текст ГОСТ 33465-2015 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Детальная архитектура |
| [`CHANGELOG.md`](CHANGELOG.md) | История изменений |
| [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) | Известные проблемы |

## Лицензия

[MIT](LICENSE)
