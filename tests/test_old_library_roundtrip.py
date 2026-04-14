"""Baseline roundtrip тест для старой библиотеки (Этап 0.4).

Для каждого эталонного пакета: parse → build → сравнить байты.
Это покажет какие пакеты уже проходят roundtrip в старой библиотеке.
"""
import json
import os
import pytest

from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015

FIXTURES_DIR = "tests/fixtures/egts_packets"


def load_packets():
    """Загрузить все эталонные пакеты."""
    packets = []
    for fname in sorted(os.listdir(FIXTURES_DIR)):
        if fname.endswith(".bin"):
            fpath = os.path.join(FIXTURES_DIR, fname)
            with open(fpath, "rb") as f:
                raw = f.read()

            meta_path = os.path.join(FIXTURES_DIR, fname.replace(".bin", ".json"))
            meta = {}
            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)

            packets.append((fname.replace(".bin", ""), raw, meta))
    return packets


class TestOldLibraryRoundtrip:
    """Baseline roundtrip для старой библиотеки."""

    @pytest.fixture
    def protocol(self):
        return EgtsProtocol2015()

    def test_all_packets_parse(self):
        """Все 51 пакет должны парситься без ошибок."""
        proto = EgtsProtocol2015()
        failures = []
        for name, raw, meta in load_packets():
            result = proto.parse_packet(raw)
            if not result.is_success:
                failures.append(f"{name}: {result.errors}")
        assert not failures, f"Пакеты не парсятся:\n" + "\n".join(failures)

    def test_all_packets_roundtrip(self):
        """Проверить roundtrip: parse → build → сравнить байты."""
        proto = EgtsProtocol2015()
        ok = 0
        failed = []
        for name, raw, meta in load_packets():
            result = proto.parse_packet(raw)
            if not result.is_success or not result.packet:
                failed.append(f"{name}: parse failed — {result.errors}")
                continue

            rebuilt = proto.build_packet(result.packet)
            if rebuilt == raw:
                ok += 1
            else:
                failed.append(
                    f"{name}: roundtrip failed\n"
                    f"  original ({len(raw)}): {raw.hex()}\n"
                    f"  rebuilt  ({len(rebuilt)}): {rebuilt.hex()}"
                )

        print(f"\nRoundtrip: {ok}/{len(list(load_packets()))} OK")
        if failed:
            print("Failed:")
            for f_msg in failed[:10]:
                print(f"  {f_msg[:120]}")

        assert not failed, f"Roundtrip failures ({len(failed)}):\n" + "\n".join(failed[:5])
