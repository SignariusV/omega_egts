"""Реализация EGTS-протокола ГОСТ 33465-2015

Публичный API адаптера:
- EgtsProtocol2015 — реализация IEgtsProtocol
- crc8, crc16, verify_crc8, verify_crc16 — CRC функции
"""

from .adapter import EgtsProtocol2015
from .crc import crc8, crc16, verify_crc8, verify_crc16

__all__ = [
    "EgtsProtocol2015",
    "crc8",
    "crc16",
    "verify_crc8",
    "verify_crc16",
]
