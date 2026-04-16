
"""Парсинг всех пакетов из data/packets/ с данными из всех сервисов.

Запуск:
    python -m examples.parse_all_packets

Читает все hex-пакеты из pure_hex_correct_20260406_190414.txt,
парсит через новую библиотеку libs/egts/ и выводит:
- Статистику по типам пакетов и сервисам
- Примеры парсинга каждого типа подзаписи
- Roundtrip для каждого пакета
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

# Импортируем парсеры подзаписей (они регистрируются автоматически)
import libs.egts._gost2015  # noqa: F401
from libs.egts.models import ParseResult
from libs.egts.registry import get_protocol

# ──────────────────────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────────────────────

PACKETS_DIR = Path(__file__).resolve().parent.parent / "data" / "packets"
HEX_FILE = PACKETS_DIR / "pure_hex_correct_20260406_190414.txt"

SRT_NAMES = {
    0: "RECORD_RESPONSE",
    1: "TERM_IDENTITY",
    2: "MODULE_DATA",
    3: "VEHICLE_DATA",
    6: "AUTH_PARAMS",
    7: "AUTH_INFO",
    8: "SERVICE_INFO",
    9: "RESULT_CODE",
    20: "ACCEL_DATA",
    33: "SERVICE_PART_DATA",
    34: "SERVICE_FULL_DATA",
    51: "COMMAND_DATA",
    62: "RAW_MSD_DATA",
    63: "TRACK_DATA",
}

SERVICE_NAMES = {
    0: "RESPONSE",
    1: "AUTH",
    2: "TELEDATA",
    4: "COMMANDS",
    9: "FIRMWARE",
    10: "ECALL",
}

PT_NAMES = {
    0: "RESPONSE",
    1: "APPDATA",
    2: "SIGNED_APPDATA",
}


# ──────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def sub_section(title: str) -> None:
    print(f"\n--- {title}")


def format_value(v: object, max_len: int = 60) -> str:
    """Форматирует значение для вывода."""
    if isinstance(v, bytes):
        hex_str = v.hex().upper()
        if len(hex_str) > max_len:
            return f"bytes({len(v)}) {hex_str[:max_len]}..."
        return f"bytes({len(v)}) {hex_str}"
    if isinstance(v, str) and len(v) > max_len:
        return f"'{v[:max_len]}...'"
    return repr(v)


# ──────────────────────────────────────────────────────────────
# Загрузка пакетов
# ──────────────────────────────────────────────────────────────

def load_packets() -> list[bytes]:
    """Загрузить все hex-пакеты из файла."""
    if not HEX_FILE.exists():
        raise FileNotFoundError(f"Файл не найден: {HEX_FILE}")

    packets = []
    for line in HEX_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                packets.append(bytes.fromhex(line))
            except ValueError:
                pass  # Пропускаем не-hex строки

    return packets


# ──────────────────────────────────────────────────────────────
# Парсинг и статистика
# ──────────────────────────────────────────────────────────────

def parse_all(packets: list[bytes]):
    """Парсит все пакеты, собирает статистику."""
    proto = get_protocol("2015")

    # Счётчики
    by_pt: Counter = Counter()          # packet_type → count
    by_service: Counter = Counter()     # service_type → count
    by_srt: Counter = Counter()         # subrecord_type → count
    by_srt_data_keys: dict[int, Counter] = defaultdict(Counter)  # SRT → ключи data

    # Результаты парсинга
    parsed_packets: list[tuple[int, bytes, ParseResult]] = []
    failed: list[tuple[int, bytes, list[str]]] = []
    roundtrip_ok = 0
    roundtrip_fail = 0

    for i, raw in enumerate(packets):
        result = proto.parse_packet(raw)
        if not result.is_success:
            failed.append((i + 1, raw, result.errors))
            continue

        parsed_packets.append((i + 1, raw, result))
        pkt = result.packet
        pt_name = PT_NAMES.get(pkt.packet_type, str(pkt.packet_type))
        by_pt[pt_name] += 1

        # Записи и подзаписи
        for rec in pkt.records:
            svc_name = SERVICE_NAMES.get(rec.service_type, str(rec.service_type))
            by_service[svc_name] += 1

            for sr in rec.subrecords:
                srt_name = SRT_NAMES.get(sr.subrecord_type, f"UNKNOWN({sr.subrecord_type})")
                by_srt[srt_name] += 1

                if isinstance(sr.data, dict):
                    for key in sr.data.keys():
                        by_srt_data_keys[sr.subrecord_type][key] += 1

        # Roundtrip
        try:
            rebuilt = proto.build_packet(pkt)
            if rebuilt == raw:
                roundtrip_ok += 1
            else:
                roundtrip_fail += 1
        except Exception:
            roundtrip_fail += 1

    return {
        "parsed": parsed_packets,
        "failed": failed,
        "by_pt": dict(by_pt),
        "by_service": dict(by_service),
        "by_srt": dict(by_srt),
        "by_srt_data_keys": {k: dict(v) for k, v in by_srt_data_keys.items()},
        "roundtrip_ok": roundtrip_ok,
        "roundtrip_fail": roundtrip_fail,
    }


# ──────────────────────────────────────────────────────────────
# Вывод
# ──────────────────────────────────────────────────────────────

def print_summary(stats: dict) -> None:
    """Сводная статистика."""
    section("1. СВОДНАЯ СТАТИСТИКА")

    total_parsed = len(stats["parsed"])
    total_failed = len(stats["failed"])
    total = total_parsed + total_failed
    print(f"  Всего пакетов:    {total}")
    print(f"  Распарсено:       {total_parsed} ✅")
    print(f"  Ошибок:           {total_failed} ❌")
    print(f"  Roundtrip OK:     {stats['roundtrip_ok']}")
    print(f"  Roundtrip FAIL:   {stats['roundtrip_fail']}")

    # По типу пакета
    sub_section("Типы пакетов (PT)")
    for pt_name, count in sorted(stats["by_pt"].items(), key=lambda x: -x[1]):
        pct = count / total_parsed * 100
        print(f"  {pt_name:20s}: {count:5d} ({pct:.1f}%)")

    # По сервисам
    sub_section("Сервисы (SST)")
    for svc_name, count in sorted(stats["by_service"].items(), key=lambda x: -x[1]):
        pct = count / total_parsed * 100
        print(f"  {svc_name:20s}: {count:5d} ({pct:.1f}%)")

    # По подзаписям
    sub_section("Подзаписи (SRT)")
    for srt_name, count in sorted(stats["by_srt"].items(), key=lambda x: -x[1]):
        total_srt = sum(stats["by_srt"].values())
        pct = count / total_srt * 100
        print(f"  {srt_name:25s}: {count:5d} ({pct:.1f}%)")


def print_failed(stats: dict) -> None:
    """Детали ошибок парсинга."""
    section("2. ОШИБКИ ПАРСИНГА")

    if not stats["failed"]:
        print("  Ошибок нет ✅")
        return

    for i, raw, errors in stats["failed"]:
        print(f"  Пакет #{i} ({len(raw)} байт): {', '.join(errors)}")
        if len(raw) <= 64:
            print(f"    Hex: {raw.hex().upper()}")


def print_all_subrecord_types(stats: dict) -> None:
    """Примеры данных каждой подзаписи."""
    section("3. ПРИМЕРЫ ДАННЫХ ПОДЗАПИСЕЙ ПО ВСЕМ СЕРВИСАМ")

    # Собираем уникальные (service_type, srt) пары
    seen: set[tuple[int, int]] = set()
    service_examples: dict[int, list[dict]] = defaultdict(list)

    for pkt_num, raw, result in stats["parsed"]:
        pkt = result.packet
        for rec in pkt.records:
            for sr in rec.subrecords:
                key = (rec.service_type, sr.subrecord_type)
                if key not in seen:
                    seen.add(key)
                    service_examples[rec.service_type].append({
                        "srt": sr.subrecord_type,
                        "data": sr.data,
                        "raw_len": len(raw),
                        "pkt_num": pkt_num,
                    })

    for svc_type in sorted(service_examples.keys()):
        svc_name = SERVICE_NAMES.get(svc_type, f"SERVICE({svc_type})")
        examples = service_examples[svc_type]

        sub_section(f"Сервис: {svc_name} (SST={svc_type}) — {len(examples)} типов подзаписей")

        for ex in examples:
            srt_name = SRT_NAMES.get(ex["srt"], f"UNKNOWN({ex['srt']})")
            print(f"\n  📦 Пакет #{ex['pkt_num']} — {srt_name} (SRT={ex['srt']})")

            if isinstance(ex["data"], dict):
                for key, val in list(ex["data"].items())[:8]:
                    print(f"     {key:20s} = {format_value(val)}")
                if len(ex["data"]) > 8:
                    print(f"     ... ещё {len(ex['data']) - 8} полей")
            else:
                print(f"     data = {format_value(ex['data'])}")


def print_roundtrip_report(stats: dict) -> None:
    """Отчёт по roundtrip."""
    section("4. ROUNDTRIP ОТЧЁТ")

    ok = stats["roundtrip_ok"]
    fail = stats["roundtrip_fail"]
    total = ok + fail

    print(f"  OK:   {ok}/{total} ({ok/total*100:.1f}%)")
    print(f"  FAIL: {fail}/{total} ({fail/total*100:.1f}%)")

    if fail > 0:
        sub_section("Примеры roundtrip-fail пакетов")
        count = 0
        for pkt_num, raw, result in stats["parsed"]:
            if count >= 3:
                break
            try:
                proto = get_protocol("2015")
                rebuilt = proto.build_packet(result.packet)
                if rebuilt != raw:
                    print(f"\n  Пакет #{pkt_num} ({len(raw)} vs {len(rebuilt)} байт)")
                    print(f"  Оригинал: {raw[:40].hex().upper()}...")
                    print(f"  Собрано:   {rebuilt[:40].hex().upper()}...")
                    count += 1
            except Exception as e:
                print(f"\n  Пакет #{pkt_num}: ошибка сборки — {e}")
                count += 1


def print_data_keys_by_srt(stats: dict) -> None:
    """Ключи данных для каждого типа подзаписи."""
    section("5. КЛЮЧИ ДАННЫХ ПО ТИПАМ ПОДЗАПИСЕЙ")

    for srt in sorted(stats["by_srt_data_keys"].keys()):
        srt_name = SRT_NAMES.get(srt, f"UNKNOWN({srt})")
        keys = stats["by_srt_data_keys"][srt]
        print(f"\n  SRT={srt} ({srt_name}):")
        for key, count in sorted(keys.items(), key=lambda x: -x[1]):
            print(f"    {key:20s} — в {count} пакетах")


# ──────────────────────────────────────────────────────────────
# Главная функция
# ──────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 70)
    print("  ПАРСИНГ ВСЕХ ПАКЕТОВ ИЗ data/packets/")
    print("  ГОСТ 33465-2015 — транспортный уровень")
    print("=" * 70)

    # Загрузка
    packets = load_packets()
    print(f"\n  Загружено {len(packets)} пакетов из {HEX_FILE.name}")

    # Парсинг
    stats = parse_all(packets)

    # Вывод
    print_summary(stats)
    print_failed(stats)
    print_all_subrecord_types(stats)
    print_data_keys_by_srt(stats)
    print_roundtrip_report(stats)

    print("\n" + "=" * 70)
    print("  ЗАВЕРШЕНО")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
