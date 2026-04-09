# mypy: ignore-errors
"""Тесты LogManager.

Проверяют:
- Подписку на события (packet.processed, connection.changed, scenario.step)
- Логирование packet.processed (hex + parsed)
- Логирование connection.changed
- Логирование scenario.step
- Создание файлов логов
- Буферизацию + сортировку по timestamp (CR-002)
- start/stop (подписка/отписка)
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.logger import LogManager

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bus():
    """Mock EventBus."""
    bus = MagicMock()
    bus.emit = AsyncMock()
    bus.on = MagicMock()
    bus.off = MagicMock()
    return bus


@pytest.fixture
def log_manager(mock_bus, tmp_path):
    """LogManager с моком EventBus и временной директорией.

    Отключает фоновый авто-sflush чтобы не мешал тестам.
    """
    with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
        lm = LogManager(
            bus=mock_bus, log_dir=tmp_path,
            flush_interval=999, flush_batch_size=9999,
        )
    return lm


@pytest.fixture
def sample_packet_processed():
    """Данные события packet.processed."""
    from core.pipeline import PacketContext

    ctx = PacketContext(
        raw=b"\x01\x00\x01\x00\x00\x00\xA1\xB2\xC3\xD4",
        connection_id="conn-1",
        channel="tcp",
        parsed={
            "packet": MagicMock(packet_id=1, packet_type="APPDATA"),
            "service": 2,
            "tid": 12345,
        },
        crc_valid=True,
        is_duplicate=False,
        terminated=False,
        errors=[],
    )
    return {
        "ctx": ctx,
        "connection_id": "conn-1",
        "channel": "tcp",
        "parsed": ctx.parsed,
        "crc_valid": True,
        "is_duplicate": False,
        "terminated": False,
    }


@pytest.fixture
def sample_connection_changed():
    """Данные события connection.changed."""
    return {
        "connection_id": "conn-1",
        "state": "CONNECTED",
        "prev_state": "DISCONNECTED",
        "timestamp": time.monotonic(),
    }


@pytest.fixture
def sample_scenario_step():
    """Данные события scenario.step."""
    return {
        "scenario_name": "auth",
        "step_name": "wait_auth_info",
        "step_type": "expect",
        "result": "PASS",
        "details": {"packet_received": True},
        "timestamp": time.monotonic(),
    }


# ---------------------------------------------------------------------------
# Тесты: инициализация и подписка
# ---------------------------------------------------------------------------


class TestLogManagerInit:
    """Инициализация и подписка на события."""

    def test_creates_log_dir(self, mock_bus, tmp_path):
        """LogManager создаёт директорию логов если не существует."""
        log_dir = tmp_path / "subdir" / "logs"
        with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
            LogManager(bus=mock_bus, log_dir=log_dir)
        assert log_dir.exists()

    def test_subscribes_on_init(self, mock_bus, tmp_path):
        """LogManager подписывается на 3 события при инициализации."""
        with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
            LogManager(bus=mock_bus, log_dir=tmp_path)

        # 3 вызова on — по одному на каждое событие
        on_calls = mock_bus.on.call_args_list
        assert len(on_calls) == 3

        event_names = [call[0][0] for call in on_calls]
        assert "packet.processed" in event_names
        assert "connection.changed" in event_names
        assert "scenario.step" in event_names

    @pytest.mark.asyncio
    async def test_stop_unsubscribes(self, mock_bus, tmp_path):
        """stop() отписывается от всех событий и сбрасывает буфер."""
        with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
            lm = LogManager(bus=mock_bus, log_dir=tmp_path)
        mock_bus.off.reset_mock()  # сбросить вызовы из __init__

        await lm.stop()

        off_calls = mock_bus.off.call_args_list
        assert len(off_calls) == 3

        event_names = [call[0][0] for call in off_calls]
        assert "packet.processed" in event_names
        assert "connection.changed" in event_names
        assert "scenario.step" in event_names


# ---------------------------------------------------------------------------
# Тесты: packet.processed
# ---------------------------------------------------------------------------


class TestPacketProcessed:
    """Логирование packet.processed."""

    @pytest.mark.asyncio
    async def test_logs_packet_hex(self, log_manager, sample_packet_processed):
        """В лог записывается hex-представление пакета (без пробелов)."""
        await log_manager._on_packet_processed(sample_packet_processed)

        # Проверяем buffer
        assert len(log_manager._buffer) == 1
        entry = log_manager._buffer[0]
        assert "hex" in entry
        # Hex без пробелов: 010001000000A1B2C3D4
        assert "010001000000A1B2C3D4" in entry["hex"]

    @pytest.mark.asyncio
    async def test_logs_parsed_data(self, log_manager):
        """В лог записываются распарсенные данные."""
        from core.pipeline import PacketContext

        ctx = PacketContext(
            raw=b"\x01\x00\x01\x00\x00\x00\xA1\xB2\xC3\xD4",
            connection_id="conn-1",
            channel="tcp",
            crc_valid=True,
        )
        # Устанавливаем parsed.extra напрямую
        mock_parsed = MagicMock()
        mock_parsed.packet = None
        mock_parsed.extra = {"service": 2, "tid": 12345}
        ctx.parsed = mock_parsed

        await log_manager._on_packet_processed({
            "ctx": ctx,
            "connection_id": "conn-1",
            "channel": "tcp",
            "crc_valid": True,
            "is_duplicate": False,
            "terminated": False,
        })

        entry = log_manager._buffer[0]
        assert "parsed" in entry
        assert entry["parsed"]["service"] == 2
        assert entry["parsed"]["tid"] == 12345

    @pytest.mark.asyncio
    async def test_logs_metadata(self, log_manager, sample_packet_processed):
        """В лог записываются connection_id, channel, crc_valid."""
        await log_manager._on_packet_processed(sample_packet_processed)

        entry = log_manager._buffer[0]
        assert entry["connection_id"] == "conn-1"
        assert entry["channel"] == "tcp"
        assert entry["crc_valid"] is True
        assert entry["is_duplicate"] is False

    @pytest.mark.asyncio
    async def test_logs_errors(self, log_manager):
        """Ошибки обработки записываются в лог."""
        from core.pipeline import PacketContext

        ctx = PacketContext(
            raw=b"\xff\xff",
            connection_id="err-conn",
            channel="tcp",
            crc_valid=False,
            terminated=True,
            errors=["CRC-8 mismatch", "Parse failed"],
        )
        data = {
            "ctx": ctx,
            "connection_id": "err-conn",
            "channel": "tcp",
            "crc_valid": False,
            "is_duplicate": False,
            "terminated": True,
        }

        await log_manager._on_packet_processed(data)

        entry = log_manager._buffer[0]
        assert "errors" in entry
        assert len(entry["errors"]) == 2
        assert entry["terminated"] is True

    @pytest.mark.asyncio
    async def test_logs_duplicate(self, log_manager):
        """Дубликат помечается в логе."""
        from core.pipeline import PacketContext

        ctx = PacketContext(
            raw=b"\x01\x00\x01\x00",
            connection_id="conn-1",
            channel="tcp",
            crc_valid=True,
            is_duplicate=True,
        )
        await log_manager._on_packet_processed({
            "ctx": ctx,
            "connection_id": "conn-1",
            "channel": "tcp",
            "crc_valid": True,
            "is_duplicate": True,
            "terminated": False,
        })

        entry = log_manager._buffer[0]
        assert entry["is_duplicate"] is True

    @pytest.mark.asyncio
    async def test_logs_sms_channel(self, log_manager):
        """SMS-канал корректно логируется."""
        from core.pipeline import PacketContext

        ctx = PacketContext(
            raw=b"\x01\x00\x01\x00",
            connection_id="conn-1",
            channel="sms",
            crc_valid=True,
        )
        await log_manager._on_packet_processed({
            "ctx": ctx,
            "connection_id": "conn-1",
            "channel": "sms",
            "crc_valid": True,
            "is_duplicate": False,
            "terminated": False,
        })

        entry = log_manager._buffer[0]
        assert entry["channel"] == "sms"

    @pytest.mark.asyncio
    async def test_empty_raw_packet(self, log_manager):
        """Пустой raw обрабатывается без ошибки."""
        from core.pipeline import PacketContext

        ctx = PacketContext(
            raw=b"",
            connection_id="empty-conn",
            channel="tcp",
        )
        data = {
            "ctx": ctx,
            "connection_id": "empty-conn",
            "channel": "tcp",
            "crc_valid": False,
            "is_duplicate": False,
            "terminated": True,
        }

        # Не должно бросать исключение
        await log_manager._on_packet_processed(data)
        assert len(log_manager._buffer) == 1

    @pytest.mark.asyncio
    async def test_parsed_is_none(self, log_manager):
        """Отсутствующий parsed обрабатывается без ошибки."""
        from core.pipeline import PacketContext

        ctx = PacketContext(
            raw=b"\x01\x00",
            connection_id="no-parse-conn",
            channel="tcp",
            parsed=None,
            crc_valid=False,
            terminated=True,
        )
        data = {
            "ctx": ctx,
            "connection_id": "no-parse-conn",
            "channel": "tcp",
            "parsed": None,
            "crc_valid": False,
            "is_duplicate": False,
            "terminated": True,
        }

        await log_manager._on_packet_processed(data)
        assert len(log_manager._buffer) == 1


# ---------------------------------------------------------------------------
# Тесты: connection.changed
# ---------------------------------------------------------------------------


class TestConnectionChanged:
    """Логирование connection.changed."""

    @pytest.mark.asyncio
    async def test_logs_state_change(self, log_manager, sample_connection_changed):
        """Смена состояния записывается в лог."""
        await log_manager._on_connection_changed(sample_connection_changed)

        assert len(log_manager._buffer) == 1
        entry = log_manager._buffer[0]

        assert entry["connection_id"] == "conn-1"
        assert entry["state"] == "CONNECTED"
        assert entry["prev_state"] == "DISCONNECTED"
        assert "log_type" in entry
        assert entry["log_type"] == "connection"

    @pytest.mark.asyncio
    async def test_logs_without_prev_state(self, log_manager):
        """Первое подключение (без prev_state) логируется."""
        data = {
            "connection_id": "new-conn",
            "state": "CONNECTED",
            "timestamp": time.monotonic(),
        }
        await log_manager._on_connection_changed(data)

        entry = log_manager._buffer[0]
        assert entry["state"] == "CONNECTED"
        assert entry.get("prev_state") is None


# ---------------------------------------------------------------------------
# Тесты: scenario.step
# ---------------------------------------------------------------------------


class TestScenarioStep:
    """Логирование scenario.step."""

    @pytest.mark.asyncio
    async def test_logs_step_result(self, log_manager, sample_scenario_step):
        """Результат шага записывается в лог."""
        await log_manager._on_scenario_step(sample_scenario_step)

        assert len(log_manager._buffer) == 1
        entry = log_manager._buffer[0]

        assert entry["scenario_name"] == "auth"
        assert entry["step_name"] == "wait_auth_info"
        assert entry["step_type"] == "expect"
        assert entry["result"] == "PASS"
        assert entry["log_type"] == "scenario"

    @pytest.mark.asyncio
    async def test_logs_fail_result(self, log_manager, sample_scenario_step):
        """FAIL-результат шага логируется."""
        sample_scenario_step["result"] = "FAIL"
        sample_scenario_step["details"] = {"error": "Timeout waiting for packet"}
        await log_manager._on_scenario_step(sample_scenario_step)

        entry = log_manager._buffer[0]
        assert entry["result"] == "FAIL"
        assert entry["details"]["error"] == "Timeout waiting for packet"


# ---------------------------------------------------------------------------
# Тесты: буферизация и сортировка
# ---------------------------------------------------------------------------


class TestBufferFlush:
    """Буферизация и сортировка по timestamp."""

    @pytest.mark.asyncio
    async def test_flush_creates_file(self, log_manager, sample_packet_processed):
        """flush() создаёт файл с логами."""
        await log_manager._on_packet_processed(sample_packet_processed)
        await log_manager.flush()

        # Файл должен существовать
        log_files = list(log_manager._log_dir.glob("*.jsonl"))
        assert len(log_files) == 1

    @pytest.mark.asyncio
    async def test_flush_writes_jsonl(self, log_manager, sample_packet_processed):
        """flush() записывает JSONL (JSON Lines)."""
        await log_manager._on_packet_processed(sample_packet_processed)
        await log_manager.flush()

        log_file = next(iter(log_manager._log_dir.glob("*.jsonl")))
        content = log_file.read_text(encoding="utf-8")
        lines = [line for line in content.strip().splitlines() if line.strip()]

        assert len(lines) == 1
        # Каждая строка — валидный JSON
        entry = json.loads(lines[0])
        assert "hex" in entry
        assert "connection_id" in entry

    @pytest.mark.asyncio
    async def test_flush_sorts_by_timestamp(self, log_manager):
        """Записи сортируются по timestamp при flush."""
        from core.pipeline import PacketContext

        # Добавляем в обратном порядке с разными timestamp
        ctx1 = PacketContext(
            raw=b"\x01",
            connection_id="conn-1",
            channel="tcp",
            crc_valid=True,
        )
        ctx1.timestamp = 100.0  # позже

        ctx2 = PacketContext(
            raw=b"\x02",
            connection_id="conn-2",
            channel="tcp",
            crc_valid=True,
        )
        ctx2.timestamp = 50.0  # раньше

        await log_manager._on_packet_processed({
            "ctx": ctx1,
            "connection_id": "conn-1",
            "channel": "tcp",
            "crc_valid": True,
            "is_duplicate": False,
            "terminated": False,
        })
        await log_manager._on_packet_processed({
            "ctx": ctx2,
            "connection_id": "conn-2",
            "channel": "tcp",
            "crc_valid": True,
            "is_duplicate": False,
            "terminated": False,
        })

        await log_manager.flush()

        log_file = next(iter(log_manager._log_dir.glob("*.jsonl")))
        lines = [json.loads(line) for line in log_file.read_text().strip().splitlines()]

        # Первый — с timestamp=50.0 (conn-2, раньше)
        assert lines[0]["timestamp"] == pytest.approx(50.0)
        # Второй — с timestamp=100.0 (conn-1, позже)
        assert lines[1]["timestamp"] == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_flush_clears_buffer(self, log_manager, sample_packet_processed):
        """flush() очищает буфер после записи."""
        await log_manager._on_packet_processed(sample_packet_processed)
        await log_manager.flush()

        assert len(log_manager._buffer) == 0

    @pytest.mark.asyncio
    async def test_flush_empty_buffer_no_file(self, mock_bus, tmp_path):
        """flush() с пустым буфером не создаёт файл."""
        lm = LogManager(bus=mock_bus, log_dir=tmp_path)
        await lm.flush()

        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 0

    @pytest.mark.asyncio
    async def test_multiple_events_in_buffer(self, log_manager):
        """Разные типы событий накапливаются в буфере."""
        from core.pipeline import PacketContext

        ctx = PacketContext(
            raw=b"\x01",
            connection_id="conn-1",
            channel="tcp",
            crc_valid=True,
        )

        await log_manager._on_packet_processed({
            "ctx": ctx,
            "connection_id": "conn-1",
            "channel": "tcp",
            "crc_valid": True,
            "is_duplicate": False,
            "terminated": False,
        })
        await log_manager._on_connection_changed({
            "connection_id": "conn-1",
            "state": "CONNECTED",
            "timestamp": time.monotonic(),
        })
        await log_manager._on_scenario_step({
            "scenario_name": "test",
            "step_name": "step1",
            "step_type": "send",
            "result": "PASS",
            "timestamp": time.monotonic(),
        })

        assert len(log_manager._buffer) == 3


# ---------------------------------------------------------------------------
# Тесты: именование файлов
# ---------------------------------------------------------------------------


class TestFileNaming:
    """Именование файлов логов."""

    @pytest.mark.asyncio
    async def test_daily_log_filename(self, mock_bus, tmp_path):
        """Файл логов именуется по дате: YYYY-MM-DD.jsonl."""
        from datetime import date

        lm = LogManager(bus=mock_bus, log_dir=tmp_path)

        from core.pipeline import PacketContext

        ctx = PacketContext(
            raw=b"\x01",
            connection_id="conn-1",
            channel="tcp",
            crc_valid=True,
        )
        await lm._on_packet_processed({
            "ctx": ctx,
            "connection_id": "conn-1",
            "channel": "tcp",
            "crc_valid": True,
            "is_duplicate": False,
            "terminated": False,
        })
        await lm.flush()

        today = date.today().isoformat()  # YYYY-MM-DD
        expected_file = tmp_path / f"{today}.jsonl"
        assert expected_file.exists()

    @pytest.mark.asyncio
    async def test_stop_flushes_before_unsubscribe(self, mock_bus, tmp_path):
        """stop() сбрасывает буфер перед отпиской."""
        from core.pipeline import PacketContext

        with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
            lm = LogManager(bus=mock_bus, log_dir=tmp_path)

        ctx = PacketContext(
            raw=b"\x01",
            connection_id="conn-1",
            channel="tcp",
            crc_valid=True,
        )
        await lm._on_packet_processed({
            "ctx": ctx, "connection_id": "conn-1", "channel": "tcp",
            "crc_valid": True, "is_duplicate": False, "terminated": False,
        })

        # Буфер не пустой
        assert len(lm._buffer) == 1

        await lm.stop()

        # Файл должен существовать (stop() вызвал flush)
        from datetime import date
        today = date.today().isoformat()
        expected_file = tmp_path / f"{today}.jsonl"
        assert expected_file.exists()

    @pytest.mark.asyncio
    async def test_auto_flush_loop(self, mock_bus, tmp_path):
        """Авто-sflush сбрасывает буфер при превышении batch_size."""
        from core.pipeline import PacketContext

        with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
            lm = LogManager(
                bus=mock_bus, log_dir=tmp_path,
                flush_interval=0.1, flush_batch_size=3,
            )
        # Запускаем авто-sflush вручную (т.к. create_task был замокан)
        lm._flush_task = asyncio.create_task(lm._auto_flush_loop())

        # Добавляем 3 записи (порог)
        for i in range(3):
            ctx = PacketContext(
                raw=bytes([i + 1]),
                connection_id=f"conn-{i}",
                channel="tcp",
                crc_valid=True,
            )
            await lm._on_packet_processed({
                "ctx": ctx, "connection_id": f"conn-{i}", "channel": "tcp",
                "crc_valid": True, "is_duplicate": False, "terminated": False,
            })

        # Ждём авто-sflush
        await asyncio.sleep(0.3)

        from datetime import date
        today = date.today().isoformat()
        log_file = tmp_path / f"{today}.jsonl"

        # Файл должен появиться
        assert log_file.exists(), "Авто-sflush не создал файл"

        await lm.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_flush_task(self, tmp_path):
        """stop() отменяет фоновую задачу автосброса."""
        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()
        mock_bus.on = MagicMock()
        mock_bus.off = MagicMock()

        lm = LogManager(
            bus=mock_bus, log_dir=tmp_path,
            flush_interval=999, flush_batch_size=9999,
        )
        assert lm._flush_task is not None
        assert not lm._flush_task.done()

        await lm.stop()

        assert lm._flush_task is None
        assert lm._running is False

    @pytest.mark.asyncio
    async def test_append_to_existing_file(self, mock_bus, tmp_path):
        """При повторном flush в тот же день — данные дописываются."""
        from datetime import date

        with patch("core.logger.asyncio.create_task", return_value=MagicMock()):
            lm = LogManager(bus=mock_bus, log_dir=tmp_path)

        from core.pipeline import PacketContext

        ctx1 = PacketContext(raw=b"\x01", connection_id="c1", channel="tcp", crc_valid=True)
        ctx2 = PacketContext(raw=b"\x02", connection_id="c2", channel="tcp", crc_valid=True)

        await lm._on_packet_processed({
            "ctx": ctx1, "connection_id": "c1", "channel": "tcp",
            "crc_valid": True, "is_duplicate": False, "terminated": False,
        })
        await lm.flush()

        await lm._on_packet_processed({
            "ctx": ctx2, "connection_id": "c2", "channel": "tcp",
            "crc_valid": True, "is_duplicate": False, "terminated": False,
        })
        await lm.flush()

        today = date.today().isoformat()
        log_file = tmp_path / f"{today}.jsonl"
        lines = [line for line in log_file.read_text().strip().splitlines() if line.strip()]
        assert len(lines) == 2
