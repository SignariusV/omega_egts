# План реализации ядра OMEGA_EGTS по ТЗ на ПАК

> **Дата:** 2026-05-15
> **Основание:** ТЗ на ПАК (редакция 2), ГОСТ 33464-2015, ГОСТ 33465-2015
> **Объект:** Ядро (`core/`) — без GUI
> **Текущая готовность ядра:** ~45%

---

## Стратегия реализации

План разбит на **8 этапов**, каждый из которых:
- Добавляет конкретную функциональность ядра
- Покрывается unit/integration тестами
- Не ломает существующую архитектуру (EventBus, pipeline, FSM)
- Может быть выполнен независимо от GUI

**Принципы:**
1. Сначала конфигурация и данные → потом логика → потом тесты
2. Каждый этап — отдельная ветка git
3. Тесты пишутся одновременно с кодом (≥90% coverage)
4. Обратная совместимость: старые сценарии JSON продолжают работать

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

## Этап 5 — Специализированные тесты (5 проверок ТЗ)

**Цель:** Создать 5 классов тестов с пошаговой логикой согласно ТЗ.

### 5.1. Архитектура тестов

```
core/test_suite/
    __init__.py
    base_test.py           # Базовый класс для всех тестов
    passive_mode_test.py   # Тест п. 7.3 (конфиг №1 и №2)
    accel_profile_test.py  # Тест п. 6.8
    trajectory_test.py     # Тест п. 6.9
    firmware_test.py       # Тест п. 7.8
    param_change_test.py   # Тест п. 9.2.2
```

### 5.2. Базовый класс `core/test_suite/base_test.py`

```python
from abc import ABC, abstractmethod
from core.test_session import TestSession, TestResult
from core.event_bus import EventBus
from core.config import Config
from core.credentials import Credentials

class BaseTest(ABC):
    """Базовый класс для всех проверок ТЗ."""

    def __init__(
        self,
        bus: EventBus,
        session: TestSession,
        config: Config,
        credentials: Credentials,
    ):
        self.bus = bus
        self.session = session
        self.config = config
        self.credentials = credentials
        self._active = False
        self._result: TestResult | None = None
        self._cancel_event = asyncio.Event()

    @property
    @abstractmethod
    def test_name(self) -> str:
        """Имя теста: '7.3', '6.8', '6.9', '7.8', '9.2.2'."""

    @property
    @abstractmethod
    def total_steps(self) -> int:
        """Общее количество шагов алгоритма."""

    async def activate(self) -> None:
        """Активировать проверку (ТЗ п. 2.3.x б)."""
        self._active = True
        self._cancel_event.clear()
        self._result = TestResult(
            test_name=self.test_name,
            passed=False,
            reasons=[],
            steps_completed=0,
            steps_total=self.total_steps,
            started_at=time.time(),
        )

    async def deactivate(self) -> None:
        """Деактивировать проверку (ТЗ п. 2.3.x в)."""
        self._active = False
        self._cancel_event.set()
        if self._result:
            self._result.completed_at = time.time()
            self.session.test_results[self.test_name] = self._result

    async def cancel(self) -> None:
        """Принудительная остановка (ТЗ: сброс всех параметров)."""
        await self.deactivate()
        self._result = None

    @abstractmethod
    async def run(self) -> TestResult:
        """Выполнить алгоритм проверки."""

    async def _step(self, step_num: int, condition: bool, fail_reason: str) -> bool:
        """Выполнить один шаг. Возвращает True если шаг пройден."""
        if not self._active:
            return False

        if self._result:
            self._result.steps_completed = step_num

        if not condition:
            if self._result:
                self._result.reasons.append(fail_reason)
            return False
        return True

    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set()
```

### 5.3. Тест п. 7.3 — Пассивный режим `core/test_suite/passive_mode_test.py`

**Алгоритм конфигурирования №1 (16 шагов):**

