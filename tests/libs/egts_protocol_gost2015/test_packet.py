"""Тесты на транспортный пакет EGTS (ГОСТ 33465-2015, раздел 5.6)

Покрывает:
- Сборка пакетов (to_bytes)
- Парсинг пакетов (from_bytes)
- CRC-8 заголовка и CRC-16 данных
- Краевые случаи (max ID, cyclic ID, invalid version)
"""

import pytest

from libs.egts_protocol_gost2015.gost2015_impl.crc import crc8, crc16
from libs.egts_protocol_gost2015.gost2015_impl.packet import Packet
from libs.egts_protocol_gost2015.gost2015_impl.types import (
    PACKET_HCS_SIZE,
    PACKET_HEADER_MIN_SIZE,
    PACKET_HEADER_WITH_ROUTING_SIZE,
    PACKET_HL_OFFSET,
    PACKET_SFRCS_SIZE,
    PacketType,
    Priority,
)


class TestPacketBuild:
    """Тесты на сборку пакетов"""

    def test_packet_build_minimal(self) -> None:
        """Сборка минимального пакета без записей"""
        packet = Packet(
            packet_id=1,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = packet.to_bytes()

        assert len(raw) >= PACKET_HEADER_MIN_SIZE
        assert isinstance(raw, bytes)

    def test_packet_build_with_priority(self) -> None:
        """Сборка пакета с приоритетом"""
        packet = Packet(
            packet_id=2,
            packet_type=PacketType.EGTS_PT_APPDATA,
            priority=Priority.HIGH,
        )
        raw = packet.to_bytes()
        assert isinstance(raw, bytes)
        assert len(raw) >= PACKET_HEADER_MIN_SIZE

    def test_packet_build_all_types(self) -> None:
        """Сборка пакетов всех типов"""
        for pt in PacketType:
            packet = Packet(packet_id=1, packet_type=pt)
            raw = packet.to_bytes()
            assert isinstance(raw, bytes)
            assert len(raw) >= PACKET_HEADER_MIN_SIZE

    def test_packet_build_with_routing(self) -> None:
        """Сборка пакета с маршрутизацией"""
        packet = Packet(
            packet_id=3,
            packet_type=PacketType.EGTS_PT_APPDATA,
            sender_address=100,
            receiver_address=200,
            ttl=5,
        )
        raw = packet.to_bytes()
        assert len(raw) >= PACKET_HEADER_WITH_ROUTING_SIZE


class TestPacketParse:
    """Тесты на парсинг пакетов"""

    def test_packet_parse_minimal(self) -> None:
        """Парсинг минимального пакета"""
        original = Packet(
            packet_id=42,
            packet_type=PacketType.EGTS_PT_APPDATA,
            priority=Priority.LOW,
        )
        raw = original.to_bytes()
        parsed = Packet.from_bytes(raw)

        assert parsed.packet_id == 42
        assert parsed.packet_type == PacketType.EGTS_PT_APPDATA
        assert parsed.priority == Priority.LOW

    def test_packet_parse_with_routing(self) -> None:
        """Парсинг пакета с маршрутизацией"""
        original = Packet(
            packet_id=100,
            packet_type=PacketType.EGTS_PT_APPDATA,
            sender_address=1000,
            receiver_address=2000,
            ttl=10,
        )
        raw = original.to_bytes()
        parsed = Packet.from_bytes(raw)

        assert parsed.packet_id == 100
        assert parsed.sender_address == 1000
        assert parsed.receiver_address == 2000
        assert parsed.ttl == 10

    def test_packet_parse_roundtrip(self) -> None:
        """Круговой тест: сборка → парсинг → сверка"""
        for packet_id in [1, 100, 1000, 65535]:
            original = Packet(
                packet_id=packet_id,
                packet_type=PacketType.EGTS_PT_APPDATA,
                priority=Priority.MEDIUM,
            )
            raw = original.to_bytes()
            parsed = Packet.from_bytes(raw)

            assert parsed.packet_id == packet_id
            assert parsed.packet_type == PacketType.EGTS_PT_APPDATA


class TestPacketCrc:
    """Тесты на контрольные суммы пакетов"""

    def test_packet_crc8_header(self) -> None:
        """CRC-8 заголовка пакета"""
        packet = Packet(
            packet_id=1,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = packet.to_bytes()

        hl = raw[PACKET_HL_OFFSET]  # HL поле — полная длина заголовка включая HCS
        header_with_hcs = raw[:hl]  # Полный заголовок с HCS

        calculated_crc = crc8(header_with_hcs[:-1])  # Без последнего байта (HCS)
        stored_crc = header_with_hcs[-1]
        assert calculated_crc == stored_crc

    def test_packet_crc16_data(self) -> None:
        """CRC-16 данных пакета (SFRD)"""
        packet = Packet(
            packet_id=1,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = packet.to_bytes()

        hl = raw[PACKET_HL_OFFSET]
        fdl = int.from_bytes(raw[5:7], "little")
        ppu_data = raw[hl : hl + fdl]

        stored_crc = int.from_bytes(raw[-PACKET_SFRCS_SIZE:], "little")
        calculated_crc = crc16(ppu_data)

        assert calculated_crc == stored_crc

    def test_packet_verify_crc_on_parse(self) -> None:
        """Проверка CRC при парсинге"""
        original = Packet(
            packet_id=1,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = original.to_bytes()

        parsed = Packet.from_bytes(raw)
        assert parsed.packet_id == 1

    def test_packet_invalid_crc8(self) -> None:
        """Парсинг пакета с неверным CRC-8 заголовка"""
        original = Packet(
            packet_id=1,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = original.to_bytes()

        corrupted = bytearray(raw)
        corrupted[PACKET_HEADER_MIN_SIZE - PACKET_HCS_SIZE] ^= 0xFF

        with pytest.raises(ValueError, match="CRC-8"):
            Packet.from_bytes(bytes(corrupted))

    def test_packet_invalid_crc16(self) -> None:
        """Парсинг пакета с неверным CRC-16 данных"""
        original = Packet(
            packet_id=1,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = original.to_bytes()

        corrupted = bytearray(raw)
        corrupted[-1] ^= 0xFF

        with pytest.raises(ValueError, match="CRC-16"):
            Packet.from_bytes(bytes(corrupted))


class TestPacketEdgeCases:
    """Тесты на краевые случаи"""

    def test_packet_invalid_version(self) -> None:
        """Парсинг пакета с неверной версией протокола"""
        original = Packet(
            packet_id=1,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = original.to_bytes()

        corrupted = bytearray(raw)
        corrupted[0] = 0x02  # Неверная версия

        with pytest.raises(ValueError, match="Неверная версия"):
            Packet.from_bytes(bytes(corrupted))

    def test_packet_max_id(self) -> None:
        """Пакет с максимальным ID (65535)"""
        packet = Packet(
            packet_id=65535,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = packet.to_bytes()
        parsed = Packet.from_bytes(raw)
        assert parsed.packet_id == 65535

    def test_packet_zero_id(self) -> None:
        """Пакет с ID 0"""
        packet = Packet(
            packet_id=0,
            packet_type=PacketType.EGTS_PT_APPDATA,
        )
        raw = packet.to_bytes()
        parsed = Packet.from_bytes(raw)
        assert parsed.packet_id == 0

    def test_packet_cyclic_id(self) -> None:
        """Проверка циклического счётчика ID"""
        packet1 = Packet(packet_id=65535, packet_type=PacketType.EGTS_PT_APPDATA)
        packet2 = Packet(packet_id=0, packet_type=PacketType.EGTS_PT_APPDATA)

        raw1 = packet1.to_bytes()
        raw2 = packet2.to_bytes()

        assert Packet.from_bytes(raw1).packet_id == 65535
        assert Packet.from_bytes(raw2).packet_id == 0
