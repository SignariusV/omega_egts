
"""Демонстрация всех возможностей новой EGTS библиотеки.

Запуск:/
    python -m examples.demo_new_library

Показывает:
1. Создание пакета вручную (модели)
2. Сборку пакета в байты (build_packet)
3. Парсинг пакета из байтов (parse_packet)
4. Roundtrip (parse → build → сравнение байтов)
5. Создание RESPONSE-пакета
6. Разные типы подзаписей
7. Реестр версий протокола
8. CRC вычисления
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────
# Импорт библиотеки
# ──────────────────────────────────────────────────────────────
# Импортируем парсеры подзаписей (они регистрируются автоматически)
import libs.egts._gost2015  # noqa: F401
from libs.egts.models import Packet, ParseResult, Record, ResponseRecord, Subrecord
from libs.egts.protocol import IEgtsProtocol
from libs.egts.registry import available_versions, get_protocol
from libs.egts.types import PacketType, ResultCode, ServiceType, SubrecordType

# ──────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────

def section(title: str) -> None:
    """Печать заголовка секции."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def hex_dump(data: bytes, width: int = 32) -> str:
    """Красивый hex-dump."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        lines.append(f"  {i:04d}: {hex_part}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# 1. Реестр версий
# ──────────────────────────────────────────────────────────────

def demo_registry() -> None:
    """Реестр версий протокола."""
    section("1. РЕЕСТР ВЕРСИЙ ПРОТОКОЛА")

    versions = available_versions()
    print(f"  Зарегистрированные версии: {versions}")

    proto: IEgtsProtocol = get_protocol("2015")
    print(f"  Протокол: {proto.version}")
    print(f"  Возможности: {proto.capabilities}")


# ──────────────────────────────────────────────────────────────
# 2. Создание пакета вручную (модели)
# ──────────────────────────────────────────────────────────────

def demo_create_packet() -> Packet:
    """Создание полного EGTS пакета из моделей."""
    section("2. СОЗДАНИЕ ПАКЕТА ВРУЧНУЮ (МОДЕЛИ)")

    # ── Подзапись RESULT_CODE (SRT=9) ──
    result_code = Subrecord(
        subrecord_type=SubrecordType.RESULT_CODE,
        data={"rcd": 0, "rcd_text": "OK"},
    )
    print(f"  Подзапись RESULT_CODE: SRT={result_code.subrecord_type}, data={result_code.data}")

    # ── Подзапись TERM_IDENTITY (SRT=1) ──
    term_identity = Subrecord(
        subrecord_type=SubrecordType.TERM_IDENTITY,
        data={
            "tid": 12345,
            "flags": 0xFE,
            "imeie": True,
            "imsie": True,
            "lngce": True,
            "nide": True,
            "bse": True,
            "mne": True,
            "imei": "310780066448313",
            "imsi": "250010000000000",
            "lngc": "rus",
            "nid": bytes([0x02, 0x03, 0x02]),
            "bs": 1024,
            "msisdn": "internet",
        },
    )
    print(f"  Подзапись TERM_IDENTITY: SRT={term_identity.subrecord_type}, tid={term_identity.data['tid']}")

    # ── Подзапись AUTH_INFO (SRT=7) ──
    auth_info = Subrecord(
        subrecord_type=SubrecordType.AUTH_INFO,
        data={"unm": "test_user", "upsw": "test_pass", "ss": None},
    )
    print(f"  Подзапись AUTH_INFO: SRT={auth_info.subrecord_type}, unm={auth_info.data['unm']}")

    # ── Запись авторизации (service=1) ──
    auth_record = Record(
        record_id=1,
        service_type=ServiceType.AUTH,
        recipient_service_type=0,
        subrecords=[term_identity],
        ssod=True,
        rsod=False,
        rpp=0,
    )
    print(f"  Запись AUTH: RN={auth_record.record_id}, SST={auth_record.service_type}")

    # ── Запись с RESULT_CODE (подтверждение) ──
    result_record = Record(
        record_id=2,
        service_type=ServiceType.AUTH,
        subrecords=[result_code],
        rsod=True,
    )
    print(f"  Запись RESULT: RN={result_record.record_id}")

    # ── Пакет транспортного уровня ──
    packet = Packet(
        protocol_version=1,
        security_key_id=0,
        prefix=False,
        routing=False,
        encryption=0,
        compressed=False,
        priority=0,
        header_encoding=0,
        packet_id=42,
        packet_type=PacketType.APPDATA,
        records=[auth_record, result_record],
    )
    print(f"  Пакет: PID={packet.packet_id}, PT={packet.packet_type}, записей={len(packet.records)}")

    return packet


# ──────────────────────────────────────────────────────────────
# 3. Сборка пакета в байты
# ──────────────────────────────────────────────────────────────

def demo_build_packet(packet: Packet, proto: IEgtsProtocol) -> bytes:
    """Сборка пакета в байты."""
    section("3. СБОРКА ПАКЕТА В БАЙТЫ (build_packet)")

    raw = proto.build_packet(packet)
    print(f"  Размер: {len(raw)} байт")
    print(f"  Hex:\n{hex_dump(raw)}")

    return raw


# ──────────────────────────────────────────────────────────────
# 4. Парсинг пакета из байтов
# ──────────────────────────────────────────────────────────────

def demo_parse_packet(raw: bytes, proto: IEgtsProtocol) -> ParseResult:
    """Парсинг пакета из байтов."""
    section("4. ПАРСИНГ ПАКЕТА ИЗ БАЙТОВ (parse_packet)")

    result = proto.parse_packet(raw)

    if result.is_success:
        pkt = result.packet
        print("  ✅ Успешно!")
        print(f"  PRV={pkt.protocol_version}, PID={pkt.packet_id}, PT={pkt.packet_type}")
        print(f"  HL={pkt.header_length}, записей={len(pkt.records)}")

        for i, rec in enumerate(pkt.records):
            print(f"  Запись {i}: RN={rec.record_id}, SST={rec.service_type}, "
                  f"подзаписей={len(rec.subrecords)}")
            for sr in rec.subrecords:
                if isinstance(sr.data, dict):
                    # Показываем только ключевые поля
                    keys = list(sr.data.keys())[:5]
                    print(f"    SRT={sr.subrecord_type}: data={{{', '.join(keys)}}}")
                else:
                    print(f"    SRT={sr.subrecord_type}: data=bytes({len(sr.data)})")
    else:
        print(f"  ❌ Ошибка: {result.errors}")

    return result


# ──────────────────────────────────────────────────────────────
# 5. Roundtrip тест
# ──────────────────────────────────────────────────────────────

def demo_roundtrip(original_raw: bytes, parsed: ParseResult, proto: IEgtsProtocol) -> None:
    """Roundtrip: parse → build → сравнение байтов."""
    section("5. ROUNDTRIP ТЕСТ (parse → build → compare)")

    if not parsed.is_success:
        print("  ❌ Пропуск: пакет не распарсился")
        return

    rebuilt = proto.build_packet(parsed.packet)

    match = rebuilt == original_raw
    print(f"  Оригинал: {len(original_raw)} байт")
    print(f"  Собрано:   {len(rebuilt)} байт")
    print(f"  Совпадение: {'✅ ДА (байт-в-байт)' if match else '❌ НЕТ'}")

    if not match:
        print(f"\n  Оригинал:\n{hex_dump(original_raw)}")
        print(f"\n  Собрано:\n{hex_dump(rebuilt)}")


# ──────────────────────────────────────────────────────────────
# 6. Создание RESPONSE-пакета
# ──────────────────────────────────────────────────────────────

def demo_response_packet(proto: IEgtsProtocol) -> bytes:
    """Создание RESPONSE-пакета (подтверждение)."""
    section("6. СОЗДАНИЕ RESPONSE-ПАКЕТА (build_response)")

    # RESPONSE для PID=42, RESULT_CODE=0 (OK), подтверждение записи RN=1
    response_record = ResponseRecord(
        rn=1,
        service=ServiceType.AUTH,
        subrecords=[],
        rsod=True,
    )

    response_bytes = proto.build_response(
        pid=42,
        result_code=ResultCode.OK,
        records=[response_record],
    )

    print(f"  Размер: {len(response_bytes)} байт")
    print(f"  Hex:\n{hex_dump(response_bytes)}")

    # Парсим RESPONSE обратно
    result = proto.parse_packet(response_bytes)
    if result.is_success:
        pkt = result.packet
        print("  Распарсен:")
        print(f"    PT={pkt.packet_type} (RESPONSE=0)")
        print(f"    RPID={pkt.response_packet_id}")
        print(f"    PR={pkt.processing_result}")
        print(f"    записей={len(pkt.records)}")
        for rec in pkt.records:
            print(f"      RN={rec.record_id}, SST={rec.service_type}")
            for sr in rec.subrecords:
                if isinstance(sr.data, dict):
                    print(f"        SRT={sr.subrecord_type}: {sr.data}")

    return response_bytes


# ──────────────────────────────────────────────────────────────
# 7. Разные типы подзаписей
# ──────────────────────────────────────────────────────────────

def demo_subrecord_types(proto: IEgtsProtocol) -> None:
    """Демонстрация разных типов подзаписей."""
    section("7. РАЗНЫЕ ТИПЫ ПОДЗАПИСЕЙ")

    examples = [
        ("RESULT_CODE (SRT=9)", SubrecordType.RESULT_CODE, {"rcd": 0}),
        ("RECORD_RESPONSE (SRT=0)", SubrecordType.RECORD_RESPONSE, {"crn": 42, "rst": 0}),
        ("COMMAND_DATA (SRT=51)", SubrecordType.COMMAND_DATA, {
            "ct": 1, "cct": 0, "cid": 100, "sid": 200,
            "acfe": False, "chsfe": False, "cd": b"test",
        }),
    ]

    for name, srt, data in examples:
        sub = Subrecord(subrecord_type=srt, data=data)
        rec = Record(record_id=1, service_type=ServiceType.AUTH, subrecords=[sub])
        pkt = Packet(packet_id=99, packet_type=PacketType.APPDATA, records=[rec])

        raw = proto.build_packet(pkt)
        result = proto.parse_packet(raw)

        status = "✅" if result.is_success else "❌"
        print(f"  {status} {name}")
        if result.is_success and result.packet.records:
            sr = result.packet.records[0].subrecords[0]
            print(f"      SRT={sr.subrecord_type}, data={sr.data}")


# ──────────────────────────────────────────────────────────────
# 8. CRC вычисления
# ──────────────────────────────────────────────────────────────

def demo_crc(proto: IEgtsProtocol) -> None:
    """CRC-8 и CRC-16 вычисления."""
    section("8. CRC ВЫЧИСЛЕНИЯ")

    test_data = bytes([0x01, 0x02, 0x03, 0x04, 0x05])

    crc8_val = proto.calculate_crc8(test_data)
    crc16_val = proto.calculate_crc16(test_data)

    print(f"  Данные: {test_data.hex().upper()}")
    print(f"  CRC-8:  0x{crc8_val:02X} ({crc8_val})")
    print(f"  CRC-16: 0x{crc16_val:04X} ({crc16_val})")

    # Проверка
    valid8 = proto.validate_crc8(test_data, crc8_val)
    valid16 = proto.validate_crc16(test_data, crc16_val)
    print(f"  CRC-8  валиден:  {'✅' if valid8 else '❌'}")
    print(f"  CRC-16 валиден:  {'✅' if valid16 else '❌'}")


# ──────────────────────────────────────────────────────────────
# 9. Парсинг эталонного пакета
# ──────────────────────────────────────────────────────────────

def demo_real_packet(proto: IEgtsProtocol) -> None:
    """Парсинг реального эталонного пакета."""
    section("9. ПАРСИНГ РЕАЛЬНОГО ЭТАЛОННОГО ПАКЕТА")

    # TERM_IDENTITY из реального теста
    hex_str = (
        "0100000B002E002A0001CC2700490080010101240001000000"
        "16383630383033303636343438333133303235303737303031"
        "373135363433390F3A"
    )
    raw = bytes.fromhex(hex_str)
    print(f"  Размер: {len(raw)} байт")
    print(f"  Hex:\n{hex_dump(raw)}")

    result = proto.parse_packet(raw)
    if result.is_success:
        pkt = result.packet
        print("\n  ✅ Распарсен:")
        print(f"    PRV={pkt.protocol_version}, PID={pkt.packet_id}, PT={pkt.packet_type}")
        print(f"    HL={pkt.header_length}, FDL={len(raw) - pkt.header_length - 2}")
        print(f"    Записей: {len(pkt.records)}")

        for i, rec in enumerate(pkt.records):
            print(f"\n    Запись {i}:")
            print(f"      RN={rec.record_id}, SST={rec.service_type}")
            print(f"      SSOD={rec.ssod}, RSOD={rec.rsod}, RPP={rec.rpp}")
            for sr in rec.subrecords:
                print(f"      Подзапись SRT={sr.subrecord_type}:")
                if isinstance(sr.data, dict):
                    for k, v in sr.data.items():
                        if isinstance(v, bytes):
                            print(f"        {k}: bytes({len(v)}) = {v.hex().upper()}")
                        else:
                            print(f"        {k}: {v}")
                else:
                    print(f"        data: bytes({len(sr.data)})")
    else:
        print(f"  ❌ Ошибка: {result.errors}")


# ──────────────────────────────────────────────────────────────
# Главная функция
# ──────────────────────────────────────────────────────────────

def main() -> None:
    """Запуск всех демо."""
    print("\n" + "=" * 70)
    print("  DEMO: Новая EGTS библиотека (libs/egts/)")
    print("  ГОСТ 33465-2015 — транспортный уровень")
    print("=" * 70)

    # Получаем протокол
    proto = get_protocol("2015")

    # 1. Реестр
    demo_registry()

    # 2. Создание пакета
    packet = demo_create_packet()

    # 3. Сборка в байты
    raw = demo_build_packet(packet, proto)

    # 4. Парсинг
    parsed = demo_parse_packet(raw, proto)

    # 5. Roundtrip
    demo_roundtrip(raw, parsed, proto)

    # 6. RESPONSE
    demo_response_packet(proto)

    # 7. Разные подзаписи
    demo_subrecord_types(proto)

    # 8. CRC
    demo_crc(proto)

    # 9. Реальный пакет
    demo_real_packet(proto)

    print("\n" + "=" * 70)
    print("  DEMO ЗАВЕРШЁН")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
