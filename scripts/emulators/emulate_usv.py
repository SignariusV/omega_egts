"""Полноценный эмулятор УСВ для тестирования по TCP.

Поддерживает:
- Полный цикл авторизации (TERM_IDENTITY -> AUTH_DATA -> RESULT_CODE response)
- Отправку телеметрии (NAVIGATION_DATA)
- Обработку входящих пакетов от платформы
- Интерактивный режим с командами оператора

Использование::

    # Быстрый старт - автоматическая авторизация
    python emulate_usv.py --port 3001 --host 127.0.0.1 --auto

    # Интерактивный режим (команды вручную)
    python emulate_usv.py --port 3001 --host 127.0.0.1 --interactive

    # Только авторизация (без интерактива)
    python emulate_usv.py --port 3001 --host 127.0.0.1
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
from libs.egts_protocol_gost2015.gost2015_impl.subrecord import Subrecord
from libs.egts_protocol_gost2015.gost2015_impl.types import (
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


# ─── FSM эмулятора ────────────────────────────────────────────────────────────

class UsvState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    AUTHENTICATING = "AUTHENTICATING"
    WAITING_AUTH_RESULT = "WAITING_AUTH_RESULT"
    AUTHORIZED = "AUTHORIZED"
    RUNNING = "RUNNING"


class UsvEmulatorFSM:
    def __init__(self) -> None:
        self.state = UsvState.DISCONNECTED
        self._next_pid = 100
        self._next_rn = 200
        self._last_platform_pid: int | None = None

    def transition(self, new_state: UsvState, reason: str = "") -> None:
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
        self.transition(UsvState.CONNECTED, "TCP подключено")

    def on_disconnect(self) -> None:
        self.transition(UsvState.DISCONNECTED, "TCP отключено")

    def on_term_identity_sent(self) -> None:
        self.transition(UsvState.AUTHENTICATING, "TERM_IDENTITY отправлен")

    def on_auth_data_sent(self) -> None:
        self.transition(UsvState.WAITING_AUTH_RESULT, "AUTH_DATA отправлен")

    def on_result_code_received(self, rcd: int) -> bool:
        if rcd == 1:
            self.transition(UsvState.AUTHORIZED, f"RESULT_CODE={rcd} (успех)")
            return True
        else:
            self.transition(UsvState.CONNECTED, f"RESULT_CODE={rcd} (ошибка)")
            return False

    def on_result_code_response_sent(self) -> None:
        self.transition(UsvState.RUNNING, "RESULT_CODE_RESPONSE отправлен")


# ─── Сборка EGTS-пакетов ──────────────────────────────────────────────────────

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
    vehicle_id = b"USV-EMULATOR"

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_VEHICLE_DATA,
        data=vehicle_id,
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


def build_navigation_data_packet(pid: int, rn: int) -> bytes:
    latitude = int(55.7558 * 60000)
    longitude = int(37.6173 * 60000)
    speed = 600
    direction = 180
    timestamp = int(time.time())

    srd = struct.pack("<I", timestamp)
    srd += struct.pack("<i", latitude)
    srd += struct.pack("<i", longitude)
    srd += struct.pack("<H", speed)
    srd += struct.pack("<B", direction)
    srd += b"\x00" * 10

    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_NAVIGATION_DATA,
        data=srd,
    )

    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_POSTAL_SERVICE,
        subrecords=[subrecord],
    )

    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.NORMAL,
        records=[record],
    )

    return packet.to_bytes()


# ─── Обработка входящих пакетов ───────────────────────────────────────────────

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
                sub_info: dict[str, Any] = {
                    "srt": sub.subrecord_type.name if hasattr(sub.subrecord_type, "name") else sub.subrecord_type,
                    "data": sub.data,
                }

                if sub.subrecord_type == SubrecordType.EGTS_SR_RECORD_RESPONSE:
                    if isinstance(sub.data, bytes) and len(sub.data) >= 3:
                        sub_info["crn"] = int.from_bytes(sub.data[0:2], "little")
                        sub_info["rst"] = sub.data[2]

                elif sub.subrecord_type == SubrecordType.EGTS_SR_RESULT_CODE:
                    if isinstance(sub.data, bytes) and len(sub.data) >= 1:
                        rcd = sub.data[0]
                        sub_info["rcd"] = rcd
                        rcd_texts = {
                            0: "Неизвестный результат",
                            1: "Успешная авторизация",
                            2: "Неверный TERM_IDENTITY",
                            3: "Неверные AUTH_PARAMS",
                        }
                        sub_info["rcd_text"] = rcd_texts.get(rcd, f"Код {rcd}")

                rec_info["subrecords"].append(sub_info)

            result["records"].append(rec_info)

        return result

    except Exception as e:
        print(f"  [ОШИБКА] Не удалось распарсить пакет: {e}")
        return None


# ─── Основной класс эмулятора ─────────────────────────────────────────────────

class UsvEmulator:
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
        self.fsm = UsvEmulatorFSM()
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
        buffer = b""
        while self._running:
            try:
                data = await self._reader.read(65536)
                if not data:
                    print("\n[ЭМУЛЯТОР] Сервер закрыл соединение")
                    self.fsm.on_disconnect()
                    break

                buffer += data
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
        self.fsm._last_platform_pid = pid

        print(f"  [ПАКЕТ] PID={pid}, PT={pt}")

        # RESPONSE от платформы
        if "RESPONSE" in pt or pt == "EGTS_PT_RESPONSE":
            pr = parsed.get("pr")
            rpid = parsed.get("rpid")
            print(f"    -> RESPONSE: PR={pr}, RPID={rpid}")
            if pr == 0:
                print(f"    -> Платформа подтвердила пакет {rpid}")

            if self.fsm.state == UsvState.AUTHENTICATING:
                print(f"    -> RESPONSE на TERM_IDENTITY - продолжаем авторизацию")

        elif "APPDATA" in pt or pt == "EGTS_PT_APPDATA":
            for rec in parsed.get("records", []):
                for sub in rec.get("subrecords", []):
                    srt = sub.get("srt")
                    await self._handle_subrecord(srt, sub, rec["rn"])

    async def _handle_subrecord(self, srt: str, sub: dict[str, Any], rn: int) -> None:
        if srt == "EGTS_SR_RESULT_CODE":
            rcd = sub.get("rcd")
            rcd_text = sub.get("rcd_text", "")
            print(f"    -> RESULT_CODE: {rcd} ({rcd_text})")
            success = self.fsm.on_result_code_received(rcd)

            if success and self.auto_mode:
                await asyncio.sleep(0.5)
                await self.send_result_code_response(rn)
                self.fsm.on_result_code_response_sent()
                if self.auto_mode:
                    await self.start_telemetry()

        elif srt == "EGTS_SR_RECORD_RESPONSE":
            crn = sub.get("crn")
            rst = sub.get("rst")
            print(f"    -> RECORD_RESPONSE: CRN={crn}, RST={rst}")

        elif srt == "EGTS_SR_AUTH_PARAMS":
            print(f"    -> AUTH_PARAMS от платформы")

        elif srt == "EGTS_SR_COMMAND_DATA":
            print(f"    -> COMMAND_DATA от платформы")

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
        self.fsm.on_term_identity_sent()

    async def send_auth_data(self) -> None:
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_vehicle_data_packet(pid, rn)
        await self._send_packet(packet, "VEHICLE_DATA")
        self.fsm.on_auth_data_sent()

    async def send_result_code_response(self, confirmed_rn: int) -> None:
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_result_code_response_packet(pid, rn, confirmed_rn)
        await self._send_packet(packet, "RECORD_RESPONSE")

    async def send_navigation_data(self) -> None:
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_navigation_data_packet(pid, rn)
        await self._send_packet(packet, "NAVIGATION_DATA")

    async def run_auto_sequence(self) -> None:
        print("\n[АВТО] Запуск автоматической последовательности...")

        print("\n[АВТО] Шаг 1: TERM_IDENTITY")
        await self.send_term_identity()
        await asyncio.sleep(1)

        print("\n[АВТО] Шаг 2: VEHICLE_DATA")
        await self.send_auth_data()
        await asyncio.sleep(1)

        print("\n[АВТО] Ожидание RESULT_CODE от платформы...")

    async def start_telemetry(self) -> None:
        print("\n[ТЕЛЕМЕТРИЯ] Запуск периодической отправки NAV_DATA...")
        count = 0
        while self._running and self.fsm.state == UsvState.RUNNING:
            count += 1
            await self.send_navigation_data()
            print(f"  [ТЕЛЕМЕТРИЯ] Пакет #{count} отправлен")
            await asyncio.sleep(5)

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

        elif cmd_lower in ("auth_data", "vehicle", "veh", "2"):
            print("\n[КОМАНДА] Отправка VEHICLE_DATA")
            await self.send_auth_data()

        elif cmd_lower in ("nav_data", "nav", "telemetry", "tel", "3"):
            print("\n[КОМАНДА] Отправка NAVIGATION_DATA")
            await self.send_navigation_data()

        elif cmd_lower in ("status", "st"):
            print(f"\n[СТАТУС] Состояние: {self.fsm.state.value}")
            print(f"  Следующий PID: {self.fsm._next_pid}")
            print(f"  Следующий RN: {self.fsm._next_rn}")

        elif cmd_lower in ("auto", "a"):
            print("\n[КОМАНДА] Запуск автоматической последовательности")
            self.auto_mode = True
            asyncio.create_task(self.run_auto_sequence())

        elif cmd_lower in ("help", "h", "?"):
            print("\n[СПРАВКА] Доступные команды:")
            print("  term_identity (1) - отправить TERM_IDENTITY")
            print("  auth_data (2)     - отправить VEHICLE_DATA")
            print("  nav_data (3)      - отправить NAVIGATION_DATA")
            print("  auto (a)          - автоматическая авторизация + телеметрия")
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
    print("  Эмулятор УСВ - тестирование сервера OMEGA_EGTS по TCP")
    print("=" * 60)

    emulator = UsvEmulator(
        host=host,
        port=port,
        auto_mode=auto,
        interactive=interactive,
    )

    try:
        await emulator.connect()

        if auto:
            asyncio.create_task(emulator.run_auto_sequence())

        if interactive:
            print("\n[ИНТЕРАКТИВ] Введите 'help' для списка команд")
            await emulator.process_commands()
        else:
            while emulator._running:
                await asyncio.sleep(1)

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
        description="Эмулятор УСВ для тестирования OMEGA_EGTS по TCP",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Адрес сервера (по умолч. 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3001, help="Порт сервера (по умолч. 3001)")
    parser.add_argument("--auto", action="store_true", help="Автоматическая авторизация + телеметрия")
    parser.add_argument("--interactive", action="store_true", help="Интерактивный режим")

    args = parser.parse_args()

    try:
        asyncio.run(main_async(args.host, args.port, args.auto, args.interactive))
    except KeyboardInterrupt:
        print("\n[ЭМУЛЯТОР] Прервано")
        sys.exit(0)


if __name__ == "__main__":
    main()
