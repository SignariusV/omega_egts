# Пошаговый план рефакторинга EGTS библиотеки

> Версия: 1.0
> Дата: 2026-04-14
> Цель: Создать чистую, типизированную, версионируемую библиотеку EGTS без дублирования моделей и с честным roundtrip.

---

## Этап 0: Подготовка

### 0.1. Создать резервную ветку
```bash
git checkout -b refactor/egts-lib
```

### 0.2. Заморозить изменения в старой библиотеке
Никаких новых фич — только багфиксы в `libs/egts_protocol_gost2015` и `libs/egts_protocol_iface`.

### 0.3. Собрать эталонные пакеты (51 штука)
Из `data/packets/all_packets_correct_20260406_190414.json` — сохранить в `tests/fixtures/egts_packets/` как `*.bin` и `*.json` с ожидаемым разбором.

### 0.4. Написать тест roundtrip для старой библиотеки
Для каждого эталонного пакета: `parse → build → сравнить байты`.
Это будет **baseline** для сравнения с новой библиотекой.

**Критерий:** Все 51 пакет парсятся без ошибок.

---

## Этап 1: Модели и типы (без парсинга)

### 1.1. Создать файлы
```
libs/egts/models.py
libs/egts/types.py
libs/egts/__init__.py
```

### 1.2. Определить Enum (`types.py`)

```python
class PacketType(IntEnum):
    RESPONSE = 0          # EGTS_PT_RESPONSE
    APPDATA = 1           # EGTS_PT_APPDATA
    SIGNED_APPDATA = 2    # EGTS_PT_SIGNED_APPDATA

class ServiceType(IntEnum):
    AUTH = 1              # EGTS_AUTH_SERVICE
    TELEDATA = 2          # EGTS_TELEDATA_SERVICE
    COMMANDS = 4          # EGTS_COMMANDS_SERVICE
    FIRMWARE = 9          # EGTS_FIRMWARE_SERVICE
    ECALL = 10            # EGTS_ECALL_SERVICE

class SubrecordType(IntEnum):
    """Все подзаписи по ГОСТ 33465-2015."""
    RECORD_RESPONSE = 0
    TERM_IDENTITY = 1
    MODULE_DATA = 2
    VEHICLE_DATA = 3
    AUTH_PARAMS = 6
    AUTH_INFO = 7
    SERVICE_INFO = 8
    RESULT_CODE = 9
    ACCEL_DATA = 20
    SERVICE_PART_DATA = 33
    SERVICE_FULL_DATA = 34
    COMMAND_DATA = 51
    RAW_MSD_DATA = 62     # ГОСТ таблица 40 (НЕ 21!)
    TRACK_DATA = 63       # ГОСТ таблица 40 (НЕ 62!)

class ResultCode(IntEnum):
    """Все коды из приложения В ГОСТ: 0, 1, 128-154 = 29 кодов."""
    OK = 0
    IN_PROGRESS = 1
    UNS_PROTOCOL = 128
    DECRYPT_ERROR = 129
    PROC_DENIED = 130
    INC_HEADERFORM = 131
    INC_DATAFORM = 132
    UNS_TYPE = 133
    NOTEN_PARAMS = 134
    DBL_PROC = 135
    PROC_SRC_DENIED = 136
    HEADERCRC_ERROR = 137
    DATACRC_ERROR = 138
    INVDATALEN = 139
    ROUTE_NFOUND = 140
    ROUTE_CLOSED = 141
    ROUTE_DENIED = 142
    INVADDR = 143
    TTLEXPIRED = 144
    NO_ACK = 145
    OBJ_NFOUND = 146
    EVNT_NFOUND = 147
    SRVC_NFOUND = 148
    SRVC_DENIED = 149
    SRVC_UNKN = 150
    AUTH_DENIED = 151
    ALREADY_EXISTS = 152
    ID_NFOUND = 153
    INC_DATETIME = 154
```

### 1.3. Реализовать датаклассы (`models.py`)

