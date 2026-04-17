"""ScenarioParser abstraction — Protocol, V1 parser, Registry, Factory.

Абстракция над форматом сценариев, аналогичная IEgtsProtocol для ГОСТ.
Позволяет добавлять новые версии формата сценариев без изменения ScenarioManager.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# --- Protocol ---


@runtime_checkable
class IScenarioParser(Protocol):
    """Интерфейс парсера формата сценариев."""

    def load(self, data: dict[str, Any]) -> ScenarioMetadata:
        """Загрузить и распарсить данные сценария.

        Args:
            data: Распарсенный JSON сценария.

        Returns:
            ScenarioMetadata — метаданные сценария.
        """
        ...

    def validate(self, data: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Валидировать формат данных сценария.

        Args:
            data: Распарсенный JSON сценария.

        Returns:
            Кортеж (errors, warnings). Пустой errors = валидно.
        """
        ...

    def get_steps(self) -> list[StepDefinition]:
        """Вернуть список шагов после загрузки.

        Returns:
            Список StepDefinition.
        """
        ...

    def get_metadata(self) -> ScenarioMetadata:
        """Вернуть метаданные сценария после загрузки.

        Returns:
            ScenarioMetadata.
        """
        ...


# --- Data models ---


@dataclass
class ScenarioMetadata:
    """Метаданные сценария."""

    name: str
    version: str
    gost_version: str | None
    timeout: float
    description: str | None
    channels: list[str] = field(default_factory=list)


@dataclass
class StepDefinition:
    """Определение шага сценария.

    Каноническая форма — не зависит от версии парсера.
    Дополнительные поля версии хранятся в extra.
    """

    name: str
    type: str  # send, expect, wait, check
    channel: str | None  # tcp, sms, None
    timeout: float | None
    checks: dict[str, Any] = field(default_factory=dict)
    capture: dict[str, str] = field(default_factory=dict)
    packet_file: str | None = None
    build: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# --- ScenarioParserV1 ---


_VALID_STEP_TYPES = {"send", "expect", "wait", "check"}
_VALID_CHANNELS = {"tcp", "sms", None}
_DEFAULT_TIMEOUT = 30.0


