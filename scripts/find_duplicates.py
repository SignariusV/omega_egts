"""
Поиск повторяющихся hex-паттернов между файлами
"""
import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data" / "packets"

def load_correct_packets():
    json_files = sorted(DATA_DIR.glob("all_packets_correct_*.json"))
    if not json_files:
        print("❌ Файлы не найдены")
        return None
    with open(json_files[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def find_duplicates():
    packets = load_correct_packets()
    if not packets:
        return

    # Группируем по hex
    hex_groups = defaultdict(list)
    for pkt in packets:
        hex_groups[pkt['hex']].append(pkt)

    # Фильтруем только дубликаты
    duplicates = {h: pkts for h, pkts in hex_groups.items() if len(pkts) > 1}

    print("\n" + "="*90)
    print("🔁 ПОВТОРЯЮЩИЕСЯ ПАКЕТЫ МЕЖДУ ФАЙЛАМИ")
    print("="*90)

    print(f"\n📦 Уникальных hex: {len(hex_groups)}")
    print(f"🔁 Из них повторяются: {len(duplicates)}")

    total_duplicates = sum(len(pkts) for pkts in duplicates.values())
    print(f"📊 Всего повторений: {total_duplicates - len(duplicates)}")

    # Группируем: какие файлы имеют одинаковые пакеты
    file_pairs = defaultdict(list)
    for hex_val, pkts in duplicates.items():
        files = set(p['file'] for p in pkts)
        sheets = set(p['sheet'] for p in pkts)

        if len(files) > 1:  # Между разными файлами
            key = tuple(sorted(files))
            file_pairs[key].append({
                'hex': hex_val[:60] + '...',
                'hex_full': hex_val,
                'sheets': list(sheets),
                'count': len(pkts),
                'size_bytes': len(hex_val) // 2,
            })

    print(f"\n📁 Повторы МЕЖДУ файлами:")
    for files, pkts in file_pairs.items():
        print(f"\n  🔗 {' ↔ '.join(f[:40] for f in files)}")
        print(f"     Одинаковых пакетов: {len(pkts)}")
        for p in pkts[:5]:
            print(f"       • {p['hex']} ({p['size_bytes']} байт) | {', '.join(p['sheets'])}")
        if len(pkts) > 5:
            print(f"       ... и ещё {len(pkts) - 5}")

    # По типам пакетов (без номеров)
    print(f"\n\n📋 Повторы по типам пакетов (нормализованным):")
    import re
    type_groups = defaultdict(list)
    for hex_val, pkts in duplicates.items():
        types = set(re.sub(r'\s*\(\d+\)\s*$', '', p['sheet']).strip() for p in pkts)
        type_key = tuple(sorted(types))
        type_groups[type_key].append({
            'hex': hex_val,
            'count': len(pkts),
            'size': len(hex_val) // 2,
        })

    for types, pkts in sorted(type_groups.items(), key=lambda x: -len(x[1])):
        if len(types) == 1:
            print(f"\n  🔹 {types[0]}: {len(pkts)} разных пакетов повторяется")
        else:
            print(f"\n  🔹 Одинаковый HEX у: {' | '.join(types)} ({len(pkts)} раз)")


if __name__ == "__main__":
    find_duplicates()
