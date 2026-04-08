"""
COMMANDS сервис EGTS (ГОСТ 33465-2015, раздел 6.7.3)

Сервис для обработки управляющих и конфигурационных команд,
информационных сообщений и статусов.

Подзаписи:
- EGTS_SR_RECORD_RESPONSE (0) - Подтверждение записи
- EGTS_SR_COMMAND_DATA (51) - Команды и сообщения
"""

from typing import Any

from .._internal.types import (
    EGTS_CHARSET,
    EGTS_CMD_MIN_SIZE,
    EGTS_COMMAND_ACL_SIZE,
    EGTS_COMMAND_ACT_MASK,
    # CD размеры
    EGTS_COMMAND_ADR_SIZE,
    EGTS_COMMAND_CCD_SIZE,
    EGTS_COMMAND_CHS_SIZE,
    EGTS_COMMAND_CID_SIZE,
    EGTS_COMMAND_CT_CCT_SIZE,
    # COMMAND_DATA размеры
    EGTS_COMMAND_DATA_MIN_SIZE,
    EGTS_COMMAND_FLAGS_SIZE,
    EGTS_COMMAND_SID_SIZE,
    EGTS_COMMAND_SZ_ACT_SIZE,
    EGTS_COMMAND_SZ_MASK,
    EGTS_COMMAND_SZ_SHIFT,
    EGTS_COMMAND_TYPE,
    EGTS_CONFIRMATION_TYPE,
    EGTS_PARAM_ACTION,
)

# Кодировки (CHS)
CHARSETS = {
    0: "CP-1251",
    1: "ASCII",
    2: "BINARY",
    3: "Latin1",
    4: "BINARY",
    5: "JIS",
    6: "Cyrillic",
    7: "Latin/Hebrew",
    8: "UCS2",
}

# Максимальные размеры для валидации
MAX_COMMAND_DATA_SIZE = 65535  # Максимальный размер CD
MAX_ACL_SIZE = 255  # Максимальный размер кода авторизации


# ============================================
# EGTS_SR_COMMAND_DATA (таблица 29)
# ============================================


def parse_command_data(data: bytes) -> dict[str, Any]:
    """
    Парсинг подзаписи EGTS_SR_COMMAND_DATA

    Args:
        data: Байты данных подзаписи (SRD)

    Returns:
        Dict с полями: ct, cct, cid, sid, acfe, chsfe, chs, acl, ac, cd

    Raises:
        ValueError: При некорректных данных или превышении размера
    """
    if len(data) < EGTS_COMMAND_DATA_MIN_SIZE:
        raise ValueError(
            f"Слишком маленькие данные COMMAND_DATA: {len(data)} байт (минимум {EGTS_COMMAND_DATA_MIN_SIZE})"
        )

    offset = 0

    # CT + CCT (1 байт)
    ct_cct = data[offset]
    offset += EGTS_COMMAND_CT_CCT_SIZE
    ct = (ct_cct >> 4) & 0x0F  # Старшие 4 бита
    cct = ct_cct & 0x0F  # Младшие 4 бита

    # CID (4 байта)
    cid = int.from_bytes(
        data[offset : offset + EGTS_COMMAND_CID_SIZE], "little"
    )
    offset += EGTS_COMMAND_CID_SIZE

    # SID (4 байта)
    sid = int.from_bytes(
        data[offset : offset + EGTS_COMMAND_SID_SIZE], "little"
    )
    offset += EGTS_COMMAND_SID_SIZE

    # Флаги (1 байт)
    flags = data[offset]
    offset += EGTS_COMMAND_FLAGS_SIZE
    acfe = bool((flags >> 7) & 0x01)  # Authorization Code Field Exists
    chsfe = bool((flags >> 6) & 0x01)  # Charset Field Exists

    # CHS (1 байт) - опционально
    chs = None
    if chsfe and offset < len(data):
        chs = data[offset]
        offset += EGTS_COMMAND_CHS_SIZE

    # ACL (1 байт) - опционально
    acl = None
    ac = None
    if acfe and offset < len(data):
        acl = data[offset]
        offset += EGTS_COMMAND_ACL_SIZE

        # Валидация размера ACL
        if acl > MAX_ACL_SIZE:
            raise ValueError(
                f"Размер кода авторизации превышает максимум: {acl} > {MAX_ACL_SIZE}"
            )

        # AC (acl байт)
        if offset + acl <= len(data):
            ac = data[offset : offset + acl]
            offset += acl

    # CD (Command Data) - оставшиеся байты
    cd = data[offset:] if offset < len(data) else b""

    # Валидация размера CD
    if len(cd) > MAX_COMMAND_DATA_SIZE:
        raise ValueError(
            f"Размер данных команды превышает максимум: {len(cd)} > {MAX_COMMAND_DATA_SIZE}"
        )

    return {
        "ct": ct,
        "ct_text": EGTS_COMMAND_TYPE(ct).name if ct in EGTS_COMMAND_TYPE._value2member_map_ else f"Unknown ({ct})",
        "cct": cct,
        "cct_text": EGTS_CONFIRMATION_TYPE(cct).name if cct in EGTS_CONFIRMATION_TYPE._value2member_map_ else f"Unknown ({cct})",
        "cid": cid,
        "sid": sid,
        "acfe": acfe,
        "chsfe": chsfe,
        "chs": chs,
        "chs_text": CHARSETS.get(chs, f"Unknown ({chs})") if chs is not None else None,
        "acl": acl,
        "ac": ac,
        "cd": cd,
    }


