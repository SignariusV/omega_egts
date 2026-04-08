"""
AUTH сервис EGTS (ГОСТ 33465-2015, раздел 6.7.2)

Сервис аутентификации УСВ на телематической платформе.
Подзаписи:
- EGTS_SR_TERM_IDENTITY (1) - Идентификация терминала
- EGTS_SR_MODULE_DATA (2) - Данные о модулях
- EGTS_SR_VEHICLE_DATA (3) - Данные о ТС
- EGTS_SR_AUTH_PARAMS (6) - Параметры авторизации
- EGTS_SR_AUTH_INFO (7) - Информация для авторизации
- EGTS_SR_SERVICE_INFO (8) - Информация о сервисах
- EGTS_SR_RESULT_CODE (9) - Результат авторизации
"""

from typing import Any

from .._internal.types import (
    # MODULE_DATA размеры
    EGTS_MODULE_DATA_MIN_SIZE,
    EGTS_MODULE_FWV_SIZE,
    EGTS_MODULE_MD_SIZE,
    EGTS_MODULE_MT_SIZE,
    EGTS_MODULE_ST_SIZE,
    EGTS_MODULE_SWV_SIZE,
    EGTS_MODULE_VID_SIZE,
    EGTS_RECORD_RESPONSE_CRN_SIZE,
    EGTS_RECORD_RESPONSE_SIZE,
    EGTS_TID_BS_SIZE,
    EGTS_TID_BSE_MASK,
    EGTS_TID_FLAGS_SIZE,
    EGTS_TID_HDID_SIZE,
    # TERM_IDENTITY флаги
    EGTS_TID_HDIDE_MASK,
    EGTS_TID_IMEI_SIZE,
    EGTS_TID_IMEIE_MASK,
    EGTS_TID_IMSI_SIZE,
    EGTS_TID_IMSIE_MASK,
    EGTS_TID_LNGC_SIZE,
    EGTS_TID_LNGCE_MASK,
    # TERM_IDENTITY размеры полей
    EGTS_TID_MIN_SIZE,
    EGTS_TID_MNE_MASK,
    EGTS_TID_MSISDN_SIZE,
    EGTS_TID_NID_SIZE,
    EGTS_TID_NIDE_MASK,
    EGTS_TID_SIZE,
    EGTS_TID_SSRA_MASK,
    # VEHICLE_DATA размеры
    EGTS_VEHICLE_DATA_SIZE,
    EGTS_VEHICLE_VHT_SIZE,
    EGTS_VEHICLE_VIN_SIZE,
    EGTS_VEHICLE_VPST_SIZE,
)

# ============================================
# Константы SERVICE_INFO (таблица 25 ГОСТ)
# ============================================

# SRVA (Service Request Attribute) - бит 7
SRVA_SUPPORTED = 0  # Поддерживаемый сервис
SRVA_REQUESTED = 1  # Запрашиваемый сервис

# SRVRP (Service Routing Priority) - биты 1-0
SRVRP_HIGHEST = 0b00  # Наивысший приоритет
SRVRP_HIGH = 0b01     # Высокий приоритет
SRVRP_MEDIUM = 0b10   # Средний приоритет
SRVRP_LOW = 0b11      # Низкий приоритет

# ============================================
# EGTS_SR_TERM_IDENTITY (таблица 19)
# ============================================


