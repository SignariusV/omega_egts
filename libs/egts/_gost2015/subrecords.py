"""Парсеры подзаписей EGTS ГОСТ 2015.

Каждая подзапись — класс с декоратором @register_subrecord.
"""

from __future__ import annotations

from typing import Any

from libs.egts._core.subrecord_registry import register_subrecord
from libs.egts.types import (
    CommandType, ConfirmationType, ActionType, Charset,
    COMMAND_CODES,
)

# ──────────────────────────────────────────────────────────────
# Helper-функции
# ──────────────────────────────────────────────────────────────

def _decode_string(data: bytes, encoding: str = "cp1251") -> str:
    """Декодировать строку с удалением null-байтов."""
    try:
        return data.rstrip(b"\x00").decode(encoding)
    except UnicodeDecodeError:
        return data.rstrip(b"\x00").decode("ascii", errors="replace")


def _encode_string(s: str, length: int, encoding: str = "cp1251") -> bytes:
    """Закодировать строку фиксированной длины."""
    encoded = s.encode(encoding) if isinstance(s, str) else s
    if len(encoded) < length:
        encoded = encoded + b"\x00" * (length - len(encoded))
    return encoded[:length]


def _decode_string_until_null(data: bytes, encoding: str = "cp1251") -> str:
    """Декодировать строку до первого null-байта."""
    if not data:
        return ""
    null_pos = data.find(b"\x00")
    if null_pos == -1:
        return _decode_string(data, encoding)
    return _decode_string(data[:null_pos], encoding)


# ──────────────────────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────────────────────

# TERM_IDENTITY
_TID_SIZE = 4
_TID_FLAGS_SIZE = 1
_TID_HDID_SIZE = 2
_TID_IMEI_SIZE = 15
_TID_IMSI_SIZE = 16
_TID_LNGC_SIZE = 3
_TID_NID_SIZE = 3
_TID_BS_SIZE = 2
_TID_MSISDN_SIZE = 15
_TID_MIN_SIZE = 5

_TID_HDIDE_MASK = 0x01
_TID_IMEIE_MASK = 0x02
_TID_IMSIE_MASK = 0x04
_TID_LNGCE_MASK = 0x08
_TID_SSRA_MASK = 0x10
_TID_NIDE_MASK = 0x20
_TID_BSE_MASK = 0x40
_TID_MNE_MASK = 0x80

# MODULE_DATA
_MODULE_DATA_MIN_SIZE = 11
_MODULE_MT_SIZE = 1
_MODULE_VID_SIZE = 4
_MODULE_FWV_SIZE = 2
_MODULE_SWV_SIZE = 2
_MODULE_MD_SIZE = 1
_MODULE_ST_SIZE = 1

# VEHICLE_DATA
_VEHICLE_VIN_SIZE = 17
_VEHICLE_VHT_SIZE = 4
_VEHICLE_VPST_SIZE = 4
_VEHICLE_DATA_SIZE = 25

# RECORD_RESPONSE
_RECORD_RESPONSE_CRN_SIZE = 2

# ACCEL_DATA
_ACCEL_SA_SIZE = 1
_ACCEL_ATM_SIZE = 4
_ACCEL_RTM_SIZE = 2
_ACCEL_XAAV_SIZE = 2
_ACCEL_YAAV_SIZE = 2
_ACCEL_ZAAV_SIZE = 2

# TRACK_DATA
_TRACK_SA_SIZE = 1
_TRACK_ATM_SIZE = 4
_TRACK_LAT_SIZE = 4
_TRACK_LON_SIZE = 4
_TRACK_SPD_SIZE = 2
_TRACK_DATA_MIN_SIZE = 5

# COMMAND_DATA
_COMMAND_DATA_MIN_SIZE = 10

# FIRMWARE
_ODH_MIN_SIZE = 7
_ODH_MAX_SIZE = 71
_MAX_OBJECT_DATA_SIZE = 65400
_MAX_PARTS = 65535
_SERVICE_PART_MIN_SIZE = 7


# ──────────────────────────────────────────────────────────────
# SRT=0 RECORD_RESPONSE
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class RecordResponseParser:
    srt = 0
    name = "RECORD_RESPONSE"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 3:
            return {"raw": raw, "parse_error": f"Too short: {len(raw)}"}
        crn = int.from_bytes(raw[0:2], "little")
        rst = raw[2]
        return {"crn": crn, "rst": rst}

    def serialize(self, data: dict[str, Any]) -> bytes:
        crn = int(data.get("crn", 0))
        rst = int(data.get("rst", 0))
        return crn.to_bytes(2, "little") + bytes([rst])


