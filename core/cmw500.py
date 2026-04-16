"""Cmw500Controller — контроллер CMW-500 через RsCmwGsmSig.

Используются реальные SCPI-команды из comands.txt.

Архитектура:
- VisaCmw500Driver — обёртка над RsCmwGsmSig (SCPI + Sense API)
- Cmw500Controller — очередь команд, retry, SMS, poll + stop/start_poll
- Cmw500Emulator — полноценный эмулятор для разработки
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

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
        return self._drv.utilities.query_str_with_opc(
            "CALL:GSM:SIGN1:CONNection:CSWitched:STATe?"
        ).strip()

    def get_ps_state(self) -> str:
        return self._drv.utilities.query_str_with_opc(
            "CALL:GSM:SIGN1:CONNection:PSWitched:STATe?"
        ).strip()

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

    def send_sms_raw(self, hex_data: str) -> bool:
        """Отправка SMS через CONF:GSM:SIGN1:SMS:OUTG:BIN и CALL:GSM:SIGN:CSWitched:ACTion SMS

        Returns:
            True если команда выполнена успешно
        """
        self._drv.utilities.write_str(f"CONF:GSM:SIGN1:SMS:OUTG:BIN #H{hex_data}")
        self._drv.utilities.write_str_with_opc("CALL:GSM:SIGN:CSWitched:ACTion SMS")
        return True

    def read_sms_raw(self) -> str | None:
        """Чтение входящей SMS через SENSe:GSM:SIGN:SMS:INComing:INFO:MTEXt?

        Returns:
            HEX-данные SMS или None если нет SMS
        """
        result = self._drv.utilities.query_str("SENSe:GSM:SIGN:SMS:INComing:INFO:MTEXt?").strip()
        if not result or result == "0":
            return None
        # Убираем префикс #H если есть
        if result.startswith("#H"):
            result = result[2:]
        return result

    def clear_sms_buffer(self) -> None:
        """Очистка буфера входящих SMS.

        Выполняет команду CLEan:GSM:SIGN<i>:SMS:INComing:INFO:MTEXt для сброса
        всех параметров, связанных с последним полученным SMS сообщением.
        """
        self._drv.utilities.write_str("CLEan:GSM:SIGN1:SMS:INComing:INFO:MTEXt")


# ===================================================================
# Cmw500Controller
# ===================================================================

@dataclass
class CmwCommand:
    """Команда CMW-500 с retry-логикой."""

    name: str
    func: Callable[..., Any]
    timeout: float = 10.0
    retry_count: int = 3
    retry_delay: float = 1.0


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
        self._queue: asyncio.Queue[tuple[CmwCommand, tuple[Any, ...], asyncio.Future[Any]]] = asyncio.Queue()
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

    async def _execute_with_retry(self, command: CmwCommand, *args: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(command.retry_count):
            try:
                result = await asyncio.wait_for(
                    self._execute_raw(command.func, *args),
                    timeout=command.timeout,
                )
                return result
            except Exception as e:
                last_error = e
                if attempt < command.retry_count - 1:
                    await asyncio.sleep(command.retry_delay * (2 ** attempt))
        if last_error:
            raise last_error
        raise RuntimeError(f"Command {command.name} failed with 0 retries")

    async def _execute_raw(self, func: Callable[..., Any], *args: Any) -> Any:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

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
        return await self._execute_with_retry(
            CmwCommand(
                name="send_sms",
                func=self._driver.send_sms_raw,
                timeout=30.0,
                retry_count=2,
                retry_delay=1.0,
            ),
            hex_data,
        )

    async def read_sms(self) -> bytes | None:
        """Прочитать входящую SMS от УСВ и очистить буфер.

        Returns:
            bytes | None: Данные SMS в виде байтов или None если SMS не найдено
        """
        if self._driver is None:
            raise ConnectionError("CMW-500 not connected")

        # Читаем SMS
        hex_data = await self._execute_with_retry(
            CmwCommand(
                name="read_sms",
                func=self._driver.read_sms_raw,
                timeout=30,
                retry_count=2,
                retry_delay=0.5,
            ),
        )
        
        # Очищаем буфер после чтения, чтобы предотвратить повторное чтение
        # одного и того же сообщения
        await self._execute_with_retry(
            CmwCommand(
                name="clear_sms_buffer",
                func=self._driver.clear_sms_buffer,
                timeout=5.0,
                retry_count=2,
                retry_delay=0.5,
            ),
        )
        
        if hex_data:
            return hex_data
        return None

    async def _poll_incoming_sms(self) -> None:
        raw = await self.read_sms()
        if raw is not None:
            await self.bus.emit(
                "raw.packet.received", {"raw": raw, "channel": "sms", "connection_id": None}
            )

    # ====================== Public API ======================

    async def get_imei(self) -> str:
        return await self._execute_with_retry(
            CmwCommand(name="get_imei", func=self._driver.get_imei, timeout=5.0, retry_count=3)
        )

    async def get_imsi(self) -> str:
        return await self._execute_with_retry(
            CmwCommand(name="get_imsi", func=self._driver.get_imsi, timeout=5.0, retry_count=3)
        )

    async def get_rssi(self) -> str:
        return await self._execute_with_retry(
            CmwCommand(name="get_rssi", func=self._driver.get_rssi, timeout=5.0, retry_count=2)
        )

    async def get_status(self) -> str:
        return await self._execute_with_retry(
            CmwCommand(name="get_status", func=self._driver.get_status, timeout=5.0, retry_count=3)
        )

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
                # Параллельный сбор данных с таймаутами
                cs_state = await self._execute_with_retry(
                    CmwCommand(name="get_cs_state", func=self._driver.get_cs_state, timeout=3.0, retry_count=1)
                )
                ps_state = await self._execute_with_retry(
                    CmwCommand(name="get_ps_state", func=self._driver.get_ps_state, timeout=3.0, retry_count=1)
                )
                rssi = await self._execute_with_retry(
                    CmwCommand(name="get_rssi", func=self._driver.get_rssi, timeout=3.0, retry_count=1)
                )
                ber = await self._execute_with_retry(
                    CmwCommand(name="get_ber", func=self._driver.get_ber, timeout=3.0, retry_count=1)
                )
                rx_level = await self._execute_with_retry(
                    CmwCommand(name="get_rx_level", func=self._driver.get_rx_level, timeout=3.0, retry_count=1)
                )
                serial = await self._execute_with_retry(
                    CmwCommand(name="serial_number", func=lambda: self._driver.serial_number, timeout=2.0, retry_count=1)
                )

                result = {
                    "connected": True,
                    "serial": serial,
                    "cs_state": cs_state,
                    "ps_state": ps_state,
                    "rssi": rssi,
                    "ber": ber,
                    "rx_level": rx_level,
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
        await self._execute_with_retry(
            CmwCommand(
                name="configure_gsm_signaling",
                func=lambda: self._driver.configure_gsm_signaling(**kwargs),
                timeout=30.0,
                retry_count=2,
                retry_delay=2.0,
            ),
        )

    async def configure_sms(self, dcoding: str = "BIT8", pid: int = 1) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        await self._execute_with_retry(
            CmwCommand(
                name="configure_sms",
                func=lambda: self._driver.configure_sms(dcoding, pid),
                timeout=10.0,
                retry_count=2,
                retry_delay=1.0,
            ),
        )

    async def configure_dau(self) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        await self._execute_with_retry(
            CmwCommand(
                name="configure_dau",
                func=self._driver.configure_dau,
                timeout=10.0,
                retry_count=2,
                retry_delay=1.0,
            ),
        )

    async def start_signaling(self) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        await self._execute_with_retry(
            CmwCommand(
                name="start_signaling",
                func=self._driver.start_signaling,
                timeout=10.0,
                retry_count=2,
                retry_delay=1.0,
            ),
        )

    async def stop_signaling(self) -> None:
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        await self._execute_with_retry(
            CmwCommand(
                name="stop_signaling",
                func=self._driver.stop_signaling,
                timeout=10.0,
                retry_count=2,
                retry_delay=1.0,
            ),
        )


# ===================================================================
# Cmw500Emulator — полноценный эмулятор
# ===================================================================

class MockDriver:
    """Мок-драйвер для эмулятора CMW-500."""

    def __init__(self) -> None:
        self.serial_number = "EMULATOR"
        self.is_open = True
        self._mock_imei = "351234567890123"
        self._mock_imsi = "250011234567890"
        self._mock_rssi = "-65"
        self._mock_status = "CONNected"
        self._mock_cs_state = "CONNected"
        self._mock_ps_state = "DISConnect"
        self._mock_ber = 0.001
        self._mock_rx_level = -70.0

    def close(self) -> None:
        pass

    def start_signaling(self) -> None:
        pass

    def stop_signaling(self) -> None:
        pass

    def get_cs_state(self) -> str:
        return self._mock_cs_state

    def get_ps_state(self) -> str:
        return self._mock_ps_state

    def get_ber(self) -> float:
        return self._mock_ber

    def get_rx_level(self) -> float:
        return self._mock_rx_level

    def get_imei(self) -> str:
        return self._mock_imei

    def get_imsi(self) -> str:
        return self._mock_imsi

    def get_rssi(self) -> str:
        return self._mock_rssi

    def get_status(self) -> str:
        return self._mock_status

    def configure_gsm_signaling(self, **kwargs: Any) -> None:
        pass

    def configure_sms(self, dcoding: str = "BIT8", pid: int = 1) -> None:
        pass

    def configure_dau(self) -> None:
        pass

    def send_sms_raw(self, hex_data: str) -> bool:
        return True

    def read_sms_raw(self) -> str | None:
        return None


class Cmw500Emulator(Cmw500Controller):
    """Эмулятор CMW-500 для разработки без реального прибора.

    Поддерживает:
    - Эмуляцию всех SCPI-команд через мок-драйвер
    - Эмуляцию SMS с задержками и ответами через хендлер
    - Настраиваемые задержки TCP и SMS
    """

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

        # Создаём мок-драйвер
        self._mock_driver = MockDriver()

    async def connect(self) -> None:
        """Подключение эмулятора — создаёт мок-драйвер вместо реального."""
        # Используем мок-драйвер вместо реального
        self._driver = cast(VisaCmw500Driver, self._mock_driver)  # type: ignore

        self._worker = asyncio.create_task(self._worker_loop())
        self._worker.add_done_callback(self._on_worker_done)

        self._poll_task = asyncio.create_task(self._poll_loop())
        self._poll_task.add_done_callback(self._on_poll_done)

        self._connected = True
        await self.bus.emit("cmw.connected", {"ip": self._ip, "simulate": True, "serial": "EMULATOR"})

    async def disconnect(self) -> None:
        """Отключение эмулятора."""
        self._connected = False
        for task in (self._worker, self._poll_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._driver = None
        self._status_cache = None
        self._status_cache_ts = 0.0
        await self.bus.emit("cmw.disconnected", {})

    def set_incoming_sms_handler(self, handler: Callable[[bytes], bytes | None]) -> None:
        """Установить хендлер для входящих SMS.

        Args:
            handler: Функция, принимающая отправленные EGTS-байты
                     и возвращающая ответный пакет или None.
        """
        self._incoming_sms_handler = handler

    # ==================== Переопределение методов с эмуляцией задержек ====================

    async def _execute_raw(self, func: Callable[..., Any], *args: Any) -> Any:
        """Переопределяем для эмуляции задержек."""
        # Эмуляция задержки для всех команд
        delay = random.uniform(self._tcp_delay_min, self._tcp_delay_max)
        await asyncio.sleep(delay)

        # Особый случай для send_sms_raw — эмуляция SMS задержки
        if func.__name__ == "send_sms_raw" and args:
            return await self._handle_send_sms_emulation(args[0])

        # Особый случай для read_sms_raw
        if func.__name__ == "read_sms_raw":
            try:
                data = self._incoming_sms_queue.get_nowait()
                return data.hex().upper()
            except asyncio.QueueEmpty:
                return None

        # Обычный вызов
        return func(*args)

    async def _handle_send_sms_emulation(self, hex_data: str) -> bool:
        """Эмуляция отправки SMS с задержкой и вызовом хендлера."""
        # Эмуляция задержки отправки SMS
        delay = random.uniform(self._sms_delay_min, self._sms_delay_max)
        await asyncio.sleep(delay)

        # Конвертируем HEX в байты
        try:
            egts_bytes = bytes.fromhex(hex_data)
        except ValueError:
            return True

        # Вызываем хендлер для генерации ответа
        if self._incoming_sms_handler:
            result = self._incoming_sms_handler(egts_bytes)
            if asyncio.iscoroutine(result):
                result = await result
            if result is not None:
                await self._incoming_sms_queue.put(result)

        return True

    async def send_sms(self, egts_bytes: bytes) -> bool:
        """Отправка SMS через эмулятор."""
        if not self._connected:
            raise ConnectionError("CMW-500 not connected")

        hex_data = egts_bytes.hex().upper()
        return await self._handle_send_sms_emulation(hex_data)

    async def read_sms(self) -> bytes | None:
        """Чтение SMS через эмулятор."""
        if not self._connected:
            raise ConnectionError("CMW-500 not connected")

        try:
            data = self._incoming_sms_queue.get_nowait()
            return data
        except asyncio.QueueEmpty:
            return None

    async def get_full_status(self) -> dict[str, Any]:
        """Статус эмулятора — моковые данные."""
        now = time.monotonic()
        if self._status_cache and now - self._status_cache_ts < self._status_cache_ttl:
            return self._status_cache

        result = {
            "connected": True,
            "serial": "EMULATOR",
            "cs_state": self._mock_driver.get_cs_state(),
            "ps_state": self._mock_driver.get_ps_state(),
            "rssi": self._mock_driver.get_rssi(),
            "ber": self._mock_driver.get_ber(),
            "rx_level": self._mock_driver.get_rx_level(),
            "simulate": True,
            "ip": self._ip,
        }

        self._status_cache = result
        self._status_cache_ts = now
        return result