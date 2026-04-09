"""Cmw500Controller — контроллер CMW-500 через SCPI/VISA over LAN."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass

from core.event_bus import EventBus


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
    """Контроллер CMW-500 через SCPI/VISA over LAN с очередью команд.

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
    ) -> None:
        self.bus = bus
        self._ip = ip
        self._poll_interval = poll_interval
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
            self._worker = asyncio.create_task(self._worker_loop())
            self._worker.add_done_callback(self._on_worker_done)
            self._poll_task = asyncio.create_task(self._poll_loop())
            self._poll_task.add_done_callback(self._on_poll_done)
            self._connected = True
            await self.bus.emit("cmw.connected", {"ip": self._ip})
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

    async def _poll_loop(self) -> None:
        """Фоновый цикл опроса входящих SMS.

        Периодически вызывает _poll_incoming_sms() с интервалом
        ``_poll_interval`` секунд. Ошибки не прерывают цикл —
        они логируются через cmw.error и цикл продолжается.
        """
        while self._connected:
            try:
                await self._poll_incoming_sms()
            except Exception as e:
                await self.bus.emit("cmw.error", {
                    "error": str(e),
                    "command": "poll_sms",
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

        Переопределяется в эмуляторе (Cmw500Emulator) и
    замещается реальной VISA-реализацией при подключении к прибору.

        Args:
            scpi: SCPI-строка команды.

        Returns:
            Ответ прибора (без завершающего newline).

        Raises:
            NotImplementedError: если не переопределён.
        """
        raise NotImplementedError(
            "_send_scpi must be overridden in subclass or mocked"
        )


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
