"""TcpServerManager — asyncio TCP-сервер для приёма EGTS-пакетов."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.event_bus import EventBus

if TYPE_CHECKING:
    from core.session import SessionManager

logger = logging.getLogger(__name__)

# Максимальный размер EGTS-пакета по ГОСТ (65535 байт)
_MAX_EGTS_PACKET_SIZE = 65536


@dataclass
class TcpServerManager:
    """Asyncio TCP-сервер для приёма EGTS-пакетов от тестируемого УСВ.

    Управляет жизненным циклом TCP-сервера: запуск, приём подключений,
    чтение данных, обработка отключений.

    События EventBus:
        - connection.changed: при подключении/отключении клиента
        - raw.packet.received: при получении данных от клиента

    Пример использования::

        bus = EventBus()
        srv = TcpServerManager(bus=bus, host="127.0.0.1", port=3001)
        await srv.start()
        try:
            # сервер работает...
            await asyncio.sleep(3600)
        finally:
            await srv.stop()
    """

    bus: EventBus
    host: str = "0.0.0.0"
    port: int = 3001
    session_mgr: SessionManager | None = None
    read_buffer_size: int = _MAX_EGTS_PACKET_SIZE

    # Внутренние поля
    _server: asyncio.Server | None = field(default=None, init=False, repr=False)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False, repr=False)

    @property
    def server(self) -> asyncio.Server | None:
        """Объект asyncio.Server или None если сервер не запущен."""
        return self._server

    @property
    def is_running(self) -> bool:
        """Проверка, запущен ли сервер."""
        return self._server is not None and self._server.is_serving()

    @property
    def actual_port(self) -> int | None:
        """Фактический порт, на котором слушает сервер.

        Returns:
            Номер порта или None если сервер не запущен.
        """
        if self._server is None:
            return None
        socks = self._server.sockets
        if not socks:
            return None
        addr: tuple[str, int] = socks[0].getsockname()
        return addr[1]

    async def start(self) -> None:
        """Запустить TCP-сервер.

        Вызывает asyncio.start_server() и начинает принимать подключения.
        Повторный вызов игнорируется (idempotent).
        """
        if self.is_running:
            logger.debug("TcpServerManager уже запущен, пропускаю start()")
            return

        self._server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port,
        )

        actual_port = self.actual_port or self.port
        logger.info("TcpServerManager запущен на %s:%s", self.host, actual_port)

        await self.bus.emit(
            "server.started",
            {"port": actual_port},
        )

    async def stop(self) -> None:
        """Остановить TCP-сервер.

        Закрывает слушающий сокет и все активные подключения.
        Вызов без start() не вызывает ошибок.
        """
        if self._server is None:
            logger.debug("TcpServerManager не запущен, пропускаю stop()")
            return

        logger.info("Останавливаю TcpServerManager...")

        # 1. Отменяем handler-задачи (иначе wait_closed зависнет)
        tasks_to_cancel = list(self._tasks)
        for task in tasks_to_cancel:
            task.cancel()

        # 2. Дожидаемся завершения отменённых задач
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        self._tasks.clear()

        # 3. Закрываем слушающий сокет
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        logger.info("TcpServerManager остановлен")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Обработка одного клиентского подключения.

        Args:
            reader: Поток чтения данных от клиента.
            writer: Поток записи данных клиенту.
        """
        peername = writer.get_extra_info("peername")
        connection_id = str(uuid.uuid4())
        remote_host = str(peername[0]) if peername else ""
        remote_port = int(peername[1]) if peername else 0
        logger.info("Новое подключение %s от %s", connection_id, peername)

        # Создание полноценной сессии через SessionManager
        if self.session_mgr is not None:
            conn = self.session_mgr.create_session(
                connection_id=connection_id,
                remote_ip=remote_host,
                remote_port=remote_port,
                reader=reader,
                writer=writer,
            )
            # Инициализация FSM при подключении (CR-010)
            if conn.fsm is not None:
                conn.fsm.on_connect()

        # Эмитим событие подключения
        await self.bus.emit(
            "connection.changed",
            {
                "connection_id": connection_id,
                "usv_id": connection_id,
                "state": "CONNECTED",
                "prev_state": None,
                "action": "connected",
                "reason": f"Connected from {peername}",
                "timestamp": time.monotonic(),
            },
        )

        # Создаём задачу для чтения данных
        task = asyncio.create_task(
            self._read_loop(connection_id, reader, writer),
            name=f"tcp-read-{connection_id[:8]}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        try:
            await task
        except asyncio.CancelledError:
            logger.debug("Задача чтения %s отменена", connection_id)

    async def _read_loop(
        self,
        connection_id: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Цикл чтения данных от клиента.

        Читает данные из потока и эмитит raw.packet.received
        для каждого полученного блока данных.

        Args:
            connection_id: Идентификатор подключения.
            reader: Поток чтения.
            writer: Поток записи (для закрытия при ошибке).
        """
        try:
            while True:
                data = await reader.read(self.read_buffer_size)
                if not data:
                    # Клиент закрыл соединение
                    logger.debug("Клиент %s закрыл соединение", connection_id)
                    break

                logger.debug(
                    "Получено %d байт от %s: %s",
                    len(data),
                    connection_id,
                    data.hex().upper(),
                )

                await self.bus.emit(
                    "raw.packet.received",
                    {
                        "raw": data,
                        "channel": "tcp",
                        "connection_id": connection_id,
                    },
                )

        except (ConnectionResetError, BrokenPipeError, OSError) as exc:
            logger.warning("Ошибка чтения от %s: %s", connection_id, exc)
        except asyncio.CancelledError:
            raise
        finally:
            await self._on_disconnect(connection_id, writer)

    async def _on_disconnect(
        self,
        connection_id: str,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Обработка отключения клиента.

        Args:
            connection_id: Идентификатор подключения.
            writer: Поток записи для закрытия.
        """
        logger.info("Отключение %s", connection_id)

        # Закрытие writer
        if writer and not writer.is_closing():
            writer.close()

        # Удаление из SessionManager с уведомлением FSM (CR-011)
        if self.session_mgr is not None:
            conn = self.session_mgr.connections.get(connection_id)
            if conn and conn.fsm is not None:
                conn.fsm.on_disconnect()
            self.session_mgr.connections.pop(connection_id, None)

        # Эмитим событие отключения
        await self.bus.emit(
            "connection.changed",
            {
                "connection_id": connection_id,
                "usv_id": connection_id,
                "state": "DISCONNECTED",
                "prev_state": conn.fsm.state.value if conn and conn.fsm else None,
                "action": "disconnected",
                "reason": "TCP connection closed",
                "timestamp": time.monotonic(),
            },
        )
