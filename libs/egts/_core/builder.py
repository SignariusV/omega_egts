"""Сборка полного EGTS-пакета из модели."""

from libs.egts.models import Packet, Record, Subrecord
from libs.egts._core.crc import crc8, crc16
from libs.egts._core.subrecord_registry import get_parser


def serialize_subrecord(sub: Subrecord) -> bytes:
    """Сериализовать подзапись в байты (SRT + SRL + SRD).

    Если data=dict — используем парсер для сериализации.
    Если data=bytes — используем raw_bytes.
    """
    if isinstance(sub.data, bytes):
        srd = sub.data
    else:
        parser = get_parser(sub.subrecord_type)
        if parser is not None:
            srd = parser.serialize(sub.data)
        elif sub.raw_bytes:
            srd = sub.raw_bytes
        else:
            raise ValueError(
                f"Нет парсера для SRT={sub.subrecord_type} и нет raw_bytes"
            )

    srt = sub.subrecord_type.to_bytes(1, 'little')
    srl = len(srd).to_bytes(2, 'little')
    return srt + srl + srd


def serialize_record(rec: Record) -> bytes:
    """Сериализовать запись в байты.

    Формат (без опциональных полей):
    RL(2) + RN(2) + RFL(1) + SST(1) + RST(1) + [SRD...]

    С опциональными:
    RL(2) + RN(2) + RFL(1) + SST(1) + RST(1)
      + [OID(4) если OBFE] + [EVID(2) если EVFE] + [TM(4) если TMFE]
      + подзаписи...

    Флаги RFL по ГОСТ 33465-2015 таблица 14:
      бит 7: SSOD
      бит 6: RSOD
      биты 5-3: RPP
      бит 2: OBFE (Object ID Flag Extended)
      бит 1: EVFE (Event ID Flag Extended)
      бит 0: TMFE (Time Mark Flag Extended)
    """
    # Сериализуем подзаписи
    subrecords_data = b''
    for sub in rec.subrecords:
        subrecords_data += serialize_subrecord(sub)

    # Флаги RFL
    obfe = rec.object_id is not None
    evfe = rec.event_id is not None
    tmfe = rec.timestamp is not None

    rfl = 0
    if rec.ssod:
        rfl |= 0x80
    if rec.rsod:
        rfl |= 0x40
    rfl |= (rec.rpp & 0x07) << 3
    if obfe:
        rfl |= 0x04
    if evfe:
        rfl |= 0x02
    if tmfe:
        rfl |= 0x01

    # Собираем запись
    parts = bytearray()
    parts.extend(rec.record_id.to_bytes(2, 'little'))   # RN
    parts.append(rfl)                                     # RFL
    parts.append(rec.service_type)                        # SST
    parts.append(rec.recipient_service_type)              # RST

    # Опциональные поля (порядок по ГОСТ)
    if obfe and rec.object_id is not None:
        parts.extend(rec.object_id.to_bytes(4, 'little'))
    if evfe and rec.event_id is not None:
        parts.extend(rec.event_id.to_bytes(2, 'little'))
    if tmfe and rec.timestamp is not None:
        parts.extend(rec.timestamp.to_bytes(4, 'little'))

    # Подзаписи
    parts.extend(subrecords_data)

    # RL = длина RD (payload) — только подзаписи
    rl = len(subrecords_data)
    return rl.to_bytes(2, 'little') + bytes(parts)


def build_full_packet(packet: Packet) -> bytes:
    """Собрать полный EGTS-пакет из модели.

    1. Сериализовать записи → SFRD
    2. Собрать заголовок с правильным FDL
    3. Добавить CRC-16 от SFRD
    4. Пересчитать HCS
    """
    # 1. Сериализуем записи
    records_data = b''
    for rec in packet.records:
        records_data += serialize_record(rec)

    # 2. FDL: для RESPONSE = RPID(2) + PR(1) + записи
    if packet.packet_type == 0:  # RESPONSE
        fdl = 3 + len(records_data)
        sfrd = (packet.response_packet_id or 0).to_bytes(2, 'little')
        sfrd += bytes([packet.processing_result or 0])
        sfrd += records_data
    else:
        fdl = len(records_data)
        sfrd = records_data

    # 3. Собираем заголовок с правильным FDL
    header = _build_header_with_fdl(packet, fdl)

    # 4. Данные = заголовок + SFRD + CRC-16
    crc = crc16(sfrd)
    crc_bytes = crc.to_bytes(2, 'little')

    return header + sfrd + crc_bytes


def _build_header_with_fdl(packet: Packet, fdl: int) -> bytes:
    """Собрать заголовок с заданным FDL и правильным HCS."""
    if packet.routing:
        hl = 15
    else:
        hl = 11

    # Флаги
    flags = 0
    if packet.prefix:
        flags |= 0x80
    if packet.routing:
        flags |= 0x40
    flags |= (packet.encryption & 0x03) << 4
    if packet.compressed:
        flags |= 0x08
    flags |= (packet.priority & 0x03)

    header = bytearray()
    header.append(packet.protocol_version)
    header.append(packet.security_key_id)
    header.append(flags)
    header.append(hl)
    header.append(packet.header_encoding)
    header.extend(fdl.to_bytes(2, 'little'))
    header.extend(packet.packet_id.to_bytes(2, 'little'))
    header.append(packet.packet_type)

    if packet.routing:
        header.extend((packet.peer_address or 0).to_bytes(2, 'little'))
        header.extend((packet.recipient_address or 0).to_bytes(2, 'little'))
        header.append(packet.ttl or 0)

    # HCS
    hcs = crc8(bytes(header))
    header.append(hcs)

    return bytes(header)