# ──────────────────────────────────────────────────────────────
# SRT=1 TERM_IDENTITY
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class TermIdentityParser:
    srt = 1
    name = "TERM_IDENTITY"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < _TID_MIN_SIZE:
            raise ValueError(f"TERM_IDENTITY too short: {len(raw)}")
        offset = 0
        tid = int.from_bytes(raw[offset:offset+_TID_SIZE], "little")
        offset += _TID_SIZE
        flags = raw[offset]
        offset += _TID_FLAGS_SIZE

        hdide = bool(flags & _TID_HDIDE_MASK)
        imeie = bool(flags & _TID_IMEIE_MASK)
        imsie = bool(flags & _TID_IMSIE_MASK)
        lngce = bool(flags & _TID_LNGCE_MASK)
        ssra = bool(flags & _TID_SSRA_MASK)
        nide = bool(flags & _TID_NIDE_MASK)
        bse = bool(flags & _TID_BSE_MASK)
        mne = bool(flags & _TID_MNE_MASK)

        result: dict[str, Any] = {
            "tid": tid, "flags": flags,
            "hdide": hdide, "imeie": imeie, "imsie": imsie,
            "lngce": lngce, "ssra": ssra,
            "nide": nide, "bse": bse, "mne": mne,
        }

        if hdide:
            result["hdid"] = int.from_bytes(raw[offset:offset+_TID_HDID_SIZE], "little")
            offset += _TID_HDID_SIZE
        if imeie:
            result["imei"] = _decode_string(raw[offset:offset+_TID_IMEI_SIZE])
            offset += _TID_IMEI_SIZE
        if imsie:
            result["imsi"] = _decode_string(raw[offset:offset+_TID_IMSI_SIZE])
            offset += _TID_IMSI_SIZE
        if lngce:
            result["lngc"] = _decode_string(raw[offset:offset+_TID_LNGC_SIZE])
            offset += _TID_LNGC_SIZE
        if nide:
            result["nid"] = raw[offset:offset+_TID_NID_SIZE]
            offset += _TID_NID_SIZE
        if bse:
            result["bs"] = int.from_bytes(raw[offset:offset+_TID_BS_SIZE], "little")
            offset += _TID_BS_SIZE
        if mne:
            result["msisdn"] = _decode_string(raw[offset:offset+_TID_MSISDN_SIZE])
            offset += _TID_MSISDN_SIZE

        return result

    def serialize(self, data: dict[str, Any]) -> bytes:
        result = bytearray()
        result.extend(int(data.get("tid", 0)).to_bytes(_TID_SIZE, "little"))

        flags = 0
        if data.get("hdide", False):
            flags |= _TID_HDIDE_MASK
        if data.get("imeie", False):
            flags |= _TID_IMEIE_MASK
        if data.get("imsie", False):
            flags |= _TID_IMSIE_MASK
        if data.get("lngce", False):
            flags |= _TID_LNGCE_MASK
        if data.get("ssra", False):
            flags |= _TID_SSRA_MASK
        if data.get("nide", False):
            flags |= _TID_NIDE_MASK
        if data.get("bse", False):
            flags |= _TID_BSE_MASK
        if data.get("mne", False):
            flags |= _TID_MNE_MASK
        result.append(flags)

        if data.get("hdide", False):
            result.extend(int(data.get("hdid", 0)).to_bytes(_TID_HDID_SIZE, "little"))
        if data.get("imeie", False):
            result.extend(_encode_string(str(data.get("imei", "")), _TID_IMEI_SIZE))
        if data.get("imsie", False):
            result.extend(_encode_string(str(data.get("imsi", "")), _TID_IMSI_SIZE))
        if data.get("lngce", False):
            result.extend(_encode_string(str(data.get("lngc", "rus")), _TID_LNGC_SIZE))
        if data.get("nide", False):
            nid = data.get("nid", b"\x00\x00\x00")
            if isinstance(nid, str):
                nid = bytes([int(x) for x in nid.split("-")])
            result.extend(nid[:_TID_NID_SIZE])
        if data.get("bse", False):
            result.extend(int(data.get("bs", 1024)).to_bytes(_TID_BS_SIZE, "little"))
        if data.get("mne", False):
            result.extend(_encode_string(data.get("msisdn", ""), _TID_MSISDN_SIZE))

        return bytes(result)


# ──────────────────────────────────────────────────────────────
# SRT=2 MODULE_DATA
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class ModuleDataParser:
    srt = 2
    name = "MODULE_DATA"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < _MODULE_DATA_MIN_SIZE:
            raise ValueError(f"MODULE_DATA too short: {len(raw)}")
        offset = 0
        mt = raw[offset]
        offset += 1
        vid = int.from_bytes(raw[offset:offset+4], "little")
        offset += 4
        fwv = int.from_bytes(raw[offset:offset+2], "little")
        offset += 2
        swv = int.from_bytes(raw[offset:offset+2], "little")
        offset += 2
        md = raw[offset]
        offset += 1
        st = raw[offset]
        offset += 1

        srn = _decode_string_until_null(raw[offset:])
        offset += len(srn) + 1
        dscr = _decode_string_until_null(raw[offset:])

        return {"mt": mt, "vid": vid, "fwv": fwv, "swv": swv, "md": md, "st": st, "srn": srn, "dscr": dscr}

    def serialize(self, data: dict[str, Any]) -> bytes:
        result = bytearray()
        result.append(data.get("mt", 1))
        result.extend(data.get("vid", 0).to_bytes(4, "little"))
        result.extend(data.get("fwv", 0).to_bytes(2, "little"))
        result.extend(data.get("swv", 0).to_bytes(2, "little"))
        result.append(data.get("md", 0))
        result.append(data.get("st", 1))
        srn = data.get("srn", "")
        result.extend(srn.encode("cp1251") if isinstance(srn, str) else srn)
        result.append(0x00)
        dscr = data.get("dscr", "")
        result.extend(dscr.encode("cp1251") if isinstance(dscr, str) else dscr)
        result.append(0x00)
        return bytes(result)


