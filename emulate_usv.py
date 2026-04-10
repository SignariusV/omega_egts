"""Простой эмулятор УСВ — подключается к серверу и отправляет TERM_IDENTITY.

Использование::

    python emulate_usv.py [--port 3001] [--host 127.0.0.1]
"""

import argparse
import asyncio
import sys

# Пакет TERM_IDENTITY (AUTH) — реальный EGTS-пакет из тестов
TERM_IDENTITY_HEX = (
    "0100000B002E002A0001CC2700490080010101240001000000"
    "16383630383033303636343438333133303235303737303031"
    "373135363433390F3A"
)


async def main(host: str, port: int) -> None:
    packet_bytes = bytes.fromhex(TERM_IDENTITY_HEX)
    print(f"[Эмулятор УСВ] Подключение к {host}:{port}...")

    reader, writer = await asyncio.open_connection(host, port)
    print(f"[Эмулятор УСВ] Подключено! Отправляю TERM_IDENTITY ({len(packet_bytes)} байт)...")
    print(f"[Эмулятор УСВ] HEX: {packet_bytes.hex().upper()}")

    writer.write(packet_bytes)
    await writer.drain()
    print("[Эмулятор УСВ] Пакет отправлен. Жду ответ...")

    # Читаем ответ (сервер должен отправить RESPONSE)
    try:
        data = await asyncio.wait_for(reader.read(4096), timeout=10.0)
        if data:
            print(f"[Эмулятор УСВ] Получен ответ ({len(data)} байт): {data.hex().upper()}")
        else:
            print("[Эмулятор УСВ] Соединение закрыто без ответа")
    except asyncio.TimeoutError:
        print("[ЭМУЛЯТОР УСВ] Таймаут ожидания ответа")

    writer.close()
    await writer.wait_closed()
    print("[Эмулятор УСВ] Готово.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Эмулятор УСВ")
    parser.add_argument("--host", default="127.0.0.1", help="Адрес сервера")
    parser.add_argument("--port", type=int, default=3001, help="Порт сервера")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.host, args.port))
    except ConnectionRefusedError:
        print(f"[Эмулятор УСВ] Не удалось подключиться к {args.host}:{args.port}")
        print("[ЭМУЛЯТОР УСВ] Убедитесь, что сервер запущен: omega-egts start")
        sys.exit(1)
