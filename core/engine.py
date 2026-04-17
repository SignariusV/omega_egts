"""CoreEngine — координатор компонентов системы."""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

            # Создаём менеджер логирования (подписывается на события EventBus)
            self.log_mgr = LogManager(bus=self.bus, log_dir=Path(self.config.logging.dir))

            # Создаём менеджер сценариев (парсер + выполнение)
            from core.scenario import ScenarioManager as _ScenarioManager
            from core.scenario_parser import (
                ScenarioParserFactory as _ParserFactory,
            )
            from core.scenario_parser import (
                ScenarioParserRegistry as _ParserRegistry,
            )
            from core.scenario_parser import (
                ScenarioParserV1 as _ParserV1,
            )

            registry = _ParserRegistry()
            registry.register("1", _ParserV1)
            parser_factory = _ParserFactory(registry=registry)
            self.scenario_mgr = _ScenarioManager(parser_factory=parser_factory)

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

            # 7. Cmw500Controller (опционально — если задан IP)
            if self.config.cmw500.ip is not None:
                from core.cmw500 import Cmw500Controller, Cmw500Emulator

                if self.config.cmw500.simulate:
                    self.cmw500 = Cmw500Emulator(
                        bus=self.bus,
                        ip=self.config.cmw500.ip,
                        poll_interval=self.config.cmw500.status_poll_interval,
                    )
                else:
                    self.cmw500 = Cmw500Controller(
                        bus=self.bus,
                        ip=self.config.cmw500.ip,
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
        """Внутренний метод для остановки всех компонентов."""
        # Останавливаем в обратном порядке создания

        if self.log_mgr is not None:
            await self.log_mgr.stop()
            self.log_mgr = None

        if self.cmw500 is not None:
            with suppress(Exception):
                await self.cmw500.disconnect()
            self.cmw500 = None

        if self.tcp_server is not None:
            with suppress(Exception):
                await self.tcp_server.stop()
            self.tcp_server = None

        # Диспетчеры отписываются от EventBus
        if self.packet_dispatcher is not None:
            with suppress(Exception):
                self.packet_dispatcher.stop()
            self.packet_dispatcher = None

        if self.command_dispatcher is not None:
            with suppress(Exception):
                self.command_dispatcher.stop()
            self.command_dispatcher = None

        # Остальные компоненты не требуют явной остановки —
        # они просто перестают получать события через EventBus.
        self.scenario_mgr = None
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
        }

        # Дополнить деталями от CMW-500
        if self.cmw500 is not None and self.is_running:
            try:
                cmw_details = await self.cmw500.get_status()
                result["cmw_details"] = cmw_details
            except Exception:
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
            return await self.cmw500.get_full_status()
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    async def run_scenario(self, scenario_path: str, connection_id: str | None = None) -> dict[str, Any]:
        """Запустить сценарий для команды ``run-scenario``.

        Параметры:
            scenario_path: путь к директории сценария (scenario.json + HEX).
            connection_id: идентификатор подключения (None — автоопределение).

        Возвращает:
            Словарь с результатами: name, status, steps_total, steps_passed, error.
        """
        if not self.is_running:
            raise RuntimeError("CoreEngine не запущен (вызовите start)")

        if self.scenario_mgr is None:
            return {"status": "error", "error": "ScenarioManager не инициализирован"}

        try:
            scenario_path_obj = Path(scenario_path)
            # Если передана директория — добавляем scenario.json
            if scenario_path_obj.is_dir():
                scenario_path_obj = scenario_path_obj / "scenario.json"

            self.scenario_mgr.load(scenario_path_obj)
            # Используем таймаут из сценария, если не задан — дефолт 60с
            scenario_timeout = (
                self.scenario_mgr.metadata.timeout
                if self.scenario_mgr.metadata and self.scenario_mgr.metadata.timeout
                else 60.0
            )
            result = await self.scenario_mgr.execute(
                bus=self.bus,
                connection_id=connection_id,
                timeout=scenario_timeout,
            )
            history = self.scenario_mgr.context.history
            return {
                "name": self.scenario_mgr.metadata.name,
                "status": result,
                "steps_total": len(history),
                "steps_passed": sum(1 for h in history if h.result == "PASS"),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

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

        if fmt == "csv":
            result: dict[str, Any] = export_csv(
                log_dir=self.config.logging.dir,
                output_path=output_path,
                log_type_filter=log_type_filter,
            )
            return result
        elif fmt == "json":
            result = export_json(
                log_dir=self.config.logging.dir,
                output_path=output_path,
                log_type_filter=log_type_filter,
            )
            return result
        else:
            raise ValueError(f"Неподдерживаемый формат экспорта: {fmt}")

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
        except Exception:
            return {"packets": 0, "connections": 0, "running": True}
