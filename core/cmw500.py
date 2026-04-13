"""Cmw500Controller — контроллер CMW-500 через RsCmwGsmSig.

Архитектура:
- VisaCmw500Driver — обёртка над RsCmwGsmSig (SCPI query/write + Sense API)
- Cmw500Controller — логика: очередь команд, retry, SMS, poll
- Cmw500Emulator — эмулятор для разработки без реального прибора
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.event_bus import EventBus

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
# VisaCmw500Driver — обёртка над RsCmwGsmSig
# ════════════════════════════════════════════════════════════


class VisaCmw500Driver:
    """Драйвер CMW-500 на базе RsCmwGsmSig.

    Обеспечивает низкоуровневый SCPI (query/write) и доступ
    к высокоуровневому Sense API. Режим симуляции (simulate=True)
    позволяет разрабатывать без реального прибора.

    Все публичные методы синхронные — вызываются из executor.
    """

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
        self._driver: object | None = None

    def open(self) -> str:
        """Открыть сессию с прибором.

        Returns:
            Серийный номер прибора.
        """
        from RsCmwGsmSig import RsCmwGsmSig

        options = "Simulate=True" if self._simulate else None
        resource = f"TCPIP::{self._ip}::HISLIP"
        self._driver = RsCmwGsmSig(
            resource,
            id_query=self._id_query,
            reset=self._reset,
            options=options,
        )
        self._driver.utilities.instrument_status_checking = True
        self._driver.utilities.opc_query_after_write = False
        return self.serial_number

    def close(self) -> None:
        """Закрыть сессию."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    @property
    def is_open(self) -> bool:
        return self._driver is not None

    @property
    def serial_number(self) -> str:
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.utilities.instrument_serial_number

    @property
    def idn_string(self) -> str:
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.utilities.idn_string

    # ──────────────────── Низкоуровневый SCPI ──────────

    def query(self, scpi: str) -> str:
        """SCPI-запрос с ожиданием ответа (команды с ``?``)."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.utilities.query_str(scpi)

    def write(self, scpi: str) -> None:
        """SCPI-команда без ожидания ответа."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.utilities.write_str(scpi)

    # ──────────────────── Sense API (состояния) ────────

    def get_cs_state(self) -> str:
        """Состояние CS-канала: DISConnect, PREPare, CONNected, ACTive, REL ease."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.connection.cswitched.connection.get()

    def get_ps_state(self) -> str:
        """Состояние PS-канала: DISConnect, PREPare, CONNected, ACTive."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.call.pswitched.state.get()

    def get_call_cs_state(self) -> str:
        """Состояние CS-вызова: DISConnect, PREParation, CONNected, ACTive, HOLD."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.call.cswitched.state.get()

    # ──────────────────── Sense API (радиопараметры) ───

    def get_ber(self) -> float:
        """BER — коэффициент битовых ошибок."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.rreport.cswitched.mbep.get()

    def get_rx_level(self) -> float:
        """Уровень приёма (dBm)."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.rreport.rx_level.sub.get()

    def get_rx_quality(self) -> float:
        """Качество приёма."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.rreport.rx_quality.sub.get()

    def get_throughput(self) -> float:
        """Пропускная способность (кбит/с)."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.connection.ethroughput.get()

    # ──────────────────── Sense API (информация об УСВ) ──

    def get_usv_ip(self) -> str:
        """IPv4-адрес УСВ."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.mss_info.ms_address.ipv4.get()

    def get_usv_class(self) -> str:
        """Класс терминала."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.mss_info.ms_class.get()

    # ──────────────────── Sense API (SMS-статусы) ──────

    def get_sms_out_status(self) -> str:
        """Статус последней исходящей SMS."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.sms.outgoing.info.get()

    def get_sms_in_status(self) -> str:
        """Статус входящих SMS."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        return self._driver.sense.sms.incoming.info.get()

    # ──────────────────── Legacy SCPI (обратная совместимость) ──

    def get_imei(self) -> str:
        return self.query("CMW:GSM:SIGN:IMEI?")

    def get_imsi(self) -> str:
        return self.query("CMW:GSM:SIGN:IMSI?")

    def get_rssi(self) -> str:
        return self.query("CMW:GSM:SIGN:RSSI?")

    def get_status(self) -> str:
        return self.query("CMW:GSM:SIGN:CONN?")

    # ──────────────────── Configure API ────────────────────

    def configure_cell_mcc(self, mcc: int) -> None:
        """MCC — код страны (250 = Россия)."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.cell.mnc.set(mcc)

    def configure_cell_mnc(self, mnc: int) -> None:
        """MNC — код оператора (60 = Волна, 01 = МТС)."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.cell.mnc.set(mnc)

    def configure_rf_level_tch(self, level_dbm: float) -> None:
        """Мощность TCH (dBm), обычно -40."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.rf_settings.level.tch.set(level_dbm)

    def configure_ps_service(self, service: str) -> None:
        """Тип PS-сервиса, обычно 'TMA'."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.connection.pswitched.service.set(service)

    def configure_ps_tlevel(self, tlevel: str) -> None:
        """Тип PS-канала, обычно 'EGPRS'."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.connection.pswitched.tlevel.set(tlevel)

    def configure_ps_cscheme_ul(self, scheme: str) -> None:
        """Схема кодирования UL, обычно 'MC9'."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.connection.pswitched.cscheme.ul.set(scheme)

    def configure_ps_dl_carrier(self, carriers: str) -> None:
        """Несущие DL — строка 'OFF,OFF,OFF,ON,ON,OFF,OFF,OFF'."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.connection.pswitched.sconfig.enable.dl.carrier.set(
            carriers
        )

    def configure_ps_dl_cscheme(self, scheme: str) -> None:
        """Кодирование DL — строка 'MC9,MC9,MC9,MC9,MC9,MC9,MC9,MC9'."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.connection.pswitched.sconfig.cscheme.dl.carrier.set(
            scheme
        )

    def configure_sms_dcoding(self, dcoding: str) -> None:
        """Кодирование SMS — обычно 'BIT8'."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.sms.outgoing.dcoding.set(dcoding)

    def configure_sms_pidentifier(self, pid: int) -> None:
        """PID SMS — обычно 1."""
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        self._driver.configure.sms.outgoing.pidentifier.set(pid)

    # ──────────────────── Полная конфигурация ─────────────

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
        """Полная настройка GSM Signaling.

        Вызывается один раз при инициализации CMW-500.
        """
        self.configure_cell_mcc(mcc)
        self.configure_cell_mnc(mnc)
        self.configure_rf_level_tch(rf_level_dbm)
        self.configure_ps_service(ps_service)
        self.configure_ps_tlevel(ps_tlevel)
        self.configure_ps_cscheme_ul(ps_cscheme_ul)
        self.configure_ps_dl_carrier(ps_dl_carrier)
        self.configure_ps_dl_cscheme(ps_dl_cscheme)

    def configure_sms(
        self,
        dcoding: str = "BIT8",
        pid: int = 1,
    ) -> None:
        """Настройка SMS-канала."""
        self.configure_sms_dcoding(dcoding)
        self.configure_sms_pidentifier(pid)

    def configure_dau(
        self,
        meas_range: str = "GSM Sig1",
        dns_type: str = "Foreign",
        ipv4_type: str = "DHCPv4",
    ) -> None:
        """Настройка DAU (Data Access Unit).

        Args:
            meas_range: Диапазон измерений (например, 'GSM Sig1').
            dns_type: Тип DNS (Foreign).
            ipv4_type: Тип IPv4-адреса (DHCPv4).
        """
        if self._driver is None:
            raise RuntimeError("Driver not opened")
        # CONF:DATA:MEAS:RAN 'GSM Sig1'
        self._driver.configure.data.meas.range.set(meas_range)
        # CONF:DATA:CONT:DNS:PRIM:STYP Foreign
        self._driver.configure.data.control.dns.primary.stype.set(dns_type)
        # CONF:DATA:CONT:IPV4:ADDR:TYPE DHCPv4
        self._driver.configure.data.control.ipv4.address.type.set(ipv4_type)


