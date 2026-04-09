"""
FIRMWARE сервис EGTS (ГОСТ 33465-2015, раздел 6.7.4)

Сервис для передачи на УСВ конфигурации и обновления программного обеспечения:
- Обновление прошивки УСВ и периферийного оборудования
- Передача конфигурационных параметров
- Поддержка передачи по частям (большие объекты)
- Поддержка передачи одним пакетом (малые объекты)

Подзаписи:
- EGTS_SR_RECORD_RESPONSE (0) - Подтверждение записи
- EGTS_SR_SERVICE_PART_DATA (33) - Данные по частям
- EGTS_SR_SERVICE_FULL_DATA (34) - Данные одним пакетом

Пример использования:
    # Обновление прошивки одним пакетом
    from egts_protocol.services.firmware import create_firmware_update

    subrecord_data, metadata = create_firmware_update(
        firmware_binary=firmware_bytes,
        version=(2, 34),
        component_id=1,
        module_type=0x01,  # УСВ
        file_name="main.bin"
    )

    # Разбиение на части для большой прошивки
    from egts_protocol.services.firmware import split_firmware_to_parts

    parts = split_firmware_to_parts(
        firmware_binary=large_firmware,
        version=(1, 0),
        component_id=2,
        module_type=0x00,  # Периферия
        max_part_size=1024
    )
"""

from typing import Any

from ..crc import crc16
from ..types import (
    EGTS_MAX_OBJECT_DATA_SIZE,
    EGTS_MAX_PARTS,
    EGTS_ODH_MAX_SIZE,
    EGTS_ODH_MIN_SIZE,
)

# ============================================
# Константы и типы данных
# ============================================


# Типы объектов (OT - Object Type)
OBJECT_TYPES: dict[int, str] = {
    0: "Прошивка (firmware)",
    1: "Конфигурация (config)",
}

# Типы модулей (MT - Module Type)
MODULE_TYPES: dict[int, str] = {
    0: "Периферийное оборудование",
    1: "УСВ (основной модуль)",
}

# Атрибуты объектов (OA - Object Attribute)
OBJECT_ATTRIBUTES: dict[int, str] = {
    0: "Стандартное обновление",
    1: "Критическое обновление",
    2: "Конфигурация",
}

# Максимальные размеры (импортированы из types.py)
# MAX_OBJECT_DATA_SIZE = 65400  # Максимальный размер данных объекта
# MAX_PARTS = 65535  # Максимальное количество частей


# ============================================
# CRC16-CCITT для WOS (Whole Object Signature)
# ============================================


def calculate_crc16_ccitt(data: bytes) -> int:
    """
    Расчет CRC16-CCITT для сигнатуры объекта (WOS)

    Args:
        data: Данные для расчета контрольной суммы

    Returns:
        CRC16-CCITT (2 байта)

    ГОСТ 33465-2015, таблица 37:
    Используется алгоритм CRC16-CCITT для расчета
    сигнатуры всей передаваемой сущности

    Note:
        Используется функция crc16 из egts_protocol.crc
        (Poly: 0x1021, Init: 0xFFFF, без реверса)
    """
    return crc16(data)


def verify_firmware_signature(data: bytes, expected_crc: int) -> bool:
    """
    Проверка сигнатуры прошивки/конфигурации

    Args:
        data: Данные для проверки
        expected_crc: Ожидаемая CRC16

    Returns:
        True если сигнатура совпадает
    """
    return calculate_crc16_ccitt(data) == expected_crc


# ============================================
# ODH (Object Data Header) - заголовок объекта
# ============================================


