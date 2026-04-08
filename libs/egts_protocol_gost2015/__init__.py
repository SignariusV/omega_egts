"""Реализация EGTS-протокола по ГОСТ 33465-2015

Конкретная реализация парсинга/сборки EGTS-пакетов.
Адаптируется к IEgtsProtocol из egts_protocol_iface.

Статус: В разработке (задачи 2.2–2.4).
"""

from .adapter import EgtsProtocol2015

__all__ = ["EgtsProtocol2015"]
