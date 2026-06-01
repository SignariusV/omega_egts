"""EGTS packet byte-level layout engine.

Computes a tree of ByteField with exact byte offsets, hex values,
and human-readable descriptions for every field in an EGTS packet.
"""

from dataclasses import dataclass, field
from enum import IntEnum


@dataclass
class ByteField:
    """A single field in the packet byte layout."""
    abbr: str
    full_name: str
    description: str
    offset_start: int
    offset_end: int
    hex_display: str
    value_display: str
    field_type: str = "field"
    error: bool = False
    children: list["ByteField"] = field(default_factory=list)


ABBREVIATIONS: dict[str, tuple[str, str]] = {
    "PRV": ("Protocol Version", "Версия протокола EGTS"),
    "SKID": ("Security Key ID", "Идентификатор ключа шифрования"),
    "PRF": ("Prefix", "Префикс заголовка (всегда 0)"),
    "RTE": ("Route", "Флаг маршрутизации — наличие PRA/RCA/TTL"),
    "ENA": ("Encryption Algorithm", "Алгоритм шифрования (зарезервирован)"),
    "CMP": ("Compressed", "Флаг сжатия данных фрейма"),
    "PR": ("Priority", "Приоритет пакета: 0=наивысший, 3=низкий"),
    "HL": ("Header Length", "Длина заголовка в байтах"),
    "HE": ("Header Encoding", "Кодирование заголовка (зарезервировано)"),
    "FDL": ("Frame Data Length", "Длина SFRD — данных уровня поддержки услуг"),
    "PID": ("Packet Identifier", "Номер пакета (циклический счётчик 0..65535)"),
    "PT": ("Packet Type", "Тип пакета: 0=RESPONSE, 1=APPDATA, 2=SIGNED_APPDATA"),
    "PRA": ("Peer Address", "Адрес ТП-отправителя"),
    "RCA": ("Recipient Address", "Адрес ТП-получателя"),
    "TTL": ("Time To Live", "Число хопов (транзитных узлов)"),
    "HCS": ("Header Check Sum", "CRC-8 заголовка (полином 0x31, init 0xFF)"),
    "SFRCS": ("Services Frame Data CRC", "CRC-16 данных SFRD (CCITT, полином 0x1021)"),
    "RPID": ("Response Packet ID", "Номер подтверждаемого пакета"),
    "PRC": ("Processing Result", "Код результата обработки"),
    "SIGL": ("Signature Length", "Длина цифровой подписи"),
    "SIGD": ("Signature Data", "Данные цифровой подписи"),
    "RL": ("Record Length", "Длина RD — данных записи (без заголовка)"),
    "RN": ("Record Number", "Номер записи (циклический счётчик)"),
    "RFL": ("Record Flags", "Флаги записи: SSOD, RSOD, RPP, OBFE, EVFE, TMFE"),
    "SSOD": ("Source Service On Device", "Сервис-отправитель на УСВ (1=на устройстве)"),
    "RSOD": ("Recipient Service On Device", "Сервис-получатель на УСВ (1=на устройстве)"),
    "RPP": ("Record Processing Priority", "Приоритет обработки записи (0=высший, 7=низший)"),
    "OBFE": ("Object ID Present", "Флаг наличия поля OID"),
    "EVFE": ("Event ID Present", "Флаг наличия поля EVID"),
    "TMFE": ("Time Mark Present", "Флаг наличия поля TM"),
    "SST": ("Source Service Type", "Тип сервиса-отправителя"),
    "RST": ("Recipient Service Type", "Тип сервиса-получателя"),
    "OID": ("Object Identifier", "Идентификатор объекта УСВ"),
    "EVID": ("Event Identifier", "Идентификатор события"),
    "TM": ("Time", "Время в секундах с 01.01.2010 00:00:00 UTC"),
    "SRT": ("Subrecord Type", "Тип подзаписи"),
    "SRL": ("Subrecord Length", "Длина данных подзаписи (SRD)"),
    "SRD": ("Subrecord Data", "Данные подзаписи"),
    "TID": ("Terminal Identifier", "Идентификатор терминала"),
    "HDID": ("Home Dispatcher ID", "Идентификатор домашней ТП"),
    "IMEI": ("IMEI", "International Mobile Equipment Identity"),
    "IMSI": ("IMSI", "International Mobile Subscriber Identity"),
    "LNGC": ("Language Code", "Код языка (3 символа, напр. 'rus')"),
    "NID": ("Network Identifier", "Идентификатор сети (MNC+MCC)"),
    "BS": ("Buffer Size", "Максимальный размер буфера приёма"),
    "MSISDN": ("MSISDN", "Номер телефона (до 15 цифр)"),
    "MT": ("Module Type", "Тип модуля"),
    "VID": ("Vendor ID", "Код производителя"),
    "FWV": ("Firmware Version", "Версия аппаратной части"),
    "SWV": ("Software Version", "Версия ПО"),
    "MD": ("Modification", "Код модификации ПО"),
    "ST": ("State", "Состояние модуля"),
    "SRN": ("Serial Number", "Серийный номер"),
    "DSCR": ("Description", "Описание модуля"),
    "RCD": ("Result Code", "Код результата"),
    "SA": ("Structures Amount", "Количество структур в подзаписи"),
    "ATM": ("Absolute Time Marker", "Абсолютная временная метка (сек с 01.01.2010)"),
    "RTM": ("Relative Time Marker", "Относительная временная метка (мс)"),
    "XAAV": ("X-Axis Acceleration Value", "Ускорение по оси X (0.1 м/с²)"),
    "YAAV": ("Y-Axis Acceleration Value", "Ускорение по оси Y (0.1 м/с²)"),
    "ZAAV": ("Z-Axis Acceleration Value", "Ускорение по оси Z (0.1 м/с²)"),
    "CT": ("Command Type", "Тип команды (COMCONF, MSGCONF, COM и т.д.)"),
    "CCT": ("Confirmation Type", "Тип подтверждения команды"),
    "CID": ("Command Identifier", "Идентификатор команды"),
    "SID": ("Source Identifier", "Идентификатор отправителя команды"),
    "ACFE": ("Auth Code Present", "Флаг наличия полей ACL/AC"),
    "CHSFE": ("Charset Present", "Флаг наличия поля CHS"),
    "CHS": ("Charset", "Кодировка символов"),
    "ACL": ("Auth Code Length", "Длина кода авторизации"),
    "AC": ("Authorization Code", "Код авторизации"),
    "ADR": ("Address", "Адрес модуля (команды)"),
    "ACT": ("Action", "Тип действия команды (SET, QUERY, DELETE и т.д.)"),
    "SZ": ("Size", "Размер операнда (2^SZ байт)"),
    "CCD": ("Command Code", "Код команды/параметра"),
    "DT": ("Data", "Данные команды"),
    "CRN": ("Confirmed Record Number", "Номер подтверждаемой записи"),
    "RCS": ("Record Status", "Статус записи (код результата)"),
    "ID": ("Entity ID", "Идентификатор сущности (FW)"),
    "PN": ("Part Number", "Номер части (FW)"),
    "EPQ": ("Expected Parts Quantity", "Ожидаемое количество частей (FW)"),
    "ODH": ("Object Data Header", "Заголовок объекта (FW)"),
    "OD": ("Object Data", "Данные объекта (FW)"),
    "VIN": ("Vehicle ID Number", "Идентификационный номер ТС (VIN)"),
    "VHT": ("Vehicle Hardware Type", "Тип аппаратной части ТС"),
    "VPST": ("Vehicle Propulsion Storage Type", "Тип энергоносителя ТС"),
    "FM": ("Format", "Формат данных MSD"),
    "MSD": ("Minimum Set of Data", "Минимальный набор данных (eCall MSD)"),
    "TNDE": ("Track Node Data Exist", "Флаг наличия данных точки трека"),
    "LOHS": ("Longitude Hemisphere", "Полушарие долготы (0=восток, 1=запад)"),
    "LAHS": ("Latitude Hemisphere", "Полушарие широты (0=север, 1=юг)"),
    "SDFE": ("Direction Field Exist", "Флаг наличия направления"),
    "SPFE": ("Speed Field Exist", "Флаг наличия скорости"),
    "LAT": ("Latitude", "Широта"),
    "LONG": ("Longitude", "Долгота"),
    "SPD": ("Speed", "Скорость (км/ч × 0.01)"),
    "DIR": ("Direction", "Направление (0-359 град)"),
    "FLG": ("Flags", "Флаги параметров авторизации"),
    "UNM": ("User Name", "Имя пользователя"),
    "UPSW": ("User Password", "Пароль пользователя"),
    "SS": ("Session String", "Строка сессии"),
    "SRVP": ("Service Parameters", "Параметры сервиса (активность + приоритет)"),
    "SRVA": ("Service Active", "Сервис активен"),
    "SRVRP": ("Service Routing Priority", "Приоритет маршрутизации сервиса"),
    "OA": ("Object Attribute", "Атрибут объекта (FW)"),
    "OT": ("Object Type (FW)", "Тип сущности (FW)"),
    "CMI": ("Component/Module ID (FW)", "Идентификатор модуля (FW)"),
    "VER": ("Version (FW)", "Версия (FW)"),
    "WOS": ("Whole Object Signature", "Сигнатура всего объекта (FW)"),
    "FN": ("File Name", "Имя файла (FW)"),
}

