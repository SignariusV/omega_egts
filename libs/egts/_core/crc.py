"""CRC-8 и CRC-16 для EGTS (ГОСТ 33465).

CRC-8: полином 0x31, init 0xFF (Приложение Д)
CRC-16 CCITT: полином 0x1021, init 0xFFFF
"""

# CRC-8 параметры
_CRC8_POLY = 0x31
_CRC8_INIT = 0xFF
_CRC8_MASK = 0xFF

# CRC-16 параметры
_CRC16_POLY = 0x1021
_CRC16_INIT = 0xFFFF
_CRC16_MASK = 0xFFFF


def crc8(data: bytes) -> int:
    """Вычисление CRC-8 для заголовка пакета.

    Полином: x^8 + x^5 + x^4 + 1 (0x31)
    Инициализация: 0xFF
    """
    crc = _CRC8_INIT
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ _CRC8_POLY) & _CRC8_MASK
            else:
                crc = (crc << 1) & _CRC8_MASK
    return crc


def crc16(data: bytes) -> int:
    """Вычисление CRC-16 для данных пакета.

    Полином: 0x1021 (CCITT)
    Инициализация: 0xFFFF
    """
    crc = _CRC16_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ _CRC16_POLY) & _CRC16_MASK
            else:
                crc = (crc << 1) & _CRC16_MASK
    return crc
