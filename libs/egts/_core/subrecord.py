"""Абстракция парсера подзаписи."""

from typing import Protocol


class SubrecordParser(Protocol):
    """Интерфейс парсера подзаписи (SRT)."""

    @property
    def srt(self) -> int:
        """Тип подзаписи (Subrecord Type)."""
        ...

    @property
    def name(self) -> str:
        """Человекочитаемое имя (например 'TERM_IDENTITY')."""
        ...

    def parse(self, raw: bytes) -> dict[str, object] | bytes:
        """Разобрать сырые байты в dict (или вернуть bytes для бинарных)."""
        ...

    def serialize(self, data: dict[str, object] | bytes) -> bytes:
        """Сериализовать dict обратно в байты."""
        ...
