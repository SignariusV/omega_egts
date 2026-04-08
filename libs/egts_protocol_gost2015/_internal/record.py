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
    RECORD_HEADER_SIZE,
    RECORD_MIN_SIZE,
    RECORD_RL_SIZE,
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

        # Данные записи (RD) - подзаписи
        # Примечание: парсинг подзаписей будет реализован отдельно
        # Пока просто сохраняем байты
        record_data = data[offset : offset + rl]

        record = cls(
            record_id=record_id,
            service_type=service_type,
            rst_service_type=rst_service_type,
            object_id=object_id,
            event_id=event_id,
            timestamp=timestamp,
            ssod=ssod,
            rsod=rsod,
            rpp=rpp,
        )

        # Сохраняем сырые данные подзаписей для последующего парсинга
        record._raw_data = record_data

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

        # Парсинг подзаписей будет реализован в Subrecord
        from .subrecord import parse_subrecords

        return parse_subrecords(self._raw_data, self.service_type)

    @staticmethod
    def parse_records(data: bytes, service_type: int) -> list["Record"]:
        """
        Парсинг списка записей из данных ППУ

        Args:
            data: Байты данных ППУ (SFRD)
            service_type: Тип сервиса для всех записей

        Returns:
            list[Record]: Список распарсенных записей
        """
        records = []
        offset = 0

        while offset < len(data):
            if offset + 2 > len(data):
                break  # Недостаточно данных для RL

            # RL (2 байта) - длина RD (данных подзаписей)
            rl = int.from_bytes(data[offset : offset + 2], "little")

            # Минимальная запись: RL(2) + RN(2) + RFL(1) + SST(1) + RST(1) = 7 байт
            # rl - это длина RD, значит полная запись = 2 (RL) + 5 (заголовок) + rl
            if offset + RECORD_RL_SIZE + RECORD_HEADER_SIZE + rl > len(data):
                break  # Недостаточно данных

            # Парсим запись (включая RL)
            record_data = data[offset : offset + RECORD_RL_SIZE + RECORD_HEADER_SIZE + rl]
            record = Record.from_bytes(record_data)
            records.append(record)

            offset += RECORD_RL_SIZE + RECORD_HEADER_SIZE + rl

        return records
