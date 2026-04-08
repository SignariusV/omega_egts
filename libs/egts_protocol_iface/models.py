"""Модели данных протокола EGTS (контракты)

Dataclass'ы для представления пакетов, записей и подзаписей.
Не содержат методов парсинга/сборки — только структуры данных.
Парсинг реализуется через IEgtsProtocol в конкретной реализации ГОСТ.

extra: dict — для расширений (ГОСТ 2023 и новые версии)
raw_bytes/raw_data — для логирования
parse_error — для диагностики ошибок парсинга
"""

from dataclasses import dataclass, field


@dataclass
class Subrecord:
    """Подзапись уровня поддержки услуг (ППУ)

    Минимальная единица данных — конкретный тип информации
    (команда, телеметрия, результат авторизации и т.д.)

    Attributes:
        subrecord_type: Тип подзаписи (SRT, 1 байт)
        data: Распарсенные данные (dict) или сырые байты
        raw_data: Исходные байты данных (для логирования)
        parse_error: Текст ошибки парсинга (если подзапись не распарсилась)
        extra: Расширения (для новых версий ГОСТ)
    """

    subrecord_type: int
    data: bytes | dict[str, object] | None = None
    raw_data: bytes = field(default_factory=bytes, repr=False)
    parse_error: str | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class Record:
    """Запись уровня поддержки услуг (ППУ)

    Контейнер для подзаписей. Одна запись относится к одному
    сервису (авторизация, команды, eCall, прошивка).

    Attributes:
        record_id: Номер записи (RN, 0-65535)
        service_type: Тип сервиса-отправителя (SST)
        subrecords: Список подзаписей
        first_record: Флаг первой записи (FRF)
        last_record: Флаг последней записи (LRF)
        ongoing_record: Флаг продолжения (ORF)
        object_id: Идентификатор объекта (OID, опционально)
        event_id: Идентификатор события (EVID, опционально)
        timestamp: Время формирования записи (TM, опционально)
        rst_service_type: Тип сервиса-получателя (RST)
        parse_error: Текст ошибки парсинга
        extra: Расширения
        _raw_data: Сырые данные записи (внутреннее поле парсера)
    """

    record_id: int
    service_type: int
    subrecords: list[Subrecord] = field(default_factory=list)

    # Флаги записи (RF)
    first_record: bool = False
    last_record: bool = False
    ongoing_record: bool = False

    # Опциональные поля
    object_id: int | None = None
    event_id: int | None = None
    timestamp: int | None = None

    rst_service_type: int = 0
    parse_error: str | None = None
    extra: dict[str, object] = field(default_factory=dict)

    # Внутреннее поле (не в __init__)
    _raw_data: bytes = field(default_factory=bytes, repr=False, init=False)

    @property
    def rf_flags(self) -> int:
        """Собрать флаги RFL в байт (для сборки пакета).

        Биты: 7=FRF, 6=LRF, 5=ORF
        """
        flags = 0
        if self.first_record:
            flags |= 0x80
        if self.last_record:
            flags |= 0x40
        if self.ongoing_record:
            flags |= 0x20
        return flags


@dataclass
class Packet:
    """Пакет транспортного уровня EGTS

    Верхнеуровневая единица данных. Содержит одну или несколько
    записей сервисного уровня.

    Attributes:
        packet_id: Идентификатор пакета (PID, 0-65535)
        packet_type: Тип пакета (0=RESPONSE, 1=APPDATA, 2=SIGNED_APPDATA)
        priority: Приоритет (0-3)
        records: Список записей сервисного уровня
        response_packet_id: Подтверждаемый пакет (RPID, только для RESPONSE)
        processing_result: Результат обработки (PR, только для RESPONSE)
        sender_address: Адрес отправителя (PRA, опционально)
        receiver_address: Адрес получателя (RCA, опционально)
        ttl: Время жизни (TTL, опционально)
        skid: Идентификатор ключа шифрования (SKID)
        raw_bytes: Исходные байты пакета
        prf: Префикс заголовка
        rte: Требуется маршрутизация
        ena: Шифрование включено
        cmp: Сжатие включено
        crc8_valid: CRC-8 заголовка валиден (None если не проверялся)
        crc16_valid: CRC-16 данных валиден (None если не проверялся)
        extra: Расширения
    """

    packet_id: int
    packet_type: int
    priority: int = 0
    records: list[Record] = field(default_factory=list)

    # RESPONSE-only
    response_packet_id: int | None = None
    processing_result: int | None = None

    # Маршрутизация (опционально)
    sender_address: int | None = None
    receiver_address: int | None = None
    ttl: int | None = None

    # Дополнительные
    skid: int = 0
    raw_bytes: bytes = field(default_factory=bytes, repr=False)

    # Флаги
    prf: bool = False
    rte: bool = False
    ena: bool = False
    cmp: bool = False

    # CRC валидность
    crc8_valid: bool | None = None
    crc16_valid: bool | None = None

    # Расширения
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def pr_flags(self) -> int:
        """Собрать PR флаги в байт (для сборки пакета).

        Биты: 7=PRF, 6=RTE, 5=ENA, 4=CMP, 3-2=PR
        """
        flags = 0
        if self.prf:
            flags |= 0x80
        if self.rte:
            flags |= 0x40
        if self.ena:
            flags |= 0x20
        if self.cmp:
            flags |= 0x10
        flags |= (self.priority & 0x03) << 2
        return flags


@dataclass
class ParseResult:
    """Результат парсинга EGTS-пакета

    Attributes:
        packet: Распарсенный пакет (None если не удалось)
        errors: Список ошибок парсинга
        warnings: Список предупреждений
        raw_bytes: Исходные байты
    """

    packet: Packet | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_bytes: bytes = field(default_factory=bytes, repr=False)

    @property
    def is_success(self) -> bool:
        """Пакет успешно распарсен (packet не None)"""
        return self.packet is not None

    @property
    def is_valid(self) -> bool:
        """Пакет распарсен без ошибок"""
        return self.packet is not None and len(self.errors) == 0

    @property
    def is_partial(self) -> bool:
        """Частичный успех — пакет есть, но были ошибки"""
        return self.packet is not None and len(self.errors) > 0
