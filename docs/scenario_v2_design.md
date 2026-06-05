# Сценарии Версии 2 (V2) — Проект

> **Статус**: черновик, обсуждение
> **Основание**: существующая V1 (линейные JSON-сценарии, `UsvStateMachine` (FSM) ядра, `ScenarioParserV1`, pipeline с автоответами)
> **Цель**: композиция, переиспользование, состояния, циклы, условия, data binding, человекочитаемый формат

---

## Содержание

1. [Мотивация](#1-мотивация)
2. [Формат — YAML](#2-формат--yaml)
3. [Состояния — стейт-машина сценариев](#3-состояния--стейт-машина-сценариев)
4. [Автоответы](#4-автоответы)
5. [Переменные и подстановки](#5-переменные-и-подстановки)
6. [Циклы](#6-циклы)
7. [Условия](#7-условия)
8. [Извлечение данных из пакетов (Data Binding)](#8-извлечение-данных-из-пакетов-data-binding)
9. [Импорты и композиция](#9-импорты-и-композиция)
10. [Определения (defs)](#10-определения-defs)
11. [Продвинутые возможности](#11-продвинутые-возможности)
12. [Архитектура](#12-архитектура)
13. [Открытые вопросы](#13-открытые-вопросы)

---

## 1. Мотивация

### Проблемы V1

- **Все сценарии самодостаточны**: auth, telemetry, commands — каждый заново реализует подключение, аутентификацию, ожидание состояний. Нет переиспользования.
- **Отсутствует связь с FSM**: сценарий ничего не знает о состоянии УСВ (`UsvState`), хотя ядро его отслеживает. Единственная интеграция — `connection.changed` в `ExpectStep` для детекта дисконнекта.
- **Линейное исполнение**: нет циклов, условий, ветвлений. Нельзя сказать «повторить 5 раз» или «если ответ X, делать Y».
- **JSON**: избыточно-подробный, без комментариев, нельзя использовать ссылки/якоря.
- **Данные из пакетов**: capture есть, но слабый — только прямое копирование, нет преобразований типов, фильтрации, TTL.
- **Ручное управление RESPONSE**: хотя pipeline генерирует их автоматически, сценарий всё ещё может «задумываться» про RESPONSE. Нужно закрепить концепцию: сценарий — только про логику, RESPONSE — за pipeline.

### Цели V2

1. **Переиспользование** — импорт/композиция сценариев (auth как модуль)
2. **State-aware** — сценарии знают про FSM, используют состояния как триггеры и гарды
3. **Нелинейное исполнение** — условия, циклы, ветвления, параллельные шаги
4. **Человекочитаемый формат** — YAML с комментариями
5. **Data binding** — мощное извлечение данных из пакетов с преобразованиями
6. **Обратная совместимость** — V1 (JSON) продолжает работать
7. **Автоответы не в сценарии** — отделяем логику теста от протокольного автомата

---

## 2. Формат — YAML

### 2.1. Базовая структура

```yaml
# scenarios/telemetry/scenario.yaml
scenario_version: "2"
name: Проверка телеметрии
description: >
  Отправляет телеметрийные данные и проверяет получение RESPONSE.
  Требует состояния RUNNING у УСВ.

# Системные
on_state: RUNNING
on_state_mismatch: import_auth

# Переменные
variables:
  pid: { start: 1, auto: true }
  imei: { resolver: device_imei }

# Импорты (переиспользование)
imports:
  - name: auth
    file: scenarios/auth/scenario.yaml
    alias: preauth
    variables:
      imei: "{{imei}}"

# Шаги
steps:
  - send:
      name: Отправить телеметрию
      build:
        packet_id: "{{pid}}"
        records:
          - service: 4
            subrecords:
              - type: EGTS_SR_RCD_DATA
                data:
                  ct: 5
                  cid: 0
                  points:
                    - { lat: 55.75, lon: 37.62 }

  - expect:
      name: Получить подтверждение
      capture:
        response_code: processing_result
        server_time: data.ST
      checks:
        processing_result: 0
```

### 2.2. Преимущества YAML над JSON

| Возможность | JSON | YAML |
|-------------|------|------|
| Комментарии | нет | `# комментарий` |
| Якоря/ссылки | нет | `&anchor`, `*anchor` |
| Многострочные строки | `\n` | `|`, `>` |
| Читаемость | скобки, запятые | отступы |
| Валидация | схема | схема + линтер |

### 2.3. Обсуждение: YAML vs TOML vs纯 Python dict

- **YAML**: привычен для конфигов и CI/CD, поддерживает сложную вложенность, комментарии. Минус — отступы могут сбиваться.
- **TOML**: проще, но плох для глубокой вложенности (шаги сценария).
- **Python dict в .py**: максимальная гибкость, но требует программирования — отходит от идеи «сценарий как данные».

---

## 3. Состояния — стейт-машина сценариев

### 3.1. Концепция

В ядре уже есть `UsvStateMachine` — она отслеживает состояния УСВ **на уровне протокола**:
`DISCONNECTED → CONNECTED → AUTHENTICATING → AUTHORIZED → RUNNING → ERROR`

Сценарии V2 надстраивают **второй уровень** — состояния самого сценария. Они триггерятся от FSM ядра, но управляют логикой теста.

```
FSM ядра (UsvStateMachine):           CONNECTED → AUTHENTICATING → AUTHORIZED → RUNNING
                                           ↓             ↓               ↓           ↓
FSM сценария (ScenarioStateMachine):  wait_connect → authenticating → authorized → running → ...
                                           ↓             ↓               ↓           ↓
                                      import:auth    steps:auth     steps:init   steps:test
```

### 3.2. Сценарий-диспетчер

```yaml
# scenarios/full_session/scenario.yaml
scenario_version: "2"
name: Полная сессия

states:
  idle:
    on_enter: wait_connect

  wait_connect:
    on_state: CONNECTED               # ждём когда ядро перейдёт в CONNECTED
    transitions:
      match: -> authenticating
      timeout: -> error

  authenticating:
    import: scenarios/auth/auth.yaml
    transitions:
      on_pass: -> authorized
      on_fail: -> error

  authorized:
    steps:
      - expect:
          checks: { processing_result: 0 }
    transitions:
      on_pass: -> running

  running:
    parallel:
      - import: scenarios/telemetry/telemetry.yaml
      - import: scenarios/track/track.yaml
      - import: scenarios/commands/commands.yaml
    transitions:
      on_disconnect: -> idle

  error:
    steps:
      - import: scenarios/reconnect/reconnect.yaml
    transitions:
      on_pass: -> idle

start: idle
final: [idle, error]
```

### 3.3. Типы переходов

| Тип | Описание |
|-----|----------|
| `on_state: CONNECTED` | Триггер от FSM ядра — переход в указанное состояние |
| `on_pass` | Под-сценарий или шаг завершился PASS |
| `on_fail` | Под-сценарий или шаг завершился FAIL |
| `on_timeout` | Истекло время ожидания состояния |
| `on_disconnect` | FSM ядра перешло в DISCONNECTED |
| `on_error` | FSM ядра перешло в ERROR |
| `match` | Автоматически при входе в состояние (безусловный переход) |
| `on_event: cmd.received` | Произвольное событие шины |

### 3.4. Гарды на вход в состояние

```yaml
states:
  running:
    guard: "{{auth_method}} == dynamic"    # войти только если условие истинно
    guard_fail: -> auth_dynamic            # альтернативный путь
    import: scenarios/telemetry/scenario.yaml
```

### 3.5. Вложенные состояния

```yaml
states:
  running:
    children:                               # под-состояния
      data_collecting:
        steps: [...]
      waiting_command:
        steps: [...]
    initial: data_collecting
```

### 3.6. Открытые вопросы

- Как сценарий-диспетчер взаимодействует с пользовательским UI (панель запуска)?
- Нужен ли визуальный редактор стейт-машины?
- Как отображать текущее состояние сценария на GUI?
- Должен ли каждый сценарий быть стейт-машиной или только опционально?

---

## 4. Автоответы

### 4.1. Принцип

Pipeline (`AutoResponseMiddleware`) уже генерирует RESPONSE на любой корректный пакет. Сценарий **не должен** определять RESPONSE — это дело протокольного уровня.

```
Входящий пакет → Pipeline (CRC → Parse → Dedup → AutoResponse → EventEmit)
                                                                    ↓
                                                             packet.processed
                                                                    ↓
                                                    ExpectStep (проверки+capture)
                                                                    ↓
                                                    ScenarioManager (следующий шаг)
```

### 4.2. Что это означает для сценариев V2

- `send` — отправляет пакет, не ждёт RESPONSE как часть шага
- `expect` — подписывается на `packet.processed` и проверяет содержимое **входящего пакета**, RESPONSE pipeline не трогает
- `expect` может совпасть как на оригинальный пакет от УСВ, так и на RESPONSE — зависит от checks
- Специальный шаг `expect_response` (опционально) — явно ждёт именно RESPONSE на отправленный пакет

### 4.3. Вариант: явный шаг для RESPONSE

```yaml
steps:
  - send:
      name: Отправить TERM_IDENTITY
      build: { ... }

  - expect_response:               # ждём RESPONSE на PID отправленного
      checks:
        processing_result: 0
      timeout: 5
```

### 4.4. Открытые вопросы

- Всегда ли RESPONSE приходит — или есть случаи когда сценарий должен его поймать?
- Нужно ли давать возможность отключить автоответ для конкретного шага?
- Как быть с SMS-каналом — там RESPONSE не отправляется на транспортном уровне?

---

## 5. Переменные и подстановки

### 5.1. Текущая система (V1)

Уже есть:
- `{{var}}` подстановка в `build` и `checks`
- `capture` — извлечение из пакета в переменную
- TTL, auto-increment, resolver-ы
- 3 формата: `value`, `{start, auto}`, `{resolver}`

### 5.2. Расширения для V2

```yaml
variables:
  # Автоинкремент (уже есть)
  pid: { start: 1, auto: true }

  # Резолвер (уже есть)
  imei: { resolver: device_imei }

  # Пустая — будет заполнена через capture
  server_tid: {}

  # Вычисляемая (expression)
  next_lat:
    expr: "{{prev_lat}} + 0.001"

  # Форматированная строка
  log_message:
    format: "Packet {pid} sent, response={resp_code}"

  # Из внешнего источника
  test_points:
    resolver: file_read
    params:
      path: "data/track_points.csv"
      format: csv

  # Запрос к БД
  expected_devices:
    resolver: database_query
    params:
      query: "SELECT count(*) FROM devices WHERE active = 1"
```

### 5.3. Типы выражений (expr)

```yaml
variables:
  counter_a: { start: 0 }
  counter_b: { start: 10 }

  # Арифметика
  sum: { expr: "{{counter_a}} + {{counter_b}}" }

  # Строковые операции
  full_imei: { expr: '"RU_" ~ {{imei}}' }

  # Булева логика
  is_valid: { expr: "{{response_code}} == 0 and {{crc_valid}} == true" }

  # Тернарный оператор
  auth_type: { expr: "{{auth_method}} == 1 ? 'static' : 'dynamic'" }
```

**Вопрос**: использовать встроенный язык выражений (а-ля Celery `expr`) или делегировать в Python-резолверы?

### 5.4. Области видимости

```yaml
imports:
  - name: auth
    file: scenarios/auth/scenario.yaml
    variables:
      # Переопределение переменных при импорте
      imei: "{{device_imei}}"
      timeout: 30
    export:                    # какие переменные пробросить наружу
      - auth_result
      - server_tid
```

| Область | Видимость |
|---------|-----------|
| `{{var}}` | локальная сценария |
| `{{import_name.var}}` | из импортированного сценария |
| `{{context.connection_id}}` | системные переменные (context) |
| `{{env.PATH}}` | переменные окружения |

---

## 6. Циклы

### 6.1. Итерация по массиву

```yaml
steps:
  - loop:
      name: Отправка точек трека
      over: "{{test_points}}"
      as: point
      index: point_idx
      parallel: false
      steps:
        - send:
            build:
              packet_id: "{{pid}}"
              records:
                - service: 4
                  subrecords:
                    - type: EGTS_SR_RCD_DATA
                      data:
                        lat: "{{point.lat}}"
                        lon: "{{point.lon}}"
        - expect:
            timeout: 2
            checks: { processing_result: 0 }
            on_fail: continue              # не прерывать цикл
```

### 6.2. Цикл по счётчику

```yaml
- loop:
    count: 10
    as: attempt
    steps:
      - send: { packet_file: "ping.hex" }
      - expect:
          checks: { processing_result: 0 }
          on_fail: break                  # прервать цикл при первой неудаче
```

### 6.3. Цикл-ожидание (while)

```yaml
- loop:
    name: Ожидание аутентификации
    while: "{{auth_state}} != AUTHORIZED"
    max_iterations: 20
    interval: 1                            # секунд между итерациями
    steps:
      - send: { packet_file: "ping.hex" }
      - expect:
          timeout: 2
          capture: { auth_state: processing_result }
```

### 6.4. Вложенные циклы

```yaml
- loop:
    over: "{{devices}}"
    as: device
    steps:
      - loop:
          over: "{{device.points}}"
          as: point
          steps:
            - send:
                build:
                  imei: "{{device.imei}}"
                  lat: "{{point.lat}}"
                  lon: "{{point.lon}}"
```

### 6.5. Параметры цикла

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `over` | — | Массив для итерации |
| `count` | — | Число итераций (альтернатива `over`) |
| `while` | — | Условие продолжения |
| `as` | `item` | Имя текущего элемента |
| `index` | — | Имя переменной индекса |
| `parallel` | `false` | Параллельное выполнение итераций |
| `max_iterations` | 1000 | Защита от бесконечного цикла |
| `interval` | 0 | Задержка между итерациями |
| `on_fail` | `stop` | `stop`, `continue`, `break` |
| `timeout` | — | Таймаут на весь цикл |

### 6.6. Открытые вопросы

- Нужен ли `for` по ключам словаря (а не только массива)?
- Параллельный `loop` — как собирать результаты из параллельных итераций?
- Баунд на `max_iterations` — должен быть обязательным?

---

## 7. Условия

### 7.1. If-elif-else

```yaml
steps:
  - if:
      condition: "{{auth_method}} == 1"
      then:
        - import: scenarios/auth_static/auth_static.yaml
      elif:
        - condition: "{{auth_method}} == 2"
          then:
            - import: scenarios/auth_dynamic/auth_dynamic.yaml
        - condition: "{{auth_method}} == 3"
          then:
            - import: scenarios/auth_modern/auth_modern.yaml
      else:
        - fail: "Неизвестный метод аутентификации: {{auth_method}}"
```

### 7.2. Switch

```yaml
- switch:
    expr: "{{subrecord_type}}"
    cases:
      51:                                   # EGTS_SR_RCD_DATA
        - send:
            build:
              subrecords:
                - type: EGTS_SR_RCD_DATA
                  data: { ct: 5, cid: 0 }
      52:                                   # EGTS_SR_RCD_EVENT
        - send:
            build:
              subrecords:
                - type: EGTS_SR_RCD_EVENT
                  data: { et: 1, ec: 100 }
      130:                                  # EGTS_SR_COMMAND_DATA
        - import: scenarios/commands/scenario.yaml
    default:
      - send: { packet_file: "unknown.hex" }
```

### 7.3. Guard на шаге

```yaml
- expect:
    name: Ожидание команды оператора
    guard: "{{is_operator_connected}} == true"
    checks:
      service: 7
      subrecord_type: 130
  send_on_match:                        # если шаг совпал — отправить ответ
    build:
      subrecords:
        - type: EGTS_SR_COMMAND_RESPONSE
          data: { result: 0 }
```

### 7.4. Комбинация условий (логические операторы)

```yaml
- if:
    condition: "{{auth_method}} in [1, 2] and {{imei}} matches '^\\d{15}$'"
    then:
      - send: { packet_file: "auth_valid.hex" }
    else:
      - send: { packet_file: "auth_invalid.hex" }
```

---

## 8. Извлечение данных из пакетов (Data Binding)

### 8.1. Текущая система (V1)

```yaml
capture:
  var_name: data.path               # простое копирование
```

### 8.2. Расширенный capture V2

```yaml
- expect:
    name: Поймать TERM_IDENTITY
    capture:
      # Простое копирование (как в V1)
      imei: IMEI
      imsi: IMSI

      # С преобразованием типа
      server_time:
        path: data.ST
        type: int
        scale: 0.001                    # из мс в секунды

      # С условием — извлечь только если проходит гард
      auth_service:
        path: records[0].service_type
        guard: "{{service}} == 1"

      # С TTL — временная переменная
      session_key:
        path: data.SESS_KEY
        ttl: 60

      # С alias — присвоить в другую переменную
      current_pid:
        alias: pid                       # будет доступно как {{pid}}
        path: response_packet_id

      # Со значением по умолчанию
      optional_field:
        path: data.OPT_FIELD
        default: 0                       # если поля нет — будет 0

      # Массив
      all_points:
        path: records[0].subrecords[0].data.points
        type: list
```

### 8.3. Множественный capture за один expect

```yaml
- expect:
    name: Поймать данные из RCD
    capture:
      lat:
        path: records[0].subrecords[0].data.points[0].lat
        type: float
      lon:
        path: records[0].subrecords[0].data.points[0].lon
        type: float
      speed:
        path: records[0].subrecords[0].data.points[0].speed
        type: int
        guard: "{{has_speed}} == true"       # опционально
```

### 8.4. Использование захваченных данных

```yaml
steps:
  - expect:
      capture:
        server_tid: data.TID

  - if:
      condition: "{{server_tid}} > 0"
      then:
        - send:
            build:
              tid: "{{server_tid}}"         # подстановка из capture
```

---

## 9. Импорты и композиция

### 9.1. Концепция

Базовый строительный блок — auth-сценарий. Он должен переиспользоваться во всех сценариях, которым нужно авторизоваться:

```
telemetry.yaml  ──import──→  auth.yaml
commands.yaml   ──import──→  auth.yaml
track.yaml      ──import──→  auth.yaml
```

### 9.2. Простой импорт

```yaml
# scenarios/telemetry/scenario.yaml
imports:
  - name: auth
    file: scenarios/auth/scenario.yaml

steps:
  - import: auth
  - send: { ... }
```

### 9.3. Импорт с параметрами

```yaml
imports:
  - name: auth
    file: scenarios/auth/scenario.yaml

steps:
  - import:
      ref: auth
      variables:
        imei: "{{device_imei}}"
        timeout: 15
      export:                              # пробросить переменные наружу
        - auth_result
        - server_tid
      on_pass: continue
      on_fail: abort_scenario
```

### 9.4. Типы импорта

| Тип | Ключ | Поведение |
|-----|------|-----------|
| `inline` | (по умолчанию) | Шаги под-сценария вставляются в текущий как копипаста |
| `subprocess` | `mode: subprocess` | Выполняется отдельно, возвращает PASS/FAIL в родитель |
| `background` | `mode: background` | Запускается параллельно (например, мониторинг команд) |
| `template` | `mode: template` | Параметризованный шаблон с `params` |

### 9.5. Фоновый импорт (background)

```yaml
- import:
    ref: monitor_command
    mode: background                       # запускается параллельно
    on_event: cmd.received                 # пробуждается по событию

- import:
    ref: monitor_connection
    mode: background
    on_event: connection.changed
```

### 9.6. Шаблоны (template)

```yaml
# scenarios/templates/send_and_expect.yaml
scenario_version: "2"
template: true                             # не запускается сам по себе
params:
  - packet_file
  - expected_code

steps:
  - send:
      packet_file: "{{packet_file}}"
  - expect:
      checks:
        processing_result: "{{expected_code}}"
```

Использование:

```yaml
steps:
  - import:
      ref: send_and_expect
      mode: template
      params:
        packet_file: "commands/block_engine.hex"
        expected_code: 0
```

### 9.7. Импорт с переопределением шагов

```yaml
imports:
  - name: auth
    file: scenarios/auth/scenario.yaml

steps:
  - import:
      ref: auth
      override:                            # переопределить/добавить шаги
        after_step: "send_identity"        # после этого шага
        steps:
          - expect:
              name: Дополнительная проверка
              checks: { service: 1 }
```

### 9.8. Области видимости переменных при импорте

```
Родительский сценарий:
  variables:
    imei: "123456789012345"

Импорт auth:
  sees {{imei}} → "123456789012345"  (наследуется)
  видит собственные переменные
  export → пробрасывает наружу

Родитель после импорта:
  может использовать {{auth_result}}
```

### 9.9. Разрешение циклических импортов

- Проверка на уровне парсера: обнаружение циклов в графе зависимостей
- Максимальная глубина импорта: configurable (default 5)

---

## 10. Определения (defs)

### 10.1. Локальные макросы

```yaml
defs:
  send_auth:
    params: [imei, imsi, tid]
    steps:
      - send:
          build:
            records:
              - service: 1
                subrecords:
                  - type: EGTS_SR_TERM_IDENTITY
                    data:
                      tid: "{{tid}}"
                      imei: "{{imei}}"
                      imsi: "{{imsi}}"
      - expect:
          capture: { auth_code: processing_result }

steps:
  - call: send_auth
    with:
      imei: "{{device_imei}}"
      imsi: "{{device_imsi}}"
      tid: 1
```

### 10.2. Глобальные определения

```yaml
# scenarios/defs/common.yaml
defs:
  send_auth: { ... }
  wait_response: { ... }
  check_crc: { ... }
```

Подключение:

```yaml
imports:
  - name: common
    file: scenarios/defs/common.yaml
    mode: definitions                     # только defs, не выполняется

steps:
  - call: common.send_auth
    with: { ... }
```

### 10.3. Открытые вопросы

- defs — это YAML-функции? Нужны ли параметры по умолчанию?
- Поддерживать ли рекурсивные вызовы defs?
- Как проверять типы параметров defs?

---

## 11. Продвинутые возможности

### 11.1. Валидация схемы пакета

```yaml
- expect:
    name: Проверить структуру пакета
    schema:
      type: object
      properties:
        packet_type:
          type: integer
          enum: [1, 2]
        records:
          type: array
          minItems: 1
          maxItems: 5
          items:
            type: object
            properties:
              service:
                type: integer
                minimum: 1
                maximum: 255
              subrecords:
                type: array
                items:
                  type: object
                  properties:
                    subrecord_type:
                      type: integer
```

### 11.2. Метрики и логирование

```yaml
steps:
  - send:
      name: Отправить телеметрию
      log_level: info
      metrics:
        latency: true
        packet_size: true
      on_slow_warning: 500                   # предупреждение если >500ms
      tags:                                   # теги для фильтрации метрик
        - telemetry
        - auth

  - expect:
      metrics:
        response_time: true
        match_rate: true
      thresholds:
        latency_ms: { max: 1000 }
        packet_loss: { max: 0 }
```

### 11.3. CSV/DataSource-провайдеры

```yaml
variables:
  test_cases:
    resolver: csv_read
    params:
      file: "data/test_cases.csv"
      delimiter: ";"

steps:
  - loop:
      over: "{{test_cases}}"
      as: case
      steps:
        - send:
            build:
              imei: "{{case.imei}}"
              imsi: "{{case.imsi}}"
        - expect:
            checks:
              processing_result: "{{case.expected_code}}"
```

### 11.4. RPC и внешние вызовы

```yaml
- rpc:
    name: Получить список УСВ от CMW-500
    target: cmw500
    method: get_device_list
    params:
      filter: "active"
    capture:
      devices: result

- rpc:
    target: database
    method: save_test_result
    params:
      scenario: "{{name}}"
      result: "{{scenario_result}}"
      timestamp: "{{system.now}}"
```

### 11.5. Сценарии проверки безопасности

```yaml
- send:
    name: Replay-атака
    packet_file: "captured_auth.hex"
    corrupt: false

- send:
    name: Битый CRC
    packet_file: "auth.hex"
    corrupt: crc8                         # испортить только CRC-8

- expect:
    name: Убедиться что сервер отклонил
    checks:
      processing_result: 4                 # WRONG_CRC
```

### 11.6. Sleep / ожидание

```yaml
- wait:
    duration: 5                            # секунд
    reason: "Ожидание стабилизации соединения"

- wait_until:
    condition: "{{fsm.state}} == RUNNING"
    timeout: 30
    interval: 0.5
```

### 11.7. Fail / Pass / Skip

```yaml
- fail:
    reason: "Невалидная конфигурация: {{config_error}}"
    screenshot: true                        # (если есть GUI)

- pass:
    message: "Сценарий пропущен — УСВ не поддерживает эту функцию"
    condition: "{{device_model}} != OMEGA-1"


- skip:
    condition: "{{feature_flag}} == false"
```

---

## 12. Архитектура

### 12.1. Новая структура файлов

```
scenarios/
├── auth/
│   └── scenario.yaml           # сценарий V2 на YAML
├── telemetry/
│   └── scenario.yaml
├── track/
│   └── scenario.yaml
├── templates/
│   └── send_and_expect.yaml    # шаблон
├── defs/
│   ├── common.yaml             # глобальные определения
│   └── auth_flow.yaml
└── suites/
    ├── smoke.yaml              # набор сценариев
    └── full_regression.yaml

core/
├── scenario_parser.py
│   ├── ScenarioParserV2        # парсер YAML (новый)
│   ├── ScenarioParserV1        # обратная совместимость с JSON
│   └── ScenarioParserFactory   # выбирает по scenario_version
│
├── scenario.py
│   ├── LoopStep                # циклы
│   ├── ConditionStep           # if/elif/else/switch
│   ├── ImportStep              # импорт под-сценария
│   ├── DefCallStep             # вызов определения
│   ├── WaitStep                # sleep/wait_until
│   ├── RpcStep                 # внешние вызовы
│   └── FailPassSkipStep        # терминальные шаги
│
├── scenario_engine.py          # НОВЫЙ
│   ├── ScenarioStateMachine    # стейт-машина сценария
│   └── ScenarioDispatcher      # управление жизненным циклом
│
├── variable_resolver.py        # НОВЫЙ
│   ├── ExprResolver            # вычисляемые выражения
│   ├── FormatResolver          # форматированные строки
│   └── DataSourceResolver      # CSV, БД, файлы
│
└── capture_engine.py           # НОВЫЙ
    ├── TypeConverter           # преобразование типов
    ├── GuardFilter             # фильтрация по условию
    └── PathResolver            # вложенные пути с defaul`тами
```

### 12.2. Механизм интеграции

```
┌──────────────────────────────────────────────────────┐
│                   ScenarioManager                     │
│  ┌──────────────────────────────────────────────┐    │
│  │   ScenarioParserFactory                       │    │
│  │   ┌──────────┐  ┌──────────┐                  │    │
│  │   │ V1 Parser │  │ V2 Parser │  ← registry   │    │
│  │   └──────────┘  └──────────┘                  │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  ┌──────────────┐   ┌──────────────┐                  │
│  │ StepFactory  │ → │  Step Exec   │                  │
│  │ (SendStep,   │   │  (await)     │                  │
│  │  ExpectStep, │   └──────────────┘                  │
│  │  LoopStep…)  │         ↓                           │
│  └──────────────┘   ┌──────────────┐                  │
│                     │ EventBus     │← packet.processed │
│                     │              │← connection.change│
│                     └──────────────┘                  │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │ ScenarioStateMachine (опционально)            │    │
│  │  idle → connect → auth → running → ...       │    │
│  │  Подписан на connection.changed              │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

### 12.3. Что НЕ меняется

- `UsvStateMachine` в `core/session.py` — остаётся как есть
- `PacketPipeline` + middleware — остаются как есть
- `AutoResponseMiddleware` — продолжает генерировать RESPONSE
- `SessionManager` — без изменений
- V1 JSON-сценарии — продолжают работать через `ScenarioParserV1`

### 12.4. Что добавляется

- `ScenarioParserV2` — парсит YAML, возвращает `ScenarioDefinition` (может содержать вложенные `ScenarioDefinition` для импортов)
- `LoopStep`, `ConditionStep`, `ImportStep` и др. — новые типы шагов, регистрируются в `StepFactory`
- `ScenarioStateMachine` — опциональная стейт-машина для сценариев-диспетчеров
- `VariableResolver` / `CaptureEngine` — утилиты для работы с переменными и извлечения данных

### 12.5. Регистрация в engine.py

```python
from core.scenario_parser import (
    ScenarioParserFactory,
    ScenarioParserRegistry,
    ScenarioParserV2,
)

registry = ScenarioParserRegistry()
registry.register("1", ScenarioParserV1)
registry.register("2", ScenarioParserV2)       # новое

parser_factory = ScenarioParserFactory(registry=registry)
scenario_mgr = ScenarioManager(parser_factory=parser_factory)
```

---

## 13. Открытые вопросы

### Формат
- YAML — окончательно? Или оставить выбор (YAML + JSON + TOML)?
- Схема валидации — JSON Schema, Pydantic, или свой валидатор?

### Состояния
- Должен ли каждый сценарий быть стейт-машиной или только опционально?
- Как отображать состояния сценария на GUI (dashboard)?
- Нужен ли визуальный редактор? (далеко в будущее)

### Импорты
- Как разрешать конфликты переменных при импорте? (префиксы, явный export)
- Как быть с циклическими импортами?
- Background-импорты — как управлять их жизненным циклом (остановка, ошибка)?

### Циклы
- Нужен ли `for` по ключам словаря?
- `break`/`continue` — только по условию? Или явные шаги-команды?
- Параллельные циклы — как собирать результаты?

### Переменные
- `expr` — встроенный язык выражений (безопасный eval) или только резолверы?
- Нужны ли переменные уровня сессии (живут между запусками сценариев)?

### Совместимость
- V1 → V2 — автоматическая миграция? (конвертер JSON → YAML)
- Поддержка V1 в долгосрочной перспективе?

### Производительность
- Насколько глубокими могут быть импорты? (max_depth)
- Background-сценарии — как не плодить корутины?
- Ограничение на `max_iterations` в циклах?

### GUI
- Как отображать состояние V2-сценария в dashboard?
- Редактор стейт-машины — в какой форме?
- Визуализация выполнения (подсветка текущего состояния/шага)?
