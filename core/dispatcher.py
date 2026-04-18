"""PacketDispatcher и CommandDispatcher — координаторы обработки пакетов.

PacketDispatcher — channel-agnostic координатор pipeline:
- Подписывается на raw.packet.received (от TcpServerManager, Cmw500Controller)
- Передаёт сырые пакеты в PacketPipeline
- EventEmitMiddleware внутри pipeline эмитит packet.processed
- Отправляет RESPONSE через writer подключения (для TCP)

CommandDispatcher — координатор отправки команд:
- Подписывается на command.send
- Отправляет через TCP или SMS в зависимости от channel
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from core.egts_adapter import create_protocol
from core.event_bus import EventBus
from core.pipeline import (
    AutoResponseMiddleware,
    CrcValidationMiddleware,
    DuplicateDetectionMiddleware,
    EventEmitMiddleware,
    PacketContext,
    PacketPipeline,
    ParseMiddleware,
)

if TYPE_CHECKING:
    from core.cmw500 import Cmw500Controller
    from core.event_bus import EventBus
    from core.session import SessionManager
    from libs.egts.protocol import IEgtsProtocol

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.CRITICAL)   #fixme

# Идентификатор SMS-сессии, создаваемой автоматически
_SMS_DEFAULT_CONNECTION_ID = "packet_dispatcher_sms"


def _is_writer_closing(writer: object) -> bool:
    """Проверить, закрывается ли writer.

    Корректно работает как с реальным asyncio.StreamWriter,
    так и с AsyncMock/MagicMock в тестах.
    """
    if hasattr(writer, "is_closing") and callable(writer.is_closing):
        try:
            result = writer.is_closing()
            # Mock возвращает coroutine — считаем активным
            if hasattr(result, "__await__"):
                return False
            return bool(result)
        except Exception:
            # Если is_closing бросил исключение — считаем writer активным
            pass
    return False


# =============================================================================
# PacketDispatcher
# =============================================================================


class PacketDispatcher:
    """Координатор pipeline — связывает raw packets → pipeline → packet.processed.

    Поддерживает оба канала (TCP и SMS) одинаково:
    - channel передаётся из источника пакета в pipeline
    - connection_id для SMS может быть None
    - Pipeline обрабатывает оба канала одинаково

    События:
        - Подписка на raw.packet.received — получение сырых пакетов
        - Подписка на packet.processed — отправка RESPONSE

    Args:
        bus: EventBus для подписки на события
        session_mgr: SessionManager для получения сессий и протокола
        pipeline: PacketPipeline для обработки пакетов
        protocol: Протокол EGTS (используется для SMS если нет сессии)
    """

    def __init__(
        self,
        bus: EventBus,
        session_mgr: SessionManager,
        pipeline: PacketPipeline | None = None,
        protocol: IEgtsProtocol | None = None,
    ) -> None:
        self.bus = bus
        self.session_mgr = session_mgr
        self.pipeline = pipeline if pipeline is not None else self._build_pipeline()
        self.protocol = protocol

        # Подписка на raw.packet.received
        self.bus.on("raw.packet.received", self._on_raw_packet)

        # Подписка на packet.processed для отправки RESPONSE
        self.bus.on("packet.processed", self._on_packet_processed)

    def _build_pipeline(self) -> PacketPipeline:
        """Создать стандартный pipeline со всеми middleware.

        Порядок важен — каждая middleware работает с результатами предыдущей:
        1. CrcValidationMiddleware — проверяет CRC-8 заголовка и CRC-16 данных
        2. ParseMiddleware — распознаёт EGTS-пакет
        3. DuplicateDetectionMiddleware — отсеивает дубликаты по PID
        4. AutoResponseMiddleware — формирует RESPONSE при успешном приёме
        5. EventEmitMiddleware — эмитит packet.processed (всегда, даже при ошибках)
        """
        p = PacketPipeline()
        p.add("crc", CrcValidationMiddleware(self.session_mgr), order=1)
        p.add("parse", ParseMiddleware(self.session_mgr), order=2)
        p.add("dedup", DuplicateDetectionMiddleware(self.session_mgr), order=3)
        p.add("auto_resp", AutoResponseMiddleware(self.session_mgr), order=4)
        p.add("emit", EventEmitMiddleware(self.bus), order=5)
        return p

    def stop(self) -> None:
        """Отписаться от событий EventBus."""
        self.bus.off("raw.packet.received", self._on_raw_packet)
        self.bus.off("packet.processed", self._on_packet_processed)
        logger.info("PacketDispatcher: отписался от событий")

    async def _on_raw_packet(self, data: dict[str, Any]) -> None:
        """Обработать сырой пакет из любого источника (TCP или SMS).

        Args:
            data: Данные события raw.packet.received:
                - raw: bytes — сырые байты пакета
                - channel: str — "tcp" или "sms"
                - connection_id: str | None — идентификатор подключения
        """
        raw: bytes = data.get("raw", b"")
        channel: str = data.get("channel", "tcp")
        connection_id: str | None = data.get("connection_id")

        if not raw:
            logger.warning("PacketDispatcher: пустой пакет, пропускаю")
            return

        # Если connection_id=None (SMS без привязки к сессии) —
        # создаём/используем SMS-сессию с внутренним ID
        if connection_id is None:
            self._ensure_sms_session()
            effective_conn_id = _SMS_DEFAULT_CONNECTION_ID
        else:
            effective_conn_id = connection_id

        # Создаём контекст пакета
        ctx = PacketContext(
            raw=raw,
            connection_id=effective_conn_id,
            channel=channel,
        )

        logger.debug(
            "PacketDispatcher: обработка пакета channel=%s, connection_id=%s, size=%d",
            channel,
            connection_id,
            len(raw),
        )

        # Передаём в pipeline
        try:
            await self.pipeline.process(ctx)
        except Exception as e:
            logger.error(
                "PacketDispatcher: ошибка pipeline: %s", e, exc_info=True
            )

    async def _on_packet_processed(self, data: dict[str, Any]) -> None:
        """Обработать событие packet.processed — отправить RESPONSE.

        Args:
            data: Данные события packet.processed:
                - ctx: PacketContext
                - connection_id: str | None
                - channel: str
        """
        ctx: PacketContext | None = data.get("ctx")
        connection_id: str | None = data.get("connection_id")
        channel: str = data.get("channel", "tcp")

        if ctx is None:
            return

        # Отправляем RESPONSE только если есть response_data
        if ctx.response_data is None:
            return

        # Для TCP — отправляем через writer
        if channel == "tcp" and connection_id:
            await self._send_response_tcp(connection_id, ctx.response_data)
            logger.info(
                "RESPONSE отправлен %s через TCP (%d байт)",
                connection_id,
                len(ctx.response_data),
            )
        # Для SMS — RESPONSE не отправляем обратно по SMS (CMW-500 управляет)
        elif channel == "sms":
            logger.debug("SMS-канал: RESPONSE не отправляется (управляется CMW-500)")

    async def _send_response_tcp(self, connection_id: str, response: bytes) -> None:
        """Отправить RESPONSE через TCP-соединение.

        Args:
            connection_id: Идентификатор подключения
            response: Байты RESPONSE-пакета
        """
        conn = self.session_mgr.get_session(connection_id)
        if conn is None:
            logger.warning(
                "PacketDispatcher: сессия %s не найдена, RESPONSE не отправлен",
                connection_id,
            )
            return

        writer = conn.writer
        if writer is None:
            logger.warning(
                "PacketDispatcher: writer для %s недоступен, RESPONSE не отправлен",
                connection_id,
            )
            return

        # Проверка is_closing
        if _is_writer_closing(writer):
            logger.warning(
                "PacketDispatcher: writer для %s закрывается, RESPONSE не отправлен",
                connection_id,
            )
            return

        try:
            writer.write(response)
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.warning(
                "PacketDispatcher: ошибка отправки RESPONSE %s: %s",
                connection_id,
                e,
            )

    def _ensure_sms_session(self) -> None:
        """Создать сессию для SMS если ещё не существует.

        Использует protocol из dispatcher если не задан в session_mgr.
        """
        if _SMS_DEFAULT_CONNECTION_ID in self.session_mgr.connections:
            return

        protocol = self.protocol
        if protocol is None:
            logger.warning(
                "PacketDispatcher: protocol=None для SMS-сессии, "
                "использую ГОСТ 2015 по умолчанию"
            )
            protocol = create_protocol("2015")

        self.session_mgr.create_session(
            connection_id=_SMS_DEFAULT_CONNECTION_ID,
            protocol=protocol,
        )
        logger.debug("PacketDispatcher: создана SMS-сессия по умолчанию")


# =============================================================================
# CommandDispatcher
# =============================================================================


class CommandDispatcher:
    """Координатор отправки команд — подписан на command.send.

    Поддерживает два канала:
    - tcp: отправка через writer конкретной сессии
    - sms: отправка через Cmw500Controller.send_sms()

    События:
        - Подписка на command.send
        - Эмит command.sent при успешной отправке
        - Эмит command.error при ошибке

    Args:
        bus: EventBus для подписки на события
        session_mgr: SessionManager для получения сессий
        cmw: Контроллер CMW-500 (для SMS-канала, опционально)
    """

    def __init__(
        self,
        bus: EventBus,
        session_mgr: SessionManager,
        cmw: Cmw500Controller | None = None,
    ) -> None:
        self.bus = bus
        self.session_mgr = session_mgr
        self.cmw = cmw
        self.bus.on("command.send", self._on_command)

    def stop(self) -> None:
        """Отписаться от событий EventBus."""
        self.bus.off("command.send", self._on_command)
        logger.info("CommandDispatcher: отписался от событий")

    def _ensure_sms_session_for_txn(self) -> None:
        """Создать SMS-сессию если ещё не существует (для транзакций)."""
        if _SMS_DEFAULT_CONNECTION_ID in self.session_mgr.connections:
            return

        protocol = self._get_sms_protocol()
        self.session_mgr.create_session(
            connection_id=_SMS_DEFAULT_CONNECTION_ID,
            protocol=protocol,
        )
        logger.debug("CommandDispatcher: создана SMS-сессия для транзакции")

    def _get_sms_protocol(self) -> IEgtsProtocol:
        """Получить протокол для SMS-сессии."""
        return create_protocol("2015")

    async def _on_command(self, data: dict[str, Any]) -> None:
        """Обработать команду отправки.

        Args:
            data: Данные события command.send:
                - channel: str — "tcp" или "sms" (по умолчанию "tcp")
                - connection_id: str | None — идентификатор подключения
                - packet_bytes: bytes — сырые байты EGTS-пакета
                - step_name: str | None — имя шага сценария
                - pid: int | None — Packet ID для транзакции
                - rn: int | None — Record Number для транзакции
                - timeout: float — таймаут транзакции (по умолчанию 30.0)
        """
        channel = data.get("channel", "tcp")
        connection_id = data.get("connection_id")
        packet_bytes = data.get("packet_bytes", b"")
        step_name = data.get("step_name")
        pid = data.get("pid")
        rn = data.get("rn")
        timeout = data.get("timeout", 30.0)

        if not packet_bytes:
            await self.bus.emit(
                "command.error",
                {
                    "error": "empty packet_bytes",
                    "step_name": step_name,
                },
            )
            return

        try:
            if channel == "tcp":
                await self._send_tcp(
                    connection_id=connection_id,
                    packet_bytes=packet_bytes,
                    step_name=step_name,
                    pid=pid,
                    rn=rn,
                    timeout=timeout,
                )
            elif channel == "sms":
                await self._send_sms(
                    packet_bytes=packet_bytes,
                    step_name=step_name,
                    pid=pid,
                    rn=rn,
                    timeout=timeout,
                )
            else:
                raise ValueError(f"Unknown channel: {channel}")
        except Exception as e:
            logger.error("CommandDispatcher: ошибка отправки: %s", e, exc_info=True)
            await self.bus.emit(
                "command.error",
                {
                    "error": str(e),
                    "step_name": step_name,
                },
            )

    async def _send_tcp(
        self,
        connection_id: str | None,
        packet_bytes: bytes,
        step_name: str | None,
        pid: int | None,
        rn: int | None,
        timeout: float,
    ) -> None:
        """Отправить команду через TCP-соединение.

        Args:
            connection_id: Идентификатор подключения
            packet_bytes: Сырые байты EGTS-пакета
            step_name: Имя шага сценария
            pid: Packet ID для транзакции
            rn: Record Number для транзакции
            timeout: Таймаут транзакции
        """
        if connection_id is None:
            raise ValueError("TCP channel requires connection_id")

        conn = self.session_mgr.get_session(connection_id)
        if conn is None:
            raise ValueError(f"Connection {connection_id} not found")

        writer = conn.writer
        if writer is None:
            raise ValueError(f"Connection {connection_id} has no writer")

        # Проверка is_closing
        if _is_writer_closing(writer):
            raise ConnectionError(
                f"Connection {connection_id} is closing"
            )

        # Извлечение PID/RN из packet_bytes если не переданы явно
        # Это позволяет регистрировать транзакции даже для hex-файлов
        effective_pid: int | None = pid
        effective_rn: int | None = rn

        if effective_pid is None or effective_rn is None:
            parsed = self._parse_packet_bytes(conn, packet_bytes)
            if parsed is not None:
                if effective_pid is None:
                    effective_pid = parsed.get("packet_id")
                if effective_rn is None:
                    effective_rn = parsed.get("record_id")

        # Регистрация транзакции ДО отправки (KI-052)
        if effective_pid is not None or effective_rn is not None:
            if conn.transaction_mgr is not None:
                conn.transaction_mgr.register(
                    pid=effective_pid,
                    rn=effective_rn,
                    step_name=step_name or "",
                    timeout=timeout,
                )
            else:
                logger.warning(
                    "CommandDispatcher: transaction_mgr отсутствует для %s",
                    connection_id,
                )

        writer.write(packet_bytes)
        await writer.drain()

        # Эмит события packet.sent для логирования отправленного пакета
        await self.bus.emit(
            "packet.sent",
            {
                "connection_id": connection_id,
                "step_name": step_name,
                "packet_bytes": packet_bytes,
                "channel": "tcp",
                "pid": effective_pid,
                "rn": effective_rn,
            },
        )

        await self.bus.emit(
            "command.sent",
            {
                "connection_id": connection_id,
                "step_name": step_name,
                "packet_bytes": packet_bytes,
                "channel": "tcp",
            },
        )
        logger.info(
            "CommandDispatcher: команда отправлена через TCP %s (pid=%s, rn=%s, %d байт)",
            connection_id,
            effective_pid,
            effective_rn,
            len(packet_bytes),
        )

    def _parse_packet_bytes(
        self, conn: object, packet_bytes: bytes
    ) -> dict[str, int | None] | None:
        """Извлечь PID/RN из сырых байтов пакета.

        Использует protocol из сессии для парсинга.
        Возвращает dict с packet_id и record_id (первая запись).
        """
        try:
            # Получаем protocol из сессии
            protocol = getattr(conn, "protocol", None)
            if protocol is None:
                logger.debug("_parse_packet_bytes: protocol недоступен")
                return None

            parsed = protocol.parse_packet(packet_bytes)
            if parsed.packet is None:
                logger.debug("_parse_packet_bytes: parse_packet вернул None")
                return None

            result: dict[str, int | None] = {
                "packet_id": parsed.packet.packet_id,
                "record_id": None,
            }

            if parsed.packet.records:
                result["record_id"] = parsed.packet.records[0].record_id

            return result

        except Exception as e:
            logger.debug("_parse_packet_bytes: ошибка: %s", e)
            return None

    async def _send_sms(
        self,
        packet_bytes: bytes,
        step_name: str | None,
        pid: int | None,
        rn: int | None,
        timeout: float,
    ) -> None:
        """Отправить команду через SMS (CMW-500).

        Args:
            packet_bytes: Сырые байты EGTS-пакета
            step_name: Имя шага сценария
            pid: Packet ID для транзакции
            rn: Record Number для транзакции
            timeout: Таймаут транзакции
        """
        if self.cmw is None:
            raise RuntimeError(
                "CommandDispatcher: CMW-500 контроллер не подключён (cmw=None)"
            )

        success = await self.cmw.send_sms(packet_bytes)
        if not success:
            raise RuntimeError("CMW-500: send_sms вернул False")

        # Регистрация транзакции для SMS-канала
        if pid is not None or rn is not None:
            self._ensure_sms_session_for_txn()
            conn = self.session_mgr.get_session(_SMS_DEFAULT_CONNECTION_ID)
            if conn is not None and conn.transaction_mgr is not None:
                conn.transaction_mgr.register(
                    pid=pid,
                    rn=rn,
                    step_name=step_name or "",
                    timeout=timeout,
                )
            else:
                logger.warning(
                    "CommandDispatcher: SMS-сессия или transaction_mgr недоступны"
                )

        # Эмит события packet.sent для логирования отправленного пакета
        await self.bus.emit(
            "packet.sent",
            {
                "connection_id": _SMS_DEFAULT_CONNECTION_ID,
                "step_name": step_name,
                "packet_bytes": packet_bytes,
                "channel": "sms",
                "pid": pid,
                "rn": rn,
            },
        )

        await self.bus.emit(
            "command.sent",
            {
                "connection_id": _SMS_DEFAULT_CONNECTION_ID,
                "step_name": step_name,
                "packet_bytes": packet_bytes,
                "channel": "sms",
            },
        )
        logger.info(
            "CommandDispatcher: команда отправлена через SMS (%d байт)",
            len(packet_bytes),
        )
