"""Запуск сервера и эмулятора УСВ в одном процессе для ручного тестирования.

Использование:
    python test_server_with_emulator.py --auto        # автоматическая авторизация
    python test_server_with_emulator.py --interactive # интерактивный режим
    python test_server_with_emulator.py               # только сервер
"""
import argparse
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
    parser = argparse.ArgumentParser(description="Сервер + эмулятор УСВ")
    parser.add_argument("--auto", action="store_true", help="Авто-авторизация")
    parser.add_argument("--interactive", action="store_true", help="Интерактивный режим")
    args = parser.parse_args()

    print("=" * 60)
    print("  OMEGA_EGTS — Сервер + Эмулятор УСВ")
    print("=" * 60)

    # 1. Запускаем сервер
    config = Config(tcp_port=3001, gost_version="2015")
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    print("\n[СЕРВЕР] Запуск на порту 3001...")
    await engine.start()
    print("[СЕРВЕР] Готов принимать подключения")

    # 2. Подключаем эмулятор
    emulator = UsvEmulator(
        host="127.0.0.1",
        port=3001,
        auto_mode=args.auto,
        interactive=args.interactive,
    )

    print("\n[ЭМУЛЯТОР] Подключение...")
    await emulator.connect()
    print("[ЭМУЛЯТОР] Подключено")

    # 3. Запускаем задачи
    if args.auto:
        print("\n[АВТО] Запуск автоматической последовательности...")
        asyncio.create_task(emulator.run_auto_sequence())

    if args.interactive:
        print("\n[ИНТЕРАКТИВ] Введите 'help' для справки")
        asyncio.create_task(emulator.process_commands())

    # 4. Держим процесс живым
    print("\n[СЕРВЕР] Работаем... Нажмите Ctrl+C для остановки")
    try:
        while True:
            await asyncio.sleep(1)
            state = emulator.fsm.state.value
            print(f"  [{emulator.fsm.state.value}] PID={emulator.fsm._next_pid}, RN={emulator.fsm._next_rn}", end="\r")
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\n[СТОП] Остановка...")
    finally:
        await emulator.disconnect()
        await engine.stop()
        print("[СТОП] Всё остановлено")


if __name__ == "__main__":
    asyncio.run(main())
