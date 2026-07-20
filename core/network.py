"""Утилиты для определения сетевых параметров локальной машины."""

import json
import logging
import subprocess
from ipaddress import IPv4Address, IPv4Network

logger = logging.getLogger(__name__)


def _get_active_interfaces() -> list[dict]:
    """Получить список активных сетевых интерфейсов с IPv4 адресами.

    Использует PowerShell Get-NetAdapter + Get-NetIPAddress.

    Returns:
        Список словарей с ключами: name, description, type, ip, prefix_len.
        type: 'Ethernet' | 'WiFi' | 'Bluetooth' | 'Unknown'
    """
    script = """
$adapters = Get-NetAdapter | Where-Object Status -eq Up
$result = @()
foreach ($adapter in $adapters) {
    $ips = Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notmatch '^169\\.254\\.' } |
        Select-Object -First 1
    if (-not $ips) { continue }
    $type = 'Ethernet'
    if ($adapter.Name -match 'Wi-Fi|Wireless|WiFi|WLAN') { $type = 'WiFi' }
    if ($adapter.Name -match 'Bluetooth') { $type = 'Bluetooth' }
    $result += [PSCustomObject]@{
        Name        = $adapter.Name
        Description = $adapter.InterfaceDescription
        Type        = $type
        IP          = $ips.IPAddress
        PrefixLen   = $ips.PrefixLength
    }
}
if ($result.Count -eq 0) { return '[]' }
return ($result | ConvertTo-Json -Compress)
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.debug("PowerShell недоступен или скрипт не выполнился")
        return []

    output = proc.stdout.strip()
    if not output or output == "[]":
        logger.debug("Активных сетевых интерфейсов с IPv4 не найдено")
        return []

    try:
        data = json.loads(output)
        if isinstance(data, dict):
            data = [data]
        logger.debug("Найдено активных интерфейсов: %d — %s", len(data), data)
        return data
    except json.JSONDecodeError:
        logger.debug("Ошибка парсинга JSON из PowerShell: %s", output[:200])
        return []


def _same_subnet(ip1: str, ip2: str, prefix: int = 24) -> bool:
    """Проверить, находятся ли два IP в одной подсети /prefix."""
    try:
        net = IPv4Network(f"{ip1}/{prefix}", strict=False)
        return IPv4Address(ip2) in net
    except (ValueError, TypeError):
        return False


def get_best_server_ip(exclude_ip: str | None = None) -> str | None:
    """Определить лучший локальный IPv4-адрес для EGTS-сервера.

    Приоритет:
      1. Ethernet-интерфейсы (кроме того, что в подсети ``exclude_ip``)
      2. Wi-Fi
      3. ``None`` — ни один интерфейс не активен

    Args:
        exclude_ip: IP-адрес, подсеть которого нужно исключить
                    (обычно IP-адрес CMW-500, чтобы не выбрать интерфейс,
                    ведущий к прибору, а не к EGTS-изделиям).

    Returns:
        IPv4-адрес или None.
    """
    interfaces = _get_active_interfaces()
    if not interfaces:
        logger.debug("Нет активных интерфейсов для выбора server_address")
        return None

    logger.debug("Выбор server_address, exclude_ip=%s", exclude_ip)

    def sort_key(iface: dict) -> tuple:
        is_eth = iface.get("Type") == "Ethernet"
        iface_ip = iface.get("IP", "")
        prefix_len = iface.get("PrefixLen", 24)

        excluded = bool(
            exclude_ip and is_eth and iface_ip
            and _same_subnet(iface_ip, exclude_ip, prefix_len)
        )

        is_wifi = iface.get("Type") == "WiFi"

        if excluded:
            logger.debug("  Исключён (подсеть CMW): %s (%s)", iface.get("Name"), iface_ip)

        if is_eth and not excluded:
            return (0, iface_ip)
        if is_wifi:
            return (1, iface_ip)
        return (2, iface_ip)

    interfaces.sort(key=sort_key)
    best = interfaces[0].get("IP", "")
    logger.debug("  Выбран: %s (%s)", interfaces[0].get("Name"), best)
    return best or None


def get_wifi_ip() -> str | None:
    """Определить IPv4-адрес Wi-Fi интерфейса (обратная совместимость)."""
    interfaces = _get_active_interfaces()
    for iface in interfaces:
        if iface.get("Type") == "WiFi":
            ip = iface.get("IP")
            logger.debug("get_wifi_ip: найден WiFi IP=%s", ip)
            return ip
    logger.debug("get_wifi_ip: WiFi интерфейс не найден")
    return None
