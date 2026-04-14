"""Побайтовое сравнение полей EGTS-пакетов с эталонными данными.

Задача: сравнить КАЖДОЕ поле пакета с эталонным описанием.

Подход:
1. Парсим description из эталона — извлекаем имя поля, тип, ожидаемое значение
2. Парсим пакет через нашу библиотеку — извлекаем фактические значения
3. Сравниваем поле-за-полем
4. Выводим отчёт: совпало / не совпало / не проверено

Использование:
    python scripts/tools/compare_fields.py
    python scripts/tools/compare_fields.py --limit 10
    python scripts/tools/compare_fields.py --output field_report.json
    python scripts/tools/compare_fields.py --verbose --limit 5
"""
import sys
import json
import re
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────────────────────
# Структуры данных
# ──────────────────────────────────────────────────────────────

@dataclass
class ExpectedField:
    """Ожидаемое поле из эталонного description."""
    name: str  # PRV, SKID, HL, FDL, PID, PT, HCS, RL, RN, RFL, SST, RST, SRT, SRL, ...
    full_name: str  # Protocol Version, Security Key ID, ...
    data_type: str  # BYTE, USHORT, UINT, STRING, BINARY
    expected_value: int | str | None = None  # Ожидаемое значение (если извлечено)
    raw_line: str = ""  # Исходная строка из description
    byte_offset: int = 0  # Смещение в пакете (примерное)


@dataclass
class ActualField:
    """Фактическое поле из нашей библиотеки."""
    name: str
    value: int | str | bytes | None = None
    data_type: str = ""
    source: str = ""  # Откуда взято: "header", "record", "subrecord"


@dataclass
class FieldComparison:
    """Сравнение одного поля."""
    expected: ExpectedField
    actual: ActualField | None = None
    status: str = "pending"  # match, mismatch, missing, unchecked, parse_error
    error: str = ""


@dataclass
class PacketFieldReport:
    """Отчёт по одному пакету."""
    index: int
    hex_preview: str
    hex_length: int
    file: str = ""
    sheet: str = ""
    comparisons: list[FieldComparison] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# Парсер description из эталона
# ──────────────────────────────────────────────────────────────

def parse_description_fields(description: str, hex_data: bytes) -> list[ExpectedField]:
    """Распарсить description из эталона.

    Формат строк:
        "PRV (Protocol Version) [BYTE]"
        "FDL (Frame Data Length) [USHORT] размер в байтах поля данных SFRD=33"
        "PID (Packet Identifier) [USHORT] номер пакета (=27)"
        "PT (Packet Type) [BYTE] EGTS_PT_APPDATA=1"
        "RL (Record Length) [USHORT] 26 байт"
        "CID (Command Identifier) [UINT] идентификатор команды"
        "8 [STRING] IMEI 860..."

    Returns:
        Список ExpectedField с извлечёнными значениями
    """
    fields: list[ExpectedField] = []
    offset = 0

    for line in description.split("\n"):
        line = line.strip()
        if not line:
            continue

        field_info = _parse_single_line(line, offset, hex_data)
        if field_info:
            fields.append(field_info)
            # Обновляем смещение
            type_size = _get_type_size(field_info.data_type)
            if type_size > 0:
                offset += type_size

    return fields


def _parse_single_line(line: str, offset: int, hex_data: bytes) -> ExpectedField | None:
    """Распарсить одну строку description."""
    # Пропускаем строки с CRC-8/CRC-16 — они проверяются отдельно
    if "CRC-8" in line or "CRC-16" in line or "SFRCS" in line:
        return None

    # Паттерн 1: "ИМЯ (Полное имя) [ТИП] описание (=значение)" или "ИМЯ=значение"
    # Примеры:
    #   "PRV (Protocol Version) [BYTE]"
    #   "FDL (Frame Data Length) [USHORT] размер в байтах поля данных SFRD=33"
    #   "PID (Packet Identifier) [USHORT] номер пакета (=27)"
    #   "PT (Packet Type) [BYTE] EGTS_PT_APPDATA=1"
    #   "RL (Record Length) [USHORT] 26 байт"
    #   "8 [STRING] IMEI 860..."

    # Базовый паттерн: NAME (...) [TYPE]
    match = re.match(r'^([A-Za-z_0-9]+)\s*\(([^)]+)\)\s*\[([A-Z]+)\](.*)$', line)
    if not match:
        # Паттерн 2: "BYTE описание" (для STRING/BINARY отдельных символов)
        match2 = re.match(r'^(\S+)\s+\[([A-Z]+)\](.*)$', line)
        if match2:
            name = match2.group(1)
            data_type = match2.group(2)
            rest = match2.group(3)
            full_name = name
        else:
            return None
    else:
        name = match.group(1)
        full_name = match.group(2)
        data_type = match.group(3)
        rest = match.group(4)

    # Извлекаем значение
    expected_value = _extract_value(rest, name, data_type, offset, hex_data)

    return ExpectedField(
        name=name,
        full_name=full_name,
        data_type=data_type,
        expected_value=expected_value,
        raw_line=line,
        byte_offset=offset,
    )


