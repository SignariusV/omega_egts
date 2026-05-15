# Исследование: Динамическая генерация пакетов в сценариях тестирования

> **Статус:** ⚠️ Устарел (April 2026)
>
> Этот документ — историческое исследование с этапа планирования. Основная информация:
> - Текущая реализация: `docs/ARCHITECTURE.md` (раздел "Способы отправки пакетов")
> - История изменений: `CHANGELOG.md`
> - Код: `core/scenario.py`, `core/scenario_parser.py`

## Резюме

Данный документ содержит подробный анализ текущей архитектуры системы тестирования УСВ (Устройств Сбора и Передачи Данных) и предлагает решение для перехода от использования статических HEX-файлов к динамической генерации пакетов на лету в сценариях тестирования.

**Текущее состояние:** Сценарии используют заранее подготовленные HEX-файлы (`packets/platform/*.hex`), содержащие сериализованные EGTS-пакеты.

**Целевое состояние:** Сценарии должны описывать пакеты декларативно (через структуру данных), а система должна собирать байты пакета на лету во время выполнения шага, сохраняя при этом возможность использования HEX-файлов для обратной совместимости.

---

## 1. Анализ текущего состояния

### 1.1. Архитектура сценариев

#### 1.1.1. Формат сценариев (V1)

Сценарии описываются в формате JSON версии 1 (`scenario_version: "1"`). Пример структуры:

```json
{
  "name": "Передача траектории движения",
  "scenario_version": "1",
  "gost_version": "ГОСТ 33465-2015",
  "timeout": 60,
  "description": "Платформа запрашивает траекторию через SMS, УСВ передаёт данные по TCP/IP",
  "channels": ["tcp", "sms"],
  "steps": [
    {
      "name": "SMS-запрос траектории",
      "type": "send",
      "channel": "sms",
      "packet_type": "EGTS_TRACK_DATA",
      "packet_file": "packets/platform/track_data_request.hex",
      "timeout": 10,
      "description": "Платформа запрашивает траекторию через SMS"
    }
  ]
}
```

#### 1.1.2. Типы шагов

| Тип | Описание | Кто отправляет | Источник пакета |
|-----|----------|----------------|-----------------|
| `send` | Отправка пакета | Платформа → УСВ | HEX-файл или build-template |
| `expect` | Ожидание пакета | УСВ → Платформа | Проверка по полям |
| `wait` | Резерв (не реализован) | — | — |
| `check` | Резерв (не реализован) | — | — |

#### 1.1.3. Текущий механизм отправки пакетов

Класс `SendStep` (`core/scenario.py`) отвечает за отправку пакетов:

```python
@dataclass
class SendStep:
    name: str
    packet_file: str | None = None      # Путь к HEX-файлу
    build: dict[str, Any] | None = None # Template для динамической генерации
    channel: str | None = None
    timeout: float | None = None
```

**Метод `_build_packet()`:**
```python
def _build_packet(self, ctx: ScenarioContext) -> bytes:
    if not self.packet_file:
        raise ValueError("packet_file is required")
    
    path = Path(self.packet_file)
    hex_text = path.read_text().strip()
    return bytes.fromhex(hex_text)
```

**Метод `_build_from_template()`:**
```python
def _build_from_template(self, ctx: ScenarioContext) -> dict[str, Any]:
    if not self.build:
        raise ValueError("build template is required")
    
    def _substitute(obj: Any) -> Any:
        if isinstance(obj, str):
            return ctx.substitute(obj)
        if isinstance(obj, dict):
            return {k: _substitute(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_substitute(item) for item in obj]
        return obj
    
    result: dict[str, Any] = _substitute(self.build)
    return result
```

**Поле `build` уже существует**, но не используется в текущих сценариях. Оно предназначено для динамической генерации пакетов.

### 1.2. Структура EGTS-пакета (ГОСТ 33465-2015)

#### 1.2.1. Транспортный уровень

```
┌─────────────────────────────────────────────────────┐
│ Заголовок (11 или 15 байт) + SFRD + CRC-16          │
└─────────────────────────────────────────────────────┘
```

**Заголовок (11 байт базовый):**
| Смещение | Поле | Размер | Описание |
|----------|------|--------|----------|
| 0 | PRV | 1 | Версия протокола (1 для ГОСТ 2015) |
| 1 | SKID | 1 | Идентификатор ключа безопасности |
| 2 | Flags | 1 | Флаги (PRF, RTE, ENA, CMP, PR) |
| 3 | HL | 1 | Длина заголовка (11 или 15) |
| 4 | HE | 1 | Кодировка заголовка |
| 5-6 | FDL | 2 | Длина данных (SFRD) |
| 7-8 | PID | 2 | Номер пакета |
| 9 | PT | 1 | Тип пакета (0=RESPONSE, 1=APPDATA, 2=SIGNED) |
| 10 | HCS | 1 | CRC-8 заголовка |

**Опционально (при RTE=1, +4 байта):**
| Смещение | Поле | Размер | Описание |
|----------|------|--------|----------|
| 11 | PRA | 2 | Адрес отправителя |
| 12-13 | RCA | 2 | Адрес получателя |
| 14 | TTL | 1 | Время жизни |

#### 1.2.2. Уровень поддержки услуг (SFRD)

**Для APPDATA (PT=1):**
```
Запись 1 + Запись 2 + ...
```