DESCRIPTIONS: dict[int, tuple[str, str]] = {
    0: ("RECORD_RESPONSE", "Подтверждение обработки записи"),
    1: ("TERM_IDENTITY", "Идентификация терминала"),
    2: ("MODULE_DATA", "Данные модуля"),
    3: ("VEHICLE_DATA", "Данные транспортного средства"),
    6: ("AUTH_PARAMS", "Параметры авторизации"),
    7: ("AUTH_INFO", "Информация для авторизации"),
    8: ("SERVICE_INFO", "Информация о сервисах"),
    9: ("RESULT_CODE", "Код результата операции"),
    20: ("ACCEL_DATA", "Профиль ускорения (акселерометр)"),
    33: ("SERVICE_PART_DATA", "Частичная передача данных ПО"),
    34: ("SERVICE_FULL_DATA", "Полная передача данных ПО"),
    51: ("COMMAND_DATA", "Команда"),
    62: ("RAW_MSD_DATA", "Данные eCall MSD"),
    63: ("TRACK_DATA", "Данные траектории/трека"),
}

PACKET_TYPE_NAMES = {0: "RESPONSE", 1: "APPDATA", 2: "SIGNED_APPDATA"}
SERVICE_TYPE_NAMES = {1: "AUTH", 2: "TELEDATA", 4: "COMMANDS", 9: "FIRMWARE", 10: "ECALL"}
PRIORITY_NAMES = {0: "0 — Highest", 1: "1 — High", 2: "2 — Medium", 3: "3 — Low"}
COMMAND_TYPE_NAMES = {0x1: "COMCONF", 0x2: "MSGCONF", 0x3: "MSGFROM", 0x4: "MSGTO", 0x5: "COM", 0x6: "DELCOM", 0x7: "SUBREQ", 0x8: "DELIV"}
CONFIRMATION_TYPE_NAMES = {0x0: "OK", 0x1: "ERROR", 0x2: "ILL", 0x3: "DEL", 0x4: "NFOUND", 0x5: "NCONF", 0x6: "INPROG"}
ACTION_TYPE_NAMES = {0x0: "PARAMS", 0x1: "QUERY", 0x2: "SET", 0x3: "ADD", 0x4: "DELETE"}
COMMAND_CODES = {
    0x0000: "EGTS_RAW_DATA", 0x0001: "EGTS_TEST_MODE", 0x0006: "EGTS_CONFIG_RESET",
    0x0007: "EGTS_SET_AUTH_CODE", 0x0008: "EGTS_RESTART", 0x0101: "EGTS_GPRS_APN",
    0x0102: "EGTS_SERVER_ADDRESS", 0x0103: "EGTS_SIM_PIN",
    0x0104: "EGTS_AUTOMATIC_REGISTRATION", 0x0105: "EGTS_REGISTRATION_ATTEMPTS",
    0x0106: "EGTS_REGISTRATION_TIMEOUT", 0x0107: "EGTS_GPRS_CONNECTION_ATTEMPTS",
    0x0108: "EGTS_GPRS_CONNECTION_TIMEOUT", 0x0109: "EGTS_TCP_CONNECTION_ATTEMPTS",
    0x010A: "EGTS_TCP_CONNECTION_TIMEOUT", 0x010B: "EGTS_INACTIVITY_TIMEOUT",
    0x010C: "EGTS_SERVICE_ENABLE", 0x010D: "EGTS_NETWORK_SEARCH_PERIOD",
    0x0113: "EGTS_ECALL_MSD_REQ", 0x0114: "EGTS_ACCEL_DATA",
    0x0115: "EGTS_TRACK_DATA", 0x0116: "EGTS_ECALL_DEREGISTRATION",
    0x0203: "EGTS_SET_GPRS_APN", 0x0204: "EGTS_SET_SERVER_ADDRESS",
    0x020D: "EGTS_ECALL_TEST_NUMBER", 0x0404: "EGTS_UNIT_ID", 0x0405: "EGTS_UNIT_IMEI",
}
RESULT_CODES: dict[int, str] = {
    0: "OK", 1: "IN_PROGRESS", 128: "UNS_PROTOCOL", 129: "DECRYPT_ERROR",
    130: "PROC_DENIED", 131: "INC_HEADERFORM", 132: "INC_DATAFORM", 133: "UNS_TYPE",
    134: "NOTEN_PARAMS", 135: "DBL_PROC", 136: "PROC_SRC_DENIED", 137: "HEADERCRC_ERROR",
    138: "DATACRC_ERROR", 139: "INVDATALEN", 140: "ROUTE_NFOUND", 141: "ROUTE_CLOSED",
    142: "ROUTE_DENIED", 143: "INVADDR", 144: "TTLEXPIRED", 145: "NO_ACK",
    146: "OBJ_NFOUND", 147: "EVNT_NFOUND", 148: "SRVC_NFOUND", 149: "SRVC_DENIED",
    150: "SRVC_UNKN", 151: "AUTH_DENIED", 152: "ALREADY_EXISTS", 153: "ID_NFOUND",
    154: "INC_DATETIME",
}
CHARSET_NAMES = {0: "CP1251", 1: "ASCII", 2: "BINARY", 3: "LATIN1",
                 4: "BINARY2", 5: "JIS", 6: "CYRILLIC", 7: "LATIN_HEBREW", 8: "UCS2"}


def _abbr(abbr: str) -> tuple[str, str]:
    return ABBREVIATIONS.get(abbr, (abbr, ""))


def _hex(data: bytes) -> str:
    return data.hex().upper() if data else ""


def _hex_spaced(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data) if data else ""


def _label(abbr: str, value_display: str = "") -> str:
    full, desc = _abbr(abbr)
    if desc:
        label = f"{abbr} ({full}) — {desc}"
    else:
        label = f"{abbr} ({full})"
    if value_display:
        return f"{label} → {value_display}"
    return label


def _make_field(abbr: str, offset_start: int, offset_end: int,
                raw_bytes: bytes, value_display: str = "",
                field_type: str = "field", error: bool = False,
                children: list | None = None) -> ByteField:
    full, desc = _abbr(abbr)
    vd = value_display or _hex_spaced(raw_bytes)
    return ByteField(
        abbr=abbr, full_name=full, description=desc,
        offset_start=offset_start, offset_end=offset_end,
        hex_display=_hex_spaced(raw_bytes),
        value_display=vd, field_type=field_type, error=error,
        children=children or []
    )


def _make_section(name: str, offset_start: int, offset_end: int,
                  children: list, value_display: str = "") -> ByteField:
    desc = f"({offset_end - offset_start + 1} bytes)" if offset_end >= offset_start else ""
    vd = value_display or desc
    return ByteField(
        abbr="", full_name=name, description="",
        offset_start=offset_start, offset_end=offset_end,
        hex_display="", value_display=vd,
        field_type="section", children=children
    )


def _int_le(data: bytes, start: int, length: int) -> int:
    return int.from_bytes(data[start:start + length], 'little')


def _int8(data: bytes, offset: int) -> int:
    return data[offset]


def _uint16_le(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], 'little')


def _uint32_le(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], 'little')


def _decode_str(data: bytes, offset: int, length: int) -> str:
    chunk = data[offset:offset + length]
    try:
        return chunk.rstrip(b"\x00").decode("cp1251")
    except UnicodeDecodeError:
        return chunk.hex()


def _decode_until_null(data: bytes, offset: int) -> tuple[str, int]:
    end = offset
    while end < len(data) and data[end] != 0:
        end += 1
    chunk = data[offset:end]
    try:
        return chunk.decode("cp1251"), end + 1
    except UnicodeDecodeError:
        return chunk.hex(), end + 1


def _build_header_layout(data: bytes) -> list[ByteField]:
    fields = []
    hl = _int8(data, 3)
    flags_byte = _int8(data, 2)

    fields.append(_make_field("PRV", 0, 0, data[0:1],
                              f"0x{data[0]:02X} ({data[0]})"))
    fields.append(_make_field("SKID", 1, 1, data[1:2],
                              f"0x{data[1]:02X} ({data[1]})"))

    flag_bits = []
    prf = bool(flags_byte & 0x80)
    rte = bool(flags_byte & 0x40)
    ena = (flags_byte >> 4) & 0x03
    cmp = bool(flags_byte & 0x08)
    pr = flags_byte & 0x03

    flag_bits.append(_make_field("PRF", 2, 2, data[2:3],
                                 f"{int(prf)} — {'set' if prf else 'clear'}",
                                 field_type="bitfield"))
    flag_bits.append(_make_field("RTE", 2, 2, data[2:3],
                                 f"{int(rte)} — {'routing present' if rte else 'no routing'}",
                                 field_type="bitfield"))
    flag_bits.append(_make_field("ENA", 2, 2, data[2:3],
                                 f"{ena} — bits 5-4 (encryption)",
                                 field_type="bitfield"))
    flag_bits.append(_make_field("CMP", 2, 2, data[2:3],
                                 f"{int(cmp)} — {'compressed' if cmp else 'not compressed'}",
                                 field_type="bitfield"))
    flag_bits.append(_make_field("PR", 2, 2, data[2:3],
                                 PRIORITY_NAMES.get(pr, f"{pr} — unknown"),
                                 field_type="bitfield"))

    fields.append(_make_field("FLAGS", 2, 2, data[2:3],
                              f"0x{flags_byte:02X}",
                              children=flag_bits))

    fields.append(_make_field("HL", 3, 3, data[3:4],
                              f"{hl} (0x{hl:02X})"))
    he = _int8(data, 4)
    fields.append(_make_field("HE", 4, 4, data[4:5],
                              f"0x{he:02X} ({he})"))
    fdl = _uint16_le(data, 5)
    fields.append(_make_field("FDL", 5, 6, data[5:7],
                              f"{fdl} (0x{fdl:04X})"))
    pid = _uint16_le(data, 7)
    fields.append(_make_field("PID", 7, 8, data[7:9],
                              f"{pid} (0x{pid:04X})"))
    pt = _int8(data, 9)
    pt_name = PACKET_TYPE_NAMES.get(pt, f"UNKNOWN_{pt}")
    fields.append(_make_field("PT", 9, 9, data[9:10],
                              f"{pt_name} ({pt})"))
    if rte:
        pra = _uint16_le(data, 10)
        fields.append(_make_field("PRA", 10, 11, data[10:12],
                                  f"0x{pra:04X} ({pra})"))
        rca = _uint16_le(data, 12)
        fields.append(_make_field("RCA", 12, 13, data[12:14],
                                  f"0x{rca:04X} ({rca})"))
        ttl = _int8(data, 14)
        fields.append(_make_field("TTL", 14, 14, data[14:15],
                                  f"{ttl}"))
        hcs_offset = 14
    else:
        hcs_offset = hl - 1

    hcs_byte = _int8(data, hcs_offset)
    computed_hcs = _crc8(data[:hcs_offset])
    hcs_ok = hcs_byte == computed_hcs
    hcs_label = f"0x{hcs_byte:02X}"
    if hcs_ok:
        hcs_label += " ✅ OK"
    else:
        hcs_label += f" ❌ (expected 0x{computed_hcs:02X})"
    fields.append(_make_field("HCS", hcs_offset, hcs_offset,
                              data[hcs_offset:hcs_offset + 1],
                              hcs_label, error=not hcs_ok))

    return fields, hl, pt, fdl, rte


