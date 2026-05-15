# План реализации ядра OMEGA_EGTS по ТЗ на ПАК

> **Дата:** 2026-05-15 (ред. 2 — переработан Этап 5)
> **Основание:** ТЗ на ПАК (редакция 2), ГОСТ 33464-2015, ГОСТ 33465-2015
> **Объект:** Ядро (`core/`) — без GUI
> **Текущая готовность ядра:** ~70% (Этапы 1-4 завершены)
> **Архитектура:** Все проверки ТЗ через сценарии JSON + ScenarioManager

---

## Стратегия реализации

План разбит на **7 этапов**, каждый из которых:
- Добавляет конкретную функциональность ядра
- Покрывается unit/integration тестами
- Не ломает существующую архитектуру (EventBus, pipeline, FSM)
- Может быть выполнен независимо от GUI

**Принципы:**
1. Сначала конфигурация и данные → потом логика → потом тесты
2. Каждый этап — отдельная ветка git
3. Тесты пишутся одновременно с кодом (≥90% coverage)
4. Обратная совместимость: старые сценарии JSON продолжают работать
5. **Все проверки ТЗ через сценарии JSON** — никаких отдельных Python-классов тестов

**Архитектурное решение:**
Система уже имеет `ScenarioManager` + `ScenarioParserFactory` + `StepFactory` для выполнения сценариев.
Этапы 5-8 используют эту архитектуру:
- Сценарии JSON описывают последовательность пакетов и проверок
- `send` / `expect` — отправка и ожидание пакетов (уже реализовано)
- `wait` — ожидание событий EventBus (новый тип шага)
- `check` — проверка условий, статусов, диапазонов (новый тип шага)
- `TestSession` обновляется автоматически через EventBus подписки
- Результаты сценариев сохраняются как `TestResult` в `TestSession`

---

## Этап 1 — Конфигурация и параметры (ТЗ п. 2.1)

**Цель:** Добавить все конфигурируемые параметры из ТЗ п. 2.1 в `Config` и `Credentials`.

### 1.1. Расширить `CmwConfig` (core/config.py)

```python
@dataclass(frozen=True)
class CmwConfig:
    # Существующие поля (сохранить)
    ip: str | None = "192.168.2.2"
    simulate: bool = False
    timeout: float = 5.0
    retries: int = 3
    sms_send_timeout: float = 10.0
    status_poll_interval: float = 2.0
    mcc: int = 250
    mnc: int = 77  # ← ИСПРАВИТЬ: было 60, ТЗ требует 77 (NID=25077)
    rf_level_tch: float = -40.0
    ps_service: str = "TMA"
    ps_tlevel: str = "EGPRS"
    ps_cscheme_ul: str = "MC9"
    ps_dl_carrier: list[str] = ...
    ps_dl_cscheme: list[str] = ...
    sms_dcoding: str = "BIT8"
    sms_pidentifier: int = 1

    # НОВЫЕ поля (ТЗ 2.1.1)
    visa_resource: str = "TCPIP::{ip}::inst0::INSTR"  # VISA адрес

    # НОВЫЕ поля (ТЗ 2.1.2)
    network_type: str = "GSM/EDGE"           # а) тип сети
    ps_domain: bool = True                    # б) PS Domain = On
    gsm_auth: bool = False                    # г) аутентификация GSM = выкл
    frequency_band: str = "900"               # д) 900 или 1800 МГц
    voice_codec: str = "FR"                   # е) речевой кодек
    arfcn_bch: int = 0                        # ж) канал BCH
    arfcn_tch: int = 0                        # з) канал TCH
    rf_level_min: float = -30.0               # и) мин мощность
    rf_level_max: float = 30.0                # и) макс мощность
    pcl_value: str = "MAX"                    # к) PCL = максимальный
    profile_imsi: str = ""                    # л) IMSI профиля (NID=25077...)
    smsc_number: str = ""                     # м) номер SMSC
    dau_ip: str = "192.168.2.1"               # н) IP модуля DAU
    dau_subnet_mask: str = "255.255.255.0"    # о) IP-маска подсети
    test_system_ip: str = "192.168.2.100"     # п) IP тестовой системы
    usv_dhcp_ip: str = "192.168.2.200"        # р) DHCP IP для УСВ
```

**Файлы для изменения:**
- `core/config.py` — добавить поля, валидацию, `_from_dict`, `merge_with_cli`
- `tests/core/test_config.py` — тесты новых полей

**Валидация (добавить в `_validate_cmw`):**
- `mnc` должен быть 77 (ТЗ: NID=25077)
- `rf_level_tch` в диапазоне [-30, +30]
- `frequency_band` ∈ {"900", "1800"}
- `dau_ip`, `test_system_ip`, `usv_dhcp_ip` — валидные IPv4
- `smsc_number` — формат MSISDN

### 1.2. Создать `VehicleConfig` (core/config.py)

```python
@dataclass(frozen=True)
class VehicleConfig:
    """Параметры ТС для аутентификации (ТЗ п. 2.1.4)."""
    vin: str = ""                    # а) VIN (17 символов)
    category: str = ""               # б) категория ТС (M1, N1, ...)
    fuel_type: str = ""              # в) тип топлива (бензин, дизель, ...)

def _validate_vehicle(v: VehicleConfig) -> None:
    if v.vin and len(v.vin) != 17:
        raise ValueError(f"VIN должен содержать 17 символов, получено {len(v.vin)}")
    if v.category and v.category not in {"M1", "M2", "M3", "N1", "N2", "N3"}:
        raise ValueError(f"Недопустимая категория ТС: {v.category}")
```

**Добавить в `Config`:**
```python
@dataclass(frozen=True)
class Config:
    ...
    vehicle: VehicleConfig = field(default_factory=VehicleConfig)
```

### 1.3. Расширить `Credentials` (core/credentials.py)

```python
@dataclass
class Credentials:
    device_id: str        # IMEI или уникальный идентификатор
    term_code: str        # Код терминала

    # НОВЫЕ поля (ТЗ п. 2.1.3)
    imsi: str = ""        # а) IMSI для авторизации
    imei: str = ""        # б) IMEI для авторизации
    msisdn: str = ""      # в) MSISDN для авторизации
    serial_number: str = ""  # г) серийный номер
    model: str = ""          # д) модель
    egts_unit_id: int = 0    # е) EGTS_UNIT_ID для конфигурирования
```

**Файлы для изменения:**
- `core/credentials.py` — добавить поля, `to_dict`, `from_dict`
- `tests/core/test_credentials.py` — тесты сериализации

### 1.4. Исправить MNC по умолчанию

**Критическая ошибка:** `CmwConfig.mnc = 60` → должно быть `77`.

**Файлы:**
- `core/config.py` — изменить default
- `tests/core/test_config.py` — обновить тесты
- `core/engine.py` — проверить, что `configure_gsm_signaling` использует `mnc=77`

### 1.5. Обновить `engine.py` — передача новых параметров в CMW

