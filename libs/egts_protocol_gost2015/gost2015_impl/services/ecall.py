"""
ECALL сервис EGTS (ГОСТ 33465-2015, раздел 7)

Сервис экстренного реагирования при аварии.
Обеспечивает передачу минимального набора данных (МНД).

Подзаписи:
- EGTS_SR_RECORD_RESPONSE (0) - Подтверждение записи
- EGTS_SR_ACCEL_DATA (20) - Данные акселерометра
- EGTS_SR_RAW_MSD_DATA (62) - Минимальный набор данных (бинарные)
- EGTS_SR_TRACK_DATA (63) - Данные траектории
"""

import os
from typing import Any

try:
    import asn1tools
except ImportError:
    asn1tools = None

from ..types import (
    EGTS_ACCEL_ATM_SIZE,
    # ACCEL_DATA размеры
    EGTS_ACCEL_DATA_MIN_SIZE,
    EGTS_ACCEL_MEASUREMENT_SIZE,
    EGTS_ACCEL_RTM_SIZE,
    EGTS_ACCEL_SA_SIZE,
    EGTS_ACCEL_XAAV_SIZE,
    EGTS_ACCEL_YAAV_SIZE,
    EGTS_ACCEL_ZAAV_SIZE,
    EGTS_TRACK_ATM_SIZE,
    # TRACK_DATA размеры
    EGTS_TRACK_DATA_MIN_SIZE,
    EGTS_TRACK_DIRH_SPDH_SIZE,
    EGTS_TRACK_LAT_MAX,
    # TRACK_DATA диапазоны
    EGTS_TRACK_LAT_MIN,
    EGTS_TRACK_LAT_SIZE,
    EGTS_TRACK_LON_MAX,
    EGTS_TRACK_LON_MIN,
    EGTS_TRACK_LON_SIZE,
    EGTS_TRACK_SA_SIZE,
    EGTS_TRACK_SPD_SIZE,
    EGTS_TRACK_TDS_SIZE,
)

# Путь к ASN.1 спецификации
_ASN1_SPEC_PATH = os.path.join(os.path.dirname(__file__), "msd.asn")

# Компиляция ASN.1 спецификации с codec='per' (unaligned PER)
if asn1tools is not None:
    try:
        _MSD_CODEC = asn1tools.compile_files(_ASN1_SPEC_PATH, codec="per")
    except Exception:
        _MSD_CODEC = None
else:
    _MSD_CODEC = None

# Форматы MSD
MSD_FORMATS = {
    0: "Неизвестен",
    1: "ГОСТ 33464 (ASN.1 PER)",
}

# Типы транспортных средств
VEHICLE_TYPES = {
    1: "Пассажирский M1",
    2: "Автобус M2",
    3: "Автобус M3",
    4: "Легкий коммерческий N1",
    5: "Тяжелый коммерческий N2",
    6: "Тяжелый коммерческий N3",
    7: "Мотоцикл L1e",
    8: "Мотоцикл L2e",
    9: "Мотоцикл L3e",
    10: "Мотоцикл L4e",
    11: "Мотоцикл L5e",
    12: "Мотоцикл L6e",
    13: "Мотоцикл L7e",
}

# Типы топлива/двигателя
PROPULSION_TYPES = {
    0b000001: "Бензин",
    0b000010: "Дизель",
    0b000100: "Газ (CNG)",
    0b001000: "Газ (LPG)",
    0b010000: "Электрический",
    0b100000: "Водород",
}


# ============================================
# EGTS_SR_ACCEL_DATA (таблица 41, 42)
# ============================================


