"""LogManager — подписчик на события, логирует 100% пакетов.

Подписывается на 3 события EventBus:
- ``packet.processed`` — каждый обработанный пакет (hex + parsed)
- ``connection.changed`` — смена состояния подключения
- ``scenario.step`` — результаты шагов сценария

Записывает логи в JSONL-файлы (JSON Lines) с именем ``YYYY-MM-DD.jsonl``.
Буферизация с сортировкой по timestamp решает проблему CR-002
(нарушение порядка при parallel-обработке EventBus).

Пример использования::

    lm = LogManager(bus=event_bus, log_dir=Path("./logs"))
    # ... работа системы ...
    await lm.flush()  # записать буфер на диск
    lm.stop()         # отписаться от событий
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.event_bus import EventBus

logger = logging.getLogger(__name__)


class LogManager:
    """Подписчик на события, логирует 100% пакетов.

    Буферизует записи и сбрасывает на диск по запросу (flush).
    Записи сортируются по timestamp при записи — порядок гарантирован
    даже при parallel-обработке событий (решение CR-002).

    Args:
        bus: EventBus для подписки на события
        log_dir: Директория для файлов логов
    """

    def __init__(self, bus: EventBus, log_dir: Path) -> None:
        self._bus = bus
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[dict[str, Any]] = []

        # Подписка на события
        self._bus.on("packet.processed", self._on_packet_processed)
        self._bus.on("connection.changed", self._on_connection_changed)
        self._bus.on("scenario.step", self._on_scenario_step)

        logger.info("LogManager инициализирован, log_dir=%s", self._log_dir)

    def stop(self) -> None:
        """Отписаться от событий EventBus."""
        self._bus.off("packet.processed", self._on_packet_processed)
        self._bus.off("connection.changed", self._on_connection_changed)
        self._bus.off("scenario.step", self._on_scenario_step)
        logger.info("LogManager: отписался от событий")

    async def flush(self) -> None:
        """Сбросить буфер на диск.

        Записи сортируются по timestamp перед записью (CR-002).
        Файл именуется по дате: ``YYYY-MM-DD.jsonl``.
        Если файл уже существует — данные дописываются.
        """
        if not self._buffer:
            return

        # Сортировка по timestamp (решение CR-002)
        self._buffer.sort(key=lambda entry: entry.get("_sort_ts", 0))

        # Файл по дате
        today_str = date.today().isoformat()  # YYYY-MM-DD
        log_file = self._log_dir / f"{today_str}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            for entry in self._buffer:
                # Убираем служебное поле _sort_ts перед записью
                entry.pop("_sort_ts", None)
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

        count = len(self._buffer)
        self._buffer.clear()
        logger.info("LogManager: записано %d записей в %s", count, log_file)

    # ====================================================================
    # Обработчики событий
    # ====================================================================

    async def _on_packet_processed(self, data: dict[str, Any]) -> None:
        """Обработать событие packet.processed.

        Логирует: hex пакета, parsed данные, connection_id, channel,
        crc_valid, is_duplicate, terminated, errors.
        """
        from core.pipeline import PacketContext

        ctx: PacketContext | None = data.get("ctx")
        if ctx is None:
            return

        raw_hex = ctx.raw.hex(" ").upper() if ctx.raw else ""

        parsed_data: dict[str, Any] | None = None
        if ctx.parsed is not None:
            # Извлекаем service, tid и т.д. из parsed
            if hasattr(ctx.parsed, "extra"):
                parsed_data = getattr(ctx.parsed, "extra", None)
            if parsed_data is None and hasattr(ctx.parsed, "packet"):
                packet = getattr(ctx.parsed, "packet", None)
                if packet is not None:
                    parsed_data = {
                        "packet_type": getattr(packet, "packet_type", None),
                        "packet_id": getattr(packet, "packet_id", None),
                    }

        entry: dict[str, Any] = {
            "log_type": "packet",
            "timestamp": time.time(),
            "_sort_ts": ctx.timestamp,
            "connection_id": ctx.connection_id,
            "channel": ctx.channel,
            "hex": raw_hex,
            "parsed": parsed_data,
            "crc_valid": ctx.crc_valid,
            "is_duplicate": ctx.is_duplicate,
            "terminated": ctx.terminated,
            "errors": list(ctx.errors) if ctx.errors else [],
        }

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
            "timestamp": time.time(),
            "_sort_ts": data.get("timestamp", time.monotonic()),
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
            "timestamp": time.time(),
            "_sort_ts": data.get("timestamp", time.monotonic()),
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
