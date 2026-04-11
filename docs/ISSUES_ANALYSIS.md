# Анализ проблем — OMEGA_EGTS

Известные проблемы, причины их появления, решения и извлечённые уроки.

**Обновлено:** 11.04.2026 | **ISSUE-003 решена**, **ISSUE-004 открыта:** FSM не переходит AUTHENTICATING → AUTHORIZED

---

## ISSUE-001: RESPONSE без RECORD_RESPONSE (16 байт вместо 29)

**Статус:** ✅ Решена | **Дата обнаружения:** 10.04.2026

| Мета-инфо | Значение |
|-----------|----------|
| **Выявлено на коммите** | `4cf7cda` (master, v1.0.0 100%) — интеграционные тесты показали RESPONSE 16 байт |
| **Решено на коммите** | `4b6eb67` (HEAD -> debug/manual-testing) — `build_response(records=...)`, ResponseRecord модель |
| **Тест обнаружения** | Ручной анализ hex RESPONSE в интеграционном тесте — пользователь заметил 16 байт вместо 29 |
| **Тест локализации** | `tests/integration/test_full_integration.py::TestFullIntegration` — побайтовый анализ RESPONSE показал отсутствие записей |
| **Тест подтверждения решения** | `tests/libs/egts_protocol_gost2015/test_adapter.py::TestBuildResponseWithRecord` (5 тестов) + `tests/integration/test_full_integration.py` (проверка RECORD_RESPONSE через `Packet.from_bytes()`) + `tests/integration/test_auth_scenario.py` (проверка 3 RESPONSE с RECORD_RESPONSE) |

### Описание

RESPONSE на TERM_IDENTITY содержал **16 байт** вместо ожидаемых **29 байт**.

| Параметр | Факт | Эталон | Разница |
|----------|------|--------|---------|
| Длина | 16 байт | 29 байт | -13 байт |
| FDL | 3 | 16 | Нет записей (SDR) |
| RECORD_RESPONSE | ❌ Отсутствует | ✅ RL=6, RN=45, CRN=73 | Критично |

По ГОСТ 33465-2015 раздел 6.8.1: платформа должна отправлять `EGTS_SR_RECORD_RESPONSE` на каждую запись входящего пакета.

### Причина

`adapter.build_response()` вызывался без информации о записях:

```python
def build_response(self, pid: int, result_code: int, **kwargs: object) -> bytes:
    internal_pkt = InternalPacket(
        ...,
        records=[],  # ← ПУСТОЙ СПИСОК — НЕТ ЗАПИСЕЙ
    )
```

`AutoResponseMiddleware` вызывал `build_response(pid, result_code=0)` без RN и SST входящих записей.

### Решение

1. Добавлен `build_response_with_record()` в адаптер — создаёт RESPONSE с RECORD_RESPONSE
2. `AutoResponseMiddleware` извлекает `records[0].record_id` из входящего пакета
3. Вызывает `build_response_with_record(pid, result_code=0, record_rn=rn)`

### Извлечённые уроки

| # | Урок |
|---|------|
| 1 | Не парсить байты вручную — использовать библиотеку `Packet.from_bytes()` + `parse_records()` |
| 2 | `_raw_data` заполняется только при парсинге, не при программном создании Record |
| 3 | Тесты должны проверять через библиотеку, не побайтовым анализом hex |
| 4 | `rsod=True` (RFL=0x40) — важный флаг: получатель записи на платформе, не на УСВ |

### Архитектурная рекомендация

Вместо плодящихся методов (`build_response_with_record`, `build_response_with_command`, ...) — единый метод с параметром `records`:

```python
protocol.build_response(pid=42, result_code=0, records=[ResponseRecord(...)])
```

Это позволит добавлять записи без новых методов интерфейса.

---

## ISSUE-002: ParseResult.extra пуст после parse_packet() (CR-016)

**Статус:** ✅ Решена | **Дата обнаружения:** 11.04.2026 | **Дата решения:** 11.04.2026

