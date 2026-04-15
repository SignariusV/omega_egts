"""ScenarioManager, ScenarioContext, StepFactory — система сценариев.

ExpectStep — ожидание пакета с проверкой полей и capture переменных.
SendStep — отправка пакета из файла или build-template.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from core.event_bus import EventBus
from core.scenario_parser import (
    IScenarioParser,
    ScenarioMetadata,
    ScenarioParserFactory,
    StepDefinition,
)

logger = logging.getLogger(__name__)


# --- Variable ---


@dataclass
class Variable:
    """Переменная сценария с TTL."""

    value: Any
    ttl: float | None  # Время жизни в секундах (None = бессрочно)
    created_at: float  # timestamp создания

    @property
    def is_expired(self) -> bool:
        """Проверить, истёк ли TTL."""
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl


@dataclass
class StepHistoryEntry:
    """Запись в истории выполнения шага."""

    step_name: str
    result: str  # PASS, FAIL, TIMEOUT, ERROR
    duration: float = 0.0
    details: str | None = None


# --- ScenarioContext ---


class ScenarioContext:
    """Контекст выполнения сценария.

    Хранит переменные, историю выполнения, connection_id.
    Поддерживает TTL переменных и подстановку шаблонов {{var}}.
    """

    def __init__(
        self,
        scenario_version: str = "1",
        gost_version: str | None = None,
    ) -> None:
        self.scenario_version = scenario_version
        self.gost_version = gost_version
        self.parser: IScenarioParser | None = None
        self.connection_id: str | None = None
        self._variables: dict[str, Variable] = {}
        self.history: list[StepHistoryEntry] = []

    # --- Variables ---

    def set(self, name: str, value: Any, ttl: float | None = None) -> None:
        """Установить переменную.

        Args:
            name: Имя переменной.
            value: Значение.
            ttl: Время жизни в секундах (None = бессрочно).
        """
        self._variables[name] = Variable(
            value=value, ttl=ttl, created_at=time.time()
        )

    def get(self, name: str) -> Any | None:
        """Получить переменную.

        Args:
            name: Имя переменной.

        Returns:
            Значение или None (если нет или истёк TTL).
        """
        var = self._variables.get(name)
        if var is None:
            return None
        if var.is_expired:
            del self._variables[name]
            return None
        return var.value

    # --- Template substitution ---

    _PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

    def substitute(self, template: str) -> str:
        """Подставить переменные в шаблон {{var}}.

        Args:
            template: Шаблон с плейсхолдерами.

        Returns:
            Строку с подставленными значениями.
        """

        def _replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            value = self.get(var_name)
            if value is None:
                return match.group(0)  # Оставить плейсхолдер
            return str(value)

        return self._PLACEHOLDER_RE.sub(_replacer, template)

    # --- Connection ID resolution ---

    def _resolve_connection_id(self, step_connection_id: str | None) -> str | None:
        """Определить connection_id для шага.

        Приоритет: ctx.connection_id > step_connection_id > None.
        """
        if self.connection_id is not None:
            return self.connection_id
        return step_connection_id

    # --- History ---

    def add_history(
        self,
        step_name: str,
        result: str,
        duration: float = 0.0,
        details: str | None = None,
    ) -> None:
        """Добавить запись в историю.

        Args:
            step_name: Имя шага.
            result: Результат (PASS/FAIL/TIMEOUT/ERROR).
            duration: Длительность выполнения.
            details: Дополнительные детали.
        """
        self.history.append(
            StepHistoryEntry(
                step_name=step_name,
                result=result,
                duration=duration,
                details=details,
            )
        )

    def all_passed(self) -> bool:
        """Проверить, все ли шаги прошли успешно."""
        if not self.history:
            return False
        return all(entry.result == "PASS" for entry in self.history)


# --- ExpectStep ---


@dataclass
class ExpectStep:
    """Шаг ожидания пакета с проверкой полей и capture переменных.

    Подписывается на packet.processed, ждёт пакет, matching по checks,
    извлекает capture переменные в контекст.

    Attributes:
        name: Имя шага.
        checks: Dict с полями для проверки (exact/range/regex).
        capture: Dict var_name → nested_path для извлечения.
        channel: Канал ожидания (tcp/sms/None).
        timeout: Таймаут ожидания в секундах.
    """

    name: str
    checks: dict[str, Any] = field(default_factory=dict)
    capture: dict[str, str] = field(default_factory=dict)
    channel: str | None = None
    timeout: float | None = None

    _RANGE_KEYS: ClassVar[set[str]] = {"min", "max"}

    def _matches(self, parsed_data: dict[str, Any]) -> bool:
        """Проверить, соответствует ли пакет checks.

        Поддерживает:
        - Exact match: ``{"service": 1}``
        - Range: ``{"points": {"min": 1, "max": 100}}``
        - Regex: ``{"imei": r"^\\d{15}$"}``
        - Nested paths: ``{"data.TID": 12345}``
        """
        for key, expected in self.checks.items():
            actual = self._get_nested(parsed_data, key)
            if actual is None:
                return False

            # Range check
            if isinstance(expected, dict) and self._RANGE_KEYS.intersection(
                expected.keys()
            ):
                if not isinstance(actual, (int, float)):
                    return False
                if "min" in expected and actual < expected["min"]:
                    return False
                if "max" in expected and actual > expected["max"]:
                    return False
                continue

            # Regex check — явный формат {"regex": "..."}
            if isinstance(expected, dict) and "regex" in expected:
                pattern = expected["regex"]
                if not isinstance(actual, str):
                    return False
                if not re.fullmatch(pattern, actual):
                    return False
                continue

            # Exact match
            if actual != expected:
                return False

        return True

    def _get_nested(self, data: dict[str, Any], path: str) -> Any | None:
        """Извлечь значение по nested path (например, ``records[0].fields.RN``)."""
        parts = path.replace("[", ".").replace("]", "").split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    def _capture(self, ctx: ScenarioContext, parsed_data: dict[str, Any]) -> None:
        """Извлечь capture переменные в контекст."""
        for var_name, nested_path in self.capture.items():
            value = self._get_nested(parsed_data, nested_path)
            if value is not None:
                ctx.set(var_name, value)

    async def execute(
        self,
        ctx: ScenarioContext,
        bus: EventBus,
        timeout: float | None = None,
    ) -> str:
        """Выполнить шаг ожидания.

        Returns:
            PASS, TIMEOUT или ERROR.
        """
        eff_timeout = timeout or self.timeout or 30.0
        event = asyncio.Event()
        result_container: dict[str, str] = {"status": "PENDING"}

        def _on_packet(data: dict[str, Any]) -> None:
            ctx_obj = data.get("ctx")
            if ctx_obj is None:
                return
            packet_data = ctx_obj.parsed
            if packet_data is None:
                return
            # Проверка channel
            step_channel = self.channel
            if step_channel is not None and data.get("channel") != step_channel:
                return
            # Извлечение данных из подзаписей (замена extra)
            extra = {}
            if hasattr(packet_data, "packet") and packet_data.packet:
                # Добавляем service_type из первой записи
                if packet_data.packet.records:
                    extra["service"] = packet_data.packet.records[0].service_type
                for rec in packet_data.packet.records:
                    for sr in rec.subrecords:
                        if isinstance(sr.data, dict):
                            extra.update(sr.data)
            if self._matches(extra):
                self._capture(ctx, extra)
                result_container["status"] = "PASS"
                event.set()

        def _on_disconnect(data: dict[str, Any]) -> None:
            state = data.get("state", "")
            if state in ("disconnected", "closed", "error"):
                result_container["status"] = "ERROR"
                event.set()

        bus.on("packet.processed", _on_packet)
        bus.on("connection.changed", _on_disconnect)

        try:
            await asyncio.wait_for(event.wait(), timeout=eff_timeout)
        except TimeoutError:
            result_container["status"] = "TIMEOUT"
        finally:
            bus.off("packet.processed", _on_packet)
            bus.off("connection.changed", _on_disconnect)

        return result_container["status"]


# --- SendStep ---


@dataclass
class SendStep:
    """Шаг отправки пакета из файла или build-template.

    Attributes:
        name: Имя шага.
        packet_file: Путь к HEX-файлу с пакетом.
        build: Template dict для динамической генерации пакета.
        channel: Канал отправки (tcp/sms).
        timeout: Таймаут ожидания подтверждения.
    """

    name: str
    packet_file: str | None = None
    build: dict[str, Any] | None = None
    channel: str | None = None
    timeout: float | None = None

    _SUB_RE = re.compile(r"\{\{(\w+)\}\}")

    def _build_packet(self, ctx: ScenarioContext) -> bytes:
        """Загрузить пакет из HEX-файла.

        Returns:
            Байты пакета.

        Raises:
            FileNotFoundError: Если файл не найден.
            ValueError: Если невалидный HEX.
        """
        if not self.packet_file:
            raise ValueError("packet_file is required")

        path = Path(self.packet_file)
        if not path.exists():
            raise FileNotFoundError(f"Packet file not found: {self.packet_file}")

        hex_text = path.read_text().strip()
        try:
            return bytes.fromhex(hex_text)
        except ValueError as exc:
            raise ValueError(f"Invalid HEX in {self.packet_file}: {exc}") from exc

    def _build_from_template(self, ctx: ScenarioContext) -> dict[str, Any]:
        """Построить пакет из build-template с подстановкой переменных.

        Returns:
            Dict с полями пакета (передаётся в CommandDispatcher).
        """
        if not self.build:
            raise ValueError("build template is required")

        def _substitute(obj: Any) -> Any:
            if isinstance(obj, str):
                return ctx.substitute(obj)
            if isinstance(obj, dict):
                return {k: _substitute(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_substitute(item) for item in obj]
            return obj

        result: dict[str, Any] = _substitute(self.build)
        return result

    async def execute(
        self,
        ctx: ScenarioContext,
        bus: EventBus,
        timeout: float | None = None,
    ) -> str:
        """Выполнить шаг отправки.

        Returns:
            PASS, TIMEOUT или ERROR.
        """
        eff_timeout = timeout or self.timeout or 10.0

        # Проверка connection_id для TCP (приоритет: ctx > step > None)
        conn_id = ctx._resolve_connection_id(None)
        if self.channel == "tcp" and conn_id is None:
            logger.error("SendStep: connection_id required for TCP channel")
            return "ERROR"

        # Построение пакета
        pid: int | None = None
        rn: int | None = None

        if self.packet_file:
            packet_bytes = self._build_packet(ctx)
        elif self.build:
            template_data = self._build_from_template(ctx)
            packet_bytes = template_data.get("packet_bytes", b"")
            # pid/rn из шаблона (если указаны)
            pid = template_data.get("pid")
            rn = template_data.get("rn")
        else:
            logger.error("SendStep: packet_file or build required")
            return "ERROR"

        if not packet_bytes:
            logger.error("SendStep: empty packet_bytes")
            return "ERROR"

        emit_data: dict[str, Any] = {
            "packet_bytes": packet_bytes,
            "channel": self.channel,
            "step_name": self.name,
        }
        if conn_id is not None:
            emit_data["connection_id"] = conn_id
        if pid is not None:
            emit_data["pid"] = pid
        if rn is not None:
            emit_data["rn"] = rn

        # Отправка команды
        event = asyncio.Event()
        result_container: dict[str, str] = {"status": "PENDING"}

        def _on_sent(data: dict[str, Any]) -> None:
            result_container["status"] = "PASS"
            event.set()

        def _on_error(data: dict[str, Any]) -> None:
            result_container["status"] = "ERROR"
            event.set()

        bus.on("command.sent", _on_sent)
        bus.on("command.error", _on_error)

        try:
            await bus.emit("command.send", emit_data)
            await asyncio.wait_for(event.wait(), timeout=eff_timeout)
        except TimeoutError:
            result_container["status"] = "TIMEOUT"
        except Exception as exc:
            logger.error("SendStep: send failed: %s", exc)
            result_container["status"] = "ERROR"
        finally:
            bus.off("command.sent", _on_sent)
            bus.off("command.error", _on_error)

        return result_container["status"]


# --- Exceptions ---


class ScenarioValidationError(Exception):
    """Ошибка валидации сценария."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