**Структура записи:**
| Поле | Размер | Описание |
|------|--------|----------|
| RL | 2 | Длина RD (payload) |
| RN | 2 | Номер записи |
| RFL | 1 | Флаги (SSOD, RSOD, RPP, OBFE, EVFE, TMFE) |
| OID | 4 | Идентификатор объекта (если OBFE=1) |
| EVID | 2 | Идентификатор события (если EVFE=1) |
| TM | 4 | Метка времени (если TMFE=1) |
| SST | 1 | Сервис-отправитель |
| RST | 1 | Сервис-получатель |
| RD | RL | Подзаписи |

#### 1.2.3. Подзаписи

| Поле | Размер | Описание |
|------|--------|----------|
| SRT | 1 | Тип подзаписи |
| SRL | 2 | Длина данных |
| SRD | SRL | Данные подзаписи |

### 1.3. Существующая библиотека сборки пакетов

#### 1.3.1. Модели данных (`libs/egts/models.py`)

```python
@dataclass
class Packet:
    protocol_version: int = 1
    security_key_id: int = 0
    prefix: bool = False
    routing: bool = False
    encryption: int = 0
    compressed: bool = False
    priority: int = 0
    header_encoding: int = 0
    packet_id: int = 0
    packet_type: int = 0  # 0=RESPONSE, 1=APPDATA, 2=SIGNED
    
    # Опциональные (только при RTE=1)
    peer_address: int | None = None
    recipient_address: int | None = None
    ttl: int | None = None
    
    # RESPONSE-only (PT=0)
    response_packet_id: int | None = None
    processing_result: int | None = None
    
    # Данные уровня поддержки услуг
    records: list['Record'] = field(default_factory=list)


@dataclass
class Record:
    record_id: int = 0
    service_type: int = 0
    recipient_service_type: int = 0
    subrecords: list['Subrecord'] = field(default_factory=list)
    
    # Опциональные (по флагам RFL)
    object_id: int | None = None
    event_id: int | None = None
    timestamp: int | None = None
    
    # Флаги RFL
    ssod: bool = False
    rsod: bool = False
    rpp: int = 0


@dataclass
class Subrecord:
    subrecord_type: int = 0
    data: dict[str, object] | bytes = field(default_factory=dict)
    raw_bytes: bytes = field(default_factory=bytes, repr=False)
    parse_error: str | None = None
```

#### 1.3.2. Сборщик пакетов (`libs/egts/_core/builder.py`)

Функция `build_full_packet(packet: Packet) -> bytes`:
1. Сериализует записи в байты через `serialize_record()`
2. Сериализует подзаписи через `serialize_subrecord()`
3. Собирает заголовок с правильным FDL и HCS (CRC-8)
4. Добавляет CRC-16 от SFRD

**Пример использования:**
```python
from libs.egts.models import Packet, Record, Subrecord
from libs.egts._gost2015.protocol import Gost2015Protocol

protocol = Gost2015Protocol()

pkt = Packet(
    packet_id=22,
    packet_type=1,  # APPDATA
    records=[
        Record(
            record_id=37,
            service_type=4,  # COMMANDS_SERVICE
            recipient_service_type=4,
            subrecords=[
                Subrecord(
                    subrecord_type=51,  # EGTS_SR_COMMAND_DATA
                    data={'ct': 5, 'cct': 0, 'cid': 0, 'sid': 0, 'cd': b'\x00\x00\x01\x14\x01'}
                )
            ]
        )
    ]
)

packet_bytes = protocol.build_packet(pkt)
```

### 1.4. Существующие HEX-файлы в сценариях

| Сценарий | Файл | Размер (байт) | Описание |
|----------|------|---------------|----------|
| track | `packets/platform/track_data_request.hex` | 38 | Запрос траектории |
| track | `packets/platform/record_response_track.hex` | 29 | RESPONSE на траекторию |
| accel | `packets/platform/accel_data_request.hex` | 38 | Запрос профиля ускорения |
| auth | `packets/platform/record_response_term_identity.hex` | 29 | RESPONSE на TERM_IDENTITY |
| auth | `packets/platform/result_code.hex` | 42 | RESULT_CODE (аутентификация успешна) |
| commands | `packets/platform/command_data.hex` | 38 | Команда конфигурирования |

**Анализ одного пакета (track_data_request.hex):**
```
Hex: 0100000B001900160001B512002500400404330F00500000000000000000000000011401EB6C

Разбор:
- PRV=1 (ГОСТ 2015)
- HL=11 (без маршрутизации)
- FDL=25 (длина SFRD)
- PID=22
- PT=37 (должно быть 1=APPDATA, но 37=0x25 — это SST сервиса!)

Запись:
- RL=36 (длина RD)
- RN=37
- RFL=0x40 (RSOD=1, получатель на платформе)
- SST=4 (COMMANDS_SERVICE)
- RST=4 (COMMANDS_SERVICE)

Подзапись:
- SRT=51 (EGTS_SR_COMMAND_DATA)
- SRL=16
- SRD: ct=5, cct=0, cid=0, sid=0, cd=b'\x00\x00\x01\x14\x01'
```

---

## 2. Способы решения проблемы

### 2.1. Вариант 1: Декларативное описание пакетов в сценарии

**Идея:** Добавить новое поле `packet_template` в определение шага `send`, которое содержит полную структуру пакета в виде JSON.

**Преимущества:**
- Полная видимость структуры пакета в сценарии
- Возможность версионирования пакетов вместе со сценарием
- Не требуется внешняя документация структуры пакета

