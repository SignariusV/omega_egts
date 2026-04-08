"""
Транспортный пакет EGTS (ГОСТ 33465-2015, раздел 5.6)

Пакет транспортного уровня состоит из:
- Заголовка (PRV, SKID, флаги, HL, HE, FDL, PID, PT, PRA, RCA, TTL, HCS)
- Данных уровня поддержки услуг (SFRD)
- Контрольной суммы данных (SFRCS, CRC-16)
"""

from dataclasses import dataclass, field

from .crc import crc8, crc16
from .record import Record
from .types import (
    EGTS_FLAGS_CMP_MASK,
    EGTS_FLAGS_ENA_MASK,
    EGTS_FLAGS_PR_MASK,
    EGTS_FLAGS_PR_SHIFT,
    EGTS_FLAGS_PRF_MASK,
    EGTS_FLAGS_RTE_MASK,
    EGTS_PRV_VERSION,
    EGTS_RFL_EVFE_MASK,
    EGTS_RFL_OBFE_MASK,
    EGTS_RFL_TMFE_MASK,
    MAX_RECORD_SIZE,
    PACKET_FDL_OFFSET,
    PACKET_FDL_SIZE,
    PACKET_FLAGS_SIZE,
    PACKET_HCS_SIZE,
    PACKET_HE_SIZE,
    PACKET_HEADER_MIN_SIZE,
    PACKET_HEADER_WITH_ROUTING_SIZE,
    PACKET_HL_OFFSET,
    PACKET_HL_SIZE,
    PACKET_PID_SIZE,
    PACKET_PRA_SIZE,
    PACKET_PRV_SIZE,
    PACKET_PT_SIZE,
    PACKET_RCA_SIZE,
    PACKET_RESPONSE_HEADER_SIZE,
    PACKET_SFRCS_SIZE,
    PACKET_SKID_SIZE,
    PACKET_TTL_SIZE,
    RECORD_EVID_SIZE,
    RECORD_HEADER_SIZE,
    RECORD_OID_SIZE,
    RECORD_RL_SIZE,
    RECORD_RN_SIZE,
    RECORD_TM_SIZE,
    PacketType,
    Priority,
)