# ──────────────────────────────────────────────────────────────
# SRT=3 VEHICLE_DATA
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class VehicleDataParser:
    srt = 3
    name = "VEHICLE_DATA"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < _VEHICLE_DATA_SIZE:
            raise ValueError(f"VEHICLE_DATA too short: {len(raw)}")
        vin = _decode_string(raw[0:17])
        vht = int.from_bytes(raw[17:21], "little")
        vpst = int.from_bytes(raw[21:25], "little")
        return {"vin": vin, "vht": vht, "vpst": vpst}

    def serialize(self, data: dict[str, Any]) -> bytes:
        vin = str(data.get("vin", ""))
        vin_bytes = vin.encode("cp1251")[:_VEHICLE_VIN_SIZE].ljust(_VEHICLE_VIN_SIZE, b"\x00")
        vht_bytes = int(data.get("vht", 0)).to_bytes(_VEHICLE_VHT_SIZE, "little")
        vpst_bytes = int(data.get("vpst", 0)).to_bytes(_VEHICLE_VPST_SIZE, "little")
        result: bytes = vin_bytes + vht_bytes + vpst_bytes
        return result


# ──────────────────────────────────────────────────────────────
# SRT=6 AUTH_PARAMS
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class AuthParamsParser:
    srt = 6
    name = "AUTH_PARAMS"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 1:
            raise ValueError(f"AUTH_PARAMS too short: {len(raw)}")
        offset = 0
        flg = raw[offset]
        offset += 1
        ena = bool(flg & 0x01)
        pke = bool((flg >> 1) & 0x01)
        isle = bool((flg >> 2) & 0x01)
        mse = bool((flg >> 3) & 0x01)
        sse = bool((flg >> 4) & 0x01)
        exe = bool((flg >> 5) & 0x01)

        pkl = pbk = isl = is_data = msz = ms = ssl = ss = exp = None

        if pke and offset + 2 <= len(raw):
            pkl = int.from_bytes(raw[offset:offset+2], "little")
            offset += 2
            if offset + pkl <= len(raw):
                pbk = raw[offset:offset+pkl]
                offset += pkl

        if isle and offset + 2 <= len(raw):
            isl = int.from_bytes(raw[offset:offset+2], "little")
            offset += 2
            if offset + isl <= len(raw):
                is_data = raw[offset:offset+isl]
                offset += isl

        if mse and offset + 2 <= len(raw):
            msz = int.from_bytes(raw[offset:offset+2], "little")
            offset += 2
            if offset + msz <= len(raw):
                ms = raw[offset:offset+msz]
                offset += msz

        if sse and offset + 2 <= len(raw):
            ssl = int.from_bytes(raw[offset:offset+2], "little")
            offset += 2
            if offset + ssl <= len(raw):
                ss = raw[offset:offset+ssl]
                offset += ssl

        if exe and offset < len(raw):
            offset += 1  # разделитель 0x00
            exp_end = raw.find(b"\x00", offset)
            if exp_end != -1:
                exp = raw[offset:exp_end]
                offset = exp_end + 1

        return {
            "flg": flg, "ena": ena, "pke": pke, "isle": isle,
            "mse": mse, "sse": sse, "exe": exe,
            "pkl": pkl, "pbk": pbk, "isl": isl, "is": is_data,
            "msz": msz, "ms": ms, "ssl": ssl, "ss": ss, "exp": exp,
        }

    def serialize(self, data: dict[str, Any]) -> bytes:
        flg = data.get("flg", 0)
        if data.get("ena", False):
            flg |= 0x01
        if data.get("pke", False):
            flg |= 0x02
        if data.get("isle", False):
            flg |= 0x04
        if data.get("mse", False):
            flg |= 0x08
        if data.get("sse", False):
            flg |= 0x10
        if data.get("exe", False):
            flg |= 0x20

        result = bytearray([flg])

        pbk = data.get("pbk")
        if pbk:
            result.extend(len(pbk).to_bytes(2, "little"))
            result.extend(pbk)

        is_data = data.get("is")
        if is_data:
            result.extend(len(is_data).to_bytes(2, "little"))
            result.extend(is_data)

        ms = data.get("ms")
        if ms:
            result.extend(len(ms).to_bytes(2, "little"))
            result.extend(ms)

        ss = data.get("ss")
        if ss:
            result.extend(len(ss).to_bytes(2, "little"))
            result.extend(ss)

        exp = data.get("exp")
        if data.get("exe", False) or exp:
            result.append(0x00)
            if exp:
                result.extend(exp)
                result.append(0x00)

        return bytes(result)


