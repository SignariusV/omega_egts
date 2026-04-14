"""
Запись уровня поддержки услуг EGTS (ГОСТ 33465-2015, раздел 6.6)

Запись состоит из:
- Заголовка (RL, RN, RFL, OID, EVID, TM, SST, RST)
- Данных записи (RD) - одна или несколько подзаписей
"""

from dataclasses import dataclass, field

from .subrecord import Subrecord
from .types import (
    EGTS_RFL_EVFE_MASK,
    EGTS_RFL_OBFE_MASK,
    EGTS_RFL_RPP_MASK,
    EGTS_RFL_RPP_SHIFT,
    EGTS_RFL_RSOD_MASK,
    EGTS_RFL_SSOD_MASK,
    EGTS_RFL_TMFE_MASK,
    MAX_RECORD_SIZE,
    RECORD_EVID_SIZE,
    RECORD_MIN_SIZE,
    RECORD_OID_SIZE,
    RECORD_RFL_SIZE,
    RECORD_RL_SIZE,
    RECORD_RN_SIZE,
    RECORD_RST_SIZE,
    RECORD_SST_SIZE,
    RECORD_TM_SIZE,
    ServiceType,
)


@dataclass
class Record:
    """
    Запись уровня поддержки услуг EGTS

    Attributes:
        record_id: Номер записи (RN, 0-65535)
        service_type: Тип сервиса (SST/RST)
        subrecords: Список подзаписей (RD)
        object_id: Идентификатор объекта (OID, опционально)
        event_id: Идентификатор события (EVID, опционально)
        timestamp: Время формирования записи (TM, опционально)
        ssod: Сервис-отправитель на УСВ (бит 7 RFL, согласно ГОСТ 33465-2015, таблица 14)
        rsod: Сервис-получатель на УСВ (бит 6 RFL, согласно ГОСТ 33465-2015, таблица 14)
        rpp: Приоритет обработки записи (биты 5-3 RFL, 0-7)
    """

    record_id: int
    service_type: ServiceType
    subrecords: list[Subrecord] = field(default_factory=list)

    # Опциональные поля
    object_id: int | None = None
    event_id: int | None = None
    timestamp: int | None = None

    # Поле RST (сервис-получатель) - может отличаться от SST
    rst_service_type: ServiceType = ServiceType.EGTS_AUTH_SERVICE

    # Флаги
    ssod: bool = False  # Source Service On Device
    rsod: bool = False  # Recipient Service On Device
    rpp: int = 0  # Record Processing Priority (0-7)

    # Внутреннее поле для хранения сырых данных
    _raw_data: bytes = field(default_factory=bytes, repr=False, init=False)

    def __post_init__(self) -> None:
        """Валидация после инициализации"""
        if not 0 <= self.rpp <= 7:
            raise ValueError(f"rpp должен быть в диапазоне 0-7, получено {self.rpp}")
        if not 0 <= self.record_id <= 65535:
            raise ValueError(
                f"record_id должен быть в диапазоне 0-65535, получено {self.record_id}"
            )

    def _build_flags(self) -> int:
        """Построение поля флагов RFL

        Согласно ГОСТ 33465-2015, таблица 14:
        - Бит 7: SSOD (Source Service On Device)
        - Бит 6: RSOD (Recipient Service On Device)
        - Биты 5-3: RPP (Record Processing Priority)
        - Бит 2: TMFE (Time Field Exists)
        - Бит 1: EVFE (Event ID Field Exists)
        - Бит 0: OBFE (Object ID Field Exists)
        """
        flags = 0

        # Бит 0: OBFE (Object ID Field Exists)
        if self.object_id is not None:
            flags |= EGTS_RFL_OBFE_MASK

        # Бит 1: EVFE (Event ID Field Exists)
        if self.event_id is not None:
            flags |= EGTS_RFL_EVFE_MASK

        # Бит 2: TMFE (Time Field Exists)
        if self.timestamp is not None:
            flags |= EGTS_RFL_TMFE_MASK

        # Биты 3-5: RPP (Record Processing Priority)
        flags |= (self.rpp & EGTS_RFL_RPP_MASK) << EGTS_RFL_RPP_SHIFT

        # Бит 6: RSOD (Recipient Service On Device)
        if self.rsod:
            flags |= EGTS_RFL_RSOD_MASK

        # Бит 7: SSOD (Source Service On Device)
        if self.ssod:
            flags |= EGTS_RFL_SSOD_MASK

        return flags

    def to_bytes(self) -> bytes:
        """
        Сериализация записи в байты

        Returns:
            bytes: Запись с заголовком и данными
        """
        # Собираем данные подзаписей
        record_data = b""
        for subrecord in self.subrecords:
            record_data += subrecord.to_bytes()

        # Собираем флаги
        rfl = self._build_flags()

        # Собираем заголовок
        header = bytearray()

        # RL (2 байта) - длина данных RD будет известна позже
        # Пока резервируем место
        header.extend(b"\x00\x00")

        # RN (2 байта) - номер записи
        header.extend(self.record_id.to_bytes(2, "little"))

        # RFL (1 байт) - флаги
        header.append(rfl)

        # Опциональные поля
        if self.object_id is not None:
            header.extend(self.object_id.to_bytes(4, "little"))

        if self.event_id is not None:
            header.extend(self.event_id.to_bytes(4, "little"))

        if self.timestamp is not None:
            header.extend(self.timestamp.to_bytes(4, "little"))

        # SST (1 байт) - сервис-отправитель
        header.append(self.service_type)

        # RST (1 байт) - сервис-получатель
        header.append(self.rst_service_type)

        # Обновляем RL (длина данных RD)
        rl = len(record_data)
        header[0:2] = rl.to_bytes(2, "little")

        # Полный пакет: заголовок + данные
        return bytes(header) + record_data

    @classmethod
    def from_bytes(cls, data: bytes) -> "Record":
        """
        Парсинг записи из байтов

        Args:
            data: Байты записи

        Returns:
            Record: Распарсенная запись
        """
        if len(data) < RECORD_MIN_SIZE:
            raise ValueError(f"Слишком маленькая запись: {len(data)} байт (минимум {RECORD_MIN_SIZE})")

        offset = 0

        # RL (2 байта) - длина данных RD
        rl = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2

        # Валидация размера RD (ГОСТ 33465-2015, таблица 14)
        if rl > MAX_RECORD_SIZE:
            raise ValueError(
                f"Размер данных RD превышает максимум: {rl} > {MAX_RECORD_SIZE}"
            )

        # RN (2 байта) - номер записи
        record_id = int.from_bytes(data[offset : offset + 2], "little")
        offset += 2

        # RFL (1 байт) - флаги
        rfl = data[offset]
        offset += 1

        # Разбираем флаги (согласно ГОСТ 33465-2015, таблица 14)
        obfe = bool(rfl & EGTS_RFL_OBFE_MASK)       # Object ID Field Exists (бит 0)
        evfe = bool(rfl & EGTS_RFL_EVFE_MASK)       # Event ID Field Exists (бит 1)
        tmfe = bool(rfl & EGTS_RFL_TMFE_MASK)       # Time Field Exists (бит 2)
        rpp = (rfl >> EGTS_RFL_RPP_SHIFT) & 0x07    # Record Processing Priority (биты 3-5)
        rsod = bool(rfl & EGTS_RFL_RSOD_MASK)       # Recipient Service On Device (бит 6)
        ssod = bool(rfl & EGTS_RFL_SSOD_MASK)       # Source Service On Device (бит 7)

        # Опциональные поля
        object_id = None
        if obfe:
            object_id = int.from_bytes(data[offset : offset + 4], "little")
            offset += 4

        event_id = None
        if evfe:
            event_id = int.from_bytes(data[offset : offset + 4], "little")
            offset += 4

        timestamp = None
        if tmfe:
            timestamp = int.from_bytes(data[offset : offset + 4], "little")
            offset += 4

        # SST (1 байт) - сервис-отправитель
        service_type = data[offset]
        offset += 1

        # RST (1 байт) - сервис-получатель
        rst_service_type = data[offset]
        offset += 1

        # Данные записи (RD) — подзаписи
        record_data = data[offset : offset + rl]

        record = cls(
            record_id=record_id,
            service_type=ServiceType(service_type),
            rst_service_type=ServiceType(rst_service_type),
            object_id=object_id,
            event_id=event_id,
            timestamp=timestamp,
            ssod=ssod,
            rsod=rsod,
            rpp=rpp,
        )

        # Сохраняем сырые данные подзаписей для обратной совместимости
        record._raw_data = record_data

        # Парсим подзаписи сразу — ГОСТ 33465 SRT/SRL/SRD + автоматический парсинг SRD
        from .subrecord import parse_subrecords

        record.subrecords = parse_subrecords(record_data, ServiceType(service_type), parse_srd=True)

        return record

    @property
    def parsed_subrecords(self) -> list[Subrecord]:
        """
        Распарсить подзаписи из данных записи

        Returns:
            List[Subrecord]: Список распарсенных подзаписей
        """
        if not hasattr(self, "_raw_data") or not self._raw_data:
            return self.subrecords

        # Парсинг подзаписей с автоматическим парсингом SRD
        from .subrecord import parse_subrecords

        return parse_subrecords(self._raw_data, self.service_type, parse_srd=True)

    @staticmethod
    def parse_records(data: bytes, service_type: int | None = None) -> list["Record"]:
        """
        Парсинг списка записей из данных ППУ

        Args:
            data: Байты данных ППУ (SFRD)
            service_type: Не используется (SST определяется внутри каждой записи).
                          Оставлен для обратной совместимости.

        Returns:
            list[Record]: Список распарсенных записей
        """
        records = []
        offset = 0

        while offset < len(data):
            # Нужно минимум RL(2) байта
            if offset + RECORD_RL_SIZE > len(data):
                break

            start_offset = offset

            # RL (2 байта) - длина данных RD
            rl = int.from_bytes(data[offset : offset + RECORD_RL_SIZE], "little")
            offset += RECORD_RL_SIZE

            # Валидация размера RD (ГОСТ 33465-2015, таблица 14)
            if rl > MAX_RECORD_SIZE:
                raise ValueError(
                    f"Размер данных RD превышает максимум: {rl} > {MAX_RECORD_SIZE}"
                )

            # RN (2 байта)
            if offset + RECORD_RN_SIZE > len(data):
                break
            offset += RECORD_RN_SIZE

            # RFL (1 байт)
            if offset + RECORD_RFL_SIZE > len(data):
                break
            rfl = data[offset]
            offset += RECORD_RFL_SIZE

            # Определяем размер опциональных полей по флагам RFL
            optional_size = 0
            if rfl & EGTS_RFL_OBFE_MASK:   # OID
                optional_size += RECORD_OID_SIZE
            if rfl & EGTS_RFL_EVFE_MASK:   # EVID
                optional_size += RECORD_EVID_SIZE
            if rfl & EGTS_RFL_TMFE_MASK:   # TM
                optional_size += RECORD_TM_SIZE

            # Полный размер заголовка (без RL): RN(2) + RFL(1) + optional + SST(1) + RST(1)
            header_without_rl = RECORD_RN_SIZE + RECORD_RFL_SIZE + optional_size + RECORD_SST_SIZE + RECORD_RST_SIZE

            # Общий размер записи = RL(2) + header_without_rl + rl
            total_size = RECORD_RL_SIZE + header_without_rl + rl

            if start_offset + total_size > len(data):
                break

            # Парсим запись (включая RL)
            record_data = data[start_offset : start_offset + total_size]
            record = Record.from_bytes(record_data)
            records.append(record)

            offset = start_offset + total_size

        return records