def _crc8(data: bytes) -> int:
    poly = 0x31
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFF
    return crc


def _crc16(data: bytes) -> int:
    poly = 0x1021
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def _build_response_sfrd(data: bytes, offset: int) -> tuple[list[ByteField], int]:
    fields = []
    rpid = _uint16_le(data, offset)
    fields.append(_make_field("RPID", offset, offset + 1, data[offset:offset + 2],
                              f"{rpid} (0x{rpid:04X})"))
    offset += 2
    pr = _int8(data, offset)
    rc_name = RESULT_CODES.get(pr, f"UNKNOWN_{pr}")
    fields.append(_make_field("PRC", offset, offset, data[offset:offset + 1],
                              f"{rc_name} ({pr})"))
    offset += 1
    return fields, offset


def _build_record_layout(data: bytes, offset: int,
                        parsed_subrecords: list[dict] | None = None
                        ) -> tuple[list[ByteField], int, int]:
    fields = []
    rec_start = offset
    rl = _uint16_le(data, offset)
    fields.append(_make_field("RL", offset, offset + 1, data[offset:offset + 2],
                              f"{rl} (0x{rl:04X})"))
    offset += 2
    rn = _uint16_le(data, offset)
    fields.append(_make_field("RN", offset, offset + 1, data[offset:offset + 2],
                              f"{rn} (0x{rn:04X})"))
    offset += 2
    rfl = _int8(data, offset)
    rfl_bits = []
    ssod = bool(rfl & 0x80)
    rsod = bool(rfl & 0x40)
    rpp = (rfl >> 3) & 0x07
    obfe = bool(rfl & 0x04)
    evfe = bool(rfl & 0x02)
    tmfe = bool(rfl & 0x01)
    rfl_bits.append(_make_field("SSOD", offset, offset, data[offset:offset + 1],
                                f"{int(ssod)} — {'on device' if ssod else 'on platform'}",
                                field_type="bitfield"))
    rfl_bits.append(_make_field("RSOD", offset, offset, data[offset:offset + 1],
                                f"{int(rsod)} — {'on device' if rsod else 'on platform'}",
                                field_type="bitfield"))
    rfl_bits.append(_make_field("RPP", offset, offset, data[offset:offset + 1],
                                f"{rpp} — priority {rpp}",
                                field_type="bitfield"))
    rfl_bits.append(_make_field("OBFE", offset, offset, data[offset:offset + 1],
                                f"{int(obfe)} — {'OID present' if obfe else 'no OID'}",
                                field_type="bitfield"))
    rfl_bits.append(_make_field("EVFE", offset, offset, data[offset:offset + 1],
                                f"{int(evfe)} — {'EVID present' if evfe else 'no EVID'}",
                                field_type="bitfield"))
    rfl_bits.append(_make_field("TMFE", offset, offset, data[offset:offset + 1],
                                f"{int(tmfe)} — {'TM present' if tmfe else 'no TM'}",
                                field_type="bitfield"))
    fields.append(_make_field("RFL", offset, offset, data[offset:offset + 1],
                              f"0x{rfl:02X}", children=rfl_bits))
    offset += 1

    sst = _int8(data, offset)
    sst_name = SERVICE_TYPE_NAMES.get(sst, f"UNKNOWN_{sst}")
    fields.append(_make_field("SST", offset, offset, data[offset:offset + 1],
                              f"{sst_name} ({sst})"))
    offset += 1
    rst = _int8(data, offset)
    rst_name = SERVICE_TYPE_NAMES.get(rst, f"UNKNOWN_{rst}")
    fields.append(_make_field("RST", offset, offset, data[offset:offset + 1],
                              f"{rst_name} ({rst})"))
    offset += 1

    if obfe:
        oid = _uint32_le(data, offset)
        fields.append(_make_field("OID", offset, offset + 3, data[offset:offset + 4],
                                  f"0x{oid:08X} ({oid})"))
        offset += 4
    if evfe:
        evid = _uint16_le(data, offset)
        fields.append(_make_field("EVID", offset, offset + 1, data[offset:offset + 2],
                                  f"{evid} (0x{evid:04X})"))
        offset += 2
    if tmfe:
        tm = _uint32_le(data, offset)
        fields.append(_make_field("TM", offset, offset + 3, data[offset:offset + 4],
                                  f"{tm} (0x{tm:08X}) sec from 2010-01-01"))
        offset += 4

    rd_end = offset + rl
    sub_fields, offset = _build_subrecords_layout(data, offset, rd_end, parsed_subrecords)
    fields.extend(sub_fields)
    offset = rd_end

    rec_end = offset - 1
    return fields, rec_start, rec_end


def _build_subrecords_layout(data: bytes, offset: int, end: int,
                             parsed_subrecords: list[dict] | None = None) -> tuple[list[ByteField], int]:
    """Build layout for subrecords within a record.

    parsed_subrecords: optional list of {srt, data, raw_bytes} from the canonical
    parser. When provided, the matching parsed_data dict is forwarded to each
    _parse_srt_N so values come from the canonical parser (single source of truth).
    """
    fields = []
    sub_idx = 0
    while offset < end:
        if offset + 3 > len(data):
            break
        srt = _int8(data, offset)
        srt_name, srt_desc = DESCRIPTIONS.get(srt, (f"SRT_{srt}", "Unknown subrecord type"))
        srt_field = _make_field("SRT", offset, offset, data[offset:offset + 1],
                                f"{srt_name} ({srt}) — {srt_desc}")
        fields.append(srt_field)
        offset += 1

        if offset + 2 > len(data):
            break
        srl = _uint16_le(data, offset)
        fields.append(_make_field("SRL", offset, offset + 1, data[offset:offset + 2],
                                  f"{srl} (0x{srl:04X})"))
        offset += 2

        # Match this subrecord to its parsed counterpart (same srt, in order).
        parsed_data = None
        if parsed_subrecords is not None and sub_idx < len(parsed_subrecords):
            psr = parsed_subrecords[sub_idx]
            if psr.get("srt") == srt:
                parsed_data = psr.get("data")

        if offset + srl > len(data):
            srl = len(data) - offset
        if srl > 0:
            srd_data = data[offset:offset + srl]
            srd_fields = _parse_srd(srt, data, offset, srl, parsed_data)
            if srd_fields:
                fields.extend(srd_fields)
            else:
                fields.append(_make_field("SRD", offset, offset + srl - 1,
                                          srd_data, field_type="subrecord_data"))
        offset += srl
        sub_idx += 1
    return fields, offset


def _parse_srd(srt: int, data: bytes, offset: int, length: int,
               parsed_data: dict | None = None) -> list[ByteField]:
    """Dispatch subrecord layout by SRT.

    parsed_data: when provided, byte offsets are still walked here (for accurate
    highlight ranges in the hex viewer), but values are pulled from parsed_data
    (produced by the canonical parser in libs/egts/_gost2015/subrecords.py).
    This eliminates duplication of the value-decoding logic and the offset bugs
    in the SRT=20/33/34/63 layout walkers.
    """
    if srt == 0:
        return _parse_srt_0(data, offset, length, parsed_data)
    elif srt == 1:
        return _parse_srt_1(data, offset, length, parsed_data)
    elif srt == 2:
        return _parse_srt_2(data, offset, length, parsed_data)
    elif srt == 3:
        return _parse_srt_3(data, offset, length, parsed_data)
    elif srt == 6:
        return _parse_srt_6(data, offset, length, parsed_data)
    elif srt == 7:
        return _parse_srt_7(data, offset, length, parsed_data)
    elif srt == 8:
        return _parse_srt_8(data, offset, length, parsed_data)
    elif srt == 9:
        return _parse_srt_9(data, offset, length, parsed_data)
    elif srt == 20:
        return _parse_srt_20(data, offset, length, parsed_data)
    elif srt == 33:
        return _parse_srt_33(data, offset, length, parsed_data)
    elif srt == 34:
        return _parse_srt_34(data, offset, length, parsed_data)
    elif srt == 51:
        return _parse_srt_51(data, offset, length, parsed_data)
    elif srt == 62:
        return _parse_srt_62(data, offset, length, parsed_data)
    elif srt == 63:
        return _parse_srt_63(data, offset, length, parsed_data)
    return []


