"""Интеграционный тест: сервер + эмулятор УСВ в одном процессе."""
import asyncio
import sys

from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus

# Добавляем корень проекта в path
sys.path.insert(0, ".")

from emulate_usv import UsvEmulator


async def main():
    print("=" * 60)
    print("  Интеграционный тест: OMEGA_EGTS сервер + эмулятор УСВ")
    print("=" * 60)

    # 1. Запускаем сервер
    config = Config(tcp_port=3001, gost_version="2015")
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    print("\n[СЕРВЕР] Запуск...")
    await engine.start()
    print("[СЕРВЕР] ✅ Запущен на порту 3001")

    # Небольшая задержка чтобы сервер точно начал слушать
    await asyncio.sleep(0.5)

    # 2. Запускаем эмулятор УСВ
    emulator = UsvEmulator(host="127.0.0.1", port=3001, auto_mode=True)

    print("\n[ЭМУЛЯТОР] Подключение...")
    await emulator.connect()
    print("[ЭМУЛЯТОР] ✅ Подключено")

    # 3. Запускаем автоматическую авторизацию
    asyncio.create_task(emulator.run_auto_sequence())

    # 4. Ждём завершения авторизации (10 секунд достаточно)
    print("\n[ТЕСТ] Ожидание завершения авторизации (10с)...")
    for i in range(10):
        await asyncio.sleep(1)
        state = emulator.fsm.state.value
        print(f"  [{i+1}с] FSM: {state}")
        if state == "RUNNING":
            print("\n[ТЕСТ] ✅ Авторизация успешна! УСВ в состоянии RUNNING")
            break

    # 5. Финальный статус
    print(f"\n[ФИНАЛ] Состояние эмулятора: {emulator.fsm.state.value}")
    print(f"[ФИНАЛ] Отправлено пакетов: PID дошёл до {emulator.fsm._next_pid}")

    # 6. Очистка
    await emulator.disconnect()
    await engine.stop()
    print("\n[ТЕСТ] ✅ Всё завершено успешно")


if __name__ == "__main__":
    asyncio.run(main())