**Недостатки:**
- Увеличение размера сценариев
- Дублирование структуры между сценариями
- Сложность поддержки при изменении формата EGTS

**Пример:**
```json
{
  "name": "Запрос траектории",
  "type": "send",
  "channel": "sms",
  "packet_template": {
    "packet_id": 22,
    "packet_type": 1,
    "records": [
      {
        "record_id": 37,
        "service_type": 4,
        "recipient_service_type": 4,
        "rsod": true,
        "subrecords": [
          {
            "subrecord_type": 51,
            "data": {
              "ct": 5,
              "cct": 0,
              "cid": 0,
              "sid": 0,
              "cd": "0000011401"
            }
          }
        ]
      }
    ]
  }
}
```

### 2.2. Вариант 2: Именованные шаблоны пакетов

**Идея:** Создать реестр именованных шаблонов пакетов, которые ссылаются на функции-билдеры.

**Преимущества:**
- Централизованное управление шаблонами
- Возможность параметризации
- Переиспользование между сценариями

**Недостатки:**
- Требуется регистрация шаблонов в коде
- Меньшая гибкость для уникальных пакетов

**Пример:**
```json
{
  "name": "Запрос траектории",
  "type": "send",
  "channel": "sms",
  "build": {
    "template": "track_data_request",
    "params": {
      "packet_id": 22,
      "record_id": 37,
      "command_type": 5
    }
  }
}
```

### 2.3. Вариант 3: Гибридный подход (рекомендуемый)

**Идея:** Использовать существующее поле `build` для декларативного описания пакета на основе моделей `Packet`, `Record`, `Subrecord`. Сохранить поддержку `packet_file` для обратной совместимости.

**Преимущества:**
- Использует существующую инфраструктуру (`build` поле уже есть)
- Обратная совместимость с HEX-файлами
- Использует существующие модели данных
- Минимальные изменения в коде

**Недостатки:**
- Требует обновления существующих сценариев (опционально)

**Пример:**
```json
{
  "name": "Запрос траектории",
  "type": "send",
  "channel": "sms",
  "build": {
    "packet": {
      "packet_id": 22,
      "packet_type": 1,
      "records": [
        {
          "record_id": 37,
          "service_type": 4,
          "recipient_service_type": 4,
          "rsod": true,
          "subrecords": [
            {
              "subrecord_type": 51,
              "data": {
                "ct": 5,
                "cct": 0,
                "cid": 0,
                "sid": 0,
                "cd_hex": "0000011401"
              }
            }
          ]
        }
      ]
    }
  }
}
```

---

## 3. Рекомендуемое решение: Детальный план

### 3.1. Архитектурные изменения

#### 3.1.1. Расширение StepDefinition

Добавить поддержку нового формата `build` в `StepDefinition` (`core/scenario_parser.py`):

```python
@dataclass
class StepDefinition:
    name: str
    type: str
    channel: str | None
    timeout: float | None
    checks: dict[str, Any] = field(default_factory=dict)
    capture: dict[str, str] = field(default_factory=dict)
    packet_file: str | None = None
    build: dict[str, Any] | None = None  # Уже существует
    extra: dict[str, Any] = field(default_factory=dict)
```

**Новая структура `build`:**
```python
build = {
    "packet": {           # Структура Packet
        "packet_id": 22,
        "packet_type": 1,
        "protocol_version": 1,
        "records": [...]
    },
    "gost_version": "2015"  # Опционально, по умолчанию из сценария
}
```

#### 3.1.2. Модификация SendStep

Изменить метод `_build_from_template()` в `SendStep` (`core/scenario.py`):

```python
def _build_from_template(self, ctx: ScenarioContext) -> bytes:
    """Построить пакет из build-template с подстановкой переменных.
    
    Returns:
        Байты собранного EGTS-пакета.
    """
    if not self.build:
        raise ValueError("build template is required")
    
    def _substitute(obj: Any) -> Any:
        if isinstance(obj, str):
            return ctx.substitute(obj)
        if isinstance(obj, dict):
            return {k: _substitute(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_substitute(item) for item in obj]
        return obj
    
    # Применяем подстановку переменных
    template_data: dict[str, Any] = _substitute(self.build)
    
    # Извлекаем структуру пакета
    packet_dict = template_data.get("packet")
    if not packet_dict:
        raise ValueError("'packet' key is required in build template")
    
    # Получаем версию ГОСТ
    gost_version = template_data.get("gost_version", "2015")
    
    # Создаём протокол
    from core.egts_adapter import create_protocol
    protocol = create_protocol(gost_version)
    
    # Конвертируем dict в модель Packet
    packet = self._dict_to_packet(packet_dict)
    
    # Собираем байты
    return protocol.build_packet(packet)


def _dict_to_packet(self, data: dict[str, Any]) -> Packet:
    """Конвертировать dict в модель Packet."""
    from libs.egts.models import Packet, Record, Subrecord
    
    # Обработка hex-строк в binary
    def _convert_hex(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k.endswith("_hex") and isinstance(v, str):
                    result[k[:-4]] = bytes.fromhex(v)
                else:
                    result[k] = _convert_hex(v)
            return result
        elif isinstance(obj, list):
            return [_convert_hex(item) for item in obj]
        return obj
    
    data = _convert_hex(data)
    
    # Создаём подзаписи
    subrecords = []
    for sr_data in data.get("subrecords", []):
        sr = Subrecord(
            subrecord_type=sr_data["subrecord_type"],
            data=sr_data.get("data", {})
        )
        subrecords.append(sr)
    
    # Создаём записи
    records = []
    for rec_data in data.get("records", []):
        rec = Record(
            record_id=rec_data["record_id"],
            service_type=rec_data["service_type"],
            recipient_service_type=rec_data.get("recipient_service_type", 0),
            subrecords=subrecords,
            object_id=rec_data.get("object_id"),
            event_id=rec_data.get("event_id"),
            timestamp=rec_data.get("timestamp"),
            ssod=rec_data.get("ssod", False),
            rsod=rec_data.get("rsod", False),
            rpp=rec_data.get("rpp", 0)
        )
        records.append(rec)
    
    # Создаём пакет
    packet = Packet(
        protocol_version=data.get("protocol_version", 1),
        security_key_id=data.get("security_key_id", 0),
        prefix=data.get("prefix", False),
        routing=data.get("routing", False),
        encryption=data.get("encryption", 0),
        compressed=data.get("compressed", False),
        priority=data.get("priority", 0),
        header_encoding=data.get("header_encoding", 0),
        packet_id=data.get("packet_id", 0),
        packet_type=data.get("packet_type", 0),
        peer_address=data.get("peer_address"),
        recipient_address=data.get("recipient_address"),
        ttl=data.get("ttl"),
        response_packet_id=data.get("response_packet_id"),
        processing_result=data.get("processing_result"),
        records=records
    )
    
    return packet
```

