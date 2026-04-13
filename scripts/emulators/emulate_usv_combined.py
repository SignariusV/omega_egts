"""Эмулятор УСВ: Верификация + Аутентификация в одной TCP-сессии.

Сначала выполняется верификация (получение команд APN, адрес, UNIT_ID),
затем аутентификация (TERM_IDENTITY, VEHICLE_DATA, ожидание RESULT_CODE).

Использование::

    python test_verification_then_auth.py --auto        # полный автомат
    python test_verification_then_auth.py --interactive # ручной режим
"""
from __future__ import annotations

import argparse
import asyncio
import struct
import sys
import time
from enum import Enum
from typing import Any


# ─── Импорт библиотек EGTS ───────────────────────────────────────────────────

from libs.egts_protocol_gost2015.gost2015_impl.packet import Packet
from libs.egts_protocol_gost2015.gost2015_impl.record import Record
from libs.egts_protocol_gost2015.gost2015_impl.services.auth import (
    serialize_term_identity,
)
from libs.egts_protocol_gost2015.gost2015_impl.services.commands import (
    create_command_response,
    parse_command_data,
    parse_command_details,
    serialize_command_data,
)
from libs.egts_protocol_gost2015.gost2015_impl.subrecord import Subrecord
from libs.egts_protocol_gost2015.gost2015_impl.types import (
    EGTS_COMMAND_TYPE,
    EGTS_CONFIRMATION_TYPE,
    PacketType,
    Priority,
    ServiceType,
    SubrecordType,
)


# ─── Константы ────────────────────────────────────────────────────────────────

USV_TID = 1
USV_IMEI = "860803066448313"
USV_IMSI = "0250770017156439"
USV_NID = b"\x00\x01\x00"
USV_UNIT_ID = b"\x00\x00\x00\x01"
USV_VEHICLE_ID = b"USV-EMULATOR"


# ─── FSM ──────────────────────────────────────────────────────────────────────

class CombinedState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    # Фаза 1: Верификация
    V_WAITING_COMMANDS = "V_WAITING_COMMANDS"
    V_APN_RECEIVED = "V_APN_RECEIVED"
    V_ADDR_RECEIVED = "V_ADDR_RECEIVED"
    V_UNIT_ID_RECEIVED = "V_UNIT_ID_RECEIVED"
    V_DONE = "V_DONE"
    # Фаза 2: Аутентификация
    A_AUTHENTICATING = "A_AUTHENTICATING"
    A_VEHICLE_SENT = "A_VEHICLE_SENT"
    A_WAITING_RESULT = "A_WAITING_RESULT"
    A_AUTHORIZED = "A_AUTHORIZED"
    A_RUNNING = "A_RUNNING"


