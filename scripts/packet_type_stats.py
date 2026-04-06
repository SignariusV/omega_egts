"""
Статистика по уникальным типам пакетов (без номеров листов)
"""
import json
from pathlib import Path
from collections import Counter
import re

DATA_DIR = Path(__file__).parent.parent / "data" / "packets"

def load_packets():
    json_files = sorted(DATA_DIR.glob("all_packets_*.json"))
    if not json_files:
        print("❌ Файлы с пакетами не найдены")
        return None
    with open(json_files[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_sheet_name(sheet_name):
    """Убирает номера листов: 'EGTS_SR_TRACK_DATA (9)' → 'EGTS_SR_TRACK_DATA'"""
    return re.sub(r'\s*\(\d+\)\s*$', '', sheet_name).strip()


def main():
    packets = load_packets()
    if not packets:
        return

    # Считаем пакеты по нормализованным именам
    type_counter = Counter()
    type_unique_hex = {}
    type_directions = {}
    type_files = {}

    for pkt in packets:
        raw_sheet = pkt['sheet']
        norm_name = normalize_sheet_name(raw_sheet)
        
        type_counter[norm_name] += 1
        
        normalized_hex = pkt['hex'].replace(' ', '').replace(':', '').upper()
        
        if norm_name not in type_unique_hex:
            type_unique_hex[norm_name] = set()
            type_directions[norm_name] = Counter()
            type_files[norm_name] = set()
        
        type_unique_hex[norm_name].add(normalized_hex)
        type_directions[norm_name][pkt['direction']] += 1
        type_files[norm_name].add(pkt['file'])

    # Вывод
    print("\n" + "="*90)
    print("📦 СТАТИСТИКА ПО УНИКАЛЬНЫМ ТИПАМ ПАКЕТОВ")
    print("="*90)
    
    print(f"\n{'Тип пакета':<40} {'Кол-во':>7} {'Уник. HEX':>10} {'Направление':<25}")
    print("-" * 90)
    
    for name, count in type_counter.most_common():
        unique_count = len(type_unique_hex[name])
        main_dir = type_directions[name].most_common(1)[0][0]
        
        # Сокращаем длинные имена
        display_name = name if len(name) <= 38 else name[:35] + "..."
        print(f"{display_name:<40} {count:>7} {unique_count:>10} {main_dir:<25}")
    
    print("-" * 90)
    print(f"{'ИТОГО':<40} {sum(type_counter.values()):>7} {len(type_counter):>10} типов: {len(type_counter)}")
    
    # Подробно по каждому типу
    print("\n" + "="*90)
    print("📋 ПОДРОБНО ПО КАЖДОМУ ТИПУ")
    print("="*90)
    
    for name, count in type_counter.most_common():
        directions = dict(type_directions[name])
        files = type_files[name]
        unique_count = len(type_unique_hex[name])
        
        print(f"\n🔹 {name}")
        print(f"   Пакетов: {count} | Уникальных HEX: {unique_count}")
        print(f"   Направление: {', '.join(f'{k}: {v}' for k, v in directions.items())}")
        print(f"   Файлы: {', '.join(files)}")


if __name__ == "__main__":
    main()
