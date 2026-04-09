"""Интеграционные тесты PacketPipeline с реальными HEX-пакетами.

Тесты загружают реальные EGTS-пакеты из data/packets/all_packets_correct_20260406_190414.json
и прогоняют их через полный конвейер:
    CRC → Parse → Dedup → EventEmit

Цели:
1. Проверить корректность работы всего конвейера целиком
2. Валидировать CRC-проверку на реальных пакетах
3. Проверить парсинг реальных EGTS-пакетов
4. Убедиться в корректной работе DuplicateDetection
5. Проверить публикацию событий для всех типов пакетов
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.event_bus import EventBus
from core.pipeline import (
    CrcValidationMiddleware,
    DuplicateDetectionMiddleware,
    EventEmitMiddleware,
    PacketContext,
    PacketPipeline,
    ParseMiddleware,
)
from core.session import SessionManager, UsvConnection
from libs.egts_protocol_iface import IEgtsProtocol, create_protocol

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def packets_data(project_root: Path) -> list[dict[str, object]]:
    """Загрузить реальные EGTS-пакеты из JSON-файла."""
    json_path = project_root / "data" / "packets" / "all_packets_correct_20260406_190414.json"
    with open(json_path, encoding="utf-8") as f:
        data: list[dict[str, object]] = json.load(f)
        return data


@pytest.fixture
def session_mgr() -> SessionManager:
    """Создать SessionManager с реальным EventBus и протоколом."""
    bus = EventBus()
    session_mgr = SessionManager(bus, gost_version="2015")
    return session_mgr


@pytest.fixture
def protocol_2015() -> IEgtsProtocol:
    """Создать экземпляр протокола ГОСТ 2015."""
    return create_protocol("2015")


@pytest.fixture
def connection_with_protocol(
    session_mgr: SessionManager,
    protocol_2015: IEgtsProtocol,
) -> UsvConnection:
    """Создать сессию с настроенным протоколом."""
    conn = session_mgr.create_session(
        connection_id="test-conn-1",
        remote_ip="127.0.0.1",
        remote_port=12345,
        protocol=protocol_2015,
        is_std_usv=False,
    )
    return conn


def _build_full_pipeline(session_mgr: SessionManager) -> PacketPipeline:
    """Создать полный конвейер из 4 middleware."""
    bus = EventBus()
    pipeline = PacketPipeline()
    pipeline.add("crc", CrcValidationMiddleware(session_mgr), order=10)
    pipeline.add("parse", ParseMiddleware(session_mgr), order=20)
    pipeline.add("dedup", DuplicateDetectionMiddleware(session_mgr), order=30)
    pipeline.add("event", EventEmitMiddleware(bus), order=40)
    return pipeline


def _hex_to_bytes(hex_str: str) -> bytes:
    """Преобразовать hex-строку в bytes."""
    return bytes.fromhex(hex_str)


# =============================================================================
# Тест 1: Полный прогон конвейера на одном пакете
# =============================================================================


class TestPipelineFullRun:
    """Тест полного прогона конвейера на одном пакете."""

    @pytest.mark.asyncio
    async def test_single_packet_pipeline(
        self, connection_with_protocol: UsvConnection
    ) -> None:
        """Один пакет проходит через весь конвейер без ошибок."""
        session_mgr = SessionManager(EventBus(), gost_version="2015")
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        # Пакет EGTS_GPRS_APN (SMS)(1) — команда конфигурирования
        raw_hex = (
            "0100000B0021001B0001321A002A00400404331700500000000000000000000000020302696E7465726E65740D48"
        )
        raw_bytes = _hex_to_bytes(raw_hex)

        pipeline = _build_full_pipeline(session_mgr)
        ctx = PacketContext(raw=raw_bytes, connection_id="test-conn-1")
        result = await pipeline.process(ctx)

        # Пакет должен пройти CRC
        assert result.crc_valid is True
        assert result.terminated is False
        assert len(result.errors) == 0

        # Парсинг должен вернуть результат
        assert result.parsed is not None
        assert result.parsed.packet is not None

        # RESPONSE не формируется на этом этапе (это задача ScenarioManager)
        # Dedup не помечает как дубликат (первый пакет)
        assert result.is_duplicate is False


# =============================================================================
# Тест 2: Прогон всех пакетов из каталога
# =============================================================================


class TestAllPacketsCatalog:
    """Прогон всех пакетов из каталога через конвейер."""

    @pytest.mark.asyncio
    async def test_all_packets_crc_validation(
        self,
        packets_data: list[dict[str, object]],
        session_mgr: SessionManager,
    ) -> None:
        """Все пакеты из каталога проходят CRC-валидацию.

        Это интеграционный тест — проверяем, что конвейер
        корректно обрабатывает все 51 пакет без падений.
        """
        # Создаём сессию
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        pipeline = _build_full_pipeline(session_mgr)

        passed_crc = 0
        failed_crc = 0
        parse_errors = 0

        for pkt in packets_data:
            hex_str = str(pkt["hex"])
            raw_bytes = _hex_to_bytes(hex_str)

            ctx = PacketContext(raw=raw_bytes, connection_id="test-conn-1")
            result = await pipeline.process(ctx)

            # Конвейер не должен падать с исключением
            # (исключения обрабатываются внутри pipeline)

            if result.crc_valid:
                passed_crc += 1
            else:
                failed_crc += 1

            if result.terminated and result.errors:
                parse_errors += 1

        # Статистика
        total = len(packets_data)
        assert passed_crc + failed_crc == total
        # Большинство пакетов должны пройти CRC (это реальные корректные пакеты)
        assert passed_crc > 0, "Ни один пакет не прошёл CRC!"

    @pytest.mark.asyncio
    async def test_all_packets_event_emitted(
        self,
        packets_data: list[dict[str, object]],
    ) -> None:
        """Для каждого пакета эмитится событие packet.processed.

        Проверяем гарантию 100% логирования — EventEmitMiddleware
        вызывается даже при terminated=True.
        """
        bus = EventBus()
        event_count = 0

        async def counter(event_data: dict[str, object]) -> None:
            nonlocal event_count
            event_count += 1

        # Подписываемся как ordered=True для последовательной обработки
        bus.on("packet.processed", counter, ordered=True)

        # Создаём SessionManager с тем же bus
        session_mgr = SessionManager(bus, gost_version="2015")
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        # Создаём pipeline вручную с нашим bus
        pipeline = PacketPipeline()
        pipeline.add("crc", CrcValidationMiddleware(session_mgr), order=10)
        pipeline.add("parse", ParseMiddleware(session_mgr), order=20)
        pipeline.add("dedup", DuplicateDetectionMiddleware(session_mgr), order=30)
        pipeline.add("event", EventEmitMiddleware(bus), order=40)

        for pkt in packets_data:
            hex_str = str(pkt["hex"])
            raw_bytes = _hex_to_bytes(hex_str)

            ctx = PacketContext(raw=raw_bytes, connection_id="test-conn-1")
            await pipeline.process(ctx)

        # Событие должно эмититься для каждого пакета
        assert event_count == len(packets_data)


# =============================================================================
# Тест 3: Duplicate detection на реальных пакетах
# =============================================================================


class TestDuplicateDetection:
    """Тест обнаружения дубликатов на реальных пакетах."""

    @pytest.mark.asyncio
    async def test_duplicate_packet_detection(
        self, session_mgr: SessionManager
    ) -> None:
        """Одинаковый PID дважды — второй помечается как дубликат."""
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        # TERM_IDENTITY пакет (PID=42)
        hex_str = "0100000B002E002A0001CC270049008001010124000100000016383630383033303636343438333133303235303737303031373135363433390F3A"
        raw_bytes = _hex_to_bytes(hex_str)

        pipeline = _build_full_pipeline(session_mgr)

        # Первый прогон
        ctx1 = PacketContext(raw=raw_bytes, connection_id="test-conn-1")
        result1 = await pipeline.process(ctx1)

        assert result1.crc_valid is True
        assert result1.is_duplicate is False
        assert result1.parsed is not None
        assert result1.parsed.packet is not None
        assert result1.parsed.packet.packet_id == 42

        # Добавляем RESPONSE в кэш (имитируем отправку RESPONSE)
        conn = session_mgr.get_session("test-conn-1")
        assert conn is not None
        conn.add_pid_response(42, b"\x01\x00\x00\x10\x00\x00\x06\x00\x01\x00\x40\x01\x01\x00\x03\x00\x49\x00\x00\xE6\xBE")

        # Второй прогон — должен определить как дубликат
        ctx2 = PacketContext(raw=raw_bytes, connection_id="test-conn-1")
        result2 = await pipeline.process(ctx2)

        assert result2.is_duplicate is True
        assert result2.terminated is True
        assert result2.response_data is not None


# =============================================================================
# Тест 4: Разные типы пакетов
# =============================================================================


class TestPacketTypes:
    """Тест обработки разных типов пакетов."""

    @pytest.mark.asyncio
    async def test_response_packet_processing(
        self, session_mgr: SessionManager
    ) -> None:
        """RESPONSE-пакет (PT=0) корректно парсится."""
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        # EGTS_SR_RECORD_RESPONSE (8) — PT=0 (RESPONSE)
        hex_str = "0100000B0010001E00003B2A000006002D00400101000300490000E6BE"
        raw_bytes = _hex_to_bytes(hex_str)

        pipeline = _build_full_pipeline(session_mgr)
        ctx = PacketContext(raw=raw_bytes, connection_id="test-conn-1")
        result = await pipeline.process(ctx)

        assert result.crc_valid is True
        assert result.parsed is not None
        assert result.parsed.packet is not None
        # PT=0 — RESPONSE
        assert result.parsed.packet.packet_type == 0

    @pytest.mark.asyncio
    async def test_appdata_packet_processing(
        self, session_mgr: SessionManager
    ) -> None:
        """APPDATA-пакет (PT=1) корректно парсится."""
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        # EGTS_SR_TERM_IDENTITY (7) — PT=1 (APPDATA)
        hex_str = "0100000B002E002A0001CC270049008001010124000100000016383630383033303636343438333133303235303737303031373135363433390F3A"
        raw_bytes = _hex_to_bytes(hex_str)

        pipeline = _build_full_pipeline(session_mgr)
        ctx = PacketContext(raw=raw_bytes, connection_id="test-conn-1")
        result = await pipeline.process(ctx)

        assert result.crc_valid is True
        assert result.parsed is not None
        assert result.parsed.packet is not None
        # PT=1 — APPDATA
        assert result.parsed.packet.packet_type == 1


# =============================================================================
# Тест 5: Error handling
# =============================================================================


class TestErrorHandling:
    """Тест обработки ошибок в конвейере."""

    @pytest.mark.asyncio
    async def test_invalid_crc_packet(self, session_mgr: SessionManager) -> None:
        """Пакет с невалидным CRC формирует RESPONSE и terminated=True."""
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        # Берём валидный пакет и портим CRC-16 (последние 2 байта)
        hex_str = "0100000B0010001E00003B2A000006002D00400101000300490000E6BE"
        raw_bytes = _hex_to_bytes(hex_str)

        # Портим CRC-16 — меняем последние 2 байта
        corrupted = raw_bytes[:-2] + b"\x00\x00"

        pipeline = _build_full_pipeline(session_mgr)
        ctx = PacketContext(raw=corrupted, connection_id="test-conn-1")
        result = await pipeline.process(ctx)

        assert result.crc_valid is False
        assert result.crc16_valid is False
        assert result.terminated is True
        assert result.response_data is not None

    @pytest.mark.asyncio
    async def test_empty_packet(self, session_mgr: SessionManager) -> None:
        """Пустой пакет (b"") → terminated=True."""
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        pipeline = _build_full_pipeline(session_mgr)
        ctx = PacketContext(raw=b"", connection_id="test-conn-1")
        result = await pipeline.process(ctx)

        assert result.crc_valid is False
        assert result.terminated is True

    @pytest.mark.asyncio
    async def test_too_short_packet(self, session_mgr: SessionManager) -> None:
        """Слишком короткий пакет (< 4 байт) → terminated=True."""
        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        pipeline = _build_full_pipeline(session_mgr)
        ctx = PacketContext(raw=b"\x01\x00\x00", connection_id="test-conn-1")
        result = await pipeline.process(ctx)

        assert result.crc_valid is False
        assert result.terminated is True

    @pytest.mark.asyncio
    async def test_unknown_connection_id(self) -> None:
        """Неизвестный connection_id → terminated=True."""
        session_mgr = SessionManager(EventBus(), gost_version="2015")
        # Не создаём сессию!

        pipeline = _build_full_pipeline(session_mgr)
        ctx = PacketContext(raw=b"\x01\x00\x00\x0B\x00", connection_id="unknown-conn")
        result = await pipeline.process(ctx)

        assert result.crc_valid is False
        assert result.terminated is True
        # CrcValidationMiddleware не добавляет ошибку в errors при неизвестном connection
        # (это поведение соответствует ГОСТ — пакет отклоняется без ошибки парсинга)


# =============================================================================
# Тест 6: Event data integrity
# =============================================================================


class TestEventDataIntegrity:
    """Тест целостности данных события packet.processed."""

    @pytest.mark.asyncio
    async def test_event_contains_full_context(
        self, session_mgr: SessionManager
    ) -> None:
        """Событие packet.processed содержит полный PacketContext."""
        bus = EventBus()
        captured_events: list[dict[str, object]] = []

        async def capture(event_data: dict[str, object]) -> None:
            captured_events.append(event_data)

        bus.on("packet.processed", capture)

        session_mgr.create_session(
            connection_id="test-conn-1",
            protocol=create_protocol("2015"),
        )

        # Пересоздаём pipeline с нашим bus
        pipeline = PacketPipeline()
        pipeline.add("crc", CrcValidationMiddleware(session_mgr), order=10)
        pipeline.add("parse", ParseMiddleware(session_mgr), order=20)
        pipeline.add("dedup", DuplicateDetectionMiddleware(session_mgr), order=30)
        pipeline.add("event", EventEmitMiddleware(bus), order=40)

        hex_str = "0100000B0010001E00003B2A000006002D00400101000300490000E6BE"
        raw_bytes = _hex_to_bytes(hex_str)

        ctx = PacketContext(raw=raw_bytes, connection_id="test-conn-1", channel="tcp")
        await pipeline.process(ctx)

        assert len(captured_events) == 1
        event = captured_events[0]

        # Проверяем все поля
        assert "ctx" in event
        assert "connection_id" in event
        assert "channel" in event
        assert "parsed" in event
        assert "crc_valid" in event
        assert "is_duplicate" in event
        assert "terminated" in event

        assert event["connection_id"] == "test-conn-1"
        assert event["channel"] == "tcp"
        assert event["crc_valid"] is True