class CombinedFSM:
    def __init__(self) -> None:
        self.state = CombinedState.DISCONNECTED
        self._next_pid = 100
        self._next_rn = 200
        self.received_commands: list[dict[str, Any]] = []
        self.responses_received: int = 0
        self.result_code_received: bool = False
        self.result_code_value: int = -1

    def transition(self, new_state: CombinedState, reason: str = "") -> None:
        old = self.state
        self.state = new_state
        print(f"  [FSM] {old.value} -> {new_state.value}" + (f" ({reason})" if reason else ""))

    def next_pid(self) -> int:
        pid = self._next_pid
        self._next_pid += 1
        return pid

    def next_rn(self) -> int:
        rn = self._next_rn
        self._next_rn += 1
        return rn

    def on_connect(self) -> None:
        self.transition(CombinedState.V_WAITING_COMMANDS, "TCP подключено, ожидаем команды верификации")

    def on_disconnect(self) -> None:
        self.transition(CombinedState.DISCONNECTED, "TCP отключено")

    # Верификация
    def on_apn_received(self) -> None:
        self.transition(CombinedState.V_APN_RECEIVED, "GPRS_APN получена")

    def on_apn_confirmed(self) -> None:
        self.transition(CombinedState.V_WAITING_COMMANDS, "APN подтверждён")

    def on_address_received(self) -> None:
        self.transition(CombinedState.V_ADDR_RECEIVED, "SERVER_ADDRESS получен")

    def on_address_confirmed(self) -> None:
        self.transition(CombinedState.V_WAITING_COMMANDS, "Адрес подтверждён")

    def on_unit_id_received(self) -> None:
        self.transition(CombinedState.V_UNIT_ID_RECEIVED, "UNIT_ID запрос получен")

    def on_unit_id_confirmed(self) -> None:
        self.transition(CombinedState.V_DONE, "UNIT_ID подтверждён — верификация завершена")

    def on_verification_complete(self) -> None:
        self.transition(CombinedState.A_AUTHENTICATING, "Верификация завершена, начинаем авторизацию")

    # Аутентификация
    def on_term_identity_sent(self) -> None:
        self.transition(CombinedState.A_AUTHENTICATING, "TERM_IDENTITY отправлен")

    def on_vehicle_data_sent(self) -> None:
        self.transition(CombinedState.A_VEHICLE_SENT, "VEHICLE_DATA отправлен")

    def on_waiting_result(self) -> None:
        self.transition(CombinedState.A_WAITING_RESULT, "Ожидание RESULT_CODE")

    def on_result_code_received(self, rcd: int) -> None:
        self.result_code_received = True
        self.result_code_value = rcd
        if rcd == 1:
            self.transition(CombinedState.A_AUTHORIZED, f"RESULT_CODE={rcd} (успех)")
        else:
            self.transition(CombinedState.A_AUTHENTICATING, f"RESULT_CODE={rcd} (ошибка)")

    def on_result_code_response_sent(self) -> None:
        self.transition(CombinedState.A_RUNNING, "RESULT_CODE_RESPONSE отправлен — СЕССИЯ ЗАВЕРШЕНА УСПЕШНО")

    def on_response_received(self) -> None:
        self.responses_received += 1


# ─── Сборка пакетов ───────────────────────────────────────────────────────────

def build_term_identity_packet(pid: int, rn: int) -> bytes:
    term_identity_data = {
        "tid": USV_TID,
        "imeie": True,
        "imei": USV_IMEI,
        "imsie": True,
        "imsi": USV_IMSI,
        "nide": True,
        "nid": USV_NID,
    }
    srd_bytes = serialize_term_identity(term_identity_data)

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_TERM_IDENTITY,
        data=srd_bytes,
    )

    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


def build_vehicle_data_packet(pid: int, rn: int) -> bytes:
    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_VEHICLE_DATA,
        data=USV_VEHICLE_ID,
    )

    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


def build_comconf_packet(pid: int, rn: int, cid: int, cct: int = 0, result_data: bytes = b"") -> bytes:
    resp_dict = create_command_response(
        cid=cid,
        sid=0,
        cct=EGTS_CONFIRMATION_TYPE.OK if cct == 0 else EGTS_CONFIRMATION_TYPE.ERROR,
        result_data=result_data,
    )
    srd_bytes = serialize_command_data(resp_dict)

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_COMMAND_DATA,
        data=srd_bytes,
    )

    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_COMMANDS_SERVICE,
        subrecords=[subrecord],
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.MEDIUM,
        records=[record],
    )

    return packet.to_bytes()


def build_result_code_response_packet(pid: int, rn: int, confirmed_rn: int) -> bytes:
    srd = confirmed_rn.to_bytes(2, "little") + b"\x00"

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_RECORD_RESPONSE,
        data=srd,
    )

    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


# ─── Парсинг входящих пакетов ─────────────────────────────────────────────────

