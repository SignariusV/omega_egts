import json

with open('data/packets/all_packets_correct_20260406_190414.json', encoding='utf-8') as f:
    packets = json.load(f)

for i, p in enumerate(packets):
    sheet = p.get('sheet', '')
    if 'SERVICE_PART_DATA (9)' in sheet or 'COMMAND_DATA (7)' in sheet:
        print(f'=== Packet #{i+1}: {sheet} ===')
        print(f'HEX: {p["hex"]}')
        print(f'Bytes: {p.get("hex_length_bytes")}')
        print(f'Description (first 500 chars):')
        print(p.get('description', '')[:500])
        print()