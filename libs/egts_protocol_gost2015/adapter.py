"""Адаптер EGTS-протокола ГОСТ 2015 к IEgtsProtocol

Реализует интерфейс IEgtsProtocol через конкретную реализацию
парсинга/сборки пакетов ГОСТ 33465-2015.

Архитектура:
- gost2015_impl/ — скопированные модули из EGTS_GUI (Packet, Record, Subrecord)
- Этот модуль — маппинг между gost2015_impl моделями и iface моделями
- Ядро OMEGA_EGTS НЕ знает о gost2015_impl — работает только с iface
"""

from libs.egts_protocol_iface import IEgtsProtocol
from libs.egts_protocol_iface.models import (
    Packet as IfacePacket,
    ParseResult,
    Record as IfaceRecord,
    ResponseRecord,
    Subrecord as IfaceSubrecord,
)

from .gost2015_impl.crc import crc8, crc16, verify_crc8, verify_crc16
from .gost2015_impl.packet import Packet as InternalPacket
from .gost2015_impl.record import Record as InternalRecord
from .gost2015_impl.sms import create_sms_pdu, parse_sms_pdu
from .gost2015_impl.subrecord import Subrecord as InternalSubrecord
from .gost2015_impl.types import (
    EGTS_SRT_RECORD_RESPONSE,
    PacketType as InternalPacketType,
    Priority as InternalPriority,
    ServiceType as InternalServiceType,
)