# ──────────────────────────────────────────────────────────────
# SRT=7 AUTH_INFO
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class AuthInfoParser:
    srt = 7
    name = "AUTH_INFO"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 2:
            raise ValueError(f"AUTH_INFO too short: {len(raw)}")
        offset = 0

        unm_end = raw.find(b"\x00", offset)
        if unm_end == -1:
            raise ValueError("No null terminator after UNM")
        unm = _decode_string(raw[offset:unm_end])
        offset = unm_end + 1

        upsw_end = raw.find(b"\x00", offset)
        if upsw_end == -1:
            raise ValueError("No null terminator after UPSW")
        upsw = _decode_string(raw[offset:upsw_end])
        offset = upsw_end + 1

        ss = None
        if offset < len(raw):
            ss = _decode_string(raw[offset:])

        return {"unm": unm, "upsw": upsw, "ss": ss}

    def serialize(self, data: dict[str, Any]) -> bytes:
        result = bytearray()
        unm = data.get("unm", "")
        result.extend(unm.encode("cp1251") if isinstance(unm, str) else unm)
        result.append(0x00)

        upsw = data.get("upsw", "")
        result.extend(upsw.encode("cp1251") if isinstance(upsw, str) else upsw)
        result.append(0x00)

        ss = data.get("ss")
        if ss is not None:
            result.extend(ss.encode("cp1251") if isinstance(ss, str) else ss)
            result.append(0x00)

        return bytes(result)


# ──────────────────────────────────────────────────────────────
# SRT=8 SERVICE_INFO
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class ServiceInfoParser:
    srt = 8
    name = "SERVICE_INFO"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 1:
            raise ValueError(f"SERVICE_INFO too short: {len(raw)}")
        srvp = raw[0]
        srva = bool((srvp >> 7) & 0x01)
        srvrp = srvp & 0x03

        services = []
        offset = 1
        while offset + 2 < len(raw):
            st = raw[offset]
            offset += 1
            sst = raw[offset]
            offset += 1
            srvp_svc = raw[offset]
            offset += 1
            services.append({
                "st": st, "sst": sst, "srvp": srvp_svc,
                "srva": bool((srvp_svc >> 7) & 0x01),
                "srvrp": srvp_svc & 0x03,
            })

        return {"srvp": srvp, "srva": srva, "srvrp": srvrp, "services": services}

    def serialize(self, data: dict[str, Any]) -> bytes:
        srvp = data.get("srvp", 0)
        if data.get("srva", False):
            srvp |= 0x80
        srvrp = data.get("srvrp", 0) & 0x03
        srvp = (srvp & ~0x03) | srvrp

        result = bytearray([srvp])
        for svc in data.get("services", []):
            if isinstance(svc, dict):
                st = svc.get("st", 0)
                sst = svc.get("sst", 0)
                srvp_svc = svc.get("srvp", 0)
                if svc.get("srva", False):
                    srvp_svc |= 0x80
                srvrp_svc = svc.get("srvrp", 0) & 0x03
                srvp_svc = (srvp_svc & ~0x03) | srvrp_svc
                result.extend([st, sst, srvp_svc])
            else:
                result.extend([svc, 0, 0])
        return bytes(result)


# ──────────────────────────────────────────────────────────────
# SRT=9 RESULT_CODE
# ──────────────────────────────────────────────────────────────

_RESULT_CODES = {
    0: "OK", 1: "IN_PROGRESS", 128: "UNS_PROTOCOL", 129: "DECRYPT_ERROR",
    130: "PROC_DENIED", 131: "INC_HEADERFORM", 132: "INC_DATAFORM",
    133: "UNS_TYPE", 134: "NOTEN_PARAMS", 135: "DBL_PROC",
    136: "PROC_SRC_DENIED", 137: "HEADERCRC_ERROR", 138: "DATACRC_ERROR",
    139: "INVDATALEN", 140: "ROUTE_NFOUND", 141: "ROUTE_CLOSED",
    142: "ROUTE_DENIED", 143: "INVADDR", 144: "TTLEXPIRED",
    145: "NO_ACK", 146: "OBJ_NFOUND", 147: "EVNT_NFOUND",
    148: "SRVC_NFOUND", 149: "SRVC_DENIED", 150: "SRVC_UNKN",
    151: "AUTH_DENIED", 152: "ALREADY_EXISTS", 153: "ID_NFOUND",
    154: "INC_DATETIME",
}