def _extract_value(rest: str, name: str, data_type: str, offset: int, hex_data: bytes) -> int | str | None:
    """Извлечь ожидаемое значение из описания."""
    if not rest:
        return None

    # Паттерн: "(=число)"
    match = re.search(r'\(=(\d+)\)', rest)
    if match:
        return int(match.group(1))

    # Паттерн: "ИМЯ=число" (например "EGTS_PT_APPDATA=1")
    match = re.search(r'[A-Z_]+=(\d+)', rest)
    if match and name not in ("SFRD",):  # Не извлекаем случайные числа из описания
        return int(match.group(1))

    # Паттерн: "N байт" для длин
    match = re.search(r'(\d+)\s*байт', rest)
    if match and name in ("HL", "RL", "FDL", "SRL"):
        return int(match.group(1))

    # Паттерн: "PRF=00", "CT=0101" и т.д.
    match = re.search(r'(?:^|\s)([A-Z]+)=(\d+|\d{2,})', rest)
    if match:
        key = match.group(1)
        val = match.group(2)
        if key in ("PRF", "RTE", "ENA", "CMP", "PR", "CT", "CCT", "ACT", "SZ", "ACFE", "CHSFE"):
            try:
                return int(val, 16) if len(val) > 2 else int(val)
            except ValueError:
                return None

    # Паттерн: STRING — извлекаем символы из hex
    if data_type == "STRING" and hex_data:
        # Попробуем извлечь символ из hex_data по offset
        # Для STRING байты идут подряд
        # Но offset здесь не точный — это счётчик полей, не байтов
        return None

    return None


def _get_type_size(data_type: str) -> int:
    """Вернуть размер типа в байтах."""
    sizes = {
        "BYTE": 1,
        "BOOLEAN": 1,
        "USHORT": 2,
        "SHORT": 2,
        "UINT": 4,
        "INT": 4,
        "ULONG": 8,
        "FLOAT": 4,
        "DOUBLE": 8,
    }
    return sizes.get(data_type, 0)


# ──────────────────────────────────────────────────────────────
# Извлечение фактических значений из распарсенного пакета
# ──────────────────────────────────────────────────────────────

