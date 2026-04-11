"""Интеграционный тест верификации: сервер + эмулятор + сценарий.

Автоматически:
1. Запускает сервер
2. Подключает эмулятор УСВ (auto_mode — отвечает COMCONF)
3. Отправляет TERM_IDENTITY для авторизации
4. Запускает сценарий верификации (3 команды → 3 COMCONF)
5. Проверяет что все шаги пройдены
"""
import asyncio
import sys

from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus

sys.path.insert(0, ".")
from pathlib import Path

from emulate_usv_verification import VerificationEmulator


async def main():
    print("=" * 60)
    print("  Интеграционный тест: Верификация по TCP")
    print("=" * 60)

    # 1. Запускаем сервер
    config = Config(tcp_port=3002, gost_version="2015")  # отдельный порт
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    print("\n[СЕРВЕР] Запуск на порту 3002...")
    await engine.start()
    print("[СЕРВЕР] Запущен")
    await asyncio.sleep(0.5)

    # 2. Подключаем эмулятор
    emulator = VerificationEmulator(
        host="127.0.0.1",
        port=3002,
        auto_mode=True,  # автоматически отвечает COMCONF
    )

    print("\n[ЭМУЛЯТОР] Подключение...")
    await emulator.connect()
    print("[ЭМУЛЯТОР] Подключено")

    # 3. Ждём пока эмулятор подключится и сессия создастся
    await asyncio.sleep(1)

    # 4. Находим connection_id
    sessions = engine.session_mgr.connections
    if not sessions:
        print("\n[ОШИБКА] Нет подключений!")
        await emulator.disconnect()
        await engine.stop()
        return

    connection_id = list(sessions.keys())[0]
    print(f"\n[СЦЕНАРИЙ] Connection ID: {connection_id}")

    # 5. Запускаем сценарий верификации (путь к scenario.json)
    scenario_path = str(Path("scenarios/verification_tcp/scenario.json"))
    print(f"[СЦЕНАРИЙ] Запуск: {scenario_path}")

    result = await engine.run_scenario(scenario_path, connection_id=connection_id)

    status = result.get("status", "unknown")
    steps_passed = result.get("steps_passed", 0)
    steps_total = result.get("steps_total", 0)
    error = result.get("error")

    print(f"\n[СЦЕНАРИЙ] Статус: {status}")
    print(f"[СЦЕНАРИЙ] Шаги: {steps_passed}/{steps_total}")
    if error:
        print(f"[СЦЕНАРИЙ] Ошибка: {error}")

    # 6. Ждём обработки эмулятором
    await asyncio.sleep(2)

    # 7. Финальный статус
    print(f"\n[ЭМУЛЯТОР] Состояние: {emulator.fsm.state.value}")
    print(f"[ЭМУЛЯТОР] Команд получено: {len(emulator.fsm.received_commands)}")
    for c in emulator.fsm.received_commands:
        ccd = c.get("ccd", 0)
        cid = c.get("cid", 0)
        data = c.get("data", b"")
        text = data.decode("ascii", errors="replace") if data else ""
        ccd_names = {0x0203: "GPRS_APN", 0x0204: "SERVER_ADDRESS", 0x0205: "UNIT_ID"}
        name = ccd_names.get(ccd, f"0x{ccd:04X}")
        print(f"  [{cid}] {name}: '{text}'")

    # 8. Итог
    print(f"\n{'=' * 40}")
    if emulator.fsm.state.value == "VERIFIED" and status == "PASS":
        print("  ✅ ВЕРИФИКАЦИЯ ПРОШЛА УСПЕШНО")
    else:
        print(f"  ⚠ Сценарий: {status}, Эмулятор: {emulator.fsm.state.value}")
    print(f"{'=' * 40}")

    # 9. Очистка
    await emulator.disconnect()
    await engine.stop()
    print("\n[ТЕСТ] Завершено")


if __name__ == "__main__":
    asyncio.run(main())
