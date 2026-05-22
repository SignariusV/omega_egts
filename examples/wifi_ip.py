"""
Скрипт для определения IPv4-адреса Wi-Fi соединения на Windows.
"""

import subprocess
import re


def get_wifi_ip() -> str | None:
    """Возвращает IPv4-адрес Wi-Fi адаптера или None, если не найден."""
    try:
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            encoding="cp866",
            check=True,
        )
    except subprocess.CalledProcessError:
        return None

    # Ищем секцию Wi-Fi адаптера
    wifi_section = re.search(
        r"(Беспроводная локальная сеть|Wi-Fi).*?(?=\n\S|\Z)",
        result.stdout,
        re.DOTALL | re.IGNORECASE,
    )

    if not wifi_section:
        # Попробуем английскую версию Windows
        wifi_section = re.search(
            r"Wireless LAN adapter Wi-Fi.*?(?=\n\S|\Z)",
            result.stdout,
            re.DOTALL | re.IGNORECASE,
        )

    if not wifi_section:
        return None

    # Ищем IPv4-адрес в секции
    ip_match = re.search(
        r"IPv4[^-].*?:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
        wifi_section.group(),
    )
    if ip_match:
        return ip_match.group(1)

    # Альтернативный паттерн (английская версия)
    ip_match = re.search(
        r"IPv4 Address[^:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
        wifi_section.group(),
    )
    return ip_match.group(1) if ip_match else None


if __name__ == "__main__":
    ip = get_wifi_ip()
    if ip:
        print(f"Wi-Fi IPv4: {ip}")
    else:
        print("Wi-Fi адаптер не найден или не подключён")