```python
@dataclass
class Packet:
    """Пакет транспортного уровня (ГОСТ таблица 3)."""
    protocol_version: int = 1              # PRV
    security_key_id: int = 0               # SKID
    prefix: bool = False                   # PRF (бит 7 flags)
    routing: bool = False                  # RTE (бит 6) — есть ли PRA/RCA/TTL
    encryption: int = 0                    # ENA (биты 5-4) — зарезервировано
    compressed: bool = False               # CMP (бит 3)
    priority: int = 0                      # PR (биты 2-1): 0=наивысший, 3=низкий
    header_encoding: int = 0               # HE
    packet_id: int                         # PID
    packet_type: int                       # PT: 0=RESPONSE, 1=APPDATA, 2=SIGNED
    
    # Опциональные (только при RTE=1)
    peer_address: int | None = None        # PRA
    recipient_address: int | None = None   # RCA
    ttl: int | None = None                 # TTL
    
    # RESPONSE-only (PT=0)
    response_packet_id: int | None = None  # RPID
    processing_result: int | None = None   # PR
    
    # SIGNED-only (PT=2)
    signature_data: bytes | None = None    # SIGD
    
    # Данные уровня поддержки услуг
    records: list['Record'] = field(default_factory=list)
    
    # Мета
    header_length: int = 11                # HL (рассчитывается)
    raw_bytes: bytes = field(default_factory=bytes, repr=False)


@dataclass
class Record:
    """Запись уровня поддержки услуг (ГОСТ таблица 14)."""
    record_id: int                         # RN
    service_type: int                      # SST (Source Service Type)
    recipient_service_type: int = 0        # RST (Recipient Service Type)
    subrecords: list['Subrecord'] = field(default_factory=list)
    
    # Опциональные (по флагам RFL: OBFE, EVFE, TMFE)
    object_id: int | None = None           # OID
    event_id: int | None = None            # EVID
    timestamp: int | None = None           # TM (секунды с 01.01.2010 UTC)
    
    # Флаги RFL
    ssod: bool = False                     # SSOD — сервис-отправитель на устройстве
    rsod: bool = False                     # RSOD — сервис-получатель на устройстве
    rpp: int = 0                           # RPP (0-7) — приоритет обработки


@dataclass
class Subrecord:
    """Подзапись уровня поддержки услуг (ГОСТ таблица 15)."""
    subrecord_type: int                    # SRT — всегда int
    data: dict[str, object] | bytes        # dict (распарсен) или bytes (бинарные)
    raw_bytes: bytes = field(default_factory=bytes, repr=False)
    parse_error: str | None = None


@dataclass(frozen=True)
class ParseResult:
    """Результат парсинга EGTS-пакета."""
    packet: Packet | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    @property
    def is_success(self) -> bool:
        return self.packet is not None and not self.errors


@dataclass
class ResponseRecord:
    """Запись для RESPONSE-пакета."""
    rn: int                                # Номер записи
    service: int                           # Тип сервиса
    subrecords: list[Subrecord]
    rsod: bool = True                      # RSOD — по умолчанию с платформы
```

**Критерий завершения:**
- Модуль импортируется без ошибок
- Датаклассы создаются
- `mypy libs/egts/` проходит без ошибок
- Все тесты `tests/test_models.py` зелёные

---

## Этап 2: Интерфейс и реестр версий

### 2.1. Создать `protocol.py`

```python
class IEgtsProtocol(Protocol):
    def parse_packet(self, data: bytes) -> ParseResult: ...
    def build_packet(self, packet: Packet) -> bytes: ...
    def build_response(self, pid: int, result_code: int,
                       records: list[ResponseRecord] = ()) -> bytes: ...
    def build_record_response(self, crn: int, rst: int) -> bytes: ...
    def calculate_crc8(self, data: bytes) -> int: ...
    def calculate_crc16(self, data: bytes) -> int: ...
    @property
    def version(self) -> str: ...
    @property
    def capabilities(self) -> set[str]: ...
```

### 2.2. Создать `registry.py`

```python
_registry: dict[str, Callable[[], IEgtsProtocol]] = {}

def register_version(version: str, factory: Callable[[], IEgtsProtocol]) -> None:
    _registry[version] = factory

def get_protocol(version: str) -> IEgtsProtocol:
    if version not in _registry:
        raise ValueError(f"Unknown EGTS version: {version}")
    return _registry[version]()
```