@register_subrecord  # type: ignore[arg-type]
class ResultCodeParser:
    srt = 9
    name = "RESULT_CODE"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 1:
            return {"rcd": 0, "rcd_text": "OK"}
        rcd = raw[0]
        return {"rcd": rcd, "rcd_text": _RESULT_CODES.get(rcd, f"Unknown ({rcd})")}

    def serialize(self, data: dict[str, Any]) -> bytes:
        return bytes([data.get("rcd", 0)])


# ──────────────────────────────────────────────────────────────
# SRT=20 ACCEL_DATA
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class AccelDataParser:
    srt = 20
    name = "ACCEL_DATA"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 5:
            raise ValueError(f"ACCEL_DATA too short: {len(raw)}")
        offset = 0
        sa = raw[offset]
        offset += 1
        atm = int.from_bytes(raw[offset:offset+4], "little")
        offset += 4

        measurements = []
        for _ in range(sa):
            if offset + 8 > len(raw):
                break
            rtm = int.from_bytes(raw[offset:offset+2], "little")
            offset += 2
            xaav = int.from_bytes(raw[offset:offset+2], "little", signed=True)
            offset += 2
            yaav = int.from_bytes(raw[offset:offset+2], "little", signed=True)
            offset += 2
            zaav = int.from_bytes(raw[offset:offset+2], "little", signed=True)
            offset += 2
            measurements.append({
                "rtm": rtm,
                "xaav": xaav * 0.1,
                "yaav": yaav * 0.1,
                "zaav": zaav * 0.1,
            })

        return {"sa": sa, "atm": atm, "measurements": measurements}

    def serialize(self, data: dict[str, Any]) -> bytes:
        measurements = data.get("measurements", [])
        result = bytearray()
        result.append(len(measurements))
        result.extend(data.get("atm", 0).to_bytes(4, "little"))

        for m in measurements:
            rtm = int(m.get("rtm", 0))
            result.extend(rtm.to_bytes(2, "little"))
            xaav = round(m.get("xaav", 0) / 0.1)
            result.extend(xaav.to_bytes(2, "little", signed=True))
            yaav = round(m.get("yaav", 0) / 0.1)
            result.extend(yaav.to_bytes(2, "little", signed=True))
            zaav = round(m.get("zaav", 0) / 0.1)
            result.extend(zaav.to_bytes(2, "little", signed=True))

        return bytes(result)


# ──────────────────────────────────────────────────────────────
# SRT=33 SERVICE_PART_DATA
# ──────────────────────────────────────────────────────────────

def _parse_odh(data: bytes) -> dict[str, Any]:
    """Разобрать ODH (Object Data Header)."""
    if len(data) < 7:
        raise ValueError(f"ODH too short: {len(data)}")
    offset = 0
    oa = data[offset]
    offset += 1
    ot_mt = data[offset]
    offset += 1
    ot = (ot_mt >> 6) & 0x03
    mt = ot_mt & 0x3F
    cmi = data[offset]
    offset += 1
    ver = int.from_bytes(data[offset:offset+2], "little")
    major = (ver >> 8) & 0xFF
    minor = ver & 0xFF
    offset += 2
    wos = int.from_bytes(data[offset:offset+2], "little")
    offset += 2

    file_name = ""
    fn_start = offset
    while offset < len(data) and data[offset] != 0x00:
        offset += 1
    if offset > fn_start:
        try:
            file_name = data[fn_start:offset].decode("cp1251")
        except UnicodeDecodeError:
            file_name = data[fn_start:offset].decode("utf-8", errors="replace")

    return {
        "oa": oa, "ot": ot, "mt": mt, "cmi": cmi,
        "version": (major, minor), "whole_signature": wos,
        "file_name": file_name,
    }


@register_subrecord  # type: ignore[arg-type]
class ServicePartDataParser:
    srt = 33
    name = "SERVICE_PART_DATA"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 7:
            raise ValueError(f"SERVICE_PART_DATA too short: {len(raw)}")
        offset = 0
        entity_id = int.from_bytes(raw[offset:offset+2], "little")
        offset += 2
        part_number = int.from_bytes(raw[offset:offset+2], "little")
        offset += 2
        total_parts = int.from_bytes(raw[offset:offset+2], "little")
        offset += 2

        odh = odh_parsed = None
        if part_number == 1 and len(raw) >= 8:
            delimiter_pos = -1
            for i in range(offset + 7, min(len(raw), offset + _ODH_MAX_SIZE)):
                if raw[i] == 0x00:
                    delimiter_pos = i
                    break
            if delimiter_pos != -1:
                odh_end = delimiter_pos + 1
                odh = raw[offset:odh_end]
                odh_parsed = _parse_odh(odh)
                offset = odh_end

        od = raw[offset:]
        return {
            "id": entity_id, "pn": part_number, "epq": total_parts,
            "odh": odh, "od": od, "odh_parsed": odh_parsed,
        }

    def serialize(self, data: dict[str, Any]) -> bytes:
        result = bytearray()
        result.extend(data.get("id", 0).to_bytes(2, "little"))
        result.extend(data.get("pn", 1).to_bytes(2, "little"))
        result.extend(data.get("epq", 1).to_bytes(2, "little"))

        odh = data.get("odh")
        if data.get("pn", 1) == 1 and odh is not None:
            result.extend(odh)

        od = data.get("od", b"")
        result.extend(od)
        return bytes(result)