```python
# В CoreEngine.start():
await self.cmw500.configure_gsm_signaling(
    mcc=cmw_cfg.mcc,
    mnc=cmw_cfg.mnc,
    rf_level_dbm=cmw_cfg.rf_level_tch,
    ps_domain=cmw_cfg.ps_domain,
    gsm_auth=cmw_cfg.gsm_auth,
    frequency_band=cmw_cfg.frequency_band,
    voice_codec=cmw_cfg.voice_codec,
    arfcn_bch=cmw_cfg.arfcn_bch,
    arfcn_tch=cmw_cfg.arfcn_tch,
    ...
)

await self.cmw500.configure_dau(
    ip=cmw_cfg.dau_ip,
    subnet_mask=cmw_cfg.dau_subnet_mask,
    test_system_ip=cmw_cfg.test_system_ip,
    usv_dhcp_ip=cmw_cfg.usv_dhcp_ip,
)
```

### 1.6. Обновить `cmw500.py` — новые SCPI-команды

```python
class VisaCmw500Driver:
    def configure_gsm_signaling(self, ..., ps_domain=True, gsm_auth=False, ...):
        # PS Domain
        self._drv.utilities.write_str_with_opc(
            f"CONFigure:GSM:SIGN:CONNection:PSWitched:STATe {'ON' if ps_domain else 'OFF'}"
        )
        # GSM Authentication
        self._drv.utilities.write_str_with_opc(
            f"CONFigure:GSM:SIGN:SECurity:AUTHentication {'ON' if gsm_auth else 'OFF'}"
        )
        # Frequency band
        self._drv.utilities.write_str_with_opc(
            f"CONFigure:GSM:SIGN:CELL:BAND {'900' if frequency_band == '900' else '1800'}"
        )
        # ARFCN
        self._drv.utilities.write_str_with_opc(
            f"CONFigure:GSM:SIGN:CELL:ARFCN:BCH {arfcn_bch}"
        )
        self._drv.utilities.write_str_with_opc(
            f"CONFigure:GSM:SIGN:CELL:ARFCN:TCH {arfcn_tch}"
        )
        # Voice codec
        self._drv.utilities.write_str_with_opc(
            f"CONFigure:GSM:SIGN:CSWitched:CODEC {voice_codec}"
        )

    def configure_dau(self, ip, subnet_mask, test_system_ip, usv_dhcp_ip):
        self._drv.utilities.write_str("CONFigure:DATA:MEAS:RAN 'GSM Sig1'")
        self._drv.utilities.write_str("CONFigure:DATA:CONTrol:DNS:PRIMary:STYPe Foreign")
        self._drv.utilities.write_str("CONFigure:DATA:CONTrol:IPVFour:ADDRess:TYPE DHCPv4")
        self._drv.utilities.write_str(f"CONFigure:DATA:CONTrol:IPVFour:ADDRess {ip}")
        self._drv.utilities.write_str(f"CONFigure:DATA:CONTrol:IPVFour:SUBNet:MASK {subnet_mask}")
```

---

## Этап 2 — EGTS подзаписи и команды (ТЗ п. 2.3, ГОСТ 33465-2015)

**Цель:** Добавить все необходимые EGTS subrecord types и парсеры команд.

### 2.1. Расширить `SubrecordType` (libs/egts/types.py)

```python
class SubrecordType(IntEnum):
    # Существующие
    TERM_IDENTITY = 1
    AUTH_PARAMS = 2
    AUTH_INFO = 3
    RESULT_CODE = 4
    NAV_DATA = 10
    TRACK_DATA = 11        # ← Добавить
    ACCEL_DATA = 12        # ← Добавить
    RAW_MSD_DATA = 13
    SERVICE_PART_DATA = 20 # ← Добавить
    SERVICE_FULL_DATA = 21 # ← Добавить
    COMMAND_DATA = 30

    # НОВЫЕ
    SERVICE_INFO = 7       # ТЗ: negotiation сервисов
    VEHICLE_DATA = 5       # ТЗ: данные ТС для аутентификации
    RECORD_RESPONSE = 0x8000  # Уже есть, проверить
```

### 2.2. Создать парсеры подзаписей (libs/egts/_gost2015/subrecords.py)

#### EGTS_SR_SERVICE_INFO (ТЗ п. 2.3.1 шаг 11)

```python
@dataclass
class ServiceInfoSubrecord:
    """EGTS_SR_SERVICE_INFO — запрос/ответ сервисов (ГОСТ 33465-2015 п. 6.7.2.7)."""
    service_type: int          # Тип сервиса (ST=10 для ECALL)
    service_status: int        # 0=available, 1=unavailable
    service_specific_data: bytes = b""

    def serialize(self) -> bytes:
        # Format: service_type (1) + service_status (1) + specific_data (var)
        return struct.pack('<BB', self.service_type, self.service_status) + self.service_specific_data

    @classmethod
    def deserialize(cls, data: bytes) -> 'ServiceInfoSubrecord':
        st, ss = struct.unpack('<BB', data[:2])
        return cls(service_type=st, service_status=ss, service_specific_data=data[2:])
```

#### EGTS_SR_VEHICLE_DATA (ТЗ п. 2.3.1 шаг 9)

```python
@dataclass
class VehicleDataSubrecord:
    """EGTS_SR_VEHICLE_DATA — данные ТС для аутентификации (ГОСТ 33465-2015 п. 6.7.2.4)."""
    vin: str                   # VIN (17 символов)
    vehicle_category: int      # Категория ТС
    fuel_type: int             # Тип топлива

    def serialize(self) -> bytes:
        vin_bytes = self.vin.encode('ascii').ljust(17, b'\x00')[:17]
        return vin_bytes + struct.pack('<BB', self.vehicle_category, self.fuel_type)

    @classmethod
    def deserialize(cls, data: bytes) -> 'VehicleDataSubrecord':
        vin = data[:17].decode('ascii').rstrip('\x00')
        cat, fuel = struct.unpack('<BB', data[17:19])
        return cls(vin=vin, vehicle_category=cat, fuel_type=fuel)
```

#### EGTS_SR_TRACK_DATA (ТЗ п. 2.3.2, 2.3.3)

```python
@dataclass
class TrackDataPoint:
    """Одна точка данных профиля ускорения или траектории."""
    timestamp_ms: int          # Временная метка (мс)
    accel_x: int               # Ускорение X (мг)
    accel_y: int               # Ускорение Y (мг)
    accel_z: int               # Ускорение Z (мг)
    # Для траектории: lat, lon, speed, course

@dataclass
class TrackDataSubrecord:
    """EGTS_SR_TRACK_DATA — данные профиля ускорения/траектории (ГОСТ 33465-2015 п. 7.3.4)."""
    data_type: int             # 1=accel profile, 2=trajectory
    points: list[TrackDataPoint]

    def serialize(self) -> bytes:
        # data_type (1) + count (2) + points (var)
        result = struct.pack('<BH', self.data_type, len(self.points))
        for pt in self.points:
            result += struct.pack('<Ihhh', pt.timestamp_ms, pt.accel_x, pt.accel_y, pt.accel_z)
        return result

    @classmethod
    def deserialize(cls, data: bytes) -> 'TrackDataSubrecord':
        data_type, count = struct.unpack('<BH', data[:3])
        points = []
        offset = 3
        for _ in range(count):
            ts, ax, ay, az = struct.unpack('<Ihhh', data[offset:offset+10])
            points.append(TrackDataPoint(ts, ax, ay, az))
            offset += 10
        return cls(data_type=data_type, points=points)
```

