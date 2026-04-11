"""Интерфейс протокола EGTS (уровень абстракции)

Ядро работают с этим интерфейсом, не завися от конкретной
реализации парсинга/сборки EGTS-пакетов.

Для получения экземпляра используйте:
    >>> from libs.egts_protocol_iface import create_protocol
    >>> protocol = create_protocol("2015")
"""

from typing import Protocol, runtime_checkable

from .models import Packet, ParseResult, ResponseRecord
from .types import (
    CRC8_INIT,
    CRC8_POLY,
    CRC16_INIT,
    CRC16_POLY,
    EGTS_PC_DATACRC_ERROR,
    EGTS_PC_HEADERCRC_ERROR,
    EGTS_SL_NOT_AUTH_TO,
    MAX_PACKET_SIZE,
    MAX_RECORD_SIZE,
    MAX_SUBRECORD_SIZE,
    MIN_PACKET_SIZE,
    MIN_RECORD_SIZE,
    MIN_SUBRECORD_SIZE,
    PACKET_HEADER_MIN_SIZE,
    TL_RECONNECT_TO,
    TL_RESEND_ATTEMPTS,
    TL_RESPONSE_TO,
    PacketType,
    RecordStatus,
    ResultCode,
    ServiceType,
    SubrecordType,
)

__all__ = [
    "CRC8_INIT",
    "CRC8_POLY",
    "CRC16_INIT",
    "CRC16_POLY",
    "EGTS_PC_DATACRC_ERROR",
    "EGTS_PC_HEADERCRC_ERROR",
    "EGTS_SL_NOT_AUTH_TO",
    "MAX_PACKET_SIZE",
    "MAX_RECORD_SIZE",
    "MAX_SUBRECORD_SIZE",
    "MIN_PACKET_SIZE",
    "MIN_RECORD_SIZE",
    "MIN_SUBRECORD_SIZE",
    "PACKET_HEADER_MIN_SIZE",
    "TL_RECONNECT_TO",
    "TL_RESEND_ATTEMPTS",
    "TL_RESPONSE_TO",
    "IEgtsProtocol",
    "Packet",
    "PacketType",
    "ParseResult",
    "RecordStatus",
    "ResponseRecord",
    "ResultCode",
    "ServiceType",
    "SubrecordType",
    "create_protocol",
]


@runtime_checkable
class IEgtsProtocol(Protocol):
    """Интерфейс EGTS-протокола для всех версий ГОСТ.

    Конкретная реализация (2015, 2023) должна реализовать
    все методы этого интерфейса.

    Методы принимают **kwargs для расширяемости — новые версии
    ГОСТ могут добавлять дополнительные параметры без изменения
    сигнатуры интерфейса.
    """

    # ----- Парсинг -----

    def parse_packet(self, data: bytes, **kwargs: object) -> ParseResult:
        """Распарсить EGTS-пакет из сырых байтов.

        Args:
            data: Сырые байты пакета.
            **kwargs: Дополнительные параметры (зависят от реализации).

        Returns:
            ParseResult с распарсенным пакетом или ошибками.
        """
        ...

    def parse_sms_pdu(self, pdu: bytes, **kwargs: object) -> bytes:
        """Извлечь EGTS-пакет из SMS PDU.

        Args:
            pdu: Байты SMS PDU.
            **kwargs: Дополнительные параметры.

        Returns:
            Байты EGTS-пакета.
        """
        ...

    # ----- Сборка -----

    def build_response(
        self, pid: int, result_code: int, records: list[ResponseRecord] | None = None, **kwargs: object
    ) -> bytes:
        """Собрать RESPONSE-пакет.

        Args:
            pid: Идентификатор подтверждаемого пакета.
            result_code: Результат обработки.
            records: Записи уровня поддержки услуг (опционально).
                records=None → минимальный RESPONSE (только RPID + PR).
                records=[...] → RESPONSE с записями и подзаписями.
            **kwargs: Дополнительные параметры.

        Returns:
            Готовые байты RESPONSE-пакета.
        """
        ...

    def build_record_response(self, crn: int, rst: int, **kwargs: object) -> bytes:
        """Собрать RECORD_RESPONSE.

        Args:
            crn: Номер подтверждаемой записи.
            rst: Статус обработки записи.
            **kwargs: Дополнительные параметры.

        Returns:
            Готовые байты RECORD_RESPONSE.
        """
        ...

    def build_packet(self, packet: Packet, **kwargs: object) -> bytes:
        """Собрать EGTS-пакет из структуры (roundtrip).

        Args:
            packet: Структура пакета для сборки.
            **kwargs: Дополнительные параметры.

        Returns:
            Готовые байты EGTS-пакета.
        """
        ...

    def build_sms_pdu(
        self, egts_packet_bytes: bytes, destination: str, **kwargs: object
    ) -> bytes:
        """Упаковать EGTS-пакет в SMS PDU.

        Args:
            egts_packet_bytes: Байты EGTS-пакета.
            destination: Номер телефона получателя.
            **kwargs: Дополнительные параметры.

        Returns:
            Байты SMS PDU.
        """
        ...

    # ----- Валидация -----

    def validate_crc8(self, header: bytes, expected: int, **kwargs: object) -> bool:
        """Проверить CRC-8 заголовка.

        Args:
            header: Байты заголовка.
            expected: Ожидаемое значение CRC-8.
            **kwargs: Дополнительные параметры.

        Returns:
            True если CRC-8 корректен.
        """
        ...

    def validate_crc16(self, data: bytes, expected: int, **kwargs: object) -> bool:
        """Проверить CRC-16 данных.

        Args:
            data: Байты данных.
            expected: Ожидаемое значение CRC-16.
            **kwargs: Дополнительные параметры.

        Returns:
            True если CRC-16 корректен.
        """
        ...

    def calculate_crc8(self, data: bytes, **kwargs: object) -> int:
        """Вычислить CRC-8.

        Args:
            data: Данные для расчёта CRC.
            **kwargs: Дополнительные параметры.

        Returns:
            Значение CRC-8.
        """
        ...

    def calculate_crc16(self, data: bytes, **kwargs: object) -> int:
        """Вычислить CRC-16.

        Args:
            data: Данные для расчёта CRC.
            **kwargs: Дополнительные параметры.

        Returns:
            Значение CRC-16.
        """
        ...

    # ----- Метаинформация -----

    @property
    def version(self) -> str:
        """Версия ГОСТ, которую реализует протокол.

        Returns:
            Строка версии, например "2015" или "2023".
        """
        ...

    @property
    def capabilities(self) -> set[str]:
        """Поддерживаемые возможности.

        Returns:
            Множество строк, например: {"sms_pdu", "firmware"}.
        """
        ...


def create_protocol(gost_version: str) -> IEgtsProtocol:
    """Создать экземпляр протокола по версии ГОСТ.

    Args:
        gost_version: Строка версии ГОСТ ("2015", "2023").

    Returns:
        Экземпляр IEgtsProtocol.

    Raises:
        NotImplementedError: Если версия не поддерживается.
    """
    if gost_version == "2015":
        from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015

        return EgtsProtocol2015()

    if gost_version == "2023":
        raise NotImplementedError("ГОСТ 2023 будет реализован в следующей итерации")

    raise ValueError(f"Неподдерживаемая версия ГОСТ: {gost_version}")
