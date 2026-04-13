"""Полный интеграционный тест: сервер + эмулятор УСВ + сценарий авторизации."""
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus
from pathlib import Path

from scripts.emulators.emulate_usv import UsvEmulator


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

    # 2. Подключаем эмулятор с ЗАДЕРЖКОЙ — пусть сценарий успеет подписаться
    emulator = UsvEmulator(host="127.0.0.1", port=3001, auto_mode=False)

    print("\n[ЭМУЛЯТОР] Подключение...")
    await emulator.connect()
    print("[ЭМУЛЯТОР] Подключено — ждём 2с перед отправкой")

    # 3. Даём время на создание сессии
    await asyncio.sleep(1)

    # 4. Получаем connection_id
    sessions = engine.session_mgr.connections
    if not sessions:
        print("\n[ОШИБКА] Нет активных подключений!")
        await emulator.disconnect()
        await engine.stop()
        return

    connection_id = list(sessions.keys())[0]
    print(f"\n[СЦЕНАРИЙ] Connection ID: {connection_id}")

    # 5. Запускаем сценарий авторизации (он начнёт ожидание TERM_IDENTITY)
    scenario_path = str(Path("scenarios/auth"))
    print(f"[СЦЕНАРИЙ] Запуск: {scenario_path}")

    # Запускаем сценарий в фоне
    scenario_task = asyncio.create_task(
        engine.run_scenario(scenario_path, connection_id=connection_id)
    )

    # Даём сценарию 1 секунду чтобы подписаться на пакеты
    await asyncio.sleep(1)

    # 6. Теперь эмулятор отправляет TERM_IDENTITY + VEHICLE_DATA
    print("\n[ЭМУЛЯТОР] Запускаю автоматическую последовательность...")
    await emulator.run_auto_sequence()

    # 7. Ждём завершения сценария
    result = await scenario_task

    print(f"\n[СЦЕНАРИЙ] Результат: {result.get('status')}")
    print(f"[СЦЕНАРИЙ] Шаги: {result.get('steps_passed', 0)}/{result.get('steps_total', 0)}")
    if result.get('error'):
        print(f"[СЦЕНАРИЙ] Ошибка: {result['error']}")

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