# ──────────────────────────────────────────────────────────────
# SRT=34 SERVICE_FULL_DATA
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class ServiceFullDataParser:
    srt = 34
    name = "SERVICE_FULL_DATA"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 8:
            raise ValueError(f"SERVICE_FULL_DATA too short: {len(raw)}")
        delimiter_pos = -1
        for i in range(7, min(len(raw), _ODH_MAX_SIZE)):
            if raw[i] == 0x00:
                delimiter_pos = i
                break
        if delimiter_pos == -1:
            raise ValueError("No ODH delimiter found")

        odh_end = delimiter_pos + 1
        odh = raw[:odh_end]
        od = raw[odh_end:]
        return {"odh": odh, "od": od, "odh_parsed": _parse_odh(odh)}

    def serialize(self, data: dict[str, Any]) -> bytes:
        odh: bytes = data.get("odh", b"") if isinstance(data.get("odh", b""), bytes) else b""
        od: bytes = data.get("od", b"") if isinstance(data.get("od", b""), bytes) else b""
        result: bytes = odh + od
        return result


# ──────────────────────────────────────────────────────────────
# SRT=51 COMMAND_DATA
# ──────────────────────────────────────────────────────────────

# Оставляем для обратной совместимости, но используем Charset enum
_CHARSETS = {
    0: "CP-1251", 1: "ASCII", 2: "BINARY", 3: "Latin1",
    4: "BINARY", 5: "JIS", 6: "Cyrillic", 7: "Latin/Hebrew", 8: "UCS2",
}


