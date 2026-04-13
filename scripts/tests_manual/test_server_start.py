"""Тест запуска сервера."""
import asyncio
from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus


async def main():
    config = Config(tcp_port=3001)
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)
    
    try:
        await engine.start()
        print("✅ Сервер запущен")
        status = engine.get_status()
        print(f"Статус: {status}")
        await asyncio.sleep(2)
        print("Работает...")
    finally:
        await engine.stop()
        print("🔴 Сервер остановлен")


if __name__ == "__main__":
    asyncio.run(main())
