"""Эмулятор УСВ для сценария верификации (TCP).

Обрабатывает COMMAND_DATA команды от платформы и отвечает COMCONF:
- GPRS_APN (CCD=0x0203) → COMCONF(cid=0)
- SERVER_ADDRESS (CCD=0x0204) → COMCONF(cid=1)
- UNIT_ID (CCD=0x0205) → COMCONF(cid=2) с UNIT_ID в ответе

Использование::

    # Только верификация (автоматически отвечает на команды)
    python emulate_usv_verification.py --port 3001 --auto

    # Интерактивный режим
    python emulate_usv_verification.py --port 3001 --interactive

    # Вместе с сервером в одном процессе
    python test_verification_with_emulator.py
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
USV_UNIT_ID = b"\x00\x00\x00\x01"  # UNIT_ID эмулятора


# ─── FSM ──────────────────────────────────────────────────────────────────────

class VerificationState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    WAITING_APN = "WAITING_APN"
    WAITING_ADDRESS = "WAITING_ADDRESS"
    WAITING_UNIT_ID = "WAITING_UNIT_ID"
    VERIFIED = "VERIFIED"


class VerificationFSM:
    def __init__(self) -> None:
        self.state = VerificationState.DISCONNECTED
        self._next_pid = 100
        self._next_rn = 200
        self.received_commands: list[dict[str, Any]] = []

    def transition(self, new_state: VerificationState, reason: str = "") -> None:
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
        self.transition(VerificationState.CONNECTED, "TCP подключено")

    def on_disconnect(self) -> None:
        self.transition(VerificationState.DISCONNECTED, "TCP отключено")

    def on_apn_received(self) -> None:
        self.transition(VerificationState.WAITING_APN, "GPRS_APN получена")

    def on_address_received(self) -> None:
        self.transition(VerificationState.WAITING_ADDRESS, "SERVER_ADDRESS получен")

    def on_unit_id_received(self) -> None:
        self.transition(VerificationState.WAITING_UNIT_ID, "UNIT_ID запрос получен")

    def on_apn_confirmed(self) -> None:
        self.transition(VerificationState.CONNECTED, "APN подтверждён")

    def on_address_confirmed(self) -> None:
        self.transition(VerificationState.CONNECTED, "Адрес подтверждён")

    def on_unit_id_confirmed(self) -> None:
        self.transition(VerificationState.VERIFIED, "UNIT_ID подтверждён — верификация завершена")


# ─── Сборка пакетов ───────────────────────────────────────────────────────────

def build_term_identity_packet(pid: int, rn: int) -> bytes:
    """TERM_IDENTITY — первый пакет для авторизации УСВ."""
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


def build_comconf_packet(pid: int, rn: int, cid: int, cct: int = 0, result_data: bytes = b"") -> bytes:
    """COMCONF-ответ на COMMAND_DATA.

    Args:
        pid: ID пакета
        rn: ID записи
        cid: ID команды (тот же что в запросе)
        cct: тип подтверждения (0=OK)
        result_data: данные результата (для UNIT_ID — сам UNIT_ID)
    """
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
                # srt может быть int или SubrecordType enum
                if hasattr(srt_raw, "name"):
                    srt = srt_raw.name
                else:
                    srt = str(srt_raw)

                sub_info: dict[str, Any] = {
                    "srt": srt,
                    "srt_raw": srt_raw,
                    "data": sub.data,
                }

                # Парсим COMMAND_DATA SRD
                is_command_data = (
                    srt_raw == SubrecordType.EGTS_SR_COMMAND_DATA
                    or srt == "EGTS_SR_COMMAND_DATA"
                    or srt == "51"
                )
                if is_command_data:
                    if isinstance(sub.data, bytes):
                        try:
                            cmd_parsed = parse_command_data(sub.data)
                            sub_info["command"] = cmd_parsed
                            sub_info["ct"] = cmd_parsed.get("ct")
                            sub_info["cid"] = cmd_parsed.get("cid")

                            # Разбираем CD если это COM запрос
                            cd_bytes = cmd_parsed.get("cd", b"")
                            if cd_bytes and cmd_parsed.get("ct") == 5:  # COM
                                details = parse_command_details(cd_bytes)
                                sub_info["command_details"] = details
                                sub_info["ccd"] = details.get("ccd")
                                sub_info["act"] = details.get("act")
                                sub_info["data"] = details.get("dt", b"")
                        except Exception as e:
                            sub_info["parse_error"] = str(e)

                # RECORD_RESPONSE
                elif sub.subrecord_type == SubrecordType.EGTS_SR_RECORD_RESPONSE:
                    if isinstance(sub.data, bytes) and len(sub.data) >= 3:
                        sub_info["crn"] = int.from_bytes(sub.data[0:2], "little")
                        sub_info["rst"] = sub.data[2]

                # RESULT_CODE
                elif sub.subrecord_type == SubrecordType.EGTS_SR_RESULT_CODE:
                    if isinstance(sub.data, bytes) and len(sub.data) >= 1:
                        sub_info["rcd"] = sub.data[0]

                rec_info["subrecords"].append(sub_info)

            result["records"].append(rec_info)

        return result

    except Exception as e:
        print(f"  [ОШИБКА] Не удалось распарсить пакет: {e}")
        return None


# ─── Эмулятор УСВ для верификации ─────────────────────────────────────────────

class VerificationEmulator:
    """Эмулятор УСВ для сценария верификации.

    Автоматически отвечает COMCONF на COMMAND_DATA команды:
    - GPRS_APN (CCD=0x0203) → COMCONF(cid=0)
    - SERVER_ADDRESS (CCD=0x0204) → COMCONF(cid=1)
    - UNIT_ID (CCD=0x0205) → COMCONF(cid=2, result_data=UNIT_ID)
    """

    # Коды команд (CCD)
    CCD_GPRS_APN = 0x0203
    CCD_SERVER_ADDRESS = 0x0204
    CCD_UNIT_ID = 0x0205
    CCD_UNIT_ID_PARAM = 0x0404  # EGTS_UNIT_ID_PARAM — альтернативный код

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
        self.fsm = VerificationFSM()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False
        self._read_task: asyncio.Task[None] | None = None
        self._command_queue: asyncio.Queue[str] = asyncio.Queue()

    async def connect(self) -> None:
        print(f"\n[ЭМУЛЯТОР] Подключение к {self.host}:{self.port}...")
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        self.fsm.on_connect()
        self._running = True
        print(f"[ЭМУЛЯТОР] Подключено!")
        self._read_task = asyncio.create_task(self._read_loop())
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
            return

        # APPDATA — обрабатываем записи
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

            print(f"    -> COMMAND_DATA: ct={ct}, cid={cid}, ccd=0x{ccd:04X} ({ccd}), act={act}")

            if ct == 5:  # COM — запрос команды от платформы
                self.fsm.received_commands.append({
                    "cid": cid,
                    "ccd": ccd,
                    "act": act,
                    "data": data_bytes,
                })

                # Определяем тип команды и отвечаем
                if ccd == self.CCD_GPRS_APN:
                    text_data = data_bytes.decode("ascii", errors="replace") if data_bytes else ""
                    print(f"       Команда: GPRS_APN, данные: '{text_data}'")
                    self.fsm.on_apn_received()
                    if self.auto_mode:
                        await asyncio.sleep(0.3)
                        await self.send_comconf(cid=0)
                        self.fsm.on_apn_confirmed()

                elif ccd == self.CCD_SERVER_ADDRESS:
                    text_data = data_bytes.decode("ascii", errors="replace") if data_bytes else ""
                    print(f"       Команда: SERVER_ADDRESS, данные: '{text_data}'")
                    self.fsm.on_address_received()
                    if self.auto_mode:
                        await asyncio.sleep(0.3)
                        await self.send_comconf(cid=1)
                        self.fsm.on_address_confirmed()

                elif ccd == self.CCD_UNIT_ID or ccd == self.CCD_UNIT_ID_PARAM:
                    print(f"       Команда: UNIT_ID (запрос)")
                    self.fsm.on_unit_id_received()
                    if self.auto_mode:
                        await asyncio.sleep(0.3)
                        # Для UNIT_ID возвращаем UNIT_ID в result_data
                        await self.send_comconf(cid=2, result_data=USV_UNIT_ID)
                        self.fsm.on_unit_id_confirmed()
                        print(f"\n  [ВЕРИФИКАЦИЯ] ЗАВЕРШЕНА! УСВ прошло все проверки.")

                else:
                    print(f"       Команда: неизвестная CCD=0x{ccd:04X}")
                    # Отвечаем COMCONF с cid как есть
                    if self.auto_mode:
                        await asyncio.sleep(0.3)
                        await self.send_comconf(cid=cid or 0)

            elif ct == 1:  # COMCONF — подтверждение от платформы
                cct = cmd.get("cct")
                print(f"       COMCONF от платформы: cid={cid}, cct={cct}")

        elif srt == "EGTS_SR_TERM_IDENTITY":
            print(f"    -> TERM_IDENTITY от платформы (необычно)")

        elif srt == "EGTS_SR_RECORD_RESPONSE":
            crn = sub.get("crn")
            rst = sub.get("rst")
            print(f"    -> RECORD_RESPONSE: CRN={crn}, RST={rst}")

        elif srt == "EGTS_SR_RESULT_CODE":
            rcd = sub.get("rcd")
            print(f"    -> RESULT_CODE: {rcd}")

        else:
            print(f"    -> {srt} (обработка не реализована)")

    async def _send_packet(self, packet_bytes: bytes, label: str = "") -> None:
        if not self._writer:
            print("[ОШИБКА] Не подключено к серверу")
            return

        self._writer.write(packet_bytes)
        await self._writer.drain()
        label_str = f" ({label})" if label else ""
        print(f"  [ВЫХОД] Отправлено {len(packet_bytes)} байт{label_str}: {packet_bytes.hex().upper()}")

    async def send_term_identity(self) -> None:
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_term_identity_packet(pid, rn)
        await self._send_packet(packet, "TERM_IDENTITY")

    async def send_comconf(self, cid: int, cct: int = 0, result_data: bytes = b"") -> None:
        """Отправить COMCONF-подтверждение."""
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_comconf_packet(pid, rn, cid, cct, result_data)
        label = f"COMCONF(cid={cid})"
        await self._send_packet(packet, label)

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

        if cmd_lower in ("term_identity", "tid", "1"):
            print("\n[КОМАНДА] Отправка TERM_IDENTITY")
            await self.send_term_identity()

        elif cmd_lower in ("comconf0", "apn", "2"):
            print("\n[КОМАНДА] Отправка COMCONF(cid=0) — APN")
            await self.send_comconf(cid=0)
            self.fsm.on_apn_confirmed()

        elif cmd_lower in ("comconf1", "addr", "3"):
            print("\n[КОМАНДА] Отправка COMCONF(cid=1) — адрес")
            await self.send_comconf(cid=1)
            self.fsm.on_address_confirmed()

        elif cmd_lower in ("comconf2", "unitid", "4"):
            print("\n[КОМАНДА] Отправка COMCONF(cid=2) — UNIT_ID")
            await self.send_comconf(cid=2, result_data=USV_UNIT_ID)
            self.fsm.on_unit_id_confirmed()
            print("\n  [ВЕРИФИКАЦИЯ] ЗАВЕРШЕНА!")

        elif cmd_lower in ("status", "st"):
            print(f"\n[СТАТУС] Состояние: {self.fsm.state.value}")
            print(f"  Получено команд: {len(self.fsm.received_commands)}")
            for c in self.fsm.received_commands:
                ccd = c.get("ccd", 0)
                cid = c.get("cid", 0)
                data = c.get("data", b"")
                text = data.decode("ascii", errors="replace") if data else ""
                print(f"    cid={cid}, CCD=0x{ccd:04X}, данные='{text}'")

        elif cmd_lower in ("auto", "a"):
            print("\n[АВТО] Автоматический режим включён")
            self.auto_mode = True

        elif cmd_lower in ("help", "h", "?"):
            print("\n[СПРАВКА] Доступные команды:")
            print("  term_identity (1) - отправить TERM_IDENTITY")
            print("  comconf0/apn (2)  - COMCONF(cid=0) — подтверждение APN")
            print("  comconf1/addr (3) - COMCONF(cid=1) — подтверждение адреса")
            print("  comconf2/unitid (4) - COMCONF(cid=2) — подтверждение UNIT_ID")
            print("  auto (a)          - автоматический режим")
            print("  status (st)       - показать статус")
            print("  quit (q)          - выйти")
            print("  help (h)          - эта справка")

        elif cmd_lower in ("quit", "q", "exit"):
            print("\n[ЭМУЛЯТОР] Выход по команде")
            self._running = False

        else:
            print(f"\n[НЕИЗВЕСТНАЯ КОМАНДА] '{cmd}'. Введите 'help' для справки.")


# ─── Точка входа ──────────────────────────────────────────────────────────────

async def main_async(host: str, port: int, auto: bool, interactive: bool) -> None:
    print("=" * 60)
    print("  Эмулятор УСВ — Верификация (TCP)")
    print("=" * 60)

    emulator = VerificationEmulator(
        host=host,
        port=port,
        auto_mode=auto,
        interactive=interactive,
    )

    try:
        await emulator.connect()

        if interactive:
            print("\n[ИНТЕРАКТИВ] Введите 'help' для списка команд")
            await emulator.process_commands()
        else:
            print("\n[ЭМУЛЯТОР] Готов принимать команды от платформы")
            if auto:
                print("[АВТО] Автоматический режим — будет отвечать COMCONF")
            while emulator._running:
                await asyncio.sleep(1)
                state = emulator.fsm.state.value
                cmds = len(emulator.fsm.received_commands)
                print(f"  [{state}] Команд получено: {cmds}", end="\r")

    except ConnectionRefusedError:
        print(f"\n[ОШИБКА] Не удалось подключиться к {host}:{port}")
        print(f"  Убедитесь, что сервер запущен: python run_server.py")
        sys.exit(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[ЭМУЛЯТОР] Прервано пользователем")
    finally:
        await emulator.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Эмулятор УСВ для сценария верификации (TCP)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Адрес сервера")
    parser.add_argument("--port", type=int, default=3001, help="Порт сервера")
    parser.add_argument("--auto", action="store_true", help="Автоматический ответ COMCONF")
    parser.add_argument("--interactive", action="store_true", help="Интерактивный режим")

    args = parser.parse_args()

    try:
        asyncio.run(main_async(args.host, args.port, args.auto, args.interactive))
    except KeyboardInterrupt:
        print("\n[ЭМУЛЯТОР] Прервано")
        sys.exit(0)


if __name__ == "__main__":
    main()