@register_subrecord  # type: ignore[arg-type]
class CommandDataParser:
    srt = 51
    name = "COMMAND_DATA"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < _COMMAND_DATA_MIN_SIZE:
            raise ValueError(f"COMMAND_DATA too short: {len(raw)}")
        offset = 0
        ct_cct = raw[offset]
        offset += 1
        ct = (ct_cct >> 4) & 0x0F
        cct = ct_cct & 0x0F

        cid = int.from_bytes(raw[offset:offset+4], "little")
        offset += 4
        sid = int.from_bytes(raw[offset:offset+4], "little")
        offset += 4

        flags = raw[offset]
        offset += 1
        acfe = bool((flags >> 7) & 0x01)
        chsfe = bool((flags >> 6) & 0x01)

        chs = None
        if chsfe and offset < len(raw):
            chs = raw[offset]
            offset += 1

        acl = ac = None
        if acfe and offset < len(raw):
            acl = raw[offset]
            offset += 1
            if offset + acl <= len(raw):
                ac = raw[offset:offset+acl]
                offset += acl

        # Парсинг CD (Command Data) в зависимости от CT
        cd_data: dict[str, Any] | bytes = raw[offset:]
        if len(raw) > offset:
            try:
                cd_data = self._parse_cd_data(ct, raw[offset:])
            except Exception:
                cd_data = raw[offset:]  # Fallback to raw bytes

        return {
            "ct": ct, "cct": cct, "cid": cid, "sid": sid,
            "acfe": acfe, "chsfe": chsfe, "chs": chs,
            "chs_text": Charset(chs).name if chs is not None else None,
            "ct_text": CommandType(ct).name if ct in [e.value for e in CommandType] else f"Unknown(0x{ct:02X})",
            "cct_text": ConfirmationType(cct).name if cct in [e.value for e in ConfirmationType] else f"Unknown(0x{cct:02X})",
            "acl": acl, "ac": ac, "cd": cd_data,
        }

    def serialize(self, data: dict[str, Any]) -> bytes:
        ct = int(data.get("ct", 0))
        cct = int(data.get("cct", 0))
        result: bytes = bytes([((ct & 0x0F) << 4) | (cct & 0x0F)])
        result += int(data.get("cid", 0)).to_bytes(4, "little")
        result += int(data.get("sid", 0)).to_bytes(4, "little")

        acfe = bool(data.get("acfe", False))
        chsfe = bool(data.get("chsfe", False))
        flags = (0x80 if acfe else 0x00) | (0x40 if chsfe else 0x00)

        if chsfe:
            result += bytes([flags, int(data.get("chs", 0))])
        else:
            result += bytes([flags])

        if acfe:
            ac = data.get("ac", b"")
            if isinstance(ac, str):
                ac_bytes = ac.encode("cp1251")
                result += bytes([len(ac_bytes)]) + ac_bytes
            elif isinstance(ac, bytes):
                result += bytes([len(ac)]) + ac
            else:
                result += bytes([0])

        # Сериализация CD (Command Data)
        cd = data.get("cd", b"")
        if isinstance(cd, dict):
            cd_bytes = self._serialize_cd_data(ct, cd)
            result += cd_bytes
        elif isinstance(cd, bytes):
            result += cd
        return result

    # ──────────────────────────────────────────────────────
    # Методы парсинга CD (Command Data)
    # ──────────────────────────────────────────────────────

    def _parse_cd_data(self, ct: int, cd_bytes: bytes) -> dict[str, Any] | bytes:
        """Парсинг CD в зависимости от CT (Command Type)."""
        if ct == CommandType.COM:
            return self._parse_cd_com(cd_bytes)
        elif ct == CommandType.COMCONF:
            return self._parse_cd_comconf(cd_bytes)
        elif ct in (CommandType.MSGCONF, CommandType.DELIV):
            return self._parse_cd_conf(cd_bytes)
        else:
            # Для остальных возвращаем raw bytes
            return cd_bytes

    def _parse_cd_com(self, cd: bytes) -> dict[str, Any]:
        """CT_COM (5) - Таблица 30: Формат команды автомобильной системы."""
        if len(cd) < 5:
            return {"raw": cd}

        offset = 0
        adr = int.from_bytes(cd[offset:offset+2], "little")
        offset += 2

        act_sz = cd[offset]
        offset += 1
        sz = (act_sz >> 5) & 0x07   # Старшие 3 бита
        act = act_sz & 0x1F          # Младшие 5 бит

        ccd = int.from_bytes(cd[offset:offset+2], "little")
        offset += 2

        dt = cd[offset:] if offset < len(cd) else b""

        return {
            "adr": adr,
            "act": act, "act_text": ActionType(act).name if act in [e.value for e in ActionType] else f"Unknown({act})",
            "sz": sz,
            "ccd": ccd, "ccd_text": COMMAND_CODES.get(ccd, f"Unknown(0x{ccd:04X})"),
            "dt": dt,
        }

    def _parse_cd_comconf(self, cd: bytes) -> dict[str, Any]:
        """CT_COMCONF (1) - Таблица 31: Формат подтверждения на команду УСВ."""
        if len(cd) < 4:
            return {"raw": cd}

        offset = 0
        adr = int.from_bytes(cd[offset:offset+2], "little")
        offset += 2

        ccd = int.from_bytes(cd[offset:offset+2], "little")
        offset += 2

        dt = cd[offset:] if offset < len(cd) else b""

        return {
            "adr": adr,
            "ccd": ccd, "ccd_text": COMMAND_CODES.get(ccd, f"Unknown(0x{ccd:04X})"),
            "dt": dt,
        }

    def _parse_cd_conf(self, cd: bytes) -> dict[str, Any]:
        """Для CT_MSGCONF, CT_DELIV - аналогично таблице 31."""
        return self._parse_cd_comconf(cd)

    # ──────────────────────────────────────────────────────
    # Методы сериализации CD (Command Data)
    # ──────────────────────────────────────────────────────

    def _serialize_cd_data(self, ct: int, cd: dict) -> bytes:
        """Сериализация CD в зависимости от CT."""
        if ct == CommandType.COM:
            return self._serialize_cd_com(cd)
        elif ct == CommandType.COMCONF:
            return self._serialize_cd_comconf(cd)
        elif ct in (CommandType.MSGCONF, CommandType.DELIV):
            return self._serialize_cd_conf(cd)
        return b""

    def _serialize_cd_com(self, cd: dict) -> bytes:
        """Сериализация для CT_COM (таблица 30)."""
        result = int(cd.get("adr", 0)).to_bytes(2, "little")

        act = int(cd.get("act", 0))
        sz = int(cd.get("sz", 0))
        result += bytes([(sz << 5) | (act & 0x1F)])

        result += int(cd.get("ccd", 0)).to_bytes(2, "little")

        dt = cd.get("dt", b"")
        if isinstance(dt, str):
            # Автоматически определяем кодировку и кодируем
            dt_bytes = dt.encode("cp1251")
            result += dt_bytes
        elif isinstance(dt, bytes):
            result += dt

        return result

    def _serialize_cd_comconf(self, cd: dict) -> bytes:
        """Сериализация для CT_COMCONF (таблица 31)."""
        result = int(cd.get("adr", 0)).to_bytes(2, "little")
        result += int(cd.get("ccd", 0)).to_bytes(2, "little")

        dt = cd.get("dt", b"")
        if isinstance(dt, str):
            dt_bytes = dt.encode("cp1251")
            result += dt_bytes
        elif isinstance(dt, bytes):
            result += dt

        return result

    def _serialize_cd_conf(self, cd: dict) -> bytes:
        """Для CT_MSGCONF, CT_DELIV - аналогично таблице 31."""
        return self._serialize_cd_comconf(cd)


