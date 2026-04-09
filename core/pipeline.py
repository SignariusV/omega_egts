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
from typing import Protocol

from core.event_bus import EventBus
from core.session import SessionManager
from libs.egts_protocol_iface import (
    EGTS_PC_DATACRC_ERROR,
    EGTS_PC_HEADERCRC_ERROR,
    PACKET_HEADER_MIN_SIZE,
)
from libs.egts_protocol_iface.models import ParseResult

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
        parsed: Результат парсинга ParseResult (заполняется ParseMiddleware)
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
    parsed: ParseResult | None = None
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

        EventEmitMiddleware (если добавлен) вызывается всегда — даже при
        terminated=True — для обеспечения 100% логирования пакетов.

        Args:
            ctx: Контекст пакета

        Returns:
            Тот же ctx (с изменениями от middleware)
        """
        if ctx.terminated:
            return ctx

        # Разделяем EventEmitMiddleware и остальные
        event_mw = None
        regular_mw = []
        for entry in self._middlewares:
            if isinstance(entry.middleware, EventEmitMiddleware):
                event_mw = entry
            else:
                regular_mw.append(entry)

        # Выполняем обычные middleware
        for entry in regular_mw:
            if ctx.terminated:
                break
            try:
                await entry.middleware(ctx)
            except Exception as e:
                ctx.errors.append(f"{entry.name}: {e!s}")
                ctx.terminated = True
                break

        # EventEmitMiddleware вызывается всегда (даже при terminated)
        if event_mw is not None:
            try:
                await event_mw.middleware(ctx)
            except Exception as e:
                # Ошибка в EventEmitMiddleware логируется, но не прерывает
                ctx.errors.append(f"{event_mw.name}: {e!s}")

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
        ctx.crc_valid = True
        logger.debug("CRC check passed for connection %s", ctx.connection_id)


# =============================================================================
# AutoResponseMiddleware
# =============================================================================


class AutoResponseMiddleware:
    """Формирование RESPONSE для успешно обработанных пакетов.

    Работает ПОСЛЕ ParseMiddleware и ПЕРЕД DuplicateDetectionMiddleware:
    - Если crc_valid=False — пропускает (RESPONSE уже в CrcValidationMiddleware)
    - Если parsed.packet=None — пропускает (парсинг не удался)
    - Если is_duplicate=True — пропускает (RESPONSE из кэша в Dedup)
    - Если response_data уже заполнен — не перезаписывает
    - Для успешного пакета формирует RESPONSE(pid, result_code=0)
    - Кеширует RESPONSE через conn.add_pid_response() для будущих дубликатов
    """

    def __init__(self, session_mgr: SessionManager) -> None:
        self._session_mgr = session_mgr

    async def __call__(self, ctx: PacketContext) -> None:
        # Пропускаем если CRC невалиден — RESPONSE уже сформирован
        if not ctx.crc_valid:
            return

        # Пропускаем если не распарсен
        if ctx.parsed is None or ctx.parsed.packet is None:
            return

        # Пропускаем если уже дубликат — RESPONSE из кэша
        if ctx.is_duplicate:
            return

        # Пропускаем если response_data уже заполнен
        if ctx.response_data is not None:
            return

        conn = self._session_mgr.get_session(ctx.connection_id)
        if conn is None:
            logger.debug("AutoResponse: connection %s not found", ctx.connection_id)
            return

        protocol = conn.protocol
        if protocol is None:
            logger.debug("AutoResponse: protocol is None for %s", ctx.connection_id)
            return

        packet = ctx.parsed.packet
        pid = packet.packet_id

        # Формируем RESPONSE с result_code=0 (успешная обработка)
        response_data = protocol.build_response(pid=pid, result_code=0)
        ctx.response_data = response_data

        # Кешируем для будущих дубликатов
        conn.add_pid_response(pid=pid, response=response_data)

        logger.debug(
            "AutoResponse: RESPONSE для PID=%d (%d байт)",
            pid,
            len(response_data),
        )


# =============================================================================
# DuplicateDetectionMiddleware
# =============================================================================


class DuplicateDetectionMiddleware:
    """Обнаружение дубликатов PID через LRU-кэш UsvConnection.

    Работает ПОСЛЕ ParseMiddleware и CrcValidationMiddleware:
    - Если crc_valid=False — пропускает (пакет с ошибкой)
    - Если parsed.packet=None — пропускает (ждёт ParseMiddleware)
    - Если ctx.is_duplicate=True — уже обработан, пропускает
    - Если PID уже в кэше — дубликат: ctx.is_duplicate=True,
      ctx.response_data из кэша, ctx.terminated=True
    - Иначе — продолжает обработку
    """

    def __init__(self, session_mgr: SessionManager) -> None:
        self._session_mgr = session_mgr

    async def __call__(self, ctx: PacketContext) -> None:
        """Проверить PID на дубликат, заполнить is_duplicate,
        response_data (при дубликате), terminated."""
        # Пропускаем если CRC невалиден — пакет с ошибкой не дубликат
        if not ctx.crc_valid:
            return

        # Пропускаем если ещё не распарсен — ждём ParseMiddleware
        if ctx.parsed is None or ctx.parsed.packet is None:
            return

        # Уже помечен как дубликат — не обрабатываем повторно
        if ctx.is_duplicate:
            return

        conn = self._session_mgr.get_session(ctx.connection_id)
        if conn is None:
            logger.debug("Dedup: connection %s not found, skipping", ctx.connection_id)
            return

        pid = ctx.parsed.packet.packet_id
        cached_response = conn.get_response(pid)

        if cached_response is not None:
            # Дубликат — RESPONSE уже отправлялся ранее
            logger.info("Duplicate packet PID=%d from %s", pid, ctx.connection_id)
            ctx.is_duplicate = True
            ctx.response_data = cached_response
            ctx.terminated = True
            return

        # Первый пакет — просто логируем. PID добавляется в кэш
        # после формирования RESPONSE (на уровне сервисной обработки).
        logger.debug("First seen PID=%d from %s", pid, ctx.connection_id)


# =============================================================================
# ParseMiddleware
# =============================================================================


class ParseMiddleware:
    """Парсинг EGTS-пакетов через protocol.

    Получает protocol из UsvConnection через SessionManager.
    При успешном парсинге заполняет ctx.parsed ParseResult.
    При ошибке — записывает ошибку в ctx.errors и устанавливает terminated=True.

    ctx.parsed — ParseResult с полями:
        - packet: Packet (распарсенный пакет)
        - errors: list[str] (ошибки парсинга)
        - warnings: list[str] (предупреждения)
        - extra: dict (дополнительные поля: service, tid, imei, imsi)
    """

    def __init__(self, session_mgr: SessionManager) -> None:
        self._session_mgr = session_mgr

    async def __call__(self, ctx: PacketContext) -> None:
        """Распарсить EGTS-пакет и заполнить ctx.parsed.

        При ошибке парсинга:
        - ctx.terminated = True
        - ctx.errors.append(...)
        """
        raw = ctx.raw

        # Получить connection через публичный метод SessionManager
        conn = self._session_mgr.get_session(ctx.connection_id)
        if conn is None:
            logger.warning("Parse: connection %s not found", ctx.connection_id)
            ctx.errors.append(f"Connection {ctx.connection_id} not found")
            ctx.terminated = True
            return

        protocol = conn.protocol
        if protocol is None:
            logger.warning("Parse: protocol is None for connection %s", ctx.connection_id)
            ctx.errors.append("Protocol not available")
            ctx.terminated = True
            return

        # Вызов парсинга
        try:
            parse_result = protocol.parse_packet(raw)
        except Exception as e:
            logger.warning("Parse exception for connection %s: %s", ctx.connection_id, e)
            ctx.errors.append(f"Parse exception: {e!s}")
            ctx.terminated = True
            return

        # Проверка успешности парсинга
        if not parse_result.is_success:
            # Полный провал — пакет не распарсен
            error_msg = "; ".join(parse_result.errors) if parse_result.errors else "Unknown parse error"
            logger.warning(
                "Parse failed for connection %s: %s", ctx.connection_id, error_msg
            )
            ctx.errors.extend(parse_result.errors)
            ctx.terminated = True
            return

        # Частичный успех или полный успех — сохраняем ParseResult
        ctx.parsed = parse_result
        logger.debug(
            "Parse successful for connection %s (packet_type=%s)",
            ctx.connection_id,
            parse_result.packet.packet_type if parse_result.packet else None,
        )


# =============================================================================
# EventEmitMiddleware
# =============================================================================


class EventEmitMiddleware:
    """Публикация события packet.processed после обработки.

    Всегда эмитит событие packet.processed — даже при terminated=True
    или ошибках (для полного логирования 100% пакетов).

    Данные события:
        - ctx: PacketContext (полный контекст обработки)
        - connection_id: идентификатор подключения
        - channel: канал получения (tcp/sms)
        - parsed: распарсенный пакет (или None)
        - crc_valid: флаг валидности CRC
        - is_duplicate: флаг дубликата
        - terminated: флаг прерывания цепочки
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def __call__(self, ctx: PacketContext) -> None:
        """Эмитить событие packet.processed с полным контекстом."""
        event_data = {
            "ctx": ctx,
            "connection_id": ctx.connection_id,
            "channel": ctx.channel,
            "parsed": ctx.parsed,
            "crc_valid": ctx.crc_valid,
            "is_duplicate": ctx.is_duplicate,
            "terminated": ctx.terminated,
        }

        await self._bus.emit("packet.processed", event_data)
        logger.debug(
            "Emitted packet.processed for connection %s (terminated=%s, crc_valid=%s)",
            ctx.connection_id,
            ctx.terminated,
            ctx.crc_valid,
        )