**Критерий:** Регистрация и получение протокола работают.

---

## Этап 3: CRC и низкоуровневые утилиты

### 3.1. Создать `_core/crc.py`

Табличные алгоритмы из ГОСТ (приложения Г и Д):

```python
def crc8(data: bytes) -> int:
    """CRC-8 CCITT (poly=0x31, init=0xFF)."""

def crc16(data: bytes) -> int:
    """CRC-16 CCITT (poly=0x1021, init=0xFFFF)."""
```

Убедиться что результаты совпадают со старой библиотекой на эталонных данных.

### 3.2. (Опционально) `_core/header_utils.py`

Функция `calc_header_length(has_routing: bool) -> int` — 11 или 16 байт.

**Критерий:** CRC тесты проходят на эталонных пакетах.

---

## Этап 4: Абстракция парсеров подзаписей

### 4.1. Создать `_core/subrecord.py`

```python
class SubrecordParser(Protocol):
    @property
    def srt(self) -> int: ...
    @property
    def name(self) -> str: ...
    def parse(self, raw: bytes) -> dict[str, object] | bytes: ...
    def serialize(self, data: dict[str, object] | bytes) -> bytes: ...
```

### 4.2. Создать `_core/subrecord_registry.py`

```python
_registry: dict[int, SubrecordParser] = {}

def register_parser(parser: SubrecordParser) -> None:
    _registry[parser.srt] = parser

def get_parser(srt: int) -> SubrecordParser | None:
    return _registry.get(srt)
```

### 4.3. Декоратор для автоматической регистрации

```python
def register_subrecord(parser_cls: type[SubrecordParser]) -> type[SubrecordParser]:
    """Декоратор: автоматически регистрирует парсер при определении класса."""
    instance = parser_cls()
    register_parser(instance)
    return parser_cls
```

**Критерий:** Регистрация работает, можно получить парсер по SRT.

---

## Этап 5: Парсинг и сборка заголовка (без записей)

### 5.1. Создать `_core/parser.py`

Функция `parse_header(data: bytes) -> Packet` — разбирает только заголовок (первые HL байт), заполняет поля Packet, включая `header_length`. CRC-8 не проверяет.

### 5.2. Создать `_core/builder.py`

Функция `build_header(packet: Packet) -> bytes` — собирает заголовок, вычисляет HL, HCS. FDL пока 0. Не включает записи.

### 5.3. Тест roundtrip заголовка

Для каждого заголовка из эталонных пакетов: `parse_header(build_header(packet))` → поля совпадают.

**Критерий:** Roundtrip заголовка работает для всех 51 пакетов.

---

## Этап 6: Парсеры подзаписей ГОСТ 2015 (14 штук)

### 6.1. Создать `_gost2015/subrecords.py`

Для каждой подзаписи написать класс с декоратором `@register_subrecord`:

| SRT | Класс | Тип data | ГОСТ таблица |
|-----|-------|----------|--------------|
| 0 | `RecordResponseParser` | dict {crn, rst} | 18 |
| 1 | `TermIdentityParser` | dict {tid, flags, imei, ...} | 19 |
| 2 | `ModuleDataParser` | dict {mt, vid, fwv, ...} | 21 |
| 3 | `VehicleDataParser` | dict {vin, vht, vpst} | 22 |
| 6 | `AuthParamsParser` | dict {flg, ena, pbk, ...} | 23 |
| 7 | `AuthInfoParser` | dict {unm, upsw, ss} | 24 |
| 8 | `ServiceInfoParser` | dict {srvp, services} | 25 |
| 9 | `ResultCodeParser` | dict {rcd, rcd_text} | 27 |
| 20 | `AccelDataParser` | dict {sa, atm, measurements} | 41-42 |
| 33 | `ServicePartDataParser` | dict {id, pn, epq, odh, od} | 36-37 |
| 34 | `ServiceFullDataParser` | dict {odh, od} | 38 |
| 51 | `CommandDataParser` | dict {ct, cct, cid, sid, cd} | 29-30 |
| 62 | `RawMsdDataParser` | bytes (MSD) | 43 |
| 63 | `TrackDataParser` | dict {sa, atm, track_points} | 44-45 |

