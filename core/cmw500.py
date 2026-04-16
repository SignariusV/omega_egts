"""Cmw500Controller — контроллер CMW-500 через RsCmwGsmSig.

Используются реальные SCPI-команды из comands.txt.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from core.event_bus import EventBus

if TYPE_CHECKING:
    from RsCmwGsmSig import RsCmwGsmSig

logger = logging.getLogger(__name__)


# ===================================================================
# VisaCmw500Driver — низкоуровневая обёртка
# ===================================================================

class VisaCmw500Driver:
    """Низкоуровневая обёртка над RsCmwGsmSig с реальными командами из comands.txt."""

    def __init__(
        self,
        ip: str,
        simulate: bool = False,
        id_query: bool = True,
        reset: bool = False,
    ) -> None:
        self._ip = ip
        self._simulate = simulate
        self._id_query = id_query
        self._reset = reset
        self._driver: RsCmwGsmSig | None = None

    def open(self) -> str:
        from RsCmwGsmSig import RsCmwGsmSig

        options = "Simulate=True" if self._simulate else None
        resource = f"TCPIP::{self._ip}::inst0::INSTR"

        self._driver = RsCmwGsmSig(
            resource, id_query=self._id_query, reset=self._reset, options=options
        )

        if not self._simulate:
            self._driver.utilities.visa_timeout = 60000

        self._driver.utilities.write_str("*CLS")
        self._driver.utilities.instrument_status_checking = True
        self._driver.utilities.opc_query_after_write = True

        return self.serial_number

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    @property
    def is_open(self) -> bool:
        return self._driver is not None

    @property
    def _drv(self) -> RsCmwGsmSig:
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver

    # ==================== Основные методы ====================

    def start_signaling(self) -> None:
        self._drv.utilities.write_str_with_opc("CALL:GSM:SIGN1:ACTivate")

    def stop_signaling(self) -> None:
        self._drv.utilities.write_str_with_opc("CALL:GSM:SIGN1:DEactivate")

    @property
    def serial_number(self) -> str:
        return self._drv.utilities.instrument_serial_number

    @property
    def idn_string(self) -> str:
        return self._drv.utilities.idn_string

    # ==================== Sense & Status ====================

    def get_cs_state(self) -> str:
        return self._drv.utilities.query_str_with_opc("CALL:GSM:SIGN1:CONNection:CSWitched:STATe?").strip()

    def get_ps_state(self) -> str:
        return self._drv.utilities.query_str_with_opc("CALL:GSM:SIGN1:CONNection:PSWitched:STATe?").strip()

    def get_ber(self) -> float:
        return float(self._drv.utilities.query_str("SENSe:RReport:CSW:MBEP?").strip())

    def get_rx_level(self) -> float:
        return float(self._drv.utilities.query_str("SENSe:RReport:RXLevel:SUB?").strip())

    def get_rx_quality(self) -> float:
        return self._drv.sense.rreport.rx_quality.sub.get()

    def get_throughput(self) -> float:
        return self._drv.sense.connection.ethroughput.get()

    def get_usv_ip(self) -> str:
        return self._drv.sense.mss_info.ms_address.ipv4.get()

    def get_imei(self) -> str:
        return self._drv.utilities.query_str("CALL:GSM:SIGN1:IMEI?").strip()

    def get_imsi(self) -> str:
        return self._drv.utilities.query_str("CALL:GSM:SIGN1:IMSI?").strip()

    def get_rssi(self) -> str:
        return self._drv.utilities.query_str("CALL:GSM:SIGN1:RSSI?").strip()

    def get_status(self) -> str:
        result = self._drv.utilities.query_str("CALL:GSM:SIGN1:CONNection:STATe?").strip()
        status_map = {"0": "DISConnected", "1": "CONNected", "2": "CAMPed", "3": "REGistered"}
        return status_map.get(result, result)

    # ==================== Configure ====================

    def configure_gsm_signaling(
        self,
        mcc: int = 250,
        mnc: int = 60,
        rf_level_dbm: float = -40.0,
        ps_service: str = "TMA",
        ps_tlevel: str = "EGPRS",
        ps_cscheme_ul: str = "MC9",
        ps_dl_carrier: str = "OFF,OFF,OFF,ON,ON,OFF,OFF,OFF",
        ps_dl_cscheme: str = "MC9,MC9,MC9,MC9,MC9,MC9,MC9,MC9",
    ) -> None:
        """Конфигурация согласно comands.txt"""
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CELL:MCC {mcc}")
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CELL:MNC {mnc}")
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:RFSettings:LEVel:TCH {rf_level_dbm}")
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CONNection:PSWitched:SERVice {ps_service}")
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CONNection:PSWitched:TLEVel {ps_tlevel}")
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CONNection:PSWitched:CSCHeme:UL {ps_cscheme_ul}")
        self._drv.utilities.write_str(
            f"CONFigure:GSM:SIGN:CONNection:PSWitched:SCONfig:ENABle:DL:CARRier {ps_dl_carrier}"
        )
        self._drv.utilities.write_str(
            f"CONFigure:GSM:SIGN:CONNection:PSWitched:SCONfig:CSCHeme:DL:CARRier {ps_dl_cscheme}"
        )

    def configure_sms(self, dcoding: str = "BIT8", pid: int = 1) -> None:
        """Конфигурация SMS согласно comands.txt"""
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:SMS:OUTGoing:DCODing {dcoding}")
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:SMS:OUTGoing:PIDentifier #H{pid}")

    def configure_dau(self) -> None:
        """Конфигурация DAU согласно comands.txt"""
        self._drv.utilities.write_str("CONFigure:DATA:MEAS:RAN 'GSM Sig1'")
        self._drv.utilities.write_str("CONFigure:DATA:CONTrol:DNS:PRIMary:STYPe Foreign")
        self._drv.utilities.write_str("CONFigure:DATA:CONTrol:IPVFour:ADDRess:TYPE DHCPv4")

    # ==================== SMS Send ====================

    def send_sms_raw(self, hex_data: str) -> None:
        """Отправка SMS через CALL:GSM:SIGN:CSWitched:ACTion SMS"""
        # Сначала устанавливаем данные SMS (как в comands.txt)
        self._drv.utilities.write_str(f"CONF:GSM:SIGN1:SMS:OUTG:BIN #H{hex_data}")
        # Запускаем отправку
        self._drv.utilities.write_str_with_opc("CALL:GSM:SIGN:CSWitched:ACTion SMS")


# ===================================================================
# Cmw500Controller
# ===================================================================

class Cmw500Controller:
    """Контроллер CMW-500 с очередью команд, retry и поддержкой эмуляции."""

    def __init__(
        self,
        bus: EventBus,
        ip: str,
        poll_interval: float = 2.0,
        simulate: bool = False,
    ) -> None:
        self.bus = bus
        self._ip = ip
        self._poll_interval = poll_interval
        self._simulate = simulate

        self._driver: VisaCmw500Driver | None = None
        self._queue: asyncio.Queue[tuple[Callable, tuple, asyncio.Future]] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._connected = False

        self._status_cache: dict[str, Any] | None = None
        self._status_cache_ts: float = 0.0
        self._status_cache_ttl: float = 5.0

    # ====================== Lifecycle ======================

    async def connect(self) -> None:
        try:
            self._driver = VisaCmw500Driver(self._ip, simulate=self._simulate)
            serial = await asyncio.get_running_loop().run_in_executor(None, self._driver.open)

            self._worker = asyncio.create_task(self._worker_loop())
            self._worker.add_done_callback(self._on_worker_done)

            self._poll_task = asyncio.create_task(self._poll_loop())
            self._poll_task.add_done_callback(self._on_poll_done)

            self._connected = True
            await self.bus.emit("cmw.connected", {"ip": self._ip, "serial": serial, "simulate": self._simulate})

        except Exception as e:
            await self.bus.emit("cmw.error", {"error": str(e), "command": "connect"})
            raise

    async def disconnect(self) -> None:
        self._connected = False
        for task in (self._worker, self._poll_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._driver is not None:
            await asyncio.get_running_loop().run_in_executor(None, self._driver.close)
            self._driver = None

        self._status_cache = None
        self._status_cache_ts = 0.0
        await self.bus.emit("cmw.disconnected", {})

    def stop_poll(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = None

    def start_poll(self) -> None:
        if not self._connected or (self._poll_task and not self._poll_task.done()):
            return
        self._poll_task = asyncio.create_task(self._poll_loop())
        self._poll_task.add_done_callback(self._on_poll_done)

    # ====================== Worker & Poll ======================

    async def _worker_loop(self) -> None:
        while self._connected:
            try:
                cmd, args, future = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                result = await self._execute(cmd, *args)
                if future and not future.cancelled():
                    future.set_result(result)
            except Exception as e:
                if future and not future.done():
                    future.set_exception(e)
            finally:
                self._queue.task_done()

    async def _execute(self, cmd: Callable, *args: Any) -> Any:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, cmd, *args)

    async def _poll_loop(self) -> None:
        while self._connected:
            try:
                await self._poll_incoming_sms()
            except Exception as e:
                await self.bus.emit("cmw.error", {"error": str(e), "command": "poll_sms"})
            await asyncio.sleep(self._poll_interval)

    # ====================== SMS ======================

    async def send_sms(self, egts_bytes: bytes) -> bool:
        """Отправка EGTS через SMS (использует реальную команду из comands.txt)"""
        if self._driver is None:
            raise ConnectionError("CMW-500 not connected")

        hex_data = egts_bytes.hex().upper()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._driver.send_sms_raw, hex_data)
        return True

    async def read_sms(self) -> bytes | None:
        # Реализация чтения входящих SMS (пока заглушка — зависит от конкретной модели CMW)
        # В реальности обычно используется SENSe или специальный запрос
        return None

    async def _poll_incoming_sms(self) -> None:
        raw = await self.read_sms()
        if raw is not None:
            await self.bus.emit(
                "raw.packet.received", {"raw": raw, "channel": "sms", "connection_id": None}
            )

    # ====================== Public API ======================

    async def get_imei(self) -> str:
        return await self._execute(self._driver.get_imei) if self._driver else ""

    async def get_imsi(self) -> str:
        return await self._execute(self._driver.get_imsi) if self._driver else ""

    async def get_rssi(self) -> str:
        return await self._execute(self._driver.get_rssi) if self._driver else ""

    async def get_full_status(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._status_cache and now - self._status_cache_ts < self._status_cache_ttl:
            return self._status_cache

        if self._simulate:
            result: dict[str, Any] = {
                "connected": True,
                "serial": "EMULATOR",
                "cs_state": "CONNected",
                "ps_state": "DISConnect",
                "rssi": "-65",
                "ber": 0.001,
                "rx_level": -70.0,
                "simulate": True,
                "ip": self._ip,
            }
        else:
            if not self._driver or not self._driver.is_open:
                return {"connected": False, "error": "Driver not open"}

            try:
                result = {
                    "connected": True,
                    "serial": self._driver.serial_number,
                    "cs_state": self._driver.get_cs_state(),
                    "ps_state": self._driver.get_ps_state(),
                    "rssi": self._driver.get_rssi(),
                    "ber": self._driver.get_ber(),
                    "rx_level": self._driver.get_rx_level(),
                    "simulate": False,
                    "ip": self._ip,
                }
            except Exception as e:
                result = {"connected": False, "error": str(e)}

        self._status_cache = result
        self._status_cache_ts = now
        return result

    # ====================== Configure ======================

    async def configure_gsm_signaling(self, **kwargs: Any) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self._driver.configure_gsm_signaling(**kwargs))

    async def configure_sms(self, dcoding: str = "BIT8", pid: int = 1) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._driver.configure_sms, dcoding, pid)

    async def configure_dau(self) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._driver.configure_dau)

    async def start_signaling(self) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._driver.start_signaling)

    async def stop_signaling(self) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._driver.stop_signaling)


# ===================================================================
# Cmw500Emulator (оставляем почти без изменений)
# ===================================================================

class Cmw500Emulator(Cmw500Controller):
    """Эмулятор CMW-500."""

    def __init__(
        self,
        bus: EventBus,
        ip: str,
        poll_interval: float = 2.0,
        tcp_delay_min: float = 0.1,
        tcp_delay_max: float = 2.0,
        sms_delay_min: float = 3.0,
        sms_delay_max: float = 30.0,
    ) -> None:
        super().__init__(bus=bus, ip=ip, poll_interval=poll_interval, simulate=True)
        self._tcp_delay_min = tcp_delay_min
        self._tcp_delay_max = tcp_delay_max
        self._sms_delay_min = sms_delay_min
        self._sms_delay_max = sms_delay_max

        self._incoming_sms_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._incoming_sms_handler: Callable[[bytes], bytes | None] | None = None

        self._mock_imei = "351234567890123"
        self._mock_imsi = "250011234567890"
        self._mock_rssi = "-65"
        self._mock_status = "1"

    async def connect(self) -> None:
        self._worker = asyncio.create_task(self._worker_loop())
        self._worker.add_done_callback(self._on_worker_done)

        self._poll_task = asyncio.create_task(self._poll_loop())
        self._poll_task.add_done_callback(self._on_poll_done)

        self._connected = True
        await self.bus.emit("cmw.connected", {"ip": self._ip, "simulate": True})

    def set_incoming_sms_handler(self, handler: Callable[[bytes], bytes | None]) -> None:
        self._incoming_sms_handler = handler

    async def _send_scpi(self, scpi: str) -> str:
        if "SMS:SEND" in scpi:
            return await self._handle_send_sms(scpi)
        if "SMS:READ" in scpi:
            await self._random_tcp_delay()
            try:
                data = self._incoming_sms_queue.get_nowait()
                return data.hex()
            except asyncio.QueueEmpty:
                return ""

        await self._random_tcp_delay()

        if "IMEI?" in scpi:
            return self._mock_imei
        if "IMSI?" in scpi:
            return self._mock_imsi
        if "RSSI?" in scpi:
            return self._mock_rssi
        if "CONN?" in scpi:
            return self._mock_status

        return "OK"

    async def _handle_send_sms(self, scpi: str) -> str:
        parts = scpi.split(" ", 1)
        if len(parts) < 2:
            await asyncio.sleep(self._random_delay(self._sms_delay_min, self._sms_delay_max))
            return "OK"

        try:
            egts_bytes = bytes.fromhex(parts[1])
        except ValueError:
            await asyncio.sleep(self._random_delay(self._sms_delay_min, self._sms_delay_max))
            return "OK"

        await asyncio.sleep(self._random_delay(self._sms_delay_min, self._sms_delay_max))

        if self._incoming_sms_handler:
            result = self._incoming_sms_handler(egts_bytes)
            if asyncio.iscoroutine(result):
                result = await result
            if result is not None:
                await self._incoming_sms_queue.put(result)

        return "OK"

    def _random_delay(self, min_val: float, max_val: float) -> float:
        return random.uniform(min_val, max_val)

    async def _random_tcp_delay(self) -> None:
        await asyncio.sleep(self._random_delay(self._tcp_delay_min, self._tcp_delay_max))