def parse_incoming_packet(data: bytes) -> dict[str, Any] | None:
    try:
        packet = Packet.from_bytes(data)

        pt_raw = packet.packet_type
        if pt_raw is not None:
            pt_name = pt_raw.name if hasattr(pt_raw, "name") else str(pt_raw)
        else:
            pt_name = "EGTS_PT_RESPONSE" if packet.response_packet_id is not None else "UNKNOWN"

        result: dict[str, Any] = {
            "pid": packet.packet_id,
            "pt": pt_name,
            "rpid": packet.response_packet_id,
            "pr": packet.processing_result,
        }

        records = packet.parse_records()
        result["records"] = []

        for rec in records:
            rec_info: dict[str, Any] = {
                "rn": rec.record_id,
                "service": rec.service_type.name if hasattr(rec.service_type, "name") else rec.service_type,
                "subrecords": [],
            }

            for sub in getattr(rec, "subrecords", []):
                srt_raw = sub.subrecord_type
                if hasattr(srt_raw, "name"):
                    srt = srt_raw.name
                else:
                    srt = str(srt_raw)

                sub_info: dict[str, Any] = {
                    "srt": srt,
                    "srt_raw": srt_raw,
                    "data": sub.data,
                }

                # COMMAND_DATA
                is_command_data = (
                    srt_raw == SubrecordType.EGTS_SR_COMMAND_DATA
                    or srt == "EGTS_SR_COMMAND_DATA"
                    or srt == "51"
                )
                if is_command_data and isinstance(sub.data, bytes):
                    try:
                        cmd_parsed = parse_command_data(sub.data)
                        sub_info["command"] = cmd_parsed
                        sub_info["ct"] = cmd_parsed.get("ct")
                        sub_info["cid"] = cmd_parsed.get("cid")
                        cd_bytes = cmd_parsed.get("cd", b"")
                        if cd_bytes and cmd_parsed.get("ct") == 5:
                            details = parse_command_details(cd_bytes)
                            sub_info["command_details"] = details
                            sub_info["ccd"] = details.get("ccd")
                            sub_info["act"] = details.get("act")
                            sub_info["data"] = details.get("dt", b"")
                    except Exception as e:
                        sub_info["parse_error"] = str(e)

                # RECORD_RESPONSE
                elif srt_raw == SubrecordType.EGTS_SR_RECORD_RESPONSE or srt == "EGTS_SR_RECORD_RESPONSE":
                    if isinstance(sub.data, bytes) and len(sub.data) >= 3:
                        sub_info["crn"] = int.from_bytes(sub.data[0:2], "little")
                        sub_info["rst"] = sub.data[2]

                # RESULT_CODE
                elif srt_raw == SubrecordType.EGTS_SR_RESULT_CODE or srt == "EGTS_SR_RESULT_CODE":
                    if isinstance(sub.data, bytes) and len(sub.data) >= 1:
                        sub_info["rcd"] = sub.data[0]

                rec_info["subrecords"].append(sub_info)

            result["records"].append(rec_info)

        return result

    except Exception as e:
        print(f"  [ОШИБКА] Не удалось распарсить пакет: {e}")
        return None


# ─── Комбинированный эмулятор ─────────────────────────────────────────────────

CCD_GPRS_APN = 0x0203
CCD_SERVER_ADDRESS = 0x0204
CCD_UNIT_ID = 0x0205
CCD_UNIT_ID_PARAM = 0x0404


