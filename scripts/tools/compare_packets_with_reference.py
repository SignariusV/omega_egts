"""Сравнение генерируемых пакетов с эталонными данными из data/packets/.

Сравнивает пакеты, созданные через библиотеку EGTS, с эталонными HEX из Excel-файлов.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.emulators.emulate_usv_combined_build import (
    build_term_identity_packet,
    build_vehicle_data_packet,
    build_comconf_packet,
    build_result_code_response_packet,
    USV_IMEI,
    USV_IMSI,
    USV_UNIT_ID,
)

# ───────── Эталонные пакеты из data/packets/all_packets_correct_20260406_190414.json ─────────

REFERENCE = {
    # Команды верификации (PLATFORM -> УСВ)
    "GPRS_APN": {
        "hex": "0100000B0021001B0001321A002A00400404331700500000000000000000000000020302696E7465726E65740D48",
        "direction": "PLATFORM -> УСВ",
        "description": "Команда EGTS_GPRS_APN (0x0203) с CID=0, данные='internet'",
    },
    "COMCONF_CID0": {
        "hex": "0100000B001400270001DC0D004600800404330A0010000000000000000000CE40",
        "direction": "УСВ -> PLATFORM",
        "description": "Подтверждение COMCONF CID=0 (APN)",
    },
    "SERVER_ADDRESS": {
        "hex": "0100000B002A001C0001AB23002B004004043320005001000000000000000000000204023230302E32302E322E3137313A393039305E55",
        "direction": "PLATFORM -> УСВ",
        "description": "Команда SERVER_ADDRESS (0x0204) с CID=1, данные='200.20.2.171:9090'",
    },
    "COMCONF_CID1": {
        "hex": "0100000B0014002800016D0D004700800404330A0010010000000000000000DC5B",
        "direction": "УСВ -> PLATFORM",
        "description": "Подтверждение COMCONF CID=1 (ADDRESS)",
    },
    "UNIT_ID": {
        "hex": "0100000B001D001D00013216002C0040040433130050020000000000000000000002040400000001BE2C",
        "direction": "PLATFORM -> УСВ",
        "description": "Команда UNIT_ID (0x0404) с CID=2, данные=0x00000001",
    },
    "COMCONF_CID2": {
        "hex": "0100000B0014002900012B0D004800800404330A00100200000000000000002277",
        "direction": "УСВ -> PLATFORM",
        "description": "Подтверждение COMCONF CID=2 (UNIT_ID) с result_data=0x00000001",
    },

    # Пакеты аутентификации (УСВ -> PLATFORM)
    "TERM_IDENTITY": {
        "hex": "0100000B002E002A0001CC270049008001010124000100000016383630383033303636343438333133303235303737303031373135363433390F3A",
        "direction": "УСВ -> PLATFORM",
        "description": "TERM_IDENTITY: TID=1, IMEI=860803066448313, IMSI=250770017156439",
    },
    "VEHICLE_DATA": {
        "hex": "0100000B0023002B0001781C004A00800101031900314434475032354230333831303837373501000000010000006CE1",
        "direction": "УСВ -> PLATFORM",
        "description": "VEHICLE_DATA: VIN=1D4GP25B038108775, VHT=1 (M1), VPST=1 (бензин)",
    },
    "RESULT_CODE": {
        "hex": "0100000B000B002000012604002F0040010109010000BA4C",
        "direction": "PLATFORM -> УСВ",
        "description": "RESULT_CODE: RCD=0 (успех)",
    },
    "RECORD_RESPONSE_AUTH": {
        "hex": "0100000B0010002C00006A20000006004B008001010003002F0000F139",
        "direction": "УСВ -> PLATFORM",
        "description": "RECORD_RESPONSE: CRN=47 (подтверждение RESULT_CODE)",
    },
}


def hex_to_bytes(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)


def parse_packet_structure(raw: bytes, label: str) -> dict:
    """Минимальный парсинг для сравнения структуры пакета."""
    if len(raw) < 16:
        return {"error": "слишком короткий"}

    result = {
        "label": label,
        "length": len(raw),
        "prv": raw[0],
        "hl": raw[2],
        "fdl": int.from_bytes(raw[3:5], "little"),
        "pid": int.from_bytes(raw[5:7], "little"),
        "pt": raw[7],
        "hcs": raw[8],
    }

    # Если RESPONSE
    if result["pt"] & 0x0F == 0x01:
        result["rpid"] = int.from_bytes(raw[9:11], "little")
        result["pr"] = raw[11]
        if len(raw) > 14:
            result["rl"] = int.from_bytes(raw[12:14], "little")
            result["rn"] = int.from_bytes(raw[14:16], "little")

    # Если APPDATA — парсим запись
    if result["pt"] & 0x0F == 0x00:
        if len(raw) > 18:
            result["rl"] = int.from_bytes(raw[9:11], "little")
            result["rn"] = int.from_bytes(raw[11:13], "little")
            rfl = raw[13] if len(raw) > 13 else 0
            result["rfl"] = f"{rfl:02X}"
            sst = raw[14] if len(raw) > 14 else 0
            rst = raw[15] if len(raw) > 15 else 0
            result["sst"] = sst
            result["rst"] = rst

            # Ищем SRT (Subrecord Type)
            srt_offset = 16
            if len(raw) > srt_offset + 2:
                srt = int.from_bytes(raw[srt_offset : srt_offset + 2], "little")
                result["srt"] = srt
                srl = int.from_bytes(raw[srt_offset + 2 : srt_offset + 4], "little")
                result["srl"] = srl

                # Данные сабрекорда
                srd = raw[srt_offset + 4 : srt_offset + 4 + srl]
                result["srd_hex"] = srd.hex().upper()

                # Для COMMAND_DATA — парсим CT, CID, CCD
                if srt == 51:  # EGTS_SR_COMMAND_DATA
                    if len(srd) >= 10:
                        ct = srd[0]
                        cid = int.from_bytes(srd[1:5], "little")
                        result["ct"] = ct
                        result["cid"] = cid
                        acfe_chsfe = srd[5] if len(srd) > 5 else 0
                        result["acfe_chsfe"] = f"{acfe_chsfe:02X}"
                        adr = int.from_bytes(srd[6:8], "little") if len(srd) > 7 else 0
                        result["adr"] = adr
                        sz_act = srd[8] if len(srd) > 8 else 0
                        result["sz_act"] = f"{sz_act:02X}"
                        ccd = int.from_bytes(srd[9:11], "little") if len(srd) > 10 else 0
                        result["ccd"] = ccd
                        if len(srd) > 11:
                            result["data"] = srd[11:].decode("ascii", errors="replace")

                # Для TERM_IDENTITY — парсим TID, IMEI, IMSI
                elif srt == 1:  # EGTS_SR_TERM_IDENTITY
                    if len(srd) >= 4:
                        tid = int.from_bytes(srd[0:4], "little")
                        result["tid"] = tid
                        flags = srd[4] if len(srd) > 4 else 0
                        result["flags"] = f"{flags:02X}"
                        offset = 5
                        imei_len = srd[offset] if len(srd) > offset else 0
                        offset += 1
                        if imei_len > 0 and len(srd) > offset + imei_len:
                            result["imei"] = srd[offset : offset + imei_len].decode("ascii", errors="replace")
                            offset += imei_len
                        imsi_len = srd[offset] if len(srd) > offset else 0
                        offset += 1
                        if imsi_len > 0 and len(srd) > offset + imsi_len:
                            result["imsi"] = srd[offset : offset + imsi_len].decode("ascii", errors="replace")

                # Для VEHICLE_DATA — парсим VIN, VHT, VPST
                elif srt == 3:  # EGTS_SR_VEHICLE_DATA
                    if len(srd) >= 17:
                        vin_len = srd[0] if len(srd) > 0 else 0
                        if vin_len > 0 and len(srd) >= 1 + vin_len:
                            result["vin"] = srd[1 : 1 + vin_len].decode("ascii", errors="replace")
                        if len(srd) >= 1 + vin_len + 8:
                            vht = int.from_bytes(srd[1 + vin_len : 1 + vin_len + 4], "little")
                            vpst = int.from_bytes(srd[1 + vin_len + 4 : 1 + vin_len + 8], "little")
                            result["vht"] = vht
                            result["vpst"] = vpst

    return result


def compare_packets(generated: bytes, reference: dict, name: str) -> dict:
    """Сравнить сгенерированный пакет с эталоном."""
    ref_bytes = hex_to_bytes(reference["hex"])
    gen_struct = parse_packet_structure(generated, f"{name} (generated)")
    ref_struct = parse_packet_structure(ref_bytes, f"{name} (reference)")

    # Сравнение по байтам
    match_exact = generated == ref_bytes

    # Сравнение длины
    length_match = len(generated) == len(ref_bytes)

    # Сравнение структуры
    structure_matches = {}
    for key in ["prv", "hl", "pt"]:
        if key in gen_struct and key in ref_struct:
            structure_matches[key] = gen_struct[key] == ref_struct[key]

    # Для COMMAND_DATA — сравнение CT, CID, CCD
    if "ct" in gen_struct and "ct" in ref_struct:
        structure_matches["ct"] = gen_struct["ct"] == ref_struct["ct"]
        structure_matches["cid"] = gen_struct.get("cid") == ref_struct.get("cid")
        structure_matches["ccd"] = gen_struct.get("ccd") == ref_struct.get("ccd")
        if "data" in gen_struct and "data" in ref_struct:
            structure_matches["data"] = gen_struct.get("data") == ref_struct.get("data")

    # Для TERM_IDENTITY
    if "tid" in gen_struct and "tid" in ref_struct:
        structure_matches["tid"] = gen_struct.get("tid") == ref_struct.get("tid")
        structure_matches["imei"] = gen_struct.get("imei") == ref_struct.get("imei")
        structure_matches["imsi"] = gen_struct.get("imsi") == ref_struct.get("imsi")

    # Для VEHICLE_DATA
    if "vin" in gen_struct and "vin" in ref_struct:
        structure_matches["vin"] = gen_struct.get("vin") == ref_struct.get("vin")
        structure_matches["vht"] = gen_struct.get("vht") == ref_struct.get("vht")
        structure_matches["vpst"] = gen_struct.get("vpst") == ref_struct.get("vpst")

    # Для RESPONSE
    if "rpid" in gen_struct and "rpid" in ref_struct:
        structure_matches["rpid"] = gen_struct.get("rpid") == ref_struct.get("rpid")
        structure_matches["pr"] = gen_struct.get("pr") == ref_struct.get("pr")

    return {
        "name": name,
        "exact_match": match_exact,
        "length_match": length_match,
        "gen_len": len(generated),
        "ref_len": len(ref_bytes),
        "structure_matches": structure_matches,
        "gen_hex": generated.hex().upper(),
        "ref_hex": reference["hex"],
        "gen_struct": gen_struct,
        "ref_struct": ref_struct,
    }


def main():
    print("=" * 80)
    print("  СРАВНЕНИЕ ГЕНЕРИРУЕМЫХ ПАКЕТОВ С ЭТАЛОННЫМИ")
    print("=" * 80)

    results = []

    # ─── 1. TERM_IDENTITY ───
    gen_ti = build_term_identity_packet(pid=42, rn=73)
    results.append(compare_packets(gen_ti, REFERENCE["TERM_IDENTITY"], "TERM_IDENTITY"))

    # ─── 2. VEHICLE_DATA ───
    # Эталон: VIN=1D4GP25B038108775, VHT=1, VPST=1
    # Наш эмулятор: VIN=USV-EMULATOR (заполненный до 17), VHT=0, VPST=0
    # Для честного сравнения пересоберём с теми же данными
    from libs.egts_protocol_gost2015.gost2015_impl.packet import Packet
    from libs.egts_protocol_gost2015.gost2015_impl.record import Record
    from libs.egts_protocol_gost2015.gost2015_impl.subrecord import Subrecord
    from libs.egts_protocol_gost2015.gost2015_impl.types import (
        PacketType,
        Priority,
        ServiceType,
        SubrecordType,
    )
    from libs.egts_protocol_gost2015.gost2015_impl.services.auth import serialize_vehicle_data

    vd_srd = serialize_vehicle_data({
        "vin": "1D4GP25B038108775",
        "vht": 1,
        "vpst": 1,
    })
    vd_sub = Subrecord(subrecord_type=SubrecordType.EGTS_SR_VEHICLE_DATA, data=vd_srd)
    vd_rec = Record(record_id=74, service_type=ServiceType.EGTS_AUTH_SERVICE, subrecords=[vd_sub])
    vd_pkt = Packet(packet_id=43, packet_type=PacketType.EGTS_PT_APPDATA, priority=Priority.HIGHEST, records=[vd_rec])
    gen_vd = vd_pkt.to_bytes()
    results.append(compare_packets(gen_vd, REFERENCE["VEHICLE_DATA"], "VEHICLE_DATA"))

    # ─── 3. COMCONF CID=0 ───
    gen_cc0 = build_comconf_packet(pid=39, rn=70, cid=0, cct=0)
    results.append(compare_packets(gen_cc0, REFERENCE["COMCONF_CID0"], "COMCONF_CID0"))

    # ─── 4. COMCONF CID=1 ───
    gen_cc1 = build_comconf_packet(pid=40, rn=71, cid=1, cct=0)
    results.append(compare_packets(gen_cc1, REFERENCE["COMCONF_CID1"], "COMCONF_CID1"))

    # ─── 5. COMCONF CID=2 с result_data ───
    gen_cc2 = build_comconf_packet(pid=41, rn=72, cid=2, cct=0, result_data=b"\x00\x00\x00\x01")
    results.append(compare_packets(gen_cc2, REFERENCE["COMCONF_CID2"], "COMCONF_CID2"))

    # ─── 6. RECORD_RESPONSE ───
    gen_rr = build_result_code_response_packet(pid=44, rn=75, confirmed_rn=47)
    results.append(compare_packets(gen_rr, REFERENCE["RECORD_RESPONSE_AUTH"], "RECORD_RESPONSE"))

    # ───────── Вывод результатов ─────────

    print()
    all_pass = True
    for r in results:
        status = "✅" if r["exact_match"] else "⚠"
        if not r["exact_match"]:
            all_pass = False

        print(f"\n{'─' * 80}")
        print(f"  {status} {r['name']}")
        print(f"{'─' * 80}")
        print(f"  Длина:       {r['gen_len']} байт (эталон: {r['ref_len']}) {'✅' if r['length_match'] else '❌'}")
        print(f"  Точное совп: {'✅ ДА' if r['exact_match'] else '❌ НЕТ'}")

        if not r["exact_match"]:
            print(f"\n  Сравнение структуры:")
            for key, match in r["structure_matches"].items():
                icon = "✅" if match else "❌"
                gen_val = r["gen_struct"].get(key, "N/A")
                ref_val = r["ref_struct"].get(key, "N/A")
                print(f"    {icon} {key}: gen={gen_val}, ref={ref_val}")

            print(f"\n  Генерированный HEX:")
            print(f"    {r['gen_hex']}")
            print(f"  Эталонный HEX:")
            print(f"    {r['ref_hex']}")

            # Покажем различия корректно
            gen_bytes = bytes.fromhex(r["gen_hex"])
            ref_bytes = bytes.fromhex(r["ref_hex"])
            max_len = max(len(gen_bytes), len(ref_bytes))
            print(f"\n  Различия по байтам:")
            diff_count = 0
            for i in range(max_len):
                gb = gen_bytes[i] if i < len(gen_bytes) else None
                rb = ref_bytes[i] if i < len(ref_bytes) else None
                if gb != rb:
                    diff_count += 1
                    gb_str = f"{gb:02X}" if gb is not None else "??"
                    rb_str = f"{rb:02X}" if rb is not None else "??"
                    print(f"    [{i:3d}] gen={gb_str}  ref={rb_str}")
                    if diff_count >= 20:
                        print(f"    ... и ещё {diff_count - 20} различий")
                        break

    print(f"\n{'=' * 80}")
    if all_pass:
        print("  ✅ ВСЕ ПАКЕТЫ СОВПАДАЮТ С ЭТАЛОНОМ")
    else:
        passed = sum(1 for r in results if r["exact_match"])
        print(f"  ⚠ {passed}/{len(results)} пакетов совпали точно")
        print("  Различия могут быть в PID, RN, CID (динамические значения)")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
