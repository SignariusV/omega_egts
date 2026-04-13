"""
Углублённая статистика пакетов:
- Направление передачи (УСВ -> Платформа, Платформа -> УСВ)
- Последовательности пакетов в каждом тесте
- Выделение сценариев (аутентификация, верификация, данные, и т.д.)
- Топ уникальных hex и их распределение
"""
import json
from pathlib import Path
from collections import Counter, defaultdict

DATA_DIR = Path(__file__).parent.parent / "data" / "packets"

def load_packets():
    """Загружает последний файл с пакетами"""
    json_files = sorted(DATA_DIR.glob("all_packets_*.json"))
    if not json_files:
        print("❌ Файлы с пакетами не найдены")
        return None
    
    latest = json_files[-1]
    print(f"📂 Загрузка: {latest.name}")
    
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_scenarios(packets):
    """Анализирует последовательности и выделяет сценарии"""
    
    # Группируем по файлам и листам
    by_file_sheet = defaultdict(list)
    for pkt in packets:
        key = f"{pkt['file']} :: {pkt['sheet']}"
        by_file_sheet[key].append(pkt)
    
    print("\n" + "="*80)
    print("🎯 СЦЕНАРИИ (последовательности пакетов)")
    print("="*80)
    
    scenarios = []
    
    for sheet_key, pkts in by_file_sheet.items():
        if len(pkts) < 3:
            continue
        
        # Определяем тип сценария по имени листа
        sheet_name = pkts[0]['sheet']
        file_name = pkts[0]['file']
        
        # Базовая классификация сценариев
        scenario_type = classify_scenario_type(sheet_name)
        
        # Направление
        directions = Counter(p['direction'] for p in pkts)
        main_direction = directions.most_common(1)[0][0] if directions else "Не определено"
        
        # Уникальные hex
        unique_hex = set()
        for p in pkts:
            normalized = p['hex'].replace(' ', '').replace(':', '').upper()
            unique_hex.add(normalized)
        
        scenario = {
            'file': file_name,
            'sheet': sheet_name,
            'type': scenario_type,
            'packets_count': len(pkts),
            'unique_hex_count': len(unique_hex),
            'main_direction': main_direction,
            'directions': dict(directions),
        }
        
        scenarios.append(scenario)
    
    # Группируем по типам сценариев
    by_type = defaultdict(list)
    for s in scenarios:
        by_type[s['type']].append(s)
    
    for scenario_type, type_scenarios in sorted(by_type.items()):
        total_packets = sum(s['packets_count'] for s in type_scenarios)
        print(f"\n📋 {scenario_type} ({len(type_scenarios)} сценариев, {total_packets} пакетов)")
        
        for s in type_scenarios:
            print(f"   • {s['sheet']}: {s['packets_count']} пакетов, "
                  f"{s['unique_hex_count']} уникальных hex, "
                  f"→ {s['main_direction']}")
    
    return scenarios


def classify_scenario_type(sheet_name):
    """Классифицирует тип сценария по имени листа"""
    sheet_upper = sheet_name.upper().strip()
    
    if 'TERM_IDENTITY' in sheet_upper:
        return "🔐 Аутентификация (идентификация терминала)"
    elif 'VEHICLE_DATA' in sheet_upper:
        return "🚗 Данные транспортного средства"
    elif 'TRACK_DATA' in sheet_upper:
        return "📍 Передача траектории движения"
    elif 'ACCEL_DATA' in sheet_upper:
        return "📈 Передача профиля ускорения"
    elif 'SERVICE_PART_DATA' in sheet_upper:
        return "📦 Передача данных (части сервиса)"
    elif 'COMMAND_DATA' in sheet_upper:
        return "⚙️ Команды конфигурирования"
    elif 'RECORD_RESPONSE' in sheet_upper:
        return "✅ Подтверждение записи (ответ)"
    elif 'RESULT_CODE' in sheet_upper:
        return "🏁 Код результата"
    elif 'GPRS_APN' in sheet_upper or 'SERVER_ADDRESS' in sheet_upper:
        return "🌐 Настройки подключения (APN/Адрес сервера)"
    elif 'COMCONF' in sheet_upper:
        return "🔧 Конфигурация (COMCONF)"
    elif 'PT_RESPONSE' in sheet_upper:
        return "📨 Транспортный ответ"
    elif 'UNIT_ID' in sheet_upper:
        return "🆔 Идентификатор устройства"
    else:
        return "❓ Другое"


