"""Tests for the byte layout engine."""

import pytest
from gui.utils.byte_layout import (
    compute_layout, ByteField, ABBREVIATIONS,
)


def _crc8(data: bytes) -> int:
    poly = 0x31
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFF
    return crc


def _crc16(data: bytes) -> int:
    poly = 0x1021
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


_TID_LE = (12345).to_bytes(4, 'little')  # 39 30 00 00


def _build_appdata(subrecord_data: bytes, pid: int = 1) -> str:
    """Build a valid APPDATA packet hex string with a single record.

    subrecord_data is the full subrecord bytes (SRT + SRL + SRD).
    """
    rl = len(subrecord_data)
    record_bytes = bytes([
        rl & 0xFF, (rl >> 8) & 0xFF,  # RL
        0x01, 0x00,  # RN=1
        0x00,  # RFL=0
        0x01,  # SST=AUTH
        0x01,  # RST=AUTH
    ]) + subrecord_data
    fdl = len(record_bytes)
    hdr = bytes([
        0x01, 0x00, 0x00, 0x0B, 0x00,
        fdl & 0xFF, (fdl >> 8) & 0xFF,
        pid & 0xFF, (pid >> 8) & 0xFF,
        0x01,  # PT=APPDATA
    ])
    hcs = _crc8(hdr)
    sfrcs = _crc16(record_bytes)
    full = hdr + bytes([hcs]) + record_bytes + sfrcs.to_bytes(2, 'little')
    return full.hex()


def _build_response(rpid: int, pr: int, records_bytes: bytes = b"") -> str:
    """Build a valid RESPONSE packet hex string."""
    resp_data = rpid.to_bytes(2, 'little') + bytes([pr]) + records_bytes
    fdl = len(resp_data)
    hdr = bytes([
        0x01, 0x00, 0x00, 0x0B, 0x00,
        fdl & 0xFF, (fdl >> 8) & 0xFF,
        0x01, 0x00,  # PID=1
        0x00,  # PT=RESPONSE
    ])
    hcs = _crc8(hdr)
    sfrcs = _crc16(resp_data)
    full = hdr + bytes([hcs]) + resp_data + sfrcs.to_bytes(2, 'little')
    return full.hex()


class TestComputeLayoutEdgeCases:
    def test_empty_hex(self):
        result = compute_layout("", {})
        assert len(result) == 1
        assert result[0].field_type == "error"

    def test_none_hex(self):
        result = compute_layout(None, {})
        assert len(result) == 1
        assert result[0].field_type == "error"

    def test_invalid_hex(self):
        result = compute_layout("ZZZ", {})
        assert len(result) == 1
        assert result[0].field_type == "error"

    def test_too_short_packet(self):
        result = compute_layout("0100", {})
        assert len(result) == 1
        assert result[0].field_type == "error"


_APP_SUB = bytes([0x01, 0x04, 0x00]) + _TID_LE  # SRT=1, SRL=4, TID=12345


class TestComputeLayoutHeader:
    def test_header_fields_present(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})
        hdr_sections = [f for f in fields if f.field_type == "section"]
        assert len(hdr_sections) >= 1

    def test_transport_header_children(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})
        hdr_section = [f for f in fields if f.field_type == "section"][0]
        hdr_abbrs = [c.abbr for c in hdr_section.children]
        assert "PRV" in hdr_abbrs
        assert "SKID" in hdr_abbrs
        assert "FLAGS" in hdr_abbrs
        assert "HL" in hdr_abbrs
        assert "FDL" in hdr_abbrs
        assert "PID" in hdr_abbrs
        assert "PT" in hdr_abbrs
        assert "HCS" in hdr_abbrs

    def test_pid_value(self):
        hex_str = _build_appdata(_APP_SUB, pid=42)
        fields = compute_layout(hex_str, {})
        hdr_section = [f for f in fields if f.field_type == "section"][0]
        pid_field = [c for c in hdr_section.children if c.abbr == "PID"][0]
        assert "42" in pid_field.value_display

    def test_pt_is_appdata(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})
        hdr_section = [f for f in fields if f.field_type == "section"][0]
        pt_field = [c for c in hdr_section.children if c.abbr == "PT"][0]
        assert "APPDATA" in pt_field.value_display

    def test_sfrds_present(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})
        sfrd_sections = [f for f in fields if "Service Frame Data" in f.full_name]
        assert len(sfrd_sections) == 1