#### 3.1.3. Приоритет источников пакета

Изменить логику выбора источника пакета в `SendStep.execute()`:

```python
async def execute(self, ctx: ScenarioContext, bus: EventBus, 
                  timeout: float | None = None) -> str:
    # ...
    
    # Построение пакета (новый приоритет)
    pid: int | None = None
    rn: int | None = None
    
    if self.build:
        # Приоритет 1: build-template (динамическая генерация)
        packet_bytes = self._build_from_template(ctx)
        # Извлечение PID/RN из собранного пакета
        packet_bytes_obj = self._parse_packet_bytes_for_pid_rn(packet_bytes)
        pid = packet_bytes_obj.get("pid")
        rn = packet_bytes_obj.get("rn")
    elif self.packet_file:
        # Приоритет 2: HEX-файл (обратная совместимость)
        packet_bytes = self._build_packet(ctx)
    else:
        logger.error("SendStep: packet_file or build required")
        return "ERROR"
    
    # ...
```

### 3.2. Примеры использования

#### 3.2.1. Простой RESPONSE-пакет

**Было (HEX-файл):**
```json
{
  "name": "Подтверждение TERM_IDENTITY",
  "type": "send",
  "channel": "tcp",
  "packet_file": "packets/platform/record_response_term_identity.hex"
}
```

**Стало (динамическая генерация):**
```json
{
  "name": "Подтверждение TERM_IDENTITY",
  "type": "send",
  "channel": "tcp",
  "build": {
    "packet": {
      "packet_id": "{{next_pid}}",
      "packet_type": 0,
      "response_packet_id": "{{last_pid}}",
      "processing_result": 0,
      "records": [
        {
          "record_id": "{{last_rn}}",
          "service_type": 1,
          "recipient_service_type": 0,
          "rsod": true,
          "subrecords": [
            {
              "subrecord_type": 0,
              "data": {
                "crn": "{{last_rn}}",
                "rst": 0
              }
            }
          ]
        }
      ]
    }
  }
}
```

#### 3.2.2. Запрос команды (COMMAND_DATA)

```json
{
  "name": "Команда конфигурирования",
  "type": "send",
  "channel": "tcp",
  "build": {
    "packet": {
      "packet_id": 22,
      "packet_type": 1,
      "records": [
        {
          "record_id": 37,
          "service_type": 4,
          "recipient_service_type": 4,
          "rsod": true,
          "subrecords": [
            {
              "subrecord_type": 51,
              "data": {
                "ct": 5,
                "cct": 0,
                "cid": 0,
                "sid": 0,
                "cd_hex": "0000011401"
              }
            }
          ]
        }
      ]
    }
  }
}
```

#### 3.2.3. RESULT_CODE (аутентификация)

```json
{
  "name": "Результат аутентификации",
  "type": "send",
  "channel": "tcp",
  "build": {
    "packet": {
      "packet_id": "{{next_pid}}",
      "packet_type": 1,
      "records": [
        {
          "record_id": "{{next_rn}}",
          "service_type": 1,
          "recipient_service_type": 0,
          "rsod": true,
          "subrecords": [
            {
              "subrecord_type": 4,
              "data": {
                "result_code": 0
              }
            }
          ]
        }
      ]
    }
  }
}
```

### 3.3. Подстановка переменных

Система должна поддерживать подстановку переменных контекста в шаблоне пакета:

**Специальные переменные:**
| Переменная | Описание | Источник |
|------------|----------|----------|
| `{{next_pid}}` | Следующий Packet ID | SessionManager.next_pid |
| `{{next_rn}}` | Следующий Record Number | SessionManager.next_rn |
| `{{last_pid}}` | Последний полученный PID | Из последнего пакета |
| `{{last_rn}}` | Последний полученный RN | Из последнего пакета |
| `{{tid}}` | Terminal ID | Capture из шага expect |
| `{{imei}}` | IMEI устройства | Capture из шага expect |

