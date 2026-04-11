"""Держит сервер запущенным пока не убьют процесс."""
import asyncio
from core.config import Config
from core.engine import CoreEngine
from core.event_bus import EventBus


async def main():
    config = Config(tcp_port=3001, gost_version="2015")
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)
    
    await engine.start()
    print("✅ Сервер запущен на порту 3001, ГОСТ 2015")
    print("Нажмите Ctrl+C для остановки")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await engine.stop()
        print("\n🔴 Сервер остановлен")


if __name__ == "__main__":
    asyncio.run(main())
