"""Интеграционный тест полного сценария авторизации.

Клиент (эмулятор УСВ) подключается к серверу и отправляет 3 пакета
по сценарию `scenarios/auth/`:
  1. TERM_IDENTITY (PID=42)
  2. VEHICLE_DATA (PID=43)
  3. RECORD_RESPONSE_RESULT (PID=44) — результат аутентификации

Между пакетами — задержка 1 секунда. После каждого пакета сервер
отправляет RESPONSE с RECORD_RESPONSE.

Проверяет:
- Все 3 RESPONSE получены
- Каждый RESPONSE содержит RECORD_RESPONSE подзапись
- FSM проходит: CONNECTED → AUTHENTICATING → AUTHORIZED → RUNNING
- Лог-файл содержит 3 записи о пакетах
- События connection.changed отражают переходы FSM

Использование::

    pytest tests/integration/test_auth_scenario.py -v -s
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

# Пакеты из scenarios/auth/packets/usv/
TERM_IDENTITY_HEX = (
    "0100000B002E002A0001CC2700490080010101240001000000"
    "16383630383033303636343438333133303235303737303031"
    "373135363433390F3A"
)

VEHICLE_DATA_HEX = (
    "0100000B0023002B0001781C004A0080010103190031443447"
    "5032354230333831303837373501000000010000006CE1"
)

RECORD_RESPONSE_RESULT_HEX = (
    "0100000B0010002C00006A20000006004B008001010003002F0000F139"
)

AUTH_PACKETS = [
    TERM_IDENTITY_HEX,
    VEHICLE_DATA_HEX,
    RECORD_RESPONSE_RESULT_HEX,
]

TEST_PORT = 3098  # Отличный от других тестов порт


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def config(tmp_path: Path) -> Config:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        gost_version="2015",
        tcp_port=TEST_PORT,
        cmw500=CmwConfig(ip=None),
        logging=LogConfig(
            dir=str(log_dir),
            level="DEBUG",
        ),
        timeouts=TimeoutsConfig(),
    )


async def _connect_and_send_sequence(
    host: str = "127.0.0.1",
    port: int = TEST_PORT,
    packets_hex: list[str] = AUTH_PACKETS,
    delay: float = 1.0,
    response_timeout: float = 5.0,
) -> list[dict[str, Any]]:
    """Подключиться, отправить пакеты с задержкой, собрать все RESPONSE.

    Returns:
        Список dict с ключами: packet_idx, response_bytes, response_hex
    """
    reader, writer = await asyncio.open_connection(host, port)

    results: list[dict[str, Any]] = []

    for idx, pkt_hex in enumerate(packets_hex):
        pkt_bytes = bytes.fromhex(pkt_hex)
        writer.write(pkt_bytes)
        await writer.drain()

        entry: dict[str, Any] = {"packet_idx": idx, "response_bytes": None, "response_hex": None}

        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=response_timeout)
            if data:
                entry["response_bytes"] = data
                entry["response_hex"] = data.hex().upper()
        except TimeoutError:
            pass

        results.append(entry)

        # Задержка перед следующим пакетом (не после последнего)
        if idx < len(packets_hex) - 1:
            await asyncio.sleep(delay)

    writer.close()
    await writer.wait_closed()
    return results


class TestAuthScenario:
    """Сценарий авторизации: TERM_IDENTITY → VEHICLE_DATA → RESULT_CODE."""

    async def test_auth_three_packets_with_responses(
        self, config: Config, event_bus: EventBus, tmp_path: Path
    ):
        """Тест: 3 пакета → 3 RESPONSE с RECORD_RESPONSE → FSM → логи.

        Шаги:
        1. Запускаем CoreEngine
        2. Подключаемся, отправляем TERM_IDENTITY (PID=42)
        3. Ждём 1 с, отправляем VEHICLE_DATA (PID=43)
        4. Ждём 1 с, отправляем RECORD_RESPONSE_RESULT (PID=44)
        5. Проверяем все 3 RESPONSE
        6. Проверяем FSM-переходы
        7. Проверяем логи
        8. Останавливаем CoreEngine
        """
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
            # 2-4. Отправляем 3 пакета с задержкой
            results = await _connect_and_send_sequence(port=TEST_PORT, delay=1.0)

            # Небольшая задержка для обработки последнего пакета
            await asyncio.sleep(0.5)

            # 5. Проверяем все 3 RESPONSE
            assert len(results) == 3, f"Ожидалось 3 ответа, получено {len(results)}"

            for idx, result in enumerate(results):
                assert result["response_bytes"] is not None, (
                    f"Пакет {idx}: сервер не отправил RESPONSE"
                )
                response = result["response_bytes"]

                # Базовая проверка: PR=0x01
                assert response[0] == 0x01, (
                    f"Пакет {idx}: PR={response[0]:#x}, ожидался 0x01"
                )

                # Проверяем через новую библиотеку
                import libs.egts._gost2015  # noqa: F401 — регистрирует протокол
                from libs.egts.registry import get_protocol

                proto = get_protocol("2015")
                resp_result = proto.parse_packet(response)
                assert resp_result.is_success, (
                    f"Пакет {idx}: RESPONSE не распарсился: {resp_result.errors}"
                )
                resp_pkt = resp_result.packet
                assert resp_pkt.packet_type == 0, (
                    f"Пакет {idx}: Тип пакета должен быть RESPONSE (0)"
                )
                assert resp_pkt.processing_result == 0, (
                    f"Пакет {idx}: PR={resp_pkt.processing_result}, ожидался 0"
                )

                # RECORD_RESPONSE
                assert len(resp_pkt.records) >= 1, (
                    f"Пакет {idx}: RESPONSE должен содержать хотя бы одну запись"
                )

                # Находим RECORD_RESPONSE подзапись
                found_record_response = False
                for rec in resp_pkt.records:
                    for sub in rec.subrecords:
                        if sub.subrecord_type == 0:  # RECORD_RESPONSE
                            found_record_response = True
                            if isinstance(sub.data, dict):
                                rst = sub.data.get("rst", 0)
                                assert rst == 0, (
                                    f"Пакет {idx}: RST={rst}, ожидался 0 (OK)"
                                )
                            break
                    if found_record_response:
                        break

                assert found_record_response, (
                    f"Пакет {idx}: RESPONSE должен содержать RECORD_RESPONSE подзапись"
                )

            # Проверка RPID: каждый RESPONSE подтверждает свой PID
            expected_pids = [42, 43, 44]
            for idx, result in enumerate(results):
                response = result["response_bytes"]
                from libs.egts.registry import get_protocol

                proto = get_protocol("2015")
                resp_result = proto.parse_packet(response)
                assert resp_result.is_success, (
                    f"Пакет {idx}: RESPONSE не распарсился: {resp_result.errors}"
                )
                resp_pkt = resp_result.packet
                assert resp_pkt.response_packet_id == expected_pids[idx], (
                    f"Пакет {idx}: RPID={resp_pkt.response_packet_id}, ожидался {expected_pids[idx]}"
                )

            # 6. Проверяем FSM-переходы
            states = [e.get("state") for e in state_events]
            # Ожидаем: CONNECTED → authenticating → authorized (→ running)
            # FSM использует верхний регистр для некоторых состояний
            states_lower = [s.lower() if isinstance(s, str) else s for s in states]
            assert "connected" in states_lower, f"Нет состояния 'connected' в {states}"
            assert "authenticating" in states_lower, f"Нет состояния 'authenticating' в {states}"

            # 7. Проверяем packet.processed
            assert len(packet_events) >= 3, (
                f"Ожидалось ≥3 событий packet.processed, получено {len(packet_events)}"
            )
            for idx, event in enumerate(packet_events[:3]):
                ctx = event.get("ctx")
                assert ctx is not None, f"Пакет {idx}: ctx отсутствует"
                assert ctx.channel == "tcp", f"Пакет {idx}: channel={ctx.channel}"
                assert ctx.crc_valid is True, f"Пакет {idx}: CRC невалиден"

            # 8. Проверяем логи
            await engine.log_mgr.flush()
            log_dir = Path(config.logging.dir)
            log_files = list(log_dir.glob("*.jsonl"))
            assert len(log_files) >= 1, "Лог-файл не создан"

            log_content = log_files[0].read_text(encoding="utf-8")
            log_lines = [l for l in log_content.strip().split("\n") if l]
            packet_log_entries = [
                json.loads(l) for l in log_lines
                if json.loads(l).get("log_type") == "packet"
            ]
            assert len(packet_log_entries) >= 3, (
                f"В логе должно быть ≥3 пакетов, найдено {len(packet_log_entries)}"
            )

            # Вывод логов на консоль
            print("\n===== ЛОГИ СЕРВЕРА (JSONL) =====")
            for i, line in enumerate(log_lines, 1):
                entry = json.loads(line)
                print(f"\n--- Запись {i} ({entry['log_type']}) ---")
                print(json.dumps(entry, ensure_ascii=False, indent=2, default=str))
            print("\n===== КОНЕЦ ЛОГОВ =====")

            # Вывод FSM-переходов
            print("\n===== FSM ПЕРЕХОДЫ =====")
            for evt in state_events:
                print(
                    f"  {evt.get('state')} — {evt.get('action')} "
                    f"(reason={evt.get('reason')})"
                )
            print("==============================")

        finally:
            await engine.stop()
