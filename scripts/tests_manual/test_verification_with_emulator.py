"""Сервер + эмулятор УСВ для сценария верификации в одном процессе.

Запускает сервер OMEGA_EGTS и эмулятор УСВ который автоматически
отвечает COMCONF на команды верификации (APN, адрес, UNIT_ID).

Использование:
    python test_verification_with_emulator.py --auto        # автоматическая верификация
    python test_verification_with_emulator.py --interactive # ручной режим
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

from scripts.emulators.emulate_usv_verification import VerificationEmulator


async def main():
    parser = argparse.ArgumentParser(description="Сервер + эмулятор верификации")
    parser.add_argument("--auto", action="store_true", help="Авто-верификация")
    parser.add_argument("--interactive", action="store_true", help="Интерактивный режим")
    args = parser.parse_args()

    print("=" * 60)
    print("  OMEGA_EGTS — Сервер + Эмулятор верификации (TCP)")
    print("=" * 60)

    # 1. Запускаем сервер
    config = Config(tcp_port=3001, gost_version="2015")
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    print("\n[СЕРВЕР] Запуск на порту 3001...")
    await engine.start()
    print("[СЕРВЕР] Готов принимать подключения")

    # 2. Подключаем эмулятор
    emulator = VerificationEmulator(
        host="127.0.0.1",
        port=3001,
        auto_mode=args.auto,
        interactive=args.interactive,
    )

    print("\n[ЭМУЛЯТОР] Подключение...")
    await emulator.connect()
    print("[ЭМУЛЯТОР] Подключено — ждёт команд верификации")

    if args.auto:
        print("[АВТО] Автоматический режим включён")

    if args.interactive:
        print("\n[ИНТЕРАКТИВ] Введите 'help' для справки")
        asyncio.create_task(emulator.process_commands())

    # 3. Держим процесс живым и мониторим
    print("\n[СЕРВЕР] Работаем... Нажмите Ctrl+C для остановки")
    print("[ПОДСКАЗКА] Запустите сценарий верификации:")
    print("  omega-egts run-scenario scenarios/verification_tcp")
    try:
        while True:
            await asyncio.sleep(1)
            state = emulator.fsm.state.value
            cmds = len(emulator.fsm.received_commands)
            print(f"  [{state}] Команд: {cmds}/3", end="\r")

            if state == "VERIFIED":
                print(f"\n\n[ВЕРИФИКАЦИЯ] ✅ УСВ прошло все 3 команды!")
                print(f"  Полученные команды:")
                for c in emulator.fsm.received_commands:
                    ccd = c.get("ccd", 0)
                    cid = c.get("cid", 0)
                    data = c.get("data", b"")
                    text = data.decode("ascii", errors="replace") if data else ""
                    ccd_names = {0x0203: "GPRS_APN", 0x0204: "SERVER_ADDRESS", 0x0205: "UNIT_ID"}
                    name = ccd_names.get(ccd, f"0x{ccd:04X}")
                    print(f"    [{cid}] {name}: '{text}'")
                # Продолжаем работать после верификации
                await asyncio.sleep(5)
                break
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\n[СТОП] Остановка...")
    finally:
        await emulator.disconnect()
        await engine.stop()
        print("[СТОП] Всё остановлено")


if __name__ == "__main__":
    asyncio.run(main())