def serialize_command_data(data: dict[str, Any]) -> bytes:
    """
    Сериализация подзаписи EGTS_SR_COMMAND_DATA

    Args:
        data: Dict с полями: ct, cct, cid, sid, acfe, chsfe, chs, acl, ac, cd

    Returns:
        Байты данных подзаписи (SRD)
    """
    # CT + CCT (1 байт)
    ct = data.get("ct", 0)
    cct = data.get("cct", 0)
    ct_cct = ((ct & 0x0F) << 4) | (cct & 0x0F)

    result = bytes([ct_cct])

    # CID (4 байта)
    cid = data.get("cid", 0)
    result += cid.to_bytes(4, "little")

    # SID (4 байта)
    sid = data.get("sid", 0)
    result += sid.to_bytes(4, "little")

    # Флаги + CHS + ACL + AC
    acfe = data.get("acfe", False)
    chsfe = data.get("chsfe", False)
    flags = (0x80 if acfe else 0x00) | (0x40 if chsfe else 0x00)

    # CHS (1 байт)
    if chsfe:
        chs = data.get("chs", 0)
        result += bytes([flags, chs])
    else:
        result += bytes([flags])

    # ACL + AC
    if acfe:
        ac = data.get("ac", b"")
        acl = len(ac)
        result += bytes([acl]) + ac

    # CD (Command Data)
    cd = data.get("cd", b"")
    result += cd

    return result  # type: ignore[no-any-return]


# ============================================
# Вспомогательные функции для команд
# ============================================


def parse_command_details(cd: bytes) -> dict[str, Any]:
    """
    Парсинг деталей команды из CD (Command Data)

    CD = ADR(2) + SZ+ACT(1) + CCD(2) + DT(...)

    Args:
        cd: Байты команды (CD)

    Returns:
        Dict с полями: adr, sz, act, ccd, dt
    """
    if len(cd) < EGTS_CMD_MIN_SIZE:
        raise ValueError(
            f"Слишком маленькие данные команды: {len(cd)} байт (минимум {EGTS_CMD_MIN_SIZE})"
        )

    # ADR (2 байта) - адрес команды
    adr = int.from_bytes(cd[0:EGTS_COMMAND_ADR_SIZE], "little")

    # SZ + ACT (1 байт)
    sz_act = cd[EGTS_COMMAND_ADR_SIZE]
    sz = (sz_act >> EGTS_COMMAND_SZ_SHIFT) & EGTS_COMMAND_SZ_MASK  # Биты 7-3
    act = sz_act & EGTS_COMMAND_ACT_MASK  # Биты 2-0

    # CCD (2 байта) - код команды
    ccd = int.from_bytes(
        cd[
            EGTS_COMMAND_ADR_SIZE
            + EGTS_COMMAND_SZ_ACT_SIZE : EGTS_COMMAND_ADR_SIZE
            + EGTS_COMMAND_SZ_ACT_SIZE
            + EGTS_COMMAND_CCD_SIZE
        ],
        "little",
    )

    # DT (данные) - оставшиеся байты
    dt = cd[EGTS_CMD_MIN_SIZE:]

    return {
        "adr": adr,
        "sz": sz,
        "act": act,
        "ccd": ccd,
        "dt": dt,
    }


