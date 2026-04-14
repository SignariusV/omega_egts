"""
Полный парсер/сериализатор подзаписей EGTS ГОСТ 2015

Связывает SRT (Subrecord Type) с конкретными парсерами из services/:
- auth.py: TERM_IDENTITY, MODULE_DATA, VEHICLE_DATA, RESULT_CODE, SERVICE_INFO
- commands.py: COMMAND_DATA
- ecall.py: ACCEL_DATA, TRACK_DATA, RAW_MSD_DATA
- firmware.py: SERVICE_PART_DATA, SERVICE_FULL_DATA

Использование:
    from subrecord_parser import parse_subrecord_data, serialize_subrecord_data

    # Парсинг SRD → dict
    parsed = parse_subrecord_data(srt=0x33, srd=b'...')
    # → {'ct': 5, 'cct': 0, 'cid': 0, 'sid': 0, ...}

    # Сериализация dict → SRD
    srd_bytes = serialize_subrecord_data(srt=0x33, data={'ct': 5, ...})
"""

from typing import Any

from .types import SubrecordType


# ──────────────────────────────────────────────────────────────
# RECORD_RESPONSE парсер/сериализатор (SRT=0)
# ──────────────────────────────────────────────────────────────

def _parse_record_response(data: bytes) -> dict[str, Any]:
    """
    Парсинг EGTS_SR_RECORD_RESPONSE (ГОСТ 33465 таблица 18)

    Структура:
    - CRN (2 байта): Confirm Record Number
    - RST (1 байт): Record Status
    """
    if len(data) < 3:
        return {"raw": data, "parse_error": f"Too short: {len(data)} bytes"}

    crn = int.from_bytes(data[0:2], "little")
    rst = data[2]
    return {"crn": crn, "rst": rst}


def _serialize_record_response(data: dict[str, Any]) -> bytes:
    """Сериализация EGTS_SR_RECORD_RESPONSE."""
    crn = data.get("crn", 0)
    rst = data.get("rst", 0)
    return crn.to_bytes(2, "little") + bytes([rst])


# ──────────────────────────────────────────────────────────────
# Registry парсеров/сериализаторов
# ──────────────────────────────────────────────────────────────

# Импортируем парсеры из services/ при первом вызове (lazy import)
_parsers: dict[int, tuple[Any, Any]] = {}  # srt → (parse_fn, serialize_fn)


def _init_parsers() -> None:
    """Ленивая инициализация registry парсеров."""
    if _parsers:
        return

    from .services import auth, commands, ecall, firmware

    # Врапперы для firmware — сигнатуры отличаются
    def _serialize_service_full_data_wrapper(data: dict) -> bytes:
        """Обёрка для serialize_service_full_data (odh + object_data из dict)."""
        odh = data.get("odh", b"")
        od = data.get("od", b"")
        if isinstance(odh, bytes) and isinstance(od, bytes):
            return firmware.serialize_service_full_data(odh, od)
        # Если уже raw есть
        return data.get("raw", b"")

    def _serialize_service_part_data_wrapper(data: dict) -> bytes:
        """Обёрка для serialize_service_part_data (parts из dict)."""
        # serialize_service_part_data принимает parts: list[dict]
        parts = data.get("parts", [])
        if parts:
            return firmware.serialize_service_part_data(parts)
        return data.get("raw", b"")

    def _parse_command_data_with_cd(data: bytes) -> dict[str, Any]:
        """Парсинг COMMAND_DATA с полным разбором CD (COM и COMCONF)."""
        from .services.commands import (
            parse_command_data,
            parse_command_details,
            parse_comconf_cd,
        )
        from .types import EGTS_COMMAND_TYPE

        result = parse_command_data(data)

        # Разбираем CD в зависимости от CT
        cd = result.get("cd", b"")
        ct = result.get("ct", 0)

        if cd and len(cd) >= 4:
            try:
                # COMCONF (CT=1): ADR(2) + CCD(2) + DT — без SZ+ACT
                if ct == EGTS_COMMAND_TYPE.COMCONF.value:
                    cd_parsed = parse_comconf_cd(cd)
                # COM (CT=5) и другие: ADR(2) + SZ+ACT(1) + CCD(2) + DT
                else:
                    cd_parsed = parse_command_details(cd)

                result.update(cd_parsed)

                # Текстовые имена
                try:
                    from .types import EGTS_PARAM_ACTION, EGTS_COMMAND_CODE

                    ccd_val = cd_parsed.get("ccd")
                    if ccd_val is not None:
                        try:
                            result["ccd_text"] = EGTS_COMMAND_CODE(ccd_val).name
                        except ValueError:
                            result["ccd_text"] = f"Unknown (0x{ccd_val:04X})"

                    # ACT есть только у COM
                    if "act" in cd_parsed:
                        act_val = cd_parsed.get("act")
                        try:
                            result["act_text"] = EGTS_PARAM_ACTION(act_val).name
                        except ValueError:
                            result["act_text"] = f"Unknown ({act_val})"

                    # DT как текст
                    dt = cd_parsed.get("dt", b"")
                    if dt:
                        try:
                            result["dt_text"] = dt.decode("cp1251")
                        except UnicodeDecodeError:
                            result["dt_hex"] = dt.hex()
                except ImportError:
                    pass
            except (ValueError, IndexError):
                # Ошибка парсинга CD — оставляем как есть
                pass

        return result

    def _serialize_command_data_with_cd(data: dict[str, Any]) -> bytes:
        """Сериализация COMMAND_DATA — используем оригинальный сериализатор."""
        from .services.commands import serialize_command_data
        return serialize_command_data(data)

    _parsers.update({
        # RECORD_RESPONSE — подтверждение записи (SRT=0)
        int(SubrecordType.EGTS_SR_RECORD_RESPONSE): (
            _parse_record_response,
            _serialize_record_response,
        ),
        # Auth сервис
        int(SubrecordType.EGTS_SR_TERM_IDENTITY): (
            auth.parse_term_identity,
            auth.serialize_term_identity,
        ),
        int(SubrecordType.EGTS_SR_MODULE_DATA): (
            auth.parse_module_data,
            auth.serialize_module_data,
        ),
        int(SubrecordType.EGTS_SR_VEHICLE_DATA): (
            auth.parse_vehicle_data,
            auth.serialize_vehicle_data,
        ),
        int(SubrecordType.EGTS_SR_RESULT_CODE): (
            auth.parse_result_code,
            auth.serialize_result_code,
        ),
        int(SubrecordType.EGTS_SR_SERVICE_INFO): (
            auth.parse_service_info,
            auth.serialize_service_info,
        ),
        # Commands сервис (с полным разбором CD)
        int(SubrecordType.EGTS_SR_COMMAND_DATA): (
            _parse_command_data_with_cd,
            _serialize_command_data_with_cd,
        ),
        # Ecall сервис
        int(SubrecordType.EGTS_SR_ACCEL_DATA): (
            ecall.parse_accel_data,
            ecall.serialize_accel_data,
        ),
        int(SubrecordType.EGTS_SR_RAW_MSD_DATA): (
            ecall.parse_raw_msd_data,
            ecall.serialize_raw_msd_data,
        ),
        int(SubrecordType.EGTS_SR_TRACK_DATA): (
            ecall.parse_track_data,
            ecall.serialize_track_data,
        ),
        # Firmware сервис (с врапперами для сериализации)
        int(SubrecordType.EGTS_SR_SERVICE_PART_DATA): (
            firmware.parse_service_part_data,
            _serialize_service_part_data_wrapper,
        ),
        int(SubrecordType.EGTS_SR_SERVICE_FULL_DATA): (
            firmware.parse_service_full_data,
            _serialize_service_full_data_wrapper,
        ),
    })


