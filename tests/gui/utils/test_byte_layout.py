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


# ──────────────────────────────────────────────────────────────
# Regression tests for byte-layout bugs fixed via canonical parser integration.
# These tests pass parsed subrecords (from libs.egts._gost2015.subrecords)
# to compute_layout() and verify the previously buggy offset computations.
# ──────────────────────────────────────────────────────────────

def _find_field(field_list, abbr):
    """Recursively find a ByteField by abbr."""
    for f in field_list:
        if f.abbr == abbr:
            return f
        if f.children:
            r = _find_field(f.children, abbr)
            if r:
                return r
    return None


def _find_section(field_list, name_substr):
    for f in field_list:
        if f.field_type == "section" and name_substr in f.full_name:
            return f
        if f.children:
            r = _find_section(f.children, name_substr)
            if r:
                return r
    return None


class TestSrt33Regression:
    """SRT=33 SERVICE_PART_DATA: OD field must show actual length, not constant 6."""

    def test_od_field_length_matches_parsed(self):
        """With parsed_data, OD length = len(parsed['od']), not the broken `remaining = 6`."""
        from libs.egts._gost2015.subrecords import ServicePartDataParser
        raw_srd = b'\x01\x00' + b'\x01\x00' + b'\x01\x00' + b'\xAA' * 20  # id=1, pn=1, epq=1, 20 bytes OD
        parsed = ServicePartDataParser().parse(raw_srd)
        sub_dicts = [{"srt": 33, "data": parsed, "raw_bytes": raw_srd}]

        # Build APPDATA with this subrecord
        srd = bytes([33]) + len(raw_srd).to_bytes(2, 'little') + raw_srd
        rl = len(srd)
        record = bytes([rl & 0xFF, (rl >> 8) & 0xFF, 1, 0, 0, 1, 1]) + srd
        fdl = len(record)
        hdr = bytes([1, 0, 0, 0x0B, 0, fdl & 0xFF, (fdl >> 8) & 0xFF, 1, 0, 1])
        hcs = _crc8(hdr)
        sfrcs = _crc16(record)
        hex_str = (hdr + bytes([hcs]) + record + sfrcs.to_bytes(2, 'little')).hex()

        fields = compute_layout(hex_str, {}, [{"subrecords": sub_dicts}])
        od = _find_field(fields, "OD")
        assert od is not None, "OD field should be present"
        assert "(20 bytes)" in od.value_display, f"OD must show 20 bytes, got: {od.value_display}"

    def test_od_offset_end_covers_full_payload(self):
        """The OD field's offset_end must equal the last byte of the payload."""
        from libs.egts._gost2015.subrecords import ServicePartDataParser
        raw_srd = b'\x01\x00' + b'\x01\x00' + b'\x01\x00' + b'\xBB' * 15
        parsed = ServicePartDataParser().parse(raw_srd)
        sub_dicts = [{"srt": 33, "data": parsed, "raw_bytes": raw_srd}]

        srd = bytes([33]) + len(raw_srd).to_bytes(2, 'little') + raw_srd
        rl = len(srd)
        record = bytes([rl & 0xFF, (rl >> 8) & 0xFF, 1, 0, 0, 1, 1]) + srd
        fdl = len(record)
        hdr = bytes([1, 0, 0, 0x0B, 0, fdl & 0xFF, (fdl >> 8) & 0xFF, 1, 0, 1])
        hcs = _crc8(hdr)
        sfrcs = _crc16(record)
        hex_str = (hdr + bytes([hcs]) + record + sfrcs.to_bytes(2, 'little')).hex()

        fields = compute_layout(hex_str, {}, [{"subrecords": sub_dicts}])
        od = _find_field(fields, "OD")
        assert od is not None
        # OD must span exactly 15 bytes
        assert od.offset_end - od.offset_start + 1 == 15


class TestSrt34Regression:
    """SRT=34 SERVICE_FULL_DATA: OD must NOT be hidden by the always-zero `remaining` bug."""

    def test_od_field_present(self):
        from libs.egts._gost2015.subrecords import ServiceFullDataParser
        # ODH: OA(1) + OT_MT(1) + CMI(1) + VER(2) + WOS(2) + null-terminated FN, then null
        odh = b'\x01\x02\x03\x04\x05\x06\x07' + b'firmware.bin\x00'
        od = b'\xDE\xAD\xBE\xEF' * 8
        raw_srd = odh + od
        parsed = ServiceFullDataParser().parse(raw_srd)
        sub_dicts = [{"srt": 34, "data": parsed, "raw_bytes": raw_srd}]

        srd = bytes([34]) + len(raw_srd).to_bytes(2, 'little') + raw_srd
        rl = len(srd)
        record = bytes([rl & 0xFF, (rl >> 8) & 0xFF, 1, 0, 0, 9, 9]) + srd
        fdl = len(record)
        hdr = bytes([1, 0, 0, 0x0B, 0, fdl & 0xFF, (fdl >> 8) & 0xFF, 1, 0, 1])
        hcs = _crc8(hdr)
        sfrcs = _crc16(record)
        hex_str = (hdr + bytes([hcs]) + record + sfrcs.to_bytes(2, 'little')).hex()

        fields = compute_layout(hex_str, {}, [{"subrecords": sub_dicts}])
        od_field = _find_field(fields, "OD")
        assert od_field is not None, "OD field must be present for SERVICE_FULL_DATA"
        assert len(od) == od_field.offset_end - od_field.offset_start + 1


