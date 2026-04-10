"""Тесты Export — выгрузка результатов тестирования в CSV/JSON.

Проверяет:
- Экспорт логов в CSV
- Экспорт логов в JSON
- Экспорт результатов сценария
- Фильтрация по дате и типу записи
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ====================================================================
# Фикстуры
# ====================================================================


@pytest.fixture
def sample_log_entries():
    """Пример записей лога (формат LogManager)."""
    return [
        {
            "log_type": "packet",
            "timestamp": 1000.0,
            "connection_id": "conn-1",
            "channel": "tcp",
            "hex": "010001000000A1B2C3D4",
            "parsed": {"packet_type": 1, "packet_id": 5},
            "crc_valid": True,
            "is_duplicate": False,
            "terminated": False,
            "errors": [],
        },
        {
            "log_type": "packet",
            "timestamp": 1001.0,
            "connection_id": "conn-1",
            "channel": "tcp",
            "hex": "020001000000A1B2C3D5",
            "parsed": None,
            "crc_valid": False,
            "is_duplicate": False,
            "terminated": True,
            "errors": ["CRC error"],
        },
        {
            "log_type": "connection",
            "timestamp": 1002.0,
            "connection_id": "conn-1",
            "state": "connected",
            "prev_state": "disconnected",
        },
        {
            "log_type": "scenario",
            "timestamp": 1003.0,
            "scenario_name": "Авторизация",
            "step_name": "expect_term_identity",
            "step_type": "expect",
            "result": "PASS",
            "details": {"matched": True},
        },
    ]


@pytest.fixture
def log_dir_with_entries(tmp_path, sample_log_entries):
    """Директория с JSONL-файлом LogManager."""
    from datetime import date

    today = date.today().isoformat()
    log_file = tmp_path / f"{today}.jsonl"
    with open(log_file, "w", encoding="utf-8") as f:
        for entry in sample_log_entries:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return tmp_path


# ====================================================================
# Тесты экспорта в CSV
# ====================================================================


class TestExportCSV:
    """Тесты экспорта в CSV."""

    def test_export_csv_creates_file(self, log_dir_with_entries, tmp_path):
        """export_csv() создаёт CSV-файл."""
        from core.export import export_csv

        output = tmp_path / "report.csv"
        result = export_csv(log_dir=log_dir_with_entries, output_path=output)

        assert output.exists()
        assert output.stat().st_size > 0
        assert isinstance(result, dict)
        assert result["exported"] == 4

    def test_export_csv_content(self, log_dir_with_entries, tmp_path):
        """CSV содержит данные из всех записей."""
        from core.export import export_csv

        output = tmp_path / "report.csv"
        export_csv(log_dir=log_dir_with_entries, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # 4 записи
        assert len(rows) == 4

        # Проверяем колонки
        assert "log_type" in rows[0]
        assert "timestamp" in rows[0]

    def test_export_csv_filters_by_type(self, log_dir_with_entries, tmp_path):
        """Фильтр log_type оставляет только нужные записи."""
        from core.export import export_csv

        output = tmp_path / "packets.csv"
        export_csv(log_dir=log_dir_with_entries, output_path=output, log_type_filter="packet")

        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Только 2 packet-записи
        assert len(rows) == 2
        assert all(r["log_type"] == "packet" for r in rows)

    def test_export_csv_filters_by_scenario(self, log_dir_with_entries, tmp_path):
        """Фильтр scenario_name оставляет только записи сценария."""
        from core.export import export_csv

        output = tmp_path / "scenario.csv"
        export_csv(
            log_dir=log_dir_with_entries, output_path=output,
            scenario_name_filter="Авторизация",
        )

        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["scenario_name"] == "Авторизация"

    def test_export_csv_sorts_by_timestamp(self, log_dir_with_entries, tmp_path):
        """Записи сортируются по timestamp."""
        from core.export import export_csv

        output = tmp_path / "sorted.csv"
        export_csv(log_dir=log_dir_with_entries, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        timestamps = [float(r["timestamp"]) for r in rows]
        assert timestamps == sorted(timestamps)

    def test_export_csv_empty_log_dir(self, tmp_path):
        """Пустая директория — пустой CSV с заголовками."""
        from core.export import export_csv

        output = tmp_path / "empty.csv"
        result = export_csv(log_dir=tmp_path, output_path=output)

        assert output.exists()
        assert isinstance(result, dict)
        assert result["exported"] == 0
        # Только заголовок
        with open(output, "r", encoding="utf-8") as f:
            content = f.read().strip()
        assert len(content.split("\n")) == 1  # header only

    def test_export_csv_no_matching_entries(self, log_dir_with_entries, tmp_path):
        """Нет записей по фильтру — пустой CSV."""
        from core.export import export_csv

        output = tmp_path / "none.csv"
        export_csv(
            log_dir=log_dir_with_entries, output_path=output,
            scenario_name_filter="Несуществующий",
        )

        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0


# ====================================================================
# Тесты экспорта в JSON
# ====================================================================


class TestExportJSON:
    """Тесты экспорта в JSON."""

    def test_export_json_creates_file(self, log_dir_with_entries, tmp_path):
        """export_json() создаёт JSON-файл."""
        from core.export import export_json

        output = tmp_path / "report.json"
        export_json(log_dir=log_dir_with_entries, output_path=output)

        assert output.exists()
        assert output.stat().st_size > 0

    def test_export_json_content(self, log_dir_with_entries, tmp_path):
        """JSON содержит массив записей."""
        from core.export import export_json

        output = tmp_path / "report.json"
        export_json(log_dir=log_dir_with_entries, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert "entries" in data
        assert len(data["entries"]) == 4

    def test_export_json_summary(self, log_dir_with_entries, tmp_path):
        """JSON содержит сводку: total, by_type."""
        from core.export import export_json

        output = tmp_path / "report.json"
        export_json(log_dir=log_dir_with_entries, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = data["summary"]
        assert summary["total"] == 4
        assert "by_type" in summary
        assert summary["by_type"]["packet"] == 2
        assert summary["by_type"]["connection"] == 1
        assert summary["by_type"]["scenario"] == 1

    def test_export_json_filters(self, log_dir_with_entries, tmp_path):
        """Фильтры работают для JSON."""
        from core.export import export_json

        output = tmp_path / "packets.json"
        export_json(log_dir=log_dir_with_entries, output_path=output, log_type_filter="packet")

        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["entries"]) == 2
        assert data["summary"]["total"] == 2

    def test_export_json_pretty_print(self, log_dir_with_entries, tmp_path):
        """JSON отформатирован с отступами."""
        from core.export import export_json

        output = tmp_path / "pretty.json"
        export_json(log_dir=log_dir_with_entries, output_path=output)

        content = output.read_text(encoding="utf-8")
        # Должен содержать переносы строк (indent=2)
        assert "\n" in content
        assert "  " in content

    def test_export_json_empty_log_dir(self, tmp_path):
        """Пустая директория — пустой массив."""
        from core.export import export_json

        output = tmp_path / "empty.json"
        export_json(log_dir=tmp_path, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["entries"] == []
        assert data["summary"]["total"] == 0


# ====================================================================
# Тесты экспорта результатов сценария
# ====================================================================


class TestExportScenarioResults:
    """Тесты экспорта результатов сценариев."""

    @pytest.fixture
    def scenario_results(self):
        """Результаты выполнения сценария."""
        return {
            "scenario_name": "Авторизация",
            "gost_version": "2015",
            "start_time": 1000.0,
            "end_time": 1050.0,
            "overall_result": "PASS",
            "steps": [
                {
                    "step_name": "expect_term_identity",
                    "step_type": "expect",
                    "result": "PASS",
                    "duration": 2.0,
                    "details": {"packet_id": 1},
                },
                {
                    "step_name": "send_auth_params",
                    "step_type": "send",
                    "result": "PASS",
                    "duration": 0.5,
                    "details": {},
                },
                {
                    "step_name": "expect_result_code",
                    "step_type": "expect",
                    "result": "FAIL",
                    "duration": 6.0,
                    "details": {"error": "timeout"},
                },
            ],
        }

    def test_export_scenario_csv(self, scenario_results, tmp_path):
        """Экспорт результатов сценария в CSV."""
        from core.export import export_scenario_results_csv

        output = tmp_path / "scenario.csv"
        export_scenario_results_csv(result=scenario_results, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 3  # 3 шага
        assert rows[0]["step_name"] == "expect_term_identity"
        assert rows[2]["result"] == "FAIL"

    def test_export_scenario_json(self, scenario_results, tmp_path):
        """Экспорт результатов сценария в JSON."""
        from core.export import export_scenario_results_json

        output = tmp_path / "scenario.json"
        export_scenario_results_json(result=scenario_results, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["scenario_name"] == "Авторизация"
        assert data["overall_result"] == "PASS"
        assert len(data["steps"]) == 3

    def test_export_scenario_csv_no_steps(self, tmp_path):
        """Сценарий без шагов — только заголовок."""
        from core.export import export_scenario_results_csv

        result = {
            "scenario_name": "Пустой",
            "gost_version": "2015",
            "overall_result": "PASS",
            "steps": [],
        }
        output = tmp_path / "empty.csv"
        export_scenario_results_csv(result=result, output_path=output)

        with open(output, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0

    def test_export_handles_malformed_jsonl(self, tmp_path):
        """Битые JSONL-строки пропускаются."""
        path = tmp_path / "bad.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"log_type": "packet", "timestamp": 1}\n')
            f.write('not json\n')
            f.write('{"log_type": "packet", "timestamp": 2}\n')

        from core.export import export_json

        output = tmp_path / "report.json"
        data = export_json(log_dir=tmp_path, output_path=output)

        assert data["summary"]["total"] == 2

    def test_export_json_with_scenario_filter_no_match(self, log_dir_with_entries, tmp_path):
        """Фильтр scenario_name без совпадений — пустой результат."""
        from core.export import export_json

        output = tmp_path / "none.json"
        data = export_json(
            log_dir=log_dir_with_entries, output_path=output,
            scenario_name_filter="Несуществующий",
        )

        assert data["summary"]["total"] == 0
        assert data["entries"] == []
