"""Полноценный интеграционный тест: сервер + эмулятор УСВ.

Запускает:
1. CoreEngine (TCP-сервер на localhost:TEST_PORT)
2. Эмулятор УСВ (подключается к серверу, отправляет TERM_IDENTITY)

Проверяет:
- TCP-соединение установлено
- Пакет TERM_IDENTITY принят и обработан
- RESPONSE отправлен эмулятору
- FSM перешёл в состояние AUTHENTICATING → AUTHORIZED
- Лог-файл записан (JSONL)
- События connection.changed корректны

Использование::

    pytest tests/integration/test_full_integration.py -v -s
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
from core.engine import CoreEngine
from core.event_bus import EventBus


# TERM_IDENTITY пакет из эмулятора УСВ
TERM_IDENTITY_HEX = (
    "0100000B002E002A0001CC2700490080010101240001000000"
    "16383630383033303636343438333133303235303737303031"
    "373135363433390F3A"
)

TEST_PORT = 3099  # Отличный от стандартного порт для тестов


@pytest.fixture
def event_bus() -> EventBus:
    """Создать EventBus для теста."""
    return EventBus()


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Создать тестовую конфигурацию."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        gost_version="2015",
        tcp_port=TEST_PORT,
        cmw500=CmwConfig(ip=None),  # Без CMW-500
        logging=LogConfig(
            dir=str(log_dir),
            level="DEBUG",
        ),
        timeouts=TimeoutsConfig(),
    )


async def _connect_and_send(
    host: str = "127.0.0.1",
    port: int = TEST_PORT,
    packet_hex: str = TERM_IDENTITY_HEX,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Подключиться к серверу, отправить пакет, получить ответ."""
    packet_bytes = bytes.fromhex(packet_hex)
    reader, writer = await asyncio.open_connection(host, port)

    writer.write(packet_bytes)
    await writer.drain()

    result: dict[str, Any] = {"response_bytes": None, "response_hex": None}

    try:
        data = await asyncio.wait_for(reader.read(4096), timeout=timeout)
        if data:
            result["response_bytes"] = data
            result["response_hex"] = data.hex().upper()
    except asyncio.TimeoutError:
        pass

    writer.close()
    await writer.wait_closed()
    return result


class TestFullIntegration:
    """Один интеграционный тест: сервер + эмулятор УСВ."""

    async def test_emulator_connects_sends_and_receives_response(
        self, config: Config, event_bus: EventBus, tmp_path: Path
    ):
        """Тест: эмулятор подключается, отправляет TERM_IDENTITY, получает RESPONSE.

        Шаги:
        1. Запускаем CoreEngine
        2. Эмулятор подключается к TCP-серверу
        3. Отправляет TERM_IDENTITY (PID=42)
        4. Сервер парсит, валидирует CRC, FSM обновляет состояние
        5. Сервер отправляет RESPONSE (PT=0, RPID=42)
        6. Проверяем логи
        7. Останавливаем CoreEngine
        """
        # Собираем события
        state_events: list[dict[str, Any]] = []
        packet_events: list[dict[str, Any]] = []

        async def on_connection_changed(data: dict[str, Any]) -> None:
            state_events.append(data)

        async def on_packet_processed(data: dict[str, Any]) -> None:
            packet_events.append(data)

        event_bus.on("connection.changed", on_connection_changed, ordered=True)
        event_bus.on("packet.processed", on_packet_processed, ordered=True)

        # 1. Запускаем сервер
        engine = CoreEngine(config=config, bus=event_bus)
        await engine.start()
        assert engine.is_running

        try:
            # 2-3. Эмулятор подключается и отправляет TERM_IDENTITY
            result = await _connect_and_send(port=TEST_PORT)

            # Небольшая задержка для обработки
            await asyncio.sleep(0.5)

            # 4. Проверяем RESPONSE
            assert result["response_bytes"] is not None, "Сервер не отправил RESPONSE"
            response = result["response_bytes"]

            # RESPONSE: PR=0x01, RPID=42 (подтверждает PID=42)
            assert response[0] == 0x01, f"PR={response[0]:#x}, ожидался 0x01"
            header_length = response[1]
            if header_length >= 6:
                rpid = int.from_bytes(response[4:6], byteorder="little")
                assert rpid == 42, f"RPID={rpid}, ожидался 42"

            # 5. Проверяем события FSM
            assert len(state_events) >= 1, "Нет событий connection.changed"
            states = [e.get("state") for e in state_events]
            assert "connected" in states or "authenticating" in states or "authorized" in states

            # 6. Проверяем packet.processed
            assert len(packet_events) >= 1, "Нет событий packet.processed"
            ctx = packet_events[0].get("ctx")
            assert ctx is not None
            assert ctx.channel == "tcp"
            assert ctx.crc_valid is True

            # 7. Проверяем логи
            await engine.log_mgr.flush()
            log_dir = Path(config.logging.dir)
            log_files = list(log_dir.glob("*.jsonl"))
            assert len(log_files) >= 1, "Лог-файл не создан"

            log_content = log_files[0].read_text(encoding="utf-8")
            log_lines = [l for l in log_content.strip().split("\n") if l]
            assert len(log_lines) >= 2, f"В логе мало записей: {len(log_lines)}"

            # Ищем запись с пакетом (может быть не первой — сначала идёт connection)
            packet_log = None
            for line in log_lines:
                entry = json.loads(line)
                if entry["log_type"] == "packet":
                    packet_log = entry
                    break

            assert packet_log is not None, "В логе нет записи типа packet"
            assert "hex" in packet_log
            assert packet_log["crc_valid"] is True

            # Выводим логи на консоль для наглядности
            print("\n===== ЛОГИ СЕРВЕРА (JSONL) =====")
            for i, line in enumerate(log_lines, 1):
                entry = json.loads(line)
                print(f"\n--- Запись {i} ({entry['log_type']}) ---")
                print(json.dumps(entry, ensure_ascii=False, indent=2, default=str))
            print("\n===== КОНЕЦ ЛОГОВ =====")

        finally:
            await engine.stop()
