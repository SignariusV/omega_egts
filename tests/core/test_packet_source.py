"""Тесты ReplaySource — загрузка JSONL-логов и повторный прогон через pipeline.

Проверяет:
- Загрузка записей из JSONL (hex → bytes)
- Прогон через pipeline (если pipeline передан)
- Пропуск дубликатов (skip_duplicates)
- Эмит событий packet.processed
- Replay без pipeline (быстрый режим — только эмиссия)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# ====================================================================
# Фикстуры
# ====================================================================


@pytest.fixture
def mock_bus():
    """EventBus с замоканными методами."""
    bus = MagicMock()
    bus.emit = AsyncMock()
    bus.on = MagicMock()
    bus.off = MagicMock()
    return bus


@pytest.fixture
def sample_jsonl_lines():
    """Пример записей JSONL-лога (формат LogManager)."""
    return [
        {
            "log_type": "packet",
            "timestamp": 1000.0,
            "connection_id": "conn-1",
            "channel": "tcp",
            "hex": "010001000000A1B2C3D4",
            "parsed": {"packet_type": "EGTS_TP_RESPONSE", "packet_id": 1},
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
            "parsed": {"packet_type": "EGTS_TP_RESPONSE", "packet_id": 2},
            "crc_valid": True,
            "is_duplicate": False,
            "terminated": False,
            "errors": [],
        },
    ]


@pytest.fixture
def jsonl_file(tmp_path, sample_jsonl_lines):
    """JSONL-файл с тестовыми данными."""
    path = tmp_path / "test_log.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for line in sample_jsonl_lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return path


@pytest.fixture
def mock_pipeline():
    """Pipeline с замоканным process."""
    pipeline = MagicMock()
    pipeline.process = AsyncMock(side_effect=lambda ctx: ctx)
    return pipeline


# ====================================================================
# Тесты загрузки (без pipeline)
# ====================================================================


class TestReplaySourceLoad:
    """Тесты загрузки записей из JSONL."""

    @pytest.mark.asyncio
    async def test_load_records_from_jsonl(self, jsonl_file, mock_bus):
        """ReplaySource загружает все записи из JSONL-файла."""
        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=jsonl_file)
        records = await source.load()

        assert len(records) == 2
        assert records[0]["connection_id"] == "conn-1"
        assert records[1]["timestamp"] == pytest.approx(1001.0)

    @pytest.mark.asyncio
    async def test_load_empty_file(self, tmp_path, mock_bus):
        """Пустой JSONL-файл → пустой список."""
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")

        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=path)
        records = await source.load()

        assert records == []

    @pytest.mark.asyncio
    async def test_load_missing_file(self, tmp_path, mock_bus):
        """Отсутствующий файл → FileNotFoundError."""
        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=tmp_path / "nonexistent.jsonl")
        with pytest.raises(FileNotFoundError):
            await source.load()

    @pytest.mark.asyncio
    async def test_load_skips_non_packet_records(self, tmp_path, mock_bus):
        """Записи с log_type != 'packet' пропускаются."""
        path = tmp_path / "mixed.jsonl"
        lines = [
            {"log_type": "connection", "state": "connected"},
            {"log_type": "packet", "hex": "0100", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": False, "terminated": False, "errors": [],
             "timestamp": 100.0, "parsed": None},
            {"log_type": "scenario", "step": "auth"},
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=path)
        records = await source.load()

        assert len(records) == 1
        assert records[0]["log_type"] == "packet"

    @pytest.mark.asyncio
    async def test_load_skips_malformed_json(self, tmp_path, mock_bus):
        """Битые JSON-строки пропускаются с предупреждением."""
        path = tmp_path / "bad.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"log_type": "packet", "hex": "0100"}\n')
            f.write('not valid json\n')
            f.write('{"log_type": "packet", "hex": "0200"}\n')

        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=path)
        records = await source.load()

        assert len(records) == 2


# ====================================================================
# Тесты replay с pipeline
# ====================================================================


class TestReplayWithPipeline:
    """Тесты replay через PacketPipeline."""

    @pytest.mark.asyncio
    async def test_replay_sends_through_pipeline(self, jsonl_file, mock_bus, mock_pipeline):
        """Каждая запись прогоняется через pipeline.process()."""
        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=jsonl_file, pipeline=mock_pipeline)
        await source.replay()

        # pipeline.process вызван дважды (2 записи)
        assert mock_pipeline.process.call_count == 2

    @pytest.mark.asyncio
    async def test_replay_emits_packet_processed(self, jsonl_file, mock_bus, mock_pipeline):
        """После pipeline эмитится packet.processed."""
        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=jsonl_file, pipeline=mock_pipeline)
        result = await source.replay()

        # bus.emit вызван для каждой записи
        emit_calls = [c for c in mock_bus.emit.call_args_list if c[0][0] == "packet.processed"]
        assert len(emit_calls) == 2
        assert result["processed"] == 2

    @pytest.mark.asyncio
    async def test_replay_without_pipeline(self, jsonl_file, mock_bus):
        """Без pipeline — просто эмиссия событий с исходными данными."""
        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=jsonl_file)
        result = await source.replay()

        emit_calls = [c for c in mock_bus.emit.call_args_list if c[0][0] == "packet.processed"]
        assert len(emit_calls) == 2
        assert result["processed"] == 2

    @pytest.mark.asyncio
    async def test_replay_hex_to_bytes(self, jsonl_file, mock_bus, mock_pipeline):
        """hex-строка конвертируется в bytes для pipeline."""
        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=jsonl_file, pipeline=mock_pipeline)
        await source.replay()

        # Проверяем что pipeline получил PacketContext с правильными raw bytes
        call_args = mock_pipeline.process.call_args_list
        first_ctx = call_args[0][1] if "ctx" in call_args[0][1] else call_args[0][0][0]

        assert first_ctx.raw == bytes.fromhex("010001000000A1B2C3D4")
        assert first_ctx.connection_id == "conn-1"
        assert first_ctx.channel == "tcp"


# ====================================================================
# Тесты skip_duplicates
# ====================================================================


class TestReplaySkipDuplicates:
    """Тесты фильтрации дубликатов при replay."""

    @pytest.mark.asyncio
    async def test_skip_duplicates_enabled(self, tmp_path, mock_bus, mock_pipeline):
        """При skip_duplicates=True — дубликаты не обрабатываются."""
        path = tmp_path / "dupes.jsonl"
        lines = [
            {"log_type": "packet", "hex": "0100", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": False, "terminated": False, "errors": [],
             "timestamp": 100.0, "parsed": None},
            {"log_type": "packet", "hex": "0100", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": True, "terminated": False, "errors": [],
             "timestamp": 101.0, "parsed": None},
            {"log_type": "packet", "hex": "0200", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": False, "terminated": False, "errors": [],
             "timestamp": 102.0, "parsed": None},
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=path, pipeline=mock_pipeline,
                              skip_duplicates=True)
        result = await source.replay()

        # 2 записи (первая и третья), дубликат пропущен
        assert mock_pipeline.process.call_count == 2
        assert result["skipped_duplicates"] == 1

    @pytest.mark.asyncio
    async def test_skip_duplicates_disabled(self, tmp_path, mock_bus, mock_pipeline):
        """При skip_duplicates=False — все записи обрабатываются."""
        path = tmp_path / "dupes.jsonl"
        lines = [
            {"log_type": "packet", "hex": "0100", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": False, "terminated": False, "errors": [],
             "timestamp": 100.0, "parsed": None},
            {"log_type": "packet", "hex": "0100", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": True, "terminated": False, "errors": [],
             "timestamp": 101.0, "parsed": None},
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=path, pipeline=mock_pipeline,
                              skip_duplicates=False)
        result = await source.replay()

        assert mock_pipeline.process.call_count == 2
        assert result["skipped_duplicates"] == 0


# ====================================================================
# Тесты результатов
# ====================================================================


class TestReplayResult:
    """Тесты возвращаемых результатов replay."""

    @pytest.mark.asyncio
    async def test_replay_returns_stats(self, jsonl_file, mock_bus, mock_pipeline):
        """replay() возвращает статистику обработки."""
        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=jsonl_file, pipeline=mock_pipeline)
        result = await source.replay()

        assert "processed" in result
        assert "skipped_duplicates" in result
        assert "errors" in result
        assert result["processed"] == 2
        assert result["skipped_duplicates"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_replay_counts_only_packet_records(self, tmp_path, mock_bus):
        """В статистику входят только packet-записи."""
        path = tmp_path / "mixed.jsonl"
        lines = [
            {"log_type": "packet", "hex": "0100", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": False, "terminated": False, "errors": [],
             "timestamp": 100.0, "parsed": None},
            {"log_type": "connection", "state": "connected"},
            {"log_type": "scenario", "step": "auth"},
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=path)
        result = await source.replay()

        assert result["processed"] == 1


# ====================================================================
# Тесты hex → bytes конверсии
# ====================================================================


class TestHexConversion:
    """Тесты конверсии hex в bytes."""

    def test_hex_to_bytes_valid(self):
        """Корректный hex → bytes."""
        from core.packet_source import _hex_to_bytes

        result = _hex_to_bytes("0100A1B2")
        assert result == b"\x01\x00\xa1\xb2"

    def test_hex_to_bytes_lowercase(self):
        """Hex в нижнем регистре → bytes."""
        from core.packet_source import _hex_to_bytes

        result = _hex_to_bytes("aabbcc")
        assert result == b"\xaa\xbb\xcc"

    def test_hex_to_bytes_empty(self):
        """Пустой hex → пустые bytes."""
        from core.packet_source import _hex_to_bytes

        result = _hex_to_bytes("")
        assert result == b""

    def test_hex_to_bytes_none(self):
        """None → пустые bytes."""
        from core.packet_source import _hex_to_bytes

        result = _hex_to_bytes(None)
        assert result == b""

    def test_hex_to_bytes_with_spaces(self):
        """Hex с пробелами → bytes (пробелы игнорируются)."""
        from core.packet_source import _hex_to_bytes

        result = _hex_to_bytes("01 00 AA BB")
        assert result == b"\x01\x00\xaa\xbb"

    def test_hex_to_bytes_invalid(self):
        """Некорректный hex → ValueError."""
        from core.packet_source import _hex_to_bytes

        with pytest.raises(ValueError):
            _hex_to_bytes("ZZZZ")


# ====================================================================
# Тесты обработки ошибок
# ====================================================================


class TestReplayErrors:
    """Тесты обработки ошибок при replay."""

    @pytest.mark.asyncio
    async def test_replay_handles_pipeline_error(self, tmp_path, mock_bus):
        """Ошибка в pipeline не прерывает replay, записывается в errors."""
        path = tmp_path / "err.jsonl"
        lines = [
            {"log_type": "packet", "hex": "0100", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": False, "terminated": False, "errors": [],
             "timestamp": 100.0, "parsed": None},
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

        broken_pipeline = MagicMock()
        broken_pipeline.process = AsyncMock(side_effect=RuntimeError("pipeline error"))

        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=path, pipeline=broken_pipeline)
        result = await source.replay()

        assert result["processed"] == 0
        assert len(result["errors"]) == 1
        assert "pipeline error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_replay_invalid_hex(self, tmp_path, mock_bus):
        """Некорректный hex в записи — ошибка, но replay продолжается."""
        path = tmp_path / "bad_hex.jsonl"
        lines = [
            {"log_type": "packet", "hex": "ZZZZ", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": False, "terminated": False, "errors": [],
             "timestamp": 100.0, "parsed": None},
            {"log_type": "packet", "hex": "0200", "connection_id": "c1", "channel": "tcp",
             "crc_valid": True, "is_duplicate": False, "terminated": False, "errors": [],
             "timestamp": 101.0, "parsed": None},
        ]
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(side_effect=lambda ctx: ctx)

        from core.packet_source import ReplaySource

        source = ReplaySource(bus=mock_bus, log_file=path, pipeline=mock_pipeline)
        result = await source.replay()

        # Первая запись — ошибка hex, вторая — обработана
        assert result["processed"] == 1
        assert len(result["errors"]) == 1