class TestComputeLayoutAppdata:
    def test_full_packet_with_record(self):
        """APPDATA with a single record containing TERM_IDENTITY subrecord."""
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})
        section_names = [f.full_name for f in fields]
        section_names += [c.full_name for f in fields for c in f.children if f.field_type == "section"]
        assert any("Service Frame Data" in s for s in section_names)

    def test_record_section_in_sfrd(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})
        sfrd = [f for f in fields if "Service Frame Data" in f.full_name]
        assert len(sfrd) == 1
        rec_sections = [c for c in sfrd[0].children if "Record" in c.full_name]
        assert len(rec_sections) >= 1

    def test_subrecord_fields_in_record(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})

        def find_abbr(field_list, abbr):
            for f in field_list:
                if f.abbr == abbr:
                    return f
                for c in f.children:
                    result = find_abbr([c], abbr)
                    if result:
                        return result
            return None

        srt_field = find_abbr(fields, "SRT")
        assert srt_field is not None
        assert "TERM_IDENTITY" in srt_field.value_display

        tid_field = find_abbr(fields, "TID")
        assert tid_field is not None
        assert "12345" in tid_field.value_display

    def test_crc16_present(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})
        crc_fields = [f for f in fields if f.abbr == "SFRCS"]
        assert len(crc_fields) == 1


class TestComputeLayoutResponse:
    def test_rpid_present(self):
        hex_str = _build_response(rpid=42, pr=0)
        fields = compute_layout(hex_str, {})
        sfrd = [f for f in fields if "Service Frame Data" in f.full_name]
        assert len(sfrd) == 1
        rpid_fields = [c for c in sfrd[0].children if c.abbr == "RPID"]
        assert len(rpid_fields) == 1
        assert "42" in rpid_fields[0].value_display

    def test_prc_present(self):
        hex_str = _build_response(rpid=42, pr=0)
        fields = compute_layout(hex_str, {})
        sfrd = [f for f in fields if "Service Frame Data" in f.full_name]
        prc_fields = [c for c in sfrd[0].children if c.abbr == "PRC"]
        assert len(prc_fields) == 1
        assert "OK" in prc_fields[0].value_display


class TestComputeLayoutSrtParsingTermIdentity:
    def test_tid_parsed(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})

        def find(field_list, abbr):
            for f in field_list:
                if f.abbr == abbr:
                    return f
                for c in f.children:
                    result = find([c], abbr)
                    if result:
                        return result
            return None

        tid = find(fields, "TID")
        assert tid is not None
        assert "12345" in tid.value_display

    def test_term_identity_srt(self):
        hex_str = _build_appdata(_APP_SUB)
        fields = compute_layout(hex_str, {})

        def find(field_list, abbr):
            for f in field_list:
                if f.abbr == abbr:
                    return f
                for c in f.children:
                    result = find([c], abbr)
                    if result:
                        return result
            return None

        srt = find(fields, "SRT")
        assert srt is not None
        assert "TERM_IDENTITY" in srt.value_display


class TestComputeLayoutFlags:
    def test_routing_flags(self):
        # Build a header with RTE=1 (HL must be 15)
        hdr = bytes([
            0x01, 0x00, 0x40, 0x0F, 0x00,  # FLAGS=0x40 → RTE=1, HL=15
            0x00, 0x00, 0x01, 0x00, 0x01,  # FDL=0, PID=1, PT=1
            0x00, 0x00, 0x00, 0x00, 0x00,  # PRA(2), RCA(2), TTL(1)
        ])
        hcs = _crc8(hdr)
        sfrcs = _crc16(b"")
        hex_str = (hdr + bytes([hcs]) + sfrcs.to_bytes(2, 'little')).hex()

        fields = compute_layout(hex_str, {})
        hdr_section = [f for f in fields if f.field_type == "section"][0]
        flags_field = [c for c in hdr_section.children if c.abbr == "FLAGS"][0]
        rte_bit = [c for c in flags_field.children if c.abbr == "RTE"][0]
        assert "1" in rte_bit.value_display

    def test_pra_present_with_routing(self):
        hdr = bytes([
            0x01, 0x00, 0x40, 0x0F, 0x00,
            0x00, 0x00, 0x01, 0x00, 0x01,
            0x34, 0x12, 0x78, 0x56, 0x0A,  # PRA=0x1234, RCA=0x5678, TTL=10
        ])
        hcs = _crc8(hdr)
        sfrcs = _crc16(b"")
        hex_str = (hdr + bytes([hcs]) + sfrcs.to_bytes(2, 'little')).hex()

        fields = compute_layout(hex_str, {})
        hdr_section = [f for f in fields if f.field_type == "section"][0]
        pra_fields = [c for c in hdr_section.children if c.abbr == "PRA"]
        assert len(pra_fields) == 1
        assert "1234" in pra_fields[0].value_display or "0x1234" in pra_fields[0].value_display


class TestAbbreviations:
    def test_common_abbreviations_exist(self):
        expected = ["PRV", "SKID", "HL", "FDL", "PID", "PT", "HCS",
                    "SFRCS", "RL", "RN", "RFL", "SST", "RST",
                    "SRT", "SRL", "TID", "CRN", "RCD"]
        for abbr in expected:
            assert abbr in ABBREVIATIONS, f"Missing abbreviation: {abbr}"

    def test_abbreviation_has_full_name_and_desc(self):
        for abbr, (full, desc) in ABBREVIATIONS.items():
            assert full, f"Abbreviation {abbr} has no full name"
            assert desc, f"Abbreviation {abbr} has no description"