**Важно:** SRT=62 и SRT=63 — это RAW_MSD_DATA и TRACK_DATA по ГОСТ таблица 40. В старой библиотеке баг (21 и 62).

Пример:

```python
@register_subrecord
class TermIdentityParser:
    srt = 1
    name = "TERM_IDENTITY"
    
    def parse(self, raw: bytes) -> dict[str, object]:
        # Реализация по таблице 19
        tid = int.from_bytes(raw[0:4], 'little')
        flags = raw[4]
        hdide = bool(flags & 0x01)
        imeie = bool(flags & 0x02)
        ...
        return {"tid": tid, "flags": flags, "hdid": hdid, ...}
    
    def serialize(self, data: dict[str, object]) -> bytes:
        result = data["tid"].to_bytes(4, 'little')
        result += bytes([data["flags"]])
        ...
        return result
```

### 6.2. Тесты для каждой подзаписи

- Для каждого SRT взять эталонные байты из реальных пакетов.
- Проверить что `parse` возвращает dict с ожидаемыми ключами.
- Проверить что `serialize(parse(raw)) == raw` (roundtrip).
- Для бинарных подзаписей (SRT=62 RAW_MSD_DATA) — `data` типа `bytes`, сериализация — просто возврат.

**Критерий:** Все 14 парсеров проходят roundtrip.

---

## Этап 7: Реализация Gost2015Protocol

### 7.1. Создать `_gost2015/__init__.py`

```python
class Gost2015Protocol(IEgtsProtocol):
    version = "2015"
    capabilities = {"auth", "commands", "ecall", "firmware"}
    
    def parse_packet(self, data: bytes) -> ParseResult:
        # 1. Проверить минимальную длину (11 байт заголовок + 2 CRC-16)
        # 2. Извлечь HL (байт 3), прочитать заголовок
        # 3. Проверить CRC-8 заголовка
        #    Если ошибка → ParseResult(packet=None, errors=["CRC-8 error"])
        # 4. Извлечь FDL, проверить длину данных
        # 5. Проверить CRC-16 данных
        #    Если ошибка → ParseResult(packet=None, errors=["CRC-16 error"])
        # 6. Разобрать записи (RL, RN, RFL, опциональные поля, подзаписи)
        #    Для каждой подзаписи:
        #      - Получить парсер по SRT
        #      - Вызвать parser.parse(srd)
        #      - Если парсера нет → data = raw_bytes
        # 7. Вернуть ParseResult(packet, errors, warnings)
    
    def build_packet(self, packet: Packet) -> bytes:
        # 1. Сериализовать записи:
        #    Для каждой записи:
        #      - Сериализовать подзаписи:
        #        * data=dict → parser.serialize(data)
        #        * data=bytes → raw_bytes
        #      - Собрать RL, RN, RFL, SST, RST, опциональные поля, SRD
        # 2. Вычислить FDL = len(records_data)
        # 3. Собрать заголовок с заполненным FDL
        # 4. Добавить records_data
        # 5. Вычислить CRC-16 от records_data, добавить
        # 6. Пересчитать HCS (CRC-8 от заголовка до HCS)
        # 7. Вернуть байты
    
    def build_response(self, pid: int, result_code: int,
                       records: list[ResponseRecord] = ()) -> bytes:
        # Создать пакет:
        #   packet_type = 0 (RESPONSE)
        #   response_packet_id = pid
        #   processing_result = result_code
        #   records = [Record(rn, service, [Subrecord(SRT=0, {crn, rst})]) for each ResponseRecord]
        #   Вызвать build_packet
    
    def build_record_response(self, crn: int, rst: int) -> bytes:
        # SRT(1) + SRL(2) + CRN(2) + RST(1) = 6 байт
        pass
    
    def calculate_crc8(self, data: bytes) -> int:
        return crc8(data)
    
    def calculate_crc16(self, data: bytes) -> int:
        return crc16(data)
```

### 7.2. Зарегистрировать протокол

```python
from ..registry import register_version
register_version("2015", lambda: Gost2015Protocol())
```

