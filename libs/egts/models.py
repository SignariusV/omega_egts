"""Модели данных EGTS (общие для всех версий ГОСТ)."""

from dataclasses import dataclass, field


@dataclass
class Packet:
    """Пакет транспортного уровня (ГОСТ 33465 таблица 3)."""
    # Обязательные поля заголовка
    protocol_version: int = 1              # PRV
    security_key_id: int = 0               # SKID
    prefix: bool = False                   # PRF (бит 7 flags)
    routing: bool = False                  # RTE (бит 6) — есть ли PRA/RCA/TTL
    encryption: int = 0                    # ENA (биты 5-4) — зарезервировано
    compressed: bool = False               # CMP (бит 3)
    priority: int = 0                      # PR (биты 2-1): 0=наивысший, 3=низкий
    header_encoding: int = 0               # HE
    packet_id: int = 0                     # PID
    packet_type: int = 0                   # PT: 0=RESPONSE, 1=APPDATA, 2=SIGNED

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
    """Запись уровня поддержки услуг (ГОСТ 33465 таблица 14)."""
    record_id: int = 0                     # RN
    service_type: int = 0                  # SST (Source Service Type)
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
    """Подзапись уровня поддержки услуг (ГОСТ 33465 таблица 15)."""
    subrecord_type: int = 0                # SRT — всегда int
    data: dict[str, object] | bytes = field(default_factory=dict)
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
    rn: int = 0                            # Номер записи
    service: int = 0                       # Тип сервиса
    subrecords: list[Subrecord] = field(default_factory=list)
    rsod: bool = True                      # RSOD — по умолчанию с платформы
