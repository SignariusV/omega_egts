"""Cmw500Controller — контроллер CMW-500 через RsCmwGsmSig.

Архитектура:
- VisaCmw500Driver — обёртка над RsCmwGsmSig (SCPI + Sense API)
- Cmw500Controller — очередь команд, retry, SMS, poll + stop/start_poll
- Cmw500Emulator — полноценный эмулятор
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
# VisaCmw500Driver
# ===================================================================

class VisaCmw500Driver:
    """Низкоуровневая обёртка над RsCmwGsmSig."""

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
        """Безопасный доступ к драйверу."""
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

    def query(self, scpi: str) -> str:
        return self._drv.utilities.query_str(scpi)

    def write(self, scpi: str) -> None:
        self._drv.utilities.write_str(scpi)

    # ==================== Sense & Legacy ====================

    def get_cs_state(self) -> str:
        return self._drv.utilities.query_str_with_opc("CALL:GSM:SIGN1:CONNection:CSWitched:STATe?").strip()

    def get_ps_state(self) -> str:
        return self._drv.utilities.query_str_with_opc("CALL:GSM:SIGN1:CONNection:PSWitched:STATe?").strip()

    def get_call_cs_state(self) -> str:
        return self._drv.call.cswitched.state.get()

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
        self.configure_cell_mcc(mcc)
        self.configure_cell_mnc(mnc)
        self.configure_rf_level_tch(rf_level_dbm)
        self.configure_ps_service(ps_service)
        self.configure_ps_tlevel(ps_tlevel)
        self.configure_ps_cscheme_ul(ps_cscheme_ul)
        self.configure_ps_dl_carrier(ps_dl_carrier)
        self.configure_ps_dl_cscheme(ps_dl_cscheme)

    def configure_cell_mcc(self, mcc: int) -> None:
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CELL:MCC {mcc}")

    def configure_cell_mnc(self, mnc: int) -> None:
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CELL:MNC {mnc}")

    def configure_rf_level_tch(self, level_dbm: float) -> None:
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:RFSettings:LEVel:TCH {level_dbm}")

    def configure_ps_service(self, service: str) -> None:
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CONNection:PSWitched:SERVice {service}")

    def configure_ps_tlevel(self, tlevel: str) -> None:
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CONNection:PSWitched:TLEVel {tlevel}")

    def configure_ps_cscheme_ul(self, scheme: str) -> None:
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:CONNection:PSWitched:CSCHeme:UL {scheme}")

    def configure_ps_dl_carrier(self, carriers: str) -> None:
        self._drv.utilities.write_str(
            f"CONFigure:GSM:SIGN:CONNection:PSWitched:SCONfig:ENABle:DL:CARRier {carriers}"
        )

    def configure_ps_dl_cscheme(self, scheme: str) -> None:
        self._drv.utilities.write_str(
            f"CONFigure:GSM:SIGN:CONNection:PSWitched:SCONfig:CSCHeme:DL:CARRier {scheme}"
        )

    def configure_sms_dcoding(self, dcoding: str) -> None:
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:SMS:OUTGoing:DCODing {dcoding}")

    def configure_sms_pidentifier(self, pid: int) -> None:
        self._drv.utilities.write_str(f"CONFigure:GSM:SIGN:SMS:OUTGoing:PIDentifier #H{pid}")

    def configure_sms(self, dcoding: str = "BIT8", pid: int = 1) -> None:
        self.configure_sms_dcoding(dcoding)
        self.configure_sms_pidentifier(pid)

    def configure_dau(
        self,
        meas_range: str = "GSM Sig1",
        dns_type: str = "Foreign",
        ipv4_type: str = "DHCPv4",
    ) -> None:
        self._drv.utilities.write_str(f"CONFigure:DATA:MEAS:RAN '{meas_range}'")
        self._drv.utilities.write_str(f"CONFigure:DATA:CONTrol:DNS:PRIMary:STYPe {dns_type}")
        self._drv.utilities.write_str(f"CONFigure:DATA:CONTrol:IPVFour:ADDRess:TYPE {ipv4_type}")


# ===================================================================
# Cmw500Controller
# ===================================================================

@dataclass
class CmwCommand:
    name: str
    scpi_template: str
    timeout: float = 5.0
    retry_count: int = 3
    retry_delay: float = 1.0

    def format(self, *args: object, **kwargs: object) -> str:
        return self.scpi_template.format(*args, **kwargs)


GET_IMEI = CmwCommand("get_imei", "CMW:GSM:SIGN:IMEI?", timeout=2.0, retry_count=3)
GET_IMSI = CmwCommand("get_imsi", "CMW:GSM:SIGN:IMSI?", timeout=2.0, retry_count=3)
GET_RSSI = CmwCommand("get_rssi", "CMW:GSM:SIGN:RSSI?", timeout=2.0, retry_count=2)
GET_STATUS = CmwCommand("get_status", "CMW:GSM:SIGN:CONN?", timeout=2.0, retry_count=3)
SEND_SMS = CmwCommand("send_sms", "CMW:GSM:SIGN:SMS:SEND {}", timeout=10.0, retry_count=2)
READ_SMS = CmwCommand("read_sms", "CMW:GSM:SIGN:SMS:READ?", timeout=5.0, retry_count=3)


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
        self._queue: asyncio.Queue[tuple[CmwCommand, tuple[object, ...], asyncio.Future[str]]] = asyncio.Queue()
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
        """Временно остановить опрос (используется перед конфигурацией)."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = None

    def start_poll(self) -> None:
        """Запустить опрос после конфигурации."""
        if not self._connected:
            return
        if self._poll_task is not None and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._poll_loop())
        self._poll_task.add_done_callback(self._on_poll_done)

    # ====================== Callbacks ======================

    def _on_worker_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            self._connected = False
            try:
                asyncio.get_running_loop().create_task(
                    self.bus.emit("cmw.error", {"error": str(exc), "command": "worker_loop"})
                )
            except RuntimeError:
                pass

    def _on_poll_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            try:
                asyncio.get_running_loop().create_task(
                    self.bus.emit("cmw.error", {"error": str(exc), "command": "poll_loop"})
                )
            except RuntimeError:
                pass

    # ====================== Worker & Poll ======================

    async def _worker_loop(self) -> None:
        while self._connected:
            try:
                command, args, future = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                result = await self._execute_with_retry(command, *args)
                if future and not future.cancelled():
                    future.set_result(result)
            except Exception as e:
                if future and not future.done():
                    future.set_exception(e)
            finally:
                self._queue.task_done()

    async def _execute_with_retry(self, command: CmwCommand, *args: object) -> str:
        last_error: Exception | None = None
        for attempt in range(command.retry_count):
            try:
                scpi = command.format(*args)
                result = await asyncio.wait_for(self._send_scpi(scpi), timeout=command.timeout)
                return result
            except Exception as e:
                last_error = e
                await asyncio.sleep(command.retry_delay * (2 ** attempt))
        if last_error:
            raise last_error
        raise RuntimeError(f"Command {command.name} failed with 0 retries")

    async def _send_scpi(self, scpi: str) -> str:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.query, scpi)

    async def _poll_loop(self) -> None:
        while self._connected:
            try:
                await self._poll_incoming_sms()
            except Exception as e:
                await self.bus.emit("cmw.error", {"error": str(e), "command": "poll_sms"})
            await asyncio.sleep(self._poll_interval)

    # ====================== SMS ======================

    async def send_sms(self, egts_bytes: bytes) -> bool:
        result = await self.execute(SEND_SMS, egts_bytes.hex())
        return "OK" in result

    async def read_sms(self) -> bytes | None:
        result = await self.execute(READ_SMS)
        return bytes.fromhex(result) if result else None

    async def _poll_incoming_sms(self) -> None:
        raw = await self.read_sms()
        if raw is not None:
            await self.bus.emit(
                "raw.packet.received", {"raw": raw, "channel": "sms", "connection_id": None}
            )

    # ====================== Public API ======================

    async def execute(self, command: CmwCommand, *args: object) -> str:
        if not self._connected:
            raise ConnectionError("CMW-500 not connected")
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        await self._queue.put((command, args, future))
        return await future

    async def get_imei(self) -> str:
        return await self.execute(GET_IMEI)

    async def get_imsi(self) -> str:
        return await self.execute(GET_IMSI)

    async def get_rssi(self) -> str:
        return await self.execute(GET_RSSI)

    async def get_status(self) -> str:
        return await self.execute(GET_STATUS)

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
            result = {"connected": self._driver is not None and self._driver.is_open}
            if self._driver:
                try:
                    result["serial"] = self._driver.serial_number
                    result["cs_state"] = "N/A (Sense не поддерживается)"
                    result["ps_state"] = "N/A (Sense не поддерживается)"
                    result["rssi"] = "N/A"
                    result["ber"] = "N/A"
                    result["rx_level"] = "N/A"
                except Exception as e:
                    result["connected"] = False
                    result["error"] = str(e)

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
        await loop.run_in_executor(None, self._driver.configure_sms_dcoding, dcoding)
        await loop.run_in_executor(None, self._driver.configure_sms_pidentifier, pid)

    async def configure_dau(self, **kwargs: Any) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self._driver.configure_dau(**kwargs))

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
# Cmw500Emulator
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