"""CLI приложение — тонкая обёртка над Core Engine.

Тонкая обёртка: не содержит бизнес-логики, только:
- Разбор аргументов (argparse)
- Вызов методов CoreEngine
- Форматирование вывода в терминал
- REPL режим (cmd.Cmd)

Пример использования::

    # Одна команда
    egts-tester start --port 3001 --gost 2015

    # REPL режим
    egts-tester
    > start
    > status
    > stop
"""

from __future__ import annotations

# Настройка Python-логирования ДО всего остального
from core.python_logger import setup_python_logging

setup_python_logging(
    log_dir="logs",
    console_level="ERROR",  # В консоль только ошибки
    file_level="DEBUG",  # В файл всё
)

import argparse
import asyncio
import threading
import json
import sys
from cmd import Cmd
from collections.abc import Awaitable, Callable, Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from core.engine import CoreEngine

_HandlerFn = Callable[[Any], Awaitable[int]]

# Точка входа для pyproject.toml

# Базовая директория проекта (OMEGA_EGTS/)
BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_scenario_path(scenario_name: str) -> str:
    """Разрешить путь к сценарию: имя → scenarios/<name>/, полный путь → as-is."""
    if "/" in scenario_name or "\\" in scenario_name:
        return scenario_name
    return str(BASE_DIR / "scenarios" / scenario_name)


