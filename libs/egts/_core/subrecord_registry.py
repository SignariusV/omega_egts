"""Реестр парсеров подзаписей."""

import logging

from libs.egts._core.subrecord import SubrecordParser

logger = logging.getLogger(__name__)

_registry: dict[int, SubrecordParser] = {}


def register_parser(parser: SubrecordParser) -> None:
    """Зарегистрировать парсер подзаписи."""
    _registry[parser.srt] = parser


def get_parser(srt: int) -> SubrecordParser | None:
    """Получить парсер по SRT."""
    return _registry.get(srt)


def register_subrecord(cls: type[SubrecordParser]) -> type[SubrecordParser]:
    """Декоратор: автоматически регистрирует парсер при определении класса."""
    instance = cls()
    register_parser(instance)
    return cls
