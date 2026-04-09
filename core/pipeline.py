"""PacketPipeline + PacketContext + Middleware — конвейер обработки пакетов.

Конвейер обрабатывает входящие EGTS-пакеты через цепочку middleware.
Каждый middleware получает PacketContext, может изменять его поля
и прервать обработку (terminated=True).

Порядок middleware определяется параметром order (меньший — раньше).
При одинаковом order — порядок добавления (стабильная сортировка).

Пример использования::

    pipeline = PacketPipeline()
    pipeline.add("crc", CrcValidationMiddleware(protocol), order=10)
    pipeline.add("parse", ParseMiddleware(session_mgr), order=20)
    pipeline.add("dedup", DuplicateDetectionMiddleware(session_mgr), order=30)
    pipeline.add("event", EventEmitMiddleware(bus), order=40)

    ctx = PacketContext(raw=packet_bytes, connection_id=conn_id)
    ctx = await pipeline.process(ctx)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.session import SessionManager
from libs.egts_protocol_iface import (
    EGTS_PC_DATACRC_ERROR,
    EGTS_PC_HEADERCRC_ERROR,
    PACKET_HEADER_MIN_SIZE,
)

logger = logging.getLogger(__name__)

# =============================================================================
# PacketContext
# =============================================================================


@dataclass
class PacketContext:
    """Контекст обработки одного пакета.

    Передаётся через все middleware — каждый может читать/изменять поля.

    Attributes:
        raw: Сырые байты пакета (не изменяется)
        connection_id: Идентификатор подключения
        channel: Канал получения — "tcp" или "sms"
        parsed: Распарсенный пакет (заполняется ParseMiddleware)
        crc8_valid: CRC-8 заголовка корректна
        crc16_valid: CRC-16 тела корректна
        crc_valid: Обе CRC корректны (агрегированный флаг)
        is_duplicate: Пакет с таким PID уже обрабатывался
        response_data: RESPONSE для отправки (ошибка, дубликат, успех)
        terminated: Прервать цепочку обработки
        errors: Список ошибок обработки (для логирования)
        timestamp: Время создания контекста (monotonic)
    """

    raw: bytes
    connection_id: str
    channel: str = "tcp"
    parsed: dict[str, Any] | None = None
    crc8_valid: bool = False
    crc16_valid: bool = False
    crc_valid: bool = False
    is_duplicate: bool = False
    response_data: bytes | None = None
    terminated: bool = False
    errors: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.monotonic)


# =============================================================================
# Middleware Protocol
# =============================================================================


class Middleware(Protocol):
    """Протокол middleware конвейера.

    Каждый middleware — async-функция, принимающая PacketContext.
    Для прерывания цепочки нужно установить ctx.terminated = True.
    Для отправки RESPONSE — заполнить ctx.response_data.
    Для записи ошибок — добавить в ctx.errors.

    Поддерживаются как классы с ``__call__``, так и обычные
    async-функции — оба варианта совместимы с Protocol.
    """

    async def __call__(self, ctx: PacketContext) -> None: ...


# =============================================================================
# Внутренние структуры
# =============================================================================


@dataclass
class _MiddlewareEntry:
    """Запись middleware в конвейере."""

    order: int
    name: str
    middleware: Middleware


# =============================================================================
# PacketPipeline
# =============================================================================


class PacketPipeline:
    """Конвейер обработки пакетов с middleware.

    Middleware добавляются через add() с параметром order.
    При process() выполняются в порядке возрастания order.
    При terminated=True или exception — цепочка прерывается,
    ошибка записывается в ctx.errors.
    """

    def __init__(self) -> None:
        self._middlewares: list[_MiddlewareEntry] = []

    def add(self, name: str, middleware: Middleware, order: int = 0) -> None:
        """Добавить middleware в конвейер.

        Args:
            name: Имя middleware (для логирования/отладки и отчётов об ошибках)
            middleware: Async-функция или объект с async __call__
            order: Порядок выполнения (меньший = раньше).
                   При равном order сохраняется порядок добавления
                   (стабильность сортировки гарантируется Python).
        """
        entry = _MiddlewareEntry(order=order, name=name, middleware=middleware)
        self._middlewares.append(entry)
        self._middlewares.sort(key=lambda e: e.order)

    async def process(self, ctx: PacketContext) -> PacketContext:
        """Запустить конвейер обработки.

        Middleware выполняются последовательно по order.
        Цепочка прерывается при:
        - ctx.terminated=True (до вызова middleware)
        - Исключении в middleware (ошибка записывается в ctx.errors)

        Args:
            ctx: Контекст пакета

        Returns:
            Тот же ctx (с изменениями от middleware)
        """
        if ctx.terminated:
            return ctx

        for entry in self._middlewares:
            if ctx.terminated:
                break
            try:
                await entry.middleware(ctx)
            except Exception as e:
                ctx.errors.append(f"{entry.name}: {e!s}")
                ctx.terminated = True
                break

        return ctx


# =============================================================================
# CrcValidationMiddleware
# =============================================================================


class CrcValidationMiddleware:
    """Валидация CRC-8 заголовка и CRC-16 данных EGTS-пакета.

    Получает protocol из UsvConnection (не хардкодит create_protocol).
    При ошибке CRC формирует RESPONSE с кодом RCR.
    """

    def __init__(self, session_mgr: SessionManager) -> None:
        self._session_mgr = session_mgr

    async def __call__(self, ctx: PacketContext) -> None:
        """Валидировать CRC и заполнить crc_valid, crc8_valid, crc16_valid,
        response_data (при ошибке), terminated."""
        raw = ctx.raw
        if not raw:
            logger.warning("CRC check: empty raw packet")
            ctx.crc_valid = False
            ctx.terminated = True
            return

        # Получить connection через публичный метод SessionManager
        conn = self._session_mgr.get_session(ctx.connection_id)
        if conn is None:
            logger.warning("CRC check: connection %s not found", ctx.connection_id)
            ctx.crc_valid = False
            ctx.terminated = True
            return

        protocol = conn.protocol
        if protocol is None:
            logger.warning("CRC check: protocol is None for connection %s", ctx.connection_id)
            ctx.crc_valid = False
            ctx.terminated = True
            return

        # Извлечь HL (header length) — байт 3 в заголовке
        if len(raw) < 4:
            logger.warning("CRC check: packet too short (%d bytes)", len(raw))
            ctx.crc_valid = False
            ctx.terminated = True
            return

        header_len = raw[3]
        if header_len < PACKET_HEADER_MIN_SIZE or len(raw) < header_len + 2:
            logger.warning(
                "CRC check: invalid header_len=%d or packet too short (%d bytes)",
                header_len,
                len(raw),
            )
            ctx.crc_valid = False
            ctx.terminated = True
            return

        # Header (включая HCS) и body
        header_with_hcs = raw[:header_len]
        body_with_crc16 = raw[header_len:]

        # Проверка наличия CRC-16 в теле
        if len(body_with_crc16) < 2:
            logger.warning(
                "CRC check: body too short for CRC-16 (%d bytes)", len(body_with_crc16)
            )
            ctx.crc_valid = False
            ctx.terminated = True
            return

        # Header без HCS (последний байт header = CRC-8)
        header_data = header_with_hcs[:-1]
        hcs_byte = header_with_hcs[-1]

        # Body без CRC-16 (последние 2 байта = CRC-16)
        body_data = body_with_crc16[:-2]
        crc16_value = int.from_bytes(body_with_crc16[-2:], "little")

        # Валидация CRC-8
        crc8_ok = protocol.validate_crc8(header_data, hcs_byte)
        ctx.crc8_valid = crc8_ok

        if not crc8_ok:
            logger.warning(
                "CRC-8 mismatch for connection %s", ctx.connection_id
            )
            ctx.crc_valid = False
            # При ошибке CRC-8 PID неизвестен → используем 0
            ctx.response_data = protocol.build_response(
                pid=0, result_code=EGTS_PC_HEADERCRC_ERROR
            )
            ctx.terminated = True
            return

        # Валидация CRC-16
        crc16_ok = protocol.validate_crc16(body_data, crc16_value)
        ctx.crc16_valid = crc16_ok

        if not crc16_ok:
            logger.warning(
                "CRC-16 mismatch for connection %s", ctx.connection_id
            )
            ctx.crc_valid = False
            # При ошибке CRC-16 PID неизвестен → используем 0
            ctx.response_data = protocol.build_response(
                pid=0, result_code=EGTS_PC_DATACRC_ERROR
            )
            ctx.terminated = True
            return

        # Всё ок
        ctx.crc8_valid = True
        ctx.crc16_valid = True
        ctx.crc_valid = True
        logger.debug("CRC check passed for connection %s", ctx.connection_id)
