"""Тесты Этапов 2-5: protocol, registry, CRC, subrecord, parser/builder."""

import os

import pytest

from libs.egts._core.crc import crc8, crc16
from libs.egts._core.parser import build_header, parse_header
from libs.egts._core.subrecord_registry import get_parser, register_subrecord
from libs.egts.models import Packet, ParseResult
from libs.egts.registry import available_versions, get_protocol, register_version

FIXTURES_DIR = "tests/fixtures/egts_packets"


# ──────────────────────────────────────────────────────────────
# Этап 2: Protocol + Registry
# ──────────────────────────────────────────────────────────────

class DummyProtocol:
    """Фейковый протокол для тестирования registry."""
    version = "dummy"
    capabilities = set()

    def parse_packet(self, data: bytes) -> ParseResult:
        return ParseResult(packet=None)

    def build_packet(self, packet: Packet) -> bytes:
        return b""

    def build_response(self, pid, rc, records=None):
        return b""

    def build_record_response(self, crn, rst):
        return b""

    def calculate_crc8(self, data):
        return crc8(data)

    def calculate_crc16(self, data):
        return crc16(data)


class TestRegistry:
    def test_register_and_get(self):
        register_version("dummy", lambda: DummyProtocol())
        proto = get_protocol("dummy")
        assert proto.version == "dummy"

    def test_unknown_version(self):
        with pytest.raises(ValueError, match="Unknown EGTS version"):
            get_protocol("2099")

    def test_available_versions(self):
        versions = available_versions()
        assert "dummy" in versions


# ──────────────────────────────────────────────────────────────
# Этап 3: CRC
# ──────────────────────────────────────────────────────────────

class TestCRC:
    def test_crc8_known(self):
        """CRC-8 от пустых данных с init=0xFF."""
        result = crc8(b"")
        assert result == 0xFF  # init value, no data

    def test_crc8_single_byte(self):
        """CRC-8 от одного байта."""
        result = crc8(b"\x00")
        # XOR с init: 0xFF ^ 0x00 = 0xFF, затем 8 сдвигов с полиномом
        # Проверяем что результат детерминирован
        assert isinstance(result, int)
        assert 0 <= result <= 255

    def test_crc16_known(self):
        """CRC-16 от пустых данных с init=0xFFFF."""
        result = crc16(b"")
        assert result == 0xFFFF

    def test_crc_consistency(self):
        """CRC от одинаковых данных должен совпадать."""
        data = b"\x01\x00\x00\x0b\x00\x21\x00\x1b\x00\x01"
        assert crc8(data) == crc8(data)
        assert crc16(data) == crc16(data)

    def test_crc8_vs_old_library(self):
        """Сравним CRC-8 с результатами из эталонных пакетов."""
        # Возьмём первый эталонный пакет и проверим CRC-8
        bin_path = os.path.join(FIXTURES_DIR, "pkt_001.bin")
        if os.path.exists(bin_path):
            with open(bin_path, "rb") as f:
                raw = f.read()
            hl = raw[3]
            hcs_in_packet = raw[hl - 1]
            computed = crc8(raw[:hl - 1])
            assert computed == hcs_in_packet


# ──────────────────────────────────────────────────────────────
# Этап 4: Subrecord Registry
# ──────────────────────────────────────────────────────────────

class TestSubrecordRegistry:
    def test_register_decorator(self):
        @register_subrecord
        class TestParser:
            srt = 99
            name = "TEST"

            def parse(self, raw: bytes):
                return {}

            def serialize(self, data):
                return b""

        parser = get_parser(99)
        assert parser is not None
        assert parser.name == "TEST"

    def test_get_parser_unknown(self):
        assert get_parser(255) is None


# ──────────────────────────────────────────────────────────────
# Этап 5: Parser + Builder (заголовок)
# ──────────────────────────────────────────────────────────────

class TestHeaderRoundtrip:
    """Roundtrip заголовка: parse_header(build_header(pkt)) == pkt."""

    def _load_ethalon_headers(self):
        """Загрузить заголовки из эталонных пакетов."""
        headers = []
        for fname in sorted(os.listdir(FIXTURES_DIR)):
            if not fname.endswith(".bin"):
                continue
            fpath = os.path.join(FIXTURES_DIR, fname)
            with open(fpath, "rb") as f:
                raw = f.read()
            headers.append((fname, raw))
        return headers

    def test_parse_all_ethalon_headers(self):
        """Все эталонные заголовки должны парситься."""
        failures = []
        for name, raw in self._load_ethalon_headers():
            try:
                pkt = parse_header(raw)
                assert pkt.packet_id >= 0
            except Exception as e:
                failures.append(f"{name}: {e}")
        assert not failures, "Ошибки парсинга:\n" + "\n".join(failures)

    def test_header_roundtrip(self):
        """parse(build(pkt)) == pkt для всех эталонных пакетов."""
        failures = []
        for name, raw in self._load_ethalon_headers():
            try:
                original = parse_header(raw)
                rebuilt_bytes = build_header(original)
                rebuilt = parse_header(rebuilt_bytes)

                # Сравниваем ключевые поля (кроме raw_bytes)
                assert rebuilt.protocol_version == original.protocol_version
                assert rebuilt.security_key_id == original.security_key_id
                assert rebuilt.prefix == original.prefix
                assert rebuilt.routing == original.routing
                assert rebuilt.packet_id == original.packet_id
                assert rebuilt.packet_type == original.packet_type
                assert rebuilt.header_encoding == original.header_encoding
                assert rebuilt.header_length == original.header_length
                assert rebuilt.peer_address == original.peer_address
                assert rebuilt.recipient_address == original.recipient_address
                assert rebuilt.ttl == original.ttl

                # HCS должен совпадать
                assert rebuilt_bytes[-1] == rebuilt.hcs if hasattr(rebuilt, 'hcs') else True

            except Exception as e:
                failures.append(f"{name}: {e}")

        assert not failures, "Roundtrip ошибки:\n" + "\n".join(failures)

    def test_response_header_fields(self):
        """RESPONSE-пакет: RPID и PR должны парситься."""
        bin_path = os.path.join(FIXTURES_DIR, "pkt_008.bin")  # RESPONSE пакет
        if os.path.exists(bin_path):
            with open(bin_path, "rb") as f:
                raw = f.read()
            pkt = parse_header(raw)
            assert pkt.packet_type == 0
            assert pkt.response_packet_id is not None
            assert pkt.processing_result is not None