@dataclass
class Packet:
    """
    Пакет транспортного уровня EGTS

    Attributes:
        packet_id: Идентификатор пакета (PID, 0-65535)
        packet_type: Тип пакета (PT): 0=RESPONSE, 1=APPDATA, 2=SIGNED_APPDATA
        priority: Приоритет пакета (PR, 2 бита)
        records: Список записей уровня ППУ
        response_packet_id: Идентификатор подтверждаемого пакета (RPID, только для RESPONSE)
        processing_result: Результат обработки (PR, только для RESPONSE)
        sender_address: Адрес отправителя (PRA, опционально)
        receiver_address: Адрес получателя (RCA, опционально)
        ttl: Время жизни (TTL, опционально)
        skid: Идентификатор ключа шифрования (SKID)
        raw_bytes: Исходные байты пакета (для парсинга)
    """

    packet_id: int
    packet_type: PacketType
    priority: Priority = Priority.LOW
    records: list = field(default_factory=list)  # List[Record]

    # Поля для RESPONSE пакетов (PT=0)
    response_packet_id: int | None = None  # RPID
    processing_result: int | None = None   # PR (результат обработки)

    # Опциональные поля маршрутизации
    sender_address: int | None = None
    receiver_address: int | None = None
    ttl: int | None = None

    # Дополнительные поля
    skid: int = 0
    raw_bytes: bytes = field(default_factory=bytes, repr=False)

    # Флаги из заголовка
    prf: bool = False  # Префикс (должен быть 0 для версии 1)
    rte: bool = False  # Маршрутизация
    ena: bool = False  # Шифрование
    cmp: bool = False  # Сжатие

    def __post_init__(self):
        """Валидация после инициализации"""
        # Проверка версии протокола
        if not hasattr(self, "_skip_validation"):
            if not (0 <= self.packet_id <= 65535):
                raise ValueError(f"Неверный идентификатор пакета: {self.packet_id} (0-65535)")

            if not (0 <= self.packet_type <= 2):
                raise ValueError(f"Неверный тип пакета: {self.packet_type} (0-2)")

        # Определяем необходимость маршрутизации
        if (
            self.sender_address is not None
            or self.receiver_address is not None
            or self.ttl is not None
        ):
            self.rte = True
        else:
            self.rte = False

    def to_bytes(self) -> bytes:
        """
        Сериализация пакета в байты

        Returns:
            bytes: Полный пакет с CRC
        """
        # Собираем данные ППУ
        ppu_data = b""

        # Для RESPONSE пакетов (PT=0) добавляем RPID и PR в начало ППУ
        # Согласно ГОСТ 33465-2015, таблица 6
        if self.packet_type == PacketType.EGTS_PT_RESPONSE:
            if self.response_packet_id is not None and self.processing_result is not None:
                ppu_data += self.response_packet_id.to_bytes(PACKET_PID_SIZE, "little")
                ppu_data += bytes([self.processing_result])

        # Сериализуем записи через метод to_bytes()
        for record in self.records:
            ppu_data += record.to_bytes()

        # Определяем длину заголовка
        # Базовый: PRV(1) + SKID(1) + флаги(1) + HL(1) + HE(1) + FDL(2) + PID(2) + PT(1) + HCS(1) = 11
        # С маршрутизацией: + PRA(2) + RCA(2) + TTL(1) = +5 → 16
        header_length = PACKET_HEADER_MIN_SIZE
        if self.rte:
            header_length = PACKET_HEADER_WITH_ROUTING_SIZE

        # Флаги: PRF(бит7) + RTE(бит6) + ENA(бит5) + CMP(бит4) + PR(бит3-2) + зарезервировано(бит1-0)
        flags = 0
        if self.prf:
            flags |= EGTS_FLAGS_PRF_MASK
        if self.rte:
            flags |= EGTS_FLAGS_RTE_MASK
        if self.ena:
            flags |= EGTS_FLAGS_ENA_MASK
        if self.cmp:
            flags |= EGTS_FLAGS_CMP_MASK
        flags |= (self.priority & 0x03) << EGTS_FLAGS_PR_SHIFT

        # Собираем заголовок (без HCS)
        header = bytearray()
        header.append(EGTS_PRV_VERSION)  # PRV - версия протокола
        header.append(self.skid)  # SKID
        header.append(flags)  # Флаги
        header.append(header_length)  # HL - длина заголовка
        header.append(0x00)  # HE - зарезервировано
        header.extend(len(ppu_data).to_bytes(PACKET_FDL_SIZE, "little"))  # FDL - длина данных
        header.extend(self.packet_id.to_bytes(PACKET_PID_SIZE, "little"))  # PID
        header.append(self.packet_type)  # PT

        # Поля маршрутизации (если нужны)
        if self.rte:
            header.extend((self.sender_address or 0).to_bytes(PACKET_PRA_SIZE, "little"))  # PRA
            header.extend((self.receiver_address or 0).to_bytes(PACKET_RCA_SIZE, "little"))  # RCA
            header.append(self.ttl or 0)  # TTL

        # Считаем CRC-8 заголовка
        header_crc = crc8(header)
        header.append(header_crc)  # HCS

        # Считаем CRC-16 данных
        data_crc = crc16(ppu_data)

        # Полный пакет
        packet_bytes = bytes(header) + ppu_data + data_crc.to_bytes(PACKET_SFRCS_SIZE, "little")

        # Сохраняем байты для последующего использования
        self.raw_bytes = packet_bytes

        return packet_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> "Packet":
        """
        Парсинг пакета из байтов

        Args:
            data: Байты пакета

        Returns:
            Packet: Распарсенный пакет

        Raises:
            ValueError: Если CRC-8 или CRC-16 не совпадают
        """
        if len(data) < PACKET_HEADER_MIN_SIZE:
            raise ValueError(f"Слишком маленький пакет: {len(data)} байт (минимум {PACKET_HEADER_MIN_SIZE})")

        # Парсим заголовок
        offset = 0

        # PRV (1 байт) - версия протокола (должна быть 0x01)
        prv = data[offset]
        if prv != EGTS_PRV_VERSION:
            raise ValueError(f"Неверная версия протокола: {prv} (ожидалась {EGTS_PRV_VERSION:#x})")
        offset += PACKET_PRV_SIZE

        skid = data[offset]
        offset += PACKET_SKID_SIZE

        flags = data[offset]
        offset += PACKET_FLAGS_SIZE

        # Разбираем флаги
        prf = bool(flags & EGTS_FLAGS_PRF_MASK)
        rte = bool(flags & EGTS_FLAGS_RTE_MASK)
        ena = bool(flags & EGTS_FLAGS_ENA_MASK)
        cmp = bool(flags & EGTS_FLAGS_CMP_MASK)
        priority = (flags & EGTS_FLAGS_PR_MASK) >> EGTS_FLAGS_PR_SHIFT

        hl = data[offset]
        offset += PACKET_HL_SIZE

        # HE (1 байт) - зарезервировано (пропускаем)
        offset += PACKET_HE_SIZE

        fdl = int.from_bytes(data[offset : offset + PACKET_FDL_SIZE], "little")
        offset += PACKET_FDL_SIZE

        packet_id = int.from_bytes(data[offset : offset + PACKET_PID_SIZE], "little")
        offset += PACKET_PID_SIZE

        packet_type = data[offset]
        offset += PACKET_PT_SIZE

        # Поля маршрутизации
        sender_address = None
        receiver_address = None
        ttl = None

        if rte:
            sender_address = int.from_bytes(data[offset : offset + PACKET_PRA_SIZE], "little")
            offset += PACKET_PRA_SIZE

            receiver_address = int.from_bytes(data[offset : offset + PACKET_RCA_SIZE], "little")
            offset += PACKET_RCA_SIZE

            ttl = data[offset]
            offset += PACKET_TTL_SIZE

        # HCS (CRC-8 заголовка)
        hcs = data[offset]
        offset += PACKET_HCS_SIZE

        # Проверяем CRC-8 заголовка
        header_for_crc = data[: hl - PACKET_HCS_SIZE]  # Все байты заголовка кроме HCS
        calculated_hcs = crc8(header_for_crc)
        if calculated_hcs != hcs:
            raise ValueError(
                f"CRC-8 заголовка не совпадает: ожидался {hcs}, вычислен {calculated_hcs}"
            )

        # Данные ППУ (SFRD)
        ppu_data = data[offset : offset + fdl]
        offset += fdl

        # CRC-16 данных (SFRCS)
        if len(data) < offset + PACKET_SFRCS_SIZE:
            raise ValueError("Недостаточно данных для CRC-16")

        sfrcs = int.from_bytes(data[offset : offset + PACKET_SFRCS_SIZE], "little")

        # Проверяем CRC-16 данных
        calculated_sfrcs = crc16(ppu_data)
        if calculated_sfrcs != sfrcs:
            raise ValueError(
                f"CRC-16 данных не совпадает: ожидался {sfrcs}, вычислен {calculated_sfrcs}"
            )

        # Для RESPONSE пакетов (PT=0) парсим RPID и PR из ППУ
        # Согласно ГОСТ 33465-2015, таблица 6
        response_packet_id = None
        processing_result = None

        if packet_type == PacketType.EGTS_PT_RESPONSE:
            if len(ppu_data) >= PACKET_RESPONSE_HEADER_SIZE:
                response_packet_id = int.from_bytes(ppu_data[0:PACKET_PID_SIZE], "little")
                processing_result = ppu_data[PACKET_PID_SIZE]

        # Создаем пакет
        packet = cls(
            packet_id=packet_id,
            packet_type=packet_type,
            priority=priority,
            skid=skid,
            sender_address=sender_address,
            receiver_address=receiver_address,
            ttl=ttl,
            prf=prf,
            rte=rte,
            ena=ena,
            cmp=cmp,
            raw_bytes=data,
            response_packet_id=response_packet_id,
            processing_result=processing_result,
        )

        # Примечание: records будут распарсены отдельно через Record.from_bytes()
        # Здесь мы только извлекаем байты ППУ

        return packet

    @property
    def ppu_data(self) -> bytes:
        """
        Данные уровня поддержки услуг (SFRD)

        Returns:
            bytes: Байты ППУ (без заголовка и CRC)
        """
        if self.raw_bytes:
            # Извлекаем из распарсенного пакета
            hl = self.raw_bytes[PACKET_HL_OFFSET]  # HL поле
            fdl = int.from_bytes(
                self.raw_bytes[PACKET_FDL_OFFSET : PACKET_FDL_OFFSET + PACKET_FDL_SIZE],
                "little"
            )  # FDL поле
            return self.raw_bytes[hl : hl + fdl]
        return b""

    @property
    def records_data(self) -> bytes:
        """
        Данные записей из ППУ (без RPID и PR для RESPONSE пакетов)

        Returns:
            bytes: Байты записей
        """
        ppu_data = self.ppu_data

        # Для RESPONSE пакетов пропускаем RPID (2 байта) и PR (1 байт)
        if self.packet_type == PacketType.EGTS_PT_RESPONSE:
            return ppu_data[PACKET_RESPONSE_HEADER_SIZE:]

        # Для остальных типов возвращаем всё ППУ
        return ppu_data

    def parse_records(self) -> list["Record"]:
        """
        Парсинг записей из данных ППУ

        Returns:
            list[Record]: Список распарсенных записей
        """
        records = []
        data = self.records_data
        offset = 0

        while offset < len(data):
            # Сначала читаем RL чтобы определить размер записи
            if offset + RECORD_RL_SIZE > len(data):
                break  # Недостаточно данных для RL

            rl = int.from_bytes(data[offset : offset + RECORD_RL_SIZE], "little")

            # Валидация размера записи (Раздел 6.6.2 ГОСТ)
            if rl > MAX_RECORD_SIZE:
                raise ValueError(f"Размер записи превышает максимум: {rl} > {MAX_RECORD_SIZE}")

            rfl = data[offset + RECORD_RL_SIZE + RECORD_RN_SIZE]  # RL(2) + RN(2) = 4

            # Размер записи: RL_field(2) + RN(2) + RFL(1) + SST(1) + RST(1) + RL(данные)
            # = RECORD_RL_SIZE + RECORD_HEADER_SIZE + rl
            record_size = RECORD_RL_SIZE + RECORD_HEADER_SIZE + rl  # Полный размер записи

            # Учитываем опциональные поля
            if rfl & EGTS_RFL_OBFE_MASK:  # OBFE
                record_size += RECORD_OID_SIZE
            if rfl & EGTS_RFL_EVFE_MASK:  # EVFE
                record_size += RECORD_EVID_SIZE
            if rfl & EGTS_RFL_TMFE_MASK:  # TMFE
                record_size += RECORD_TM_SIZE

            # Проверка что достаточно данных
            if offset + record_size > len(data):
                raise ValueError(f"Недостаточно данных для записи: offset={offset}, record_size={record_size}, len(data)={len(data)}")

            # Вырезаем данные одной записи
            record_data = data[offset : offset + record_size]
            record = Record.from_bytes(record_data)
            records.append(record)

            # Переход к следующей записи
            offset += record_size

        return records