**Пример использования:**
```json
{
  "name": " RESPONSE с использованием переменных",
  "type": "send",
  "build": {
    "packet": {
      "packet_id": "{{next_pid}}",
      "packet_type": 0,
      "response_packet_id": "{{last_pid}}",
      "processing_result": 0,
      "records": [
        {
          "record_id": "{{last_rn}}",
          "service_type": 1,
          "rsod": true,
          "subrecords": [
            {
              "subrecord_type": 0,
              "data": {
                "crn": "{{last_rn}}",
                "rst": 0
              }
            }
          ]
        }
      ]
    }
  }
}
```

---

## 4. Критерии успешности

### 4.1. Функциональные критерии

| № | Критерий | Статус |
|---|----------|--------|
| 1 | Система поддерживает оба формата: HEX-файлы и build-templates | Обязательно |
| 2 | Build-templates корректно собирают пакеты всех типов (RESPONSE, APPDATA) | Обязательно |
| 3 | Подстановка переменных `{{var}}` работает во всех полях шаблона | Обязательно |
| 4 | Специальные переменные `{{next_pid}}`, `{{next_rn}}` работают | Обязательно |
| 5 | CRC-8 заголовка и CRC-16 данных рассчитываются корректно | Обязательно |
| 6 | Собранные пакеты проходят валидацию на стороне УСВ | Обязательно |
| 7 | Обратная совместимость: старые сценарии с HEX-файлами работают без изменений | Обязательно |

### 4.2. Технические критерии

| № | Критерий | Метрика |
|---|----------|---------|
| 1 | Время сборки пакета | < 10 мс на пакет |
| 2 | Покрытие тестами | ≥ 90% кода сборщика |
| 3 | Отсутствие регрессий | Все существующие тесты проходят |
| 4 | Документация | Обновлены README, примеры, API doc |

### 4.3. Критерии качества кода

| № | Критерий |
|---|----------|
| 1 | Код соответствует existing code style (type hints, docstrings) |
| 2 | Нет дублирования логики между HEX и build-путями |
| 3 | Логирование ошибок сборки пакетов |
| 4 | Валидация входных данных шаблона |

---

## 5. План реализации

### Этап 1: Подготовка (1-2 дня)

1. **Анализ существующих HEX-файлов**
   - Распарсить все HEX-файлы в сценариях
   - Создать эталонные структуры Packet для каждого
   - Документировать различия между типами пакетов

2. **Создание utility-функций**
   - Функция конвертации Hex → Packet (для отладки)
   - Функция валидации структуры шаблона

### Этап 2: Реализация (3-5 дней)

1. **Модификация SendStep**
   - Добавить метод `_dict_to_packet()`
   - Обновить `_build_from_template()` для работы с Packet
   - Добавить приоритет build над packet_file

2. **Поддержка переменных**
   - Расширить `ScenarioContext.substitute()` для специальных переменных
   - Добавить методы получения `next_pid`, `next_rn` из SessionManager

3. **Валидация шаблонов**
   - Добавить валидацию структуры build-шаблона
   - Логирование ошибок с указанием пути к проблемному полю

### Этап 3: Тестирование (2-3 дня)

1. **Юнит-тесты**
   - Тесты на конвертацию dict → Packet
   - Тесты на сборку пакетов разных типов
   - Тесты на подстановку переменных

2. **Интеграционные тесты**
   - Запуск существующих сценариев (обратная совместимость)
   - Запуск новых сценариев с build-templates
   - Сравнение HEX-выхода с эталонными файлами

### Этап 4: Документация (1 день)

1. Обновление `scenarios/README.md`
2. Создание примеров build-templates
3. Документирование специальных переменных

---

## 6. Тесты

### 6.1. Юнит-тесты

#### 6.1.1. Тест конвертации dict → Packet

```python
# tests/core/test_scenario_build.py

import pytest
from core.scenario import SendStep
from libs.egts.models import Packet, Record, Subrecord


class TestDictToPacketConversion:
    
    def test_simple_response_packet(self):
        """Конвертация простого RESPONSE-пакета."""
        step = SendStep(name="test")
        
        packet_dict = {
            "packet_id": 10,
            "packet_type": 0,
            "response_packet_id": 5,
            "processing_result": 0,
            "records": [
                {
                    "record_id": 5,
                    "service_type": 1,
                    "rsod": True,
                    "subrecords": [
                        {
                            "subrecord_type": 0,
                            "data": {"crn": 5, "rst": 0}
                        }
                    ]
                }
            ]
        }
        
        packet = step._dict_to_packet(packet_dict)
        
        assert packet.packet_id == 10
        assert packet.packet_type == 0
        assert packet.response_packet_id == 5
        assert len(packet.records) == 1
        assert packet.records[0].record_id == 5
        assert packet.records[0].service_type == 1
    
    def test_hex_to_binary_conversion(self):
        """Конвертация hex-строк в binary."""
        step = SendStep(name="test")
        
        packet_dict = {
            "packet_id": 22,
            "packet_type": 1,
            "records": [
                {
                    "record_id": 37,
                    "service_type": 4,
                    "subrecords": [
                        {
                            "subrecord_type": 51,
                            "data": {
                                "cd_hex": "0000011401"
                            }
                        }
                    ]
                }
            ]
        }
        
        packet = step._dict_to_packet(packet_dict)
        
        assert packet.records[0].subrecords[0].data["cd"] == b'\x00\x00\x01\x14\x01'
        assert "cd_hex" not in packet.records[0].subrecords[0].data
    
    def test_nested_hex_conversion(self):
        """Конвертация hex в nested структурах."""
        step = SendStep(name="test")
        
        packet_dict = {
            "packet_id": 1,
            "packet_type": 1,
            "records": [
                {
                    "record_id": 1,
                    "service_type": 1,
                    "subrecords": [
                        {
                            "subrecord_type": 1,
                            "data": {
                                "nested": {
                                    "value_hex": "ABCD"
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        packet = step._dict_to_packet(packet_dict)
        
        assert packet.records[0].subrecords[0].data["nested"]["value"] == b'\xAB\xCD'
```