| Мета-инфо | Значение |
|-----------|----------|
| **Выявлено на коммите** | `4b6eb67` (debug/manual-testing) — интеграционный тест `test_auth_scenario_full.py` завис на ExpectStep |
| **Решено на коммите** | pending — `adapter.parse_packet()` заполняет `extra` из `packet.records[0]` |
| **Тест обнаружения** | `tests/integration/test_auth_scenario_full.py` — сценарий завис на ExpectStep, EventBus трейсинг показал `extra={}` |
| **Тест локализации** | `tests/core/test_cr016_parse_result_extra_empty.py` (4 теста) — подтвердил что `parse_packet()` возвращал `extra={}` |
| **Тест подтверждения решения** | `tests/core/test_cr016_parse_result_extra_empty.py::TestCR016_ParseResultExtraPopulated` (4 теста) + `tests/libs/egts_protocol_gost2015/test_adapter.py::test_parse_packet_populates_extra` + `test_parse_packet_extra_empty_when_no_records` |

### Описание

`ExpectStep._matches()` ищет `service` и `subrecord_type` в `packet_data.extra`, но `extra={}` после `parse_packet()`. Сценарии зависают на шагах `expect`.

**Подтверждено:** EventBus лог показывает `extra={}` для всех пакетов. Тест-демонстрация: `tests/core/test_cr016_parse_result_extra_empty.py`.

### Хронология появления бага

| Итерация | Что сделано | Где допущена ошибка |
|----------|-------------|---------------------|
| **2.1** | Создан `ParseResult` с `extra: dict[str, object]`, docstring: `"service, tid, imei, imsi"` | ✅ Контракт описан правильно |
| **2.3** | Реализован `EgtsProtocol2015.parse_packet()` | ❌ **Возвращает ParseResult без extra** — данные есть в `packet.records`, но не извлечены |
| **4.3** | Создан `ParseMiddleware` | ❌ **Не обогащает extra** — посчитал что адаптер уже заполнил |
| **4.x** | Тесты middleware используют **моки** с заполненным `extra` | ❌ **Тесты не ловят баг** — мокируют `parse_packet()` с `extra={"service": 1}` |
| **7.0** | Создан `ExpectStep._matches()` — читает `packet_data.extra` | ✅ Потребитель работает по контракту |
| **10.0** | Интеграционный тест — **сценарий зависает** | 💥 Баг обнаружен |

### Цепочка данных

```
1. adapter.parse_packet(raw)
   ├── Парсит пакет → packet.records[0].service_type = 1
   ├── records[0].subrecords[0].subrecord_type = "EGTS_SR_TERM_IDENTITY"
   └── Возвращает ParseResult(extra={})  ← ❌ extra не заполнен

2. ParseMiddleware.__call__()
   ├── ctx.parsed = parse_result
   └── Ничего не делает с extra  ← ❌ посчитал что адаптер заполнил

3. EventEmitMiddleware
   └── emit("packet.processed", {"parsed": ctx.parsed})
       └── ctx.parsed.extra = {}  ← ❌ пустой

4. ExpectStep._on_packet()
   ├── packet_data = ctx.parsed
   └── self._matches(packet_data.extra)  ← extra={}
       └── extra.get("service") → None  ← ❌ check провален
           └── STEP TIMEOUT
```

### Почему тесты не поймали

**`test_parse_middleware.py`** и **`test_scenario_manager.py`** мокают `parse_packet()`:

```python
parsed_mock = MagicMock()
parsed_mock.extra = {"service": 1}  # ← Заполнено вручную!
```

Тесты проходят потому что моки заполняют `extra`. Реальный `EgtsProtocol2015.parse_packet()` возвращает `extra={}`.

### Рекомендуемое решение

**Вариант A (архитектурно правильный):** `adapter.parse_packet()` извлекает метаданные:

```python
def parse_packet(self, data: bytes, **kwargs: object) -> ParseResult:
    # ... парсинг ...
    
    extra: dict[str, object] = {}
    if iface_packet.records:
        rec = iface_packet.records[0]
        extra["service"] = rec.service_type
        if rec.subrecords:
            extra["subrecord_type"] = rec.subrecords[0].subrecord_type
    
    return ParseResult(
        packet=iface_packet,
        errors=errors,
        warnings=warnings,
        raw_bytes=data,
        extra=extra,  # ← Заполнен!
    )
```

**Вариант B (middleware fallback):** `ParseMiddleware` обогащает `extra` если адаптер не заполнил.

**Рекомендация:** Вариант A — адаптер знает структуру EGTS, не должен делегировать middleware.

### Реализованное решение

**Изменённые файлы:**