#### EGTS_SR_SERVICE_PART_DATA / SERVICE_FULL_DATA (ТЗ п. 2.3.4)

```python
@dataclass
class ServicePartDataSubrecord:
    """EGTS_SR_SERVICE_PART_DATA — часть ПО (ГОСТ 33465-2015 п. 6.7.4)."""
    part_number: int           # Номер части
    total_parts: int           # Всего частей
    data: bytes                # Данные части

    def serialize(self) -> bytes:
        return struct.pack('<HH', self.part_number, self.total_parts) + self.data

    @classmethod
    def deserialize(cls, data: bytes) -> 'ServicePartDataSubrecord':
        pn, tp = struct.unpack('<HH', data[:4])
        return cls(part_number=pn, total_parts=tp, data=data[4:])

@dataclass
class ServiceFullDataSubrecord:
    """EGTS_SR_SERVICE_FULL_DATA — полный образ ПО."""
    firmware_version: str
    data: bytes
```

### 2.3. Создать парсеры COMMAND_DATA (ТЗ п. 2.3, Таблица 34)

**Файл:** `libs/egts/_gost2015/command_params.py`

```python
class EgtsCommandParamType(IntEnum):
    """Типы параметров команд EGTS (ТЗ Таблица 34)."""
    EGTS_GPRS_APN = 1
    EGTS_SERVER_ADDRESS = 2
    EGTS_UNIT_ID = 3
    EGTS_UNIT_MIC_LEVEL = 4
    EGTS_UNIT_SPK_LEVEL = 5
    EGTS_TRACK_DATA = 6
    # ... остальные из Таблицы 34

@dataclass
class EgtsCommandParam:
    """Параметр команды EGTS."""
    param_type: EgtsCommandParamType
    value: Any  # str для APN, int для UNIT_ID, etc.

    def serialize(self) -> bytes:
        if self.param_type == EgtsCommandParamType.EGTS_GPRS_APN:
            return struct.pack('<B', self.param_type) + self.value.encode('ascii')
        elif self.param_type == EgtsCommandParamType.EGTS_SERVER_ADDRESS:
            # IPv4 address
            return struct.pack('<B4s', self.param_type, ipaddress.IPv4Address(self.value).packed)
        elif self.param_type == EgtsCommandParamType.EGTS_UNIT_ID:
            return struct.pack('<BI', self.param_type, self.value)
        elif self.param_type in (EgtsCommandParamType.EGTS_UNIT_MIC_LEVEL,
                                  EgtsCommandParamType.EGTS_UNIT_SPK_LEVEL):
            if not (0 <= self.value <= 10):
                raise ValueError(f"Level must be 0-10, got {self.value}")
            return struct.pack('<BB', self.param_type, self.value)
        ...
```

### 2.4. Зарегистрировать новые subrecord в реестре

**Файл:** `libs/egts/_gost2015/subrecords.py`

```python
# В конце файла:
SUBRECORD_REGISTRY.register(7, ServiceInfoSubrecord)
SUBRECORD_REGISTRY.register(5, VehicleDataSubrecord)
SUBRECORD_REGISTRY.register(11, TrackDataSubrecord)
SUBRECORD_REGISTRY.register(12, AccelDataSubrecord)
SUBRECORD_REGISTRY.register(20, ServicePartDataSubrecord)
SUBRECORD_REGISTRY.register(21, ServiceFullDataSubrecord)
```

### 2.5. Тесты

**Файлы:**
- `tests/libs/egts/test_service_info.py`
- `tests/libs/egts/test_vehicle_data.py`
- `tests/libs/egts/test_track_data.py`
- `tests/libs/egts/test_firmware_data.py`
- `tests/libs/egts/test_command_params.py`

**Каждый тест:**
- Round-trip: serialize → deserialize → сравнение
- Граничные случаи: пустые данные, максимальные значения
- Ошибки: невалидный VIN, level > 10, etc.

---

## Этап 3 — Валидация авторизации и аутентификации

**Цель:** Реализовать сверку TERM_IDENTITY и VEHICLE_DATA с конфигурацией.

### 3.1. Создать `core/validators/auth_validator.py`

```python
@dataclass
class AuthValidationResult:
    passed: bool
    reasons: list[str]  # Причины отказа (если passed=False)

class AuthValidator:
    """Валидация авторизации (ТЗ п. 2.3.1 шаг 8, 2.3.2 шаг 9, ...)."""

    def __init__(self, config: Config, credentials: Credentials):
        self.config = config
        self.credentials = credentials

    def validate_term_identity(
        self,
        unit_id: int | None,
        imsi: str | None,
        imei: str | None,
        msisdn: str | None,
    ) -> AuthValidationResult:
        """Сверка параметров TERM_IDENTITY с настройками (ТЗ п. 2.1.3)."""
        reasons: list[str] = []

        if imsi and self.credentials.imsi and imsi != self.credentials.imsi:
            reasons.append(f"IMSI mismatch: {imsi} != {self.credentials.imsi}")
        if imei and self.credentials.imei and imei != self.credentials.imei:
            reasons.append(f"IMEI mismatch: {imei} != {self.credentials.imei}")
        if msisdn and self.credentials.msisdn and msisdn != self.credentials.msisdn:
            reasons.append(f"MSISDN mismatch: {msisdn} != {self.credentials.msisdn}")
        if unit_id is not None and self.credentials.egts_unit_id and unit_id != self.credentials.egts_unit_id:
            reasons.append(f"UNIT_ID mismatch: {unit_id} != {self.credentials.egts_unit_id}")

        return AuthValidationResult(passed=len(reasons) == 0, reasons=reasons)

    def validate_vehicle_data(
        self,
        vin: str | None,
        category: int | None,
        fuel_type: int | None,
    ) -> AuthValidationResult:
        """Сверка параметров VEHICLE_DATA с настройками (ТЗ п. 2.1.4)."""
        reasons: list[str] = []

        if vin and self.config.vehicle.vin and vin != self.config.vehicle.vin:
            reasons.append(f"VIN mismatch: {vin} != {self.config.vehicle.vin}")
        if category is not None and self.config.vehicle.category:
            cat_map = {"M1": 1, "M2": 2, "M3": 3, "N1": 4, "N2": 5, "N3": 6}
            expected = cat_map.get(self.config.vehicle.category)
            if expected is not None and category != expected:
                reasons.append(f"Category mismatch: {category} != {expected}")
        if fuel_type is not None and self.config.vehicle.fuel_type:
            fuel_map = {"бензин": 1, "дизель": 2, "газ": 3, "электричество": 4}
            expected = fuel_map.get(self.config.vehicle.fuel_type)
            if expected is not None and fuel_type != expected:
                reasons.append(f"Fuel type mismatch: {fuel_type} != {expected}")

        return AuthValidationResult(passed=len(reasons) == 0, reasons=reasons)
```

### 3.2. Создать `core/validators/service_info_validator.py`

