"""CoreEngine — координатор компонентов системы."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from core.config import Config
from core.event_bus import EventBus


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

        # TODO: заменить заглушки на реальную инициализацию
        # Локальные импорты будут добавлены здесь, когда компоненты появятся,
        # чтобы избежать циклических зависимостей.

        try:
            # 1. SessionManager
            # self.session_mgr = SessionManager(bus=self.bus, gost_version=self.config.gost_version)

            # 2. LogManager
            # self.log_mgr = LogManager(bus=self.bus, log_dir=self.config.logging.dir)

            # 3. ScenarioManager
            # self.scenario_mgr = ScenarioManager(bus=self.bus, session_mgr=self.session_mgr)

            # 4. PacketDispatcher
            # self.packet_dispatcher = PacketDispatcher(bus=self.bus, session_mgr=self.session_mgr)

            # 5. CommandDispatcher
            # self.command_dispatcher = CommandDispatcher(bus=self.bus, session_mgr=self.session_mgr)

            # 6. TcpServerManager
            # self.tcp_server = TcpServerManager(
            #     bus=self.bus, host=self.config.tcp_host, port=self.config.tcp_port,
            # )
            # await self.tcp_server.start()

            # 7. Cmw500Controller
            # self.cmw500 = Cmw500Controller(bus=self.bus, ip=self.config.cmw500.ip)
            # await self.cmw500.connect()

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

        if self.cmw500 is not None:
            with suppress(Exception):
                await self.cmw500.disconnect()
            self.cmw500 = None

        if self.tcp_server is not None:
            with suppress(Exception):
                await self.tcp_server.stop()
            self.tcp_server = None

        # Остальные компоненты не требуют явной остановки —
        # они просто перестают получать события через EventBus.
        self.packet_dispatcher = None
        self.command_dispatcher = None
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
            f"CoreEngine(state={state}, port={self.config.tcp_port}, "
            f"cmw={cmw_status}, gost={self.config.gost_version})"
        )