| Файл | Изменение |
|------|-----------|
| `libs/egts_protocol_gost2015/adapter.py` | `parse_packet()` заполняет `extra` из `packet.records[0]` (service + subrecord_type если есть) |
| `tests/libs/egts_protocol_gost2015/test_adapter.py` | +2 теста: `test_parse_packet_populates_extra`, `test_parse_packet_extra_empty_when_no_records` |
| `tests/core/test_cr016_parse_result_extra_empty.py` | Переписан: с демонстрации бага → подтверждение исправления (4 теста PASS) |

**Замечание:** `subrecord_type` может быть `None` если `parse_records()` возвращает пустой список subrecords. Это отдельная проблема внутреннего парсера. `service=1` достаточно для ExpectStep матчинга.

### Профилактика повторения

| Мера | Где применить |
|------|---------------|
| Тест адаптера: проверять `extra` заполнен | `tests/libs/egts_protocol_gost2015/test_adapter.py` |
| Интеграционный тест: реальный `parse_packet()` → `extra` не пуст | `tests/core/test_parse_middleware.py` |
| Правило: моки ≠ интеграционные тесты | Документировать в PLAN.md |
| Контрактная валидация: `extra` документирован → тест должен проверить | Добавить в CI |

---

## Общие извлечённые уроки

### 1. Контракт без реализации — баг

Когда поле определено в модели (`extra: dict`) но не заполнено в реализации — тесты с моками это не поймают. **Правило:** если поле документировано — юнит-тест реальной реализации должен проверить его заполнение.

### 2. Моки скрывают интеграционные проблемы

Моки `MagicMock(extra={"service": 1})` проходят, реальный код — нет. **Правило:** наряду с моками — хотя бы один интеграционный тест с реальными данными.

### 3. Цепочка компонентов — слабое звено

Данные проходят: `adapter → middleware → event → consumer`. Если одно звено не заполняет — все последующие ломаются. **Правило:** каждый компонент должен либо заполнить, либо явно пропустить с warning.

### 4. Тесты должны использовать библиотеку, не ручной парсинг

Побайтовый анализ hex — источник ошибок в смещениях. **Правило:** тесты проверяют через `Packet.from_bytes()` + `parse_records()` + `Subrecord.from_bytes()`.

---

## Шаблон для будущих проблем

При добавлении новой проблемы заполняй:

| Поле | Описание |
|------|----------|
| **Выявлено на коммите** | `git hash` + ветка + при каких обстоятельствах |
| **Решено на коммите** | `git hash` + краткое описание фикса (или ❌ Не решено) |
| **Тест обнаружения** | Какой тест/пример/ручной анализ впервые показал проблему |
| **Тест локализации** | Какой тест изолировал корневую причину |
| **Тест подтверждения решения** | Какой тест проверяет что фикс работает (unit + integration) |

---

## ISSUE-003: ScenarioManager не выполняет сценарий авторизации

**Статус:** ✅ Решена | **Дата обнаружения:** 11.04.2026 | **Дата решения:** 11.04.2026

| Мета-инфо | Значение |
|-----------|----------|
| **Выявлено на коммите** | `4b6eb67` (debug/manual-testing) — `test_auth_scenario_full.py` FAIL |
| **Решено на коммите** | pending — 4 исправления + парсинг SRD RECORD_RESPONSE |
| **Тест обнаружения** | `tests/integration/test_auth_scenario_full.py` — сценарий застревает, нет `[КОМАНДА]` |
| **Тест локализации** | 8 тестов изоляции: `test_issue003_*.py` (4 core + 2 libs + 2 integration) |
| **Тест подтверждения** | `test_auth_scenario.py` — 4/4 PASS; `test_auth_scenario_full.py` — 6/6 шагов PASS |

### Хронология исправлений

| # | Исправление | Файл | Что сделано | Результат |
|---|-------------|------|-------------|-----------|
| 1 | **Record.from_bytes() не парсит subrecords** | `record.py` | Добавлен вызов `parse_subrecords()` после сохранения `_raw_data` | ✅ `subrecords` заполнен |
| 2 | **SubrecordType int → str** | `adapter.py` | `_map_subrecord_to_iface()` конвертирует `int` → `"EGTS_SR_TERM_IDENTITY"` | ✅ ExpectStep матчит по строке |
| 3 | **SendStep без connection_id** | `scenario.py` | `emit_data["connection_id"] = conn_id` | ✅ CommandDispatcher получает connection_id |
| 4 | **Парсинг RECORD_RESPONSE SRD** | `adapter.py` | Извлечение CRN + RST из SRD подзаписи → `extra["record_status"]` | ✅ `extra["record_status"] = 0` (EGTS_PC_OK) |
| 5 | **Сценарий auth/scenario.json** | `scenarios/auth/scenario.json` | `"rst": 0` → `"record_status": 0` | ✅ Шаг 6 PASS |