def create_command(
    ct: EGTS_COMMAND_TYPE,
    cid: int,
    command_code: int,
    address: int = 0,
    action: EGTS_PARAM_ACTION = EGTS_PARAM_ACTION.PARAMS,
    data: bytes = b"",
    sid: int = 0,
    ac: bytes = b"",
    chs: EGTS_CHARSET = EGTS_CHARSET.CP1251,
    sz: int = 0,  # SZ=0 для строк переменной длины
) -> dict[str, Any]:
    """
    Создание команды для УСВ

    Args:
        ct: Тип команды (EGTS_COMMAND_TYPE)
        cid: Идентификатор команды (0-4294967295)
        command_code: Код команды (например, EGTS_GET_VERSION)
        address: Адрес команды (ADR, 0-65535)
        action: Действие (EGTS_PARAM_ACTION)
        data: Данные команды (DT, макс. 255 байт)
        sid: Идентификатор отправителя (0-4294967295)
        ac: Код авторизации (макс. 255 байт)
        chs: Кодировка (EGTS_CHARSET)
        sz: Размер данных (0-31, 0 для строк переменной длины)

    Returns:
        Dict для serialize_command_data

    Raises:
        ValueError: При некорректных входных данных
    """
    # Валидация диапазонов
    if not (0 <= cid <= 0xFFFFFFFF):
        raise ValueError(f"CID должен быть в диапазоне 0-4294967295, получен {cid}")
    if not (0 <= address <= 0xFFFF):
        raise ValueError(f"Address должен быть в диапазоне 0-65535, получен {address}")
    if not (0 <= sid <= 0xFFFFFFFF):
        raise ValueError(f"SID должен быть в диапазоне 0-4294967295, получен {sid}")
    if len(data) > 255:
        raise ValueError(f"Данные команды не могут превышать 255 байт, получено {len(data)}")
    if len(ac) > 255:
        raise ValueError(f"Код авторизации не может превышать 255 байт, получено {len(ac)}")
    if not (0 <= sz <= 31):
        raise ValueError(f"SZ должен быть в диапазоне 0-31, получен {sz}")

    # Формируем тело команды: ADR + SZ + ACT + CCD + DT
    cmd_body = address.to_bytes(EGTS_COMMAND_ADR_SIZE, "little")

    # SZ + ACT (1 байт)
    # ГОСТ 33465-2015, таблица 30:
    # Биты 7-3: SZ (Size) — 5 бит, размер данных (0-31)
    # Биты 2-0: ACT (Action) — 3 бита, действие (0-7)
    # SZ=0 означает строку переменной длины (окончание по 0x00)
    sz_act = bytes([((sz & EGTS_COMMAND_SZ_MASK) << EGTS_COMMAND_SZ_SHIFT) | (action & EGTS_COMMAND_ACT_MASK)])

    # CCD (2 байта)
    cmd_body += sz_act + command_code.to_bytes(EGTS_COMMAND_CCD_SIZE, "little")

    # DT (данные)
    cmd_body += data

    return {
        "ct": ct.value if isinstance(ct, EGTS_COMMAND_TYPE) else ct,
        "cct": 0,
        "cid": cid,
        "sid": sid,
        "acfe": len(ac) > 0,
        "chsfe": chs != 0,
        "chs": chs.value if chs != 0 else None,
        "acl": len(ac) if len(ac) > 0 else None,
        "ac": ac if len(ac) > 0 else None,
        "cd": cmd_body,
    }