```python
class ServiceInfoValidator:
    """Валидация Service Info negotiation (ТЗ п. 2.3.1 шаг 11)."""

    ALLOWED_SERVICE_TYPE = 10  # EGTS_ECALL_SERVICE

    def validate_request(self, service_type: int) -> AuthValidationResult:
        """Проверить, запрашивает ли УВ разрешённый сервис."""
        if service_type == self.ALLOWED_SERVICE_TYPE:
            return AuthValidationResult(passed=True, reasons=[])
        return AuthValidationResult(
            passed=False,
            reasons=[f"Сервис ST={service_type} не поддерживается (разрешён только ST=10)"]
        )

    def build_accept_response(self) -> ServiceInfoSubrecord:
        """Построить ответ: сервис ST=10 доступен."""
        return ServiceInfoSubrecord(
            service_type=self.ALLOWED_SERVICE_TYPE,
            service_status=0  # available
        )

    def build_reject_response(self, requested_type: int) -> ServiceInfoSubrecord:
        """Построить ответ: сервис недоступен."""
        return ServiceInfoSubrecord(
            service_type=requested_type,
            service_status=1  # unavailable
        )
```

### 3.3. Интеграция с `SessionManager`

**Файл:** `core/session.py`

```python
class SessionManager:
    def __init__(self, bus: EventBus, config: Config, credentials_repo, ...):
        ...
        self.auth_validator = AuthValidator(config, credentials_repo.get_default())
        self.service_info_validator = ServiceInfoValidator()

    async def _on_packet_processed(self, data: dict) -> None:
        ...
        # При получении TERM_IDENTITY:
        if service == 1:  # TERM_IDENTITY
            result = self.auth_validator.validate_term_identity(
                unit_id=parsed.get("unit_id"),
                imsi=parsed.get("imsi"),
                imei=parsed.get("imei"),
                msisdn=parsed.get("msisdn"),
            )
            if not result.passed:
                await self.bus.emit("auth.validation_failed", {
                    "connection_id": connection_id,
                    "reasons": result.reasons,
                })

        # При получении VEHICLE_DATA:
        if service == 5:  # VEHICLE_DATA
            result = self.auth_validator.validate_vehicle_data(
                vin=parsed.get("vin"),
                category=parsed.get("category"),
                fuel_type=parsed.get("fuel_type"),
            )
            if not result.passed:
                await self.bus.emit("auth.validation_failed", {
                    "connection_id": connection_id,
                    "reasons": result.reasons,
                })
```

### 3.4. Новые события EventBus

```python
# Добавить в ARCHITECTURE.md таблицу событий:
"auth.validation_failed"  → {"connection_id", "reasons": [...]}
"auth.validation_passed"  → {"connection_id"}
"service_info.requested"  → {"connection_id", "service_type"}
"service_info.responded"  → {"connection_id", "service_type", "status"}
```

### 3.5. Тесты

**Файлы:**
- `tests/core/validators/test_auth_validator.py`
- `tests/core/validators/test_service_info_validator.py`

---

## Этап 4 — Управление сеансом проверок

**Цель:** Реализовать концепцию "сеанса проверок" (ТЗ п. 2.2.5-2.2.6).

### 4.1. Создать `core/test_session.py`

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Any
import time

