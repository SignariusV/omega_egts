"""Сравнение hex динамического сценария с эталонными .hex файлами."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.scenario import ScenarioManager
from core.scenario_parser import ScenarioParserFactory, ScenarioParserRegistry, ScenarioParserV1


def load_reference_hex(path: str) -> bytes:
    raw = Path(path).read_text(encoding="utf-8").strip()
    return bytes.fromhex(raw)


def main():
    scenario_path = Path(__file__).resolve().parent.parent.parent / "scenarios" / "verification_dynamic" / "scenario.json"

    registry = ScenarioParserRegistry()
    registry.register("1", ScenarioParserV1)
    factory = ScenarioParserFactory(registry)
    mgr = ScenarioManager(parser_factory=factory)
    mgr.load(scenario_path)

    refs = {
        0: ("scenarios/verification/packets/platform/gprs_apn.hex", "GPRS/APN"),
        2: ("scenarios/verification/packets/platform/server_address.hex", "Server Address"),
        4: ("scenarios/verification/packets/platform/unit_id.hex", "Unit ID"),
    }

    send_indices = [0, 2, 4]

    all_ok = True
    for i, step_idx in enumerate(send_indices):
        step = mgr.steps[step_idx]
        ref_path, label = refs[step_idx]
        ref_bytes = load_reference_hex(ref_path)

        packet_bytes = step._build_from_template_bytes(mgr.context)

        match = packet_bytes == ref_bytes
        status = "OK" if match else "MISMATCH"
        all_ok = all_ok and match

        print(f"=== Step {step_idx+1}: {step.name} ({label}) ===")
        print(f"  Reference: {ref_bytes.hex()}")
        print(f"  Dynamic:   {packet_bytes.hex()}")
        print(f"  Result: {'PASS' if match else 'FAIL'}")

        if not match:
            for pos in range(max(len(packet_bytes), len(ref_bytes))):
                if pos >= len(packet_bytes):
                    print(f"    Byte {pos}: dynamic=<missing> reference={ref_bytes[pos]:02x}")
                elif pos >= len(ref_bytes):
                    print(f"    Byte {pos}: dynamic={packet_bytes[pos]:02x} reference=<missing>")
                elif packet_bytes[pos] != ref_bytes[pos]:
                    print(f"    Byte {pos}: dynamic={packet_bytes[pos]:02x} reference={ref_bytes[pos]:02x}")
            if len(packet_bytes) != len(ref_bytes):
                print(f"    Length: dynamic={len(packet_bytes)} reference={len(ref_bytes)}")
        print()

    if all_ok:
        print("ALL MATCH")
    else:
        print("SOME MISMATCHES FOUND")
        sys.exit(1)


if __name__ == "__main__":
    main()