class CombinedEmulator:
    """Эмулятор: верификация → аутентификация в одной сессии."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3001,
        auto_mode: bool = False,
        interactive: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.auto_mode = auto_mode
        self.interactive = interactive
        self.fsm = CombinedFSM()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False
        self._command_queue: asyncio.Queue[str] = asyncio.Queue()

    async def connect(self) -> None:
        print(f"\n[ЭМУЛЯТОР] Подключение к {self.host}:{self.port}...")
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        self.fsm.on_connect()
        self._running = True
        print("[ЭМУЛЯТОР] Подключено!")
        asyncio.create_task(self._read_loop())
        if self.interactive:
            asyncio.create_task(self._interactive_input())

    async def disconnect(self) -> None:
        self._running = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self.fsm.on_disconnect()
        print("[ЭМУЛЯТОР] Отключено")

    async def _read_loop(self) -> None:
        while self._running:
            try:
                data = await self._reader.read(65536)
                if not data:
                    print("\n[ЭМУЛЯТОР] Сервер закрыл соединение")
                    self.fsm.on_disconnect()
                    break

                print(f"\n  [ВХОД] Получено {len(data)} байт: {data.hex().upper()}")

                parsed = parse_incoming_packet(data)
                if parsed:
                    await self._handle_packet(parsed)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"\n  [ОШИБКА] При чтении: {e}")
                break

    async def _handle_packet(self, parsed: dict[str, Any]) -> None:
        pid = parsed["pid"]
        pt = parsed["pt"]
        print(f"  [ПАКЕТ] PID={pid}, PT={pt}")

        # RESPONSE
        if "RESPONSE" in pt or pt == "EGTS_PT_RESPONSE":
            pr = parsed.get("pr")
            rpid = parsed.get("rpid")
            print(f"    -> RESPONSE: PR={pr}, RPID={rpid}")
            if pr == 0:
                print(f"    -> Платформа подтвердила пакет {rpid}")
            self.fsm.on_response_received()
            return

        # APPDATA
        if "APPDATA" in pt or pt == "EGTS_PT_APPDATA":
            for rec in parsed.get("records", []):
                for sub in rec.get("subrecords", []):
                    srt = sub.get("srt")
                    await self._handle_subrecord(srt, sub, rec["rn"])

    async def _handle_subrecord(self, srt: str, sub: dict[str, Any], rn: int) -> None:
        srt_raw = sub.get("srt_raw")
        is_command_data = (
            srt_raw == SubrecordType.EGTS_SR_COMMAND_DATA
            or srt == "EGTS_SR_COMMAND_DATA"
            or srt == "51"
        )

        if is_command_data:
            cmd = sub.get("command", {})
            ct = sub.get("ct")
            cid = sub.get("cid")
            ccd = sub.get("ccd")
            act = sub.get("act")
            data_bytes = sub.get("data", b"")

            print(f"    -> COMMAND_DATA: ct={ct}, cid={cid}, ccd=0x{ccd:04X}, act={act}")

            if ct == 5:  # COM запрос
                self.fsm.received_commands.append({
                    "cid": cid,
                    "ccd": ccd,
                    "act": act,
                    "data": data_bytes,
                })

                if ccd in (CCD_GPRS_APN, CCD_SERVER_ADDRESS, CCD_UNIT_ID, CCD_UNIT_ID_PARAM):
                    text = data_bytes.decode("ascii", errors="replace") if data_bytes else ""
                    ccd_names = {
                        CCD_GPRS_APN: "GPRS_APN",
                        CCD_SERVER_ADDRESS: "SERVER_ADDRESS",
                        CCD_UNIT_ID: "UNIT_ID",
                        CCD_UNIT_ID_PARAM: "UNIT_ID",
                    }
                    name = ccd_names.get(ccd, f"0x{ccd:04X}")
                    print(f"       Команда: {name}, данные: '{text}'")

                    # Определяем cid для COMCONF
                    if ccd == CCD_GPRS_APN:
                        self.fsm.on_apn_received()
                        if self.auto_mode:
                            await asyncio.sleep(0.3)
                            await self.send_comconf(cid=0)
                            self.fsm.on_apn_confirmed()

                    elif ccd == CCD_SERVER_ADDRESS:
                        self.fsm.on_address_received()
                        if self.auto_mode:
                            await asyncio.sleep(0.3)
                            await self.send_comconf(cid=1)
                            self.fsm.on_address_confirmed()

                    elif ccd in (CCD_UNIT_ID, CCD_UNIT_ID_PARAM):
                        self.fsm.on_unit_id_received()
                        if self.auto_mode:
                            await asyncio.sleep(0.3)
                            await self.send_comconf(cid=2, result_data=USV_UNIT_ID)
                            self.fsm.on_unit_id_confirmed()

                    # Проверяем завершение верификации
                    if self.fsm.state == CombinedState.V_DONE and self.auto_mode:
                        print(f"\n  [ВЕРИФИКАЦИЯ] ✅ Все 3 команды получены и подтверждены!")
                        print(f"  [АВТО] Запускаем аутентификацию...")
                        await asyncio.sleep(1)
                        await self.run_authentication()

                else:
                    print(f"       Команда: неизвестная CCD=0x{ccd:04X}")
                    if self.auto_mode:
                        await asyncio.sleep(0.3)
                        await self.send_comconf(cid=cid or 0)

        elif srt == "EGTS_SR_RESULT_CODE":
            rcd = sub.get("rcd")
            print(f"    -> RESULT_CODE: {rcd}")
            self.fsm.on_result_code_received(rcd)

            if self.fsm.result_code_received and self.auto_mode:
                await asyncio.sleep(0.5)
                await self.send_result_code_response(rn)
                self.fsm.on_result_code_response_sent()

        elif srt == "EGTS_SR_RECORD_RESPONSE":
            crn = sub.get("crn")
            rst = sub.get("rst")
            print(f"    -> RECORD_RESPONSE: CRN={crn}, RST={rst}")

    async def _send_packet(self, packet_bytes: bytes, label: str = "") -> None:
        if not self._writer:
            print("[ОШИБКА] Не подключено к серверу")
            return
        self._writer.write(packet_bytes)
        await self._writer.drain()
        label_str = f" ({label})" if label else ""
        print(f"  [ВЫХОД] Отправлено {len(packet_bytes)} байт{label_str}: {packet_bytes.hex().upper()}")

    async def send_comconf(self, cid: int, cct: int = 0, result_data: bytes = b"") -> None:
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_comconf_packet(pid, rn, cid, cct, result_data)
        await self._send_packet(packet, f"COMCONF(cid={cid})")

    async def send_term_identity(self) -> None:
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_term_identity_packet(pid, rn)
        await self._send_packet(packet, "TERM_IDENTITY")
        self.fsm.on_term_identity_sent()

    async def send_vehicle_data(self) -> None:
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_vehicle_data_packet(pid, rn)
        await self._send_packet(packet, "VEHICLE_DATA")
        self.fsm.on_vehicle_data_sent()

    async def send_result_code_response(self, confirmed_rn: int) -> None:
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_result_code_response_packet(pid, rn, confirmed_rn)
        await self._send_packet(packet, "RECORD_RESPONSE")

    async def run_authentication(self) -> None:
        """Запустить фазу аутентификации после верификации."""
        self.fsm.on_verification_complete()

        print("\n  [АВТО] Шаг A1: TERM_IDENTITY")
        await self.send_term_identity()
        await asyncio.sleep(1)

        print("\n  [АВТО] Шаг A2: VEHICLE_DATA")
        await self.send_vehicle_data()
        await asyncio.sleep(0.5)

        self.fsm.on_waiting_result()
        print("\n  [АВТО] Ожидание RESULT_CODE от платформы...")

    async def _interactive_input(self) -> None:
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                await self._command_queue.put(line.strip())
            except Exception:
                break

    async def process_commands(self) -> None:
        while self._running:
            try:
                cmd = await asyncio.wait_for(self._command_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await self._handle_command(cmd)

    async def _handle_command(self, cmd: str) -> None:
        cmd_lower = cmd.lower().strip()

        if cmd_lower in ("v1", "apn"):
            print("\n[КОМАНДА] COMCONF(cid=0) — APN")
            self.fsm.on_apn_received()
            await self.send_comconf(cid=0)
            self.fsm.on_apn_confirmed()

        elif cmd_lower in ("v2", "addr"):
            print("\n[КОМАНДА] COMCONF(cid=1) — адрес")
            self.fsm.on_address_received()
            await self.send_comconf(cid=1)
            self.fsm.on_address_confirmed()

        elif cmd_lower in ("v3", "unitid"):
            print("\n[КОМАНДА] COMCONF(cid=2) — UNIT_ID")
            self.fsm.on_unit_id_received()
            await self.send_comconf(cid=2, result_data=USV_UNIT_ID)
            self.fsm.on_unit_id_confirmed()

        elif cmd_lower in ("auth", "a1"):
            print("\n[КОМАНДА] TERM_IDENTITY")
            await self.send_term_identity()

        elif cmd_lower in ("vehicle", "a2"):
            print("\n[КОМАНДА] VEHICLE_DATA")
            await self.send_vehicle_data()

        elif cmd_lower in ("start", "go"):
            print("\n[КОМАНДА] Запуск полного цикла")
            if self.fsm.state == CombinedState.V_WAITING_COMMANDS:
                print("  Ожидание команд верификации от платформы...")
            elif self.fsm.state == CombinedState.V_DONE:
                await self.run_authentication()

        elif cmd_lower in ("status", "st"):
            print(f"\n[СТАТУС] Состояние: {self.fsm.state.value}")
            print(f"  Команд верификации: {len(self.fsm.received_commands)}")
            print(f"  RESPONSE получено: {self.fsm.responses_received}")
            print(f"  RESULT_CODE: {'да (rcd=' + str(self.fsm.result_code_value) + ')' if self.fsm.result_code_received else 'нет'}")

        elif cmd_lower in ("help", "h", "?"):
            print("\n[СПРАВКА] Верификация:")
            print("  v1/apn    — COMCONF(cid=0) подтверждение APN")
            print("  v2/addr   — COMCONF(cid=1) подтверждение адреса")
            print("  v3/unitid — COMCONF(cid=2) подтверждение UNIT_ID")
            print("\n[СПРАВКА] Аутентификация:")
            print("  auth/a1   — TERM_IDENTITY")
            print("  vehicle/a2 — VEHICLE_DATA")
            print("\n[СПРАВКА] Общее:")
            print("  start/go  — запустить полный цикл")
            print("  status/st — статус")
            print("  quit/q    — выход")
            print("  help/h    — справка")

        elif cmd_lower in ("quit", "q", "exit"):
            print("\n[ЭМУЛЯТОР] Выход")
            self._running = False

        else:
            print(f"\n[НЕИЗВЕСТНАЯ] '{cmd}'. Введите 'help'.")


# ─── Точка входа ──────────────────────────────────────────────────────────────

async def main_async(host: str, port: int, auto: bool, interactive: bool) -> None:
    print("=" * 60)
    print("  Эмулятор УСВ — Верификация + Аутентификация")
    print("=" * 60)
    print("\n  Фаза 1: Верификация (APN → Адрес → UNIT_ID)")
    print("  Фаза 2: Аутентификация (TERM_IDENTITY → VEHICLE_DATA → RESULT_CODE)")
    print("=" * 60)

    emulator = CombinedEmulator(
        host=host,
        port=port,
        auto_mode=auto,
        interactive=interactive,
    )

    try:
        await emulator.connect()

        if auto:
            print("\n[АВТО] Полный цикл: верификация → аутентификация")
            print("[АВТО] Ожидание команд верификации от платформы...")

        if interactive:
            print("\n[ИНТЕРАКТИВ] Введите 'help' для справки")
            await emulator.process_commands()
        else:
            while emulator._running:
                await asyncio.sleep(1)
                state = emulator.fsm.state.value
                cmds = len(emulator.fsm.received_commands)
                print(f"  [{state}] Команд:{cmds} RESP:{emulator.fsm.responses_received}", end="\r")

                if state == CombinedState.A_RUNNING:
                    print(f"\n\n  [УСПЕХ] Полный цикл завершён!")
                    await asyncio.sleep(3)
                    break

    except ConnectionRefusedError:
        print(f"\n[ОШИБКА] Не удалось подключиться к {host}:{port}")
        sys.exit(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[ЭМУЛЯТОР] Прервано")
    finally:
        await emulator.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Эмулятор УСВ: Верификация + Аутентификация в одной сессии",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Адрес сервера")
    parser.add_argument("--port", type=int, default=3001, help="Порт сервера")
    parser.add_argument("--auto", action="store_true", help="Автоматический полный цикл")
    parser.add_argument("--interactive", action="store_true", help="Интерактивный режим")

    args = parser.parse_args()

    try:
        asyncio.run(main_async(args.host, args.port, args.auto, args.interactive))
    except KeyboardInterrupt:
        print("\n[ЭМУЛЯТОР] Прервано")
        sys.exit(0)


if __name__ == "__main__":
    main()