@dataclass
class CmwCommand:
    """Команда CMW-500 как first-class объект."""

    name: str
    scpi_template: str
    timeout: float = 5.0
    retry_count: int = 3
    retry_delay: float = 1.0

    def format(self, *args: object, **kwargs: object) -> str:
        """Отформатировать SCPI-строку с аргументами."""
        return self.scpi_template.format(*args, **kwargs)


# ──────────────────── Предопределённые команды ────────────────────

GET_IMEI = CmwCommand("get_imei", "CMW:GSM:SIGN:IMEI?", timeout=2.0, retry_count=3)
GET_IMSI = CmwCommand("get_imsi", "CMW:GSM:SIGN:IMSI?", timeout=2.0, retry_count=3)
GET_RSSI = CmwCommand("get_rssi", "CMW:GSM:SIGN:RSSI?", timeout=2.0, retry_count=2)
GET_STATUS = CmwCommand("get_status", "CMW:GSM:SIGN:CONN?", timeout=2.0, retry_count=3)
SEND_SMS = CmwCommand("send_sms", "CMW:GSM:SIGN:SMS:SEND {}", timeout=10.0, retry_count=2)
READ_SMS = CmwCommand("read_sms", "CMW:GSM:SIGN:SMS:READ?", timeout=5.0, retry_count=3)


