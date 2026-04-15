"""Интерфейс EGTS протокола."""

from typing import Protocol

from libs.egts.models import Packet, ParseResult, ResponseRecord


class IEgtsProtocol(Protocol):
    """Интерфейс реализации EGTS для конкретной версии ГОСТ."""

    def parse_packet(self, data: bytes) -> ParseResult:
        """Разобрать EGTS-пакет из байтов."""
        ...

    def build_packet(self, packet: Packet) -> bytes:
        """Собрать EGTS-пакет в байты."""
        ...

    def build_response(self, pid: int, result_code: int,
                       records: list[ResponseRecord] | None = None) -> bytes:
        """Собрать RESPONSE-пакет."""
        ...

    def build_record_response(self, crn: int, rst: int) -> bytes:
        """Собрать байты подзаписи RECORD_RESPONSE (SRT=0)."""
        ...

    def calculate_crc8(self, data: bytes) -> int:
        """Вычислить CRC-8 заголовка."""
        ...

    def calculate_crc16(self, data: bytes) -> int:
        """Вычислить CRC-16 данных."""
        ...

    def validate_crc8(self, header_data: bytes, expected: int) -> bool:
        """Проверить CRC-8 заголовка."""
        ...

    def validate_crc16(self, body_data: bytes, expected: int) -> bool:
        """Проверить CRC-16 тела."""
        ...

    @property
    def version(self) -> str:
        """Версия ГОСТ (например '2015')."""
        ...

    @property
    def capabilities(self) -> set[str]:
        """Поддерживаемые возможности (например {'auth', 'commands'})."""
        ...