class SessionState(Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    COMPLETED = "completed"

@dataclass
class TestSession:
    """Сеанс проверок (ТЗ п. 2.2.5-2.2.6)."""
    state: SessionState = SessionState.INACTIVE
    started_at: float | None = None
    completed_at: float | None = None

    # Статусы (ТЗ п. 2.2.2)
    cmw_connected: bool = False
    usv_registered: bool = False
    gprs_attached: bool = False
    registered_imsi: str | None = None
    tcp_connected: bool = False
    config_done: bool = False
    auth_done: bool = False
    auth_result: bool | None = None
    auth_validation_passed: bool | None = None
    vehicle_auth_done: bool = False
    vehicle_auth_passed: bool | None = None
    voice_connected: bool = False

    # Результаты тестов
    test_results: dict[str, 'TestResult'] = field(default_factory=dict)

    # Snapshot конфигурации (для отчёта)
    config_snapshot: dict[str, Any] | None = None
    credentials_snapshot: dict[str, Any] | None = None

    def activate(self, config: Config, credentials: Credentials) -> None:
        """Начать новый сеанс (ТЗ п. 2.2.1)."""
        self.state = SessionState.ACTIVE
        self.started_at = time.time()
        self.config_snapshot = self._snapshot_config(config)
        self.credentials_snapshot = self._snapshot_credentials(credentials)
        self._reset_statuses()

    def deactivate(self) -> None:
        """Завершить сеанс (ТЗ п. 2.2.5)."""
        self.state = SessionState.COMPLETED
        self.completed_at = time.time()

    def reset_on_network_off(self) -> None:
        """Сброс при выключении сети (ТЗ п. 2.2.5)."""
        self.usv_registered = False
        self.gprs_attached = False
        self.registered_imsi = None
        self.tcp_connected = False
        self.auth_done = False
        self.auth_result = None
        # Тесты сохраняются — они уже прошли

    def reset_all(self) -> None:
        """Полный сброс при повторной активации (ТЗ п. 2.2.6)."""
        self.__init__()  # Сброс всех параметров в начальные значения

    def _reset_statuses(self) -> None:
        """Сбросить статусы в значения по умолчанию."""
        self.usv_registered = False
        self.gprs_attached = False
        self.registered_imsi = None
        self.tcp_connected = False
        self.config_done = False
        self.auth_done = False
        self.auth_result = None
        self.vehicle_auth_done = False
        self.voice_connected = False

    @staticmethod
    def _snapshot_config(config: Config) -> dict[str, Any]:
        return {
            "cmw500": {
                "ip": config.cmw500.ip,
                "mcc": config.cmw500.mcc,
                "mnc": config.cmw500.mnc,
                "dau_ip": config.cmw500.dau_ip,
                "test_system_ip": config.cmw500.test_system_ip,
                ...
            },
            "vehicle": {
                "vin": config.vehicle.vin,
                "category": config.vehicle.category,
                "fuel_type": config.vehicle.fuel_type,
            },
        }

    @staticmethod
    def _snapshot_credentials(creds: Credentials) -> dict[str, Any]:
        return {
            "imsi": creds.imsi,
            "imei": creds.imei,
            "msisdn": creds.msisdn,
            "egts_unit_id": creds.egts_unit_id,
            ...
        }

@dataclass
class TestResult:
    """Результат одной проверки."""
    test_name: str           # "7.3", "6.8", "6.9", "7.8", "9.2.2"
    passed: bool
    reasons: list[str]       # Причины отрицательного результата
    steps_completed: int     # Сколько шагов выполнено
    steps_total: int         # Всего шагов
    started_at: float
    completed_at: float | None = None
    config_type: str | None = None  # Для теста 7.3: "1" или "2"
```

### 4.2. Интеграция с `CoreEngine`

```python
@dataclass
class CoreEngine:
    test_session: TestSession = field(default_factory=TestSession)

    async def start_session(self) -> None:
        """Активировать сеанс проверок (ТЗ п. 2.2.1)."""
        creds = self.credentials_repo.get_default()
        self.test_session.activate(self.config, creds)
        await self.bus.emit("session.started", {"timestamp": time.time()})

    async def stop_session(self) -> None:
        """Завершить сеанс (ТЗ п. 2.2.5)."""
        self.test_session.deactivate()
        await self.bus.emit("session.completed", {
            "test_results": {k: v.__dict__ for k, v in self.test_session.test_results.items()},
        })

    async def on_network_off(self) -> None:
        """Выключение сети — сброс статусов (ТЗ п. 2.2.5)."""
        self.test_session.reset_on_network_off()
        await self.bus.emit("session.statuses_reset", {})
```

### 4.3. Подписка на события для обновления статусов

```python
# В CoreEngine.start():
self.bus.on("cmw.connected", self._on_cmw_connected)
self.bus.on("cmw.disconnected", self._on_cmw_disconnected)
self.bus.on("connection.changed", self._on_connection_changed)
self.bus.on("auth.validation_passed", self._on_auth_passed)
self.bus.on("auth.validation_failed", self._on_auth_failed)

async def _on_cmw_connected(self, data: dict) -> None:
    self.test_session.cmw_connected = True

async def _on_cmw_disconnected(self, data: dict) -> None:
    self.test_session.cmw_connected = False
    await self.on_network_off()

async def _on_connection_changed(self, data: dict) -> None:
    state = data.get("state")
    if state == "connected":
        self.test_session.tcp_connected = True
    elif state == "disconnected":
        self.test_session.tcp_connected = False

async def _on_auth_passed(self, data: dict) -> None:
    self.test_session.auth_done = True
    self.test_session.auth_validation_passed = True
```

### 4.4. Тесты

**Файлы:**
- `tests/core/test_test_session.py`

---

## Этап 5 — Специализированные проверки ТЗ (через сценарии)

**Цель:** Реализовать 5 проверок ТЗ (п. 7.3, 6.8, 6.9, 7.8, 9.2.2) через существующую систему сценариев — **без** создания отдельных Python-классов тестов.

### 5.1. Архитектурный принцип

Все проверки ТЗ выполняются через **сценарии JSON** (`scenarios/`) + `ScenarioManager`.
Инфраструктура (EventBus, TestSession, AuthValidationMiddleware, FSM) уже работает.
Сценарии описывают последовательность пакетов, а система автоматически:
- Валидирует авторизацию (AuthValidationMiddleware, order=2.5)
- Обновляет статусы (TestSession через EventBus подписки)
- Ведёт FSM (UsvStateMachine)
- Логирует 100% пакетов (LogManager)

### 5.2. Реализовать тип шага `wait` — ожидание события EventBus

**Файл:** `core/scenario.py`

```python
@dataclass
class WaitStep:
    """Шаг ожидания события EventBus с условием.

    Примеры использования:
    - Ожидание TCP-соединения (connection.changed → state="connected")
    - Ожидание регистрации УСВ (cmw.status → imsi="25077...")
    - Ожидание авторизации (auth.validation_passed)
    """

    name: str
    event: str              # Имя события EventBus
    condition: dict         # Условие: field → expected_value
    timeout: float = 30.0
    capture: dict[str, str] = field(default_factory=dict)  # var_name → field_path

    async def execute(self, ctx: ScenarioContext, bus: EventBus, timeout: float | None = None) -> str:
        """Подписаться на event, ждать совпадения condition, извлечь capture."""
        eff_timeout = timeout or self.timeout
        event = asyncio.Event()
        result_container: dict[str, str] = {"status": "PENDING"}

        def _on_event(data: dict) -> None:
            # Проверка condition (exact match по полям)
            for field, expected in self.condition.items():
                actual = data.get(field)
                if actual != expected:
                    return  # Не совпало — ждём дальше
            # Совпало — извлечь capture
            for var_name, field_path in self.capture.items():
                value = data.get(field_path)
                if value is not None:
                    ctx.set(var_name, value)
            result_container["status"] = "PASS"
            event.set()

        bus.on(self.event, _on_event)
        try:
            await asyncio.wait_for(event.wait(), timeout=eff_timeout)
        except TimeoutError:
            result_container["status"] = "TIMEOUT"
        finally:
            bus.off(self.event, _on_event)

        return result_container["status"]
```

**Пример в сценарии:**
```json
{
  "name": "Ожидание TCP-соединения",
  "type": "wait",
  "event": "connection.changed",
  "condition": {"state": "connected"},
  "timeout": 30,
  "capture": {"usv_id": "usv_id"}
}
```

### 5.3. Реализовать тип шага `check` — проверка условий

**Файл:** `core/scenario.py`

```python
@dataclass
class CheckStep:
    """Шаг проверки условий (статусы TestSession, переменные, диапазоны).

    Примеры:
    - Проверка что config_done=false (предварительные условия)
    - Проверка что получено ≥600 сэмплов ускорения
    - Проверка что VIN совпадает с конфигурацией
    """

    name: str
    check_type: str         # "session_status", "variable", "range"
    target: str             # Путь: "config_done", "accel_samples", "vehicle.vin"
    expected: Any           # Ожидаемое значение или {"min": N, "max": N}
    timeout: float = 5.0

    async def execute(self, ctx: ScenarioContext, bus: EventBus,
                      timeout: float | None = None,
                      engine: Any = None) -> str:  # engine для доступа к test_session
        eff_timeout = timeout or self.timeout
        start = time.monotonic()

        while (time.monotonic() - start) < eff_timeout:
            actual = self._resolve(engine, ctx)
            if self._matches(actual):
                return "PASS"
            await asyncio.sleep(0.1)

        return "FAIL"

    def _resolve(self, engine: Any, ctx: ScenarioContext) -> Any:
        if self.check_type == "session_status" and engine:
            return getattr(engine.test_session, self.target, None)
        if self.check_type == "variable":
            return ctx.get(self.target)
        return None

    def _matches(self, actual: Any) -> bool:
        if isinstance(self.expected, dict) and "min" in self.expected:
            if not isinstance(actual, (int, float)):
                return False
            return actual >= self.expected["min"]
        return actual == self.expected
```

**Пример в сценарии:**
```json
{
  "name": "Проверка предварительных условий",
  "type": "check",
  "check_type": "session_status",
  "target": "config_done",
  "expected": false
}
```

### 5.4. Обновить StepFactory

**Файл:** `core/scenario.py`

```python
class StepFactory:
    @staticmethod
    def create(step_def: StepDefinition) -> Step:
        if step_def.type == "expect":
            return ExpectStep(...)
        if step_def.type == "send":
            return SendStep(...)
        if step_def.type == "wait":
            return WaitStep(
                name=step_def.name,
                event=step_def.extra.get("event", ""),
                condition=step_def.extra.get("condition", {}),
                timeout=step_def.timeout or 30.0,
                capture=step_def.capture,
            )
        if step_def.type == "check":
            return CheckStep(
                name=step_def.name,
                check_type=step_def.extra.get("check_type", ""),
                target=step_def.extra.get("target", ""),
                expected=step_def.extra.get("expected"),
                timeout=step_def.timeout or 5.0,
            )
        raise NotImplementedError(f"Step type '{step_def.type}' is not implemented")
```

### 5.5. Обновить ScenarioParserV1.validate()

Добавить валидацию обязательных полей для новых типов:

```python
# В validate(), внутри цикла по шагам:
if step_type == "wait":
    if "event" not in step:
        errors.append(f"{prefix}: Missing 'event' field for wait step")
    if "condition" not in step:
        errors.append(f"{prefix}: Missing 'condition' field for wait step")

if step_type == "check":
    if "check_type" not in step:
        errors.append(f"{prefix}: Missing 'check_type' field for check step")
    if "target" not in step:
        errors.append(f"{prefix}: Missing 'target' field for check step")
    if "expected" not in step:
        errors.append(f"{prefix}: Missing 'expected' field for check step")
```

### 5.6. Интеграция результатов сценариев с TestSession

**Файл:** `core/engine.py`

Обновить `run_scenario()` чтобы сохранять результат как `TestResult`:

```python
async def run_scenario(self, scenario_path: str, connection_id: str | None = None,
                       test_name: str | None = None) -> dict[str, Any]:
    """Запустить сценарий и сохранить результат в TestSession."""
    if not self.is_running:
        raise RuntimeError("CoreEngine не запущен")

    if self.scenario_mgr is None:
        return {"status": "error", "error": "ScenarioManager не инициализирован"}

    scenario_path_obj = Path(scenario_path)
    if scenario_path_obj.is_dir():
        scenario_path_obj = scenario_path_obj / "scenario.json"

    self.scenario_mgr.load(scenario_path_obj)
    scenario_timeout = self.scenario_mgr.metadata.timeout or 60.0

    result = await self.scenario_mgr.execute(
        bus=self.bus, connection_id=connection_id, timeout=scenario_timeout,
    )
    history = self.scenario_mgr.context.history

    # Сохранить в TestSession как TestResult
    if self.test_session.state == SessionState.ACTIVE:
        test_name = test_name or self.scenario_mgr.metadata.name
        test_result = TestResult(
            test_name=test_name,
            passed=(result == "PASS"),
            reasons=[h.details for h in history if h.result != "PASS"],
            steps_completed=sum(1 for h in history if h.result == "PASS"),
            steps_total=len(history),
            started_at=time.time() - sum(h.duration for h in history),
            completed_at=time.time(),
        )
        self.test_session.test_results[test_name] = test_result

    return {
        "name": self.scenario_mgr.metadata.name,
        "status": result,
        "steps_total": len(history),
        "steps_passed": sum(1 for h in history if h.result == "PASS"),
    }
```

### 5.7. Сценарии для 5 проверок ТЗ

#### 5.7.1. п. 7.3 — Пассивный режим (конфигурирование №1)

**Файл:** `scenarios/test_7_3_config1/scenario.json`

```json
{
  "name": "Тест 7.3 — Пассивный режим (конфиг №1)",
  "scenario_version": "1",
  "gost_version": "ГОСТ 33465-2015",
  "timeout": 120,
  "description": "Полный алгоритм пассивного режима: конфигурирование через SMS, авторизация, аутентификация",
  "channels": ["tcp", "sms"],
  "steps": [
    {
      "name": "Проверка: конфигурирование не выполнено",
      "type": "check",
      "check_type": "session_status",
      "target": "config_done",
      "expected": false
    },
    {
      "name": "Проверка: TCP не подключён",
      "type": "check",
      "check_type": "session_status",
      "target": "tcp_connected",
      "expected": false
    },
    {
      "name": "Ожидание регистрации УСВ (IMSI)",
      "type": "wait",
      "event": "cmw.status",
      "condition": {},
      "timeout": 60,
      "capture": {"registered_imsi": "imsi"}
    },
    {
      "name": "Конфигурирование: GPRS APN (SMS)",
      "type": "send",
      "channel": "sms",
      "packet_file": "packets/platform/gprs_apn.hex",
      "timeout": 10
    },
    {
      "name": "Подтверждение APN",
      "type": "expect",
      "channel": "sms",
      "checks": {"subrecord_type": "CT_COMCONF"},
      "timeout": 10
    },
    {
      "name": "Конфигурирование: Server Address (SMS)",
      "type": "send",
      "channel": "sms",
      "packet_file": "packets/platform/server_address.hex",
      "timeout": 10
    },
    {
      "name": "Подтверждение Server Address",
      "type": "expect",
      "channel": "sms",
      "checks": {"subrecord_type": "CT_COMCONF"},
      "timeout": 10
    },
    {
      "name": "Конфигурирование: UNIT_ID (SMS)",
      "type": "send",
      "channel": "sms",
      "packet_file": "packets/platform/unit_id.hex",
      "timeout": 10
    },
    {
      "name": "Подтверждение UNIT_ID",
      "type": "expect",
      "channel": "sms",
      "checks": {"subrecord_type": "CT_COMCONF"},
      "timeout": 10
    },
    {
      "name": "Ожидание TCP-соединения",
      "type": "wait",
      "event": "connection.changed",
      "condition": {"state": "connected"},
      "timeout": 30
    },
    {
      "name": "Ожидание TERM_IDENTITY",
      "type": "expect",
      "channel": "tcp",
      "checks": {"service": 1},
      "capture": {"tid": "TID", "imei": "IMEI", "imsi": "IMSI"},
      "timeout": 10
    },
    {
      "name": "Ожидание VEHICLE_DATA",
      "type": "expect",
      "channel": "tcp",
      "checks": {"service": 5},
      "capture": {"vin": "VIN", "category": "vehicle_category", "fuel_type": "fuel_type"},
      "timeout": 10
    },
    {
      "name": "Service Info (ST=10 accept)",
      "type": "send",
      "channel": "tcp",
      "build": {
        "gost_version": "2015",
        "packet": {
          "packet_id": 99,
          "packet_type": 2,
          "records": [{
            "record_id": 1,
            "service_type": 10,
            "subrecords": [{
              "subrecord_type": 7,
              "data": {"service_type": 10, "service_status": 0}
            }]
          }]
        }
      },
      "timeout": 5
    },
    {
      "name": "RESULT_CODE (AUTH_OK)",
      "type": "send",
      "channel": "tcp",
      "packet_file": "packets/platform/result_code.hex",
      "timeout": 5
    },
    {
      "name": "Подтверждение RESULT_CODE",
      "type": "expect",
      "channel": "tcp",
      "checks": {"subrecord_type": "EGTS_SR_RECORD_RESPONSE", "rst": 0},
      "timeout": 5
    }
  ]
}
```

#### 5.7.2. п. 7.3 — Пассивный режим (конфигурирование №2)

**Файл:** `scenarios/test_7_3_config2/scenario.json`

Аналогично конфиг №1, но без шагов конфигурирования (шаги 4-9). УСВ уже сконфигурировано.

#### 5.7.3. п. 6.8 — Профиль ускорения

**Файл:** `scenarios/test_6_8/scenario.json`

```json
{
  "name": "Тест 6.8 — Профиль ускорения",
  "scenario_version": "1",
  "gost_version": "ГОСТ 33465-2015",
  "timeout": 180,
  "description": "Приём профиля ускорения: ≥600 выборок (250×1мс + 350×10мс)",
  "channels": ["tcp", "sms"],
  "steps": [
    {
      "name": "Проверка: конфигурирование выполнено",
      "type": "check",
      "check_type": "session_status",
      "target": "config_done",
      "expected": true
    },
    {
      "name": "Ожидание TCP-соединения",
      "type": "wait",
      "event": "connection.changed",
      "condition": {"state": "connected"},
      "timeout": 30
    },
    {
      "name": "Ожидание TERM_IDENTITY",
      "type": "expect",
      "channel": "tcp",
      "checks": {"service": 1},
      "timeout": 10
    },
    {
      "name": "RESULT_CODE (AUTH_OK)",
      "type": "send",
      "channel": "tcp",
      "packet_file": "packets/platform/result_code.hex",
      "timeout": 5
    },
    {
      "name": "Service Info (ST=10)",
      "type": "send",
      "channel": "tcp",
      "build": {
        "gost_version": "2015",
        "packet": {
          "packet_id": 99,
          "packet_type": 2,
          "records": [{
            "record_id": 1,
            "service_type": 10,
            "subrecords": [{
              "subrecord_type": 7,
              "data": {"service_type": 10, "service_status": 0}
            }]
          }]
        }
      },
      "timeout": 5
    },
    {
      "name": "Команда: запрос профиля ускорения (SMS)",
      "type": "send",
      "channel": "sms",
      "packet_file": "packets/platform/accel_data_request.hex",
      "timeout": 10
    },
    {
      "name": "Подтверждение SMS-команды",
      "type": "expect",
      "channel": "sms",
      "checks": {"subrecord_type": "CT_COMCONF"},
      "timeout": 10
    },
    {
      "name": "Приём данных профиля ускорения",
      "type": "expect",
      "channel": "tcp",
      "checks": {"service": 2, "subrecord_type": "EGTS_SR_ACCEL_DATA"},
      "capture": {"accel_points_count": "points_count"},
      "timeout": 60
    },
    {
      "name": "Проверка: ≥600 выборок",
      "type": "check",
      "check_type": "variable",
      "target": "accel_points_count",
      "expected": {"min": 600}
    },
    {
      "name": "Подтверждение профиля ускорения",
      "type": "send",
      "channel": "tcp",
      "packet_file": "packets/platform/record_response_accel.hex",
      "timeout": 5
    }
  ]
}
```

#### 5.7.4. п. 6.9 — Траектория движения

**Файл:** `scenarios/test_6_9/scenario.json`

Аналогично п. 6.8, но:
- Команда: `packets/platform/track_data_request.hex`
- Проверка: `expected: {"min": 70}` (координаты, 1с интервал)
- Подтверждение: `packets/platform/record_response_track.hex`

#### 5.7.5. п. 7.8 — Загрузка ПО

**Файл:** `scenarios/test_7_8/scenario.json`

```json
{
  "name": "Тест 7.8 — Загрузка ПО",
  "scenario_version": "1",
  "gost_version": "ГОСТ 33465-2015",
  "timeout": 300,
  "description": "Передача ПО частями через TCP/IP, проверка целостности",
  "channels": ["tcp"],
  "steps": [
    {
      "name": "Проверка: авторизация пройдена",
      "type": "check",
      "check_type": "session_status",
      "target": "auth_done",
      "expected": true
    },
    {
      "name": "Часть 1 прошивки",
      "type": "send",
      "channel": "tcp",
      "packet_file": "packets/platform/service_part_data_1.hex",
      "timeout": 30
    },
    {
      "name": "Подтверждение части 1 (IN_PROGRESS)",
      "type": "expect",
      "channel": "tcp",
      "checks": {"subrecord_type": "EGTS_SR_RECORD_RESPONSE", "rst": 1},
      "timeout": 10
    },
    {
      "name": "Часть 2 прошивки",
      "type": "send",
      "channel": "tcp",
      "packet_file": "packets/platform/service_part_data_2.hex",
      "timeout": 30
    },
    {
      "name": "Подтверждение части 2 (OK)",
      "type": "expect",
      "channel": "tcp",
      "checks": {"subrecord_type": "EGTS_SR_RECORD_RESPONSE", "rst": 0},
      "timeout": 10
    }
  ]
}
```

#### 5.7.6. п. 9.2.2 — Изменение параметров

**Файл:** `scenarios/test_9_2_2/scenario.json`

```json
{
  "name": "Тест 9.2.2 — Изменение параметров (MIC/SPK)",
  "scenario_version": "1",
  "gost_version": "ГОСТ 33465-2015",
  "timeout": 60,
  "description": "Изменение уровня микрофона и динамика через EGTS_COMMANDS_SERVICE",
  "channels": ["tcp"],
  "steps": [
    {
      "name": "Проверка: авторизация пройдена",
      "type": "check",
      "check_type": "session_status",
      "target": "auth_done",
      "expected": true
    },
    {
      "name": "Команда: MIC level = 5",
      "type": "send",
      "channel": "tcp",
      "build": {
        "gost_version": "2015",
        "packet": {
          "packet_id": 50,
          "packet_type": 2,
          "records": [{
            "record_id": 1,
            "service_type": 4,
            "subrecords": [{
              "subrecord_type": 30,
              "data": {
                "command_code_hex": "0501",
                "params_hex": "0405"
              }
            }]
          }]
        }
      },
      "timeout": 10
    },
    {
      "name": "Подтверждение MIC level",
      "type": "expect",
      "channel": "tcp",
      "checks": {"subrecord_type": "CT_COMCONF"},
      "timeout": 10
    },
    {
      "name": "Команда: SPK level = 5",
      "type": "send",
      "channel": "tcp",
      "build": {
        "gost_version": "2015",
        "packet": {
          "packet_id": 51,
          "packet_type": 2,
          "records": [{
            "record_id": 1,
            "service_type": 4,
            "subrecords": [{
              "subrecord_type": 30,
              "data": {
                "command_code_hex": "0502",
                "params_hex": "0505"
              }
            }]
          }]
        }
      },
      "timeout": 10
    },
    {
      "name": "Подтверждение SPK level",
      "type": "expect",
      "channel": "tcp",
      "checks": {"subrecord_type": "CT_COMCONF"},
      "timeout": 10
    }
  ]
}
```

### 5.8. Тесты

**Файлы:**
- `tests/core/test_scenario_wait_step.py` — WaitStep unit-тесты
- `tests/core/test_scenario_check_step.py` — CheckStep unit-тесты
- `tests/core/test_scenario_integration.py` — интеграционные тесты сценариев с TestSession

**Каждый тест:**
- WaitStep: ожидание события, condition match/mismatch, timeout, capture
- CheckStep: session_status, variable, range check, polling
- Integration: запуск сценария → проверка что TestResult сохранён в TestSession

---

## Этап 6 — Отчёты по тестам (ТЗ п. 1.7, 2.2.7)

**Цель:** Создать модуль формирования отчётов с результатами тестов из TestSession + история сценариев.

### 6.1. Создать `core/report.py`

```python
@dataclass
class TestReport:
    """Отчёт о проверках (ТЗ п. 2.2.7)."""
    session: TestSession
    generated_at: float = field(default_factory=time.time)

    def to_json(self) -> dict[str, Any]:
        return {
            "report_type": "ПАК проверка УВ",
            "generated_at": datetime.fromtimestamp(self.generated_at).isoformat(),
            "session": {
                "started_at": datetime.fromtimestamp(self.session.started_at).isoformat() if self.session.started_at else None,
                "completed_at": datetime.fromtimestamp(self.session.completed_at).isoformat() if self.session.completed_at else None,
                "state": self.session.state.value,
            },
            "configuration_parameters": self.session.config_snapshot or {},
            "credentials_parameters": self.session.credentials_snapshot or {},
            "test_results": {
                name: {
                    "passed": result.passed,
                    "reasons": result.reasons,
                    "steps_completed": result.steps_completed,
                    "steps_total": result.steps_total,
                    "config_type": result.config_type,
                }
                for name, result in self.session.test_results.items()
            },
            "summary": {
                "total_tests": len(self.session.test_results),
                "passed": sum(1 for r in self.session.test_results.values() if r.passed),
                "failed": sum(1 for r in self.session.test_results.values() if not r.passed),
            },
        }

    def to_html(self) -> str:
        """HTML-отчёт для печати."""
        # Простой HTML с таблицей результатов
        ...

    def save_json(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")

    def save_html(self, path: str) -> None:
        Path(path).write_text(self.to_html(), encoding="utf-8")
```

### 6.2. Интеграция с `CoreEngine`

```python
async def generate_report(self, output_path: str, fmt: str = "json") -> None:
    """Сформировать отчёт (ТЗ п. 2.2.7)."""
    if self.test_session.state != SessionState.COMPLETED:
        raise RuntimeError("Сеанс не завершён")

    report = TestReport(session=self.test_session)
    if fmt == "json":
        report.save_json(output_path)
    elif fmt == "html":
        report.save_html(output_path)
    else:
        raise ValueError(f"Unsupported format: {fmt}")
```

### 6.3. Тесты

**Файлы:**
- `tests/core/test_report.py` — round-trip JSON, HTML генерация, save

---

## Этап 7 — Интеграция и end-to-end тесты

**Цель:** Связать все компоненты и проверить полные сценарии через `Cmw500Emulator`.

### 8.1. Обновить `CoreEngine` — API для запуска проверок ТЗ

```python
@dataclass
class CoreEngine:
    # Существующие поля...

    async def run_tz_test(self, test_id: str, **kwargs) -> dict[str, Any]:
        """Запустить проверку ТЗ по ID.

        test_id: "7.3_config1", "7.3_config2", "6.8", "6.9", "7.8", "9.2.2"
        """
        scenario_map = {
            "7.3_config1": "scenarios/test_7_3_config1",
            "7.3_config2": "scenarios/test_7_3_config2",
            "6.8": "scenarios/test_6_8",
            "6.9": "scenarios/test_6_9",
            "7.8": "scenarios/test_7_8",
            "9.2.2": "scenarios/test_9_2_2",
        }
        scenario_path = scenario_map.get(test_id)
        if not scenario_path:
            raise ValueError(f"Unknown test ID: {test_id}")

        return await self.run_scenario(scenario_path, test_name=test_id, **kwargs)

    async def run_all_tz_tests(self) -> dict[str, dict[str, Any]]:
        """Запустить все проверки ТЗ последовательно."""
        results = {}
        for test_id in ["7.3_config1", "7.3_config2", "6.8", "6.9", "7.8", "9.2.2"]:
            try:
                results[test_id] = await self.run_tz_test(test_id)
            except Exception as e:
                results[test_id] = {"status": "error", "error": str(e)}
        return results
```

### 8.2. End-to-end тесты

**Файлы:**
- `tests/integration/test_e2e_passive_mode.py` — полный flow через эмулятор
- `tests/integration/test_e2e_accel_profile.py` — профиль ускорения с валидацией 600 сэмплов
- `tests/integration/test_e2e_trajectory.py` — траектория с валидацией 70 точек
- `tests/integration/test_e2e_firmware.py` — загрузка ПО частями
- `tests/integration/test_e2e_param_change.py` — изменение MIC/SPK level

**Каждый тест:**
- Использует `Cmw500Emulator`
- Эмулирует УСВ (отправка TERM_IDENTITY, VEHICLE_DATA, ACCEL_DATA, ...)
- Запускает сценарий через `CoreEngine.run_scenario()`
- Проверяет что TestResult сохранён в TestSession
- Проверяет статусы TestSession

### 8.3. Обновить документацию

**Файлы:**
- `docs/ARCHITECTURE.md` — обновить диаграммы, добавить WaitStep, CheckStep, TestReport
- `docs/CMW500_SPEC.md` — обновить список SCPI-команд (voice, MSD)
- Добавить `docs/TEST_SCENARIOS.md` — описание 6 сценариев проверок ТЗ

---

## Сводный план по этапам

| Этап | Область | Файлы (новые) | Файлы (изменения) | Оценочная сложность |
|------|---------|---------------|-------------------|---------------------|
| **1** | Конфигурация | — | `config.py`, `credentials.py`, `engine.py`, `cmw500.py` | Низкая |
| **2** | EGTS подзаписи | `command_params.py` | `types.py`, `subrecords.py`, `registry.py` | Средняя |
| **3** | Валидация | `validators/auth_validator.py`, `validators/service_info_validator.py` | `session.py`, `event_bus.py` | Средняя |
| **4** | Сеанс | `test_session.py` | `engine.py` | Средняя |
| **5** | 5 проверок ТЗ | 6 сценариев JSON | `scenario.py`, `scenario_parser.py`, `engine.py` | Средняя |
| **6** | Отчёты | `report.py` | `engine.py` | Низкая |
| **7** | CMW voice/МНД | `msd_decoder.py` | `cmw500.py` | Высокая |
| **7** | Интеграция | 5 e2e тестов | `engine.py`, `ARCHITECTURE.md` | Средняя |

---

## Критические исправления (сделать в первую очередь)

1. **MNC 60 → 77** — `core/config.py` строка `mnc: int = 60` → `mnc: int = 77`
2. **VISA resource string** — вынести в конфиг, не хардкодить
3. **VehicleConfig** — создать dataclass с VIN, category, fuel_type
4. **Credentials поля** — добавить IMSI, IMEI, MSISDN, serial_number, model, egts_unit_id

---

## Зависимости между этапами

```
Этап 1 (Конфигурация)
    ↓
Этап 2 (EGTS подзаписи)
    ↓
Этап 3 (Валидация) ← использует Этап 1 + Этап 2
    ↓
Этап 4 (Сеанс) ← использует Этап 1
    ↓
Этап 5 (5 проверок ТЗ) ← использует Этапы 1-4 + сценарии JSON
    ↓
Этап 6 (Отчёты) ← использует Этап 4 + Этап 5
    ↓
Этап 7 (CMW voice/МНД) — параллельно с Этапами 1-4
    ↓
Этап 7 (Интеграция) ← использует все предыдущие
```

**Параллельно можно делать:**
- Этапы 1 + 7 (независимы)
- Этапы 2 + 7 (независимы)
- Этап 6 после Этапа 4 (не ждёт Этап 5)

---

## Риски и ограничения

| Риск | Влияние | Митигация |
|------|---------|-----------|
| SCPI-команды CMW-500 могут отличаться от ожидаемых | Высокое | Тестировать на реальном приборе на ранних этапах |
| Тоновой модем МНД — сложная DSP-задача | Высокое | Использовать готовую библиотеку (например, `goertzel`) |
| Эмулятор УСВ для интеграционных тестов | Среднее | Создать простой mock, который отправляет заранее записанные пакеты |
| Обратная совместимость сценариев JSON | Среднее | Не менять формат V1, добавить `wait`/`check` как новые типы |
| Время таймаутов в ТЗ (ГОСТ п. 6.8) | Низкое | Вынести все таймауты в `TimeoutsConfig` |
