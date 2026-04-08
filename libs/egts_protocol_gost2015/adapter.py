"""Адаптер EGTS-протокола ГОСТ 2015 к IEgtsProtocol

Реализует интерфейс IEgtsProtocol через конкретную реализацию
парсинга/сборки пакетов ГОСТ 33465-2015.

Статус: Заглушка — полная реализация в задачах 2.2–2.4.
"""

from libs.egts_protocol_iface import IEgtsProtocol, Packet, ParseResult


class EgtsProtocol2015(IEgtsProtocol):
    """Реализация EGTS-протокола по ГОСТ 33465-2015.

    Методы пока бросают NotImplementedError — полная реализация
    в задачах 2.2–2.4 (копирование парсера из EGTS_GUI, CRC, SMS).
    """

    @property
    def version(self) -> str:
        return "2015"

    @property
    def capabilities(self) -> set[str]:
        return {"sms_pdu"}

    def parse_packet(self, data: bytes, **kwargs: object) -> ParseResult:
        raise NotImplementedError("parse_packet будет реализован в задаче 2.3")

    def build_response(self, pid: int, result_code: int, **kwargs: object) -> bytes:
        raise NotImplementedError("build_response будет реализован в задаче 2.3")

    def build_record_response(self, crn: int, rst: int, **kwargs: object) -> bytes:
        raise NotImplementedError("build_record_response будет реализован в задаче 2.3")

    def build_packet(self, packet: Packet, **kwargs: object) -> bytes:
        raise NotImplementedError("build_packet будет реализован в задаче 2.3")

    def validate_crc8(
        self, header: bytes, expected: int, **kwargs: object
    ) -> bool:
        raise NotImplementedError("validate_crc8 будет реализован в задаче 2.3")

    def validate_crc16(
        self, data: bytes, expected: int, **kwargs: object
    ) -> bool:
        raise NotImplementedError("validate_crc16 будет реализован в задаче 2.3")

    def calculate_crc8(self, data: bytes, **kwargs: object) -> int:
        raise NotImplementedError("calculate_crc8 будет реализован в задаче 2.3")

    def calculate_crc16(self, data: bytes, **kwargs: object) -> int:
        raise NotImplementedError("calculate_crc16 будет реализован в задаче 2.3")

    def build_sms_pdu(
        self, egts_packet_bytes: bytes, destination: str, **kwargs: object
    ) -> bytes:
        raise NotImplementedError("build_sms_pdu будет реализован в задаче 2.4")

    def parse_sms_pdu(self, pdu: bytes, **kwargs: object) -> bytes:
        raise NotImplementedError("parse_sms_pdu будет реализован в задаче 2.4")
