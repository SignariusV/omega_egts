"""LogManager — подписчик на события, логирует 100% пакетов.

Подписывается на 3 события EventBus:
- ``packet.processed`` — каждый обработанный пакет (hex + parsed)
- ``connection.changed`` — смена состояния подключения
- ``scenario.step`` — результаты шагов сценария

Записывает логи в JSONL-файлы (JSON Lines) с именем ``YYYY-MM-DD.jsonl``.
Буферизация с сортировкой по timestamp решает проблему CR-002
(нарушение порядка при parallel-обработке EventBus).

Автоматический сброс буфера:
- По порогу (``flush_batch_size`` записей)
- По интервалу (``flush_interval`` секунд) — фоновая задача

Пример использования::

    lm = LogManager(bus=event_bus, log_dir=Path("./logs"))
    # ... работа системы (фоновый авто-sflush работает автоматически) ...
    await lm.stop()  # сбрасывает буфер и отписывается
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.event_bus import EventBus

logger = logging.getLogger(__name__)

# Параметры автосброса по умолчанию
_DEFAULT_FLUSH_INTERVAL = 5.0  # секунд
_DEFAULT_FLUSH_BATCH_SIZE = 1000  # записей


class LogManager:
    """Подписчик на события, логирует 100% пакетов.

    Буферизует записи и сбрасывает на диск по запросу (flush)
    или автоматически (по порогу и интервалу).
    Записи сортируются по timestamp при записи — порядок гарантирован
    даже при parallel-обработке событий (решение CR-002).

    Args:
        bus: EventBus для подписки на события
        log_dir: Директория для файлов логов
        flush_interval: Интервал автосброса в секундах (по умолчанию 5.0)
        flush_batch_size: Порог записей для автосброса (по умолчанию 1000)
    """

    def __init__(
        self,
        bus: EventBus,
        log_dir: Path,
        *,
        flush_interval: float = _DEFAULT_FLUSH_INTERVAL,
        flush_batch_size: int = _DEFAULT_FLUSH_BATCH_SIZE,
    ) -> None:
        self._bus = bus
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[dict[str, Any]] = []
        self._flush_interval = flush_interval
        self._flush_batch_size = flush_batch_size
        self._running = False
        self._flush_task: asyncio.Task[None] | None = None

        # Подписка на события
        self._bus.on("packet.processed", self._on_packet_processed)
        self._bus.on("connection.changed", self._on_connection_changed)
        self._bus.on("scenario.step", self._on_scenario_step)

        # Запуск фоновой задачи автосброса
        self._running = True
        self._flush_task = asyncio.create_task(self._auto_flush_loop())

        logger.info(
            "LogManager инициализирован, log_dir=%s, flush_interval=%.1f, batch_size=%d",
            self._log_dir,
            self._flush_interval,
            self._flush_batch_size,
        )

    async def stop(self) -> None:
        """Остановить LogManager: сбросить буфер и отписаться от событий."""
        # Сбросить оставшиеся логи
        await self.flush()

        # Остановить фоновую задачу
        self._running = False
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Отписаться от событий
        self._bus.off("packet.processed", self._on_packet_processed)
        self._bus.off("connection.changed", self._on_connection_changed)
        self._bus.off("scenario.step", self._on_scenario_step)
        logger.info("LogManager: остановлен, буфер сброшен")

    async def flush(self) -> None:
        """Сбросить буфер на диск.

        Записи сортируются по timestamp перед записью (CR-002).
        Файл именуется по дате: ``YYYY-MM-DD.jsonl``.
        Если файл уже существует — данные дописываются.
        """
        if not self._buffer:
            return

        # Сортировка по timestamp (решение CR-002)
        self._buffer.sort(key=lambda entry: entry.get("timestamp", 0))

        # Файл по дате
        today_str = date.today().isoformat()  # YYYY-MM-DD
        log_file = self._log_dir / f"{today_str}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            for entry in self._buffer:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

        count = len(self._buffer)
        self._buffer.clear()
        logger.debug("LogManager: записано %d записей в %s", count, log_file)

    async def _auto_flush_loop(self) -> None:
        """Фоновая задача: автосброс буфера по интервалу или порогу.

        Проверяет буфер каждые ``flush_interval`` секунд.
        Сбрасывает если количество записей >= ``flush_batch_size``.
        """
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                if len(self._buffer) >= self._flush_batch_size:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("LogManager: ошибка в цикле автосброса")

    # ====================================================================
    # Обработчики событий
    # ====================================================================

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику буферизованных записей.

        Возвращает:
            Словарь с количеством записей по типам.
        """
        stats: dict[str, int] = {
            "packets": 0,
            "connections": 0,
            "scenarios": 0,
            "total": len(self._buffer),
        }
        for entry in self._buffer:
            log_type = entry.get("log_type", "")
            if log_type == "packet":
                stats["packets"] += 1
            elif log_type == "connection":
                stats["connections"] += 1
            elif log_type == "scenario":
                stats["scenarios"] += 1
        return stats

    async def _on_packet_processed(self, data: dict[str, Any]) -> None:
        """Обработать событие packet.processed.

        Логирует: hex пакета, parsed данные, connection_id, channel,
        crc_valid, is_duplicate, terminated, errors.
        """
        from core.pipeline import PacketContext

        ctx: PacketContext | None = data.get("ctx")
        if ctx is None:
            return

        raw_hex = ctx.raw.hex().upper() if ctx.raw else ""

        # Извлечение parsed данных: поддерживаем ParseResult и dict
        parsed_data: dict[str, Any] | None = None
        if ctx.parsed is not None:
            parsed_data = self._extract_parsed_data(ctx.parsed)

        entry: dict[str, Any] = {
            "log_type": "packet",
            "timestamp": ctx.timestamp,
            "connection_id": ctx.connection_id,
            "channel": ctx.channel,
            "hex": raw_hex,
            "parsed": parsed_data,
            "crc_valid": ctx.crc_valid,
            "is_duplicate": ctx.is_duplicate,
            "terminated": ctx.terminated,
            "errors": list(ctx.errors) if ctx.errors else [],
        }

        # RESPONSE (если сформирован)
        if ctx.response_data is not None:
            entry["response_hex"] = ctx.response_data.hex().upper()

        self._buffer.append(entry)
        logger.debug(
            "LogManager: packet conn=%s channel=%s crc=%s dup=%s",
            ctx.connection_id,
            ctx.channel,
            ctx.crc_valid,
            ctx.is_duplicate,
        )

    async def _on_connection_changed(self, data: dict[str, Any]) -> None:
        """Обработать событие connection.changed.

        Логирует: connection_id, state, prev_state.
        """
        entry: dict[str, Any] = {
            "log_type": "connection",
            "timestamp": data.get("timestamp", time.monotonic()),
            "connection_id": data.get("connection_id"),
            "state": data.get("state"),
            "prev_state": data.get("prev_state"),
        }

        self._buffer.append(entry)
        logger.debug(
            "LogManager: connection %s %s -> %s",
            entry["connection_id"],
            entry["prev_state"],
            entry["state"],
        )

    async def _on_scenario_step(self, data: dict[str, Any]) -> None:
        """Обработать событие scenario.step.

        Логирует: scenario_name, step_name, step_type, result, details.
        """
        entry: dict[str, Any] = {
            "log_type": "scenario",
            "timestamp": data.get("timestamp", time.monotonic()),
            "scenario_name": data.get("scenario_name"),
            "step_name": data.get("step_name"),
            "step_type": data.get("step_type"),
            "result": data.get("result"),
            "details": data.get("details"),
        }

        self._buffer.append(entry)
        logger.debug(
            "LogManager: scenario %s step=%s result=%s",
            entry["scenario_name"],
            entry["step_name"],
            entry["result"],
        )

    @staticmethod
    def _extract_parsed_data(parsed: object) -> dict[str, Any] | None:
        """Извлечь данные из ParseResult для логирования.

        Поддерживает:
        - ParseResult с полями packet, extra
        - dict (legacy формат из SessionManager)
        """
        # dict — legacy формат из SessionManager._on_packet_processed
        if isinstance(parsed, dict):
            return parsed

        result: dict[str, Any] = {}

        # Извлечение packet info
        if hasattr(parsed, "packet") and parsed.packet is not None:
            packet = parsed.packet
            result["packet_type"] = getattr(packet, "packet_type", None)
            result["packet_id"] = getattr(packet, "packet_id", None)

        # Извлечение данных из подзаписей (замена extra)
        if hasattr(parsed, "records"):
            for rec in getattr(parsed, "records", []):
                for sr in getattr(rec, "subrecords", []):
                    if isinstance(sr.data, dict):
                        result.update(sr.data)

        return result if result else None
