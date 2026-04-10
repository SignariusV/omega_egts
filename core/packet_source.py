"""ReplaySource — загрузка JSONL-логов и повторный прогон через pipeline.

Загружает записи из JSONL-файла (формат LogManager), конвертирует hex → bytes
и прогоняет каждый пакет через PacketPipeline (если pipeline передан).
После обработки эмитит событие packet.processed для каждого пакета.

Пример использования::

    source = ReplaySource(bus=event_bus, log_file=Path("logs/2026-04-09.jsonl"),
                          pipeline=pipeline, skip_duplicates=True)
    result = await source.replay()
    # result: {"processed": 150, "skipped_duplicates": 12, "errors": []}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.event_bus import EventBus
    from core.pipeline import PacketPipeline

logger = logging.getLogger(__name__)


def _hex_to_bytes(hex_str: str | None) -> bytes:
    """Конвертировать hex-строку в bytes.

    Args:
        hex_str: Hex-строка (с пробелами или без), может быть None или пустой.

    Returns:
        Bytes-представление или пустые bytes.
    """
    if not hex_str:
        return b""
    cleaned = hex_str.replace(" ", "")
    return bytes.fromhex(cleaned)


class ReplaySource:
    """Загрузка и повторная обработка пакетов из JSONL-лога.

    Args:
        bus: EventBus для эмиссии событий packet.processed.
        log_file: Путь к JSONL-файлу с логами.
        pipeline: PacketPipeline для обработки (None — быстрый режим, без pipeline).
        skip_duplicates: Пропускать дубликаты из лога (по умолчанию True).
    """

    def __init__(
        self,
        bus: EventBus,
        log_file: Path | str,
        pipeline: PacketPipeline | None = None,
        skip_duplicates: bool = True,
    ) -> None:
        self._bus = bus
        self._log_file = Path(log_file)
        self._pipeline = pipeline
        self._skip_duplicates = skip_duplicates

    async def load(self) -> list[dict[str, Any]]:
        """Загрузить записи из JSONL-файла.

        Возвращает только записи с log_type='packet'.
        Остальные записи (connection, scenario) пропускаются.

        Returns:
            Список словарей с данными пакетов.

        Raises:
            FileNotFoundError: Если файл не найден.
        """
        if not self._log_file.exists():
            raise FileNotFoundError(f"Log file not found: {self._log_file}")

        records: list[dict[str, Any]] = []
        with open(self._log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if record.get("log_type") == "packet":
                        records.append(record)
                except json.JSONDecodeError as exc:
                    logger.warning("ReplaySource: пропуск строки JSON: %s", exc)

        logger.info("ReplaySource: загружено %d записей из %s", len(records), self._log_file)
        return records

    async def replay(self) -> dict[str, Any]:
        """Повторная обработка пакетов через pipeline.

        Для каждой записи:
        1. Конвертирует hex → bytes
        2. Если pipeline задан — прогоняет через pipeline.process()
        3. Эмитит packet.processed

        При skip_duplicates=True — записи с is_duplicate=True пропускаются.

        Returns:
            Словарь со статистикой:
                - processed: количество обработанных пакетов
                - skipped_duplicates: количество пропущенных дубликатов
                - errors: список ошибок обработки
        """
        records = await self.load()

        processed = 0
        skipped_duplicates = 0
        errors: list[str] = []

        for record in records:
            if self._skip_duplicates and record.get("is_duplicate"):
                skipped_duplicates += 1
                logger.debug("ReplaySource: пропуск дубликата %s", record.get("connection_id"))
                continue

            try:
                raw_bytes = _hex_to_bytes(record.get("hex"))
            except ValueError as exc:
                error_msg = f"Некорректный hex в записи: {exc!s}"
                errors.append(error_msg)
                logger.warning("ReplaySource: %s", error_msg)
                continue

            try:
                # Создаём контекст единообразно, pipeline — опционально
                from core.pipeline import PacketContext

                ctx = PacketContext(
                    raw=raw_bytes,
                    connection_id=record.get("connection_id") or "",
                    channel=record.get("channel", "tcp"),
                    crc_valid=record.get("crc_valid", False),
                    is_duplicate=False,
                    terminated=record.get("terminated", False),
                )

                if self._pipeline is not None:
                    ctx = await self._pipeline.process(ctx)

                event_data = {
                    "ctx": ctx,
                    "connection_id": ctx.connection_id,
                    "channel": ctx.channel,
                    "parsed": ctx.parsed if self._pipeline else record.get("parsed"),
                    "crc_valid": ctx.crc_valid,
                    "is_duplicate": ctx.is_duplicate,
                    "terminated": ctx.terminated,
                }

                await self._bus.emit("packet.processed", event_data)
                processed += 1

            except Exception as exc:
                error_msg = f"Ошибка replay: {exc!s}"
                errors.append(error_msg)
                logger.warning("ReplaySource: %s", error_msg)

        result = {
            "processed": processed,
            "skipped_duplicates": skipped_duplicates,
            "errors": errors,
        }

        logger.info(
            "ReplaySource: завершено — processed=%d, skipped=%d, errors=%d",
            processed,
            skipped_duplicates,
            len(errors),
        )
        return result