def create_odh(
    object_attribute: int = 0x00,
    object_type: int = 0x00,
    module_type: int = 0x01,
    component_id: int = 0,
    version: tuple[int, int] = (0, 0),
    whole_signature: int = 0,
    file_name: str | None = None,
) -> bytes:
    """
    Создание заголовка объекта ODH (ГОСТ 33465-2015, таблица 37)

    Args:
        object_attribute: Атрибут объекта (OA), 1 байт
        object_type: Тип объекта (OT), 2 бита (0x00=прошивка, 0x01=конфигурация)
        module_type: Тип модуля (MT), 6 бит (0x00=периферия, 0x01=УСВ)
        component_id: Идентификатор компонента (CMI), 1 байт
        version: Версия (VER), кортеж (major, minor), 2 байта
        whole_signature: Сигнатура объекта (WOS), CRC16, 2 байта
        file_name: Имя файла (FN), 0-64 байта (опционально)

    Returns:
        Байты заголовка ODH (7-71 байт)

    Raises:
        ValueError: При выходе параметров за допустимые пределы

    Структура ODH:
        ├── OA (1 байт) - атрибут объекта
        ├── OT+MT (1 байт):
        │   ├── Bit 7-6: OT (Object Type)
        │   └── Bit 5-0: MT (Module Type)
        ├── CMI (1 байт) - идентификатор компонента
        ├── VER (2 байта) - версия (major.minor)
        ├── WOS (2 байта) - CRC16 сигнатура
        ├── FN (0-64 байта) - имя файла (опционально)
        └── D (1 байт) - разделитель (0x00)
    """
    # Валидация диапазонов значений
    if not 0 <= object_attribute <= 0xFF:
        raise ValueError(f"object_attribute вне диапазона 0-255: {object_attribute}")
    if not 0 <= object_type <= 0x03:
        raise ValueError(f"object_type вне диапазона 0-3: {object_type}")
    if not 0 <= module_type <= 0x3F:
        raise ValueError(f"module_type вне диапазона 0-63: {module_type}")
    if not 0 <= component_id <= 0xFF:
        raise ValueError(f"component_id вне диапазона 0-255: {component_id}")
    if not 0 <= whole_signature <= 0xFFFF:
        raise ValueError(f"whole_signature вне диапазона 0-65535: {whole_signature}")

    major, minor = version
    if not 0 <= major <= 0xFF:
        raise ValueError(f"version major вне диапазона 0-255: {major}")
    if not 0 <= minor <= 0xFF:
        raise ValueError(f"version minor вне диапазона 0-255: {minor}")

    result = bytearray()

    # OA (1 байт) - атрибут объекта
    result.append(object_attribute)

    # OT+MT (1 байт): Bit 7-6 = OT, Bit 5-0 = MT
    ot_mt = (object_type << 6) | module_type
    result.append(ot_mt)

    # CMI (1 байт) - идентификатор компонента
    result.append(component_id)

    # VER (2 байта) - версия (major << 8 | minor)
    ver = (major << 8) | minor
    result.extend(ver.to_bytes(2, "little"))

    # WOS (2 байта) - сигнатура объекта
    result.extend((whole_signature & 0xFFFF).to_bytes(2, "little"))

    # FN (0-64 байта) - имя файла (опционально)
    # Максимум 63 байта: OA(1)+OT+MT(1)+CMI(1)+VER(2)+WOS(2)=7 + FN(63) + D(1) = 71 = EGTS_ODH_MAX_SIZE
    if file_name:
        fn_bytes = file_name.encode("cp1251")
        if len(fn_bytes) > 63:
            raise ValueError(
                f"Имя файла слишком длинное: {len(fn_bytes)} байт (максимум 63). "
                f"Файл: {file_name!r}"
            )
        result.extend(fn_bytes)

    # D (1 байт) - разделитель (всегда 0x00)
    result.append(0x00)

    return bytes(result)


