"""Export — выгрузка результатов тестирования в CSV/JSON.

Поддерживаемые форматы:
- CSV — таблица записей лога (для открытия в Excel)
- JSON — структурированные данные со сводкой

Источники данных:
- JSONL-файлы LogManager (YYYY-MM-DD.jsonl)
- Результаты выполнения сценариев (dict)

Пример использования::

    # Экспорт всех логов в CSV
    export_csv(log_dir=Path("logs/"), output_path=Path("report.csv"))

    # Экспорт только packet-записей в JSON
    export_json(log_dir=Path("logs/"), output_path=Path("report.json"),
                log_type_filter="packet")

    # Экспорт результатов сценария
    export_scenario_results_csv(result=scenario_result,
                                output_path=Path("scenario.csv"))
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Поля для CSV-экспорта логов
_LOG_CSV_FIELDS = [
    "log_type", "timestamp", "connection_id", "channel",
    "crc_valid", "is_duplicate", "terminated", "errors",
    "hex", "parsed",
    "state", "prev_state",
    "scenario_name", "step_name", "step_type", "result", "details",
]

# Поля для CSV-экспорта шагов сценария
_SCENARIO_CSV_FIELDS = [
    "step_name", "step_type", "result", "duration", "details", "error",
]


# ====================================================================
# Внутренние утилиты
# ====================================================================


def _load_all_entries(log_dir: Path) -> list[dict[str, Any]]:
    """Загрузить все записи из JSONL-файлов в директории.

    Читает все файлы *.jsonl, парсит JSON-строки,
    объединяет в единый список.

    Args:
        log_dir: Директория с JSONL-файлами.

    Returns:
        Список записей лога.
    """
    entries: list[dict[str, Any]] = []
    for jsonl_file in sorted(log_dir.glob("*.jsonl")):
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        logger.warning("Export: пропуск битой строки в %s", jsonl_file)
        except OSError as exc:
            logger.warning("Export: ошибка чтения %s: %s", jsonl_file, exc)

    return entries


def _flatten_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Подготовить записи для CSV — преобразовать вложенные структуры в строки."""
    flat: dict[str, Any] = {}
    for key, value in entry.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value, ensure_ascii=False, default=str)
        else:
            flat[key] = value
    return flat


# ====================================================================
# Экспорт логов
# ====================================================================


def _filter_and_sort(
    entries: list[dict[str, Any]],
    *,
    log_type_filter: str | None = None,
    scenario_name_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Отфильтровать и отсортировать записи по timestamp.

    Args:
        entries: Список записей лога.
        log_type_filter: Фильтр по типу записи.
        scenario_name_filter: Фильтр по имени сценария.

    Returns:
        Отфильтрованный и отсортированный список.
    """
    if log_type_filter is not None:
        entries = [e for e in entries if e.get("log_type") == log_type_filter]
    if scenario_name_filter is not None:
        entries = [
            e for e in entries
            if e.get("scenario_name") == scenario_name_filter
        ]
    entries.sort(key=lambda e: e.get("timestamp", 0))
    return entries


def export_csv(
    log_dir: Path | str,
    output_path: Path | str,
    *,
    log_type_filter: str | None = None,
    scenario_name_filter: str | None = None,
) -> dict[str, Any]:
    """Экспортировать логи в CSV.

    Args:
        log_dir: Директория с JSONL-файлами LogManager.
        output_path: Путь к выходному CSV-файлу.
        log_type_filter: Фильтр по типу записи (packet/connection/scenario).
        scenario_name_filter: Фильтр по имени сценария.

    Returns:
        Количество записанных записей.
    """
    log_dir = Path(log_dir)
    output_path = Path(output_path)

    entries = _load_all_entries(log_dir)
    entries = _filter_and_sort(
        entries,
        log_type_filter=log_type_filter,
        scenario_name_filter=scenario_name_filter,
    )

    if not entries:
        logger.warning("Export CSV: нет записей для экспорта в %s", log_dir)

    # Запись CSV
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_LOG_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for entry in entries:
            writer.writerow(_flatten_entry(entry))

    logger.info("Export CSV: записано %d записей в %s", len(entries), output_path)
    return {"exported": len(entries), "output": str(output_path)}


def export_json(
    log_dir: Path | str,
    output_path: Path | str,
    *,
    log_type_filter: str | None = None,
    scenario_name_filter: str | None = None,
) -> dict[str, Any]:
    """Экспортировать логи в JSON со сводкой.

    Args:
        log_dir: Директория с JSONL-файлами LogManager.
        output_path: Путь к выходному JSON-файлу.
        log_type_filter: Фильтр по типу записи.
        scenario_name_filter: Фильтр по имени сценария.

    Returns:
        Словарь с данными (entries + summary).
    """
    log_dir = Path(log_dir)
    output_path = Path(output_path)

    entries = _load_all_entries(log_dir)
    entries = _filter_and_sort(
        entries,
        log_type_filter=log_type_filter,
        scenario_name_filter=scenario_name_filter,
    )

    # Сводка
    by_type: dict[str, int] = {}
    for entry in entries:
        lt = entry.get("log_type", "unknown")
        by_type[lt] = by_type.get(lt, 0) + 1

    summary = {
        "total": len(entries),
        "by_type": by_type,
    }

    data = {
        "entries": entries,
        "summary": summary,
    }

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info("Export JSON: записано %d записей в %s", len(entries), output_path)
    return data


# ====================================================================
# Экспорт результатов сценария
# ====================================================================


def export_scenario_results_csv(
    result: dict[str, Any],
    output_path: Path | str,
) -> int:
    """Экспортировать результаты выполнения сценария в CSV.

    Каждая строка — один шаг сценария.

    Args:
        result: Словарь с результатами сценария
            (scenario_name, gost_version, overall_result, steps).
        output_path: Путь к выходному CSV-файлу.

    Returns:
        Количество записанных шагов.
    """
    output_path = Path(output_path)
    steps = result.get("steps", [])

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_SCENARIO_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()

        for step in steps:
            row = _flatten_entry(step)
            writer.writerow(row)

    logger.info("Export scenario CSV: записано %d шагов в %s", len(steps), output_path)
    return len(steps)


def export_scenario_results_json(
    result: dict[str, Any],
    output_path: Path | str,
) -> None:
    """Экспортировать результаты выполнения сценария в JSON.

    Args:
        result: Словарь с результатами сценария.
        output_path: Путь к выходному JSON-файлу.
    """
    output_path = Path(output_path)

    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info("Export scenario JSON: сохранено в %s", output_path)
