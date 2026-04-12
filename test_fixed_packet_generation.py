"""Исправленная генерация пакетов с правильными флагами RFL.

Эталонные данные из data/packets/all_packets_correct_20260406_190414.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from libs.egts_protocol_gost2015.gost2015_impl.packet import Packet
from libs.egts_protocol_gost2015.gost2015_impl.record import Record
from libs.egts_protocol_gost2015.gost2015_impl.subrecord import Subrecord
from libs.egts_protocol_gost2015.gost2015_impl.types import (
    EGTS_CONFIRMATION_TYPE,
    PacketType,
    Priority,
    ServiceType,
    SubrecordType,
)
from libs.egts_protocol_gost2015.gost2015_impl.services.auth import (
    serialize_term_identity,
    serialize_vehicle_data,
    serialize_record_response,
    serialize_result_code,
)
from libs.egts_protocol_gost2015.gost2015_impl.services.commands import (
    create_command_response,
    serialize_command_data,
)

# ───────── Параметры УСВ ─────────

USV_TID = 1
USV_IMEI = "860803066448313"
USV_IMSI = "0250770017156439"
USV_NID = b"\x00\x01\x00"
USV_UNIT_ID = b"\x00\x00\x00\x01"
USV_VIN = "1D4GP25B038108775"  # Эталонный VIN


def build_term_identity_packet(pid: int, rn: int) -> bytes:
    """TERM_IDENTITY — TID=1, IMEI, IMSI.

    Эталон: 0100000B002E002A0001CC270049008001010124000100000016383630383033303636343438333133303235303737303031373135363433390F3A
    """
    srd_bytes = serialize_term_identity({
        "tid": USV_TID,
        "imeie": True,
        "imei": USV_IMEI,
        "imsie": True,
        "imsi": USV_IMSI,
        "lngce": False,
        "lngc": "",
        "ssra": False,
        "nide": False,  # NID не передаётся в эталоне
        "nid": b"",
        "bse": False,
        "bs": 0,
        "mne": False,
        "msisdn": "",
    })

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_TERM_IDENTITY,
        data=srd_bytes,
    )

    # RFL=0x80 → ssod=True (сервис-отправитель на УСВ)
    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
        ssod=True,  # Source Service On Device = 1
        rsod=False,
        rpp=0,
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


def build_vehicle_data_packet(pid: int, rn: int) -> bytes:
    """VEHICLE_DATA — VIN, VHT, VPST.

    Эталон: 0100000B0023002B0001781C004A00800101031900314434475032354230333831303837373501000000010000006CE1
    """
    srd_bytes = serialize_vehicle_data({
        "vin": USV_VIN,
        "vht": 1,  # Class M1
        "vpst": 1,  # бензин
    })

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_VEHICLE_DATA,
        data=srd_bytes,
    )

    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
        ssod=True,  # RFL=0x80
        rsod=False,
        rpp=0,
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


def build_comconf_packet(pid: int, rn: int, cid: int, cct: int = 0, result_data: bytes = b"") -> bytes:
    """COMCONF — подтверждение команды.

    Эталон CID=0: 0100000B001400270001DC0D004600800404330A0010000000000000000000CE40
    Эталон CID=2: 0100000B0014002900012B0D004800800404330A00100200000000000000002277
    """
    resp_dict = create_command_response(
        cid=cid,
        sid=0,
        cct=EGTS_CONFIRMATION_TYPE(cct),
        result_data=result_data,
    )

    srd_bytes = serialize_command_data(resp_dict)

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_COMMAND_DATA,
        data=srd_bytes,
    )

    # SST=4, RST=4 (COMMANDS_SERVICE)
    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_COMMANDS_SERVICE,
        subrecords=[subrecord],
        rst_service_type=ServiceType.EGTS_COMMANDS_SERVICE,
        ssod=True,  # RFL=0x80
        rsod=True,  # оба на УСВ
        rpp=0,
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.MEDIUM,
        records=[record],
    )

    return packet.to_bytes()


def build_result_code_response_packet(pid: int, rn: int, confirmed_rn: int) -> bytes:
    """RECORD_RESPONSE для RESULT_CODE.

    Эталон: 0100000B0010002C00006A20000006004B008001010003002F0000F139
    """
    srd_bytes = serialize_record_response({
        "crn": confirmed_rn,
        "rst": 0,
    })

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_RECORD_RESPONSE,
        data=srd_bytes,
    )

    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
        rst_service_type=ServiceType.EGTS_AUTH_SERVICE,
        ssod=True,  # RFL=0x80
        rsod=False,
        rpp=0,
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


def build_result_code_packet(pid: int, rn: int, rcd: int = 0) -> bytes:
    """RESULT_CODE — код результата аутентификации.

    Эталон: 0100000B000B002000012604002F0040010109010000BA4C
    """
    srd_bytes = serialize_result_code({"rcd": rcd})

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_RESULT_CODE,
        data=srd_bytes,
    )

    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
        ssod=False,  # RFL=0x40 (от платформы)
        rsod=True,
        rpp=0,
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


# ───────── Проверка ─────────

def main():
    print("=" * 80)
    print("  ПРОВЕРКА ИСПРАВЛЕННОЙ ГЕНЕРАЦИИ ПАКЕТОВ")
    print("=" * 80)

    # TERM_IDENTITY
    ti = build_term_identity_packet(pid=42, rn=73)
    ti_ref = bytes.fromhex("0100000B002E002A0001CC270049008001010124000100000016383630383033303636343438333133303235303737303031373135363433390F3A")
    print(f"\n  TERM_IDENTITY:")
    print(f"    Длина: {len(ti)} (эталон: {len(ti_ref)})")
    print(f"    HEX:   {ti.hex().upper()}")
    print(f"    REF:   {ti_ref.hex().upper()}")
    print(f"    Совп:  {'✅ ДА' if ti == ti_ref else '❌ НЕТ'}")

    # VEHICLE_DATA
    vd = build_vehicle_data_packet(pid=43, rn=74)
    vd_ref = bytes.fromhex("0100000B0023002B0001781C004A00800101031900314434475032354230333831303837373501000000010000006CE1")
    print(f"\n  VEHICLE_DATA:")
    print(f"    Длина: {len(vd)} (эталон: {len(vd_ref)})")
    print(f"    HEX:   {vd.hex().upper()}")
    print(f"    REF:   {vd_ref.hex().upper()}")
    print(f"    Совп:  {'✅ ДА' if vd == vd_ref else '❌ НЕТ'}")

    # COMCONF CID=0
    cc0 = build_comconf_packet(pid=39, rn=70, cid=0)
    cc0_ref = bytes.fromhex("0100000B001400270001DC0D004600800404330A0010000000000000000000CE40")
    print(f"\n  COMCONF CID=0:")
    print(f"    Длина: {len(cc0)} (эталон: {len(cc0_ref)})")
    print(f"    HEX:   {cc0.hex().upper()}")
    print(f"    REF:   {cc0_ref.hex().upper()}")
    print(f"    Совп:  {'✅ ДА' if cc0 == cc0_ref else '❌ НЕТ'}")

    # COMCONF CID=2 с result_data
    cc2 = build_comconf_packet(pid=41, rn=72, cid=2, result_data=b"\x00\x00\x00\x01")
    cc2_ref = bytes.fromhex("0100000B0014002900012B0D004800800404330A00100200000000000000002277")
    print(f"\n  COMCONF CID=2:")
    print(f"    Длина: {len(cc2)} (эталон: {len(cc2_ref)})")
    print(f"    HEX:   {cc2.hex().upper()}")
    print(f"    REF:   {cc2_ref.hex().upper()}")
    print(f"    Совп:  {'✅ ДА' if cc2 == cc2_ref else '❌ НЕТ'}")

    # RECORD_RESPONSE
    rr = build_result_code_response_packet(pid=44, rn=75, confirmed_rn=47)
    rr_ref = bytes.fromhex("0100000B0010002C00006A20000006004B008001010003002F0000F139")
    print(f"\n  RECORD_RESPONSE:")
    print(f"    Длина: {len(rr)} (эталон: {len(rr_ref)})")
    print(f"    HEX:   {rr.hex().upper()}")
    print(f"    REF:   {rr_ref.hex().upper()}")
    print(f"    Совп:  {'✅ ДА' if rr == rr_ref else '❌ НЕТ'}")


if __name__ == "__main__":
    main()