def parse_odh(data: bytes) -> dict[str, Any]:
    """
    Парсинг заголовка объекта ODH (ГОСТ 33465-2015, таблица 37)

    Args:
        data: Байты заголовка ODH

    Returns:
        Dict с полями: oa, ot, mt, cmi, version, whole_signature, file_name

    Raises:
        ValueError: Если размер ODH меньше 7 байт
    """
    if len(data) < 7:
        raise ValueError(f"Слишком маленький ODH: {len(data)} байт (минимум 7)")

    offset = 0

    # OA (1 байт) - атрибут объекта
    oa = data[offset]
    offset += 1

    # OT+MT (1 байт)
    ot_mt = data[offset]
    ot = (ot_mt >> 6) & 0x03
    mt = ot_mt & 0x3F
    offset += 1

    # CMI (1 байт) - идентификатор компонента
    cmi = data[offset]
    offset += 1

    # VER (2 байта) - версия
    ver = int.from_bytes(data[offset : offset + 2], "little")
    major = (ver >> 8) & 0xFF
    minor = ver & 0xFF
    offset += 2

    # WOS (2 байта) - сигнатура объекта
    wos = int.from_bytes(data[offset : offset + 2], "little")
    offset += 2

    # FN (0-64 байта) - имя файла (до разделителя 0x00)
    file_name = ""
    fn_start = offset
    while offset < len(data) and data[offset] != 0x00:
        offset += 1

    if offset > fn_start:
        try:
            file_name = data[fn_start:offset].decode("cp1251")
        except UnicodeDecodeError:
            file_name = data[fn_start:offset].decode("utf-8", errors="replace")

    return {
        "oa": oa,
        "oa_text": OBJECT_ATTRIBUTES.get(oa, f"Неизвестен ({oa})"),
        "ot": ot,
        "ot_text": OBJECT_TYPES.get(ot, f"Неизвестен ({ot})"),
        "mt": mt,
        "mt_text": MODULE_TYPES.get(mt, f"Неизвестен ({mt})"),
        "cmi": cmi,
        "version": (major, minor),
        "version_str": f"{major}.{minor}",
        "whole_signature": wos,
        "file_name": file_name,
    }


# ============================================
# EGTS_SR_SERVICE_FULL_DATA (таблица 38)
# ============================================


def serialize_service_full_data(odh: bytes, object_data: bytes) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_SERVICE_FULL_DATA
    (ГОСТ 33465-2015, таблица 38)

    Args:
        odh: Заголовок объекта ODH (7-71 байт)
        object_data: Данные объекта (1-65400 байт)

    Returns:
        Байты данных подзаписи (SRD)

    Структура SERVICE_FULL_DATA:
        ├── ODH (7-71 байт) - заголовок (обязательный)
        └── OD (1-65400 байт) - данные объекта
    """
    if len(odh) < EGTS_ODH_MIN_SIZE:
        raise ValueError(f"Слишком маленький ODH: {len(odh)} байт (минимум {EGTS_ODH_MIN_SIZE})")
    if len(odh) > EGTS_ODH_MAX_SIZE:
        raise ValueError(f"Слишком большой ODH: {len(odh)} байт (максимум {EGTS_ODH_MAX_SIZE})")
    if len(object_data) < 1:
        raise ValueError("Пустые данные объекта")
    if len(object_data) > EGTS_MAX_OBJECT_DATA_SIZE:
        raise ValueError(f"Слишком большие данные: {len(object_data)} байт (максимум {EGTS_MAX_OBJECT_DATA_SIZE})")

    return odh + object_data


def parse_service_full_data(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_SERVICE_FULL_DATA
    (ГОСТ 33465-2015, таблица 38)

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: odh, od, odh_parsed

    Raises:
        ValueError: Если размер данных меньше 7 байт
    """
    if len(data) < 8:
        raise ValueError(
            f"Слишком маленькие данные: {len(data)} байт (минимум 8)"
        )

    # Находим разделитель ODH (0x00)
    # ODH структура: OA(1) + OT+MT(1) + CMI(1) + VER(2) + WOS(2) + FN(0-64) + D(1)
    # Минимальный ODH: 8 байт, разделитель на позиции 7
    # С FN: разделитель после FN, но не позже EGTS_ODH_MAX_SIZE
    # Поиск ограничен EGTS_ODH_MAX_SIZE — байт 0x00 из OD не попадёт в диапазон
    delimiter_pos = -1
    odh_search_limit = min(len(data), EGTS_ODH_MAX_SIZE)
    for i in range(7, odh_search_limit):
        if data[i] == 0x00:
            delimiter_pos = i
            break

    if delimiter_pos == -1:
        raise ValueError("Не найден разделитель ODH (0x00)")

    # ODH включает разделитель
    odh_end = delimiter_pos + 1
    odh = data[:odh_end]
    od = data[odh_end:]

    return {
        "odh": odh,
        "od": od,
        "odh_parsed": parse_odh(odh),
    }