```python
class PassiveModeTest(BaseTest):
    test_name = "7.3"
    total_steps = 16  # Для конфига №1

    def __init__(self, ..., config_type: str = "1", auth_response: bool = True):
        super().__init__(...)
        self.config_type = config_type  # "1" или "2"
        self.auth_response = auth_response  # Ответ на авторизацию да/нет

    async def run(self) -> TestResult:
        await self.activate()

        # Шаг 2: Проверка предварительных условий
        if not await self._step(2,
            not self.session.config_done
            and not self.session.tcp_connected
            and not self.session.auth_done,
            "Конфигурирование уже выполнено / TCP соединение уже установлено / Авторизация уже пройдена"
        ):
            return await self._fail()

        # Шаг 3: Ожидание регистрации на IMSI (NID=25077)
        imsi = await self._wait_for_registration()
        if not await self._step(3, imsi is not None, "УВ не зарегистрировалось"):
            return await self._fail()

        self.session.usv_registered = True
        self.session.registered_imsi = imsi

        if self.config_type == "1":
            return await self._run_config_1()
        else:
            return await self._run_config_2()

    async def _run_config_1(self) -> TestResult:
        """Конфигурирование №1 (ТЗ п. 2.3.1.1)."""

        # Шаг 5: Установка параметров через SMS
        params = [
            (EgtsCommandParamType.EGTS_GPRS_APN, self.config.cmw500.dau_ip),
            (EgtsCommandParamType.EGTS_SERVER_ADDRESS, self.config.cmw500.test_system_ip),
            (EgtsCommandParamType.EGTS_UNIT_ID, self.credentials.egts_unit_id),
        ]
        for param_type, value in params:
            success = await self._send_config_command(param_type, value)
            if not await self._step(5, success, f"Конфигурирование не удалось ({param_type.name})"):
                return await self._fail()

        self.session.config_done = True

        # Шаг 6: Ожидание TCP/IP соединения (30 сек)
        tcp_ok = await self._wait_for_tcp_connection(timeout=30.0)
        if not await self._step(6, tcp_ok, "Не удалось установить соединение TCP/IP"):
            return await self._fail()

        # Шаг 7: Ожидание TERM_IDENTITY (авторизация)
        term_identity = await self._wait_for_term_identity()
        if not await self._step(7, term_identity is not None, "Авторизация не удалась"):
            return await self._fail()

        # Шаг 8: Сверка TERM_IDENTITY с настройками
        validation = self.auth_validator.validate_term_identity(
            unit_id=term_identity.unit_id,
            imsi=term_identity.imsi,
            imei=term_identity.imei,
            msisdn=term_identity.msisdn,
        )
        if not await self._step(8, validation.passed, f"Авторизационные параметры не совпадают: {validation.reasons}"):
            return await self._fail()

        # Шаг 9: Ожидание VEHICLE_DATA (аутентификация)
        vehicle_data = await self._wait_for_vehicle_data()
        if not await self._step(9, vehicle_data is not None, "Аутентификация не удалась"):
            return await self._fail()

        # Шаг 10: Сверка VEHICLE_DATA с настройками
        validation = self.auth_validator.validate_vehicle_data(
            vin=vehicle_data.vin,
            category=vehicle_data.category,
            fuel_type=vehicle_data.fuel_type,
        )
        if not await self._step(10, validation.passed, f"Аутентификационные параметры не совпадают: {validation.reasons}"):
            return await self._fail()

        # Шаг 11: Service Info negotiation
        if not await self._handle_service_info():
            return await self._fail()

        # Шаг 12: Отправка RESULT_CODE
        result_code = 0 if self.auth_response else 151  # 151 = AUTH_DENIED
        success = await self._send_result_code(result_code)
        if not await self._step(12, success, "Авторизация/аутентификация не удалась"):
            return await self._fail()

        # Шаг 13: Обновление статусов
        self.session.auth_done = True
        self.session.auth_result = self.auth_response
        if not self.auth_response:
            return await self._fail("В авторизации/аутентификации отказано по решению пользователя")

        # Успех
        if self._result:
            self._result.passed = True
        return await self._succeed()
```

**Методы-хелперы:**