### Финальная цепочка данных

```
adapter.parse_packet(raw)
  ├─ Record.from_bytes() → subrecords=[Subrecord(subrecord_type=1, ...)]  ✅
  ├─ _map_subrecord_to_iface() → subrecord_type="EGTS_SR_TERM_IDENTITY"   ✅
  ├─ RECORD_RESPONSE SRD → extra["record_status"] = 0                     ✅
  └─ SendStep.execute() → emit_data={"connection_id": "...", ...}         ✅
```

### Результат интеграционного теста

```
[СЦЕНАРИЙ] Результат: PASS
  Идентификация терминала: PASS
  Подтверждение TERM_IDENTITY: PASS
  Данные транспортного средства: PASS
  Подтверждение VEHICLE_DATA: PASS
  Результат аутентификации: PASS
  Подтверждение результата: PASS
```

### Реализованное решение

**Изменённые файлы:**

| Файл | Изменение |
|------|-----------|
| `libs/egts_protocol_gost2015/gost2015_impl/record.py` | `from_bytes()` вызывает `parse_subrecords()` |
| `libs/egts_protocol_gost2015/adapter.py` | `_map_subrecord_to_iface()` → `SubrecordType(srt).name`; парсинг RECORD_RESPONSE SRD → `extra["record_status"]`, `extra["confirmed_record_number"]` |
| `core/scenario.py` | `SendStep.execute()` → `emit_data["connection_id"] = conn_id` |
| `scenarios/auth/scenario.json` | `"rst": 0` → `"record_status": 0` |
| `tests/libs/egts_protocol_gost2015/test_issue003_subrecords_empty.py` | 2 теста |
| `tests/core/test_issue003_expectstep_missing_subrecord.py` | 3 теста |
| `tests/core/test_issue003_scenario_execution.py` | 4 теста |
| `tests/core/test_issue003_sendstep_with_real_file.py` | 1 тест |

---

## ISSUE-004: FSM не переходит AUTHENTICATING → AUTHORIZED после успешной авторизации

**Статус:** 🔴 Открыта | **Дата обнаружения:** 11.04.2026

| Мета-инфо | Значение |
|-----------|----------|
| **Выявлено на коммите** | pending — `test_auth_scenario_full.py` FAIL после решения ISSUE-003 |
| **Решено на коммите** | ❌ Не решено |
| **Тест обнаружения** | `tests/integration/test_auth_scenario_full.py` — assertion `assert "authorized" in states_lower` FAIL |
| **Тест локализации** | ❌ Требуется |
| **Тест подтверждения решения** | ❌ Не создан |

### Описание

После успешного выполнения всех 6 шагов сценария авторизации, FSM остаётся в состоянии `authenticating`:

```
[ТЕСТ] FSM состояния: ['CONNECTED', 'authenticating']
Ожидалось: ['CONNECTED', 'authenticating', 'AUTHORIZED'] или ['CONNECTED', 'authenticating', 'RUNNING']
```

**Сценарий PASS** — все пакеты обработаны, RESPONSE отправлены, но FSM не получил переход `AUTHENTICATING → AUTHORIZED`.

### Возможные причины

| Гипотеза | Проверка |
|----------|----------|
| `SessionManager._on_packet_processed()` не вызывает `fsm.on_result_code_sent()` | Проверить что RESULT_CODE пакет триггерит переход |
| `on_result_code_sent(0)` не вызывается при отправке RESULT_CODE | Проверить `AutoResponseMiddleware` или `CommandDispatcher` |
| FSM ждёт `EGTS_SR_RESULT_CODE` но получает RESPONSE | Проверить что сервис RESULT_CODE распознаётся |
| Переход требует `service=9` (RESULT_CODE), но FSM видит `service=1` | Проверить что RESULT_CODE пакет имеет правильный service |

### Рекомендуемое решение

1. Добавить отладку в `SessionManager._on_packet_processed()`:
   - Проверить что `on_result_code_sent(0)` вызывается при RESULT_CODE
   - Проверить FSM переходы после каждого пакета
2. Создать юнит-тест: FSM AUTHENTICATING + RESULT_CODE(0) → AUTHORIZED
3. Если FSM не получает `on_result_code_sent()` — добавить вызов в `CommandDispatcher` или `SessionManager`