# --- StepFactory ---


class StepFactory:
    """Фабрика шагов — создаёт ExpectStep/SendStep по типу из StepDefinition."""

    @staticmethod
    def create(step_def: StepDefinition) -> ExpectStep | SendStep:
        """Создать шаг из определения.

        Args:
            step_def: Определение шага из парсера.

        Returns:
            ExpectStep или SendStep.

        Raises:
            NotImplementedError: Если тип шага не реализован.
        """
        if step_def.type == "expect":
            return ExpectStep(
                name=step_def.name,
                channel=step_def.channel,
                timeout=step_def.timeout,
                checks=step_def.checks,
                capture=step_def.capture,
            )
        if step_def.type == "send":
            return SendStep(
                name=step_def.name,
                channel=step_def.channel,
                timeout=step_def.timeout,
                packet_file=step_def.packet_file,
                build=step_def.build,
            )
        raise NotImplementedError(
            f"Step type '{step_def.type}' is not implemented yet"
        )


# --- ScenarioManager ---


class ScenarioManager:
    """Загрузка и выполнение сценариев из scenario.json.

    Делегирует парсинг ScenarioParserFactory, создаёт шаги через StepFactory.

    Args:
        parser_factory: Фабрика парсеров сценариев.
    """

    def __init__(self, parser_factory: ScenarioParserFactory) -> None:
        self._parser_factory = parser_factory
        self._steps: list[ExpectStep | SendStep] = []
        self._context = ScenarioContext()
        self._metadata: ScenarioMetadata | None = None

    @property
    def metadata(self) -> ScenarioMetadata:
        """Метаданные загруженного сценария."""
        if self._metadata is None:
            raise RuntimeError("load() must be called first")
        return self._metadata

    @property
    def steps(self) -> list[ExpectStep | SendStep]:
        """Список шагов загруженного сценария."""
        return list(self._steps)

    @property
    def context(self) -> ScenarioContext:
        """Контекст выполнения."""
        return self._context

    def load(self, path: Path) -> None:
        """Загрузить сценарий из JSON-файла.

        Args:
            path: Путь к scenario.json.

        Raises:
            ScenarioValidationError: Ошибка валидации.
            FileNotFoundError: Если файл не найден.
        """
        data = json.loads(path.read_text(encoding="utf-8"))

        # Парсинг через factory
        parser = self._parser_factory.detect_and_create(data)
        errors, warnings = parser.validate(data)
        if warnings:
            logger.debug("Scenario load warnings: %s", warnings)
        if errors:
            raise ScenarioValidationError(errors)

        self._metadata = parser.load(data)
        step_defs = parser.get_steps()

        # Создание шагов через StepFactory
        self._steps = [StepFactory.create(sd) for sd in step_defs]

        # Разрешаем относительные пути packet_file относительно директории сценария
        scenario_dir = path.resolve().parent
        for step in self._steps:
            if hasattr(step, "packet_file") and step.packet_file:
                pf = Path(step.packet_file)
                if not pf.is_absolute():
                    resolved = scenario_dir / pf
                    if resolved.exists():
                        step.packet_file = str(resolved)
                    # Иначе оставляем как есть — FileNotFoundError будет при execute

        self._context = ScenarioContext(
            scenario_version=self._metadata.version,
            gost_version=self._metadata.gost_version,
        )
        self._context.parser = parser

    async def execute(
        self,
        bus: EventBus,
        connection_id: str | None = None,
        timeout: float | None = None,
    ) -> str:
        """Выполнить загруженный сценарий.

        Args:
            bus: EventBus для взаимодействия.
            connection_id: Идентификатор подключения.
            timeout: Общий таймаут сценария.

        Returns:
            PASS, FAIL, TIMEOUT или ERROR.
        """
        if not self._steps:
            raise RuntimeError("No steps loaded — call load() first")

        self._context.connection_id = connection_id
        eff_timeout = timeout or (self._metadata.timeout if self._metadata else 60.0)
        start_total = time.monotonic()

        for step in self._steps:
            elapsed = time.monotonic() - start_total
            remaining = eff_timeout - elapsed
            if remaining <= 0:
                self._context.add_history(step.name, "TIMEOUT", 0.0)
                return "TIMEOUT"

            start_time = time.monotonic()
            try:
                result = await step.execute(self._context, bus, timeout=remaining)
            except Exception as exc:
                logger.error("ScenarioManager: step '%s' failed: %s", step.name, exc)
                result = "ERROR"

            duration = time.time() - start_time
            self._context.add_history(step.name, result, duration)

            if result != "PASS":
                logger.warning(
                    "ScenarioManager: step '%s' returned %s", step.name, result
                )
                return result

        return "PASS"

    def load_by_name(self, name: str) -> None:
        """Загрузить сценарий по имени из директории scenarios/.

        Args:
            name: Имя сценария (директория в scenarios/).

        Raises:
            FileNotFoundError: Если файл scenario.json не найден.
        """
        path = Path("scenarios") / name / "scenario.json"
        if not path.exists():
            raise FileNotFoundError(f"Сценарий '{name}' не найден: {path}")
        self.load(path)

    async def execute_by_name(
        self,
        scenario_name: str,
        bus: EventBus,
        connection_id: str | None = None,
        timeout: float | None = None,
    ) -> str:
        """Запустить сценарий по имени.

        Args:
            scenario_name: Имя сценария (директория в scenarios/).
            bus: EventBus для взаимодействия.
            connection_id: Идентификатор подключения.
            timeout: Общий таймаут сценария.

        Returns:
            PASS, FAIL, TIMEOUT или ERROR.
        """
        self.load_by_name(scenario_name)
        return await self.execute(bus=bus, connection_id=connection_id, timeout=timeout)
