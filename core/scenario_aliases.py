"""Система строковых алиасов для сценариев EGTS.

Позволяет использовать читаемые строковые имена вместо магических чисел
в JSON-сценариях. Алиасы резолвятся в числа на основе IntEnum из
libs/egts/types.py и словаря COMMAND_CODES.

Пример:
    # До (магические числа)
    "subrecord_type": 51,
    "ct": 5,
    "ccd": 1026

    # После (читаемые алиасы)
    "subrecord_type": "COMMAND_DATA",
    "ct": "COM",
    "ccd": "EGTS_SERVER_ADDRESS"
"""

from __future__ import annotations

from typing import Any

from libs.egts.types import (
    ActionType,
    Charset,
    CommandType,
    ConfirmationType,
    PacketType,
    ResultCode,
    ServiceType,
    SubrecordType,
    COMMAND_CODES,
)

# Маппинг: имя поля → Enum или dict для резолва
_FIELD_ALIASES: dict[str, Any] = {
    "packet_type": PacketType,
    "service_type": ServiceType,
    "recipient_service_type": ServiceType,
    "subrecord_type": SubrecordType,
    "ct": CommandType,
    "cct": ConfirmationType,
    "act": ActionType,
    "ccd": COMMAND_CODES,  # dict[int, str] — нужен обратный маппинг
    "chs": Charset,
    "rcd": ResultCode,
}

# Обратный маппинг для CCD: имя_команды → код
_CCD_REVERSE: dict[str, int] = {v: k for k, v in COMMAND_CODES.items()}


def resolve_alias(field: str, value: Any) -> Any:
    """Резолвить строковый алиас в числовое значение.

    Если value — строка и field известен в _FIELD_ALIASES,
    возвращает соответствующее числовое значение.
    Иначе возвращает value без изменений.

    Args:
        field: Имя поля (например, "ct", "ccd", "subrecord_type")
        value: Значение из JSON (может быть str или int)

    Returns:
        Числовое значение если алиас найден, иначе исходное value.
    """
    if not isinstance(value, str):
        return value

    alias_map = _FIELD_ALIASES.get(field)
    if alias_map is None:
        return value

    if alias_map is COMMAND_CODES:
        # CCD — обратный маппинг из имени в код
        return _CCD_REVERSE.get(value, value)

    # IntEnum — поиск по имени
    try:
        return alias_map[value].value
    except (KeyError, TypeError):
        return value


def resolve_aliases_recursive(obj: Any, path: str = "") -> Any:
    """Рекурсивно резолвить алиасы во вложенной структуре.

    Проходит по всем dict и list, резолвит значения полей,
    имена которых известны в _FIELD_ALIASES.

    Args:
        obj: JSON-объект (dict, list, или примитив)
        path: Текущий путь (для отладки)

    Returns:
        Тот же объект с резолвленными алиасами.
    """
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else key
            # Резолвим значение если это известное поле
            if key in _FIELD_ALIASES:
                result[key] = resolve_alias(key, value)
            else:
                # Рекурсивно обрабатываем вложенные структуры
                result[key] = resolve_aliases_recursive(value, new_path)
        return result

    if isinstance(obj, list):
        return [resolve_aliases_recursive(item, f"{path}[]") for item in obj]

    return obj