#### 6.1.2. Тест сборки пакета

```python
class TestPacketBuilding:
    
    def test_build_response_packet(self):
        """Сборка RESPONSE-пакета и сравнение с эталоном."""
        step = SendStep(name="test")
        
        packet_dict = {
            "packet_id": 10,
            "packet_type": 0,
            "response_packet_id": 5,
            "processing_result": 0,
            "records": [
                {
                    "record_id": 5,
                    "service_type": 1,
                    "rsod": True,
                    "subrecords": [
                        {
                            "subrecord_type": 0,
                            "data": {"crn": 5, "rst": 0}
                        }
                    ]
                }
            ]
        }
        
        packet = step._dict_to_packet(packet_dict)
        packet_bytes = step._build_packet_from_dict(packet_dict)
        
        # Проверяем длину (должна быть 29 байт для RESPONSE с одной записью)
        assert len(packet_bytes) == 29
        
        # Проверяем CRC
        from libs.egts._gost2015.protocol import Gost2015Protocol
        protocol = Gost2015Protocol()
        result = protocol.parse_packet(packet_bytes)
        
        assert result.is_success
        assert result.packet.packet_id == 10
        assert result.packet.packet_type == 0
    
    def test_build_command_data_packet(self):
        """Сборка пакета COMMAND_DATA."""
        step = SendStep(name="test")
        
        packet_dict = {
            "packet_id": 22,
            "packet_type": 1,
            "records": [
                {
                    "record_id": 37,
                    "service_type": 4,
                    "recipient_service_type": 4,
                    "rsod": True,
                    "subrecords": [
                        {
                            "subrecord_type": 51,
                            "data": {
                                "ct": 5,
                                "cct": 0,
                                "cid": 0,
                                "sid": 0,
                                "cd_hex": "0000011401"
                            }
                        }
                    ]
                }
            ]
        }
        
        packet_bytes = step._build_packet_from_dict(packet_dict)
        
        # Сравниваем с эталонным HEX
        expected_hex = "0100000B001900160001B512002500400404330F00500000000000000000000000011401EB6C"
        assert packet_bytes.hex().upper() == expected_hex
```

#### 6.1.3. Тест подстановки переменных

```python
class TestVariableSubstitution:
    
    def test_simple_variable_substitution(self):
        """Подстановка простых переменных."""
        from core.scenario import ScenarioContext
        
        ctx = ScenarioContext()
        ctx.set("tid", 12345)
        ctx.set("imei", "123456789012345")
        
        step = SendStep(name="test")
        step.build = {
            "packet": {
                "packet_id": "{{tid}}",
                "records": [
                    {
                        "record_id": 1,
                        "service_type": 1,
                        "subrecords": [
                            {
                                "subrecord_type": 1,
                                "data": {
                                    "TID": "{{tid}}",
                                    "IMEI": "{{imei}}"
                                }
                            }
                        ]
                    }
                ]
            }
        }
        
        packet_dict = step._build_from_template(ctx)
        
        assert packet_dict["packet"]["packet_id"] == "12345"
        assert packet_dict["packet"]["records"][0]["subrecords"][0]["data"]["TID"] == "12345"
        assert packet_dict["packet"]["records"][0]["subrecords"][0]["data"]["IMEI"] == "123456789012345"
    
    def test_special_variables(self):
        """Подстановка специальных переменных next_pid, next_rn."""
        from core.scenario import ScenarioContext
        
        ctx = ScenarioContext()
        ctx.set("next_pid", 100)
        ctx.set("next_rn", 200)
        
        step = SendStep(name="test")
        step.build = {
            "packet": {
                "packet_id": "{{next_pid}}",
                "records": [
                    {
                        "record_id": "{{next_rn}}",
                        "service_type": 1
                    }
                ]
            }
        }
        
        packet_dict = step._build_from_template(ctx)
        
        assert packet_dict["packet"]["packet_id"] == "100"
        assert packet_dict["packet"]["records"][0]["record_id"] == "200"
```

### 6.2. Интеграционные тесты

#### 6.2.1. Тест обратной совместимости

```python
# tests/integration/test_scenario_backward_compat.py

import pytest
from pathlib import Path
from core.scenario import ScenarioManager
from core.scenario_parser import ScenarioParserFactory, ScenarioParserRegistry, ScenarioParserV1


class TestBackwardCompatibility:
    
    @pytest.mark.parametrize("scenario_path", [
        "scenarios/auth/scenario.json",
        "scenarios/track/scenario.json",
        "scenarios/accel/scenario.json",
        "scenarios/commands/scenario.json",
    ])
    def test_existing_scenarios_still_work(self, scenario_path):
        """Существующие сценарии с HEX-файлами работают без изменений."""
        full_path = Path(scenario_path)
        if not full_path.exists():
            pytest.skip(f"Scenario {scenario_path} not found")
        
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)
        
        manager = ScenarioManager(bus=Mock(), parser_factory=factory, step_factory=StepFactory())
        manager.load(full_path)
        
        # Проверяем, что шаги загружены
        assert len(manager._steps) > 0
        
        # Проверяем, что send-шаги имеют packet_file
        send_steps = [s for s in manager._steps if s.type == "send"]
        for step in send_steps:
            assert step.packet_file is not None
```