def extract_actual_fields(raw_data: bytes, parse_result: Any) -> list[ActualField]:
    """Извлечь фактические поля из распарсенного пакета.

    Извлекает:
    - Заголовок: PRV, SKID, PR flags, HL, HE, FDL, PID, PT, HCS, PRA, RCA, TTL
    - Записи: RL, RN, RFL, OID, EVID, TM, SST, RST
    - Подзаписи: SRT, SRL, SRD
    """
    actual: list[ActualField] = []

    # Заголовок
    actual.append(ActualField("PRV", raw_data[0], "BYTE", "header"))
    actual.append(ActualField("SKID", raw_data[1], "BYTE", "header"))

    flags_byte = raw_data[2]
    actual.append(ActualField("PR_FLAGS", flags_byte, "BYTE", "header"))
    actual.append(ActualField("PRF", bool(flags_byte & 0x80), "BOOLEAN", "header"))
    actual.append(ActualField("RTE", bool(flags_byte & 0x40), "BOOLEAN", "header"))
    actual.append(ActualField("ENA", bool(flags_byte & 0x20), "BOOLEAN", "header"))
    actual.append(ActualField("CMP", bool(flags_byte & 0x10), "BOOLEAN", "header"))
    actual.append(ActualField("PR", (flags_byte >> 2) & 0x03, "BYTE", "header"))

    actual.append(ActualField("HL", raw_data[3], "BYTE", "header"))
    actual.append(ActualField("HE", raw_data[4], "BYTE", "header"))

    fdl = int.from_bytes(raw_data[5:7], "little")
    actual.append(ActualField("FDL", fdl, "USHORT", "header"))

    pid = int.from_bytes(raw_data[7:9], "little")
    actual.append(ActualField("PID", pid, "USHORT", "header"))

    actual.append(ActualField("PT", raw_data[9], "BYTE", "header"))

    # Маршрутизация (если HL > 11)
    hl = raw_data[3]
    offset = 10  # После PT

    if hl > 11:
        if offset + 2 <= len(raw_data):
            pra = int.from_bytes(raw_data[offset:offset+2], "little")
            actual.append(ActualField("PRA", pra, "USHORT", "header"))
            offset += 2
        if offset + 2 <= len(raw_data):
            rca = int.from_bytes(raw_data[offset:offset+2], "little")
            actual.append(ActualField("RCA", rca, "USHORT", "header"))
            offset += 2
        if offset + 1 <= len(raw_data):
            actual.append(ActualField("TTL", raw_data[offset], "BYTE", "header"))
            offset += 1

    # HCS
    if offset < len(raw_data):
        actual.append(ActualField("HCS", raw_data[offset], "BYTE", "header"))
        offset += 1

    # RESPONSE поля (PT=0)
    if raw_data[9] == 0:  # RESPONSE
        if offset + 2 <= len(raw_data):
            rpid = int.from_bytes(raw_data[offset:offset+2], "little")
            actual.append(ActualField("RPID", rpid, "USHORT", "header"))
            offset += 2
        if offset < len(raw_data):
            actual.append(ActualField("PR", raw_data[offset], "BYTE", "header"))
            offset += 1

    # Записи — если есть распарсенный результат
    if parse_result and parse_result.packet:
        packet = parse_result.packet

        for i, rec in enumerate(packet.records):
            prefix = f"REC[{i}]" if len(packet.records) > 1 else ""

            # RL — длина данных записи (RD) = сумма длин ВСЕХ подзаписей включая SRT+SRL+SRD
            # Эталон считает RL = сумма(SRT + SRL + SRD) для каждой подзаписи
            rec_rl = sum(
                3 + len(sub.data if isinstance(sub.data, bytes) else sub.raw_data or b"")
                for sub in rec.subrecords
            )
            actual.append(ActualField(f"{prefix}RL", rec_rl, "USHORT", "record"))
            actual.append(ActualField(f"{prefix}RN", rec.record_id, "USHORT", "record"))
            actual.append(ActualField(f"{prefix}RFL", rec.rf_flags, "BYTE", "record"))
            actual.append(ActualField(f"{prefix}SSOD", rec.ssod, "BOOLEAN", "record"))
            actual.append(ActualField(f"{prefix}RSOD", rec.rsod, "BOOLEAN", "record"))
            actual.append(ActualField(f"{prefix}RPP", rec.rpp, "BYTE", "record"))

            if rec.object_id is not None:
                actual.append(ActualField(f"{prefix}OID", rec.object_id, "UINT", "record"))
            if rec.event_id is not None:
                actual.append(ActualField(f"{prefix}EVID", rec.event_id, "UINT", "record"))
            if rec.timestamp is not None:
                actual.append(ActualField(f"{prefix}TM", rec.timestamp, "UINT", "record"))

            actual.append(ActualField(f"{prefix}SST", rec.service_type, "BYTE", "record"))
            actual.append(ActualField(f"{prefix}RST", rec.rst_service_type, "BYTE", "record"))

            # Подзаписи
            for j, sub in enumerate(rec.subrecords):
                sub_prefix = f"{prefix}SR[{j}]" if len(rec.subrecords) > 1 else f"{prefix}"

                # SRT — subrecord type
                srt_val = sub.subrecord_type
                if isinstance(srt_val, str):
                    actual.append(ActualField(f"{sub_prefix}SRT_NAME", srt_val, "STRING", "subrecord"))
                    # Попробуем конвертировать в int для сравнения
                    try:
                        from libs.egts_protocol_gost2015.gost2015_impl.types import SubrecordType
                        srt_int = SubrecordType[srt_val].value
                        actual.append(ActualField(f"{sub_prefix}SRT", srt_int, "BYTE", "subrecord"))
                    except (KeyError, ImportError):
                        pass
                else:
                    actual.append(ActualField(f"{sub_prefix}SRT", srt_val, "BYTE", "subrecord"))

                # SRL — subrecord length
                srd = sub.data if isinstance(sub.data, bytes) else sub.raw_data
                srl = len(srd) if srd else 0
                actual.append(ActualField(f"{sub_prefix}SRL", srl, "USHORT", "subrecord"))

                # Если data = dict (распарсенные поля) — извлекаем все поля
                if isinstance(sub.data, dict):
                    for field_name, field_value in sub.data.items():
                        if field_name in ("raw", "parse_error"):
                            continue
                        actual.append(ActualField(
                            f"{sub_prefix}{field_name.upper()}",
                            field_value,
                            type(field_value).__name__,
                            "subrecord_field",
                        ))

                # SRD — для STRING/BINARY (только если data = bytes)
                if isinstance(srd, bytes) and srd and len(srd) <= 100:
                    try:
                        text = srd.decode("cp1251")
                        actual.append(ActualField(f"{sub_prefix}SRD", text, "STRING", "subrecord"))
                    except UnicodeDecodeError:
                        actual.append(ActualField(f"{sub_prefix}SRD_HEX", srd.hex(), "BINARY", "subrecord"))

    return actual


