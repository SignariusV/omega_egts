"""Скрипт для проверки roundtrip всех эталонных пакетов.

Запустить:
    python -m examples.packet_verification

Сравнивает:
1. Парсинг эталонного HEX → структура
2. Сборка структуры → HEX
3. Побайтовое сравнение
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import libs.egts._gost2015
from libs.egts.registry import get_protocol


def hex_dump(data: bytes, width: int = 32) -> str:
    """Красивый hex-dump."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        lines.append(f"  {i:04d}: {hex_part}")
    return "\n".join(lines)


def analyze_packet(packet_data: dict[str, Any], proto) -> dict[str, Any]:
    """Проверить один пакет: parse -> build -> compare."""
    hex_str = packet_data["hex"].replace(" ", "").strip()
    raw = bytes.fromhex(hex_str)

    result = {
        "sheet": packet_data.get("sheet", "unknown"),
        "hex_length": packet_data.get("hex_length_bytes", len(raw)),
        "parse_error": None,
        "build_error": None,
        "match": False,
        "original_hex": hex_str,
        "rebuilt_hex": None,
        "parsed": None,
    }

    parse_result = proto.parse_packet(raw)
    if not parse_result.is_success:
        result["parse_error"] = parse_result.errors
        return result

    result["parsed"] = {
        "packet_id": parse_result.packet.packet_id,
        "packet_type": str(parse_result.packet.packet_type),
        "records": len(parse_result.packet.records),
    }

    rebuilt = proto.build_packet(parse_result.packet)
    result["rebuilt_hex"] = rebuilt.hex().upper()

    result["match"] = result["original_hex"] == result["rebuilt_hex"]

    if not result["match"]:
        result["diff"] = {
            "original_len": len(result["original_hex"]),
            "rebuilt_len": len(result["rebuilt_hex"]),
        }

    return result


def main() -> None:
    """Главная функция."""
    print("\n" + "=" * 70)
    print("  VERIFICATION: Сравнение эталонных пакетов с библиотекой")
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
    build_errors = 0
    matches = 0

    print("\n" + "-" * 70)
    print("Обработка пакетов...")

    for i, pkt in enumerate(packets):
        result = analyze_packet(pkt, proto)
        results.append(result)

        if result["parse_error"]:
            parse_errors += 1
            print(f"  [{i+1:02d}] ❌ {result['sheet'][:40]:40s} │ PARSE ERROR")
        elif result["build_error"]:
            build_errors += 1
            print(f"  [{i+1:02d}] ❌ {result['sheet'][:40]:40s} │ BUILD ERROR")
        elif result["match"]:
            matches += 1
            print(f"  [{i+1:02d}] ✅ {result['sheet'][:40]:40s}")
        else:
            print(f"  [{i+1:02d}] ⚠️  {result['sheet'][:40]:40s} │ MISMATCH")

    print("-" * 70)

    print(f"\nИТОГИ:")
    print(f"  ✅ Совпадение:    {matches}/{len(packets)}")
    print(f"  ❌ Ошибки парса:  {parse_errors}/{len(packets)}")
    print(f"  ❌ Ошибки сборки: {build_errors}/{len(packets)}")
    print(f"  ⚠️  Не совпадение: {len(packets) - matches - parse_errors - build_errors}/{len(packets)}")

    mismatches = [r for r in results if not r["match"] and not r["parse_error"] and not r["build_error"]]
    if mismatches:
        print(f"\n" + "=" * 70)
        print("  ДЕТАЛИ НЕСОВПАДЕНИЙ")
        print("=" * 70)
        for m in mismatches:
            print(f"\n--- {m['sheet']} ---")
            print(f"  Оригинал: {m['original_hex'][:64]}...")
            print(f"  Собрано:  {m['rebuilt_hex'][:64]}...")
            if m.get("diff"):
                print(f"  Размер: ориг={m['diff']['original_len']}, собр={m['diff']['rebuilt_len']}")

    parse_errored = [r for r in results if r["parse_error"]]
    if parse_errored:
        print(f"\n" + "=" * 70)
        print("  ОШИБКИ ПАРСИНГА")
        print("=" * 70)
        for e in parse_errored:
            print(f"\n--- {e['sheet']} ---")
            print(f"  Ошибка: {e['parse_error']}")
            print(f"  HEX: {e['original_hex'][:64]}...")

    print("\n" + "=" * 70)
    print("  VERIFICATION ЗАВЕРШЁН")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()