"""CRC-8 и CRC-16 функции для протокола EGTS (ГОСТ 33465-2015)

Чистая реализация на Python — без внешних зависимостей.
CRC-8: полином 0x31, init 0xFF (Приложение Д)
CRC-16 CCITT: полином 0x1021, init 0xFFFF
"""

from .types import CRC8_INIT, CRC8_POLY, CRC16_INIT, CRC16_POLY

# Маска для 8-битного CRC (полином без старшего бита)
_CRC8_MASK = 0xFF
_CRC8_POLY_MASK = CRC8_POLY & _CRC8_MASK  # 0x31

# Маска для 16-битного CRC (полином без старшего бита)
_CRC16_MASK = 0xFFFF
_CRC16_POLY_MASK = CRC16_POLY & _CRC16_MASK  # 0x1021


def crc8(data: bytes) -> int:
    """Вычисление CRC-8 для заголовка пакета.

    Полином: 0x31 (x^8 + x^5 + x^4 + 1)
    Инициализация: 0xFF

    Args:
        data: Входные данные.

    Returns:
        Вычисленное значение CRC-8 (0-255).
    """
    crc = CRC8_INIT
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ _CRC8_POLY_MASK) & _CRC8_MASK
            else:
                crc = (crc << 1) & _CRC8_MASK
    return crc


def crc16(data: bytes) -> int:
    """Вычисление CRC-16 для данных пакета.

    Полином: 0x1021 (CCITT)
    Инициализация: 0xFFFF

    Args:
        data: Входные данные.

    Returns:
        Вычисленное значение CRC-16 (0-65535).
    """
    crc = CRC16_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ _CRC16_POLY_MASK) & _CRC16_MASK
            else:
                crc = (crc << 1) & _CRC16_MASK
    return crc


def verify_crc8(data: bytes, expected_crc: int) -> bool:
    """Проверка CRC-8.

    Args:
        data: Данные для проверки.
        expected_crc: Ожидаемое значение CRC.

    Returns:
        True если CRC совпадает.
    """
    return crc8(data) == expected_crc


def verify_crc16(data: bytes, expected_crc: int) -> bool:
    """Проверка CRC-16.

    Args:
        data: Данные для проверки.
        expected_crc: Ожидаемое значение CRC.

    Returns:
        True если CRC совпадает.
    """
    return crc16(data) == expected_crc
