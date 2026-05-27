"""CoreEngine — координатор компонентов системы."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent

from core.config import Config
from core.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class CoreEngine:
    """Главный координатор системы.

    Управляет жизненным циклом: инициализация, запуск, остановка.
    Все компоненты создаются и управляются через CoreEngine.

    Пример использования::

        config = Config.from_file("config/settings.json")
        bus = EventBus()
        engine = CoreEngine(config, bus)

        await engine.start()
        try:
            await asyncio.sleep(3600)  # работаем час
        finally:
            await engine.stop()
    """

    config: Config
    bus: EventBus

    # Компоненты (создаются в start(), сбрасываются в stop()).
    # Пока компоненты не реализованы — Any. Типы будут уточнены
    # по мере реализации TcpServerManager, SessionManager и т.д.
    tcp_server: Any = field(default=None, init=False, repr=False)
    cmw500: Any = field(default=None, init=False, repr=False)
    session_mgr: Any = field(default=None, init=False, repr=False)
    packet_dispatcher: Any = field(default=None, init=False, repr=False)
    command_dispatcher: Any = field(default=None, init=False, repr=False)
    scenario_mgr: Any = field(default=None, init=False, repr=False)
    log_mgr: Any = field(default=None, init=False, repr=False)

    # Background task для выполнения сценария (не блокирует event loop)
    _scenario_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    # Флаг — атомарная проверка «запущен ли CoreEngine».
    # Source of truth для состояния компонентов — их собственные поля,
    # но _started нужен для быстрой проверки без обращения к компонентам.
    _started: bool = field(default=False, init=False, repr=False)

    async def start(self) -> None:
        """Запустить систему.

        Инициализирует все компоненты в правильном порядке:

        1. SessionManager (нужен для всех остальных)
        2. LogManager (подписывается на события)
        3. ScenarioManager (подписывается на события)
        4. PacketDispatcher (подписывается на ``raw.packet.received``)
        5. CommandDispatcher (подписывается на ``command.send``)
        6. TcpServerManager (начинает принимать соединения)
        7. Cmw500Controller (подключается к железу/эмулятору)

        Повторный вызов игнорируется (idempotent).
        При ошибке запуска уже созданные компоненты корректно останавливаются.
        """
        if self._started:
            return

        # Локальные импорты — избегаем циклических зависимостей
        from core.cmw500 import Cmw500Controller
        from core.dispatcher import CommandDispatcher, PacketDispatcher
        from core.logger import LogManager
        from core.session import SessionManager
        from core.tcp_server import TcpServerManager

        try:
            # Создаём менеджер сессий (требуется для работы других компонентов)
            self.session_mgr = SessionManager(bus=self.bus, gost_version=self.config.gost_version)

            # Получаем session_id из python_logger
            from core.python_logger import get_session_id
            session_id = get_session_id()

            # Создаём менеджер логирования (подписывается на события EventBus)
            self.log_mgr = LogManager(bus=self.bus, log_dir=BASE_DIR / self.config.logging.dir, session_id=session_id)
            self.log_mgr.start()

            # Создаём менеджер сценариев (парсер + выполнение)
            from core.scenario import ScenarioManager as _ScenarioManager
            from core.scenario_parser import (
                ScenarioParserFactory as _ParserFactory,
                ScenarioParserRegistry as _ParserRegistry,
                ScenarioParserV1 as _ParserV1,
            )

            registry = _ParserRegistry()
            registry.register("1", _ParserV1)
            parser_factory = _ParserFactory(registry=registry)
            self.scenario_mgr = _ScenarioManager(parser_factory=parser_factory)

            # Регистрируем резолвер для server_address
            from core.network import get_wifi_ip
            self.scenario_mgr.register_resolver(
                "server_address",
                lambda: f"{get_wifi_ip() or '127.0.0.1'}:{self.config.tcp_port}",
            )

            # Создаём диспетчер пакетов (подписывается на raw.packet.received)
            self.packet_dispatcher = PacketDispatcher(bus=self.bus, session_mgr=self.session_mgr)

            # Создаём диспетчер команд (отправка через TCP или SMS)
            # cmw пока None — CMW-500 подключается на шаге 7
            self.command_dispatcher = CommandDispatcher(bus=self.bus, session_mgr=self.session_mgr)

            # Создаём TCP-сервер (принимает соединения от УСВ)
            self.tcp_server = TcpServerManager(
                bus=self.bus,
                host=self.config.tcp_host,
                port=self.config.tcp_port,
                session_mgr=self.session_mgr,
            )
            await self.tcp_server.start()

            # 7. Cmw500Controller (опционально — если задан IP или simulate=True)
            if self.config.cmw500.ip is not None or self.config.cmw500.simulate:
                from core.cmw500 import Cmw500Controller, Cmw500Emulator

                if self.config.cmw500.simulate:
                    self.cmw500 = Cmw500Emulator(
                        bus=self.bus,
                        ip=self.config.cmw500.ip or "127.0.0.1",
                        poll_interval=self.config.cmw500.status_poll_interval,
                    )
                else:
                    self.cmw500 = Cmw500Controller(
                        bus=self.bus,
                        ip=self.config.cmw500.ip or "127.0.0.1",
                        simulate=False,
                    )
                await self.cmw500.connect()

                # Останавливаем poll_loop на время конфигурации
                self.cmw500.stop_poll()

                # Автоконфигурация GSM Signaling + SMS (из docs/comands.txt)
                cmw_cfg = self.config.cmw500
                await self.cmw500.configure_gsm_signaling(
                    mcc=cmw_cfg.mcc,
                    mnc=cmw_cfg.mnc,
                    rf_level_dbm=cmw_cfg.rf_level_tch,
                    ps_service=cmw_cfg.ps_service,
                    ps_tlevel=cmw_cfg.ps_tlevel,
                    ps_cscheme_ul=cmw_cfg.ps_cscheme_ul,
                    ps_dl_carrier=",".join(cmw_cfg.ps_dl_carrier),
                    ps_dl_cscheme=",".join(cmw_cfg.ps_dl_cscheme),
                )
                await self.cmw500.configure_sms(
                    dcoding=cmw_cfg.sms_dcoding,
                    pid=cmw_cfg.sms_pidentifier,
                )
                await self.cmw500.configure_dau()

                # Запускаем poll_loop после конфигурации
                self.cmw500.start_poll()

                # Обновляем cmw в CommandDispatcher для SMS-канала
                self.command_dispatcher.cmw = self.cmw500

            self._started = True
            await self.bus.emit(
                "server.started",
                {"port": self.config.tcp_port, "gost_version": self.config.gost_version},
            )

        except Exception as exc:
            await self._cleanup()
            raise RuntimeError(f"Не удалось запустить CoreEngine: {exc}") from exc

    async def stop(self) -> None:
        """Остановить систему.

        Корректно останавливает все компоненты в обратном порядке:
        CMW-500 → TCP сервер → остальные компоненты (их stop не требуется,
        они просто перестают получать события через EventBus).

        Вызов без предварительного start() не вызывает ошибок.
        """
        if not self._started:
            return

        await self._cleanup()
        self._started = False
        await self.bus.emit("server.stopped", {"reason": "shutdown"})

    async def _cleanup(self) -> None:
        """Внутренний метод для остановки всех компонентов (обратный порядок создания)."""
        # 7 → 6: CMW-500 + TCP-сервер (источники внешних событий)
        if self.cmw500 is not None:
            with suppress(Exception):
                await asyncio.wait_for(self.cmw500.disconnect(), timeout=10.0)
            self.cmw500 = None

        if self.tcp_server is not None:
            with suppress(Exception):
                await self.tcp_server.stop()
            self.tcp_server = None

        # 5 → 4: диспетчеры (обработчики)
        if self.command_dispatcher is not None:
            with suppress(Exception):
                self.command_dispatcher.stop()
            self.command_dispatcher = None

        if self.packet_dispatcher is not None:
            with suppress(Exception):
                self.packet_dispatcher.stop()
            self.packet_dispatcher = None

        await self._cancel_scenario_task()

        # 3 → 1: менеджеры (не генерируют события)
        self.scenario_mgr = None
        if self.log_mgr is not None:
            await self.log_mgr.stop()
            self.log_mgr = None
        self.session_mgr = None

    @property
    def is_running(self) -> bool:
        """Проверка, запущена ли система."""
        return self._started

    def __str__(self) -> str:
        """Компактное строковое представление для логов."""
        state = "running" if self.is_running else "stopped"
        cmw_status = "connected" if self.cmw500 is not None else "disconnected"
        return (
            f"CoreEngine(state={state}, port={self.config.tcp_port}, cmw={cmw_status}, gost={self.config.gost_version})"
        )

    # ===== Private helpers =====

    @staticmethod
    def _error_result(msg: str) -> dict[str, str]:
        return {"status": "error", "error": msg}

    async def _cancel_scenario_task(self) -> None:
        if self._scenario_task is not None and not self._scenario_task.done():
            self._scenario_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._scenario_task
        self._scenario_task = None

    async def _emit_scenario_finished(self, result: str, **extra: Any) -> None:
        name = self.scenario_mgr.metadata.name if self.scenario_mgr else "unknown"
        await self.bus.emit("scenario.finished", {"scenario_name": name, "result": result, **extra})

    # ===== API для CLI (задача 9.0) =====

    async def get_status(self) -> dict[str, Any]:
        """Полный статус системы для команды ``status``.

        Возвращает словарь с:
        - ``running`` — запущен ли CoreEngine
        - ``port`` — TCP порт
        - ``gost_version`` — версия ГОСТ
        - ``tcp_server`` — "running"/"stopped"
        - ``cmw500`` — "connected"/"disconnected"
        - ``session_mgr``, ``log_mgr``, ``scenario_mgr`` — созданы ли
        - ``cmw_details`` — данные от CMW-500 (если подключён)
        """
        result: dict[str, Any] = {
            "running": self.is_running,
            "port": self.config.tcp_port,
            "gost_version": self.config.gost_version,
            "tcp_server": "running" if self.tcp_server is not None else "stopped",
            "cmw500": "connected" if self.cmw500 is not None else "disconnected",
            "session_mgr": self.session_mgr is not None,
            "log_mgr": self.log_mgr is not None,
            "scenario_mgr": self.scenario_mgr is not None,
            "scenario_running": self.scenario_mgr is not None and self.scenario_mgr.is_running,
        }

        # Дополнить деталями от CMW-500
        if self.cmw500 is not None and self.is_running:
            try:
                cmw_details = await self.cmw500.get_status()
                result["cmw_details"] = cmw_details
            except Exception as e:
                logger.debug("Не удалось получить статус CMW-500: %s", e)
                result["cmw_details"] = None

        return result

    async def cmw_status(self) -> dict[str, Any]:
        """Расширенный статус CMW-500 для команды ``cmw-status``.

        Возвращает:
        - ``connected`` — подключён ли
        - ``serial`` — серийный номер
        - ``cs_state`` — состояние CS-канала
        - ``ps_state`` — состояние PS-канала
        - ``rssi`` — уровень сигнала
        - ``ber`` — битовая ошибка
        - ``rx_level`` — уровень приёма
        - ``simulate`` — режим симуляции
        - ``ip`` — адрес подключения
        - ``error`` — сообщение об ошибке
        """
        if self.cmw500 is None:
            return {
                "connected": False,
                "error": "CMW-500 не инициализирован (вызовите start)",
            }

        try:
            result = await self.cmw500.get_full_status()
            return {"connected": True, **result} if isinstance(result, dict) else {"connected": True, "data": result}
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    async def run_scenario(self, scenario_path: str, connection_id: str | None = None) -> dict[str, Any]:
        """Запустить сценарий как background task.

        Параметры:
            scenario_path: путь к директории сценария (scenario.json + HEX).
            connection_id: идентификатор подключения (None — автоопределение).

        Возвращает:
            Словарь с результатами: name, status, steps_total, steps_passed, error.
        """
        if not self.is_running:
            raise RuntimeError("CoreEngine не запущен (вызовите start)")

        if self.scenario_mgr is None:
            return self._error_result("ScenarioManager не инициализирован")

        if self._scenario_task is not None and not self._scenario_task.done():
            return self._error_result("Сценарий уже выполняется")

        try:
            scenario_path_obj = Path(scenario_path)
            if scenario_path_obj.is_dir():
                scenario_path_obj = scenario_path_obj / "scenario.json"

            self.scenario_mgr.load(scenario_path_obj)
            scenario_timeout = (
                self.scenario_mgr.metadata.timeout
                if self.scenario_mgr.metadata and self.scenario_mgr.metadata.timeout
                else 60.0
            )

            async def _run():
                try:
                    result = await self.scenario_mgr.execute(
                        bus=self.bus,
                        connection_id=connection_id,
                        timeout=scenario_timeout,
                    )
                    failed_steps = []
                    for h in self.scenario_mgr.context.history:
                        if h.result != "PASS":
                            fs: dict[str, Any] = {"step": h.step_name, "result": h.result}
                            if h.details:
                                try:
                                    fs["details"] = json.loads(h.details)
                                except (json.JSONDecodeError, TypeError):
                                    fs["details"] = h.details
                            failed_steps.append(fs)
                    await self._emit_scenario_finished(result, failed_steps=failed_steps)
                except asyncio.CancelledError:
                    await self._emit_scenario_finished("CANCELLED")
                except Exception as exc:
                    await self._emit_scenario_finished("ERROR", error=str(exc))
                finally:
                    self._scenario_task = None

            self._scenario_task = asyncio.create_task(_run())
            return {
                "name": self.scenario_mgr.metadata.name,
                "status": "RUNNING",
                "steps_total": len(self.scenario_mgr.steps),
                "steps_passed": 0,
            }
        except Exception as exc:
            return self._error_result(str(exc))

    async def cancel_scenario(self) -> dict[str, Any]:
        """Отменить выполнение сценария.

        Возвращает:
            Словарь с результатом отмены.
        """
        if self.scenario_mgr is None:
            return self._error_result("ScenarioManager не инициализирован")

        if not self.scenario_mgr.is_running:
            return self._error_result("Сценарий не выполняется")

        self.scenario_mgr.cancel()
        await self._cancel_scenario_task()
        return {"status": "ok", "result": "CANCELLED"}

    async def replay(self, log_path: str, scenario_path: str | None = None) -> dict[str, Any]:
        """Replay JSONL-лога через pipeline для команды ``replay``.

        Параметры:
            log_path: путь к файлу JSONL
            scenario_path: опционально — сценарий для валидации (пока игнорируется)

        Возвращает:
            Словарь с processed, skipped_duplicates, errors.
        """
        if not self.is_running:
            raise RuntimeError("CoreEngine не запущен (вызовите start)")

        from core.packet_source import ReplaySource

        replay_source = ReplaySource(
            bus=self.bus,
            log_file=log_path,
        )

        result = await replay_source.replay()
        return result

    async def export(self, data_type: str, fmt: str, output_path: str) -> dict[str, Any]:
        """Выгрузка данных для команды ``export``.

        Параметры:
            data_type: тип данных (packets, scenarios, connections)
            fmt: формат (csv, json)
            output_path: путь к файлу вывода

        Возвращает:
            Словарь с rows, file.
        """
        if not self.is_running:
            raise RuntimeError("CoreEngine не запущен (вызовите start)")

        from core.export import export_csv, export_json

        # Нормализация: CLI использует мн.ч. ("packets"), LogManager — ед.ч. ("packet")
        log_type_map = {
            "packets": "packet",
            "connections": "connection",
            "scenarios": "scenario",
        }
        log_type_filter = log_type_map.get(data_type, data_type)

        formatters = {"csv": export_csv, "json": export_json}
        if fmt not in formatters:
            raise ValueError(f"Неподдерживаемый формат экспорта: {fmt}")
        return formatters[fmt](
            log_dir=self.config.logging.dir,
            output_path=output_path,
            log_type_filter=log_type_filter,
        )

    async def get_log_stats(self) -> dict[str, Any]:
        """Статистика лог-файлов.

        Возвращает:
            Словарь с packets, connections, running.
        """
        if self.log_mgr is None:
            return {"packets": 0, "connections": 0, "running": False}

        try:
            stats = self.log_mgr.get_stats()
            return {**stats, "running": True}
        except Exception as e:
            logger.debug("Ошибка получения статистики логгера: %s", e)
            return {"packets": 0, "connections": 0, "running": True}