class EgtsProtocol2015(IEgtsProtocol):
    """Реализация EGTS-протокола по ГОСТ 33465-2015.

    Использует внутренние модули gost2015_impl/ (копии из EGTS_GUI)
    для парсинга/сборки, маппит результаты в iface-модели.
    """

    @property
    def version(self) -> str:
        return "2015"

    @property
    def capabilities(self) -> set[str]:
        return {"sms_pdu", "auth", "commands", "ecall", "firmware"}

    # ========================================================================
    # Парсинг
    # ========================================================================

    def parse_packet(self, data: bytes, **kwargs: object) -> ParseResult:
        """Распарсить EGTS-пакет из сырых байтов."""
        if not data:
            return ParseResult(errors=["Пустые данные пакета"], raw_bytes=data)

        errors: list[str] = []
        warnings: list[str] = []

        try:
            internal_packet = InternalPacket.from_bytes(data)
        except ValueError as exc:
            errors.append(f"Ошибка парсинга: {exc}")
            return ParseResult(errors=errors, warnings=warnings, raw_bytes=data)

        # Парсинг записей
        internal_records: list[InternalRecord] = []
        try:
            internal_records = internal_packet.parse_records()
        except ValueError as exc:
            errors.append(f"Ошибка парсинга записей: {exc}")

        # Маппинг в iface-модели
        iface_records = [
            self._map_record_to_iface(rec) for rec in internal_records
        ]

        iface_packet = self._map_packet_to_iface(internal_packet, iface_records)
        # CRC уже проверен в from_bytes, но явно сохраняем статус
        header_len = internal_packet.raw_bytes[3]  # HL — полная длина заголовка
        header_data = data[:header_len - 1]  # Без HCS байта
        hcs_byte = data[header_len - 1]
        iface_packet.crc8_valid = verify_crc8(header_data, hcs_byte)
        iface_packet.crc16_valid = True  # from_bytes бросает при ошибке
        iface_packet.raw_bytes = data

        # Заполняем extra метаданными для ExpectStep/FSM/LogManager
        extra: dict[str, object] = {}
        if iface_packet.records:
            rec = iface_packet.records[0]
            extra["service"] = rec.service_type
            if rec.subrecords:
                extra["subrecord_type"] = rec.subrecords[0].subrecord_type

        return ParseResult(
            packet=iface_packet,
            errors=errors,
            warnings=warnings,
            raw_bytes=data,
            extra=extra,
        )

    def parse_sms_pdu(self, pdu: bytes, **kwargs: object) -> bytes:
        """Извлечь EGTS-пакет из SMS PDU."""
        result = parse_sms_pdu(pdu)
        return bytes(result["user_data"])

    # ========================================================================
    # Сборка
    # ========================================================================

    def build_response(
        self, pid: int, result_code: int, records: list[ResponseRecord] | None = None, **kwargs: object
    ) -> bytes:
        """Собрать RESPONSE-пакет."""
        rpid_val = kwargs.get("rpid", pid)
        rpid: int = rpid_val if isinstance(rpid_val, int) else pid

        internal_records_list: list[InternalRecord] = []

        if records:
            for rr in records:
                # Маппинг subrecords
                internal_subs = [
                    InternalSubrecord(
                        subrecord_type=sr.subrecord_type,
                        data=sr.data,
                        raw_data=sr.raw_data,
                    )
                    for sr in rr.subrecords
                ]

                # Маппинг service: int → ServiceType с fallback
                try:
                    svc_type = InternalServiceType(rr.service)
                except ValueError:
                    # Неизвестный сервис → fallback на AUTH_SERVICE
                    svc_type = InternalServiceType.EGTS_AUTH_SERVICE

                internal_rec = InternalRecord(
                    record_id=rr.rn,
                    service_type=svc_type,
                    subrecords=internal_subs,
                    rsod=rr.rsod,
                )
                internal_records_list.append(internal_rec)

        internal_pkt = InternalPacket(
            packet_id=pid,
            packet_type=InternalPacketType.EGTS_PT_RESPONSE,
            priority=InternalPriority.HIGHEST,
            response_packet_id=rpid,
            processing_result=result_code,
            records=internal_records_list,
        )
        return internal_pkt.to_bytes()

    def build_record_response(self, crn: int, rst: int, **kwargs: object) -> bytes:
        """Собрать RECORD_RESPONSE подзапись.

        Формат: SRT(1) + SRL(2) + CRN(2) + RST(1)
        """
        from .gost2015_impl.types import EGTS_SRT_RECORD_RESPONSE

        crn_bytes = crn.to_bytes(2, "little")
        srd = crn_bytes + bytes([rst])
        return (
            bytes([EGTS_SRT_RECORD_RESPONSE])  # SRT
            + len(srd).to_bytes(2, "little")  # SRL
            + srd  # SRD
        )

    def build_packet(self, packet: IfacePacket, **kwargs: object) -> bytes:
        """Собрать EGTS-пакет из iface-структуры (roundtrip)."""
        internal_pkt = self._map_packet_to_internal(packet)
        return internal_pkt.to_bytes()

    def build_sms_pdu(
        self, egts_packet_bytes: bytes, destination: str, **kwargs: object
    ) -> bytes:
        """Упаковать EGTS-пакет в SMS PDU."""
        params: dict[str, object] = {
            "phone_number": destination,
            "user_data": egts_packet_bytes,
        }
        for key in (
            "smsc_number",
            "message_reference",
            "request_status_report",
            "concatenated",
            "concat_ref",
            "concat_total",
            "concat_seq",
        ):
            if key in kwargs:
                params[key] = kwargs[key]

        return create_sms_pdu(**params)  # type: ignore[arg-type]

    # ========================================================================
    # Валидация
    # ========================================================================

    def validate_crc8(self, header: bytes, expected: int, **kwargs: object) -> bool:
        """Проверить CRC-8 заголовка."""
        return verify_crc8(header, expected)

    def validate_crc16(self, data: bytes, expected: int, **kwargs: object) -> bool:
        """Проверить CRC-16 данных."""
        return verify_crc16(data, expected)

    def calculate_crc8(self, data: bytes, **kwargs: object) -> int:
        """Вычислить CRC-8."""
        return crc8(data)

    def calculate_crc16(self, data: bytes, **kwargs: object) -> int:
        """Вычислить CRC-16."""
        return crc16(data)

    # ========================================================================
    # Мапперы: Internal → Iface
    # ========================================================================

    def _map_packet_to_iface(
        self, internal: InternalPacket, records: list[IfaceRecord]
    ) -> IfacePacket:
        """InternalPacket → IfacePacket."""
        return IfacePacket(
            packet_id=internal.packet_id,
            packet_type=int(internal.packet_type),
            priority=int(internal.priority),
            records=records,
            response_packet_id=internal.response_packet_id,
            processing_result=internal.processing_result,
            sender_address=internal.sender_address,
            receiver_address=internal.receiver_address,
            ttl=internal.ttl,
            skid=internal.skid,
            prf=internal.prf,
            rte=internal.rte,
            ena=internal.ena,
            cmp=internal.cmp,
        )

    def _map_record_to_iface(self, internal: InternalRecord) -> IfaceRecord:
        """InternalRecord → IfaceRecord."""
        iface_subrecords = [
            self._map_subrecord_to_iface(sub) for sub in internal.subrecords
        ]
        return IfaceRecord(
            record_id=internal.record_id,
            service_type=int(internal.service_type),
            subrecords=iface_subrecords,
            object_id=internal.object_id,
            event_id=internal.event_id,
            timestamp=internal.timestamp,
            rst_service_type=int(internal.rst_service_type),
        )

    def _map_subrecord_to_iface(
        self, internal: InternalSubrecord
    ) -> IfaceSubrecord:
        """InternalSubrecord → IfaceSubrecord."""
        return IfaceSubrecord(
            subrecord_type=internal.subrecord_type,
            data=internal.data,
            raw_data=internal.raw_data,
        )

    # ========================================================================
    # Мапперы: Iface → Internal
    # ========================================================================

    def _map_packet_to_internal(self, iface: IfacePacket) -> InternalPacket:
        """IfacePacket → InternalPacket."""
        internal_records = [
            self._map_record_to_internal(rec) for rec in iface.records
        ]
        return InternalPacket(
            packet_id=iface.packet_id,
            packet_type=InternalPacketType(iface.packet_type),
            priority=InternalPriority(iface.priority),
            records=internal_records,
            response_packet_id=iface.response_packet_id,
            processing_result=iface.processing_result,
            sender_address=iface.sender_address,
            receiver_address=iface.receiver_address,
            ttl=iface.ttl,
            skid=iface.skid,
            prf=iface.prf,
            rte=iface.rte,
            ena=iface.ena,
            cmp=iface.cmp,
        )

    def _map_record_to_internal(self, iface: IfaceRecord) -> InternalRecord:
        """IfaceRecord → InternalRecord."""
        internal_subrecords = [
            self._map_subrecord_to_internal(sub) for sub in iface.subrecords
        ]
        # Internal Record требует ServiceType enum, iface использует int
        # Неизвестный service_type — ошибка (ГОСТ 2023 или vendor extension)
        svc_type = InternalServiceType(iface.service_type)
        # rst_service_type=0 означает «не указан» — маппим на AUTH (ближайший аналог)
        rst_type = (
            InternalServiceType(iface.rst_service_type)
            if iface.rst_service_type != 0
            else InternalServiceType.EGTS_AUTH_SERVICE
        )

        return InternalRecord(
            record_id=iface.record_id,
            service_type=svc_type,
            subrecords=internal_subrecords,
            object_id=iface.object_id,
            event_id=iface.event_id,
            timestamp=iface.timestamp,
            rst_service_type=rst_type,
        )

    def _map_subrecord_to_internal(
        self, iface: IfaceSubrecord
    ) -> InternalSubrecord:
        """IfaceSubrecord → InternalSubrecord."""
        return InternalSubrecord(
            subrecord_type=iface.subrecord_type,
            data=iface.data,
            raw_data=iface.raw_data,
        )