class Cmw500Controller:
    """Контроллер CMW-500 с очередью команд.

    Все команды проходят через asyncio.Queue, что гарантирует
    последовательное выполнение без конфликтов VISA-сессии.

    SMS:
    - send_sms(egts_bytes) — CMW-500 сам кодирует PDU и шлёт УСВ
    - read_sms() — CMW-500 декодирует PDU, возвращает сырые EGTS-байты
    - _poll_incoming_sms() — фоновый опрос READ_SMS, emit raw.packet.received
    """

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
        self._queue: asyncio.Queue[tuple[CmwCommand, tuple[object, ...], asyncio.Future[str]]] = (
            asyncio.Queue()
        )
        self._worker: asyncio.Task[None] | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._connected = False

    # ──────────────────── Подключение ────────────────────

    async def connect(self) -> None:
        """Подключиться к CMW-500 и запустить worker-цикл + опрос SMS."""
        try:
            self._driver = VisaCmw500Driver(self._ip, simulate=self._simulate)
            serial = await asyncio.get_running_loop().run_in_executor(
                None, self._driver.open
            )
            self._worker = asyncio.create_task(self._worker_loop())
            self._worker.add_done_callback(self._on_worker_done)
            self._poll_task = asyncio.create_task(self._poll_loop())
            self._poll_task.add_done_callback(self._on_poll_done)
            self._connected = True
            await self.bus.emit("cmw.connected", {
                "ip": self._ip,
                "serial": serial,
                "simulate": self._simulate,
            })
        except Exception as e:
            await self.bus.emit("cmw.error", {"error": str(e), "command": "connect"})
            raise

    def _on_worker_done(self, task: asyncio.Task[None]) -> None:
        """Callback при завершении worker task."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            self._connected = False
            # Fire and forget — event loop может быть уже остановлен
            try:
                asyncio.get_running_loop().create_task(
                    self.bus.emit("cmw.error", {
                        "error": str(exc),
                        "command": "worker_loop",
                    })
                )
            except RuntimeError:
                # Event loop закрыт — пропускаем
                pass

    def _on_poll_done(self, task: asyncio.Task[None]) -> None:
        """Callback при завершении poll task."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            # Fire and forget — event loop может быть уже остановлен
            try:
                asyncio.get_running_loop().create_task(
                    self.bus.emit("cmw.error", {
                        "error": str(exc),
                        "command": "poll_loop",
                    })
                )
            except RuntimeError:
                # Event loop закрыт — пропускаем
                pass

    async def disconnect(self) -> None:
        """Отключиться от CMW-500."""
        self._connected = False
        if self._worker and not self._worker.done():
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._driver is not None:
            await asyncio.get_running_loop().run_in_executor(
                None, self._driver.close
            )
            self._driver = None
        # Сброс кэша состояний
        self._last_cs_state = None
        self._last_ps_state = None
        self._last_rssi = None
        self._last_ber = None
        self._last_rx_level = None
        self._status_cache = None
        self._status_cache_ts = 0.0
        await self.bus.emit("cmw.disconnected", {})

    # ──────────────────── Выполнение команд ──────────────

    async def execute(self, command: CmwCommand, *args: object) -> str:
        """Поставить команду в очередь и дождаться результата.

        Raises:
            ConnectionError: Если CMW-500 не подключён.
        """
        if not self._connected:
            raise ConnectionError("CMW-500 not connected")
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        await self._queue.put((command, args, future))
        return await future

    # ──────────────────── SMS ─────────────────────────────

    async def send_sms(self, egts_bytes: bytes) -> bool:
        """Отправить сырые EGTS-байты через SMS.

        CMW-500 сам кодирует SMS PDU и отправляет подключённому УСВ.

        Args:
            egts_bytes: Сырые байты EGTS-пакета (без PDU-обёртки).

        Returns:
            True если CMW-500 вернул "OK", иначе False.
        """
        result = await self.execute(SEND_SMS, egts_bytes.hex())
        return "OK" in result

    async def read_sms(self) -> bytes | None:
        """Прочитать принятую SMS от УСВ.

        CMW-500 сам декодирует SMS PDU и возвращает содержимое.

        Returns:
            Сырые EGTS-байты из SMS или None если SMS нет.
        """
        result = await self.execute(READ_SMS)
        if not result:
            return None
        return bytes.fromhex(result)

    async def _poll_incoming_sms(self) -> None:
        """Один цикл опроса входящих SMS.

        Вызывает READ_SMS? и при наличии ответа эмитит
        ``raw.packet.received`` с ``channel="sms"`` и ``connection_id=None``.
        """
        raw = await self.read_sms()
        if raw is not None:
            await self.bus.emit("raw.packet.received", {
                "raw": raw,
                "channel": "sms",
                "connection_id": None,
            })

    # ──────────────────── Периодический мониторинг состояний ──

    # Кэш предыдущих значений — эмитим событие только при изменении
    _last_cs_state: str | None = None
    _last_ps_state: str | None = None
    _last_rssi: str | None = None
    _last_ber: float | None = None
    _last_rx_level: float | None = None

    # Кэш статусов с TTL (KI-046)
    _status_cache: dict[str, Any] | None = None
    _status_cache_ts: float = 0.0
    _status_cache_ttl: float = 5.0  # секунд

    async def _poll_states(self) -> None:
        """Опрос состояний CMW-500 и эмит EventBus-событий.

        Проверяет:
        - CS state → ``cmw.cs_state_changed``
        - PS state → ``cmw.ps_state_changed``
        - RSSI → ``cmw.rssi_updated``
        - BER → ``cmw.ber_updated``
        - RX level → ``cmw.rx_level_updated``

        Событие эмитится только при изменении значения.
        """
        driver = self._driver  # локальная ссылка — защита от disconnect
        if driver is None:
            return

        loop = asyncio.get_running_loop()

        # CS state
        try:
            cs_state = await loop.run_in_executor(
                None, driver.get_cs_state
            )
            if cs_state != self._last_cs_state:
                self._last_cs_state = cs_state
                await self.bus.emit("cmw.cs_state_changed", {
                    "state": cs_state,
                })
        except Exception as e:
            logger.debug("CMW poll CS state error: %s", e)

        # PS state
        try:
            ps_state = await loop.run_in_executor(
                None, driver.get_ps_state
            )
            if ps_state != self._last_ps_state:
                self._last_ps_state = ps_state
                await self.bus.emit("cmw.ps_state_changed", {
                    "state": ps_state,
                })
        except Exception as e:
            logger.debug("CMW poll PS state error: %s", e)

        # RSSI
        try:
            rssi = await loop.run_in_executor(
                None, driver.get_rssi
            )
            if rssi != self._last_rssi:
                self._last_rssi = rssi
                await self.bus.emit("cmw.rssi_updated", {
                    "rssi": rssi,
                })
        except Exception as e:
            logger.debug("CMW poll RSSI error: %s", e)

        # BER
        try:
            ber = await loop.run_in_executor(
                None, driver.get_ber
            )
            if self._last_ber is None or abs(ber - self._last_ber) > 0.01:
                self._last_ber = ber
                await self.bus.emit("cmw.ber_updated", {
                    "ber": ber,
                })
        except Exception as e:
            logger.debug("CMW poll BER error: %s", e)

        # RX level
        try:
            rx_level = await loop.run_in_executor(
                None, driver.get_rx_level
            )
            if (
                self._last_rx_level is None
                or abs(rx_level - self._last_rx_level) > 0.5
            ):
                self._last_rx_level = rx_level
                await self.bus.emit("cmw.rx_level_updated", {
                    "rx_level": rx_level,
                })
        except Exception as e:
            logger.debug("CMW poll RX level error: %s", e)

    async def _poll_loop(self) -> None:
        """Фоновый цикл опроса.

        Периодически вызывает:
        - _poll_incoming_sms() — входящие SMS
        - _poll_states() — состояния (CS, PS, RSSI, BER)

        Ошибки не прерывают цикл — они логируются через cmw.error.
        """
        while self._connected:
            try:
                await self._poll_incoming_sms()
            except Exception as e:
                await self.bus.emit("cmw.error", {
                    "error": str(e),
                    "command": "poll_sms",
                })
            try:
                await self._poll_states()
            except Exception as e:
                await self.bus.emit("cmw.error", {
                    "error": str(e),
                    "command": "poll_states",
                })
            await asyncio.sleep(self._poll_interval)

    # ──────────────────── Удобные методы ──────────────────

    async def get_imei(self) -> str:
        """Получить IMEI подключённого УСВ."""
        return await self.execute(GET_IMEI)

    async def get_imsi(self) -> str:
        """Получить IMSI подключённого УСВ."""
        return await self.execute(GET_IMSI)

    async def get_rssi(self) -> str:
        """Получить уровень сигнала (RSSI) подключённого УСВ."""
        return await self.execute(GET_RSSI)

    async def get_status(self) -> str:
        """Получить статус подключения УСВ."""
        return await self.execute(GET_STATUS)

    # ──────────────────── Worker loop ─────────────────────

    async def _worker_loop(self) -> None:
        """Бесконечный цикл обработки команд из очереди."""
        while self._connected:
            future: asyncio.Future[str] | None = None
            try:
                command, args, future = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                # Worker task отменён — корректно завершаем цикл
                break

            try:
                result = await self._execute_with_retry(command, *args)
                if future is not None and not future.cancelled():
                    future.set_result(result)
            except asyncio.CancelledError:
                # future может быть отменён — ничего не делаем
                pass
            except Exception as e:
                # future может быть уже отменён или установлен —
                # проверяем перед установкой исключения
                if future is not None and not future.done():
                    future.set_exception(e)
            finally:
                self._queue.task_done()

    async def _execute_with_retry(
        self, command: CmwCommand, *args: object
    ) -> str:
        """Выполнить SCPI-команду с экспоненциальным retry."""
        last_error: Exception | None = None
        for attempt in range(command.retry_count):
            try:
                scpi = command.format(*args)
                result = await asyncio.wait_for(
                    self._send_scpi(scpi), timeout=command.timeout
                )
                return result
            except Exception as e:
                last_error = e
                # Экспоненциальная задержка: retry_delay * 2^attempt
                await asyncio.sleep(command.retry_delay * (2 ** attempt))
        if last_error is not None:
            raise last_error
        raise RuntimeError(
            f"Command {command.name} failed with 0 retries"
        )

    async def _send_scpi(self, scpi: str) -> str:
        """Отправить SCPI-команду и получить ответ.

        Делегирует VisaCmw500Driver.query() через run_in_executor.

        Args:
            scpi: SCPI-строка команды.

        Returns:
            Ответ прибора (без завершающего newline).

        Raises:
            ConnectionError: Если драйвер не подключён.
        """
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.query, scpi)

    # ──────────────────── Sense API (async-обёртки) ──────

    async def get_cs_state(self) -> str:
        """Состояние CS-канала."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_cs_state)

    async def get_ps_state(self) -> str:
        """Состояние PS-канала."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_ps_state)

    async def get_call_cs_state(self) -> str:
        """Состояние CS-вызова."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_call_cs_state)

    async def get_ber(self) -> float:
        """BER — битовая ошибка."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_ber)

    async def get_rx_level(self) -> float:
        """Уровень приёма (dBm)."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_rx_level)

    async def get_rx_quality(self) -> float:
        """Качество приёма."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_rx_quality)

    async def get_throughput(self) -> float:
        """Пропускная способность (кбит/с)."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_throughput)

    async def get_usv_ip(self) -> str:
        """IPv4-адрес УСВ."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_usv_ip)

    async def get_sms_out_status(self) -> str:
        """Статус исходящих SMS."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_sms_out_status)

    async def get_sms_in_status(self) -> str:
        """Статус входящих SMS."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._driver.get_sms_in_status)

    # ──────────────────── Расширенный статус (TTL-кэш) ──────

    async def get_full_status(self) -> dict[str, Any]:
        """Полный статус CMW-500 с TTL-кэшем (KI-046).

        Вместо 3+ SCPI-запросов на каждый вызов, кэширует
        результат на ``_status_cache_ttl`` секунд.

        Returns:
            Словарь: connected, serial, cs_state, ps_state,
            rssi, ber, rx_level, simulate, ip.
        """
        import time

        now = time.monotonic()
        if (
            self._status_cache is not None
            and now - self._status_cache_ts < self._status_cache_ttl
        ):
            return self._status_cache

        if self._driver is None:
            result = {
                "connected": False,
                "error": "driver not open",
            }
            return result

        loop = asyncio.get_running_loop()

        def _gather() -> dict[str, Any]:
            """Синхронно собрать все данные."""
            data: dict[str, Any] = {"connected": True}
            try:
                data["serial"] = self._driver.serial_number
            except Exception:
                pass
            try:
                data["cs_state"] = self._driver.get_cs_state()
            except Exception:
                data["cs_state"] = "N/A"
            try:
                data["ps_state"] = self._driver.get_ps_state()
            except Exception:
                data["ps_state"] = "N/A"
            try:
                data["rssi"] = self._driver.get_rssi()
            except Exception:
                data["rssi"] = "N/A"
            try:
                data["ber"] = self._driver.get_ber()
            except Exception:
                data["ber"] = "N/A"
            try:
                data["rx_level"] = self._driver.get_rx_level()
            except Exception:
                data["rx_level"] = "N/A"
            return data

        result = await loop.run_in_executor(None, _gather)
        result["simulate"] = self._simulate
        result["ip"] = self._ip

        # Обновляем кэш
        self._status_cache = result
        self._status_cache_ts = now

        return result

    def invalidate_status_cache(self) -> None:
        """Сбросить кэш статусов."""
        self._status_cache = None
        self._status_cache_ts = 0.0

    # ──────────────────── Configure API (async-обёртки) ─────

    async def configure_gsm_signaling(
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
        """Полная настройка GSM Signaling."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()

        def _do_config() -> None:
            self._driver.configure_gsm_signaling(
                mcc=mcc,
                mnc=mnc,
                rf_level_dbm=rf_level_dbm,
                ps_service=ps_service,
                ps_tlevel=ps_tlevel,
                ps_cscheme_ul=ps_cscheme_ul,
                ps_dl_carrier=ps_dl_carrier,
                ps_dl_cscheme=ps_dl_cscheme,
            )

        await loop.run_in_executor(None, _do_config)

    async def configure_sms(
        self,
        dcoding: str = "BIT8",
        pid: int = 1,
    ) -> None:
        """Настройка SMS-канала."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: self._driver.configure_sms(dcoding=dcoding, pid=pid)
        )

    async def configure_dau(
        self,
        meas_range: str = "GSM Sig1",
        dns_type: str = "Foreign",
        ipv4_type: str = "DHCPv4",
    ) -> None:
        """Настройка DAU (Data Access Unit)."""
        if self._driver is None:
            raise ConnectionError("CMW-500 driver not connected")
        loop = asyncio.get_running_loop()

        def _do_config() -> None:
            self._driver.configure_dau(
                meas_range=meas_range,
                dns_type=dns_type,
                ipv4_type=ipv4_type,
            )

        await loop.run_in_executor(None, _do_config)


