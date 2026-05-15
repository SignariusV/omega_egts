"""Вывод детального сравнения для одного пакета."""

import json
import libs.egts._gost2015
from libs.egts.registry import get_protocol

proto = get_protocol("2015")

with open("data/packets/all_packets_correct_20260406_190414.json", encoding="utf-8") as f:
    packets = json.load(f)

# EGTS_SR_TERM_IDENTITY (7) - packet #7
pkt = packets[6]
hex_str = pkt["hex"]
raw = bytes.fromhex(hex_str)

result = proto.parse_packet(raw)
p = result.packet
rec = p.records[0]
sr = rec.subrecords[0]

print("=" * 60)
print("СРАВНЕНИЕ ПОЛЕЙ")
print("=" * 60)
print()
print("ЭТАЛОН (из description):")
print("  Header:")
print("    PRV = 1")
print("    SKID = 0")
print("    HL = 11")
print("    FDL = 46")
print("    PID = 42")
print("    PT = 1 (APPDATA)")
print("  Record:")
print("    RN = 73")
print("    SST = 1 (AUTH)")
print("    RST = 1")
print("  Subrecord:")
print("    SRT = 1 (TERM_IDENTITY)")
print("    TID = 1")
print("    flags = 0x16 (00010110)")
print("    IMEI = 860803066448313")
print("    IMSI = 250770017156439")
print()
print("БИБЛИОТЕКА:")
print(f"  Header:")
print(f"    PRV = {p.protocol_version}")
print(f"    SKID = {p.security_key_id}")
print(f"    HL = {p.header_length}")
print(f"    FDL = {raw[5] | (raw[6] << 8)}")
print(f"    PID = {p.packet_id}")
print(f"    PT = {p.packet_type}")
print(f"  Record:")
print(f"    RN = {rec.record_id}")
print(f"    SST = {rec.service_type}")
print(f"    RST = {rec.recipient_service_type}")
print(f"  Subrecord:")
print(f"    SRT = {sr.subrecord_type}")
print(f"    data:")
for k, v in sr.data.items():
    print(f"      {k}: {v}")