#### 6.2.2. Тест новых сценариев с build-templates

```python
# tests/integration/test_scenario_build_templates.py

import pytest
from core.scenario import ScenarioManager, SendStep, ScenarioContext
from core.event_bus import EventBus


class TestBuildTemplates:
    
    def test_full_scenario_with_build_templates(self):
        """Полный сценарий с использованием build-templates."""
        
        scenario_data = {
            "name": "Тест с build-templates",
            "scenario_version": "1",
            "gost_version": "ГОСТ 33465-2015",
            "timeout": 30,
            "steps": [
                {
                    "name": "Отправка RESPONSE через build",
                    "type": "send",
                    "channel": "tcp",
                    "build": {
                        "packet": {
                            "packet_id": 10,
                            "packet_type": 0,
                            "response_packet_id": 5,
                            "processing_result": 0,
                            "records": [
                                {
                                    "record_id": 5,
                                    "service_type": 1,
                                    "rsod": True,
                                    "subrecords": [
                                        {
                                            "subrecord_type": 0,
                                            "data": {"crn": 5, "rst": 0}
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            ]
        }
        
        # Загружаем сценарий
        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        factory = ScenarioParserFactory(registry)
        
        manager = ScenarioManager(bus=EventBus(), parser_factory=factory, step_factory=StepFactory())
        manager._load_from_dict(scenario_data)
        
        # Выполняем шаг
        step = manager._steps[0]
        assert isinstance(step, SendStep)
        
        ctx = ScenarioContext()
        result = asyncio.run(step.execute(ctx, EventBus()))
        
        assert result == "PASS"
```

### 6.3. Тесты на сравнение с эталонами

```python
# tests/core/test_packet_roundtrip.py

import pytest
from pathlib import Path
from libs.egts._gost2015.protocol import Gost2015Protocol


class TestPacketRoundtrip:
    """Тесты на круговое преобразование: HEX → Packet → HEX."""
    
    @pytest.mark.parametrize("hex_file", [
        "scenarios/track/packets/platform/track_data_request.hex",
        "scenarios/auth/packets/platform/record_response_term_identity.hex",
        "scenarios/commands/packets/platform/command_data.hex",
    ])
    def test_hex_to_packet_to_hex(self, hex_file):
        """Распаковка HEX в Packet и обратно даёт идентичный результат."""
        full_path = Path(hex_file)
        if not full_path.exists():
            pytest.skip(f"File {hex_file} not found")
        
        # Читаем эталонный HEX
        expected_hex = full_path.read_text().strip().upper()
        expected_bytes = bytes.fromhex(expected_hex)
        
        # Парсим в Packet
        protocol = Gost2015Protocol()
        result = protocol.parse_packet(expected_bytes)
        
        assert result.is_success
        packet = result.packet
        
        # Собираем обратно
        rebuilt_bytes = protocol.build_packet(packet)
        
        # Сравниваем
        assert rebuilt_bytes == expected_bytes, \
            f"Roundtrip failed for {hex_file}: {rebuilt_bytes.hex().upper()} != {expected_hex}"
```

---

## 7. Обновление документации

### 7.1. scenarios/README.md

Добавить раздел **"Динамическая генерация пакетов"**:

