"""Реестр версий EGTS протокола."""

from collections.abc import Callable

from libs.egts.protocol import IEgtsProtocol

_registry: dict[str, Callable[[], IEgtsProtocol]] = {}


def register_version(version: str, factory: Callable[[], IEgtsProtocol]) -> None:
    """Зарегистрировать фабрику для версии ГОСТ."""
    _registry[version] = factory


def get_protocol(version: str) -> IEgtsProtocol:
    """Получить экземпляр протокола по версии ГОСТ."""
    if version not in _registry:
        available = ", ".join(sorted(_registry.keys()))
        raise ValueError(
            f"Unknown EGTS version: {version!r}. Available: {available}"
        )
    return _registry[version]()


def available_versions() -> list[str]:
    """Список зарегистрированных версий."""
    return sorted(_registry.keys())