def analyze_unique_hex(packets):
    """Анализ уникальных hex значений"""
    hex_counter = Counter()
    hex_details = {}
    
    for pkt in packets:
        normalized = pkt['hex'].replace(' ', '').replace(':', '').upper()
        hex_counter[normalized] += 1
        
        if normalized not in hex_details and pkt['description']:
            hex_details[normalized] = {
                'hex_raw': pkt['hex'],
                'description': pkt['description'],
                'length': pkt['hex_length'],
            }
    
    print("\n" + "="*80)
    print("🔢 УНИКАЛЬНЫЕ HEX (ТОП-30 по частоте)")
    print("="*80)
    
    for hex_val, count in hex_counter.most_common(30):
        details = hex_details.get(hex_val, {})
        desc = details.get('description', '')
        length = details.get('length', '?')
        
        print(f"\n  HEX: {hex_val[:60]}{'...' if len(hex_val) > 60 else ''}")
        print(f"     Длина: {length} байт | Встречается: {count} раз")
        if desc:
            print(f"     Описание: {desc[:100]}...")


def save_scenario_report(scenarios):
    """Сохраняет отчёт по сценариям"""
    report = {
        'scenarios': scenarios,
        'scenario_types': {},
    }
    
    # Группируем по типам
    by_type = defaultdict(list)
    for s in scenarios:
        by_type[s['type']].append(s)
    
    for scenario_type, type_scenarios in by_type.items():
        report['scenario_types'][scenario_type] = {
            'count': len(type_scenarios),
            'total_packets': sum(s['packets_count'] for s in type_scenarios),
            'scenarios': type_scenarios,
        }
    
    report_file = DATA_DIR / "scenario_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Отчёт сохранён: {report_file}")


def generate_hex_catalog(packets):
    """Создаёт каталог уникальных hex с описаниями"""
    hex_catalog = {}
    
    for pkt in packets:
        normalized = pkt['hex'].replace(' ', '').replace(':', '').upper()
        
        if normalized not in hex_catalog:
            hex_catalog[normalized] = {
                'hex': pkt['hex'],
                'hex_length': pkt['hex_length'],
                'descriptions': set(),
                'files': set(),
                'sheets': set(),
                'direction': pkt['direction'],
                'count': 0,
            }
        
        hex_catalog[normalized]['count'] += 1
        if pkt['description']:
            hex_catalog[normalized]['descriptions'].add(pkt['description'])
        hex_catalog[normalized]['files'].add(pkt['file'])
        hex_catalog[normalized]['sheets'].add(pkt['sheet'])
    
    # Преобразуем set в list для JSON
    catalog_serializable = {}
    for hex_val, info in hex_catalog.items():
        catalog_serializable[hex_val] = {
            'hex': info['hex'],
            'hex_length': info['hex_length'],
            'descriptions': list(info['descriptions'])[:5],  # Первые 5
            'files': list(info['files']),
            'sheets': list(info['sheets']),
            'direction': info['direction'],
            'count': info['count'],
        }
    
    catalog_file = DATA_DIR / "hex_catalog.json"
    with open(catalog_file, 'w', encoding='utf-8') as f:
        json.dump(catalog_serializable, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Каталог HEX сохранён: {catalog_file}")
    print(f"   Уникальных HEX: {len(catalog_serializable)}")


if __name__ == "__main__":
    packets = load_packets()
    if not packets:
        exit(1)
    
    print(f"\n📊 Анализ {len(packets)} пакетов...")
    
    # Сценарии
    scenarios = analyze_scenarios(packets)
    save_scenario_report(scenarios)
    
    # Уникальные hex
    analyze_unique_hex(packets)
    
    # Каталог hex
    generate_hex_catalog(packets)
    
    print("\n✅ Анализ завершён!")
