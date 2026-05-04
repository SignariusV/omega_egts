"""Скрипт для детального сравнения полей эталонных пакетов с библиотекой.

Сравнивает каждое поле из description с распарсенным значением.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import libs.egts._gost2015
from libs.egts.registry import get_protocol


def extract_expected_values(packet_data: dict[str, Any]) -> dict[str, Any]:
    """Извлечь ожидаемые значения из description."""
    desc = packet_data.get("description", "")
    lines = desc.split("\n")

    expected = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line:
            continue

        m = re.match(r"PRV.*?\[BYTE\]", line)
        if m:
            continue

        m = re.match(r"SKID.*?\[BYTE\]", line)
        if m:
            continue

        m = re.match(r"PR.*?PRF=(\d+)", line)
        if m:
            expected["PR"] = int(m.group(1))
            continue

        m = re.match(r"HL[1]?.*?(\d+)\s*байт", line)
        if m:
            expected["header_length"] = int(m.group(1))
            continue

        m = re.match(r"HE.*?Кодирование.*?(?:[\d]+)", line)
        if m:
            continue

        m = re.match(r"FDL.*?SFRD=(\d+)", line)
        if m:
            expected["frame_data_length"] = int(m.group(1))
            continue

        m = re.match(r"PID.*?\(=(\d+)\)", line)
        if m:
            expected["packet_id"] = int(m.group(1))
            continue

        m = re.match(r"PT.*?=(\d+)", line)
        if m:
            expected["packet_type"] = int(m.group(1))
            continue

        m = re.match(r"HCS.*?CRC-8", line)
        if m:
            continue

        m = re.match(r"RL.*?(\d+)\s*байт", line)
        if m:
            expected["record_length"] = int(m.group(1))
            continue

        m = re.match(r"RN.*?\(=(\d+)\)", line)
        if m:
            expected["record_number"] = int(m.group(1))
            continue

        m = re.match(r"RFL.*?", line)
        if m:
            continue

        m = re.match(r"SST.*?", line)
        if m:
            m2 = re.search(r"=(\d+)", lines[i-1] if i > 0 else "")
            if m2:
                expected["source_service_type"] = int(m2.group(1))
            continue

        m = re.match(r"RST.*?", line)
        if m:
            m2 = re.search(r"=(\d+)", lines[i-1] if i > 0 else "")
            if m2:
                expected["recipient_service_type"] = int(m2.group(1))
            continue

        m = re.match(r"SRT.*?Подзапись.*?:", line, re.IGNORECASE)
        if m and i < len(lines):
            m2 = re.search(r"=(\d+)", lines[i])
            if m2:
                expected["subrecord_type"] = int(m2.group(1))
            continue

        m = re.match(r"SRL.*?\(=(\d+)\)", line)
        if m:
            expected["subrecord_length"] = int(m.group(1))
            continue

        m = re.match(r"TID.*?\(=(\d+)\)", line)
        if m:
            expected["tid"] = int(m.group(1))
            continue

        m = re.match(r"Flags.*?=([0-9a-fA-F]+)", line)
        if m:
            expected["flags"] = int(m.group(1), 16)
            continue

        m = re.match(r"IMEI\s+([0-9]+)", line)
        if m:
            expected["imei"] = m.group(1)
            continue

        m = re.match(r"IMSI\s+([0-9]+)", line)
        if m:
            expected["imsi"] = m.group(1)
            continue

        m = re.match(r"VIN.*?:?\s*([0-9A-Z]+)", line)
        if m:
            expected["vin"] = m.group(1)
            continue

        m = re.match(r"VHT.*?\((\w+)\)", line)
        if m:
            expected["vehicle_type"] = m.group(1)
            continue

        m = re.match(r"VPST.*?\((\w+)\)", line)
        if m:
            expected["fuel_type"] = m.group(1)
            continue

        m = re.match(r"RCD.*?=(\d+)", line)
        if m:
            expected["result_code"] = int(m.group(1))
            continue

        m = re.match(r"RPID.*?\(=(\d+)\)", line)
        if m:
            expected["response_packet_id"] = int(m.group(1))
            continue

        m = re.match(r"PR.*?EGTS_PC_(\w+)", line)
        if m:
            expected["processing_result"] = m.group(1)
            continue

        m = re.match(r"CRN.*?\(=(\d+)\)", line)
        if m:
            expected["confirmed_record_number"] = int(m.group(1))
            continue

        m = re.match(r"RST.*?EGTS_PC_(\w+)", line)
        if m:
            expected["record_status"] = m.group(1)
            continue

        m = re.match(r"CT.*?(\d+)", line)
        if m:
            expected["command_type"] = int(m.group(1))
            continue

        m = re.match(r"CID.*?\(=(\d+)\)", line)
        if m:
            expected["command_id"] = int(m.group(1))
            continue

    return expected


def get_parsed_fields(packet, raw: bytes) -> dict[str, Any]:
    """Извлечь поля из распарсенного пакета."""
    fields = {}

    fields["protocol_version"] = packet.protocol_version
    fields["security_key_id"] = packet.security_key_id
    fields["header_length"] = packet.header_length

    if len(raw) > 5:
        fdl = raw[5] | (raw[6] << 8)
        fields["frame_data_length"] = fdl

    fields["packet_id"] = packet.packet_id
    fields["packet_type"] = int(packet.packet_type.value) if hasattr(packet.packet_type, 'value') else packet.packet_type

    if packet.records:
        rec = packet.records[0]
        fields["record_number"] = rec.record_id
        fields["source_service_type"] = int(rec.service_type.value) if hasattr(rec.service_type, 'value') else rec.service_type
        fields["recipient_service_type"] = rec.recipient_service_type

        if rec.subrecords:
            sr = rec.subrecords[0]
            fields["subrecord_type"] = int(sr.subrecord_type.value) if hasattr(sr.subrecord_type, 'value') else sr.subrecord_type
            if isinstance(sr.data, dict):
                for k, v in sr.data.items():
                    if isinstance(v, bytes):
                        fields[k] = v.hex().upper() if v else v
                    else:
                        fields[k] = v

    return fields


def compare_packet(packet_data: dict[str, Any], proto) -> dict[str, Any]:
    """Сравнить эталонные значения с парсингом библиотеки."""
    hex_str = packet_data["hex"].replace(" ", "").strip()
    raw = bytes.fromhex(hex_str)

    result = {
        "sheet": packet_data.get("sheet", "unknown"),
        "parse_error": None,
        "expected": {},
        "parsed": {},
        "differences": [],
    }

    expected = extract_expected_values(packet_data)
    result["expected"] = expected

    parse_result = proto.parse_packet(raw)
    if not parse_result.is_success:
        result["parse_error"] = parse_result.errors
        return result

    parsed = get_parsed_fields(parse_result.packet, raw)
    result["parsed"] = parsed

    for key, exp_val in expected.items():
        if key in parsed:
            par_val = parsed[key]
            if str(exp_val) != str(par_val):
                result["differences"].append({
                    "field": key,
                    "expected": exp_val,
                    "parsed": par_val,
                })

    return result


def main() -> None:
    """Главная функция."""
    print("\n" + "=" * 70)
    print("  DETAILED COMPARISON: Поля эталонных пакетов vs Библиотека")
    print("=" * 70)

    proto = get_protocol("2015")

    packets_file = Path("data/packets/all_packets_correct_20260406_190414.json")
    if not packets_file.exists():
        print(f"❌ Файл не найден: {packets_file}")
        sys.exit(1)

    with open(packets_file, encoding="utf-8") as f:
        packets = json.load(f)

    print(f"\nВсего пакетов: {len(packets)}")

    results: list[dict[str, Any]] = []
    parse_errors = 0
    no_diffs = 0
    with_diffs = 0

    print("\n" + "-" * 70)
    print("Обработка...")

    for i, pkt in enumerate(packets):
        result = compare_packet(pkt, proto)
        results.append(result)

        if result["parse_error"]:
            parse_errors += 1
            print(f"  [{i+1:02d}] ❌ {result['sheet'][:35]:35s} │ PARSE ERROR")
        elif result["differences"]:
            with_diffs += 1
            print(f"  [{i+1:02d}] ⚠️  {result['sheet'][:35]:35s} │ {len(result['differences'])} diff(s)")
        else:
            no_diffs += 1
            print(f"  [{i+1:02d}] ✅ {result['sheet'][:35]:35s}")

    print("-" * 70)

    print(f"\nИТОГИ:")
    print(f"  ✅ Без различий: {no_diffs}/{len(packets)}")
    print(f"  ⚠️  С различиями: {with_diffs}/{len(packets)}")
    print(f"  ❌ Ошибки парса: {parse_errors}/{len(packets)}")

    diff_results = [r for r in results if r["differences"]]
    if diff_results:
        print(f"\n" + "=" * 70)
        print("  РАЗЛИЧИЯ")
        print("=" * 70)
        for r in diff_results[:10]:
            print(f"\n--- {r['sheet']} ---")
            for d in r["differences"]:
                print(f"  {d['field']}: expected={d['expected']}, parsed={d['parsed']}")

    print("\n" + "=" * 70)
    print("  DONE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()