# ──────────────────────────────────────────────────────────────
# SRT=62 RAW_MSD_DATA
# ──────────────────────────────────────────────────────────────

@register_subrecord
class RawMsdDataParser:
    srt = 62
    name = "RAW_MSD_DATA"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < 1:
            raise ValueError(f"RAW_MSD_DATA too short: {len(raw)}")
        fm = raw[0]
        msd = raw[1:]
        return {"fm": fm, "msd": msd, "msd_len": len(msd)}

    def serialize(self, data: dict | bytes) -> bytes:
        if isinstance(data, bytes):
            return data
        result = bytearray([data.get("fm", 1)])
        result.extend(data.get("msd", b""))
        return bytes(result)


# ──────────────────────────────────────────────────────────────
# SRT=63 TRACK_DATA
# ──────────────────────────────────────────────────────────────

@register_subrecord  # type: ignore[arg-type]
class TrackDataParser:
    srt = 63
    name = "TRACK_DATA"

    def parse(self, raw: bytes) -> dict[str, Any]:
        if len(raw) < _TRACK_DATA_MIN_SIZE:
            raise ValueError(f"TRACK_DATA too short: {len(raw)}")
        offset = 0
        sa = raw[offset]
        offset += 1
        atm = int.from_bytes(raw[offset:offset+4], "little")
        offset += 4

        track_points = []
        for _ in range(sa):
            if offset >= len(raw):
                break
            header = raw[offset]
            offset += 1
            tnde = bool((header >> 7) & 0x01)
            lohs = bool((header >> 6) & 0x01)
            lahs = bool((header >> 5) & 0x01)
            sdfe = bool((header >> 4) & 0x01)
            spfe = bool((header >> 3) & 0x01)
            rtm = header & 0x07

            point: dict = {"tnde": tnde, "lohs": lohs, "lahs": lahs, "sdfe": sdfe, "spfe": spfe, "rtm": rtm}
            dirh = 0

            if offset + 4 <= len(raw):
                lat_abs = int.from_bytes(raw[offset:offset+4], "little")
                point["lat"] = -lat_abs if lahs else lat_abs
                offset += 4

            if offset + 4 <= len(raw):
                lon_abs = int.from_bytes(raw[offset:offset+4], "little")
                point["lon"] = -lon_abs if lohs else lon_abs
                offset += 4

            spdh = 0
            if spfe and offset + 3 <= len(raw):
                spdl = int.from_bytes(raw[offset:offset+2], "little")
                dirh_spdh = raw[offset + 2]
                spdh = dirh_spdh & 0x01
                dirh = (dirh_spdh >> 1) & 0x01
                spd_raw = ((spdh << 14) | (spdl & 0x3FFF))
                point["spd"] = spd_raw * 0.01
                point["_spdh"] = spdh
                point["_dirh"] = dirh
                offset += 3

            if sdfe and offset < len(raw):
                dir_raw = raw[offset]
                dir_full = (dirh << 8) | dir_raw
                point["sd"] = dir_full
                offset += 1

            track_points.append(point)

        return {"sa": sa, "atm": atm, "track_points": track_points}

    def serialize(self, data: dict[str, Any]) -> bytes:
        track_points = data.get("track_points", [])
        result = bytearray()
        result.append(len(track_points))
        result.extend(data.get("atm", 0).to_bytes(4, "little"))

        for point in track_points:
            lahs = point.get("lahs", 1 if point.get("lat", 0) < 0 else 0)
            lohs = point.get("lohs", 1 if point.get("lon", 0) < 0 else 0)
            sdfe = 1 if "sd" in point else 0
            spfe = 1 if point.get("spd") is not None else 0
            rtm = point.get("rtm", 0) & 0x07
            tnde = 1 if point.get("tnde", False) else 0

            header = (tnde << 7) | (lohs << 6) | (lahs << 5) | (sdfe << 4) | (spfe << 3) | rtm
            result.append(header)

            if "lat" in point:
                result.extend(abs(int(point["lat"])).to_bytes(4, "little"))
            if "lon" in point:
                result.extend(abs(int(point["lon"])).to_bytes(4, "little"))

            if "spd" in point:
                spd_raw = round(point["spd"] / 0.01)
                spd_raw = max(0, min(32767, spd_raw))
                spdh = (spd_raw >> 14) & 0x01
                spdl = spd_raw & 0x3FFF
                result.extend(spdl.to_bytes(2, "little"))
                dirh = point.get("_dirh", 0)
                result.append((dirh << 1) | spdh)

            if "sd" in point:
                dir_full = int(point["sd"]) & 0x1FF
                dirh = (dir_full >> 8) & 0x01
                dir_low = dir_full & 0xFF
                if "spd" in point:
                    last = len(result) - 1
                    result[last] = result[last] | (dirh << 1)
                result.append(dir_low)

        return bytes(result)