class TestSrt20Regression:
    """SRT=20 ACCEL_DATA: bounds checks and iteration count must use parsed measurements."""

    def test_measurements_count_matches_parsed(self):
        from libs.egts._gost2015.subrecords import AccelDataParser
        # 3 measurements, each 8 bytes
        m1 = b'\x00\x01' + b'\x10\x00' + b'\x20\x00' + b'\x30\x00'  # rtm=256, +16, +32, +48
        m2 = b'\x00\x02' + b'\x11\x00' + b'\x21\x00' + b'\x31\x00'
        m3 = b'\x00\x03' + b'\x12\x00' + b'\x22\x00' + b'\x32\x00'
        raw_srd = b'\x03' + b'\x00\x00\x00\x00' + m1 + m2 + m3
        parsed = AccelDataParser().parse(raw_srd)
        assert len(parsed["measurements"]) == 3

        sub_dicts = [{"srt": 20, "data": parsed, "raw_bytes": raw_srd}]
        srd = bytes([20]) + len(raw_srd).to_bytes(2, 'little') + raw_srd
        rl = len(srd)
        record = bytes([rl & 0xFF, (rl >> 8) & 0xFF, 1, 0, 0, 1, 1]) + srd
        fdl = len(record)
        hdr = bytes([1, 0, 0, 0x0B, 0, fdl & 0xFF, (fdl >> 8) & 0xFF, 1, 0, 1])
        hcs = _crc8(hdr)
        sfrcs = _crc16(record)
        hex_str = (hdr + bytes([hcs]) + record + sfrcs.to_bytes(2, 'little')).hex()

        fields = compute_layout(hex_str, {}, [{"subrecords": sub_dicts}])
        measurements = [c for c in fields[1].children
                        if "Measurement" in c.full_name]  # type: ignore[union-attr]
        # Find measurements anywhere in the tree
        all_measurements = []
        def collect(fs):
            for f in fs:
                if f.field_type == "section" and "Measurement" in f.full_name:
                    all_measurements.append(f)
                if f.children:
                    collect(f.children)
        collect(fields)
        assert len(all_measurements) == 3, f"Expected 3 measurements, got {len(all_measurements)}"


class TestSrt63Regression:
    """SRT=63 TRACK_DATA: Point section must cover actual point bytes, not 2 bytes."""

    def test_point_section_covers_full_point(self):
        from libs.egts._gost2015.subrecords import TrackDataParser
        # 1 point with all fields: FLG(1) + LAT(4) + LONG(4) + SPD(3) = 12 bytes (no DIR)
        # FLG byte: TNDE=1, LOHS=0, LAHS=0, SDFE=0, SPFE=1, RTM=2 → 0x8A
        # 128 | 8 | 2 = 138 = 0x8A
        flg = 0x80 | 0x08 | 0x02  # tnde + spfe + rtm=2
        point = bytes([flg]) + b'\x00\x00\x00\x80' + b'\x00\x00\x00\x40' + b'\x00\x01\x02'
        raw_srd = b'\x01' + b'\x00\x00\x00\x00' + point  # SA=1, ATM=0
        parsed = TrackDataParser().parse(raw_srd)
        assert len(parsed["track_points"]) == 1

        sub_dicts = [{"srt": 63, "data": parsed, "raw_bytes": raw_srd}]
        srd = bytes([63]) + len(raw_srd).to_bytes(2, 'little') + raw_srd
        rl = len(srd)
        record = bytes([rl & 0xFF, (rl >> 8) & 0xFF, 1, 0, 0, 1, 1]) + srd
        fdl = len(record)
        hdr = bytes([1, 0, 0, 0x0B, 0, fdl & 0xFF, (fdl >> 8) & 0xFF, 1, 0, 1])
        hcs = _crc8(hdr)
        sfrcs = _crc16(record)
        hex_str = (hdr + bytes([hcs]) + record + sfrcs.to_bytes(2, 'little')).hex()

        fields = compute_layout(hex_str, {}, [{"subrecords": sub_dicts}])
        point_section = _find_section(fields, "Point 1")
        assert point_section is not None
        # FLG(1) + LAT(4) + LONG(4) + SPD(3) = 12 bytes
        point_size = point_section.offset_end - point_section.offset_start + 1
        assert point_size == 12, (
            f"Point 1 section should cover 12 bytes (FLG+LAT+LONG+SPD), got {point_size}. "
            f"Offset range: [{point_section.offset_start}-{point_section.offset_end}]"
        )


class TestTruncatedRecordRegression:
    """Б-04 fix: APPDATA record bound check uses 7 (not 4) bytes for record header."""

    def test_truncated_record_breaks_gracefully(self):
        """A record with RL=10 but only 8 bytes present should not crash."""
        # RL=10, RN=1, RFL=0, SST=1, RST=1 = 7 bytes header, then 1 byte of RD
        # Total available: 8 (truncated RD)
        record = bytes([10, 0, 1, 0, 0, 1, 1, 0xAA])
        fdl = len(record)
        hdr = bytes([1, 0, 0, 0x0B, 0, fdl & 0xFF, (fdl >> 8) & 0xFF, 1, 0, 1])
        hcs = _crc8(hdr)
        sfrcs = _crc16(record)
        hex_str = (hdr + bytes([hcs]) + record + sfrcs.to_bytes(2, 'little')).hex()

        # Should not raise an exception
        fields = compute_layout(hex_str, {})
        # At minimum, the header section should be present
        assert len(fields) >= 1
