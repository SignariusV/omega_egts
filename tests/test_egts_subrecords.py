"""Тесты Этапа 6: парсеры подзаписей."""

import pytest

# Импорт регистрирует все парсеры автоматически
import libs.egts._gost2015.subrecords  # noqa: F401
from libs.egts._core.subrecord_registry import get_parser


class TestSubrecordRoundtrip:
    """Roundtrip тест каждого парсера: parse(serialize(data)) == data."""

    def _test_srt_roundtrip(self, srt: int, raw: bytes, expected_keys: set[str] | None = None):
        """Общий тест roundtrip для SRT."""
        parser = get_parser(srt)
        assert parser is not None, f"Парсер для SRT={srt} не найден"

        # Parse
        data = parser.parse(raw)

        if expected_keys:
            assert expected_keys.issubset(set(data.keys()) if isinstance(data, dict) else set()), \
                f"SRT={srt}: ключи {expected_keys - set(data.keys())} отсутствуют"

        # Serialize
        rebuilt = parser.serialize(data)

        # Roundtrip
        assert rebuilt == raw, (
            f"SRT={srt}: roundtrip failed\n"
            f"  original ({len(raw)}): {raw.hex()}\n"
            f"  rebuilt  ({len(rebuilt)}): {rebuilt.hex()}"
        )

    # SRT=0 RECORD_RESPONSE
    def test_srt0_record_response(self):
        raw = bytes([10, 0, 0])  # CRN=10, RST=0
        self._test_srt_roundtrip(0, raw, {"crn", "rst"})

    # SRT=9 RESULT_CODE
    def test_srt9_result_code_ok(self):
        raw = bytes([0])  # RCD=0 (OK)
        self._test_srt_roundtrip(9, raw, {"rcd", "rcd_text"})

    def test_srt9_result_code_error(self):
        raw = bytes([137])  # RCD=137 (HEADERCRC_ERROR)
        self._test_srt_roundtrip(9, raw, {"rcd", "rcd_text"})

    # SRT=1 TERM_IDENTITY — тест на реальном пакете
    def test_srt1_term_identity(self):
        """TERM_IDENTITY из эталонного пакета."""
        # TID(4) + flags(1) + IMEI(15) + IMSI(16) + LNGC(3) + NID(3) + BS(2) + MSISDN(15)
        # flags=0xFE (IMEIE|IMSIE|LNGCE|NIDE|BSE|MNE = 1, HDIDE=0, SSRA=0)
        raw = bytes([
            0x01, 0x00, 0x00, 0x00,  # TID=1
            0xFE,                       # flags: IMEI, IMSI, LNGC, NID, BS, MSISDN
            # IMEI (15 байт, BCD, padded 0xFF)
            0x33, 0x11, 0x70, 0x00, 0x50, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # IMSI (16 байт)
            0x32, 0x50, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # LNGC
            0x72, 0x75, 0x73,
            # NID
            0x02, 0x03, 0x02,
            # BS
            0x00, 0x04,
            # MSISDN (15 байт)
            0x69, 0x6E, 0x74, 0x65, 0x72, 0x6E, 0x65, 0x74,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ])
        parser = get_parser(1)
        assert parser is not None
        data = parser.parse(raw)
        assert data["tid"] == 1
        assert data["imei"] is not None
        rebuilt = parser.serialize(data)
        assert rebuilt == raw
