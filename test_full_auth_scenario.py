"""Полный интеграционный тест: сервер + эмулятор УСВ + сценарий авторизации."""
import asyncio
import sys

from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus

sys.path.insert(0, ".")
from pathlib import Path

from emulate_usv import UsvEmulator


async def main():
    print("=" * 60)
    print("  Полный интеграционный тест")
    print("  Сервер + Эмулятор УСВ + Сценарий авторизации")
    print("=" * 60)

    # 1. Запускаем сервер
    config = Config(tcp_port=3001, gost_version="2015")
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    print("\n[СЕРВЕР] Запуск...")
    await engine.start()
    print("[СЕРВЕР] Запущен на порту 3001")
    await asyncio.sleep(0.5)

    # 2. Подключаем эмулятор
    emulator = UsvEmulator(host="127.0.0.1", port=3001, auto_mode=True)

    print("\n[ЭМУЛЯТОР] Подключение...")
    await emulator.connect()
    print("[ЭМУЛЯТОР] Подключено")

    # 3. Ждём пока эмулятор отправит TERM_IDENTITY и VEHICLE_DATA
    await asyncio.sleep(3)

    # 4. Получаем connection_id эмулятора
    sessions = engine.session_mgr.connections
    if not sessions:
        print("\n[ОШИБКА] Нет активных подключений!")
        await emulator.disconnect()
        await engine.stop()
        return

    connection_id = list(sessions.keys())[0]
    print(f"\n[СЦЕНАРИЙ] Connection ID: {connection_id}")

    # 5. Запускаем сценарий авторизации
    scenario_path = str(Path("scenarios/auth"))
    print(f"[СЦЕНАРИЙ] Запуск: {scenario_path}")

    result = await engine.run_scenario(scenario_path, connection_id=connection_id)

    print(f"\n[СЦЕНАРИЙ] Результат: {result.get('status')}")
    print(f"[СЦЕНАРИЙ] Шаги: {result.get('steps_passed', 0)}/{result.get('steps_total', 0)}")

    # 6. Ждём пока эмулятор обработает RESULT_CODE
    await asyncio.sleep(2)

    # 7. Финальный статус
    print(f"\n[ФИНАЛ] Состояние эмулятора: {emulator.fsm.state.value}")

    # 8. Очистка
    await emulator.disconnect()
    await engine.stop()
    print("\n[ТЕСТ] Завершено")


if __name__ == "__main__":
    asyncio.run(main())