```python
    async def _wait_for_registration(self, timeout=60.0) -> str | None:
        """Ожидание регистрации УВ на профиле IMSI (NID=25077)."""
        # Подписка на cmw.status → проверка IMSI
        # Возвращает IMSI или None по таймауту

    async def _send_config_command(self, param_type, value) -> bool:
        """Отправка команды конфигурирования через SMS."""
        # Строит EGTS_SR_COMMAND_DATA → EGTS_PT_APPDATA → SMS
        # Ждёт подтверждение EGTS_SR_COMMAND_DATA

    async def _wait_for_tcp_connection(self, timeout=30.0) -> bool:
        """Ожидание TCP/IP соединения."""
        # Подписка на connection.changed → state="connected"

    async def _wait_for_term_identity(self, timeout=10.0) -> dict | None:
        """Ожидание TERM_IDENTITY от УВ."""
        # Подписка на packet.processed → service=1

    async def _wait_for_vehicle_data(self, timeout=10.0) -> dict | None:
        """Ожидание VEHICLE_DATA от УВ."""
        # Подписка на packet.processed → service=5

    async def _handle_service_info(self) -> bool:
        """Service Info negotiation (ST=10, отказ другим)."""
        # Отправка EGTS_SR_SERVICE_INFO (ST=10, status=0)
        # Если УВ запросит другой сервис → отказ (status=1)

    async def _send_result_code(self, code: int) -> bool:
        """Отправка EGTS_SR_RESULT_CODE."""
        # Строит RECORD → EGTS_PT_APPDATA → TCP
        # Ждёт RECORD_RESPONSE
```

### 5.4. Тест п. 6.8 — Профиль ускорения `core/test_suite/accel_profile_test.py`

```python
class AccelProfileTest(BaseTest):
    test_name = "6.8"
    total_steps = 18

    REQUIRED_SAMPLES = 600  # 250×1мс + 350×10мс
    MAX_SAMPLES_PER_RECORD = 255

    async def run(self) -> TestResult:
        await self.activate()

        # Шаг 2: Проверка предварительных условий
        if not await self._step(2,
            self.session.config_done and self.session.vehicle_auth_done,
            "Конфигурирование не выполнено / Аутентификация не пройдена"
        ):
            return await self._fail()

        # Шаг 3-4: Ожидание экстренного вызова + регистрация
        imsi = await self._wait_for_emergency_call()
        if not await self._step(4, imsi is not None, "Экстренный вызов не получен"):
            return await self._fail()

        # Шаг 6: Приём МНД
        mnd = await self._wait_for_mnd(timeout=60.0)
        if not await self._step(6, mnd is not None, "МНД не принято"):
            return await self._fail()

        # Шаг 7: TCP соединение (30 сек)
        tcp_ok = await self._wait_for_tcp_connection(timeout=30.0)
        if not await self._step(7, tcp_ok, "Не удалось установить соединение TCP/IP"):
            return await self._fail()

        # Шаг 8-9: Авторизация + валидация
        term_identity = await self._wait_for_term_identity()
        if not await self._step(8, term_identity is not None, "Авторизация не удалась"):
            return await self._fail()

        validation = self.auth_validator.validate_term_identity(...)
        if not await self._step(9, validation.passed, "Авторизационные параметры не совпадают"):
            return await self._fail()

        # Шаг 10: RESULT_CODE
        await self._send_result_code(0 if self.auth_response else 151)

        # Шаг 12: Service Info
        if not await self._handle_service_info():
            return await self._fail()

        # Шаг 14: Команда EGTS_TRACK_DATA через SMS
        cmd_ok = await self._send_track_data_command()
        if not await self._step(14, cmd_ok, "Не удалось подать команду на передачу данных"):
            return await self._fail()

        # Шаг 15: Приём данных профиля ускорения
        accel_data = await self._wait_for_accel_data(timeout=60.0)
        if not await self._step(15, accel_data is not None, "Данные профиля ускорения не получены"):
            return await self._fail()

        # Валидация: 600 выборок
        total_samples = sum(len(record.points) for record in accel_data.records)
        if not await self._step(15, total_samples >= self.REQUIRED_SAMPLES,
            f"Получено {total_samples} выборок, требуется {self.REQUIRED_SAMPLES}"
        ):
            return await self._fail()

        return await self._succeed()
```

### 5.5. Тест п. 6.9 — Траектория `core/test_suite/trajectory_test.py`

Аналогично 6.8, но:
- `REQUIRED_SAMPLES = 70` (координаты, 1с интервал)
- `MAX_SAMPLES_PER_RECORD = 255` → достаточно 1 записи

### 5.6. Тест п. 7.8 — Загрузка ПО `core/test_suite/firmware_test.py`

