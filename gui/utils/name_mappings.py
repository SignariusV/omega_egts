"""Human-readable name mappings for EGTS protocol fields."""

from libs.egts.types import (
    PacketType, ServiceType, SubrecordType, ResultCode,
    CommandType, ConfirmationType, ActionType, Charset,
    COMMAND_CODES,
)

# Priority descriptions (ГОСТ таблица 3, биты 2-1 PR)
PRIORITY_NAMES = {
    0: "Highest (наивысший)",
    1: "High (высокий)",
    2: "Medium (средний)",
    3: "Low (низкий)",
}

# Field label mapping: dataclass field name -> human-readable label
FIELD_LABELS: dict[str, str] = {
    "packet_id": "Packet ID (PID)",
    "packet_type": "Packet Type (PT)",
    "protocol_version": "Protocol Version (PRV)",
    "security_key_id": "Security Key ID (SKID)",
    "header_length": "Header Length (HL)",
    "prefix": "Prefix (PRF)",
    "routing": "Routing (RTE)",
    "encryption": "Encryption (ENA)",
    "compressed": "Compressed (CMP)",
    "priority": "Priority (PR)",
    "header_encoding": "Header Encoding (HE)",
    "peer_address": "Peer Address (PRA)",
    "recipient_address": "Recipient Address (RCA)",
    "ttl": "Time To Live (TTL)",
    "response_packet_id": "Response PID (RPID)",
    "processing_result": "Processing Result (PR)",
    "signature_data": "Signature Data (SIGD)",
    "raw_bytes": "Raw Bytes",
    "records": "Records",
    "record_id": "Record Number (RN)",
    "service_type": "Service Type (SST)",
    "recipient_service_type": "Recipient Service (RST)",
    "object_id": "Object ID (OID)",
    "event_id": "Event ID (EVID)",
    "timestamp": "Timestamp (TM)",
    "ssod": "Service Source On Device (SSOD)",
    "rsod": "Service Recipient On Device (RSOD)",
    "rpp": "Record Processing Priority (RPP)",
    "subrecord_type": "Subrecord Type (SRT)",
    "data": "Data",
    "parse_error": "Parse Error",
    "records_count": "Records Count",
    "service": "Service",
}


def get_service_name(service_type: int) -> str:
    """Get human-readable service name from int value."""
    try:
        return ServiceType(service_type).name
    except ValueError:
        return f"Unknown ({service_type})"


def format_service(service_type: int) -> str:
    """Format service as 'AUTH (1)' or 'Unknown (99)'."""
    try:
        srv = ServiceType(service_type)
        return f"{srv.name} ({service_type})"
    except ValueError:
        return f"Unknown Service ({service_type})"


def get_packet_type_name(pt: int) -> str:
    """Get human-readable packet type name."""
    try:
        return PacketType(pt).name
    except ValueError:
        return f"Unknown ({pt})"


def format_packet_type(pt: int) -> str:
    """Format packet type as 'APPDATA (1)' or 'Unknown (99)'."""
    try:
        return f"{PacketType(pt).name} ({pt})"
    except ValueError:
        return f"Unknown ({pt})"


def get_subrecord_type_name(srt: int) -> str:
    """Get human-readable subrecord type name."""
    try:
        return SubrecordType(srt).name
    except ValueError:
        return f"SRT_{srt}"


def format_subrecord_type(srt: int) -> str:
    """Format subrecord type as 'TERM_IDENTITY (1)' or 'SRT_99 (99)'."""
    try:
        return f"{SubrecordType(srt).name} ({srt})"
    except ValueError:
        return f"SRT_{srt} ({srt})"


def format_result_code(rc: int) -> str:
    """Format result code as 'EGTS_PC_OK (0)' or 'Unknown (255)'."""
    try:
        return f"{ResultCode(rc).name} ({rc})"
    except ValueError:
        return f"ResultCode ({rc})"


def format_priority(pr: int) -> str:
    """Format priority value with description."""
    desc = PRIORITY_NAMES.get(pr, f"Unknown ({pr})")
    return f"{pr} — {desc}" if pr in PRIORITY_NAMES else desc


def format_bool(value: bool | int | str) -> str:
    """Format boolean-like value as Yes/No."""
    if isinstance(value, str):
        return value
    return "Yes" if value else "No"


def format_command_code(code: int) -> str:
    """Format command code as 'EGTS_GPRS_APN (0x0101)'."""
    name = COMMAND_CODES.get(code)
    if name:
        return f"{name} (0x{code:04X})"
    return f"0x{code:04X}"


def format_command_type(ct: int) -> str:
    """Format command type as 'COM (0x5)'."""
    try:
        return f"{CommandType(ct).name} ({hex(ct)})"
    except ValueError:
        return f"CT_{ct} ({hex(ct)})"


def format_confirmation_type(cct: int) -> str:
    """Format confirmation type as 'OK (0x0)'."""
    try:
        return f"{ConfirmationType(cct).name} ({hex(cct)})"
    except ValueError:
        return f"CCT_{cct} ({hex(cct)})"


def format_action_type(act: int) -> str:
    """Format action type as 'SET (0x2)'."""
    try:
        return f"{ActionType(act).name} ({hex(act)})"
    except ValueError:
        return f"ACT_{act} ({hex(act)})"


def format_charset(chs: int) -> str:
    """Format charset as 'CP1251 (0)'."""
    try:
        return f"{Charset(chs).name} ({chs})"
    except ValueError:
        return f"CHS_{chs} ({chs})"


def get_field_label(key: str) -> str:
    """Get human-readable label for a dataclass field name."""
    return FIELD_LABELS.get(key, key)


def format_value(key: str | None, value: object) -> str:
    """Format a field value using type-specific human-readable formatting."""
    if value is None:
        return "—"

    if isinstance(value, bool):
        return format_bool(value)

    if isinstance(value, bytes):
        if len(value) > 32:
            return f"bytes ({len(value)} bytes)"
        return value.hex() if value else "(empty)"

    if isinstance(value, int):
        if key is None:
            return str(value)
        key_lower = key.lower()

        if "service_type" in key_lower or key_lower == "service":
            return format_service(value)
        if "packet_type" in key_lower:
            return format_packet_type(value)
        if "subrecord_type" in key_lower:
            return format_subrecord_type(value)
        if "result_code" in key_lower or key_lower == "processing_result":
            return format_result_code(value)
        if "priority" in key_lower:
            return format_priority(value)
        if "command_code" in key_lower or key_lower in ("ccd", "code"):
            return format_command_code(value)
        if "ct" == key_lower:
            return format_command_type(value)
        if "cct" == key_lower:
            return format_confirmation_type(value)
        if "act" in key_lower:
            return format_action_type(value)
        if "chs" == key_lower:
            return format_charset(value)

    return str(value)


def format_direction(direction: str) -> str:
    """Format direction as human-readable."""
    if direction == "rx":
        return "Received (rx)"
    if direction == "tx":
        return "Transmitted (tx)"
    return direction


def format_channel(channel: str) -> str:
    """Format channel as human-readable."""
    if channel == "tcp":
        return "TCP"
    if channel == "sms":
        return "SMS"
    return channel


def format_crc_status(crc: str) -> str:
    """Format CRC status with description."""
    if crc == "OK":
        return "Valid"
    if crc == "FAIL":
        return "Invalid"
    return crc


def format_duplicate(dup: str) -> str:
    """Format duplicate status."""
    if dup == "Yes":
        return "Duplicate"
    if dup == "No":
        return "Original"
    return dup
