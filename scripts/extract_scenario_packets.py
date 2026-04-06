"""
Извлечь HEX-пакеты из JSON в папки сценариев
"""
import json
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "packets" / "all_packets_correct_20260406_190414.json"
SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    packets = json.load(f)

# Словарь: (scenario, subfolder, filename) -> packet_num
PACKET_MAP = {
    # verification (file 1, sheets 1-6)
    ("verification", "platform", "gprs_apn.hex"): 1,
    ("verification", "usv", "comconf_apn.hex"): 2,
    ("verification", "platform", "server_address.hex"): 3,
    ("verification", "usv", "comconf_address.hex"): 4,
    ("verification", "platform", "unit_id.hex"): 5,
    ("verification", "usv", "comconf_unit_id.hex"): 6,

    # auth (file 1, sheets 7-12 и file 2-5 sheets 3-8)
    ("auth", "usv", "term_identity.hex"): 7,
    ("auth", "platform", "record_response_term_identity.hex"): 8,
    ("auth", "usv", "vehicle_data.hex"): 9,
    ("auth", "platform", "record_response_vehicle_data.hex"): 10,
    ("auth", "platform", "result_code.hex"): 11,
    ("auth", "usv", "record_response_result.hex"): 12,

    # track (file 2)
    ("track", "platform", "track_data_request.hex"): 13,
    ("track", "usv", "comconf_track.hex"): 14,
    ("track", "usv", "sr_track_data.hex"): 21,
    ("track", "platform", "record_response_track.hex"): 22,

    # accel (file 3)
    ("accel", "platform", "accel_data_request.hex"): 23,
    ("accel", "usv", "comconf_accel.hex"): 24,
    ("accel", "usv", "sr_accel_data.hex"): 31,
    ("accel", "platform", "record_response_accel.hex"): 32,

    # fw_update (file 4)
    ("fw_update", "platform", "service_part_data_1.hex"): 39,
    ("fw_update", "usv", "record_response_fw_1.hex"): 40,
    ("fw_update", "platform", "service_part_data_2.hex"): 41,
    ("fw_update", "usv", "record_response_fw_2.hex"): 42,

    # commands (file 5)
    ("commands", "platform", "command_data.hex"): 49,
    ("commands", "usv", "pt_response.hex"): 50,
    ("commands", "usv", "comconf_command.hex"): 51,
}

for (scenario, subfolder, filename), pkt_num in PACKET_MAP.items():
    pkt = packets[pkt_num - 1]  # 0-indexed
    hex_data = pkt["hex"]
    
    scenario_dir = SCENARIOS_DIR / scenario / "packets" / subfolder
    scenario_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = scenario_dir / filename
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(hex_data)
    
    print(f"✅ {scenario}/{subfolder}/{filename} ({len(hex_data)//2} байт)")

print(f"\n📊 Извлечено {len(PACKET_MAP)} пакетов")
