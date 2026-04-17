"""Парсинг заголовка транспортного уровня EGTS (ГОСТ таблица 3).

Формат заголовка (11 байт без маршрутизации, 16 байт с RTE=1):

Offset  Size  Field
  0       1    PRV    — версия протокола
  1       1    SKID   — идентификатор ключа
  2       1    Flags  — PRF|RTE|ENA|ENA|CMP|PR|PR
  3       1    HL     — длина заголовка (11 или 16)
  4       1    HE     — кодирование заголовка
  5       2    FDL    — длина данных уровня поддержки услуг (USHORT LE)
  7       2    PID    — идентификатор пакета (USHORT LE)
  9       1    PT     — тип пакета (0=RESP, 1=APP, 2=SIGNED)
  [10-11]  2    PRA    — адрес peer (если RTE=1)
  [12-13]  2    RCA    — адрес recipient (если RTE=1)
  [14]     1    TTL    — time-to-live (если RTE=1)

Для PT=0 (RESPONSE):
  [HL]     2    RPID   — идентификатор подтверждаемого пакета
  [HL+2]   1    PR     — результат обработки

HCS (CRC-8) находится в последнем байте заголовка: offset = HL-1
"""

import logging

from libs.egts.models import Packet

logger = logging.getLogger(__name__)


def parse_header(data: bytes) -> Packet:
    """Разобрать заголовок EGTS-пакета из байтов.

    Формат заголовка (ГОСТ 33465, таблица 5):
    - Обязательная часть: PRV, SKID, FLAGS, HL, HE, FDL, PID, PT
    - Опциональная часть (RTE=1): PRA, RCA, TTL
    - RESPONSE (PT=0): RPID, PR — после заголовка

    Args:
        data: Байты начиная с заголовка (минимум 11 байт).

    Returns:
        Packet с заполненными полями заголовка.

    Raises:
        ValueError: если данных недостаточно для заголовка.
    """
    if len(data) < 9:
        raise ValueError(f"Недостаточно данных для заголовка: {len(data)} < 9")

    # Обязательные поля (байты 0-9)
    prv = data[0]           # PRV — версия протокола
    skid = data[1]         # SKID — идентификатор ключа шифрования
    flags = data[2]        # FLAGS — флаги (PRF, RTE, ENA, CMP, PR)
    hl = data[3]          # HL — длина заголовка
    he = data[4]          # HE — кодировка заголовка
    int.from_bytes(data[5:7], 'little')  # FDL — длина данных (для нас не важно)
    pid = int.from_bytes(data[7:9], 'little')  # PID — идентификатор пакета
    pt = data[9] if len(data) > 9 else 0  # PT — тип пакета

    # Распаковка флагов (биты: PRF|RTE|ENA(2)|CMP|PR(2))
    prf = bool(flags & 0x80)       # бит 7 — префикс
    rte = bool(flags & 0x40)       # бит 6 — маршрутизация включена
    ena = (flags >> 4) & 0x03      # биты 5-4 — тип шифрования
    cmp_flag = bool(flags & 0x08)  # бит 3 — сжатие
    priority = flags & 0x03        # биты 2-1 — приоритет

    # Опциональные поля маршрутизации (только при RTE=1)
    peer_address = None
    recipient_address = None
    ttl = None

    if rte:
        if len(data) < 15:
            raise ValueError(
                f"RTE=1 но данных недостаточно для PRA/RCA/TTL: {len(data)} < 15"
            )
        peer_address = int.from_bytes(data[10:12], 'little')  # PRA — адрес отправителя
        recipient_address = int.from_bytes(data[12:14], 'little')  # RCA — адрес получателя
        ttl = data[14]  # TTL — время жизни

    # RESPONSE-поля (PT=0) — идут после заголовка, не внутри него
    response_packet_id = None
    processing_result = None
    if pt == 0 and len(data) >= hl + 3:
        response_packet_id = int.from_bytes(data[hl:hl+2], 'little')  # RPID
        processing_result = data[hl+2]  # PR — код результата

    return Packet(
        protocol_version=prv,
        security_key_id=skid,
        prefix=prf,
        routing=rte,
        encryption=ena,
        compressed=cmp_flag,
        priority=priority,
        header_encoding=he,
        packet_id=pid,
        packet_type=pt,
        peer_address=peer_address,
        recipient_address=recipient_address,
        ttl=ttl,
        response_packet_id=response_packet_id,
        processing_result=processing_result,
        header_length=hl,
        raw_bytes=data[:hl],
    )


def build_header(packet: Packet) -> bytes:
    """Собрать заголовок из Packet.

    Вычисляет HL и HCS (CRC-8).
    FDL = 0 (данные добавляются отдельно).
    """
    # Определяем HL
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

    # Собираем заголовок без HCS
    header = bytearray()
    header.append(packet.protocol_version)       # PRV
    header.append(packet.security_key_id)        # SKID
    header.append(flags)                          # Flags
    header.append(hl)                             # HL
    header.append(packet.header_encoding)         # HE
    header.extend((0).to_bytes(2, 'little'))      # FDL = 0 (placeholder)
    header.extend(packet.packet_id.to_bytes(2, 'little'))  # PID
    header.append(packet.packet_type)             # PT

    # Маршрутизация
    if packet.routing:
        if packet.peer_address is not None:
            header.extend(packet.peer_address.to_bytes(2, 'little'))
        else:
            header.extend(b'\x00\x00')
        if packet.recipient_address is not None:
            header.extend(packet.recipient_address.to_bytes(2, 'little'))
        else:
            header.extend(b'\x00\x00')
        header.append(packet.ttl if packet.ttl is not None else 0)

    # HCS = CRC-8 от заголовка до HCS (байты 0..HL-2)
    # HL включает HCS в последний байт
    # Для HL=11: CRC от bytes[0:10], HCS = byte[10]
    from libs.egts._core.crc import crc8
    hcs = crc8(bytes(header))
    header.append(hcs)

    return bytes(header)