def parse_term_identity(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_TERM_IDENTITY

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: tid, flags, hdid, imei, imsi, lngc, ssra, nid, bs, msisdn

    Flags (таблица 19):
        Бит 0: HDIDE (HDID exists)
        Бит 1: IMEIE (IMEI exists)
        Бит 2: IMSIE (IMSI exists)
        Бит 3: LNGCE (Language Code exists)
        Бит 4: SSRA (Simple Service Request Algorithm)
        Бит 5: NIDE (Network ID exists)
        Бит 6: BSE (Buffer Size exists)
        Бит 7: MNE (MSISDN exists)
    """
    if len(data) < EGTS_TID_MIN_SIZE:
        raise ValueError(
            f"Слишком маленькие данные TERM_IDENTITY: {len(data)} байт"
        )

    offset = 0

    # TID (4 байта)
    tid = int.from_bytes(data[offset : offset + EGTS_TID_SIZE], "little")
    offset += EGTS_TID_SIZE

    # Flags (1 байт)
    flags = data[offset]
    offset += EGTS_TID_FLAGS_SIZE

    # Разбираем флаги
    hdide = bool(flags & EGTS_TID_HDIDE_MASK)  # HDID exists (бит 0)
    imeie = bool(flags & EGTS_TID_IMEIE_MASK)  # IMEI exists (бит 1)
    imsie = bool(flags & EGTS_TID_IMSIE_MASK)  # IMSI exists (бит 2)
    lngce = bool(flags & EGTS_TID_LNGCE_MASK)  # LNGC exists (бит 3)
    ssra = bool(flags & EGTS_TID_SSRA_MASK)  # Simple Service Request Algorithm (бит 4)
    nide = bool(flags & EGTS_TID_NIDE_MASK)  # NID exists (бит 5)
    bse = bool(flags & EGTS_TID_BSE_MASK)  # Buffer Size exists (бит 6)
    mne = bool(flags & EGTS_TID_MNE_MASK)  # MSISDN exists (бит 7)

    result: dict[str, Any] = {
        "tid": tid,
        "flags": flags,
        "hdide": hdide,
        "imeie": imeie,
        "imsie": imsie,
        "lngce": lngce,
        "ssra": ssra,
        "nide": nide,
        "bse": bse,
        "mne": mne,
    }

    # HDID (2 байта)
    if hdide:
        if offset + EGTS_TID_HDID_SIZE > len(data):
            raise ValueError("Недостаточно данных для HDID")
        result["hdid"] = int.from_bytes(
            data[offset : offset + EGTS_TID_HDID_SIZE], "little"
        )
        offset += EGTS_TID_HDID_SIZE

    # IMEI (15 байт)
    if imeie:
        if offset + EGTS_TID_IMEI_SIZE > len(data):
            raise ValueError("Недостаточно данных для IMEI")
        result["imei"] = _decode_string(
            data[offset : offset + EGTS_TID_IMEI_SIZE]
        )
        offset += EGTS_TID_IMEI_SIZE

    # IMSI (16 байт)
    if imsie:
        if offset + EGTS_TID_IMSI_SIZE > len(data):
            raise ValueError("Недостаточно данных для IMSI")
        result["imsi"] = _decode_string(
            data[offset : offset + EGTS_TID_IMSI_SIZE]
        )
        offset += EGTS_TID_IMSI_SIZE

    # LNGC (3 байта)
    if lngce:
        if offset + EGTS_TID_LNGC_SIZE > len(data):
            raise ValueError("Недостаточно данных для LNGC")
        result["lngc"] = _decode_string(
            data[offset : offset + EGTS_TID_LNGC_SIZE]
        )
        offset += EGTS_TID_LNGC_SIZE

    # NID (3 байта)
    if nide:
        if offset + EGTS_TID_NID_SIZE > len(data):
            raise ValueError("Недостаточно данных для NID")
        result["nid"] = data[offset : offset + EGTS_TID_NID_SIZE]
        offset += EGTS_TID_NID_SIZE

    # BS (2 байта)
    if bse:
        if offset + EGTS_TID_BS_SIZE > len(data):
            raise ValueError("Недостаточно данных для BS")
        result["bs"] = int.from_bytes(
            data[offset : offset + EGTS_TID_BS_SIZE], "little"
        )
        offset += EGTS_TID_BS_SIZE

    # MSISDN (15 байт)
    if mne:
        if offset + EGTS_TID_MSISDN_SIZE > len(data):
            raise ValueError("Недостаточно данных для MSISDN")
        result["msisdn"] = _decode_string(
            data[offset : offset + EGTS_TID_MSISDN_SIZE]
        )
        offset += EGTS_TID_MSISDN_SIZE

    return result


def serialize_term_identity(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_TERM_IDENTITY

    Args:
        data: Dict с полями: tid, flags, hdid, imei, imsi, lngc, ssra, nid, bs, msisdn

    Returns:
        Байты данных подзаписи (SRD)

    Flags (таблица 19):
        Бит 0: HDIDE (HDID exists)
        Бит 1: IMEIE (IMEI exists)
        Бит 2: IMSIE (IMSI exists)
        Бит 3: LNGCE (Language Code exists)
        Бит 4: SSRA (Simple Service Request Algorithm)
        Бит 5: NIDE (Network ID exists)
        Бит 6: BSE (Buffer Size exists)
        Бит 7: MNE (MSISDN exists)
    """
    result = bytearray()

    # TID (4 байта)
    tid = data.get("tid", 0)
    result.extend(tid.to_bytes(EGTS_TID_SIZE, "little"))

    # Вычисляем флаги из отдельных полей
    flags = 0
    if data.get("hdide", False):
        flags |= EGTS_TID_HDIDE_MASK  # Бит 0 - HDIDE
    if data.get("imeie", False):
        flags |= EGTS_TID_IMEIE_MASK  # Бит 1 - IMEIE
    if data.get("imsie", False):
        flags |= EGTS_TID_IMSIE_MASK  # Бит 2 - IMSIE
    if data.get("lngce", False):
        flags |= EGTS_TID_LNGCE_MASK  # Бит 3 - LNGCE
    if data.get("ssra", False):
        flags |= EGTS_TID_SSRA_MASK  # Бит 4 - SSRA
    if data.get("nide", False):
        flags |= EGTS_TID_NIDE_MASK  # Бит 5 - NIDE
    if data.get("bse", False):
        flags |= EGTS_TID_BSE_MASK  # Бит 6 - BSE
    if data.get("mne", False):
        flags |= EGTS_TID_MNE_MASK  # Бит 7 - MNE

    result.append(flags)

    # HDID (2 байта)
    if data.get("hdide", False):
        hdid = data.get("hdid", 0)
        result.extend(hdid.to_bytes(EGTS_TID_HDID_SIZE, "little"))

    # IMEI (15 байт)
    if data.get("imeie", False):
        imei = data.get("imei", "")
        imei_bytes = _encode_string(imei, EGTS_TID_IMEI_SIZE)
        result.extend(imei_bytes)

    # IMSI (16 байт)
    if data.get("imsie", False):
        imsi = data.get("imsi", "")
        imsi_bytes = _encode_string(imsi, EGTS_TID_IMSI_SIZE)
        result.extend(imsi_bytes)

    # LNGC (3 байта)
    if data.get("lngce", False):
        lngc = data.get("lngc", "rus")
        lngc_bytes = _encode_string(lngc, EGTS_TID_LNGC_SIZE)
        result.extend(lngc_bytes)

    # NID (3 байта)
    if data.get("nide", False):
        nid = data.get("nid", b"\x00\x00\x00")
        if isinstance(nid, str):
            nid = bytes([int(x) for x in nid.split("-")])
        result.extend(nid[: EGTS_TID_NID_SIZE])

    # BS (2 байта)
    if data.get("bse", False):
        bs = data.get("bs", 1024)
        result.extend(bs.to_bytes(EGTS_TID_BS_SIZE, "little"))

    # MSISDN (15 байт)
    if data.get("mne", False):
        msisdn = data.get("msisdn", "")
        msisdn_bytes = _encode_string(msisdn, EGTS_TID_MSISDN_SIZE)
        result.extend(msisdn_bytes)

    return bytes(result)


# ============================================
# EGTS_SR_MODULE_DATA (таблица 21)
# ============================================


def parse_module_data(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_MODULE_DATA (ГОСТ 33465-2015, таблица 21)

    Структура данных:
    - MT (1 байт): тип модуля
    - VID (4 байта): идентификатор производителя
    - FWV (2 байта): версия аппаратного обеспечения
    - SWV (2 байта): версия программного обеспечения
    - MD (1 байт): данные модуля
    - ST (1 байт): тип сервиса
    - SRN (0-32 байта) + D (1 байт, 0x00): серийный номер с разделителем
    - DSCR (0-32 байта) + D (1 байт, 0x00): описание с разделителем

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: mt, vid, fwv, swv, md, st, srn, dscr
    """
    if len(data) < EGTS_MODULE_DATA_MIN_SIZE:
        raise ValueError(
            f"Слишком маленькие данные MODULE_DATA: {len(data)} байт"
        )

    offset = 0

    # MT (1 байт)
    mt = data[offset]
    offset += EGTS_MODULE_MT_SIZE

    # VID (4 байта)
    vid = int.from_bytes(
        data[offset : offset + EGTS_MODULE_VID_SIZE], "little"
    )
    offset += EGTS_MODULE_VID_SIZE

    # FWV (2 байта)
    fwv = int.from_bytes(
        data[offset : offset + EGTS_MODULE_FWV_SIZE], "little"
    )
    offset += EGTS_MODULE_FWV_SIZE

    # SWV (2 байта)
    swv = int.from_bytes(
        data[offset : offset + EGTS_MODULE_SWV_SIZE], "little"
    )
    offset += EGTS_MODULE_SWV_SIZE

    # MD (1 байт)
    md = data[offset]
    offset += EGTS_MODULE_MD_SIZE

    # ST (1 байт)
    st = data[offset]
    offset += EGTS_MODULE_ST_SIZE

    result: dict[str, Any] = {
        "mt": mt,
        "vid": vid,
        "fwv": fwv,
        "swv": swv,
        "md": md,
        "st": st,
    }

    # SRN (строка до 32 байт + разделитель D 0x00)
    srn = _decode_string_until_null(data[offset:])
    offset += len(srn) + 1  # +1 для разделителя D (0x00)
    result["srn"] = srn

    # DSCR (строка до 32 байт + разделитель D 0x00)
    dscr = _decode_string_until_null(data[offset:])
    offset += len(dscr) + 1  # +1 для разделителя D (0x00)
    result["dscr"] = dscr

    return result


def serialize_module_data(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_MODULE_DATA (ГОСТ 33465-2015, таблица 21)

    Структура данных:
    - MT (1 байт): тип модуля
    - VID (4 байта): идентификатор производителя
    - FWV (2 байта): версия аппаратного обеспечения
    - SWV (2 байта): версия программного обеспечения
    - MD (1 байт): данные модуля
    - ST (1 байт): тип сервиса
    - SRN (0-32 байта) + D (1 байт, 0x00): серийный номер с разделителем
    - DSCR (0-32 байта) + D (1 байт, 0x00): описание с разделителем

    Args:
        data: Dict с полями: mt, vid, fwv, swv, md, st, srn, dscr

    Returns:
        Байты данных подзаписи (SRD)
    """
    result = bytearray()

    # MT (1 байт)
    result.append(data.get("mt", 1))

    # VID (4 байта)
    vid = data.get("vid", 0)
    result.extend(vid.to_bytes(EGTS_MODULE_VID_SIZE, "little"))

    # FWV (2 байта)
    fwv = data.get("fwv", 0)
    result.extend(fwv.to_bytes(EGTS_MODULE_FWV_SIZE, "little"))

    # SWV (2 байта)
    swv = data.get("swv", 0)
    result.extend(swv.to_bytes(EGTS_MODULE_SWV_SIZE, "little"))

    # MD (1 байт)
    result.append(data.get("md", 0))

    # ST (1 байт)
    result.append(data.get("st", 1))

    # SRN (строка + разделитель D 0x00)
    srn = data.get("srn", "")
    result.extend(srn.encode("cp1251") if isinstance(srn, str) else srn)
    result.append(0x00)  # Разделитель D

    # DSCR (строка + разделитель D 0x00)
    dscr = data.get("dscr", "")
    result.extend(dscr.encode("cp1251") if isinstance(dscr, str) else dscr)
    result.append(0x00)  # Разделитель D

    return bytes(result)


# ============================================
# Вспомогательные функции
# ============================================


class StringEncoder:
    """
    Утилиты для кодирования/декодирования строк согласно ГОСТ 33465-2015

    Согласно ГОСТ, строки кодируются в CP-1251 (Windows-1251) для кириллицы
    или ASCII для латиницы. Строки дополняются нулевыми байтами до фиксированной длины.
    """

    @staticmethod
    def decode(data: bytes, encoding: str = "cp1251") -> str:
        """
        Декодирование строки с удалением нулевых байтов

        Args:
            data: Байты для декодирования
            encoding: Кодировка (по умолчанию cp1251)

        Returns:
            str: Декодированная строка
        """
        try:
            return data.rstrip(b"\x00").decode(encoding)
        except UnicodeDecodeError:
            # Если не получилось, пробуем ASCII с заменой
            return data.rstrip(b"\x00").decode("ascii", errors="replace")

    @staticmethod
    def encode(s: str, length: int, encoding: str = "cp1251") -> bytes:
        """
        Кодирование строки с дополнением нулями до нужной длины

        Args:
            s: Строка для кодирования
            length: Желаемая длина в байтах
            encoding: Кодировка (по умолчанию cp1251)

        Returns:
            bytes: Закодированная строка нужной длины
        """
        encoded = s.encode(encoding) if isinstance(s, str) else s
        if len(encoded) < length:
            encoded = encoded + b"\x00" * (length - len(encoded))
        return encoded[:length]

    @staticmethod
    def decode_until_null(data: bytes, encoding: str = "cp1251") -> str:
        """
        Декодирование строки до нулевого байта

        Args:
            data: Байты для декодирования
            encoding: Кодировка (по умолчанию cp1251)

        Returns:
            str: Декодированная строка до первого нулевого байта
        """
        if not data:
            return ""

        # Находим первый нулевой байт
        null_pos = data.find(b"\x00")
        if null_pos == -1:
            # Нет нулевого байта, декодируем всё
            return StringEncoder.decode(data, encoding)

        # Декодируем до нулевого байта
        return StringEncoder.decode(data[:null_pos], encoding)


# Сохраняем старые функции для обратной совместимости
def _decode_string(data: bytes) -> str:
    """Декодирование строки с удалением нулевых байтов (устарело, используйте StringEncoder.decode)"""
    return StringEncoder.decode(data)


def _encode_string(s: str, length: int) -> bytes:
    """Кодирование строки с дополнением нулями (устарело, используйте StringEncoder.encode)"""
    return StringEncoder.encode(s, length)


def _decode_string_until_null(data: bytes) -> str:
    """Декодирование строки до нулевого байта (устарело, используйте StringEncoder.decode_until_null)"""
    return StringEncoder.decode_until_null(data)


# ============================================
# EGTS_SR_VEHICLE_DATA (таблица 22)
# ============================================


def parse_vehicle_data(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_VEHICLE_DATA

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: vin, vht, vpst
    """
    if len(data) < EGTS_VEHICLE_DATA_SIZE:
        raise ValueError(
            f"Слишком маленькие данные VEHICLE_DATA: {len(data)} байт (минимум {EGTS_VEHICLE_DATA_SIZE})"
        )

    offset = 0

    # VIN (17 байт)
    vin = (
        data[offset : offset + EGTS_VEHICLE_VIN_SIZE]
        .decode("cp1251")
        .rstrip("\x00")
    )
    offset += EGTS_VEHICLE_VIN_SIZE

    # VHT (4 байта)
    vht = int.from_bytes(
        data[offset : offset + EGTS_VEHICLE_VHT_SIZE], "little"
    )
    offset += EGTS_VEHICLE_VHT_SIZE

    # VPST (4 байта)
    vpst = int.from_bytes(
        data[offset : offset + EGTS_VEHICLE_VPST_SIZE], "little"
    )

    return {
        "vin": vin,
        "vht": vht,
        "vpst": vpst,
    }


def serialize_vehicle_data(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_VEHICLE_DATA

    Args:
        data: Dict с полями: vin, vht, vpst

    Returns:
        Байты данных подзаписи (SRD)
    """
    # VIN (17 байт, дополняем нулями)
    vin = data.get("vin", "")
    vin_bytes = (
        vin.encode("cp1251")[: EGTS_VEHICLE_VIN_SIZE].ljust(
            EGTS_VEHICLE_VIN_SIZE, b"\x00"
        )
    )

    # VHT (4 байта)
    vht = data.get("vht", 0)
    vht_bytes = vht.to_bytes(EGTS_VEHICLE_VHT_SIZE, "little")

    # VPST (4 байта)
    vpst = data.get("vpst", 0)
    vpst_bytes = vpst.to_bytes(EGTS_VEHICLE_VPST_SIZE, "little")

    return vin_bytes + vht_bytes + vpst_bytes  # type: ignore[no-any-return]


# ============================================
# EGTS_SR_RECORD_RESPONSE (таблица 18)
# ============================================


def parse_record_response(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_RECORD_RESPONSE

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: crn, rst
    """
    if len(data) < EGTS_RECORD_RESPONSE_SIZE:
        raise ValueError(
            f"Слишком маленькие данные RECORD_RESPONSE: {len(data)} байт (минимум {EGTS_RECORD_RESPONSE_SIZE})"
        )

    offset = 0

    # CRN (2 байта)
    crn = int.from_bytes(
        data[offset : offset + EGTS_RECORD_RESPONSE_CRN_SIZE], "little"
    )
    offset += EGTS_RECORD_RESPONSE_CRN_SIZE

    # RST (1 байт)
    rst = data[offset]

    return {
        "crn": crn,
        "rst": rst,
    }


def serialize_record_response(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_RECORD_RESPONSE

    Args:
        data: Dict с полями: crn, rst

    Returns:
        Байты данных подзаписи (SRD)

    Raises:
        ValueError: Если CRN или RST вне допустимого диапазона

    Note:
        Согласно Таблице 18 ГОСТ 33465-2015:
        - CRN (Confirm Record Number): 2 байта (0-65535)
        - RST (Record Status): 1 байт (0-255)
    """
    crn = data.get("crn", 0)
    rst = data.get("rst", 0)

    # Валидация диапазонов (Таблица 18 ГОСТ)
    if not (0 <= crn <= 65535):
        raise ValueError(f"CRN вне диапазона: {crn} (0-65535)")
    if not (0 <= rst <= 255):
        raise ValueError(f"RST вне диапазона: {rst} (0-255)")

    return (
        crn.to_bytes(EGTS_RECORD_RESPONSE_CRN_SIZE, "little") + bytes([rst])
    )  # type: ignore[no-any-return]


# ============================================
# EGTS_SR_RESULT_CODE (таблица 27 + Приложение В)
# ============================================

# Коды результатов обработки (Приложение В)
RESULT_CODES = {
    0: "EGTS_PC_OK",  # Успешно
    1: "EGTS_PC_INVALID",  # Неверный пакет
    2: "EGTS_PC_TTLEXPIRED",  # Истек TTL
    3: "EGTS_PC_NOROUTE",  # Нет маршрута
    4: "EGTS_PC_NOSERVICE",  # Сервис не поддерживается
    5: "EGTS_PC_AUTHFAIL",  # Ошибка аутентификации
    6: "EGTS_PC_NOTSUPPORTED",  # Не поддерживается
    7: "EGTS_PC_BUSY",  # Занято
    8: "EGTS_PC_NOTREADY",  # Не готов
    9: "EGTS_PC_ACCESSDENIED",  # Доступ запрещен
    10: "EGTS_PC_TOBIGHSRL",  # Превышен размер подзаписи
    11: "EGTS_PC_TOBIGHSRD",  # Превышен размер данных подзаписи
    12: "EGTS_PC_INVALIDSUBR",  # Неверная подзапись
    13: "EGTS_PC_INVALIDDATA",  # Неверные данные
    14: "EGTS_PC_MODULEFAULT",  # Неисправность модуля (>127)
    15: "EGTS_PC_BADTID",  # Неверный TID
    16: "EGTS_PC_BADVIN",  # Неверный VIN
}


def parse_result_code(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_RESULT_CODE

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: rcd, rcd_text
    """
    if len(data) < 1:
        return {"rcd": 0, "rcd_text": RESULT_CODES.get(0, "Unknown")}

    rcd = data[0]
    return {
        "rcd": rcd,
        "rcd_text": RESULT_CODES.get(rcd, f"Unknown ({rcd})"),
    }


def serialize_result_code(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_RESULT_CODE

    Args:
        data: Dict с полем: rcd

    Returns:
        Байты данных подзаписи (SRD)
    """
    rcd = data.get("rcd", 0)
    return bytes([rcd])


# ============================================
# EGTS_SR_SERVICE_INFO (таблица 26)
# ============================================


def parse_service_info(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_SERVICE_INFO (ГОСТ 33465-2015, таблица 25/26)

    Структура по ГОСТ (таблица 26):
    Каждый сервис занимает 3 байта:
    - ST (1 байт): тип сервиса
    - SST (1 байт): состояние сервиса
    - SRVP (1 байт): параметры сервиса

    Структура SRVP (1 байт):
    - Бит 7: SRVA (Service Request Attribute)
    - Биты 6-2: резерв
    - Биты 1-0: SRVRP (Service Routing Priority)

    Состояния сервиса (SST):
    - 0: EGTS_SST_IN_SERVICE (сервис в рабочем состоянии)
    - 128: EGTS_SST_OUT_OF_SERVICE (сервис выключен)
    - 129: EGTS_SST_DENIED (сервис запрещён)
    - 130: EGTS_SST_NO_CONF (сервис не настроен)
    - 131: EGTS_SST_TEMP_UNAVAIL (сервис временно недоступен)

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями:
        - srvp: общий байт флагов (первый байт)
        - srva: флаг запроса (bool)
        - srvrp: приоритет (int)
        - services: список сервисов, каждый сервис это dict {st, sst, srvp, srva, srvrp}
    """
    if len(data) < 1:
        raise ValueError(f"Слишком маленькие данные SERVICE_INFO: {len(data)} байт")

    offset = 0

    # Первый байт - общий SRVP (для обратной совместимости)
    srvp = data[offset]
    offset += 1

    # Разбираем флаги SRVP по ГОСТ
    # Бит 7: SRVA (Service Request Attribute)
    srva = bool((srvp >> 7) & 0x01)  # 1 = запрашиваемый, 0 = поддерживаемый
    # Биты 1-0: SRVRP (Service Routing Priority)
    srvrp = srvp & 0x03  # 2 бита приоритета

    # Список сервисов (каждый по 3 байта: ST + SST + SRVP)
    # Согласно таблице 26 ГОСТ
    services = []
    while offset + 2 <= len(data):
        st = data[offset]
        offset += 1
        sst = data[offset]
        offset += 1
        srvp_svc = data[offset]
        offset += 1

        # Разбираем SRVP сервиса
        srva_svc = bool((srvp_svc >> 7) & 0x01)
        srvrp_svc = srvp_svc & 0x03

        services.append({
            "st": st,
            "sst": sst,
            "srvp": srvp_svc,
            "srva": srva_svc,
            "srvrp": srvrp_svc,
        })

    return {
        "srvp": srvp,
        "srva": srva,
        "srvrp": srvrp,
        "request": srva,  # Для обратной совместимости
        "services": services,
    }


def serialize_service_info(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_SERVICE_INFO (ГОСТ 33465-2015, таблица 25/26)

    Структура по ГОСТ (таблица 26):
    Каждый сервис занимает 3 байта:
    - ST (1 байт): тип сервиса
    - SST (1 байт): состояние сервиса (0=в рабочем состоянии)
    - SRVP (1 байт): параметры сервиса

    Структура SRVP (1 байт):
    - Бит 7: SRVA (0=поддерживаемый, 1=запрашиваемый)
    - Биты 6-2: зарезервировано (0)
    - Биты 1-0: SRVRP (приоритет маршрутизации)

    Args:
        data: Dict с полями:
        - srvp: общий байт флагов (int, опционально)
        - srva: флаг запроса (bool, опционально)
        - srvrp: приоритет (int, опционально)
        - services: список сервисов (int или dict {st, sst, srvp, srva, srvrp})

    Returns:
        Байты данных подзаписи (SRD)
    """
    # SRVP (1 байт) - общий заголовок
    srvp = data.get("srvp", 0)

    # Устанавливаем бит 7 (SRVA)
    if data.get("srva", False):
        srvp |= 0x80
    else:
        srvp &= ~0x80

    # Устанавливаем биты 1-0 (SRVRP)
    srvrp = data.get("srvrp", 0) & 0x03  # 2 бита
    srvp = (srvp & ~0x03) | srvrp

    result = bytearray([srvp])

    # Список сервисов
    for service in data.get("services", []):
        if isinstance(service, dict):
            # Расширенный формат: {st, sst, srvp, srva, srvrp}
            st = service.get("st", 0)
            sst = service.get("sst", 0)

            # Формируем SRVP сервиса
            srvp_svc = service.get("srvp", 0)
            if service.get("srva", False):
                srvp_svc |= 0x80
            srvrp_svc = service.get("srvrp", 0) & 0x03
            srvp_svc = (srvp_svc & ~0x03) | srvrp_svc

            result.append(st)
            result.append(sst)
            result.append(srvp_svc)
        else:
            # Простой формат: только ST (для обратной совместимости)
            # SST=0 (в рабочем состоянии), SRVP=0 (наивысший приоритет, поддерживаемый)
            result.append(service)
            result.append(0)  # SST=0 (EGTS_SST_IN_SERVICE)
            result.append(0)  # SRVP=0 (SRVA=0, SRVRP=00)

    return bytes(result)


# ============================================
# EGTS_SR_AUTH_PARAMS (таблица 24)
# ============================================


def parse_auth_params(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_AUTH_PARAMS (ГОСТ 33465-2015, таблица 23)

    Структура данных согласно ГОСТ:
    - FLG (1 байт): флаги
    - PKL (2 байта, опц.): длина публичного ключа
    - PBK (0-PKL байт, опц.): публичный ключ
    - ISL (2 байта, опц.): длина идентификатора
    - IS (0-ISL байт, опц.): идентификатор
    - MSZ (2 байта, опц.): длина подписи модуля
    - MS (0-MSZ байт, опц.): подпись модуля
    - SS (0-255 байт, опц.): серверная последовательность
    - D (1 байт, 0x00): разделитель
    - EXP (0-255 байт, опц.): дополнительные данные
    - D (1 байт, 0x00): разделитель

    Флаги FLG:
    - Бит 0: ENA (Encryption Algorithm)
    - Бит 1: PKE (Public Key Exists)
    - Бит 2: ISLE (Identity String Length Exists)
    - Бит 3: MSE (Module Signature Exists)
    - Бит 4: SSE (Server Signature Exists)
    - Бит 5: EXE (Extended Exists)

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями:
        - flg: флаги (int)
        - ena: флаг алгоритма шифрования (bool)
        - pke: флаг существования публичного ключа (bool)
        - isle: флаг существования длины идентификатора (bool)
        - mse: флаг существования подписи модуля (bool)
        - sse: флаг существования серверной подписи (bool)
        - exe: флаг расширенных данных (bool)
        - pkl: длина публичного ключа (int | None)
        - pbk: публичный ключ (bytes | None)
        - isl: длина идентификатора (int | None)
        - is: идентификатор (bytes | None)
        - msz: длина подписи модуля (int | None)
        - ms: подпись модуля (bytes | None)
        - ssl: длина серверной последовательности (int | None)
        - ss: серверная последовательность (bytes | None)
    """
    if len(data) < 1:
        raise ValueError(f"Слишком маленькие данные AUTH_PARAMS: {len(data)} байт")

    offset = 0

    # FLG (1 байт)
    flg = data[offset]
    offset += 1

    # Разбираем флаги
    ena = bool(flg & 0x01)  # Encryption Algorithm
    pke = bool((flg >> 1) & 0x01)  # Public Key Exists
    isle = bool((flg >> 2) & 0x01)  # Identity String Length Exists
    mse = bool((flg >> 3) & 0x01)  # Module Signature Exists
    sse = bool((flg >> 4) & 0x01)  # Server Signature Exists
    exe = bool((flg >> 5) & 0x01)  # Extended Exists

    # PKL (2 байта) - опционально
    pkl = None
    pbk = None
    if pke and offset + 2 <= len(data):
        pkl = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2
        # PBK (pkl байт)
        if offset + pkl <= len(data):
            pbk = data[offset : offset + pkl]
            offset += pkl

    # ISL (2 байта) - опционально
    isl = None
    is_data = None
    if isle and offset + 2 <= len(data):
        isl = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2
        # IS (isl байт)
        if offset + isl <= len(data):
            is_data = data[offset : offset + isl]
            offset += isl

    # MSZ (2 байта) - опционально
    msz = None
    ms = None
    if mse and offset + 2 <= len(data):
        msz = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2
        # MS (msz байт)
        if offset + msz <= len(data):
            ms = data[offset : offset + msz]
            offset += msz

    # SSL (2 байта) + SS - опционально
    ssl = None
    ss = None
    if sse and offset + 2 <= len(data):
        ssl = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2
        # SS (ssl байт)
        if offset + ssl <= len(data):
            ss = data[offset : offset + ssl]
            offset += ssl

    # Разделитель D (1 байт, 0x00) - опционально
    if exe and offset < len(data):
        if data[offset] != 0x00:
            raise ValueError(f"Ожидался разделитель D (0x00) на позиции {offset}, получено {data[offset]:02X}")
        offset += 1

    # EXP (длина до следующего разделителя) - опционально
    exp = None
    if exe and offset < len(data):
        exp_start = offset
        exp_end = data.find(b"\x00", offset)
        if exp_end != -1:
            exp = data[exp_start:exp_end]
            offset = exp_end + 1  # Пропускаем разделитель

    return {
        "flg": flg,
        "ena": ena,
        "pke": pke,
        "isle": isle,
        "mse": mse,
        "sse": sse,
        "exe": exe,
        "pkl": pkl,
        "pbk": pbk,
        "isl": isl,
        "is": is_data,
        "msz": msz,
        "ms": ms,
        "ssl": ssl,
        "ss": ss,
        "exp": exp,
    }


def serialize_auth_params(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_AUTH_PARAMS (ГОСТ 33465-2015, таблица 23)

    Структура данных согласно ГОСТ:
    - FLG (1 байт): флаги
    - PKL (2 байта, опц.): длина публичного ключа
    - PBK (0-PKL байт, опц.): публичный ключ
    - ISL (2 байта, опц.): длина идентификатора
    - IS (0-ISL байт, опц.): идентификатор
    - MSZ (2 байта, опц.): длина подписи модуля
    - MS (0-MSZ байт, опц.): подпись модуля
    - SS (0-255 байт, опц.): серверная последовательность
    - D (1 байт, 0x00): разделитель
    - EXP (0-255 байт, опц.): дополнительные данные
    - D (1 байт, 0x00): разделитель

    Флаги FLG:
    - Бит 0: ENA (Encryption Algorithm)
    - Бит 1: PKE (Public Key Exists)
    - Бит 2: ISLE (Identity String Length Exists)
    - Бит 3: MSE (Module Signature Exists)
    - Бит 4: SSE (Server Signature Exists)
    - Бит 5: EXE (Extended Exists)

    Args:
        data: Dict с полями:
        - flg: флаги (int)
        - ena: флаг алгоритма шифрования (bool)
        - pke: флаг существования публичного ключа (bool)
        - isle: флаг существования длины идентификатора (bool)
        - mse: флаг существования подписи модуля (bool)
        - sse: флаг существования серверной подписи (bool)
        - exe: флаг расширенных данных (bool)
        - pbk: публичный ключ (bytes | None)
        - is: идентификатор (bytes | None)
        - ms: подпись модуля (bytes | None)
        - ss: серверная последовательность (bytes | None)
        - exp: дополнительные данные (bytes | None)

    Returns:
        Байты данных подзаписи (SRD)

    Пример использования:
        data = {
            "pke": True,
            "pbk": b"public_key_data",
            "isle": True,
            "is": b"identity_data",
            "mse": True,
            "ms": b"module_signature",
        }
        bytes = serialize_auth_params(data)
    """
    # Формируем FLG
    flg = data.get("flg", 0)
    if data.get("ena", False):
        flg |= 0x01
    if data.get("pke", False):
        flg |= 0x02
    if data.get("isle", False):
        flg |= 0x04
    if data.get("mse", False):
        flg |= 0x08
    if data.get("sse", False):
        flg |= 0x10
    if data.get("exe", False):
        flg |= 0x20

    result = bytearray()
    result.append(flg)

    # PKL + PBK
    pbk = data.get("pbk")
    if pbk:
        pkl = len(pbk)
        result.extend(pkl.to_bytes(2, "little"))
        result.extend(pbk)

    # ISL + IS
    is_data = data.get("is")
    if is_data:
        isl = len(is_data)
        result.extend(isl.to_bytes(2, "little"))
        result.extend(is_data)

    # MSZ + MS
    ms = data.get("ms")
    if ms:
        msz = len(ms)
        result.extend(msz.to_bytes(2, "little"))
        result.extend(ms)

    # SSL + SS
    ss = data.get("ss")
    if ss:
        ssl = len(ss)
        result.extend(ssl.to_bytes(2, "little"))
        result.extend(ss)

    # Разделитель D + EXP
    exp = data.get("exp")
    if data.get("exe", False) or exp:
        result.append(0x00)  # Разделитель D
        if exp:
            result.extend(exp)
            result.append(0x00)  # Разделитель D после EXP

    return bytes(result)


# ============================================
# EGTS_SR_AUTH_INFO (таблица 24)
# ============================================


def parse_auth_info(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_AUTH_INFO (ГОСТ 33465-2015, таблица 24)

    Структура по ГОСТ:
    - UNM (0-32 байта): имя пользователя + разделитель D (0x00)
    - UPSW (0-32 байта): пароль + разделитель D (0x00)
    - SS (0-255 байт, опц.): серверная последовательность + разделитель D (0x00, опц.)

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями:
        - unm: str (имя пользователя)
        - upsw: str (пароль)
        - ss: str | None (серверная последовательность, опционально)
    """
    if len(data) < 2:
        raise ValueError(f"Слишком маленькие данные AUTH_INFO: {len(data)} байт (минимум 2 байта для разделителей UNM и UPSW)")

    offset = 0

    # UNM: строка до нулевого разделителя (максимум 32 байта + разделитель)
    unm_end = data.find(b"\x00", offset)
    if unm_end == -1:
        raise ValueError("Не найден разделитель D (0x00) после UNM")
    if unm_end - offset > 32:
        raise ValueError(f"UNM превышает максимальную длину 32 байта: {unm_end - offset}")
    unm = _decode_string(data[offset:unm_end])
    offset = unm_end + 1  # Пропускаем разделитель

    # UPSW: строка до нулевого разделителя (максимум 32 байта + разделитель)
    upsw_end = data.find(b"\x00", offset)
    if upsw_end == -1:
        raise ValueError("Не найден разделитель D (0x00) после UPSW")
    if upsw_end - offset > 32:
        raise ValueError(f"UPSW превышает максимальную длину 32 байта: {upsw_end - offset}")
    upsw = _decode_string(data[offset:upsw_end])
    offset = upsw_end + 1  # Пропускаем разделитель

    # SS: опциональная строка до нулевого разделителя (максимум 255 байт + разделитель)
    ss: str | None = None
    if offset < len(data):
        ss_end = data.find(b"\x00", offset)
        if ss_end == -1:
            # Нет разделителя, но есть данные - декодируем до конца
            if len(data) - offset > 255:
                raise ValueError(f"SS превышает максимальную длину 255 байт: {len(data) - offset}")
            ss = _decode_string(data[offset:])
        else:
            if ss_end - offset > 255:
                raise ValueError(f"SS превышает максимальную длину 255 байт: {ss_end - offset}")
            ss = _decode_string(data[offset:ss_end])

    return {
        "unm": unm,
        "upsw": upsw,
        "ss": ss,
    }


def serialize_auth_info(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_AUTH_INFO (ГОСТ 33465-2015, таблица 24)

    Структура по ГОСТ:
    - UNM (0-32 байта): имя пользователя + разделитель D (0x00)
    - UPSW (0-32 байта): пароль + разделитель D (0x00)
    - SS (0-255 байт, опц.): серверная последовательность + разделитель D (0x00, опц.)

    Args:
        data: Dict с полями:
        - unm: str (имя пользователя, макс. 32 символа)
        - upsw: str (пароль, макс. 32 символа)
        - ss: str | None (серверная последовательность, макс. 255 символов, опционально)

    Returns:
        Байты данных подзаписи (SRD)

    Raises:
        ValueError: Если длина UNM или UPSW > 32, или SS > 255
    """
    result = bytearray()

    # UNM: имя пользователя + разделитель D (0x00)
    unm = data.get("unm", "")
    if isinstance(unm, str):
        unm_bytes = unm.encode("cp1251")
    else:
        unm_bytes = unm
    if len(unm_bytes) > 32:
        raise ValueError(f"UNM превышает максимальную длину 32 байта: {len(unm_bytes)}")
    result.extend(unm_bytes)
    result.append(0x00)  # Разделитель D

    # UPSW: пароль + разделитель D (0x00)
    upsw = data.get("upsw", "")
    if isinstance(upsw, str):
        upsw_bytes = upsw.encode("cp1251")
    else:
        upsw_bytes = upsw
    if len(upsw_bytes) > 32:
        raise ValueError(f"UPSW превышает максимальную длину 32 байта: {len(upsw_bytes)}")
    result.extend(upsw_bytes)
    result.append(0x00)  # Разделитель D

    # SS: серверная последовательность + разделитель D (0x00, опционально)
    ss = data.get("ss")
    if ss is not None:
        if isinstance(ss, str):
            ss_bytes = ss.encode("cp1251")
        else:
            ss_bytes = ss
        if len(ss_bytes) > 255:
            raise ValueError(f"SS превышает максимальную длину 255 байт: {len(ss_bytes)}")
        result.extend(ss_bytes)
        result.append(0x00)  # Разделитель D

    return bytes(result)