# ════════════════════════════════════════════════════════════
# Эмулятор CMW-500 для разработки и тестов
# ════════════════════════════════════════════════════════════


class Cmw500Emulator(Cmw500Controller):
    """Эмулятор CMW-500 для разработки без реального прибора.

    Переопределяет ``_send_scpi`` с настраиваемыми случайными задержками:
    - Обычные команды: 100мс–2с
    - SEND_SMS: 3–30с (настраиваемый диапазон ``sms_delay_min``–``sms_delay_max``)

    SMS-эмуляция (через очередь команд, как в реальном контроллере):
    - ``send_sms(egts_bytes)`` — ставит SEND_SMS в очередь, _send_scpi эмулирует задержку
    - _send_scpi при SEND_SMS вызывает handler для генерации ответа УСВ
    - ``read_sms()`` — возврат ответа из очереди входящих SMS
    - ``set_incoming_sms_handler(handler)`` — колбэк для генерации ответов УСВ
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
        super().__init__(bus, ip, poll_interval)
        self._tcp_delay_min = tcp_delay_min
        self._tcp_delay_max = tcp_delay_max
        self._sms_delay_min = sms_delay_min
        self._sms_delay_max = sms_delay_max
        self._incoming_sms_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._incoming_sms_handler: Callable[[bytes], bytes | None] | None = None

        # Настраиваемые ответы на SCPI-команды
        self._mock_imei: str = "351234567890123"
        self._mock_imsi: str = "250011234567890"
        self._mock_rssi: str = "-65"
        self._mock_status: str = "1"

    async def connect(self) -> None:
        """Подключиться (эмулятор — без реального драйвера)."""
        # Эмулятор НЕ открывает VisaCmw500Driver — работает напрямую
        self._worker = asyncio.create_task(self._worker_loop())
        self._worker.add_done_callback(self._on_worker_done)
        self._poll_task = asyncio.create_task(self._poll_loop())
        self._poll_task.add_done_callback(self._on_poll_done)
        self._connected = True
        await self.bus.emit("cmw.connected", {"ip": self._ip})

    async def get_full_status(self) -> dict[str, Any]:
        """Статус эмулятора — моковые данные."""
        return {
            "connected": True,
            "serial": "EMULATOR",
            "cs_state": "CONNected",
            "ps_state": "DISConnect",
            "rssi": self._mock_rssi,
            "ber": 0.001,
            "rx_level": -70.0,
            "simulate": True,
            "ip": self._ip,
        }

    async def configure_gsm_signaling(self, **kwargs: Any) -> None:
        """Эмулятор: заглушка конфигурации GSM."""
        pass  # Конфигурация применяется к реальному прибору

    async def configure_sms(
        self, dcoding: str = "BIT8", pid: int = 1
    ) -> None:
        """Эмулятор: заглушка конфигурации SMS."""
        pass

    async def configure_dau(
        self,
        meas_range: str = "GSM Sig1",
        dns_type: str = "Foreign",
        ipv4_type: str = "DHCPv4",
    ) -> None:
        """Эмулятор: заглушка конфигурации DAU."""
        pass

    def set_incoming_sms_handler(
        self, handler: Callable[[bytes], bytes | None]
    ) -> None:
        """Установить колбэк для генерации ответов УСВ на отправленные SMS.

        Args:
            handler: Функция, принимающая сырые EGTS-байты отправленного пакета
                и возвращающая ответный пакет (или None если ответа нет).
        """
        self._incoming_sms_handler = handler

    # ──────────────────── Эмуляция SCPI ─────────────────────

    async def _send_scpi(self, scpi: str) -> str:
        """Эмулировать отправку SCPI-команды с задержкой.

        Args:
            scpi: SCPI-строка команды.

        Returns:
            Эмулированный ответ прибора.
        """
        # Определяем задержку по типу команды
        if "SMS:SEND" in scpi:
            return await self._handle_send_sms(scpi)
        if "SMS:READ" in scpi:
            # READ_SMS? — проверяем очередь входящих
            await self._random_tcp_delay()
            try:
                data = self._incoming_sms_queue.get_nowait()
                return data.hex()
            except asyncio.QueueEmpty:
                return ""
        if "IMEI?" in scpi:
            await self._random_tcp_delay()
            return self._mock_imei
        if "IMSI?" in scpi:
            await self._random_tcp_delay()
            return self._mock_imsi
        if "RSSI?" in scpi:
            await self._random_tcp_delay()
            return self._mock_rssi
        if "CONN?" in scpi:
            await self._random_tcp_delay()
            return self._mock_status

        # Неизвестная команда — эмулируем задержку и ответ
        await self._random_tcp_delay()
        return "OK"

    async def _handle_send_sms(self, scpi: str) -> str:
        """Обработка команды SEND_SMS — эмуляция задержки + вызов handler.

        Формат SCPI: ``CMW:GSM:SIGN:SMS:SEND {hex_data}``

        Args:
            scpi: SCPI-строка с HEX-данными EGTS-пакета.

        Returns:
            Всегда "OK" (эмуляция успешной отправки).
        """
        # Извлекаем HEX-данные из SCPI-команды
        parts = scpi.split(" ", 1)
        if len(parts) < 2:
            await asyncio.sleep(self._random_delay(self._sms_delay_min, self._sms_delay_max))
            return "OK"

        try:
            egts_bytes = bytes.fromhex(parts[1])
        except ValueError:
            await asyncio.sleep(self._random_delay(self._sms_delay_min, self._sms_delay_max))
            return "OK"

        # Эмулируем задержку отправки SMS
        delay = self._random_delay(self._sms_delay_min, self._sms_delay_max)
        await asyncio.sleep(delay)

        # Вызываем handler для генерации ответа от «УСВ»
        if self._incoming_sms_handler is not None:
            handler_result = self._incoming_sms_handler(egts_bytes)
            # Поддержка async handler
            if asyncio.iscoroutine(handler_result):
                handler_result = await handler_result
            if handler_result is not None:
                await self._incoming_sms_queue.put(handler_result)

        return "OK"

    # ──────────────────── Вспомогательные методы ─────────────

    def _random_delay(self, min_val: float, max_val: float) -> float:
        """Случайная задержка в диапазоне [min_val, max_val]."""
        return random.uniform(min_val, max_val)

    async def _random_tcp_delay(self) -> None:
        """Случайная TCP-задержка."""
        await asyncio.sleep(self._random_delay(self._tcp_delay_min, self._tcp_delay_max))