```python
class FirmwareTest(BaseTest):
    test_name = "7.8"
    total_steps = 17

    def __init__(self, ..., firmware_path: str, command_code: int):
        super().__init__(...)
        self.firmware_path = firmware_path
        self.command_code = command_code

    async def run(self) -> TestResult:
        ...
        # Шаг 13: Команда на загрузку ПО через SMS (EGTS_RAW_DATA)
        cmd_ok = await self._send_firmware_command(self.command_code)
        if not await self._step(13, cmd_ok, "Не удалось подать команду на загрузку ПО по SMS"):
            return await self._fail()

        # Шаг 14: Передача ПО частями через TCP/IP
        firmware_data = Path(self.firmware_path).read_bytes()
        chunk_size = 1024  # Размер части
        total_parts = (len(firmware_data) + chunk_size - 1) // chunk_size

        for i in range(total_parts):
            chunk = firmware_data[i*chunk_size:(i+1)*chunk_size]
            success = await self._send_firmware_part(i+1, total_parts, chunk)
            if not await self._step(14, success, "Не удалось осуществить загрузку ПО"):
                return await self._fail()
```

### 5.7. Тест п. 9.2.2 — Изменение параметров `core/test_suite/param_change_test.py`

```python
class ParamChangeTest(BaseTest):
    test_name = "9.2.2"
    total_steps = 16

    def __init__(self, ..., mic_level: int = 5, spk_level: int = 5):
        super().__init__(...)
        if not (0 <= mic_level <= 10):
            raise ValueError("mic_level must be 0-10")
        if not (0 <= spk_level <= 10):
            raise ValueError("spk_level must be 0-10")
        self.mic_level = mic_level
        self.spk_level = spk_level

    async def run(self) -> TestResult:
        ...
        # Шаг 13: Отправка команд MIC/SPK level через TCP/IP
        mic_ok = await self._send_param_command(
            EgtsCommandParamType.EGTS_UNIT_MIC_LEVEL, self.mic_level
        )
        spk_ok = await self._send_param_command(
            EgtsCommandParamType.EGTS_UNIT_SPK_LEVEL, self.spk_level
        )
        if not await self._step(13, mic_ok and spk_ok, "Не удалось выполнить установку параметров"):
            return await self._fail()
```

### 5.8. Тесты

**Файлы:**
- `tests/core/test_suite/test_passive_mode.py`
- `tests/core/test_suite/test_accel_profile.py`
- `tests/core/test_suite/test_trajectory.py`
- `tests/core/test_suite/test_firmware.py`
- `tests/core/test_suite/test_param_change.py`

---

## Этап 6 — Отчёты по тестам (ТЗ п. 1.7, 2.2.7)

**Цель:** Создать модуль формирования отчётов с результатами тестов и конфигурационными параметрами.

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
- `tests/core/test_report.py`

---

## Этап 7 — CMW-500: голосовое соединение и МНД

**Цель:** Расширить CMW-500 контроллер функциями голосового соединения и приёма МНД.

### 7.1. Голосовое соединение `core/cmw500.py`

```python
class VisaCmw500Driver:
    def initiate_voice_call(self, phone_number: str) -> None:
        """Начать голосовой вызов."""
        self._drv.utilities.write_str_with_opc(
            f"CALL:GSM:SIGN:CSWitched:ACTion VCALL"
        )

    def accept_voice_call(self) -> None:
        """Принять входящий голосовой вызов."""
        self._drv.utilities.write_str_with_opc(
            "CALL:GSM:SIGN:CSWitched:ACTion ACCept"
        )

    def disconnect_voice_call(self) -> None:
        """Разорвать голосовое соединение."""
        self._drv.utilities.write_str_with_opc(
            "CALL:GSM:SIGN:CSWitched:ACTion DISConnect"
        )

    def get_voice_call_state(self) -> str:
        """Получить статус голосового вызова."""
        return self._drv.utilities.query_str_with_opc(
            "FETCh:GSM:SIGN:CSWitched:STATe?"
        ).strip()
```

### 7.2. Тоновой модем для МНД

**Файл:** `core/cmw500.py` или отдельный `core/msd_decoder.py`

```python
class MsdDecoder:
    """Декодирование МНД (минимальный набор данных) через тоновый модем."""

    # DTMF/тоновые частоты для eCall MSD
    MSD_TONE_FREQUENCIES = {
        '0': (941, 1336),
        '1': (697, 1209),
        ...
    }

    def decode_from_audio(self, audio_data: bytes, sample_rate: int = 8000) -> bytes | None:
        """Декодировать MSD из аудиопотока."""
        # Реализация через Goertzel algorithm или FFT
        # Возвращает сырые байты MSD или None
        ...

    def parse_msd(self, msd_bytes: bytes) -> dict[str, Any]:
        """Распарсить MSD согласно ГОСТ 33469-2015."""
        # VIN, timestamp, coordinates, vehicle type, etc.
        ...
```

