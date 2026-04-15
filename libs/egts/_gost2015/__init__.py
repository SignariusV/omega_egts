"""Gost2015Protocol — полная реализация EGTS ГОСТ 2015."""

# Импорт регистрирует все парсеры
import libs.egts._gost2015.subrecords  # noqa: F401

from libs.egts.models import Packet, Record, Subrecord, ParseResult, ResponseRecord
from libs.egts.protocol import IEgtsProtocol
from libs.egts.registry import register_version
from libs.egts._core.crc import crc8, crc16
from libs.egts._core.subrecord_registry import get_parser
from libs.egts._core.builder import serialize_subrecord, serialize_record, build_full_packet


class Gost2015Protocol(IEgtsProtocol):
    """Реализация EGTS по ГОСТ 33465-2015."""

    version = "2015"
    capabilities = {"auth", "commands", "ecall", "firmware"}

    def parse_packet(self, data: bytes) -> ParseResult:
        """Разобрать EGTS-пакет из байтов."""
        errors: list[str] = []
        warnings: list[str] = []

        try:
            # Минимальная длина: 11 байт заголовок + 2 CRC-16
            if len(data) < 13:
                return ParseResult(
                    packet=None,
                    errors=[f"Недостаточно данных: {len(data)} < 13"],
                )

            # 1. Разбор заголовка
            hl = data[3]
            if hl not in (11, 15):
                return ParseResult(
                    packet=None,
                    errors=[f"Неверная длина заголовка: {hl}"],
                )

            if len(data) < hl + 2:  # заголовок + CRC-16
                return ParseResult(
                    packet=None,
                    errors=["Недостаточно данных для CRC-16"],
                )

            # 2. Проверка CRC-8 заголовка
            hcs_in_packet = data[hl - 1]
            hcs_computed = crc8(data[:hl - 1])
            if hcs_computed != hcs_in_packet:
                return ParseResult(
                    packet=None,
                    errors=[
                        f"CRC-8 заголовка не совпадает: "
                        f"ожидался {hcs_in_packet}, вычислен {hcs_computed}"
                    ],
                )

            # 3. Извлечение FDL
            fdl = int.from_bytes(data[5:7], 'little')

            # 4. Проверка длины данных
            if len(data) < hl + fdl + 2:
                return ParseResult(
                    packet=None,
                    errors=[f"Недостаточно данных: нужно {hl + fdl + 2}, есть {len(data)}"],
                )

            # 5. Проверка CRC-16
            sfrd = data[hl:hl + fdl]
            crc_in_packet = int.from_bytes(data[hl + fdl:hl + fdl + 2], 'little')
            crc_computed = crc16(sfrd)
            if crc_computed != crc_in_packet:
                return ParseResult(
                    packet=None,
                    errors=[
                        f"CRC-16 данных не совпадает: "
                        f"ожидался {crc_in_packet}, вычислен {crc_computed}"
                    ],
                )

            # 6. Парсинг заголовка
            packet = self._parse_header(data)

            # 7. Для RESPONSE (PT=0) — RPID и PR после заголовка
            if packet.packet_type == 0:
                rpid = int.from_bytes(data[hl:hl+2], 'little')
                pr = data[hl+2]
                packet.response_packet_id = rpid
                packet.processing_result = pr
                # Для RESPONSE оставшиеся байты после RPID+PR — это записи
                remaining_fdl = fdl - 3  # RPID(2) + PR(1)
                if remaining_fdl > 0:
                    self._parse_records(packet, data[hl+3:hl+3+remaining_fdl], warnings)
            else:
                # APPDATA — разбираем записи из всего SFRD
                self._parse_records(packet, sfrd, warnings)

            packet.raw_bytes = data
            return ParseResult(packet=packet, errors=errors, warnings=warnings)

        except Exception as e:
            return ParseResult(packet=None, errors=[f"Ошибка парсинга: {e}"])

    def build_packet(self, packet: Packet) -> bytes:
        """Собрать EGTS-пакет из модели."""
        return build_full_packet(packet)

    def build_response(self, pid: int, result_code: int,
                       records: list[ResponseRecord] | None = None) -> bytes:
        """Собрать RESPONSE-пакет."""
        if records is None:
            records = []

        pkt = Packet(
            packet_id=pid,
            packet_type=0,  # RESPONSE
            response_packet_id=pid,
            processing_result=result_code,
        )

        for rr in records:
            # Подзапись RECORD_RESPONSE
            sr_data = {"crn": rr.rn, "rst": 0}
            subrecord = Subrecord(
                subrecord_type=0,  # RECORD_RESPONSE
                data=sr_data,
            )
            rec = Record(
                record_id=rr.rn,
                service_type=rr.service,
                recipient_service_type=0,
                subrecords=[subrecord],
                rsod=rr.rsod,
            )
            pkt.records.append(rec)

        return self.build_packet(pkt)

    def build_record_response(self, crn: int, rst: int) -> bytes:
        """Собрать байты подзаписи RECORD_RESPONSE (SRT=0)."""
        sr_data = {"crn": crn, "rst": rst}
        sr = Subrecord(subrecord_type=0, data=sr_data)
        return serialize_subrecord(sr)

    def calculate_crc8(self, data: bytes) -> int:
        return crc8(data)

    def calculate_crc16(self, data: bytes) -> int:
        return crc16(data)

    def validate_crc8(self, header_data: bytes, expected: int) -> bool:
        """Проверить CRC-8 заголовка."""
        return crc8(header_data) == expected

    def validate_crc16(self, body_data: bytes, expected: int) -> bool:
        """Проверить CRC-16 тела."""
        return crc16(body_data) == expected

    # ──────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_header(data: bytes) -> Packet:
        """Разобрать заголовок из байтов (без CRC проверки).

        Делегирует parse_header() из _core.parser, но НЕ парсит RPID/PR
        (они обрабатываются отдельно в parse_packet()).
        """
        from libs.egts._core.parser import parse_header

        # parse_header() может распарсить RPID/PR для PT=0, но мы их игнорируем
        # потому что в Gost2015Protocol.parse_packet() они извлекаются отдельно
        packet = parse_header(data)

        # Сбрасываем RPID/PR которые мог распарсить parse_header()
        # чтобы обработать их самостоятельно с правильным offset
        packet.response_packet_id = None
        packet.processing_result = None

        return packet

    @staticmethod
    def _parse_records(packet: Packet, sfrd: bytes, warnings: list[str]) -> None:
        """Разобрать записи уровня поддержки услуг.
        
        По ГОСТ 33465-2015 таблица 14:
        Запись = RL(2) + RN(2) + RFL(1) + [OID] + [EVID] + [TM] + SST(1) + RST(1) + RD(RL)
        RL = длина RD (payload), НЕ включая RL/RN/RFL/SST/RST
        """
        offset = 0
        while offset + 2 <= len(sfrd):  # RL(2) минимум
            # RL — длина RD (payload), НЕ включая заголовок записи
            rl = int.from_bytes(sfrd[offset:offset+2], 'little')
            offset += 2

            # Минимальный заголовок записи: RN(2) + RFL(1) + SST(1) + RST(1) = 5
            header_size = 5  # без опциональных полей

            if offset + header_size > len(sfrd):
                break

            # RN
            rn = int.from_bytes(sfrd[offset:offset+2], 'little')
            offset += 2

            # RFL
            rfl = sfrd[offset]; offset += 1
            ssod = bool(rfl & 0x80)
            rsod = bool(rfl & 0x40)
            rpp = (rfl >> 3) & 0x07
            obfe = bool(rfl & 0x04)
            evfe = bool(rfl & 0x02)
            tmfe = bool(rfl & 0x01)

            # Определяем размер опциональных полей
            optional_size = 0
            if obfe:
                optional_size += 4  # OID
            if evfe:
                optional_size += 2  # EVID
            if tmfe:
                optional_size += 4  # TM

            header_size = 4 + optional_size + 1 + 1  # RN + optional + SST + RST

            # SST
            sst = sfrd[offset]; offset += 1

            # RST
            rst = sfrd[offset]; offset += 1

            # Опциональные поля
            object_id = event_id = timestamp = None
            if obfe and offset + 4 <= len(sfrd):
                object_id = int.from_bytes(sfrd[offset:offset+4], 'little')
                offset += 4
            if evfe and offset + 2 <= len(sfrd):
                event_id = int.from_bytes(sfrd[offset:offset+2], 'little')
                offset += 2
            if tmfe and offset + 4 <= len(sfrd):
                timestamp = int.from_bytes(sfrd[offset:offset+4], 'little')
                offset += 4

            # RD (payload) — rl байт
            if offset + rl > len(sfrd):
                warnings.append(f"RD выходит за границы: нужно {rl}, есть {len(sfrd) - offset}")
                rd = sfrd[offset:]
                offset = len(sfrd)
            else:
                rd = sfrd[offset:offset+rl]
                offset += rl

            # Парсим подзаписи из RD
            subrecords = []
            rd_offset = 0
            while rd_offset + 3 <= len(rd):  # SRT(1) + SRL(2)
                srt = rd[rd_offset]; rd_offset += 1
                srl = int.from_bytes(rd[rd_offset:rd_offset+2], 'little')
                rd_offset += 2

                if rd_offset + srl > len(rd):
                    warnings.append(f"Подзапись SRT={srt} выходит за границы RD")
                    break

                srd = rd[rd_offset:rd_offset+srl]
                rd_offset += srl

                # Парсим подзапись
                parser = get_parser(srt)
                if parser is not None:
                    try:
                        sr_data = parser.parse(srd)
                        sub = Subrecord(
                            subrecord_type=srt,
                            data=sr_data,
                            raw_bytes=srd,
                        )
                    except Exception as e:
                        sub = Subrecord(
                            subrecord_type=srt,
                            data=srd,
                            raw_bytes=srd,
                            parse_error=str(e),
                        )
                        warnings.append(f"Ошибка парсинга SRT={srt}: {e}")
                else:
                    sub = Subrecord(
                        subrecord_type=srt,
                        data=srd,
                        raw_bytes=srd,
                    )

                subrecords.append(sub)

            rec = Record(
                record_id=rn,
                service_type=sst,
                recipient_service_type=rst,
                subrecords=subrecords,
                object_id=object_id,
                event_id=event_id,
                timestamp=timestamp,
                ssod=ssod,
                rsod=rsod,
                rpp=rpp,
            )
            packet.records.append(rec)


# Регистрация
register_version("2015", lambda: Gost2015Protocol())