class ScenarioParserV1:
    """Парсер формата сценариев версии 1.

    Формат V1:
    - scenario_version: "1"
    - steps с type/send/expect, channel (tcp/sms), checks, capture, packet_file, build
    """

    def __init__(self) -> None:
        self._metadata: ScenarioMetadata | None = None
        self._steps: list[StepDefinition] = []

    def validate(self, data: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Валидировать формат данных сценария V1.

        Проверки:
        - steps существует и не пуст
        - type ∈ {send, expect, wait, check}
        - channel ∈ {tcp, sms, None}
        - capture paths корректны
        - timeout предупреждение при отсутствии
        - duplicate step names предупреждение

        Returns:
            Кортеж (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Deprecated version key detection
        if "scenario_version" not in data and "version" in data:
            warnings.append(
                "Deprecated 'version' key detected; use 'scenario_version' instead"
            )

        # steps exists
        steps = data.get("steps")
        if not steps or not isinstance(steps, list):
            errors.append("Missing or invalid 'steps' field")
            return errors, warnings

        # Проверка каждого шага
        seen_names: set[str] = set()
        for i, step in enumerate(steps):
            prefix = f"steps[{i}]"

            # type
            step_type = step.get("type")
            if not step_type:
                errors.append(f"{prefix}: Missing 'type' field")
            elif step_type not in _VALID_STEP_TYPES:
                errors.append(
                    f"{prefix}: Invalid type '{step_type}', "
                    f"expected one of {sorted(_VALID_STEP_TYPES)}"
                )

            # channel
            channel = step.get("channel")
            if channel not in _VALID_CHANNELS:
                errors.append(
                    f"{prefix}: Invalid channel '{channel}', "
                    f"expected one of {sorted(c for c in _VALID_CHANNELS if c is not None)} or None"
                )

            # timeout warning
            if "timeout" not in step:
                warnings.append(
                    f"{prefix}: Missing 'timeout' (default {_DEFAULT_TIMEOUT}s will be used)"
                )

            # duplicate names warning
            step_name = step.get("name", "")
            if step_name in seen_names:
                warnings.append(f"{prefix}: Duplicate step name '{step_name}'")
            seen_names.add(step_name)

        return errors, warnings

    def load(self, data: dict[str, Any]) -> ScenarioMetadata:
        """Загрузить и распарсить данные сценария V1.

        Args:
            data: Распарсенный JSON сценария.

        Returns:
            ScenarioMetadata — метаданные сценария.
        """
        # Metadata
        self._metadata = ScenarioMetadata(
            name=data.get("name", "Unnamed Scenario"),
            version=data.get("scenario_version", "1"),
            gost_version=data.get("gost_version"),
            timeout=float(data.get("timeout", _DEFAULT_TIMEOUT)),
            description=data.get("description"),
            channels=data.get("channels", []),
        )

        # Steps
        self._steps = []
        for step_data in data.get("steps", []):
            step = StepDefinition(
                name=step_data.get("name", ""),
                type=step_data.get("type", ""),
                channel=step_data.get("channel"),
                timeout=step_data.get("timeout"),
                checks=step_data.get("checks", {}),
                capture=step_data.get("capture", {}),
                packet_file=step_data.get("packet_file"),
                build=step_data.get("build"),
                extra={
                    k: v
                    for k, v in step_data.items()
                    if k
                    not in (
                        "name",
                        "type",
                        "channel",
                        "timeout",
                        "checks",
                        "capture",
                        "packet_file",
                        "build",
                    )
                },
            )
            self._steps.append(step)

        return self._metadata

    def get_steps(self) -> list[StepDefinition]:
        """Вернуть список шагов после загрузки."""
        return list(self._steps)

    def get_metadata(self) -> ScenarioMetadata:
        """Вернуть метаданные сценария после загрузки."""
        if self._metadata is None:
            raise RuntimeError("load() must be called before get_metadata()")
        return self._metadata


# --- ScenarioParserRegistry ---


class ScenarioParserRegistry:
    """Реестр парсеров по версиям формата сценариев.

    Пример использования::

        registry = ScenarioParserRegistry()
        registry.register("1", ScenarioParserV1)
        parser_cls = registry.get("1")  # ScenarioParserV1
    """

    def __init__(self) -> None:
        self._parsers: dict[str, type[IScenarioParser]] = {}

    def register(self, version: str, parser_cls: type[IScenarioParser]) -> None:
        """Зарегистрировать класс парсера для версии.

        Args:
            version: Строка версии (например, "1", "2").
            parser_cls: Класс, реализующий IScenarioParser.
        """
        self._parsers[version] = parser_cls

    def get(self, version: str) -> type[IScenarioParser]:
        """Получить класс парсера для версии.

        Args:
            version: Строка версии.

        Returns:
            Класс парсера.

        Raises:
            KeyError: Если версия не зарегистрирована.
        """
        return self._parsers[version]

    def __iter__(self) -> Iterator[tuple[str, type[IScenarioParser]]]:
        """Итерация по всем зарегистрированным версиям."""
        yield from self._parsers.items()


# --- ScenarioParserFactory ---


class ScenarioParserFactory:
    """Фабрика парсеров сценариев.

    Читает scenario_version из данных и создаёт нужный парсер.
    """

    def __init__(self, registry: ScenarioParserRegistry) -> None:
        """Создать фабрику.

        Args:
            registry: Реестр парсеров.
        """
        self._registry = registry

    def create(self, version: str) -> IScenarioParser:
        """Создать экземпляр парсера по версии.

        Args:
            version: Строка версии (например, "1").

        Returns:
            Экземпляр парсера.

        Raises:
            NotImplementedError: Если версия не поддерживается.
        """
        try:
            parser_cls = self._registry.get(version)
        except KeyError as exc:
            raise NotImplementedError(
                f"Scenario format version '{version}' is not supported"
            ) from exc
        return parser_cls()

    def detect_and_create(self, data: dict[str, Any]) -> IScenarioParser:
        """Определить версию из данных и создать парсер.

        Args:
            data: Распарсенный JSON сценария.

        Returns:
            Экземпляр парсера.

        Raises:
            NotImplementedError: Если версия не поддерживается.
        """
        version = data.get("scenario_version", "1")
        return self.create(version)