### 7.3. Интеграция с `TestSession`

```python
# При активации голосового соединения:
self.session.voice_connected = True

# При разрыве:
self.session.voice_connected = False

# При приёме МНД:
msd = self.msd_decoder.decode_from_audio(audio_data)
if msd:
    await self.bus.emit("mnd.received", {"msd": msd, "connection_id": ...})
```

### 7.4. Тесты

**Файлы:**
- `tests/core/test_cmw500_voice.py`
- `tests/core/test_msd_decoder.py`

---

## Этап 8 — Интеграция и end-to-end тесты

**Цель:** Связать все компоненты и проверить полные сценарии.

### 8.1. Обновить `CoreEngine` — регистрация тестов

```python
@dataclass
class CoreEngine:
    test_suite: dict[str, BaseTest] = field(default_factory=dict)

    def _init_test_suite(self) -> None:
        """Создать все 5 тестов."""
        creds = self.credentials_repo.get_default()
        common = {
            "bus": self.bus,
            "session": self.test_session,
            "config": self.config,
            "credentials": creds,
        }
        self.test_suite["7.3"] = PassiveModeTest(**common, config_type="1")
        self.test_suite["6.8"] = AccelProfileTest(**common)
        self.test_suite["6.9"] = TrajectoryTest(**common)
        self.test_suite["7.8"] = FirmwareTest(**common, firmware_path="", command_code=0)
        self.test_suite["9.2.2"] = ParamChangeTest(**common)

    async def run_test(self, test_name: str, **kwargs) -> TestResult:
        """Запустить конкретный тест."""
        test = self.test_suite.get(test_name)
        if test is None:
            raise ValueError(f"Unknown test: {test_name}")
        return await test.run()
```

### 8.2. End-to-end тесты

**Файлы:**
- `tests/integration/test_full_passive_mode.py`
- `tests/integration/test_full_accel_profile.py`
- `tests/integration/test_full_trajectory.py`
- `tests/integration/test_full_firmware.py`
- `tests/integration/test_full_param_change.py`

**Каждый тест:**
- Использует `Cmw500Emulator`
- Эмулирует УСВ (отправка TERM_IDENTITY, VEHICLE_DATA, TRACK_DATA, ...)
- Запускает тест
- Проверяет результат

### 8.3. Обновить документацию

**Файлы:**
- `docs/ARCHITECTURE.md` — обновить диаграммы, добавить test_suite, test_session, validators
- `docs/CMW500_SPEC.md` — обновить список SCPI-команд
- Добавить `docs/TEST_SUITE.md` — описание 5 тестов, алгоритмы, шаги

---

## Сводный план по этапам

| Этап | Область | Файлы (новые) | Файлы (изменения) | Оценочная сложность |
|------|---------|---------------|-------------------|---------------------|
| **1** | Конфигурация | — | `config.py`, `credentials.py`, `engine.py`, `cmw500.py` | Низкая |
| **2** | EGTS подзаписи | `command_params.py` | `types.py`, `subrecords.py`, `registry.py` | Средняя |
| **3** | Валидация | `validators/auth_validator.py`, `validators/service_info_validator.py` | `session.py`, `event_bus.py` | Средняя |
| **4** | Сеанс | `test_session.py` | `engine.py` | Средняя |
| **5** | 5 тестов | `test_suite/base_test.py`, `passive_mode_test.py`, `accel_profile_test.py`, `trajectory_test.py`, `firmware_test.py`, `param_change_test.py` | — | Высокая |
| **6** | Отчёты | `report.py` | `engine.py` | Низкая |
| **7** | CMW voice/МНД | `msd_decoder.py` | `cmw500.py` | Высокая |
| **8** | Интеграция | — | `engine.py`, `ARCHITECTURE.md` | Средняя |

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
Этап 5 (5 тестов) ← использует Этапы 1, 2, 3, 4
    ↓
Этап 6 (Отчёты) ← использует Этап 4
    ↓
Этап 7 (CMW voice/МНД) — параллельно с Этапами 1-4
    ↓
Этап 8 (Интеграция) ← использует все предыдущие
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
| Обратная совместимость сценариев JSON | Среднее | Не менять формат V1, добавить V2 только для новых тестов |
| Время таймаутов в ТЗ (ГОСТ п. 6.8) | Низкое | Вынести все таймауты в `TimeoutsConfig` |