def _parse_srt_0(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len >= 2:
        crn = parsed_data["crn"] if parsed_data and "crn" in parsed_data else _uint16_le(data, offset)
        fields.append(_make_field("CRN", offset, offset + 1, data[offset:offset + 2],
                                  f"{crn} (0x{crn:04X})"))
        offset += 2
    if _len >= 3:
        rcs = parsed_data["rst"] if parsed_data and "rst" in parsed_data else _int8(data, offset)
        rc_name = RESULT_CODES.get(rcs, f"UNKNOWN_{rcs}")
        fields.append(_make_field("RCS", offset, offset, data[offset:offset + 1],
                                  f"{rc_name} ({rcs})"))
    return fields


def _parse_srt_1(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 4:
        return fields
    tid = parsed_data["tid"] if parsed_data and "tid" in parsed_data else _uint32_le(data, offset)
    fields.append(_make_field("TID", offset, offset + 3, data[offset:offset + 4],
                              f"{tid} (0x{tid:08X})"))
    offset += 4
    if _len < 5:
        return fields
    flags = parsed_data["flags"] if parsed_data and "flags" in parsed_data else _int8(data, offset)
    flag_names = ["HDIDE", "IMEIE", "IMSIE", "LNGCE", "SSRA", "NIDE", "BSE", "MNE"]
    flag_bits = []
    flag_desc = ["Home Dispatcher ID", "IMEI", "IMSI", "Language Code",
                 "Simple Service Request Algorithm", "Network ID",
                 "Buffer Size", "MSISDN"]
    for i, (fn, fd) in enumerate(zip(flag_names, flag_desc)):
        bit_val = bool(flags & (1 << i))
        flag_bits.append(_make_field(fn, offset, offset, data[offset:offset + 1],
                                     f"{int(bit_val)} — {'present' if bit_val else 'absent'} ({fd})",
                                     field_type="bitfield"))
    fields.append(_make_field("FLG", offset, offset, data[offset:offset + 1],
                              f"0x{flags:02X}", children=flag_bits))
    offset += 1

    if _len >= 7 and (flags & 0x01):
        hdid = parsed_data["hdid"] if parsed_data and "hdid" in parsed_data else _uint16_le(data, offset)
        fields.append(_make_field("HDID", offset, offset + 1, data[offset:offset + 2],
                                  f"0x{hdid:04X} ({hdid})"))
        offset += 2
    if _len >= 22 and (flags & 0x02):
        if parsed_data and "imei" in parsed_data:
            imei = str(parsed_data["imei"])
        else:
            imei = _decode_str(data, offset, 15)
        fields.append(_make_field("IMEI", offset, offset + 14, data[offset:offset + 15],
                                  imei))
        offset += 15
    if _len >= 38 and (flags & 0x04):
        if parsed_data and "imsi" in parsed_data:
            imsi = str(parsed_data["imsi"])
        else:
            imsi = _decode_str(data, offset, 16)
        fields.append(_make_field("IMSI", offset, offset + 15, data[offset:offset + 16],
                                  imsi))
        offset += 16
    if _len >= 41 and (flags & 0x08):
        if parsed_data and "lngc" in parsed_data:
            lngc = str(parsed_data["lngc"])
        else:
            lngc = _decode_str(data, offset, 3)
        fields.append(_make_field("LNGC", offset, offset + 2, data[offset:offset + 3],
                                  lngc))
        offset += 3
    if _len >= 44 and (flags & 0x20):
        if parsed_data and "nid" in parsed_data and isinstance(parsed_data["nid"], (bytes, bytearray)):
            nid = bytes(parsed_data["nid"])
        else:
            nid = data[offset:offset + 3]
        fields.append(_make_field("NID", offset, offset + 2, nid,
                                  nid.hex()))
        offset += 3
    if _len >= 46 and (flags & 0x40):
        bs = parsed_data["bs"] if parsed_data and "bs" in parsed_data else _uint16_le(data, offset)
        fields.append(_make_field("BS", offset, offset + 1, data[offset:offset + 2],
                                  f"{bs} (0x{bs:04X})"))
        offset += 2
    if _len >= 61 and (flags & 0x80):
        if parsed_data and "msisdn" in parsed_data:
            msisdn = str(parsed_data["msisdn"])
        else:
            msisdn = _decode_str(data, offset, 15)
        fields.append(_make_field("MSISDN", offset, offset + 14, data[offset:offset + 15],
                                  msisdn))
        offset += 15
    return fields


def _parse_srt_2(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 11:
        return fields
    mt = parsed_data["mt"] if parsed_data and "mt" in parsed_data else _int8(data, offset)
    mt_names = {1: "Main", 2: "I/O", 3: "GNSS", 4: "Wireless"}
    mt_name = mt_names.get(mt, f"Unknown ({mt})")
    fields.append(_make_field("MT", offset, offset, data[offset:offset + 1], mt_name))
    offset += 1
    vid = parsed_data["vid"] if parsed_data and "vid" in parsed_data else _uint32_le(data, offset)
    fields.append(_make_field("VID", offset, offset + 3, data[offset:offset + 4],
                              f"0x{vid:08X} ({vid})"))
    offset += 4
    fwv = parsed_data["fwv"] if parsed_data and "fwv" in parsed_data else _uint16_le(data, offset)
    fields.append(_make_field("FWV", offset, offset + 1, data[offset:offset + 2],
                              f"{fwv} (major={fwv >> 8}, minor={fwv & 0xFF})"))
    offset += 2
    swv = parsed_data["swv"] if parsed_data and "swv" in parsed_data else _uint16_le(data, offset)
    fields.append(_make_field("SWV", offset, offset + 1, data[offset:offset + 2],
                              f"{swv} (major={swv >> 8}, minor={swv & 0xFF})"))
    offset += 2
    md_val = parsed_data["md"] if parsed_data and "md" in parsed_data else _int8(data, offset)
    fields.append(_make_field("MD", offset, offset, data[offset:offset + 1],
                              f"0x{md_val:02X} ({md_val})"))
    offset += 1
    st_val = parsed_data["st"] if parsed_data and "st" in parsed_data else _int8(data, offset)
    st_names = {0: "Off", 1: "On"}
    st_name = st_names.get(st_val, f"Fault ({st_val})" if st_val > 127 else str(st_val))
    fields.append(_make_field("ST", offset, offset, data[offset:offset + 1], st_name))
    offset += 1
    remaining = data[offset:]
    if remaining:
        srn_value = parsed_data.get("srn") if parsed_data else None
        srn, offset = _decode_until_null(data, offset)
        if srn_value is None:
            srn_value = srn
        fields.append(_make_field("SRN", offset - len(srn) - 1, offset - 2,
                                  data[offset - len(srn) - 1:offset],
                                  srn_value, field_type="subrecord_data"))
        if offset < len(data):
            dscr, offset = _decode_until_null(data, offset)
            if dscr:
                dscr_value = parsed_data.get("dscr") if parsed_data else None
                if dscr_value is None:
                    dscr_value = dscr
                fields.append(_make_field("DSCR", offset - len(dscr) - 1, offset - 2,
                                          data[offset - len(dscr) - 1:offset],
                                          dscr_value, field_type="subrecord_data"))
    return fields


def _parse_srt_3(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 25:
        return fields
    vin = parsed_data.get("vin", _decode_str(data, offset, 17)) if parsed_data else _decode_str(data, offset, 17)
    fields.append(_make_field("VIN", offset, offset + 16, data[offset:offset + 17], vin))
    offset += 17
    vht = parsed_data["vht"] if parsed_data and "vht" in parsed_data else _uint32_le(data, offset)
    fields.append(_make_field("VHT", offset, offset + 3, data[offset:offset + 4],
                              f"0x{vht:08X}"))
    offset += 4
    vpst = parsed_data["vpst"] if parsed_data and "vpst" in parsed_data else _uint32_le(data, offset)
    fields.append(_make_field("VPST", offset, offset + 3, data[offset:offset + 4],
                              f"0x{vpst:08X}"))
    return fields


def _parse_srt_6(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 1:
        return fields
    flg = parsed_data["flg"] if parsed_data and "flg" in parsed_data else _int8(data, offset)
    flag_bits = []
    bit_names = ["ENA", "PKE", "ISLE", "MSE", "SSE", "EXE"]
    bit_desc = ["Encryption Algorithm", "Public Key", "Identity String Len",
                "Mod Size", "Server Sequence", "Exp"]
    for i, (fn, fd) in enumerate(zip(bit_names, bit_desc)):
        bit_val = bool(flg & (1 << i))
        flag_bits.append(_make_field(fn, offset, offset, data[offset:offset + 1],
                                     f"{int(bit_val)} — {'present' if bit_val else 'absent'} ({fd})",
                                     field_type="bitfield"))
    fields.append(_make_field("FLG", offset, offset, data[offset:offset + 1],
                              f"0x{flg:02X}", children=flag_bits))
    offset += 1

    pos = offset
    if _len >= 3 and (flg & 0x02):
        if pos + 2 <= len(data):
            pkl = parsed_data["pkl"] if parsed_data and "pkl" in parsed_data else _uint16_le(data, pos)
            fields.append(_make_field("PKL", pos, pos + 1, data[pos:pos + 2], f"{pkl}"))
            pos += 2
            if pkl and pkl > 0 and pos + pkl <= len(data):
                fields.append(_make_field("PBK", pos, pos + pkl - 1,
                                          data[pos:pos + pkl], f"({pkl} bytes)"))
                pos += pkl
    if _len >= 3 and (flg & 0x04):
        if pos + 2 <= len(data):
            isl = parsed_data["isl"] if parsed_data and "isl" in parsed_data else _uint16_le(data, pos)
            fields.append(_make_field("ISL", pos, pos + 1, data[pos:pos + 2], f"{isl}"))
            pos += 2
            if isl and isl > 0 and pos + isl <= len(data):
                fields.append(_make_field("IS", pos, pos + isl - 1,
                                          data[pos:pos + isl], f"({isl} bytes)"))
                pos += isl
    if _len >= 3 and (flg & 0x08):
        if pos + 2 <= len(data):
            msz = parsed_data["msz"] if parsed_data and "msz" in parsed_data else _uint16_le(data, pos)
            fields.append(_make_field("MSZ", pos, pos + 1, data[pos:pos + 2], f"{msz}"))
            pos += 2
    if _len >= 3 and (flg & 0x10):
        if pos + 2 <= len(data):
            ssl = parsed_data["ssl"] if parsed_data and "ssl" in parsed_data else _uint16_le(data, pos)
            fields.append(_make_field("SSL", pos, pos + 1, data[pos:pos + 2], f"{ssl}"))
            pos += 2
            if ssl and ssl > 0 and pos + ssl <= len(data):
                fields.append(_make_field("SS", pos, pos + ssl - 1,
                                          data[pos:pos + ssl], f"({ssl} bytes)"))
                pos += ssl
    if flg & 0x20:
        if pos < len(data) and data[pos] == 0:
            pos += 1
            exp_str, pos = _decode_until_null(data, pos)
            if exp_str:
                exp_value = parsed_data.get("exp") if parsed_data else None
                if exp_value is None:
                    exp_value = exp_str
                fields.append(_make_field("EXP", pos - len(exp_str) - 1, pos - 2,
                                          data[pos - len(exp_str) - 1:pos],
                                          exp_value, field_type="subrecord_data"))
    return fields


def _parse_srt_7(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    pos = offset
    unm_local, pos = _decode_until_null(data, pos)
    if unm_local:
        unm_value = parsed_data.get("unm") if parsed_data else None
        if unm_value is None:
            unm_value = unm_local
        fields.append(_make_field("UNM", offset, pos - 2,
                                  data[offset:pos], unm_value))
    upsw_local, pos = _decode_until_null(data, pos)
    if upsw_local:
        fstart = pos - len(upsw_local) - 1
        upsw_value = parsed_data.get("upsw") if parsed_data else None
        if upsw_value is None:
            upsw_value = upsw_local
        fields.append(_make_field("UPSW", fstart, pos - 2,
                                  data[fstart:pos], upsw_value))
    if pos < len(data):
        ss_local, pos = _decode_until_null(data, pos)
        if ss_local:
            fstart = pos - len(ss_local) - 1
            ss_value = parsed_data.get("ss") if parsed_data else None
            if ss_value is None:
                ss_value = ss_local
            fields.append(_make_field("SS", fstart, pos - 2,
                                      data[fstart:pos], ss_value))
    return fields


def _parse_srt_8(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    pos = offset
    if pos >= len(data):
        return fields
    srvp = parsed_data["srvp"] if parsed_data and "srvp" in parsed_data else _int8(data, pos)
    srvp_bits = []
    srva = bool(srvp & 0x80)
    srvrp = srvp & 0x03
    srvp_bits.append(_make_field("SRVA", pos, pos, data[pos:pos + 1],
                                 f"{int(srva)} — {'active' if srva else 'inactive'}",
                                 field_type="bitfield"))
    srvp_bits.append(_make_field("SRVRP", pos, pos, data[pos:pos + 1],
                                 f"{srvrp} — priority {srvrp}",
                                 field_type="bitfield"))
    fields.append(_make_field("SRVP", pos, pos, data[pos:pos + 1],
                              f"0x{srvp:02X}", children=srvp_bits))
    pos += 1

    while pos + 2 < len(data):
        st_val = _int8(data, pos)
        st_name = SERVICE_TYPE_NAMES.get(st_val, f"Unknown ({st_val})")
        fields.append(_make_field("ST", pos, pos, data[pos:pos + 1],
                                  f"{st_name} ({st_val})"))
        pos += 1
        sst_val = _int8(data, pos)
        sst_name = SERVICE_TYPE_NAMES.get(sst_val, f"Unknown ({sst_val})")
        fields.append(_make_field("SST", pos, pos, data[pos:pos + 1],
                                  f"{sst_name} ({sst_val})"))
        pos += 1
        srvp_n = _int8(data, pos)
        fields.append(_make_field("SRVP", pos, pos, data[pos:pos + 1],
                                  f"0x{srvp_n:02X}"))
        pos += 1
    return fields


def _parse_srt_9(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len >= 1:
        rcd = parsed_data["rcd"] if parsed_data and "rcd" in parsed_data else _int8(data, offset)
        rc_name = parsed_data.get("rcd_text") if parsed_data else None
        if not rc_name:
            rc_name = RESULT_CODES.get(rcd, f"UNKNOWN_{rcd}")
        fields.append(_make_field("RCD", offset, offset, data[offset:offset + 1],
                                  f"{rc_name} ({rcd})"))
    return fields


def _parse_srt_20(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 5:
        return fields
    sa = parsed_data["sa"] if parsed_data and "sa" in parsed_data else _int8(data, offset)
    fields.append(_make_field("SA", offset, offset, data[offset:offset + 1], f"{sa}"))
    offset += 1
    # FIX Б-03: bounds check was `offset + 4 > offset + _len` (tautology ≡ 4 > _len).
    # Correct: use len(data) since SRL may be longer than actual buffer.
    if offset + 4 > len(data):
        return fields
    atm = parsed_data["atm"] if parsed_data and "atm" in parsed_data else _uint32_le(data, offset)
    fields.append(_make_field("ATM", offset, offset + 3, data[offset:offset + 4],
                              f"{atm} sec from 2010-01-01"))
    offset += 4

    # FIX Б-03: prefer iterating the canonical `measurements` list (already
    # correctly bounded). Fallback uses `range(sa)` with `len(data)` bounds check.
    if parsed_data and isinstance(parsed_data.get("measurements"), list):
        measurements = parsed_data["measurements"]
        for i, m in enumerate(measurements):
            if offset + 8 > len(data):
                break
            measurement_start = offset
            ad_fields = []
            rtm = m.get("rtm") if isinstance(m, dict) else None
            if rtm is None:
                rtm = _uint16_le(data, offset)
            xaav = m.get("xaav") if isinstance(m, dict) else None
            yaav = m.get("yaav") if isinstance(m, dict) else None
            zaav = m.get("zaav") if isinstance(m, dict) else None
            if xaav is None or yaav is None or zaav is None:
                xaav = int.from_bytes(data[offset + 2:offset + 4], 'little', signed=True) * 0.1
                yaav = int.from_bytes(data[offset + 4:offset + 6], 'little', signed=True) * 0.1
                zaav = int.from_bytes(data[offset + 6:offset + 8], 'little', signed=True) * 0.1
            ad_fields.append(_make_field("RTM", offset, offset + 1, data[offset:offset + 2],
                                         f"{rtm} ms"))
            ad_fields.append(_make_field("XAAV", offset + 2, offset + 3, data[offset + 2:offset + 4],
                                         f"{xaav:.1f} m/s²"))
            ad_fields.append(_make_field("YAAV", offset + 4, offset + 5, data[offset + 4:offset + 6],
                                         f"{yaav:.1f} m/s²"))
            ad_fields.append(_make_field("ZAAV", offset + 6, offset + 7, data[offset + 6:offset + 8],
                                         f"{zaav:.1f} m/s²"))
            offset += 8
            fields.append(_make_section(f"Measurement {i + 1}",
                                        measurement_start, offset - 1, ad_fields,
                                        f"[{rtm}ms] X={xaav:.1f} Y={yaav:.1f} Z={zaav:.1f}"))
    else:
        for i in range(sa):
            if offset + 8 > len(data):
                break
            measurement_start = offset
            ad_fields = []
            rtm = _uint16_le(data, offset)
            ad_fields.append(_make_field("RTM", offset, offset + 1, data[offset:offset + 2],
                                         f"{rtm} ms"))
            offset += 2
            xaav = int.from_bytes(data[offset:offset + 2], 'little', signed=True) * 0.1
            ad_fields.append(_make_field("XAAV", offset, offset + 1, data[offset:offset + 2],
                                         f"{xaav:.1f} m/s²"))
            offset += 2
            yaav = int.from_bytes(data[offset:offset + 2], 'little', signed=True) * 0.1
            ad_fields.append(_make_field("YAAV", offset, offset + 1, data[offset:offset + 2],
                                         f"{yaav:.1f} m/s²"))
            offset += 2
            zaav = int.from_bytes(data[offset:offset + 2], 'little', signed=True) * 0.1
            ad_fields.append(_make_field("ZAAV", offset, offset + 1, data[offset:offset + 2],
                                         f"{zaav:.1f} m/s²"))
            offset += 2
            fields.append(_make_section(f"Measurement {i + 1}",
                                        measurement_start, offset - 1, ad_fields,
                                        f"[{rtm}ms] X={xaav:.1f} Y={yaav:.1f} Z={zaav:.1f}"))
    return fields


def _parse_srt_33(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 8:
        return fields
    sid = parsed_data["id"] if parsed_data and "id" in parsed_data else _uint16_le(data, offset)
    fields.append(_make_field("ID", offset, offset + 1, data[offset:offset + 2],
                              f"0x{sid:04X} ({sid})"))
    offset += 2
    pn = parsed_data["pn"] if parsed_data and "pn" in parsed_data else _uint16_le(data, offset)
    fields.append(_make_field("PN", offset, offset + 1, data[offset:offset + 2], f"{pn}"))
    offset += 2
    epq = parsed_data["epq"] if parsed_data and "epq" in parsed_data else _uint16_le(data, offset)
    fields.append(_make_field("EPQ", offset, offset + 1, data[offset:offset + 2], f"{epq}"))
    offset += 2

    # FIX Б-01: when parsed_data has `odh`, use its length instead of re-walking bytes.
    odh_raw = parsed_data.get("odh") if parsed_data else None
    if isinstance(odh_raw, (bytes, bytearray)) and len(odh_raw) > 0 and pn == 1:
        odh_data = bytes(odh_raw)
        odh_fields, _ = _parse_odh(data, offset, len(odh_data))
        fields.append(_make_section("ODH", offset, offset + len(odh_data) - 1, odh_fields,
                                    f"({len(odh_data)} bytes)"))
        offset += len(odh_data)
    elif pn == 1 and offset < len(data):
        # Fallback: walk bytes to find null-terminated ODH
        odh_end = offset
        while odh_end < len(data) and data[odh_end] != 0:
            odh_end += 1
        if odh_end < len(data):
            odh_end += 1
        odh_data = data[offset:odh_end]
        if odh_data:
            odh_fields, _ = _parse_odh(data, offset, len(odh_data))
            fields.append(_make_section("ODH", offset, odh_end - 1, odh_fields,
                                        f"({len(odh_data)} bytes)"))
            offset = odh_end

    # FIX Б-01: use parsed_data["od"] length, not the broken `remaining = _len - 6` formula.
    od_raw = parsed_data.get("od") if parsed_data else None
    if isinstance(od_raw, (bytes, bytearray)):
        od_data = bytes(od_raw)
        if len(od_data) > 0:
            fields.append(_make_field("OD", offset, offset + len(od_data) - 1,
                                      od_data, f"({len(od_data)} bytes)",
                                      field_type="subrecord_data"))
    elif offset < len(data):
        # Fallback: take all remaining bytes
        rest = data[offset:]
        if rest:
            fields.append(_make_field("OD", offset, offset + len(rest) - 1,
                                      rest, f"({len(rest)} bytes)",
                                      field_type="subrecord_data"))
    return fields


def _parse_srt_34(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    # FIX Б-02: use parsed_data["odh"] length when available, not the broken formula.
    odh_raw = parsed_data.get("odh") if parsed_data else None
    if isinstance(odh_raw, (bytes, bytearray)) and len(odh_raw) > 0:
        odh_data = bytes(odh_raw)
        odh_fields, _ = _parse_odh(data, offset, len(odh_data))
        fields.append(_make_section("ODH", offset, offset + len(odh_data) - 1, odh_fields,
                                    f"({len(odh_data)} bytes)"))
        offset += len(odh_data)
    else:
        # Fallback: walk bytes to find null-terminated ODH
        odh_end = offset
        while odh_end < len(data) and data[odh_end] != 0:
            odh_end += 1
        if odh_end < len(data):
            odh_end += 1
        odh_data = data[offset:odh_end]
        if odh_data:
            odh_fields, new_offset = _parse_odh(data, offset, len(odh_data))
            fields.append(_make_section("ODH", offset, new_offset - 1, odh_fields,
                                        f"({len(odh_data)} bytes)"))
            offset = new_offset

    # FIX Б-02: OD length comes from parsed_data["od"], not from the always-zero formula.
    od_raw = parsed_data.get("od") if parsed_data else None
    if isinstance(od_raw, (bytes, bytearray)):
        od_data = bytes(od_raw)
        if len(od_data) > 0:
            fields.append(_make_field("OD", offset, offset + len(od_data) - 1,
                                      od_data, f"({len(od_data)} bytes)",
                                      field_type="subrecord_data"))
    elif offset < len(data):
        rest = data[offset:]
        if rest:
            fields.append(_make_field("OD", offset, offset + len(rest) - 1,
                                      rest, f"({len(rest)} bytes)",
                                      field_type="subrecord_data"))
    return fields


def _parse_odh(data: bytes, offset: int, _len: int) -> tuple[list[ByteField], int]:
    fields = []
    end = offset + _len
    if offset >= len(data):
        return fields, offset
    oa = _int8(data, offset)
    fields.append(_make_field("OA", offset, offset, data[offset:offset + 1],
                              f"0x{oa:02X}"))
    offset += 1
    if offset >= len(data):
        return fields, offset
    ot_mt = _int8(data, offset)
    ot = (ot_mt >> 6) & 0x03
    mt_val = ot_mt & 0x3F
    fields.append(_make_field("OT", offset, offset, data[offset:offset + 1],
                              f"OT={ot}, MT={mt_val}"))
    offset += 1
    if offset >= len(data):
        return fields, offset
    cmi = _int8(data, offset)
    fields.append(_make_field("CMI", offset, offset, data[offset:offset + 1],
                              f"0x{cmi:02X} ({cmi})"))
    offset += 1
    if offset + 1 >= len(data):
        return fields, offset
    ver = _uint16_le(data, offset)
    fields.append(_make_field("VER", offset, offset + 1, data[offset:offset + 2],
                              f"major={ver >> 8}, minor={ver & 0xFF}"))
    offset += 2
    if offset + 1 >= len(data):
        return fields, offset
    wos = _uint16_le(data, offset)
    fields.append(_make_field("WOS", offset, offset + 1, data[offset:offset + 2],
                              f"0x{wos:04X}"))
    offset += 2
    if offset < end:
        fn_str, offset = _decode_until_null(data, offset)
        if fn_str:
            fields.append(_make_field("FN", offset - len(fn_str) - 1, offset - 2,
                                      data[offset - len(fn_str) - 1:offset],
                                      fn_str, field_type="subrecord_data"))
    return fields, offset


def _parse_srt_51(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 10:
        return fields
    if parsed_data and "ct" in parsed_data:
        ct = parsed_data["ct"]
        cct = parsed_data["cct"]
        ct_name = parsed_data.get("ct_text") or COMMAND_TYPE_NAMES.get(ct, f"UNKNOWN_CT_{ct}")
        cct_name = parsed_data.get("cct_text") or CONFIRMATION_TYPE_NAMES.get(cct, f"UNKNOWN_CCT_{cct}")
    else:
        ct_cct = _int8(data, offset)
        ct = (ct_cct >> 4) & 0x0F
        cct = ct_cct & 0x0F
        ct_name = COMMAND_TYPE_NAMES.get(ct, f"UNKNOWN_CT_{ct}")
        cct_name = CONFIRMATION_TYPE_NAMES.get(cct, f"UNKNOWN_CCT_{cct}")
    ctcct_bits = []
    ct_label = f"CT ({ct_name})"
    cct_label = f"CCT ({cct_name})"
    ctcct_bits.append(_make_field("CT", offset, offset, data[offset:offset + 1],
                                  ct_label, field_type="bitfield"))
    ctcct_bits.append(_make_field("CCT", offset, offset, data[offset:offset + 1],
                                  cct_label, field_type="bitfield"))
    fields.append(_make_field("FLG", offset, offset, data[offset:offset + 1],
                              f"CT={ct_name} ({ct}), CCT={cct_name} ({cct})",
                              children=ctcct_bits))
    offset += 1
    cid = parsed_data["cid"] if parsed_data and "cid" in parsed_data else _uint32_le(data, offset)
    fields.append(_make_field("CID", offset, offset + 3, data[offset:offset + 4],
                              f"0x{cid:08X}"))
    offset += 4
    sid = parsed_data["sid"] if parsed_data and "sid" in parsed_data else _uint32_le(data, offset)
    fields.append(_make_field("SID", offset, offset + 3, data[offset:offset + 4],
                              f"0x{sid:08X}"))
    offset += 4
    if parsed_data and "acfe" in parsed_data:
        acfe = bool(parsed_data["acfe"])
        chsfe = bool(parsed_data["chsfe"])
    else:
        ac_chs_flags = _int8(data, offset)
        acfe = bool(ac_chs_flags & 0x80)
        chsfe = bool(ac_chs_flags & 0x40)
    flag_bits = []
    flag_bits.append(_make_field("ACFE", offset, offset, data[offset:offset + 1],
                                 f"{int(acfe)}", field_type="bitfield"))
    flag_bits.append(_make_field("CHSFE", offset, offset, data[offset:offset + 1],
                                 f"{int(chsfe)}", field_type="bitfield"))
    fields.append(_make_field("ACL", offset, offset, data[offset:offset + 1],
                              f"0x{(_int8(data, offset)):02X}", children=flag_bits))
    offset += 1
    acl_len = 0
    if chsfe and offset < len(data):
        if parsed_data and "chs" in parsed_data and parsed_data["chs"] is not None:
            chs = parsed_data["chs"]
            chs_name = parsed_data.get("chs_text") or CHARSET_NAMES.get(chs, f"UNKNOWN_{chs}")
        else:
            chs = _int8(data, offset)
            chs_name = CHARSET_NAMES.get(chs, f"UNKNOWN_{chs}")
        fields.append(_make_field("CHS", offset, offset, data[offset:offset + 1],
                                  f"{chs_name} ({chs})"))
        offset += 1
    if acfe and offset < len(data):
        acl_val = parsed_data["acl"] if parsed_data and "acl" in parsed_data else _int8(data, offset)
        fields.append(_make_field("ACL", offset, offset, data[offset:offset + 1], f"{acl_val}"))
        offset += 1
        if acl_val is not None and acl_val > 0 and offset + acl_val <= len(data):
            ac_data = data[offset:offset + acl_val]
            fields.append(_make_field("AC", offset, offset + acl_val - 1,
                                      ac_data, f"({acl_val} bytes)"))
            offset += acl_val
            acl_len = acl_val

    cd_remaining = max(0, _len - 10 - (1 if chsfe else 0) - (1 if acfe else 0) - acl_len)

    if cd_remaining > 0:
        cd_fields = _parse_cd(ct, data, offset, cd_remaining)
        if cd_fields:
            fields.append(_make_section("CD", offset, offset + cd_remaining - 1,
                                        cd_fields, f"({cd_remaining} bytes)"))
        else:
            fields.append(_make_field("CD", offset, offset + cd_remaining - 1,
                                      data[offset:offset + cd_remaining],
                                      f"({cd_remaining} bytes)", field_type="subrecord_data"))
    return fields


def _parse_cd(ct: int, data: bytes, offset: int, _len: int) -> list[ByteField]:
    if ct == 5:
        return _parse_cd_com(data, offset, _len)
    elif ct == 1:
        return _parse_cd_comconf(data, offset, _len)
    return []


def _parse_cd_com(data: bytes, offset: int, _len: int) -> list[ByteField]:
    fields = []
    if _len < 5:
        return fields
    adr = _uint16_le(data, offset)
    fields.append(_make_field("ADR", offset, offset + 1, data[offset:offset + 2],
                              f"0x{adr:04X} ({adr})"))
    offset += 2
    act_sz = _int8(data, offset)
    sz = (act_sz >> 5) & 0x07
    act = act_sz & 0x1F
    act_name = ACTION_TYPE_NAMES.get(act, f"UNKNOWN_{act}")
    act_bits = []
    act_bits.append(_make_field("ACT", offset, offset, data[offset:offset + 1],
                                f"{act_name} ({act})", field_type="bitfield"))
    act_bits.append(_make_field("SZ", offset, offset, data[offset:offset + 1],
                                f"{sz} (2^{sz} = {2 ** sz} bytes)", field_type="bitfield"))
    fields.append(_make_field("ACT", offset, offset, data[offset:offset + 1],
                              f"{act_name} ({act}), 2^{sz}={2**sz}",
                              children=act_bits))
    offset += 1
    ccd = _uint16_le(data, offset)
    ccd_name = COMMAND_CODES.get(ccd, f"0x{ccd:04X}")
    fields.append(_make_field("CCD", offset, offset + 1, data[offset:offset + 2],
                              f"{ccd_name} (0x{ccd:04X})"))
    offset += 2
    dt_len = _len - 5
    if dt_len > 0:
        fields.append(_make_field("DT", offset, offset + dt_len - 1,
                                  data[offset:offset + dt_len],
                                  _decode_str(data, offset, dt_len) if dt_len <= 64
                                  else f"({dt_len} bytes)", field_type="subrecord_data"))
    return fields


def _parse_cd_comconf(data: bytes, offset: int, _len: int) -> list[ByteField]:
    fields = []
    if _len < 4:
        return fields
    adr = _uint16_le(data, offset)
    fields.append(_make_field("ADR", offset, offset + 1, data[offset:offset + 2],
                              f"0x{adr:04X} ({adr})"))
    offset += 2
    ccd = _uint16_le(data, offset)
    ccd_name = COMMAND_CODES.get(ccd, f"0x{ccd:04X}")
    fields.append(_make_field("CCD", offset, offset + 1, data[offset:offset + 2],
                              f"{ccd_name} (0x{ccd:04X})"))
    offset += 2
    dt_len = _len - 4
    if dt_len > 0:
        fields.append(_make_field("DT", offset, offset + dt_len - 1,
                                  data[offset:offset + dt_len],
                                  _decode_str(data, offset, dt_len) if dt_len <= 64
                                  else f"({dt_len} bytes)", field_type="subrecord_data"))
    return fields


def _parse_srt_62(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 1:
        return fields
    fm = parsed_data["fm"] if parsed_data and "fm" in parsed_data else _int8(data, offset)
    fields.append(_make_field("FM", offset, offset, data[offset:offset + 1],
                              f"0x{fm:02X} ({fm})"))
    offset += 1
    if _len > 1:
        # When parsed_data is available, prefer the canonical parser's MSD bytes
        # (guaranteed to match what the server sent, even if SRL is malformed).
        if parsed_data and "msd" in parsed_data and isinstance(parsed_data["msd"], (bytes, bytearray)):
            msd_data = bytes(parsed_data["msd"])
        else:
            msd_data = data[offset:offset + _len - 1]
        if msd_data:
            fields.append(_make_field("MSD", offset, offset + len(msd_data) - 1,
                                      msd_data, f"({len(msd_data)} bytes)",
                                      field_type="subrecord_data"))
    return fields


def _parse_srt_63(data: bytes, offset: int, _len: int,
                parsed_data: dict | None = None) -> list[ByteField]:
    fields = []
    if _len < 5:
        return fields
    sa = parsed_data["sa"] if parsed_data and "sa" in parsed_data else _int8(data, offset)
    fields.append(_make_field("SA", offset, offset, data[offset:offset + 1], f"{sa}"))
    offset += 1
    atm = parsed_data["atm"] if parsed_data and "atm" in parsed_data else _uint32_le(data, offset)
    fields.append(_make_field("ATM", offset, offset + 3, data[offset:offset + 4],
                              f"{atm} sec from 2010-01-01"))
    offset += 4

    # FIX Б-05: iterate `track_points` from canonical parser (correct count) and
    # track each point's byte range via `point_start` (was `offset - 1 - len(data[offset-1:offset])`).
    track_points = parsed_data.get("track_points") if parsed_data else None
    if isinstance(track_points, list):
        point_iter = track_points
    else:
        point_iter = range(sa)

    for i, _ in enumerate(point_iter):
        if offset >= len(data):
            break
        # FIX Б-05: save the start of the point section before advancing offset.
        point_start = offset
        hdr = _int8(data, offset)
        tnde = bool(hdr & 0x80)
        lohs = bool(hdr & 0x40)
        lahs = bool(hdr & 0x20)
        sdfe = bool(hdr & 0x10)
        spfe = bool(hdr & 0x08)
        rtm = hdr & 0x07

        tp_bits = [
            _make_field("TNDE", offset, offset, data[offset:offset + 1],
                        f"{int(tnde)}", field_type="bitfield"),
            _make_field("LOHS", offset, offset, data[offset:offset + 1],
                        f"{int(lohs)}", field_type="bitfield"),
            _make_field("LAHS", offset, offset, data[offset:offset + 1],
                        f"{int(lahs)}", field_type="bitfield"),
            _make_field("SDFE", offset, offset, data[offset:offset + 1],
                        f"{int(sdfe)}", field_type="bitfield"),
            _make_field("SPFE", offset, offset, data[offset:offset + 1],
                        f"{int(spfe)}", field_type="bitfield"),
            _make_field("RTM", offset, offset, data[offset:offset + 1],
                        f"{rtm} ({rtm * 0.1}s)", field_type="bitfield"),
        ]
        tp_fields = [_make_field("FLG", offset, offset, data[offset:offset + 1],
                                 f"0x{hdr:02X}", children=tp_bits)]
        offset += 1

        if tnde and offset + 11 <= len(data):
            lat_raw = _uint32_le(data, offset)
            tp_fields.append(_make_field("LAT", offset, offset + 3, data[offset:offset + 4],
                                         f"{lat_raw} (degrees: {lat_raw / 0xFFFFFFFF * 180:.6f})"))
            offset += 4
            if offset + 4 > len(data):
                break
            lon_raw = _uint32_le(data, offset)
            tp_fields.append(_make_field("LONG", offset, offset + 3, data[offset:offset + 4],
                                         f"{lon_raw} (degrees: {lon_raw / 0xFFFFFFFF * 360:.6f})"))
            offset += 4
            if spfe and offset + 2 <= len(data):
                spd_low = _uint16_le(data, offset)
                offset += 2
                if offset < len(data):
                    dirh_spdh = _int8(data, offset)
                    spd_high = (dirh_spdh >> 1) & 0x01
                    dir_high = dirh_spdh & 0x01
                    speed = ((spd_high << 14) | spd_low) * 0.01
                    tp_fields.append(_make_field("SPD", offset - 2, offset,
                                                  data[offset - 2:offset + 1],
                                                  f"{speed:.2f} km/h"))
                    offset += 1
        elif tnde and spfe and offset + 3 <= len(data):
            spd_low = _uint16_le(data, offset)
            offset += 2
            if offset < len(data):
                dirh_spdh = _int8(data, offset)
                spd_high = (dirh_spdh >> 1) & 0x01
                dir_high = dirh_spdh & 0x01
                speed = ((spd_high << 14) | spd_low) * 0.01
                tp_fields.append(_make_field("SPD", offset - 2, offset,
                                              data[offset - 2:offset + 1],
                                              f"{speed:.2f} km/h"))
                offset += 1

        if sdfe and offset < len(data):
            direc = _int8(data, offset)
            tp_fields.append(_make_field("DIR", offset, offset, data[offset:offset + 1],
                                         f"{direc}°"))
            offset += 1

        summary = f"Point {i + 1} [RTM={rtm * 0.1}s]"
        # FIX Б-05: use point_start (correct) instead of `offset - 1 - len(data[offset-1:offset])` (= offset - 2).
        fields.append(_make_section(f"Point {i + 1}",
                                    point_start, offset - 1, tp_fields, summary))
    return fields
    sa = _int8(data, offset)
    fields.append(_make_field("SA", offset, offset, data[offset:offset + 1], f"{sa}"))
    offset += 1
    atm = _uint32_le(data, offset)
    fields.append(_make_field("ATM", offset, offset + 3, data[offset:offset + 4],
                              f"{atm} sec from 2010-01-01"))
    offset += 4

    for i in range(sa):
        if offset >= len(data):
            break
        hdr = _int8(data, offset)
        tnde = bool(hdr & 0x80)
        lohs = bool(hdr & 0x40)
        lahs = bool(hdr & 0x20)
        sdfe = bool(hdr & 0x10)
        spfe = bool(hdr & 0x08)
        rtm = hdr & 0x07

        tp_bits = [
            _make_field("TNDE", offset, offset, data[offset:offset + 1],
                        f"{int(tnde)}", field_type="bitfield"),
            _make_field("LOHS", offset, offset, data[offset:offset + 1],
                        f"{int(lohs)}", field_type="bitfield"),
            _make_field("LAHS", offset, offset, data[offset:offset + 1],
                        f"{int(lahs)}", field_type="bitfield"),
            _make_field("SDFE", offset, offset, data[offset:offset + 1],
                        f"{int(sdfe)}", field_type="bitfield"),
            _make_field("SPFE", offset, offset, data[offset:offset + 1],
                        f"{int(spfe)}", field_type="bitfield"),
            _make_field("RTM", offset, offset, data[offset:offset + 1],
                        f"{rtm} ({rtm * 0.1}s)", field_type="bitfield"),
        ]
        tp_fields = [_make_field("FLG", offset, offset, data[offset:offset + 1],
                                 f"0x{hdr:02X}", children=tp_bits)]
        offset += 1

        if tnde and offset + 11 <= len(data):
            lat_raw = _uint32_le(data, offset)
            tp_fields.append(_make_field("LAT", offset, offset + 3, data[offset:offset + 4],
                                         f"{lat_raw} (degrees: {lat_raw / 0xFFFFFFFF * 180:.6f})"))
            offset += 4
            if offset + 4 > len(data):
                break
            lon_raw = _uint32_le(data, offset)
            tp_fields.append(_make_field("LONG", offset, offset + 3, data[offset:offset + 4],
                                         f"{lon_raw} (degrees: {lon_raw / 0xFFFFFFFF * 360:.6f})"))
            offset += 4
            if spfe and offset + 2 <= len(data):
                spd_low = _uint16_le(data, offset)
                offset += 2
                if offset < len(data):
                    dirh_spdh = _int8(data, offset)
                    spd_high = (dirh_spdh >> 1) & 0x01
                    dir_high = dirh_spdh & 0x01
                    speed = ((spd_high << 14) | spd_low) * 0.01
                    tp_fields.append(_make_field("SPD", offset - 2, offset,
                                                  data[offset - 2:offset + 1],
                                                  f"{speed:.2f} km/h"))
                    offset += 1
        elif tnde and spfe and offset + 3 <= len(data):
            spd_low = _uint16_le(data, offset)
            offset += 2
            if offset < len(data):
                dirh_spdh = _int8(data, offset)
                spd_high = (dirh_spdh >> 1) & 0x01
                speed = ((spd_high << 14) | spd_low) * 0.01
                tp_fields.append(_make_field("SPD", offset - 2, offset,
                                              data[offset - 2:offset + 1],
                                              f"{speed:.2f} km/h"))
                offset += 1

        if sdfe and offset < len(data):
            direc = _int8(data, offset)
            tp_fields.append(_make_field("DIR", offset, offset, data[offset:offset + 1],
                                         f"{direc}°"))
            offset += 1

        summary = f"Point {i + 1} [RTM={rtm * 0.1}s]"
        fields.append(_make_section(f"Point {i + 1}", offset - 1 - len(data[offset-1:offset]),
                                    offset - 1, tp_fields, summary))
    return fields


def compute_layout(hex_str: str, parsed: dict,
                  parsed_records: list[dict] | None = None) -> list[ByteField]:
    """Build complete byte-level layout tree for an EGTS packet.

    Args:
        hex_str: Hex-encoded packet data
        parsed: Parsed dict from live_packets (may be empty) — metadata only
        parsed_records: Optional list of {subrecords: [{srt, data, raw_bytes}, ...]}
            from the canonical parser. When provided, subrecord field values are
            pulled from the canonical parser (single source of truth), eliminating
            the offset/size bugs in the byte-walking layout functions.

    Returns:
        List of root-level ByteField items (sections + fields)
    """
    if not hex_str or not isinstance(hex_str, str):
        return [ByteField("", "No data", "",
                          0, -1, "", "No packet data", "error", True)]

    try:
        raw = bytes.fromhex(hex_str)
    except (ValueError, AttributeError):
        return [ByteField("", "Invalid hex", "",
                          0, -1, "", "Cannot decode hex string", "error", True)]

    if len(raw) < 13:
        return [ByteField("", "Too short", "",
                          0, len(raw) - 1, raw.hex().upper(),
                          f"Packet too short: {len(raw)} bytes (min 13)", "error", True)]

    root = []

    # --- Transport Header ---
    hdr_fields, hl, pt, fdl, rte = _build_header_layout(raw)
    header_end = hl - 1
    root.append(_make_section(f"Transport Header [0-{header_end}]",
                               0, header_end, hdr_fields,
                               f"({header_end + 1} bytes, RTE={'1' if rte else '0'}, PT={pt})"))

    # --- Service Frame Data ---
    sfrd_offset = hl
    sfrd_end = hl + fdl - 1

    def _record_subs(idx: int) -> list[dict] | None:
        if not parsed_records or idx >= len(parsed_records):
            return None
        return parsed_records[idx].get("subrecords") if isinstance(parsed_records[idx], dict) else None

    if pt == 0:
        # RESPONSE
        sfrd_fields = []
        resp_fields, resp_end = _build_response_sfrd(raw, sfrd_offset)
        sfrd_fields.extend(resp_fields)
        if resp_end + 6 < len(raw):
            rec_fields, rec_start, rec_end = _build_record_layout(raw, resp_end, _record_subs(0))
            sfrd_fields.append(_make_section(f"Record 1 [{rec_start}-{rec_end}]",
                                              rec_start, rec_end, rec_fields))
        root.append(_make_section(f"Service Frame Data (RESPONSE) [{sfrd_offset}-{sfrd_end}]",
                                   sfrd_offset, sfrd_end, sfrd_fields,
                                   f"({fdl} bytes)"))
    elif pt == 2:
        # SIGNED_APPDATA
        sfrd_fields = []
        if sfrd_offset + 2 <= len(raw):
            sigl = _uint16_le(raw, sfrd_offset)
            sfrd_fields.append(_make_field("SIGL", sfrd_offset, sfrd_offset + 1,
                                            raw[sfrd_offset:sfrd_offset + 2], f"{sigl}"))
            sigd_start = sfrd_offset + 2
            sigd_end = sigd_start + sigl - 1
            if sigl > 0 and sigd_end < len(raw):
                sfrd_fields.append(_make_field("SIGD", sigd_start, sigd_end,
                                                raw[sigd_start:sigd_end + 1],
                                                f"({sigl} bytes)"))
            record_offset = sigd_end + 1
            if record_offset <= sfrd_end:
                rec_fields, rec_start, rec_end = _build_record_layout(raw, record_offset, _record_subs(0))
                sfrd_fields.append(_make_section(f"Record 1 [{rec_start}-{rec_end}]",
                                                  rec_start, rec_end, rec_fields))
        root.append(_make_section(f"Service Frame Data (SIGNED) [{sfrd_offset}-{sfrd_end}]",
                                   sfrd_offset, sfrd_end, sfrd_fields,
                                   f"({fdl} bytes)"))
    else:
        # APPDATA — direct records
        sfrd_fields = []
        record_offset = sfrd_offset
        rec_idx = 0
        while record_offset < sfrd_end and record_offset + 4 <= len(raw):
            if record_offset + 2 > len(raw):
                break
            rl_candidate = _uint16_le(raw, record_offset)
            # FIX Б-04: record header is 7 bytes (RL+RN+RFL+SST+RST), not 4.
            if rl_candidate == 0 or record_offset + 7 + rl_candidate > len(raw):
                break
            rec_fields, rec_start, rec_end = _build_record_layout(raw, record_offset, _record_subs(rec_idx))
            rec_idx += 1
            sfrd_fields.append(_make_section(
                f"Record {rec_idx} [{rec_start}-{rec_end}]",
                rec_start, rec_end, rec_fields,
                f"({rec_end - rec_start + 1} bytes)"))
            record_offset = rec_end + 1
            if rec_idx > 100:
                break
        if sfrd_fields:
            root.append(_make_section(
                f"Service Frame Data (APPDATA) [{sfrd_offset}-{sfrd_end}]",
                sfrd_offset, sfrd_end, sfrd_fields,
                f"({fdl} bytes, {rec_idx} record(s))"))
        elif fdl > 0:
            root.append(_make_section(
                f"Service Frame Data [{sfrd_offset}-{sfrd_end}]",
                sfrd_offset, sfrd_end, [],
                f"({fdl} bytes, no records parsed)"))

    # --- CRC-16 ---
    crc_offset = hl + fdl
    if crc_offset + 1 < len(raw):
        crc_in_pkt = _uint16_le(raw, crc_offset)
        sfrd_data = raw[hl:hl + fdl] if fdl <= len(raw) - hl else b""
        computed_crc = _crc16(sfrd_data) if sfrd_data else 0
        crc_ok = crc_in_pkt == computed_crc
        crc_label = f"0x{crc_in_pkt:04X}"
        if crc_ok:
            crc_label += " ✅ OK"
        else:
            crc_label += f" ❌ (expected 0x{computed_crc:04X})"
        root.append(_make_field("SFRCS", crc_offset, crc_offset + 1,
                                 raw[crc_offset:crc_offset + 2],
                                 crc_label, error=not crc_ok))

    return root
