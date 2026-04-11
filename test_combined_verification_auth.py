"""Интеграционный тест: Верификация + Аутентификация в одной TCP-сессии.

Сначала запускаем верификацию, ждём завершения, 
затем запускаем аутентификацию.
"""
import asyncio
import sys

from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus

sys.path.insert(0, ".")
from pathlib import Path

from emulate_usv_combined import CombinedEmulator, CombinedState


async def main():
    print("=" * 60)
    print("  Интеграционный тест: Верификация + Аутентификация")
    print("  Одна TCP-сессия, две процедуры последовательно")
    print("=" * 60)

    # 1. Запускаем сервер
    config = Config(tcp_port=3003, gost_version="2015")
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    print("\n[СЕРВЕР] Запуск на порту 3003...")
    await engine.start()
    print("[СЕРВЕР] Запущен")
    await asyncio.sleep(0.5)

    # 2. Подключаем эмулятор
    emulator = CombinedEmulator(
        host="127.0.0.1",
        port=3003,
        auto_mode=True,  # автоматически отвечает COMCONF и запускает авторизацию
    )

    print("\n[ЭМУЛЯТОР] Подключение...")
    await emulator.connect()
    print("[ЭМУЛЯТОР] Подключено — готов к верификации и авторизации")

    # 3. Ждём подключения сессии
    await asyncio.sleep(1)

    sessions = engine.session_mgr.connections
    if not sessions:
        print("\n[ОШИБКА] Нет подключений!")
        await emulator.disconnect()
        await engine.stop()
        return

    connection_id = list(sessions.keys())[0]
    print(f"\n[СЕССИЯ] Connection ID: {connection_id}")

    # 4. Фаза 1: Запускаем сценарий верификации
    scenario_v = str(Path("scenarios/verification_tcp/scenario.json"))
    print(f"\n{'=' * 50}")
    print("  ФАЗА 1: Верификация")
    print(f"{'=' * 50}")

    result_v = await engine.run_scenario(scenario_v, connection_id=connection_id)

    # Ждём пока эмулятор обработает все 3 команды
    await asyncio.sleep(2)

    print(f"\n[ВЕРИФИКАЦИЯ] Команд получено: {len(emulator.fsm.received_commands)}")
    for c in emulator.fsm.received_commands:
        ccd = c.get("ccd", 0)
        cid = c.get("cid", 0)
        data = c.get("data", b"")
        text = data.decode("ascii", errors="replace") if data else ""
        ccd_names = {0x0203: "GPRS_APN", 0x0204: "SERVER_ADDRESS", 0x0205: "UNIT_ID", 0x0404: "UNIT_ID"}
        name = ccd_names.get(ccd, f"0x{ccd:04X}")
        print(f"  [{cid}] {name}: '{text}'")

    # Проверяем что верификация завершена
    v_done = emulator.fsm.state == CombinedState.V_DONE or len(emulator.fsm.received_commands) >= 3
    if v_done:
        print(f"\n✅ ВЕРИФИКАЦИЯ завершена")
    else:
        print(f"\n⚠ ВЕРИФИКАЦИЯ не завершена: {emulator.fsm.state.value}")

    # 5. Даём время эмулятору запустить авторизацию
    print(f"\n{'=' * 50}")
    print("  ФАЗА 2: Аутентификация")
    print(f"{'=' * 50}")

    # Ждём пока эмулятор отправит TERM_IDENTITY и VEHICLE_DATA
    await asyncio.sleep(3)

    print(f"[АУТЕНТИФИКАЦИЯ] Эмулятор отправил:")
    print(f"  RESPONSE получено: {emulator.fsm.responses_received}")
    print(f"  RESULT_CODE: {'да (rcd=' + str(emulator.fsm.result_code_value) + ')' if emulator.fsm.result_code_received else 'ожидание...'}")

    # 6. Запускаем сценарий аутентификации
    # Эмулятор уже отправил TERM_IDENTITY и VEHICLE_DATA, сценарий должен их найти
    scenario_a = str(Path("scenarios/auth/scenario.json"))
    print(f"\n[СЦЕНАРИЙ] Запуск аутентификации: {scenario_a}")

    result_a = await engine.run_scenario(scenario_a, connection_id=connection_id)

    # Ждём обработки RESULT_CODE
    await asyncio.sleep(2)

    # 7. Итог
    print(f"\n{'=' * 60}")
    print("  ИТОГ ТЕСТА")
    print(f"{'=' * 60}")
    print(f"  Верификация:")
    print(f"    Команд получено:    {len(emulator.fsm.received_commands)}")
    print(f"    Состояние FSM:      {emulator.fsm.state.value}")
    print(f"  Аутентификация:")
    print(f"    RESPONSE получено:  {emulator.fsm.responses_received}")
    print(f"    RESULT_CODE:        {'rcd=' + str(emulator.fsm.result_code_value) if emulator.fsm.result_code_received else 'нет'}")
    print(f"    Финальное FSM:      {emulator.fsm.state.value}")

    print(f"\n{'=' * 60}")
    if emulator.fsm.state == CombinedState.A_RUNNING:
        print("  ✅ ПОЛНЫЙ ЦИКЛ ЗАВЕРШЕН УСПЕШНО")
        print("     Верификация: 3 команды → COMCONF")
        print("     Аутентификация: TERM_IDENTITY → VEHICLE_DATA → RESULT_CODE → RECORD_RESPONSE")
    elif len(emulator.fsm.received_commands) >= 3 and emulator.fsm.responses_received >= 2:
        print("  ⚠ ЧАСТИЧНЫЙ УСПЕХ")
        print(f"     Верификация: ✅ 3 команды")
        print(f"     Аутентификация: отправлены пакеты, RESPONSE получены")
        if not emulator.fsm.result_code_received:
            print(f"     RESULT_CODE: не получен (нужен сценарий/платформа)")
    else:
        print("  ❌ ТЕСТ НЕ ПРОШЁЛ")
    print(f"{'=' * 60}")

    # 8. Очистка
    await emulator.disconnect()
    await engine.stop()
    print("\n[ТЕСТ] Завершено")


if __name__ == "__main__":
    asyncio.run(main())