### 7.3. Тест roundtrip всех 51 эталонных пакетов

Для каждого: `protocol.parse_packet(data) → protocol.build_packet(packet) → сравниваем байты`.

Допускаются различия только в незначащих полях (raw_bytes не сравниваем).

**Критерий:** Все 51 пакет проходят roundtrip байт-в-байт.

---

## Этап 8: Dual-write в ядре проекта (переход)

### 8.1. Создать фабрику протоколов в `core/session.py`

Вместо прямой зависимости от `libs.egts_protocol_iface.create_protocol` — использовать новую библиотеку через `get_protocol("2015")`.

### 8.2. Временный режим dual-write

В `SessionManager._on_packet_processed`:

1. Сначала парсим старой библиотекой (получаем extra и т.д.)
2. Параллельно парсим новой библиотекой (получаем ParseResult)
3. Сравниваем результаты (логируем расхождения, но продолжаем работу со старой логикой)
4. Постепенно переключаем FSM и логику на новые модели

### 8.3. Миграция подсистем

| Подсистема | Действие |
|------------|----------|
| **FSM** (session.py) | Переписать на использование `record.service_type` и `subrecord.data` вместо `extra` |
| **Logger** (logger.py) | Логировать `subrecord.data` напрямую, без `extra` |
| **Scenario** (scenario.py) | Матчинг по `subrecord.subrecord_type` и `subrecord.data` |
| **Pipeline** (pipeline.py) | Не меняется — работает с `ParseResult` через `ctx.parsed` |

### 8.4. Удаление старой библиотеки

Когда все тесты проходят — удалить:
- `libs/egts_protocol_gost2015/`
- `libs/egts_protocol_iface/`

**Критерий:** Все интеграционные тесты зелёные, логи не содержат предупреждений о расхождениях.

---

## Этап 9: Чистка и документация

### 9.1. Обновить README
Описать новую архитектуру, примеры использования.

### 9.2. Удалить мёртвый код
- Убрать `extra` из всех мест
- Удалить старые модули
- Удалить `InternalPacket`, `InternalRecord`, `InternalSubrecord`

### 9.3. Обновить типы
Убедиться что `mypy` проходит без ошибок.

### 9.4. Удалить скрипты анализа
Удалить временные скрипты из `scripts/` созданные на этапе исследования.

**Критерий:** Проект готов к слиянию в `master`.

---

## Сводка изменений

| Что | Было | Стало |
|-----|------|-------|
| Модели | 2 набора (Internal + Iface) + 6 мапперов | **1 набор** (models.py) |
| Subrecord.data | `bytes \| dict \| None` — непредсказуемо | **`dict \| bytes`** — всегда определено |
| ParseResult.extra | Свалка метаданных | **Убрано полностью** |
| subrecord_type | `int` но adapter кладёт `str` | **Всегда int** |
| SRT TRACK_DATA | 62 (баг) | **63** (по ГОСТ) |
| SRT RAW_MSD_DATA | 21 (баг) | **62** (по ГОСТ) |
| create_protocol | if/elif | **Registry** |
| Roundtrip | Берёт raw_data игнорируя data | **Честный**: dict → serialize → bytes |
| Константы ГОСТ | В iface/types.py | **В implementation** (_gost2015/) |
| Мёртвые поля Record | first/last/ongoing_record | **Убраны** |

## Что НЕ делаем

- **SMS PDU** — CMW-500 берёт на себя
- **Шифрование (ENA)** — не используется в ГОСТ 2015, поле зарезервировано
- **Маршрутизация (PRA/RCA/TTL)** — в эталоне нет ни одного пакета с RTE=1, но поля есть
- **SIGNED_APPDATA (PT=2)** — в эталоне нет, но поле есть

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| Ядро зависит от `extra` ключей | Поэтапный переход: dual-write на Этапе 8 |
| `Subrecord.data` dict имеет разные ключи для разных SRT | Каждый парсер документирует свои ключи |
| Roundtrip может сломаться на бинарных данных | Тест на всех 51 эталонных пакетах (Этап 7.3) |
| Баг SRT=21/62 → SRT=62/63 ломает старые тесты | Исправить тесты вместе с новой библиотекой |