# ──────────────────────────────────────────────────────────────
# Сравнение полей
# ──────────────────────────────────────────────────────────────

def compare_fields(expected_fields: list[ExpectedField], actual_fields: list[ActualField]) -> list[FieldComparison]:
    """Сравнить ожидаемые и фактические поля."""
    comparisons: list[FieldComparison] = []

    # Создаём lookup для фактических полей
    actual_lookup: dict[str, ActualField] = {}
    for af in actual_fields:
        actual_lookup[af.name] = af

    for ef in expected_fields:
        comparison = FieldComparison(expected=ef)

        # Ищем соответствующее фактическое поле
        af = actual_lookup.get(ef.name)
        if af is None:
            # Пробуем маппинг имён
            af = _map_field_name(ef.name, actual_lookup)

        if af is None:
            comparison.status = "missing"
            comparison.error = f"Поле {ef.name} не найдено в распарсенных данных"
        elif ef.expected_value is None:
            comparison.status = "unchecked"
            comparison.actual = af
        elif _values_match(ef.expected_value, af.value):
            comparison.status = "match"
            comparison.actual = af
        else:
            comparison.status = "mismatch"
            comparison.actual = af
            comparison.error = f"Ожидалось {ef.expected_value}, получено {af.value}"

        comparisons.append(comparison)

    return comparisons


def _map_field_name(expected_name: str, actual_lookup: dict[str, ActualField]) -> ActualField | None:
    """Попробовать замаппить имя поля."""
    # Маппинги: ожидаемое имя → возможное имя в actual
    mappings = {
        "PR": "PR_FLAGS",
        "PRF": "PRF",
        "RTE": "RTE",
        "ENA": "ENA",
        "CMP": "CMP",
        "HCS": "HCS",
        "HE": "HE",
        "PRA": "PRA",
        "RCA": "RCA",
        "TTL": "TTL",
        "RPID": "RPID",
        "RL": "RL",
        "RN": "RN",
        "RFL": "RFL",
        "SSOD": "SSOD",
        "RSOD": "RSOD",
        "RPP": "RPP",
        "OID": "OID",
        "EVID": "EVID",
        "TM": "TM",
        "SST": "SST",
        "RST": "RST",
        "SRT": "SRT",
        "SRL": "SRL",
        "HL": "HL",
        "FDL": "FDL",
        "PID": "PID",
        "PT": "PT",
        "PRV": "PRV",
        "SKID": "SKID",
        # Поля подзаписей (из распарсенного dict)
        "CT": "CT",
        "CCT": "CCT",
        "CID": "CID",
        "SID": "SID",
        "ACFE": "ACFE",
        "ACFE/CHSFE": "ACFE",
        "CHSFE": "CHSFE",
        "CHS": "CHS",
        "ACL": "ACL",
        "AC": "AC",
        "CD": "CD",
        "ADR": "ADR",
        "CCD": "CCD",
        "SZ": "SZ",
        "ACT": "ACT",
        "DT": "DT",
        "RC": "RC",
        "RCD": "RCD",
        "CRN": "CRN",
        "TID": "TID",
        "IMEI": "IMEI",
        "IMSI": "IMSI",
        "MSISDN": "MSISDN",
    }

    mapped = mappings.get(expected_name)
    if mapped:
        return actual_lookup.get(mapped)
    return None


def _values_match(expected: int | str, actual: int | str | bytes | None) -> bool:
    """Проверить совпадение значений."""
    if actual is None:
        return False

    if isinstance(expected, int):
        if isinstance(actual, (int, bool)):
            return expected == int(actual)
        if isinstance(actual, str):
            try:
                return expected == int(actual)
            except ValueError:
                return False
        return False

    if isinstance(expected, str):
        if isinstance(actual, str):
            return expected == actual
        return False

    return expected == actual