def parse_accel_data(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_ACCEL_DATA

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: sa, atm, measurements
    """
    if len(data) < EGTS_ACCEL_DATA_MIN_SIZE:
        raise ValueError(
            f"Слишком маленькие данные ACCEL_DATA: {len(data)} байт"
        )

    offset = 0

    # SA (1 байт) - количество структур
    sa = data[offset]
    offset += EGTS_ACCEL_SA_SIZE

    # ATM (4 байта) - абсолютное время
    atm = int.from_bytes(
        data[offset : offset + EGTS_ACCEL_ATM_SIZE], "little"
    )
    offset += EGTS_ACCEL_ATM_SIZE

    # ADS структуры (по 8 байт каждая)
    measurements = []
    for _ in range(sa):
        if offset + EGTS_ACCEL_MEASUREMENT_SIZE > len(data):
            break

        # RTM (2 байта)
        rtm = int.from_bytes(
            data[offset : offset + EGTS_ACCEL_RTM_SIZE], "little"
        )
        offset += EGTS_ACCEL_RTM_SIZE

        # XAAV (2 байта) - ускорение по оси X (0.1 м/с²)
        xaav = int.from_bytes(
            data[offset : offset + EGTS_ACCEL_XAAV_SIZE], "little", signed=True
        )
        offset += EGTS_ACCEL_XAAV_SIZE

        # YAAV (2 байта) - ускорение по оси Y
        yaav = int.from_bytes(
            data[offset : offset + EGTS_ACCEL_YAAV_SIZE], "little", signed=True
        )
        offset += EGTS_ACCEL_YAAV_SIZE

        # ZAAV (2 байта) - ускорение по оси Z
        zaav = int.from_bytes(
            data[offset : offset + EGTS_ACCEL_ZAAV_SIZE], "little", signed=True
        )
        offset += EGTS_ACCEL_ZAAV_SIZE

        measurements.append(
            {
                "rtm": rtm,  # мс
                "xaav": xaav * 0.1,  # м/с²
                "yaav": yaav * 0.1,  # м/с²
                "zaav": zaav * 0.1,  # м/с²
            }
        )

    return {
        "sa": sa,
        "atm": atm,
        "measurements": measurements,
    }


def serialize_accel_data(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_ACCEL_DATA

    Args:
        data: Dict с полями: sa, atm, measurements

    Returns:
        Байты данных подзаписи (SRD)
    """
    measurements = data.get("measurements", [])
    sa = len(measurements)

    result = bytearray()

    # SA (1 байт)
    result.append(sa)

    # ATM (4 байта)
    atm = data.get("atm", 0)
    result.extend(atm.to_bytes(EGTS_ACCEL_ATM_SIZE, "little"))

    # ADS структуры
    for m in measurements:
        # RTM (2 байта)
        rtm = int(m.get("rtm", 0))
        result.extend(rtm.to_bytes(EGTS_ACCEL_RTM_SIZE, "little"))

        # XAAV (2 байта) - конвертируем из м/с² в 0.1 м/с²
        xaav = round(m.get("xaav", 0) / 0.1)
        result.extend(xaav.to_bytes(EGTS_ACCEL_XAAV_SIZE, "little", signed=True))

        # YAAV (2 байта)
        yaav = round(m.get("yaav", 0) / 0.1)
        result.extend(yaav.to_bytes(EGTS_ACCEL_YAAV_SIZE, "little", signed=True))

        # ZAAV (2 байта)
        zaav = round(m.get("zaav", 0) / 0.1)
        result.extend(zaav.to_bytes(EGTS_ACCEL_ZAAV_SIZE, "little", signed=True))

    return bytes(result)


# ============================================
# EGTS_SR_RAW_MSD_DATA (таблица 43)
# ============================================


def parse_raw_msd_data(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_RAW_MSD_DATA

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: fm, msd, msd_text, decoded_msd
    """
    if len(data) < 1:
        raise ValueError(
            f"Слишком маленькие данные RAW_MSD_DATA: {len(data)} байт"
        )

    offset = 0

    # FM (1 байт) - формат
    fm = data[offset]
    offset += 1

    # MSD (оставшиеся байты)
    msd = data[offset:]

    # Попытка декодирования ASN.1 PER для FM=1
    decoded_msd = None
    if fm == 1 and _MSD_CODEC is not None:
        try:
            decoded_msd = _MSD_CODEC.decode("MSDMessage", msd)
        except Exception:
            # Если декодирование не удалось, оставляем None
            pass

    return {
        "fm": fm,
        "fm_text": MSD_FORMATS.get(fm, f"Неизвестен ({fm})"),
        "msd": msd,
        "msd_len": len(msd),
        "decoded_msd": decoded_msd,
    }


def serialize_raw_msd_data(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_RAW_MSD_DATA

    Args:
        data: Dict с полями: fm, msd

    Returns:
        Байты данных подзаписи (SRD)
    """
    result = bytearray()

    # FM (1 байт)
    fm = data.get("fm", 1)  # По умолчанию ГОСТ 33464
    result.append(fm)

    # MSD (бинарные данные)
    msd = data.get("msd", b"")
    result.extend(msd)

    return bytes(result)


def create_msd_data(
    vin: str = "",
    latitude: float = 0.0,
    longitude: float = 0.0,
    direction: int = 0,
    timestamp: int | None = None,
    vehicle_type: int = 1,
    propulsion_type: int = 1,
    crash_severity: int = 0,
    num_occupants: int = 0,
    automatic_activation: bool = True,
    test_call: bool = False,
    position_can_be_trusted: bool = True,
) -> bytes:
    """
    Создание минимального набора данных (МСД) по ГОСТ 33464-2015

    Используется ASN.1 PER кодирование согласно спецификации MSDASN1Module.

    Структура MSD:
    - Message Identifier (0-255)
    - Control Type (automaticActivation, testCall, positionCanBeTrusted, vehicleType)
    - VIN (17 символов: WMI+VDS+VIS)
    - Vehicle Propulsion Storage Type (флаги типов топлива)
    - Timestamp (секунды с 1970-01-01 UTC)
    - Vehicle Location (широта и долгота в микросекундах дуги)
    - Vehicle Direction (0-255, 1 = 2 градуса)
    - Number Of Passengers (опционально)

    Args:
        vin: VIN код (17 символов, формат ISO 3779)
        latitude: Широта (градусы, WGS-84, диапазон: ±90°)
        longitude: Долгота (градусы, WGS-84, диапазон: ±180°)
        direction: Направление движения (0-255, 1 = 2 градуса, 0xFF = неизвестно)
        timestamp: Временная метка (секунды с 1970-01-01 UTC). Если None, используется текущее время
        vehicle_type: Тип ТС (1-13, см. VEHICLE_TYPES)
        propulsion_type: Тип двигателя (битовая маска):
            бит 0: бензин
            бит 1: дизель
            бит 2: газ (CNG)
            бит 3: газ (LPG)
            бит 4: электрический
            бит 5: водород
        crash_severity: Тяжесть ДТП (0-2047, индекс AS/15 * 100). 0 = низкая, 2047 = высокая
        num_occupants: Количество пассажиров (0-255)
        automatic_activation: Автоматическая активация (True = ДТП, False = ручной вызов)
        test_call: Тестовый вызов
        position_can_be_trusted: Позиция достоверна

    Returns:
        Байты MSD (ASN.1 PER кодирование)

    Raises:
        RuntimeError: Если ASN.1 кодек не инициализирован
        ValueError: При некорректных входных параметрах
    """
    import time

    if _MSD_CODEC is None:
        raise RuntimeError("ASN.1 кодек не инициализирован")

    # Валидация параметров
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(f"Широта вне диапазона: {latitude} (должно быть от -90.0 до 90.0)")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(f"Долгота вне диапазона: {longitude} (должно быть от -180.0 до 180.0)")
    if not (0 <= direction <= 255):
        raise ValueError(f"Направление вне диапазона: {direction} (должно быть от 0 до 255)")
    if not (1 <= vehicle_type <= 13):
        raise ValueError(f"Тип ТС вне диапазона: {vehicle_type} (должно быть от 1 до 13)")
    if not (0 <= crash_severity <= 2047):
        raise ValueError(f"Тяжесть ДТП вне диапазона: {crash_severity} (должно быть от 0 до 2047)")
    if not (0 <= num_occupants <= 255):
        raise ValueError(f"Количество пассажиров вне диапазона: {num_occupants} (должно быть от 0 до 255)")

    # Парсинг VIN согласно ISO 3779
    # WMI (3) + VDS (6) + VIS (8) = 17 символов
    vin_clean = vin.upper().replace(" ", "").replace("-", "")
    if len(vin_clean) < 17:
        vin_clean = vin_clean.ljust(17, "0")
    elif len(vin_clean) > 17:
        vin_clean = vin_clean[:17]

    wmi = vin_clean[0:3]
    vds = vin_clean[3:9]
    vis_model_year = vin_clean[9:10]
    vis_seq_plant = vin_clean[10:17]

    # Конвертация координат в микросекунды дуги
    lat_micro = int(latitude * 3600000)
    lon_micro = int(longitude * 3600000)

    # Timestamp
    if timestamp is None:
        timestamp = int(time.time())

    # Конвертация типа топлива в булевы флаги
    propulsion_flags = {
        "gasolineTankPresent": bool(propulsion_type & 0b000001),
        "dieselTankPresent": bool(propulsion_type & 0b000010),
        "compressedNaturalGas": bool(propulsion_type & 0b000100),
        "liquidPropaneGas": bool(propulsion_type & 0b001000),
        "electricEnergyStorage": bool(propulsion_type & 0b010000),
        "hydrogenStorage": bool(propulsion_type & 0b100000),
    }

    # Структура MSD для кодирования
    msd_structure = {
        "messageIdentifier": 1,  # Будет увеличиваться для каждого вызова
        "control": {
            "automaticActivation": automatic_activation,
            "testCall": test_call,
            "positionCanBeTrusted": position_can_be_trusted,
            "vehicleType": vehicle_type,
        },
        "vehicleIdentificationNumber": {
            "isowmi": wmi,
            "isovds": vds,
            "isovisModelyear": vis_model_year,
            "isovisSeqPlant": vis_seq_plant,
        },
        "vehiclePropulsionStorageType": propulsion_flags,
        "timestamp": timestamp,
        "vehicleLocation": {
            "positionLatitude": lat_micro,
            "positionLongitude": lon_micro,
        },
        "vehicleDirection": direction & 0xFF,
    }

    # Добавляем опциональные поля если они заданы
    if num_occupants > 0:
        msd_structure["numberOfPassengers"] = num_occupants

    # Полное сообщение MSD
    msd_message = {
        "msdStructure": msd_structure,
    }

    # Добавляем дополнительные данные если есть
    if crash_severity > 0:
        # ERA Additional Data с оценкой тяжести ДТП
        msd_message["optionalAdditionalData"] = {
            "oid": [1, 4, 1],  # ERA OIDs
            "data": _encode_era_additional_data(crash_severity),
        }

    # Кодирование ASN.1 PER
    encoded = _MSD_CODEC.encode("MSDMessage", msd_message)

    return bytes(encoded)


def _encode_era_additional_data(crash_severity: int) -> bytes:
    """
    Кодирование дополнительных данных ЭРА-ГЛОНАСС

    Args:
        crash_severity: Оценка тяжести ДТП (0-2047)

    Returns:
        Байты дополнительных данных
    """
    # Простая реализация: кодируем crash_severity как 2 байта (big-endian)
    # В полной реализации нужно использовать ASN.1 для ERAAdditionalData
    return crash_severity.to_bytes(2, "big")


def decode_msd_data(msd_bytes: bytes) -> dict[str, Any]:
    """
    Декодирование MSD данных из ASN.1 PER

    Args:
        msd_bytes: Байты MSD

    Returns:
        Dict с декодированными данными MSD
    """
    if _MSD_CODEC is None:
        raise RuntimeError("ASN.1 кодек не инициализирован")

    decoded = _MSD_CODEC.decode("MSDMessage", msd_bytes)

    # Конвертация в удобный формат
    msd_struct = decoded["msdStructure"]

    result = {
        "message_id": msd_struct["messageIdentifier"],
        "automatic_activation": msd_struct["control"]["automaticActivation"],
        "test_call": msd_struct["control"]["testCall"],
        "position_can_be_trusted": msd_struct["control"]["positionCanBeTrusted"],
        "vehicle_type": msd_struct["control"]["vehicleType"],
        "vehicle_type_text": VEHICLE_TYPES.get(
            msd_struct["control"]["vehicleType"], "Неизвестен"
        ),
        "vin": (
            msd_struct["vehicleIdentificationNumber"]["isowmi"]
            + msd_struct["vehicleIdentificationNumber"]["isovds"]
            + msd_struct["vehicleIdentificationNumber"]["isovisModelyear"]
            + msd_struct["vehicleIdentificationNumber"]["isovisSeqPlant"]
        ),
        "propulsion": _decode_propulsion(msd_struct["vehiclePropulsionStorageType"]),
        "timestamp": msd_struct["timestamp"],
        "latitude": msd_struct["vehicleLocation"]["positionLatitude"] / 3600000.0,
        "longitude": msd_struct["vehicleLocation"]["positionLongitude"] / 3600000.0,
        "direction": msd_struct["vehicleDirection"] * 2.0,  # 1 единица = 2 градуса
    }

    # Опциональные поля
    if "numberOfPassengers" in msd_struct:
        result["num_occupants"] = msd_struct["numberOfPassengers"]

    # Дополнительные данные
    if "optionalAdditionalData" in decoded:
        add_data = decoded["optionalAdditionalData"]
        result["additional_data_oid"] = add_data["oid"]
        result["additional_data"] = add_data["data"]

        # Парсинг ERA дополнительных данных
        if add_data["oid"] == [1, 4, 1]:
            crash_severity = int.from_bytes(add_data["data"], "big")
            result["crash_severity"] = crash_severity

    return result


def _decode_propulsion(propulsion: dict[str, bool]) -> list[str]:
    """
    Декодирование типа двигателя из булевых флагов

    Args:
        propulsion: Dict с булевыми флагами

    Returns:
        Список названий типов топлива
    """
    result = []
    if propulsion.get("gasolineTankPresent", False):
        result.append("Бензин")
    if propulsion.get("dieselTankPresent", False):
        result.append("Дизель")
    if propulsion.get("compressedNaturalGas", False):
        result.append("Газ (CNG)")
    if propulsion.get("liquidPropaneGas", False):
        result.append("Газ (LPG)")
    if propulsion.get("electricEnergyStorage", False):
        result.append("Электрический")
    if propulsion.get("hydrogenStorage", False):
        result.append("Водород")

    return result if result else ["Неизвестно"]


# ============================================
# EGTS_SR_TRACK_DATA (таблица 44, 45)
# ============================================


def parse_track_data(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_TRACK_DATA (ГОСТ 33465-2015, таблицы 44, 45)

    Формат точки (по ГОСТ 33465 таблица 45):
      - TDS (1 байт): флаги TNDE, LOHS, LAHS, SDFE, SPFE, RTM
      - LAT (4 байта): широта по модулю (UINT32 LE, если TNDE=1)
      - LONG (4 байта): долгота по модулю (UINT32 LE, если TNDE=1)
      - SPDL (2 байта): младшие 14 бит скорости (если SPFE=1)
      - DIRH/SPDH (1 байт): бит 0 = SPDH, бит 1 = DIRH (если SPFE=1)
      - DIR (1 байт): младшие 8 бит направления (если SDFE=1)

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: sa, atm, track_points
    """
    if len(data) < EGTS_TRACK_DATA_MIN_SIZE:
        raise ValueError(
            f"Слишком маленькие данные TRACK_DATA: {len(data)} байт"
        )

    offset = 0

    # SA (1 байт) - количество точек
    sa = data[offset]
    offset += EGTS_TRACK_SA_SIZE

    # ATM (4 байта) - абсолютное время
    atm = int.from_bytes(
        data[offset : offset + EGTS_TRACK_ATM_SIZE], "little"
    )
    offset += EGTS_TRACK_ATM_SIZE

    # TDS структуры (переменная длина)
    track_points = []
    for _ in range(sa):
        if offset >= len(data):
            break

        # Заголовок точки (1 байт)
        header = data[offset]
        offset += EGTS_TRACK_TDS_SIZE

        tnde = bool((header >> 7) & 0x01)  # Type of Number Direction
        lohs = bool((header >> 6) & 0x01)  # Longitude Half Sign (знак долготы)
        lahs = bool((header >> 5) & 0x01)  # Latitude Half Sign (знак широты)
        sdfe = bool((header >> 4) & 0x01)  # Speed Direction Field Exists
        spfe = bool((header >> 3) & 0x01)  # Speed Field Exists
        rtm = header & 0x07  # Relative Time (3 бита)

        point: dict[str, Any] = {
            "tnde": tnde,
            "lohs": lohs,
            "lahs": lahs,
            "sdfe": sdfe,
            "spfe": spfe,
            "rtm": rtm,
        }

        # LAT (4 байта) — широта по модулю (UINT32 LE, знак определяется LAHS)
        # LAHS=0 → северная широта, LAHS=1 → южная широта
        if offset + EGTS_TRACK_LAT_SIZE <= len(data):
            lat_abs = int.from_bytes(
                data[offset : offset + EGTS_TRACK_LAT_SIZE], "little"
            )
            lat_signed = -lat_abs if lahs else lat_abs
            offset += EGTS_TRACK_LAT_SIZE
            point["lat"] = lat_signed

        # LON (4 байта) — долгота по модулю (UINT32 LE, знак определяется LOHS)
        # LOHS=0 → восточная долгота, LOHS=1 → западная долгота
        if offset + EGTS_TRACK_LON_SIZE <= len(data):
            lon_abs = int.from_bytes(
                data[offset : offset + EGTS_TRACK_LON_SIZE], "little"
            )
            lon_signed = -lon_abs if lohs else lon_abs
            offset += EGTS_TRACK_LON_SIZE
            point["lon"] = lon_signed

        # SPDL (2 байта) — младшие биты скорости (USHORT LE, value * 0.01 км/ч)
        # По ГОСТ 33465 таблица 45: скорость = 15 бит (SPDL[13:0] + SPDH)
        if spfe and offset + EGTS_TRACK_SPD_SIZE <= len(data):
            spdl = int.from_bytes(
                data[offset : offset + EGTS_TRACK_SPD_SIZE], "little"
            )
            # DIRH/SPDH байт — содержит SPDH (бит 0) и DIRH (бит 1)
            spdh = 0
            dirh = 0
            if offset + EGTS_TRACK_SPD_SIZE + EGTS_TRACK_DIRH_SPDH_SIZE <= len(data):
                dirh_spdh = data[offset + EGTS_TRACK_SPD_SIZE]
                spdh = dirh_spdh & 0x01       # Бит 0 — старший бит скорости
                dirh = (dirh_spdh >> 1) & 0x01  # Бит 1 — старший бит направления

            # Собираем 15-битную скорость: SPDH (1 бит) + SPDL (14 бит)
            spd_raw = ((spdh << 14) | (spdl & 0x3FFF))
            spd_kmh: float = spd_raw * 0.01  # Конвертация в км/ч
            point["spd"] = spd_kmh
            point["_spdh"] = spdh  # Сохраняем для сериализации
            point["_dirh"] = dirh  # Сохраняем для сериализации
            offset += EGTS_TRACK_SPD_SIZE + EGTS_TRACK_DIRH_SPDH_SIZE

        # DIR (1 байт) — направление (0-255, value * 360/256 градусов)
        # DIRH — старший бит направления (9-й бит), хранится в DIRH/SPDH байте
        # DIR передаётся только если SDFE=1 (по ГОСТ 33465 таблица 45)
        if sdfe and offset < len(data):
            dir_raw = data[offset]
            # Восстанавливаем 9-битное направление: DIRH (старший) + DIR (младшие 8)
            dir_full = (dirh << 8) | dir_raw
            point["sd"] = dir_full  # 0-511 (9 бит)
            offset += 1

        track_points.append(point)

    return {
        "sa": sa,
        "atm": atm,
        "track_points": track_points,
    }


def serialize_track_data(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_TRACK_DATA (ГОСТ 33465-2015, таблицы 44, 45)

    Формат точки (по ГОСТ 33465 таблица 45):
      - TDS (1 байт): флаги TNDE, LOHS, LAHS, SDFE, SPFE, RTM
      - LAT (4 байта): широта по модулю (UINT32 LE, если TNDE=1 и LAHS определяет знак)
      - LONG (4 байта): долгота по модулю (UINT32 LE, если TNDE=1 и LOHS определяет знак)
      - SPDL (2 байта): младшие 14 бит скорости (USHORT LE, value * 0.01 км/ч)
      - DIRH/SPDH (1 байт): бит 0 = SPDH (старший бит скорости), бит 1 = DIRH (старший бит DIR)
      - DIR (1 байт): младшие 8 бит направления (если SDFE=1)

    Args:
        data: Dict с полями: sa, atm, track_points

    Returns:
        Байты данных подзаписи (SRD)
    """
    track_points = data.get("track_points", [])
    sa = len(track_points)

    result = bytearray()

    # SA (1 байт)
    result.append(sa)

    # ATM (4 байта)
    atm = data.get("atm", 0)
    result.extend(atm.to_bytes(EGTS_TRACK_ATM_SIZE, "little"))

    # TDS структуры
    for point in track_points:
        # Заголовок (1 байт)
        tnde = 1 if point.get("tnde", False) else 0
        # LAHS и LOHS могут быть указаны явно, иначе определяются знаком координат
        if "lahs" in point:
            lahs = point["lahs"]
        else:
            lahs = 1 if point.get("lat", 0) < 0 else 0
        if "lohs" in point:
            lohs = point["lohs"]
        else:
            lohs = 1 if point.get("lon", 0) < 0 else 0
        # SDFE = 1 если есть DIR (по ГОСТ 33465 таблица 45)
        sdfe = 1 if "sd" in point else 0
        spfe = 1 if point.get("spd") is not None else 0
        rtm = point.get("rtm", 0) & 0x07

        header = (tnde << 7) | (lohs << 6) | (lahs << 5) | (sdfe << 4) | (spfe << 3) | rtm
        result.append(header)

        # LAT (4 байта) — абсолютное значение (UINT32 LE), знак в LAHS
        if "lat" in point:
            lat = int(point["lat"])
            lat_abs = abs(lat)
            # Валидация диапазона широты (±90 градусов → 0..0xFFFFFFFF)
            if lat_abs > 0xFFFFFFFF:
                raise ValueError(
                    f"Широта вне диапазона: {lat} (абсолютное значение > UINT32)"
                )
            result.extend(lat_abs.to_bytes(EGTS_TRACK_LAT_SIZE, "little"))

        # LON (4 байта) — абсолютное значение (UINT32 LE), знак в LOHS
        if "lon" in point:
            lon = int(point["lon"])
            lon_abs = abs(lon)
            # Валидация диапазона долготы (±180 градусов → 0..0xFFFFFFFF)
            if lon_abs > 0xFFFFFFFF:
                raise ValueError(
                    f"Долгота вне диапазона: {lon} (абсолютное значение > UINT32)"
                )
            result.extend(lon_abs.to_bytes(EGTS_TRACK_LON_SIZE, "little"))

        # SPDL (2 байта) + DIRH/SPDH (1 байт) — скорость 15 бит
        if "spd" in point:
            spd_raw = round(point["spd"] / 0.01)  # Конвертация км/ч в raw value
            spd_raw = max(0, min(32767, spd_raw))  # Ограничение 15 бит (макс 327.67 км/ч)
            spdh = (spd_raw >> 14) & 0x01  # Старший бит скорости
            spdl = spd_raw & 0x3FFF  # Младшие 14 бит
            result.extend(spdl.to_bytes(EGTS_TRACK_SPD_SIZE, "little"))

            # DIRH/SPDH байт: бит 0 = SPDH, бит 1 = DIRH
            dirh = point.get("_dirh", 0)
            dirh_spdh = (dirh << 1) | spdh
            result.append(dirh_spdh)

        # DIR (1 байт) — направление (9 бит: DIRH + DIR младшие 8)
        # DIR передаётся только если SDFE=1 (по ГОСТ 33465 таблица 45)
        if "sd" in point:
            dir_full = int(point["sd"]) & 0x1FF  # 9 бит (0-511)
            dirh = (dir_full >> 8) & 0x01  # Старший бит
            dir_low = dir_full & 0xFF  # Младшие 8 бит

            if "spd" in point:
                # DIRH записывается в байт DIRH/SPDH (бит 1)
                last_byte_idx = len(result) - 1
                prev = result[last_byte_idx]
                result[last_byte_idx] = prev | (dirh << 1)
            elif dirh:
                # По ГОСТ 33465 табл. 45: DIRH/SPDH байт существует только при SPFE=1.
                # Если скорости нет, направление ограничено 8 битами (0-255).
                raise ValueError(
                    f"Направление {dir_full} требует 9 бит (DIRH=1), но поле SPD отсутствует. "
                    f"Без SPD направление ограничено 0-255."
                )

            result.append(dir_low)

    return bytes(result)


def create_track_point(
    rtm: int,
    latitude: float | None = None,
    longitude: float | None = None,
    direction: float | None = None,
    speed: float | None = None,
    tnde: bool = False,
) -> dict[str, Any]:
    """
    Создание точки траектории (ГОСТ 33465-2015, таблицы 44, 45)

    Args:
        rtm: Относительное время (0-7, шаг 0.1 с)
        latitude: Широта в градусах (None если не передавать)
        longitude: Долгота в градусах (None если не передавать)
        direction: Направление движения в градусах (0-359, север = 0, по часовой стрелке)
        speed: Скорость в км/ч (0-327.67)
        tnde: Флаг наличия данных точки (Type of Number Direction Exists)

    Returns:
        Dict для track_points
    """
    point: dict[str, Any] = {
        "rtm": rtm & 0x07,
        "tnde": tnde,
    }

    if latitude is not None:
        # Конвертируем в UINT32: |lat| / 90 * 0xFFFFFFFF
        lat_val = int(abs(latitude) / 90.0 * 0xFFFFFFFF)
        lat_val = min(lat_val, 0xFFFFFFFF)
        # Сохраняем знак — serialize_track_data определяет LAHS по знаку
        point["lat"] = -lat_val if latitude < 0 else lat_val

    if longitude is not None:
        # Конвертируем в UINT32: |lon| / 180 * 0xFFFFFFFF
        lon_val = int(abs(longitude) / 180.0 * 0xFFFFFFFF)
        lon_val = min(lon_val, 0xFFFFFFFF)
        # Сохраняем знак — serialize_track_data определяет LOHS по знаку
        point["lon"] = -lon_val if longitude < 0 else lon_val

    if direction is not None:
        # Конвертация из градусов в 9-битное значение (0-359 → 0-511)
        dir_raw = int(direction / 360.0 * 512) & 0x1FF
        point["sd"] = dir_raw

    if speed is not None:
        # Конвертация км/ч в 15-битное значение (0.01 км/ч на единицу)
        spd_raw = int(speed / 0.01) & 0x7FFF
        point["spd"] = float(spd_raw * 0.01)

    return point