def create_firmware_update(
    firmware_binary: bytes,
    version: tuple[int, int],
    component_id: int,
    module_type: int = 0x01,
    object_type: int = 0x00,
    object_attribute: int = 0x00,
    file_name: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """
    Создание обновления прошивки/конфигурации (FULL_DATA)

    Args:
        firmware_binary: Бинарные данные прошивки/конфигурации
        version: Версия (major, minor)
        component_id: Идентификатор компонента (0-255)
        module_type: Тип модуля (0x00=периферия, 0x01=УСВ)
        object_type: Тип объекта (0x00=прошивка, 0x01=конфигурация)
        object_attribute: Атрибут объекта
        file_name: Имя файла (опционально)

    Returns:
        Tuple[bytes, dict]:
            - bytes: Данные подзаписи SERVICE_FULL_DATA
            - dict: Метаданные (version, crc16, file_name, size)

    Пример:
        >>> subrecord_data, metadata = create_firmware_update(
        ...     firmware_binary=b"\\x00\\x01\\x02...",
        ...     version=(2, 34),
        ...     component_id=1,
        ...     module_type=0x01,
        ...     file_name="main.bin"
        ... )
    """
    # Расчет CRC16 для всей прошивки
    crc16 = calculate_crc16_ccitt(firmware_binary)

    # Создание ODH заголовка
    odh = create_odh(
        object_attribute=object_attribute,
        object_type=object_type,
        module_type=module_type,
        component_id=component_id,
        version=version,
        whole_signature=crc16,
        file_name=file_name,
    )

    # Сериализация SERVICE_FULL_DATA
    subrecord_data = serialize_service_full_data(odh, firmware_binary)

    metadata = {
        "version": version,
        "version_str": f"{version[0]}.{version[1]}",
        "crc16": crc16,
        "file_name": file_name,
        "size": len(firmware_binary),
        "module_type": module_type,
        "module_type_text": MODULE_TYPES.get(module_type, f"Неизвестен ({module_type})"),
        "object_type": object_type,
        "object_type_text": OBJECT_TYPES.get(object_type, f"Неизвестен ({object_type})"),
    }

    return subrecord_data, metadata


def create_config_update(
    config_binary: bytes,
    version: tuple[int, int],
    component_id: int,
    module_type: int = 0x01,
    object_attribute: int = 0x02,
    file_name: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """
    Создание обновления конфигурации (FULL_DATA)

    Args:
        config_binary: Бинарные данные конфигурации
        version: Версия (major, minor)
        component_id: Идентификатор компонента
        module_type: Тип модуля (0x00=периферия, 0x01=УСВ)
        object_attribute: Атрибут объекта (по умолчанию 0x02=конфигурация)
        file_name: Имя файла (опционально)

    Returns:
        Tuple[bytes, dict]:
            - bytes: Данные подзаписи SERVICE_FULL_DATA
            - dict: Метаданные

    Пример:
        >>> subrecord_data, metadata = create_config_update(
        ...     config_binary=b'{"apn": "internet"}',
        ...     version=(1, 5),
        ...     component_id=1,
        ...     file_name="config.json"
        ... )
    """
    return create_firmware_update(
        firmware_binary=config_binary,
        version=version,
        component_id=component_id,
        module_type=module_type,
        object_type=0x01,  # Конфигурация
        object_attribute=object_attribute,
        file_name=file_name,
    )


# ============================================
# EGTS_SR_SERVICE_PART_DATA (таблица 36)
# ============================================


def serialize_service_part_data(
    entity_id: int,
    part_number: int,
    total_parts: int,
    object_data: bytes,
    odh: bytes | None = None,
) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_SERVICE_PART_DATA
    (ГОСТ 33465-2015, таблица 36)

    Args:
        entity_id: Уникальный идентификатор сущности (ID)
        part_number: Номер текущей части (PN), 1-based
        total_parts: Ожидаемое количество частей (EPQ)
        object_data: Данные части (OD)
        odh: Заголовок объекта (только для первой части, опционально)

    Returns:
        Байты данных подзаписи (SRD)

    Структура SERVICE_PART_DATA:
        ├── ID (2 байта) - уникальный ID сущности
        ├── PN (2 байта) - номер текущей части
        ├── EPQ (2 байта) - ожидаемое количество частей
        ├── ODH (0-71 байт) - заголовок (только для части 1)
        └── OD (1-65400 байт) - данные части

    Примечание:
        ODH передается только в первой части (part_number=1).
        Для второй и последующих частей ODH не передается.
    """
    if part_number < 1 or part_number > EGTS_MAX_PARTS:
        raise ValueError(f"Неверный номер части: {part_number} (1-{EGTS_MAX_PARTS})")
    if total_parts < 1 or total_parts > EGTS_MAX_PARTS:
        raise ValueError(f"Неверное количество частей: {total_parts} (1-{EGTS_MAX_PARTS})")
    if part_number > total_parts:
        raise ValueError("Номер части не может быть больше общего количества")
    if len(object_data) < 1:
        raise ValueError("Пустые данные части")
    if len(object_data) > EGTS_MAX_OBJECT_DATA_SIZE:
        raise ValueError(f"Слишком большие данные: {len(object_data)} байт")

    result = bytearray()

    # ID (2 байта) - уникальный идентификатор сущности
    result.extend((entity_id & 0xFFFF).to_bytes(2, "little"))

    # PN (2 байта) - номер текущей части
    result.extend((part_number & 0xFFFF).to_bytes(2, "little"))

    # EPQ (2 байта) - ожидаемое количество частей
    result.extend((total_parts & 0xFFFF).to_bytes(2, "little"))

    # ODH (только для первой части)
    if part_number == 1 and odh is not None:
        if len(odh) < EGTS_ODH_MIN_SIZE:
            raise ValueError(f"Слишком маленький ODH: {len(odh)} байт")
        if len(odh) > EGTS_ODH_MAX_SIZE:
            raise ValueError(f"Слишком большой ODH: {len(odh)} байт")
        result.extend(odh)

    # OD - данные части
    result.extend(object_data)

    return bytes(result)


def parse_service_part_data(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_SERVICE_PART_DATA
    (ГОСТ 33465-2015, таблица 36)

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: id, pn, epq, odh, od, odh_parsed, is_first_part

    Raises:
        ValueError: Если размер данных меньше минимального
    """
    if len(data) < 7:  # Минимум: 6 байт заголовка (ID+PN+EPQ) + 1 байт OD
        raise ValueError(
            f"Слишком маленькие данные: {len(data)} байт (минимум 7)"
        )

    offset = 0

    # ID (2 байта)
    entity_id = int.from_bytes(data[offset : offset + 2], "little")
    offset += 2

    # PN (2 байта)
    part_number = int.from_bytes(data[offset : offset + 2], "little")
    offset += 2

    # EPQ (2 байта)
    total_parts = int.from_bytes(data[offset : offset + 2], "little")
    offset += 2

    is_first_part = part_number == 1

    # Проверка pn <= epq по ГОСТ 33465 (таблица 36, примечание)
    if part_number > total_parts:
        raise ValueError(
            f"Номер части ({part_number}) больше общего количества ({total_parts})"
        )

    # Для первой части минимум: 6 + 1 (ODH минимум 7 + разделитель) + 1 (OD) = 8
    # Для остальных частей минимум: 6 + 1 (OD) = 7
    if is_first_part and len(data) < 8:
        raise ValueError(
            f"Слишком маленькие данные для первой части: {len(data)} байт (минимум 8)"
        )

    # ODH (только для первой части)
    odh: bytes | None = None
    odh_parsed: dict[str, Any] | None = None

    if is_first_part:
        # Находим разделитель ODH (0x00) — последний байт ODH
        # ODH структура: OA(1) + OT+MT(1) + CMI(1) + VER(2) + WOS(2) + FN(0-64) + D(1)
        # Поиск ограничен EGTS_ODH_MAX_SIZE — байт 0x00 из OD не попадёт в диапазон
        delimiter_pos = -1
        odh_search_limit = min(len(data), offset + EGTS_ODH_MAX_SIZE)
        for i in range(offset + 7, odh_search_limit):
            if data[i] == 0x00:
                delimiter_pos = i
                break

        if delimiter_pos != -1:
            # ODH включает разделитель
            odh_end = delimiter_pos + 1
            odh = data[offset:odh_end]
            odh_parsed = parse_odh(odh)
            offset = odh_end

    # OD - данные части
    od = data[offset:]

    return {
        "id": entity_id,
        "pn": part_number,
        "epq": total_parts,
        "odh": odh,
        "od": od,
        "odh_parsed": odh_parsed,
        "is_first_part": is_first_part,
    }


def split_firmware_to_parts(
    firmware_binary: bytes,
    version: tuple[int, int],
    component_id: int,
    module_type: int = 0x01,
    object_type: int = 0x00,
    object_attribute: int = 0x00,
    file_name: str | None = None,
    max_part_size: int = 1024,
) -> list[tuple[bytes, dict[str, Any]]]:
    """
    Разбиение прошивки/конфигурации на части для передачи (PART_DATA)

    Args:
        firmware_binary: Бинарные данные прошивки/конфигурации
        version: Версия (major, minor)
        component_id: Идентификатор компонента
        module_type: Тип модуля (0x00=периферия, 0x01=УСВ)
        object_type: Тип объекта (0x00=прошивка, 0x01=конфигурация)
        object_attribute: Атрибут объекта
        file_name: Имя файла (опционально)
        max_part_size: Максимальный размер одной части (по умолчанию 1024)

    Returns:
        List[Tuple[bytes, dict]]: Список кортежей (данные_части, метаданные)
            - bytes: Данные подзаписи SERVICE_PART_DATA
            - dict: Метаданные части (pn, epq, crc16, size)

    Пример:
        >>> parts = split_firmware_to_parts(
        ...     firmware_binary=b"\\xFF" * 10000,
        ...     version=(1, 0),
        ...     component_id=2,
        ...     module_type=0x00,
        ...     max_part_size=1024
        ... )
        >>> print(f"Разбито на {len(parts)} частей")
    """
    if len(firmware_binary) < 1:
        raise ValueError("Пустые данные прошивки")

    # Расчет CRC16 для всей прошивки
    crc16 = calculate_crc16_ccitt(firmware_binary)

    # Создание ODH заголовка (только для первой части)
    odh = create_odh(
        object_attribute=object_attribute,
        object_type=object_type,
        module_type=module_type,
        component_id=component_id,
        version=version,
        whole_signature=crc16,
        file_name=file_name,
    )

    # Уникальный ID сущности (генерируем из CRC16 и component_id)
    entity_id = (crc16 + component_id) & 0xFFFF

    # Разбиение на части
    # Учитываем накладные расходы: ID(2) + PN(2) + EPQ(2) + ODH(до 71)
    overhead_first = 6 + len(odh)  # Первая часть с ODH
    overhead_other = 6  # Остальные части без ODH

    # Доступный размер для данных в части
    data_size_first = max_part_size - overhead_first
    data_size_other = max_part_size - overhead_other

    if data_size_first < 1 or data_size_other < 1:
        raise ValueError(
            f"Слишком маленький max_part_size={max_part_size}: "
            f"первая часть вмещает {data_size_first} байт данных, "
            f"остальные — {data_size_other} байт"
        )

    # Разбиваем данные с учётом разного размера первой и остальных частей
    parts_data: list[bytes] = []
    offset = 0

    # Первая часть (может вместить больше данных из-за ODH)
    if len(firmware_binary) > 0:
        end = min(offset + data_size_first, len(firmware_binary))
        parts_data.append(firmware_binary[offset:end])
        offset = end

    # Остальные части
    while offset < len(firmware_binary):
        end = min(offset + data_size_other, len(firmware_binary))
        parts_data.append(firmware_binary[offset:end])
        offset = end

    total_parts = len(parts_data)

    # Проверка: не больше EGTS_MAX_PARTS (65535)
    if total_parts > EGTS_MAX_PARTS:
        raise ValueError(
            f"Слишком много частей: {total_parts} > {EGTS_MAX_PARTS}. "
            f"Увеличьте max_part_size (текущий: {max_part_size})"
        )

    # Создаем сериализованные подзаписи
    result = []
    for i, part_data in enumerate(parts_data):
        part_number = i + 1
        is_first = part_number == 1

        # ODH только для первой части
        part_odh = odh if is_first else None

        # Сериализация части
        subrecord_data = serialize_service_part_data(
            entity_id=entity_id,
            part_number=part_number,
            total_parts=total_parts,
            object_data=part_data,
            odh=part_odh,
        )

        metadata = {
            "pn": part_number,
            "epq": total_parts,
            "size": len(part_data),
            "is_first": is_first,
            "entity_id": entity_id,
            "crc16": crc16,
            "version": version,
        }

        result.append((subrecord_data, metadata))

    return result


def assemble_parts(
    parts: list[bytes],
    expected_crc: int | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """
    Сборка частей в целую сущность

    Args:
        parts: Список байтов частей (данные OD из SERVICE_PART_DATA)
        expected_crc: Ожидаемая CRC16 сигнатура (опционально, для проверки)

    Returns:
        Tuple[bytes, dict]:
            - bytes: Собранная сущность
            - dict: Метаданные (size, crc_valid если указана expected_crc)

    Raises:
        ValueError: Если части некорректны или CRC не совпадает
    """
    if not parts:
        raise ValueError("Пустой список частей")

    # Конкатенируем данные
    assembled = b"".join(parts)

    metadata: dict[str, Any] = {
        "size": len(assembled),
    }

    # Проверка CRC16 сигнатуры (если указана expected_crc)
    if expected_crc is not None:
        calculated_crc = calculate_crc16_ccitt(assembled)
        metadata["crc_valid"] = calculated_crc == expected_crc
        metadata["calculated_crc"] = calculated_crc
        if not metadata["crc_valid"]:
            raise ValueError(
                f"CRC16 не совпадает: ожидается {expected_crc:#06x}, "
                f"получен {calculated_crc:#06x}"
            )

    return assembled, metadata


# ============================================
# Вспомогательные функции
# ============================================


def validate_firmware_data(data: bytes) -> bool:
    """
    Базовая валидация данных прошивки/конфигурации

    Args:
        data: Данные для валидации

    Returns:
        True если данные валильны
    """
    if len(data) < 1:
        return False
    if len(data) > EGTS_MAX_OBJECT_DATA_SIZE:
        return False
    return True


def get_firmware_info(subrecord_data: bytes) -> dict[str, Any]:
    """
    Получение информации о прошивке/конфигурации из подзаписи

    Args:
        subrecord_data: Данные подзаписи (FULL_DATA или PART_DATA)

    Returns:
        Dict с информацией о прошивке

    Raises:
        ValueError: Если не удалось определить тип подзаписи
    """
    # Пытаемся определить тип подзаписи по структуре
    # Для FULL_DATA: сразу начинается с ODH
    # Для PART_DATA: первые 6 байт = ID+PN+EPQ

    # Проверяем как PART_DATA (сначала, т.к. у него явные маркеры)
    # PART_DATA имеет ID, PN, EPQ в начале
    if len(subrecord_data) >= 7:  # Минимум: ID(2)+PN(2)+EPQ(2)+OD(1)
        pn = int.from_bytes(subrecord_data[2:4], "little")
        epq = int.from_bytes(subrecord_data[4:6], "little")
        # Если PN и EPQ в разумных пределах и PN <= EPQ, это может быть PART_DATA
        if 1 <= pn <= epq <= EGTS_MAX_PARTS:
            try:
                parsed = parse_service_part_data(subrecord_data)
                # Дополнительная проверка: для первой части должен быть ODH
                if parsed["is_first_part"] and parsed["odh_parsed"] is None:
                    pass  # Это не PART_DATA, пробуем FULL_DATA
                else:
                    return {
                        "type": "PART_DATA",
                        "entity_id": parsed["id"],
                        "part_number": parsed["pn"],
                        "total_parts": parsed["epq"],
                        "is_first_part": parsed["is_first_part"],
                        "odh": parsed["odh_parsed"],
                        "data_size": len(parsed["od"]),
                    }
            except ValueError:
                pass

    # Проверяем как FULL_DATA
    try:
        parsed = parse_service_full_data(subrecord_data)
        return {
            "type": "FULL_DATA",
            "odh": parsed["odh_parsed"],
            "data_size": len(parsed["od"]),
        }
    except ValueError:
        pass

    raise ValueError("Не удалось определить тип подзаписи")
