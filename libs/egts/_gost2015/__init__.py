"""Gost2015Protocol — полная реализация EGTS ГОСТ 2015."""

# Импорт регистрирует все парсеры
import libs.egts._gost2015.subrecords  # noqa: F401

from libs.egts.registry import register_version
from libs.egts._gost2015.protocol import Gost2015Protocol

# Регистрация
register_version("2015", lambda: Gost2015Protocol())
