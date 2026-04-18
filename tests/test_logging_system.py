#!/usr/bin/env python3
"""Тестовый скрипт для проверки работы системы логирования.

Запускает программу, эмулирует подключение клиента и отправку пакетов,
затем проверяет наличие файлов логов в папке logs/.

Использование:
    python test_logging_system.py
"""

import asyncio
import sys
import time
from pathlib import Path


async def test_logging():
    """Основной тест системы логирования."""
    from core.config import CmwConfig, Config
    from core.engine import CoreEngine
    from core.event_bus import EventBus

    # Очистка предыдущих логов
    log_dir = Path("logs")
    if log_dir.exists():
        for f in log_dir.glob("*.jsonl"):
            f.unlink()

    print("=" * 60)
    print("ТЕСТ СИСТЕМЫ ЛОГИРОВАНИЯ")
    print("=" * 60)

    # 1. Инициализация системы
    print("\n[1] Инициализация системы...")
    config = Config(cmw500=CmwConfig(ip=None))  # Отключаем CMW-500
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    await engine.start()
    print(f"✅ Engine запущен: {engine.is_running}")
    print(f"✅ LogManager создан: {engine.log_mgr is not None}")
    if engine.log_mgr:
        print(f"   Директория логов: {engine.log_mgr._log_dir}")

    # 2. Эмуляция события подключения
    print("\n[2] Эмуляция подключения клиента...")
    await bus.emit(
        "connection.changed",
        {
            "connection_id": "test-conn-1",
            "state": "CONNECTED",
            "prev_state": "DISCONNECTED",
            "timestamp": time.monotonic(),
        }
    )
    print("✅ Событие connection.changed отправлено")

    # 3. Эмуляция получения пакета через raw.packet.received
    print("\n[3] Эмуляция получения пакета (raw.packet.received)...")
    test_packet = b"\x01\x00\x01\x00\x00\x00\xA1\xB2\xC3\xD4"
    await bus.emit(
        "raw.packet.received",
        {
            "raw": test_packet,
            "channel": "tcp",
            "connection_id": "test-conn-1",
        }
    )
    print(f"✅ Событие raw.packet.received отправлено ({len(test_packet)} байт)")

    # Небольшая задержка для обработки pipeline
    await asyncio.sleep(0.1)

    # 4. Проверка буфера LogManager
    print("\n[4] Проверка буфера LogManager...")
    if engine.log_mgr:
        stats = engine.log_mgr.get_stats()
        print(f"   Записей в буфере: {stats['total']}")
        print(f"   - Пакеты: {stats['packets']}")
        print(f"   - Подключения: {stats['connections']}")
        print(f"   - Сценарии: {stats['scenarios']}")

    # 5. Принудительный сброс буфера
    print("\n[5] Принудительный сброс буфера (flush)...")
    if engine.log_mgr:
        await engine.log_mgr.flush()
        print("✅ Буфер сброшен на диск")

    # 6. Проверка наличия файлов логов
    print("\n[6] Проверка файлов логов...")
    log_files = list(log_dir.glob("*.jsonl"))
    if log_files:
        print(f"✅ Найдено файлов логов: {len(log_files)}")
        for lf in log_files:
            print(f"   - {lf.name}")
            content = lf.read_text(encoding="utf-8")
            lines = [l for l in content.strip().splitlines() if l.strip()]
            print(f"     Записей: {len(lines)}")
    else:
        print("❌ Файлы логов НЕ найдены!")
        return False

    # 7. Проверка содержимого логов
    print("\n[7] Анализ содержимого логов...")
    if log_files:
        content = log_files[0].read_text(encoding="utf-8")
        has_packet = '"log_type": "packet"' in content
        has_connection = '"log_type": "connection"' in content
        has_hex = test_packet.hex().upper() in content

        print(f"   - Записи о пакетах: {'✅' if has_packet else '❌'}")
        print(f"   - Записи о подключениях: {'✅' if has_connection else '❌'}")
        print(f"   - Hex пакета в логе: {'✅' if has_hex else '❌'}")

        if not (has_packet and has_connection and has_hex):
            print("\n⚠️ ВНИМАНИЕ: Не все ожидаемые записи найдены в логах!")
            print(f"\nСодержимое файла:\n{content}")
            return False

    # 8. Остановка системы
    print("\n[8] Остановка системы...")
    await engine.stop()
    print("✅ Engine остановлен")

    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕН УСПЕШНО ✅")
    print("=" * 60)
    return True


def main():
    """Точка входа."""
    try:
        success = asyncio.run(test_logging())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