```markdown
## Динамическая генерация пакетов

Начиная с версии X.X, сценарии поддерживают динамическую генерацию пакетов на лету без использования HEX-файлов.

### Формат build-шаблона

Вместо указания `packet_file` используйте поле `build`:

```json
{
  "name": "Шаг с динамическим пакетом",
  "type": "send",
  "channel": "tcp",
  "build": {
    "packet": {
      "packet_id": 10,
      "packet_type": 0,
      "records": [...]
    }
  }
}
```

### Структура пакета

#### Транспортный уровень

| Поле | Тип | Обязательное | По умолчанию | Описание |
|------|-----|--------------|--------------|----------|
| `packet_id` | int | Да | — | Номер пакета (PID) |
| `packet_type` | int | Да | — | 0=RESPONSE, 1=APPDATA, 2=SIGNED |
| `protocol_version` | int | Нет | 1 | Версия протокола |
| `response_packet_id` | int | Для PT=0 | — | Номер подтверждаемого пакета |
| `processing_result` | int | Для PT=0 | — | Результат обработки |

#### Запись уровня услуг

| Поле | Тип | Обязательное | По умолчанию | Описание |
|------|-----|--------------|--------------|----------|
| `record_id` | int | Да | — | Номер записи (RN) |
| `service_type` | int | Да | — | Сервис-отправитель |
| `recipient_service_type` | int | Нет | 0 | Сервис-получатель |
| `rsod` | bool | Нет | False | Получатель на устройстве |
| `subrecords` | array | Да | — | Подзаписи |

#### Подзапись

| Поле | Тип | Обязательное | По умолчанию | Описание |
|------|-----|--------------|--------------|----------|
| `subrecord_type` | int | Да | — | Тип подзаписи (SRT) |
| `data` | object | Да | — | Данные подзаписи |

### Специальные форматы данных

#### Hex-строки

Для бинарных данных используйте суффикс `_hex`:

```json
{
  "subrecord_type": 51,
  "data": {
    "cd_hex": "0000011401"
  }
}
```

Система автоматически сконвертирует `cd_hex` в `cd` как `bytes`.

### Переменные

В шаблонах поддерживается подстановка переменных через `{{var_name}}`:

```json
{
  "packet_id": "{{next_pid}}",
  "records": [
    {
      "record_id": "{{last_rn}}",
      "service_type": 1
    }
  ]
}
```

#### Специальные переменные

| Переменная | Описание |
|------------|----------|
| `{{next_pid}}` | Следующий доступный Packet ID |
| `{{next_rn}}` | Следующий доступный Record Number |
| `{{last_pid}}` | PID последнего полученного пакета |
| `{{last_rn}}` | RN последней полученной записи |

#### Пользовательские переменные

Переменные, захваченные через `capture` в шагах `expect`:

```json
{
  "steps": [
    {
      "name": "Ожидание TERM_IDENTITY",
      "type": "expect",
      "capture": {
        "tid": "data.TID"
      }
    },
    {
      "name": "RESPONSE с использованием tid",
      "type": "send",
      "build": {
        "packet": {
          "packet_id": "{{tid}}",
          ...
        }
      }
    }
  ]
}
```

### Приоритет источников

Если указаны оба поля (`build` и `packet_file`), приоритет имеет `build`.

### Примеры

#### RESPONSE-пакет

```json
{
  "build": {
    "packet": {
      "packet_id": 10,
      "packet_type": 0,
      "response_packet_id": 5,
      "processing_result": 0,
      "records": [
        {
          "record_id": 5,
          "service_type": 1,
          "rsod": true,
          "subrecords": [
            {
              "subrecord_type": 0,
              "data": {"crn": 5, "rst": 0}
            }
          ]
        }
      ]
    }
  }
}
```

#### COMMAND_DATA

```json
{
  "build": {
    "packet": {
      "packet_id": 22,
      "packet_type": 1,
      "records": [
        {
          "record_id": 37,
          "service_type": 4,
          "recipient_service_type": 4,
          "rsod": true,
          "subrecords": [
            {
              "subrecord_type": 51,
              "data": {
                "ct": 5,
                "cct": 0,
                "cd_hex": "0000011401"
              }
            }
          ]
        }
      ]
    }
  }
}
```
```

### 7.2. docs/ARCHITECTURE.md

Добавить раздел в описание `SendStep`:

```markdown
### SendStep (обновлено)

**Файл:** `core/scenario.py`

Шаг отправки пакета с поддержкой двух источников:

1. **HEX-файл** (`packet_file`) — обратная совместимость
2. **Build-template** (`build`) — динамическая генерация

**Приоритет:** `build` > `packet_file`

**Методы:**
- `_build_packet()` — загрузка из HEX-файла
- `_build_from_template()` — сборка из build-template
- `_dict_to_packet()` — конвертация dict → Packet

**Формат build-template:**
```json
{
  "packet": {
    "packet_id": "{{next_pid}}",
    "packet_type": 0,
    "records": [...]
  },
  "gost_version": "2015"
}
```
```

### 7.3. Примеры сценариев

Создать новые примеры в `scenarios/examples/`:

```
scenarios/examples/
├── build_template_example.json    # Полный пример с build
├── mixed_example.json             # HEX + build в одном сценарии
└── variables_example.json         # Использование переменных
```

**build_template_example.json:**
```json
{
  "name": "Пример с build-templates",
  "scenario_version": "1",
  "gost_version": "ГОСТ 33465-2015",
  "timeout": 30,
  "description": "Демонстрация динамической генерации пакетов",
  "channels": ["tcp"],
  "steps": [
    {
      "name": "RESPONSE через build",
      "type": "send",
      "channel": "tcp",
      "build": {
        "packet": {
          "packet_id": 10,
          "packet_type": 0,
          "response_packet_id": 5,
          "processing_result": 0,
          "records": [
            {
              "record_id": 5,
              "service_type": 1,
              "rsod": true,
              "subrecords": [
                {
                  "subrecord_type": 0,
                  "data": {"crn": 5, "rst": 0}
                }
              ]
            }
          ]
        }
      },
      "description": "Отправка RESPONSE без HEX-файла"
    }
  ]
}
```

---

## 8. Риски и меры mitigation

| Риск | Вероятность | Влияние | Меры mitigation |
|------|-------------|---------|-----------------|
| Ошибки в расчёте CRC | Средняя | Высокое | Юнит-тесты на CRC, сравнение с эталонами |
| Несовместимость с УСВ | Низкая | Высокое | Интеграционные тесты с реальным устройством |
| Производительность | Низкая | Среднее | Бенчмарки, кэширование часто используемых шаблонов |
| Сложность отладки | Средняя | Низкое | Логирование структур пакетов до сборки |
| Регрессии в старых сценариях | Низкая | Высокое | Полное покрытие тестами обратной совместимости |

---

## 9. Заключение

Предложенное решение позволяет перейти от статических HEX-файлов к динамической генерации пакетов, сохраняя при этом полную обратную совместимость. Ключевые преимущества:

1. **Гибкость:** Параметры пакетов могут зависеть от контекста выполнения
2. **Поддерживаемость:** Структура пакета видна непосредственно в сценарии
3. **Безопасность:** Автоматический расчёт CRC исключает человеческие ошибки
4. **Эволюционность:** Постепенный переход без breaking changes

Рекомендуется начать с пилотного внедрения на одном сценарии (например, `auth`), затем масштабировать на остальные.