def build_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов со всеми подкомандами.

    Подкоманды (ТЗ Раздел 5.1):
    - start — запуск сервера
    - stop — остановка
    - replay — replay JSONL-лога
    - run-scenario — запуск сценария
    - batch — пакетный запуск
    - status — статус системы
    - export — выгрузка данных
    - cmw-status — статус CMW-500
    - monitor — интерактивный монитор (REPL)
    """
    parser = argparse.ArgumentParser(
        prog="egts-tester",
        description="Серверный тестер УСВ — испытания на ГОСТ 33465/33464",
    )
    sub = parser.add_subparsers(dest="command")

    # start
    p_start = sub.add_parser("start", help="Запуск сервера")
    p_start.add_argument("--port", type=int, default=3001, help="TCP порт (по умолч. 3001)")
    p_start.add_argument(
        "--gost",
        choices=["2015", "2023"],
        default="2015",
        help="Версия ГОСТ (по умолч. 2015)",
    )
    p_start.add_argument("--cmw", type=str, default=None, help="IP CMW-500")
    p_start.add_argument(
        "--simulate",
        action="store_true",
        default=False,
        help="Запустить CMW-500 в режиме симуляции (эмулятор)",
    )
    p_start.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Уровень логирования",
    )

    # stop
    sub.add_parser("stop", help="Остановка сервера")

    # status
    sub.add_parser("status", help="Статус системы")

    # cmw-status
    sub.add_parser("cmw-status", help="Статус CMW-500")

    # run-scenario
    p_scenario = sub.add_parser("run-scenario", help="Запуск сценария")
    p_scenario.add_argument("scenario_path", help="Путь к директории сценария")
    p_scenario.add_argument(
        "--connection-id",
        default=None,
        help="Идентификатор подключения",
    )

    # replay
    p_replay = sub.add_parser("replay", help="Replay JSONL-лога")
    p_replay.add_argument("log_path", help="Путь к JSONL-файлу")
    p_replay.add_argument("--scenario", default=None, help="Путь к сценарию (опционально)")

    # batch
    p_batch = sub.add_parser("batch", help="Пакетный запуск сценариев")
    p_batch.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        required=True,
        help="Имя или путь к сценарию (можно указывать несколько раз)",
    )
    p_batch.add_argument("--output", default=None, help="Файл отчёта (JSON)")

    # export
    p_export = sub.add_parser("export", help="Выгрузка данных")
    p_export.add_argument(
        "data_type",
        choices=["packets", "connections", "scenarios"],
        help="Тип данных для выгрузки",
    )
    p_export.add_argument(
        "--format",
        choices=["csv", "json"],
        required=True,
        help="Формат выгрузки",
    )
    p_export.add_argument("--output", required=True, help="Файл вывода")

    # monitor (REPL)
    sub.add_parser("monitor", help="Интерактивный монитор (REPL)")

    return parser


# ===== Обработчики команд =====


def _format_status(data: dict[str, Any]) -> str:
    """Форматировать статус системы для вывода."""
    lines = []
    state = "🟢 running" if data.get("running") else "🔴 stopped"
    lines.append(f"Состояние: {state}")
    lines.append(f"Порт: {data.get('port')}")
    lines.append(f"ГОСТ: {data.get('gost_version')}")
    lines.append(f"TCP сервер: {data.get('tcp_server')}")
    lines.append(f"CMW-500: {data.get('cmw500')}")
    lines.append(f"SessionManager: {'✅' if data.get('session_mgr') else '❌'}")
    lines.append(f"LogManager: {'✅' if data.get('log_mgr') else '❌'}")
    lines.append(f"ScenarioManager: {'✅' if data.get('scenario_mgr') else '❌'}")

    if data.get("cmw_details"):
        lines.append("")
        lines.append("CMW-500 детали:")
        for key, value in data["cmw_details"].items():
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)


def _format_cmw_status(data: dict[str, Any]) -> str:
    """Форматировать статус CMW-500."""
    if not data.get("connected"):
        return f"🔴 CMW-500 не подключён: {data.get('error', 'неизвестная ошибка')}"

    lines = ["🟢 CMW-500 подключён"]

    # Основные параметры
    if data.get("serial"):
        lines.append(f"  Серийный номер: {data['serial']}")
    if data.get("ip"):
        lines.append(f"  IP-адрес: {data['ip']}")
    if data.get("simulate"):
        lines.append("  Режим: симуляция")

    lines.append("")

    # Состояния каналов
    lines.append("Каналы:")
    cs = data.get("cs_state", "N/A")
    ps = data.get("ps_state", "N/A")
    lines.append(f"  CS: {cs}")
    lines.append(f"  PS: {ps}")

    lines.append("")

    # Радиопараметры
    lines.append("Радиопараметры:")
    rssi = data.get("rssi", "N/A")
    if rssi != "N/A":
        lines.append(f"  RSSI: {rssi} dBm")
    else:
        lines.append(f"  RSSI: {rssi}")
    ber = data.get("ber", "N/A")
    if ber != "N/A" and isinstance(ber, (int, float)):
        lines.append(f"  BER: {ber:.6f}")
    else:
        lines.append(f"  BER: {ber}")
    rx = data.get("rx_level", "N/A")
    if rx != "N/A" and isinstance(rx, (int, float)):
        lines.append(f"  RX Level: {rx} dBm")
    else:
        lines.append(f"  RX Level: {rx}")

    return "\n".join(lines)


def _format_scenario_result(data: dict[str, Any]) -> str:
    """Форматировать результат сценария."""
    status = data.get("status", "unknown")
    icon = "✅ PASSED" if status == "PASS" else f"❌ {status}"
    lines = [
        f"Сценарий: {data.get('name', 'unknown')}",
        f"Результат: {icon}",
        f"Шаги: {data.get('steps_passed', 0)}/{data.get('steps_total', 0)}",
    ]
    if data.get("error"):
        lines.append(f"Ошибка: {data['error']}")
    return "\n".join(lines)


def _format_replay_result(data: dict[str, Any]) -> str:
    """Форматировать результат replay."""
    lines = [
        f"Обработано: {data.get('processed', 0)}",
        f"Пропущено дубликатов: {data.get('skipped_duplicates', 0)}",
    ]
    errors = data.get("errors", [])
    if errors:
        lines.append(f"Ошибки: {len(errors)}")
        for err in errors[:5]:
            lines.append(f"  - {err}")
    return "\n".join(lines)


def _format_export_result(data: dict[str, Any]) -> str:
    """Форматировать результат экспорта."""
    return f"Экспортировано {data.get('rows', 0)} записей → {data.get('file', 'unknown')}"


# ===== Утилиты =====


async def _with_engine(fn: _HandlerFn) -> int:
    """Создать CoreEngine, запустить, выполнить fn(engine), остановить."""
    from core.config import Config
    from core.engine import CoreEngine
    from core.event_bus import EventBus

    engine = CoreEngine(config=Config(), bus=EventBus())
    await engine.start()
    try:
        return await fn(engine)
    finally:
        await engine.stop()


# ===== Асинхронные обработчики =====


async def _cmd_start(args: argparse.Namespace) -> int:
    """Обработать команду start."""
    from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
    from core.engine import CoreEngine
    from core.event_bus import EventBus

    config = Config(
        gost_version=args.gost,
        tcp_port=args.port,
        cmw500=CmwConfig(ip=args.cmw, simulate=args.simulate) if args.cmw else CmwConfig(simulate=args.simulate),
        logging=LogConfig(level=args.log_level),
        timeouts=TimeoutsConfig(),
    )

    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    try:
        await engine.start()
        print(f"✅ Сервер запущен на порту {args.port}, ГОСТ {args.gost}")
        if args.cmw:
            print(f"   CMW-500: {args.cmw}")
        print("   Нажмите Ctrl+C для остановки")

        # Ждём пока не прервут
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
    finally:
        await engine.stop()
        print("\n🔴 Сервер остановлен")

    return 0


async def _cmd_stop(args: argparse.Namespace) -> int:
    """Обработать команду stop.

    Примечание: stop работает только через остановку процесса start.
    В текущей архитектуре start блокирует процесс, поэтому stop —
    это сигнал оператору завершить процесс вручную.
    """
    print("Для остановки сервера нажмите Ctrl+C в терминале с запущенным egts-tester")
    return 0


async def _cmd_status(args: argparse.Namespace) -> int:
    """Обработать команду status.

    Примечание: показывает статус только из конфига, т.к.
    сервер запускается в отдельном процессе. Для статуса
    запущенного сервера используйте REPL (monitor).
    """
    from core.config import Config

    config = Config()
    lines = [
        "Конфигурация (сервер не запущен):",
        f"  Порт: {config.tcp_port}",
        f"  ГОСТ: {config.gost_version}",
        f"  CMW-500: {config.cmw500.ip or 'не задан'}",
        f"  Лог: {config.logging.level}",
        "",
        "Для запуска: egts-tester start",
        "Для REPL:   egts-tester monitor",
    ]
    print("\n".join(lines))
    return 0


async def _try_get_engine_cmw_status() -> dict[str, Any] | None:
    """Попытаться получить CMW статус от запущенного сервера.

    Returns:
        dict со статусом или None если сервер не запущен.
    """
    import asyncio

    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", 3001),
            timeout=2.0,
        )
        writer.close()
        await writer.wait_closed()
    except (OSError, TimeoutError):
        return None

    # Сервер запущен — пытаемся получить engine
    # Это работает только в рамках того же процесса,
    # поэтому для CLI без сервера возвращаем None
    return None


async def _cmd_cmw_status(args: argparse.Namespace) -> int:
    """Обработать команду cmw-status.

    Если сервер запущен — показывает расширенный статус через engine.
    Иначе — показывает конфигурацию CMW-500.
    """
    from core.config import Config

    # Пытаемся получить статус от запущенного сервера
    status_data = await _try_get_engine_cmw_status()
    if status_data is not None:
        print(_format_cmw_status(status_data))
        return 0 if status_data.get("connected") else 1

    # Fallback — показываем конфигурацию
    config = Config()
    ip = config.cmw500.ip
    if ip:
        print(f"CMW-500: {ip} (подключение при запуске сервера)")
    else:
        print("CMW-500: не настроен (укажите --cmw IP при запуске)")
    return 0


async def _cmd_run_scenario(args: argparse.Namespace) -> int:
    """Обработать команду run-scenario."""

    async def _fn(engine: "CoreEngine") -> int:
        result = await engine.run_scenario(
            args.scenario_path,
            connection_id=args.connection_id,
        )
        print(_format_scenario_result(result))
        return 0 if result.get("status") == "PASS" else 1

    return await _with_engine(_fn)


async def _cmd_replay(args: argparse.Namespace) -> int:
    """Обработать команду replay."""

    async def _fn(engine: "CoreEngine") -> int:
        result = await engine.replay(args.log_path, args.scenario)
        print(_format_replay_result(result))
        return 0

    return await _with_engine(_fn)


async def _cmd_batch(args: argparse.Namespace) -> int:
    """Обработать команду batch."""
    from core.config import Config
    from core.engine import CoreEngine
    from core.event_bus import EventBus

    config = Config()
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    await engine.start()
    results: list[dict[str, Any]] = []

    try:
        for scenario_name in args.scenarios:
            scenario_path = _resolve_scenario_path(scenario_name)
            print(f"\n▶ Запуск сценария: {scenario_name}")
            result = await engine.run_scenario(scenario_path)
            results.append({"name": scenario_name, **result})
            print(_format_scenario_result(result))

        # Сохранить отчёт
        if args.output:
            Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
            print(f"\n📄 Отчёт сохранён: {args.output}")

        passed = sum(1 for r in results if r.get("status") == "PASS")
        print(f"\nИтого: {passed}/{len(results)} сценариев прошли")
        return 0 if passed == len(results) else 1
    finally:
        await engine.stop()


async def _cmd_export(args: argparse.Namespace) -> int:
    """Обработать команду export."""

    async def _fn(engine: "CoreEngine") -> int:
        result = await engine.export(args.data_type, args.format, args.output)
        print(_format_export_result(result))
        return 0

    return await _with_engine(_fn)


def _cmd_monitor(_args: argparse.Namespace) -> int:
    """Обработать команду monitor — запустить REPL.

    НЕ async-функция: cmdloop() блокирует поток, а внутри REPL
    используется отдельный event loop через _run(). Если вызвать
    через asyncio.run() — run_until_complete() упадёт с
    RuntimeError: event loop уже запущен.
    """
    cli = EGTSTesterCLI()
    cli.cmdloop()
    return 0


# ===== REPL режим =====


class EGTSTesterCLI(Cmd):
    """Интерактивный REPL для egts-tester.

    Поддерживаемые команды:
    - start, stop, status, cmw-status
    - run-scenario <path> [--connection-id <id>]
    - replay <log_path> [--scenario <path>]
    - batch --scenario <name> [--scenario <name> ...]
    - export <type> --format <fmt> --output <file>
    - exit, quit, help
    """

    intro = "egts-tester REPL. Введите 'help' для списка команд."
    prompt = "egts-tester> "

    _command_help: dict[str, str] = {
        "start": "Запустить сервер [--port PORT] [--gost VER] [--cmw IP] [--simulate]",
        "stop": "Остановить сервер",
        "status": "Статус TCP-сервера",
        "cmw-status": "Статус CMW-500",
        "run-scenario": "Запустить сценарий <path> [--connection-id ID]",
        "replay": "Replay лога <log_path> [--scenario PATH]",
        "batch": "Пакетный запуск --scenario <name> [--scenario <name> ...] [--output FILE]",
        "export": "Выгрузка данных <type> --format <fmt> --output <file>",
        "help": "Справка по командам",
        "quit": "Выйти из REPL",
        "exit": "Выйти из REPL",
    }

    _aliases: dict[str, str] = {
        "cmw-status": "cmw_status",
        "run-scenario": "run_scenario",
    }

    def __init__(self) -> None:
        super().__init__()

        # Настройка логирования (на случай если запущен напрямую)
        from core.python_logger import setup_python_logging

        setup_python_logging(
            log_dir="logs",
            console_level="ERROR",
            file_level="DEBUG",
        )

        self._engine: Any = None
        self._config: Any = None
        self._bus: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server_thread: threading.Thread | None = None
        self._server_running = False

    # ------------------------------------------------------------------
    # Вспомогательные методы для работы с event loop
    # ------------------------------------------------------------------

    def _run_short(self, coro: Any) -> Any:
        """Запустить короткую async-корутину во временном loop."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _run_in_server_loop(self, coro: Any) -> Any:
        """Запустить корутину в loop сервера (работает в фоновом потоке)."""
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("Event loop сервера не активен")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=60)
        except Exception:
            # Пробрасываем оригинальное исключение
            raise

    def _run_loop_forever(self) -> None:
        """Запустить loop.run_forever() в фоновом потоке."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        except Exception as e:
            print(f"Ошибка в фоновом event loop: {e}")
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.close()

    # ------------------------------------------------------------------
    # Команды REPL
    # ------------------------------------------------------------------

    def do_help(self, arg: str) -> None:
        if arg.strip():
            super().do_help(arg)
            return
        print("\nДоступные команды:\n")
        max_cmd = max(len(cmd) for cmd in self._command_help)
        for cmd, desc in self._command_help.items():
            print(f"  {cmd:<{max_cmd}}  {desc}")
        print()

    def onecmd(self, line: str) -> bool:
        parts = line.strip().split(None, 1)
        if parts:
            cmd = parts[0].lower()
            if cmd in self._aliases:
                rest = parts[1] if len(parts) > 1 else ""
                return super().onecmd(f"{self._aliases[cmd]} {rest}".strip())
        return super().onecmd(line)

    def do_start(self, arg: str) -> None:
        """Запустить сервер: start [--port PORT] [--gost VERSION] [--cmw IP] [--simulate]"""
        if self._server_running:
            print("Сервер уже запущен")
            return

        # Парсинг опций
        parts = arg.split()
        port = 3001
        gost = "2015"
        cmw_ip = None
        simulate = False
        i = 0
        while i < len(parts):
            if parts[i] == "--port" and i + 1 < len(parts):
                try:
                    port = int(parts[i + 1])
                except ValueError:
                    print(f"Ошибка: --port должен быть целым числом, получено '{parts[i + 1]}'")
                    return
                i += 2
            elif parts[i] == "--gost" and i + 1 < len(parts):
                gost = parts[i + 1]
                i += 2
            elif parts[i] == "--cmw" and i + 1 < len(parts):
                cmw_ip = parts[i + 1]
                i += 2
            elif parts[i] == "--simulate":
                simulate = True
                i += 1
            else:
                i += 1

        from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
        from core.engine import CoreEngine
        from core.event_bus import EventBus

        self._config = Config(
            gost_version=gost,
            tcp_port=port,
            cmw500=CmwConfig(ip=cmw_ip, simulate=simulate) if cmw_ip else CmwConfig(simulate=simulate),
            logging=LogConfig(),
            timeouts=TimeoutsConfig(),
        )
        self._bus = EventBus()
        self._engine = CoreEngine(config=self._config, bus=self._bus)

        # Создаём event loop и запускаем engine
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._engine.start())
        print(f"✅ Сервер запущен на порту {port}, ГОСТ {gost}")
        if cmw_ip:
            mode = "(режим симуляции)" if simulate else ""
            print(f"   CMW-500: {cmw_ip} {mode}")
        elif simulate:
            print("   CMW-500: режим симуляции")
        print("   Используйте 'stop' для остановки сервера")

        # Запускаем loop в фоновом потоке
        self._server_running = True
        self._server_thread = threading.Thread(target=self._run_loop_forever, daemon=True)
        self._server_thread.start()

    def do_stop(self, arg: str) -> None:
        """Остановить сервер: stop"""
        if not self._server_running or self._engine is None or self._loop is None:
            print("Сервер не запущен")
            return

        try:
            # Останавливаем engine в фоновом loop
            future = asyncio.run_coroutine_threadsafe(self._engine.stop(), self._loop)
            future.result(timeout=30)

            # Останавливаем loop
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._server_thread is not None:
                self._server_thread.join(timeout=5)

            print("🔴 Сервер остановлен")
        except Exception as e:
            print(f"⚠️ Ошибка при остановке сервера: {e}")
        finally:
            self._server_running = False
            self._loop = None
            self._server_thread = None
            self._engine = None

    def do_status(self, arg: str) -> None:
        if not self._server_running or self._engine is None:
            print("Сервер не запущен")
            return
        try:
            status = self._run_in_server_loop(self._engine.get_status())
            print(_format_status(status))
        except Exception as e:
            print(f"Ошибка получения статуса: {e}")

    def do_cmw_status(self, arg: str) -> None:
        if not self._server_running or self._engine is None:
            print("Сервер не запущен")
            return
        try:
            status = self._run_in_server_loop(self._engine.cmw_status())
            print(_format_cmw_status(status))
        except Exception as e:
            print(f"Ошибка получения статуса CMW: {e}")

    def do_run_scenario(self, arg: str) -> None:
        if not arg.strip():
            print("Использование: run-scenario <path> [--connection-id <id>]")
            return

        parts = arg.split()
        scenario_path = parts[0]
        connection_id = None
        i = 1
        while i < len(parts):
            if parts[i] == "--connection-id" and i + 1 < len(parts):
                connection_id = parts[i + 1]
                i += 2
            else:
                i += 1

        if not self._server_running or self._engine is None:

            async def _run():
                return await _cmd_run_scenario(
                    argparse.Namespace(scenario_path=scenario_path, connection_id=connection_id)
                )

            self._run_short(_run())
            return

        try:
            result = self._run_in_server_loop(self._engine.run_scenario(scenario_path, connection_id))
            print(_format_scenario_result(result))
        except Exception as e:
            print(f"Ошибка выполнения сценария: {e}")

    def do_replay(self, arg: str) -> None:
        if not arg.strip():
            print("Использование: replay <log_path> [--scenario <path>]")
            return

        parts = arg.split()
        log_path = parts[0]
        scenario = None
        i = 1
        while i < len(parts):
            if parts[i] == "--scenario" and i + 1 < len(parts):
                scenario = parts[i + 1]
                i += 2
            else:
                i += 1

        if not self._server_running or self._engine is None:

            async def _run():
                return await _cmd_replay(argparse.Namespace(log_path=log_path, scenario=scenario))

            self._run_short(_run())
            return

        try:
            result = self._run_in_server_loop(self._engine.replay(log_path, scenario))
            print(_format_replay_result(result))
        except Exception as e:
            print(f"Ошибка replay: {e}")

    def do_export(self, arg: str) -> None:
        if not arg.strip():
            print("Использование: export <type> --format <fmt> --output <file>")
            return

        parts = arg.split()
        if len(parts) < 5:
            print("Использование: export <type> --format <fmt> --output <file>")
            return

        data_type = parts[0]
        fmt = None
        output = None
        i = 1
        while i < len(parts):
            if parts[i] == "--format" and i + 1 < len(parts):
                fmt = parts[i + 1]
                i += 2
            elif parts[i] == "--output" and i + 1 < len(parts):
                output = parts[i + 1]
                i += 2
            else:
                i += 1

        if not fmt or not output:
            print("Использование: export <type> --format <fmt> --output <file>")
            return

        if not self._server_running or self._engine is None:

            async def _run():
                return await _cmd_export(argparse.Namespace(data_type=data_type, format=fmt, output=output))

            self._run_short(_run())
            return

        try:
            result = self._run_in_server_loop(self._engine.export(data_type, fmt, output))
            print(_format_export_result(result))
        except Exception as e:
            print(f"Ошибка экспорта: {e}")

    def do_batch(self, arg: str) -> None:
        if not arg.strip():
            print("Использование: batch --scenario <name> [--scenario <name> ...] [--output FILE]")
            return

        parts = arg.split()
        scenarios: list[str] = []
        output_file = None
        i = 0
        while i < len(parts):
            if parts[i] == "--scenario" and i + 1 < len(parts):
                scenarios.append(parts[i + 1])
                i += 2
            elif parts[i] == "--output" and i + 1 < len(parts):
                output_file = parts[i + 1]
                i += 2
            else:
                i += 1

        if not scenarios:
            print("Использование: batch --scenario <name> [--scenario <name> ...] [--output FILE]")
            return

        async def _run_batch():
            return await _cmd_batch(argparse.Namespace(scenarios=scenarios, output=output_file))

        self._run_short(_run_batch())

    def do_exit(self, arg: str) -> bool:
        if self._server_running:
            self.do_stop("")
        return True

    def do_quit(self, arg: str) -> bool:
        return self.do_exit("")

    def do_EOF(self, arg: str) -> bool:
        print()
        return self.do_exit("")

    def emptyline(self) -> bool:
        return False


# ===== Точка входа =====


def main() -> None:
    """Точка входа для CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        # Без команды — запускаем REPL
        _cmd_monitor(None)
        sys.exit(0)

    # Маппинг команд на обработчики
    async_handlers: dict[str, Callable[[argparse.Namespace], Awaitable[int]]] = {
        "start": _cmd_start,
        "stop": _cmd_stop,
        "status": _cmd_status,
        "cmw-status": _cmd_cmw_status,
        "run-scenario": _cmd_run_scenario,
        "replay": _cmd_replay,
        "batch": _cmd_batch,
        "export": _cmd_export,
    }
    sync_handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "monitor": _cmd_monitor,
    }

    # sync-команды
    if args.command in sync_handlers:
        sys.exit(sync_handlers[args.command](args))

    # async-команды
    handler = async_handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    try:
        exit_code: int = asyncio.run(cast("Coroutine[Any, Any, int]", handler(args)))
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