def parse_subrecord_data(srt: int, srd: bytes) -> dict[str, Any]:
    """
    Распарсить SRD в dict через специфичный парсер.

    Args:
        srt: Subrecord Type (int или SubrecordType)
        srd: Сырые байты данных подзаписи

    Returns:
        Dict с распарсенными полями подзаписи.
        Если парсер для SRT не найден — возвращает {'raw': srd}

    Example:
        >>> parse_subrecord_data(0x33, b'P\\x00...')
        {'ct': 5, 'cct': 0, 'cid': 0, 'sid': 0, 'acfe': False, ...}
    """
    _init_parsers()

    srt_int = int(srt) if isinstance(srt, (SubrecordType, int)) else srt

    parser = _parsers.get(srt_int)
    if parser is None:
        # Нет парсера — возвращаем сырые байты
        return {"raw": srd}

    parse_fn, _ = parser
    try:
        return parse_fn(srd)
    except (ValueError, IndexError, KeyError) as e:
        # Ошибка парсинга — возвращаем сырые байты + ошибку
        return {"raw": srd, "parse_error": str(e)}


def serialize_subrecord_data(srt: int, data: dict[str, Any]) -> bytes:
    """
    Сериализовать dict в SRD через специфичный сериализатор.

    Args:
        srt: Subrecord Type
        data: Dict с полями подзаписи (результат parse_subrecord_data)

    Returns:
        Байты SRD.
        Если сериализатор не найден — возвращает data.get('raw', b'')

    Example:
        >>> serialize_subrecord_data(0x33, {'ct': 5, 'cct': 0, 'cid': 0, ...})
        b'P\\x00...'
    """
    _init_parsers()

    srt_int = int(srt) if isinstance(srt, (SubrecordType, int)) else srt

    serializer = _parsers.get(srt_int)
    if serializer is None:
        # Нет сериализатора — берём raw
        return data.get("raw", b"")

    _, serialize_fn = serializer

    # Если есть parse_error — значит парсинг не удался, берём raw
    if "parse_error" in data:
        return data.get("raw", b"")

    try:
        return serialize_fn(data)
    except (ValueError, KeyError, TypeError) as e:
        raise ValueError(f"Ошибка сериализации SRT={srt_int}: {e}") from e


def has_parser(srt: int) -> bool:
    """Проверить есть ли парсер для данного SRT."""
    _init_parsers()
    return int(srt) in _parsers


def get_supported_srts() -> list[int]:
    """Вернуть список SRT для которых есть парсеры."""
    _init_parsers()
    return sorted(_parsers.keys())
