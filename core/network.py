"""Утилиты для определения сетевых параметров локальной машины."""

import re
import subprocess


def get_wifi_ip() -> str | None:
    """Определить IPv4-адрес Wi-Fi интерфейса.

    Выполняет ipconfig, находит секцию Wi-Fi адаптера
    и извлекает из неё IPv4-адрес.

    Returns:
        IPv4-адрес или None, если Wi-Fi не подключён.
    """
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

    wifi_section = re.search(
        r"(Беспроводная локальная сеть|Wi-Fi).*?(?=\n\S|\Z)",
        result.stdout,
        re.DOTALL | re.IGNORECASE,
    )

    if not wifi_section:
        wifi_section = re.search(
            r"Wireless LAN adapter Wi-Fi.*?(?=\n\S|\Z)",
            result.stdout,
            re.DOTALL | re.IGNORECASE,
        )

    if not wifi_section:
        return None

    ip_match = re.search(
        r"IPv4[^-].*?:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
        wifi_section.group(),
    )
    if ip_match:
        return ip_match.group(1)

    ip_match = re.search(
        r"IPv4 Address[^:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
        wifi_section.group(),
    )
    return ip_match.group(1) if ip_match else None
