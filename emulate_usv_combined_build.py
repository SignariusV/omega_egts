"""Эмулятор УСВ: Верификация + Аутентификация в одной TCP-сессии.

Все пакеты **динамически генерируются через библиотеку EGTS** (без HEX-файлов).

Использование::

    python emulate_usv_combined_build.py --auto        # полный автомат
    python emulate_usv_combined_build.py --interactive # ручной режим
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from enum import Enum
from typing import Any

# ───────── Импорт библиотеки EGTS ─────────

from libs.egts_protocol_gost2015.gost2015_impl.packet import Packet
from libs.egts_protocol_gost2015.gost2015_impl.record import Record
from libs.egts_protocol_gost2015.gost2015_impl.subrecord import Subrecord
from libs.egts_protocol_gost2015.gost2015_impl.types import (
    EGTS_COMMAND_TYPE,
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
)
from libs.egts_protocol_gost2015.gost2015_impl.services.commands import (
    create_command_response,
    serialize_command_data,
)

# ───────── Константы ─────────

# Параметры УСВ
USV_TID = 1
USV_IMEI = "860803066448313"
USV_IMSI = "0250770017156439"
USV_NID = b"\x00\x01\x00"
USV_UNIT_ID = b"\x00\x00\x00\x01"
USV_VEHICLE_ID = b"USV-EMULATOR"

# Коды команд верификации
CCD_GPRS_APN = 0x0203
CCD_SERVER_ADDRESS = 0x0204
CCD_UNIT_ID = 0x0205
CCD_UNIT_ID_PARAM = 0x0404


# ───────── FSM ─────────

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

    # Аутентификация
    def on_verification_complete(self) -> None:
        self.transition(CombinedState.A_AUTHENTICATING, "Верификация завершена, начинаем авторизацию")

    def on_term_identity_sent(self) -> None:
        self.transition(CombinedState.A_AUTHENTICATING, "TERM_IDENTITY отправлен")

    def on_vehicle_data_sent(self) -> None:
        self.transition(CombinedState.A_VEHICLE_SENT, "VEHICLE_DATA отправлен")

    def on_waiting_result(self) -> None:
        self.transition(CombinedState.A_WAITING_RESULT, "Ожидание RESULT_CODE")

    def on_result_code_received(self, rcd: int) -> None:
        self.result_code_received = True
        self.result_code_value = rcd
        self.transition(CombinedState.A_AUTHORIZED, f"RESULT_CODE={rcd}")

    def on_result_code_response_sent(self) -> None:
        self.transition(CombinedState.A_RUNNING, "RECORD_RESPONSE отправлен — авторизация завершена")

    def on_response_received(self) -> None:
        self.responses_received += 1


# ───────── Генераторы пакетов (динамическая сборка через библиотеку) ─────────

def build_term_identity_packet(pid: int, rn: int) -> bytes:
    """Собрать пакет TERM_IDENTITY через библиотеку EGTS."""
    # 1. Сериализуем данные сабрекорда
    srd_bytes = serialize_term_identity({
        "tid": USV_TID,
        "imeie": True,
        "imei": USV_IMEI,
        "imsie": True,
        "imsi": USV_IMSI,
        "lngce": False,
        "lngc": "",
        "ssra": False,
        "nide": True,
        "nid": USV_NID,
        "bse": False,
        "bs": 0,
        "mne": False,
        "msisdn": "",
    })

    # 2. Создаём сабрекорд
    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_TERM_IDENTITY,
        data=srd_bytes,
    )

    # 3. Создаём запись (PPU)
    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
    )

    # 4. Создаём транспортный пакет
    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    # 5. Сериализуем в байты (с CRC-8 + CRC-16)
    return packet.to_bytes()


def build_vehicle_data_packet(pid: int, rn: int) -> bytes:
    """Собрать пакет VEHICLE_DATA через библиотеку EGTS."""
    # 1. Сериализуем данные сабрекорда
    srd_bytes = serialize_vehicle_data({
        "vin": USV_VEHICLE_ID.ljust(17, b"\x00").decode("ascii")[:17],
        "vht": 0,  # тип структуры
        "vpst": 0,  # тип структуры
    })

    # 2. Создаём сабрекорд
    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_VEHICLE_DATA,
        data=srd_bytes,
    )

    # 3. Создаём запись
    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
    )

    # 4. Создаём пакет
    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


def build_comconf_packet(pid: int, rn: int, cid: int, cct: int = 0, result_data: bytes = b"") -> bytes:
    """Собрать пакет COMCONF (подтверждение команды) через библиотеку EGTS."""
    # 1. Создаём словарь подтверждения команды
    resp_dict = create_command_response(
        cid=cid,
        sid=0,
        cct=EGTS_CONFIRMATION_TYPE(cct),
        result_data=result_data,
    )

    # 2. Сериализуем данные команды
    srd_bytes = serialize_command_data(resp_dict)

    # 3. Создаём сабрекорд COMMAND_DATA
    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_COMMAND_DATA,
        data=srd_bytes,
    )

    # 4. Создаём запись
    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_COMMANDS_SERVICE,
        subrecords=[subrecord],
    )

    # 5. Создаём пакет
    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.MEDIUM,
        records=[record],
    )

    return packet.to_bytes()


def build_result_code_response_packet(pid: int, rn: int, confirmed_rn: int) -> bytes:
    """Собрать пакет RECORD_RESPONSE для RESULT_CODE через библиотеку EGTS."""
    # 1. Сериализуем ответ на запись
    srd_bytes = serialize_record_response({
        "crn": confirmed_rn,
        "rst": 0,  # успешно
    })

    # 2. Создаём сабрекорд
    subrecord = Subrecord(
        subrecord_type=SubrecordType.EGTS_SR_RECORD_RESPONSE,
        data=srd_bytes,
    )

    # 3. Создаём запись
    record = Record(
        record_id=rn,
        service_type=ServiceType.EGTS_AUTH_SERVICE,
        subrecords=[subrecord],
    )

    # 4. Создаём пакет
    packet = Packet(
        packet_id=pid,
        packet_type=PacketType.EGTS_PT_APPDATA,
        priority=Priority.HIGHEST,
        records=[record],
    )

    return packet.to_bytes()


# ───────── Эмулятор ─────────

class CombinedEmulator:
    """Эмулятор УСВ с динамической генерацией пакетов через библиотеку EGTS."""

    def __init__(self, host: str, port: int, auto_mode: bool = True, interactive: bool = False) -> None:
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
        print(f"\n  [ЭМУЛЯТОР] Подключение к {self.host}:{self.port}...")
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        self._running = True
        self.fsm.on_connect()
        print("  [ЭМУЛЯТОР] Подключено!")

    async def disconnect(self) -> None:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self.fsm.on_disconnect()
        self._running = False
        print("  [ЭМУЛЯТОР] Отключено")

    async def run(self) -> None:
        """Основной цикл эмулятора."""
        tasks = [
            asyncio.create_task(self._receive_loop()),
        ]

        if self.auto_mode:
            tasks.append(asyncio.create_task(self._auto_mode()))
        elif self.interactive:
            tasks.append(asyncio.create_task(self._interactive_input()))
            tasks.append(asyncio.create_task(self._process_commands()))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    async def _receive_loop(self) -> None:
        """Цикл приёма пакетов от сервера."""
        while self._running and self._reader:
            try:
                # Читаем заголовок (минимум 16 байт)
                header = await asyncio.wait_for(self._reader.read(16), timeout=1.0)
                if not header:
                    print("\n  [СЕРВЕР] Закрыл соединение")
                    self._running = False
                    break

                # Читаем остаток пакета по длине
                pkt_len = header[0]  # HL поле
                remaining = pkt_len - 16 if pkt_len > 16 else 0
                body = await asyncio.wait_for(self._reader.read(remaining), timeout=5.0) if remaining else b""

                full_packet = header + body
                await self._handle_packet(full_packet)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"\n  [ОШИБКА] Приёма: {e}")
                self._running = False
                break

    async def _handle_packet(self, raw: bytes) -> None:
        """Обработать входящий пакет."""
        print(f"\n  [ВХОД] Получено {len(raw)} байт: {raw.hex().upper()}")

        # Минимальный парсинг для определения типа пакета
        if len(raw) < 16:
            print("    [!] Слишком короткий пакет")
            return

        # PT (Packet Type) — поле в заголовке
        pt_byte = raw[4] if len(raw) > 4 else 0

        # RESPONSE
        if pt_byte & 0x0F == 0x01:  # EGTS_PT_RESPONSE
            print(f"  [ПАКЕТ] RESPONSE")
            self.fsm.on_response_received()
            return

        # APPDATA — разбираем записи
        if pt_byte & 0x0F == 0x00:  # EGTS_PT_APPDATA
            # Упрощённый парсинг — ищем COMMAND_DATA или RESULT_CODE
            if b"\x40\x04" in raw:  # EGTS_SR_COMMAND_DATA marker
                await self._handle_command_data(raw)
            elif b"\x01\x00" in raw:  # EGTS_SR_RESULT_CODE marker
                await self._handle_result_code(raw)

    async def _handle_command_data(self, raw: bytes) -> None:
        """Обработать COMMAND_DATA."""
        # Ищем CCD (команда) в пакете
        # Структура: ... SRT(2) SRL(2) CT(1) CCT(1) CID(4) ... CCD(2) ...
        ccd_offset = raw.find(b"\x02\x03")  # GPRS_APN
        if ccd_offset == -1:
            ccd_offset = raw.find(b"\x02\x04")  # SERVER_ADDRESS
        if ccd_offset == -1:
            ccd_offset = raw.find(b"\x02\x05")  # UNIT_ID
        if ccd_offset == -1:
            ccd_offset = raw.find(b"\x04\x04")  # UNIT_ID параметр

        if ccd_offset == -1:
            print("    [?] Неизвестная команда")
            return

        ccd = int.from_bytes(raw[ccd_offset:ccd_offset+2], "big")
        ccd_names = {
            CCD_GPRS_APN: "GPRS_APN",
            CCD_SERVER_ADDRESS: "SERVER_ADDRESS",
            CCD_UNIT_ID: "UNIT_ID",
            CCD_UNIT_ID_PARAM: "UNIT_ID",
        }
        name = ccd_names.get(ccd, f"0x{ccd:04X}")
        print(f"    -> COMMAND_DATA: {name}")

        # Автоматический ответ COMCONF
        if self.auto_mode:
            if ccd == CCD_GPRS_APN:
                self.fsm.on_apn_received()
                await asyncio.sleep(0.3)
                await self.send_comconf(cid=0)
                self.fsm.on_apn_confirmed()

            elif ccd == CCD_SERVER_ADDRESS:
                self.fsm.on_address_received()
                await asyncio.sleep(0.3)
                await self.send_comconf(cid=1)
                self.fsm.on_address_confirmed()

            elif ccd in (CCD_UNIT_ID, CCD_UNIT_ID_PARAM):
                self.fsm.on_unit_id_received()
                await asyncio.sleep(0.3)
                await self.send_comconf(cid=2, result_data=USV_UNIT_ID)
                self.fsm.on_unit_id_confirmed()

            # Проверяем завершение верификации
            if self.fsm.state == CombinedState.V_DONE:
                print(f"\n  [ВЕРИФИКАЦИЯ] ✅ Все 3 команды получены и подтверждены!")
                print(f"  [АВТО] Запускаем аутентификацию...")
                await asyncio.sleep(1)
                await self.run_authentication()

    async def _handle_result_code(self, raw: bytes) -> None:
        """Обработать RESULT_CODE."""
        # Ищем RCD (Result Code Data) — 1 байт после маркера
        rcd_marker = raw.find(b"\x01\x00")  # EGTS_SR_RESULT_CODE
        if rcd_marker != -1 and len(raw) > rcd_marker + 6:
            rcd = raw[rcd_marker + 5]  # RCD поле
            print(f"    -> RESULT_CODE: {rcd}")
            self.fsm.on_result_code_received(rcd)

            if self.fsm.result_code_received and self.auto_mode:
                await asyncio.sleep(0.5)
                await self.send_result_code_response(rcd)
                self.fsm.on_result_code_response_sent()

    # ───────── Отправка пакетов (через библиотеку) ─────────

    async def _send_packet(self, packet_bytes: bytes, label: str = "") -> None:
        """Отправить пакет на сервер."""
        if not self._writer:
            print("[ОШИБКА] Не подключено к серверу")
            return
        self._writer.write(packet_bytes)
        await self._writer.drain()
        label_str = f" ({label})" if label else ""
        print(f"  [ВЫХОД] Отправлено {len(packet_bytes)} байт{label_str}: {packet_bytes.hex().upper()}")

    async def send_comconf(self, cid: int, cct: int = 0, result_data: bytes = b"") -> None:
        """Отправить COMCONF (подтверждение команды)."""
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_comconf_packet(pid, rn, cid, cct, result_data)
        await self._send_packet(packet, f"COMCONF(cid={cid})")

    async def send_term_identity(self) -> None:
        """Отправить TERM_IDENTITY."""
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_term_identity_packet(pid, rn)
        await self._send_packet(packet, "TERM_IDENTITY")
        self.fsm.on_term_identity_sent()

    async def send_vehicle_data(self) -> None:
        """Отправить VEHICLE_DATA."""
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_vehicle_data_packet(pid, rn)
        await self._send_packet(packet, "VEHICLE_DATA")
        self.fsm.on_vehicle_data_sent()

    async def send_result_code_response(self, confirmed_rn: int) -> None:
        """Отправить RECORD_RESPONSE для RESULT_CODE."""
        pid = self.fsm.next_pid()
        rn = self.fsm.next_rn()
        packet = build_result_code_response_packet(pid, rn, confirmed_rn)
        await self._send_packet(packet, "RECORD_RESPONSE")

    # ───────── Режимы работы ─────────

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

    async def _auto_mode(self) -> None:
        """Автоматический режим — ждёт команд верификации."""
        print("\n[АВТО] Полный цикл: верификация → аутентификация")
        print("[АВТО] Ожидание команд верификации от платформы...")
        while self._running:
            await asyncio.sleep(1)
            if self.fsm.state == CombinedState.A_RUNNING:
                print(f"\n\n  [УСПЕХ] Полный цикл завершён!")
                await asyncio.sleep(3)
                self._running = False
                break

    async def _interactive_input(self) -> None:
        """Чтение команд из stdin."""
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                await self._command_queue.put(line.strip())
            except Exception:
                break

    async def _process_commands(self) -> None:
        """Обработка интерактивных команд."""
        while self._running:
            try:
                cmd = await asyncio.wait_for(self._command_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await self._handle_command(cmd)

    async def _handle_command(self, cmd: str) -> None:
        """Обработать одну команду."""
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
            if self.fsm.state == CombinedState.V_DONE:
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


# ───────── Точка входа ─────────

async def main_async(host: str, port: int, auto: bool, interactive: bool) -> None:
    print("=" * 60)
    print("  Эмулятор УСВ — Верификация + Аутентификация")
    print("  ПАКЕТЫ ГЕНЕРИРУЮТСЯ ЧЕРЕЗ БИБЛИОТЕКУ EGTS (без HEX)")
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
        await emulator.run()

    except ConnectionRefusedError:
        print(f"\n[ОШИБКА] Не удалось подключиться к {host}:{port}")
        sys.exit(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[ЭМУЛЯТОР] Прервано")
    finally:
        await emulator.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Эмулятор УСВ: Верификация + Аутентификация (динамическая генерация пакетов)",
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