# ──────────────────────────────────────────────────────────────
# Отчёт
# ──────────────────────────────────────────────────────────────

def format_comparison_report(comparisons: list[FieldComparison], verbose: bool = False) -> str:
    """Форматировать текстовый отчёт."""
    lines = []

    for c in comparisons:
        ef = c.expected
        status_icon = {
            "match": "✅",
            "mismatch": "❌",
            "missing": "⚠️ ",
            "unchecked": "📝",
            "parse_error": "💥",
        }.get(c.status, "❓")

        line = f"  {status_icon} {ef.name} [{ef.data_type}]"

        if ef.expected_value is not None:
            line += f" = {ef.expected_value}"

        if c.actual and c.actual.value is not None:
            line += f" → {c.actual.value}"

        if c.error and c.status != "match":
            line += f" | {c.error}"

        lines.append(line)

        if verbose and ef.raw_line:
            lines.append(f"     Эталон: {ef.raw_line}")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Основная функция
# ──────────────────────────────────────────────────────────────

def compare_one_packet(hex_str: str, idx: int, metadata: dict[str, Any] | None = None) -> PacketFieldReport:
    """Сравнить поля одного пакета."""
    from libs.egts_protocol_gost2015.adapter import EgtsProtocol2015

    report = PacketFieldReport(
        index=idx,
        hex_preview=hex_str[:50] + "..." if len(hex_str) > 50 else hex_str,
        hex_length=len(hex_str) // 2,
    )

    if metadata:
        report.file = metadata.get("file", "")
        report.sheet = metadata.get("sheet", "")

    # Конвертируем hex → bytes
    try:
        raw_data = bytes.fromhex(hex_str)
    except ValueError as e:
        report.parse_errors.append(f"Неверный hex: {e}")
        return report

    # Парсим через нашу библиотеку
    protocol = EgtsProtocol2015()
    parse_result = protocol.parse_packet(raw_data)

    if not parse_result.packet:
        report.parse_errors.extend(parse_result.errors)
        return report

    # Извлекаем ожидаемые поля из description
    description = metadata.get("description", "") if metadata else ""
    if description:
        expected_fields = parse_description_fields(description, raw_data)
    else:
        expected_fields = []

    # Извлекаем фактические поля
    actual_fields = extract_actual_fields(raw_data, parse_result)

    # Сравниваем
    if expected_fields:
        comparisons = compare_fields(expected_fields, actual_fields)
        report.comparisons = comparisons
    else:
        # Без description — просто покажем фактические поля
        report.comparisons = [
            FieldComparison(
                expected=ExpectedField(name=af.name, full_name="", data_type=af.data_type),
                actual=af,
                status="unchecked",
            )
            for af in actual_fields
        ]

    # Статистика
    report.summary = {
        "match": sum(1 for c in report.comparisons if c.status == "match"),
        "mismatch": sum(1 for c in report.comparisons if c.status == "mismatch"),
        "missing": sum(1 for c in report.comparisons if c.status == "missing"),
        "unchecked": sum(1 for c in report.comparisons if c.status == "unchecked"),
        "total": len(report.comparisons),
    }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Побайтовое сравнение полей EGTS-пакетов с эталоном"
    )
    parser.add_argument(
        "--packets-file",
        default="data/packets/all_packets_correct_20260406_190414.json",
        help="JSON-файл с пакетами и description",
    )
    parser.add_argument("--output", help="Файл для сохранения отчёта (JSON)")
    parser.add_argument("--limit", type=int, help="Ограничить число пакетов")
    parser.add_argument("--verbose", action="store_true", help="Подробный вывод")
    parser.add_argument("--only-mismatches", action="store_true", help="Показать только расхождения")
    args = parser.parse_args()

    print(f"╔{'═'*78}╗")
    print(f"║  EGTS: Побайтовое сравнение полей с эталоном{' '*33}║")
    print(f"╚{'═'*78}╝")
    print()

    # Загружаем пакеты
    packets_file = Path(args.packets_file)
    if not packets_file.exists():
        print(f"❌ Файл не найден: {packets_file}")
        return 1

    print(f"📂 Загрузка из {packets_file}...")
    packets = json.loads(packets_file.read_text(encoding="utf-8"))
    print(f"  Пакетов: {len(packets)}")
    print()

    if args.limit:
        packets = packets[: args.limit]
        print(f"⚡ Ограничение: {args.limit} пакетов")
        print()

    # Тестируем каждый пакет
    all_reports: list[PacketFieldReport] = []
    total_match = 0
    total_mismatch = 0
    total_missing = 0
    total_unchecked = 0

    for i, pkt in enumerate(packets):
        hex_str = pkt.get("hex", "")
        if not hex_str:
            continue

        idx = i + 1
        print(f"[{idx}/{len(packets)}] {hex_str[:40]}...", end=" ")

        report = compare_one_packet(hex_str, idx, pkt)
        all_reports.append(report)

        s = report.summary
        total_match += s.get("match", 0)
        total_mismatch += s.get("mismatch", 0)
        total_missing += s.get("missing", 0)
        total_unchecked += s.get("unchecked", 0)

        if report.parse_errors:
            print(f"❌ parse error: {report.parse_errors[0][:60]}")
        elif s.get("mismatch", 0) > 0:
            print(f"❌ {s['mismatch']} расхождений")
        elif s.get("missing", 0) > 0:
            print(f"⚠️  {s['missing']} пропущено")
        else:
            print(f"✅ {s.get('match', 0)} полей совпало")

        if args.verbose and report.comparisons:
            if not args.only_mismatches or s.get("mismatch", 0) > 0 or s.get("missing", 0) > 0:
                print(format_comparison_report(report.comparisons, args.verbose))
            print()

    # ── Статистика ──
    print(f"\n{'='*80}")
    print(f"📊 Итоговая статистика")
    print(f"{'='*80}")

    total_fields = total_match + total_mismatch + total_missing + total_unchecked
    pct = total_fields and total_match / total_fields * 100 or 0
    pct_m = total_fields and total_mismatch / total_fields * 100 or 0
    pct_miss = total_fields and total_missing / total_fields * 100 or 0
    pct_u = total_fields and total_unchecked / total_fields * 100 or 0
    print(f"  ✅ Совпало:       {total_match}/{total_fields} ({pct:.0f}%)")
    print(f"  ❌ Не совпало:    {total_mismatch}/{total_fields} ({pct_m:.0f}%)")
    print(f"  ⚠️  Не найдено:    {total_missing}/{total_fields} ({pct_miss:.0f}%)")
    print(f"  📝 Не проверено:  {total_unchecked}/{total_fields} ({pct_u:.0f}%)")

    # Показать расхождения
    mismatches = [
        (r, c)
        for r in all_reports
        for c in r.comparisons
        if c.status in ("mismatch", "missing")
    ]

    if mismatches:
        print(f"\n{'='*80}")
        print(f"❌ Расхождения (первые 50)")
        print(f"{'='*80}")

        for report, comp in mismatches[:50]:
            print(f"\n  [{report.index}] {report.hex_preview}")
            print(f"  Файл: {report.file}")
            print(f"  Sheet: {report.sheet}")
            print(f"  {comp.status.upper()}: {comp.expected.name} [{comp.expected.data_type}]")
            if comp.expected.expected_value is not None:
                print(f"    Ожидалось: {comp.expected.expected_value}")
            if comp.actual:
                print(f"    Получено:  {comp.actual.value}")
            if comp.error:
                print(f"    {comp.error}")
            if args.verbose:
                print(f"    Эталон: {comp.expected.raw_line}")

    # Сохранение отчёта
    if args.output:
        output_file = Path(args.output)

        report_data = {
            "summary": {
                "total_fields": total_fields,
                "match": total_match,
                "mismatch": total_mismatch,
                "missing": total_missing,
                "unchecked": total_unchecked,
                "total_packets": len(all_reports),
                "packets_with_errors": sum(1 for r in all_reports if r.parse_errors),
                "packets_with_mismatches": sum(1 for r in all_reports if r.summary.get("mismatch", 0) > 0),
            },
            "packets": [
                {
                    "index": r.index,
                    "hex_preview": r.hex_preview,
                    "hex_length": r.hex_length,
                    "file": r.file,
                    "sheet": r.sheet,
                    "parse_errors": r.parse_errors,
                    "summary": r.summary,
                    "comparisons": [
                        {
                            "name": c.expected.name,
                            "type": c.expected.data_type,
                            "expected_value": c.expected.expected_value,
                            "actual_value": c.actual.value if c.actual else None,
                            "status": c.status,
                            "error": c.error,
                        }
                        for c in r.comparisons
                    ],
                }
                for r in all_reports
            ],
        }

        output_file.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  💾 Отчёт сохранён: {output_file}")

    return 0 if total_mismatch == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