def create_command_response(
    cid: int,
    sid: int,
    cct: EGTS_CONFIRMATION_TYPE | int,
    result_data: bytes = b"",
) -> dict[str, Any]:
    """
    Создание подтверждения команды

    Args:
        cid: Идентификатор команды (из запроса, 0-4294967295)
        sid: Идентификатор отправителя (из запроса, 0-4294967295)
        cct: Тип подтверждения (EGTS_CONFIRMATION_TYPE или int)
        result_data: Данные результата (макс. 255 байт)

    Returns:
        Dict для serialize_command_data

    Raises:
        ValueError: При некорректных входных данных
    """
    # Валидация диапазонов
    if not (0 <= cid <= 0xFFFFFFFF):
        raise ValueError(f"CID должен быть в диапазоне 0-4294967295, получен {cid}")
    if not (0 <= sid <= 0xFFFFFFFF):
        raise ValueError(f"SID должен быть в диапазоне 0-4294967295, получен {sid}")
    if len(result_data) > 255:
        raise ValueError(f"Данные результата не могут превышать 255 байт, получено {len(result_data)}")

    # Преобразование cct в значение
    cct_value = cct.value if isinstance(cct, EGTS_CONFIRMATION_TYPE) else cct

    return {
        "ct": EGTS_COMMAND_TYPE.COMCONF.value,  # CT_COMCONF
        "cct": cct_value,
        "cid": cid,
        "sid": sid,
        "acfe": False,
        "chsfe": False,
        "cd": result_data,
    }


def create_message(
    message: str,
    cid: int,
    sid: int = 0,
    chs: EGTS_CHARSET = EGTS_CHARSET.CP1251,
) -> dict[str, Any]:
    """
    Создание информационного сообщения

    Args:
        message: Текст сообщения
        cid: Идентификатор сообщения (0-4294967295)
        sid: Идентификатор отправителя (0-4294967295)
        chs: Кодировка (EGTS_CHARSET)

    Returns:
        Dict для serialize_command_data

    Raises:
        ValueError: При некорректных входных данных или ошибке кодирования
    """
    # Валидация диапазонов
    if not (0 <= cid <= 0xFFFFFFFF):
        raise ValueError(f"CID должен быть в диапазоне 0-4294967295, получен {cid}")
    if not (0 <= sid <= 0xFFFFFFFF):
        raise ValueError(f"SID должен быть в диапазоне 0-4294967295, получен {sid}")

    # Валидация кодировки
    if not isinstance(chs, EGTS_CHARSET):
        try:
            chs = EGTS_CHARSET(chs)
        except ValueError as err:
            raise ValueError(f"Неизвестная кодировка: {chs}") from err

    # Выбор кодировки
    encoding_map = {
        EGTS_CHARSET.CP1251: "cp1251",
        EGTS_CHARSET.ASCII: "ascii",
        EGTS_CHARSET.LATIN1: "latin-1",
        EGTS_CHARSET.UCS2: "utf-16-le",
    }

    encoding = encoding_map.get(chs, "cp1251")

    try:
        cd = message.encode(encoding)
    except UnicodeEncodeError as err:
        raise ValueError(f"Невозможно закодировать сообщение в {chs.name}: {err}") from err

    if len(cd) > 65535:
        raise ValueError(f"Сообщение слишком длинное: {len(cd)} байт")

    return {
        "ct": EGTS_COMMAND_TYPE.MSGTO.value,  # CT_MSGTO
        "cct": 0,
        "cid": cid,
        "sid": sid,
        "acfe": False,
        "chsfe": True,  # Всегда передаем CHS
        "chs": chs.value,
        "cd": cd,
    }
