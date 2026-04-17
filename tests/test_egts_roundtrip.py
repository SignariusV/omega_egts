"""Финальный roundtrip тест: новая библиотека на 51 эталонном пакете."""

import json
import os

import pytest

# Импорт регистрирует протокол "2015"
import libs.egts._gost2015  # noqa: F401
from libs.egts.protocol import IEgtsProtocol
from libs.egts.registry import get_protocol

FIXTURES_DIR = "tests/fixtures/egts_packets"


def load_packets():
    """Загрузить все эталонные пакеты."""
    packets = []
    for fname in sorted(os.listdir(FIXTURES_DIR)):
        if not fname.endswith(".bin"):
            continue
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


class TestNewLibraryRoundtrip:
    """Roundtrip всех 51 эталонных пакетов через новую библиотеку."""

    @pytest.fixture
    def proto(self) -> IEgtsProtocol:
        return get_protocol("2015")

    def test_protocol_registered(self):
        """Протокол '2015' должен быть зарегистрирован."""
        proto = get_protocol("2015")
        assert proto.version == "2015"
        assert "auth" in proto.capabilities

    def test_all_packets_parse(self, proto: IEgtsProtocol):
        """Все 51 пакет должны парситься (кроме дефектных #41, #49)."""
        failures = []
        parsed_count = 0
        for name, raw, meta in load_packets():
            result = proto.parse_packet(raw)
            if not result.is_success:
                # #41 и #49 — известные дефекты эталона
                if name in ("pkt_041", "pkt_049"):
                    continue
                failures.append(f"{name}: {result.errors}")
            else:
                parsed_count += 1

        assert not failures, "Ошибки парсинга:\n" + "\n".join(failures)
        assert parsed_count >= 49, f"Распарсено только {parsed_count}/51"

    def test_all_packets_roundtrip(self, proto: IEgtsProtocol):
        """parse → build → байты должны совпасть (кроме #41, #49)."""
        ok = 0
        failed = []
        for name, raw, meta in load_packets():
            # Пропускаем дефектные
            if name in ("pkt_041", "pkt_049"):
                continue

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

        print(f"\nRoundtrip: {ok}/{len(list(load_packets())) - 2} OK")
        if failed:
            print("Failed (первые 5):")
            for f_msg in failed[:5]:
                print(f"  {f_msg[:150]}")

        assert not failed, f"Roundtrip failures ({len(failed)}):\n" + "\n".join(failed[:5])

    def test_response_packets_parsed(self, proto: IEgtsProtocol):
        """RESPONSE-пакеты должны иметь RPID и PR."""
        # pkt_008 — RESPONSE
        bin_path = os.path.join(FIXTURES_DIR, "pkt_008.bin")
        if os.path.exists(bin_path):
            with open(bin_path, "rb") as f:
                raw = f.read()
            result = proto.parse_packet(raw)
            assert result.is_success
            assert result.packet.packet_type == 0
            assert result.packet.response_packet_id is not None
            assert result.packet.processing_result is not None

    def test_appdata_packets_parsed(self, proto: IEgtsProtocol):
        """APPDATA-пакеты должны иметь записи и подзаписи."""
        # pkt_001 — APPDATA
        bin_path = os.path.join(FIXTURES_DIR, "pkt_001.bin")
        if os.path.exists(bin_path):
            with open(bin_path, "rb") as f:
                raw = f.read()
            result = proto.parse_packet(raw)
            assert result.is_success
            assert result.packet.packet_type == 1
            assert len(result.packet.records) > 0
            assert len(result.packet.records[0].subrecords) > 0
