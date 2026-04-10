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

import argparse
import asyncio
import json
import sys
from cmd import Cmd
from pathlib import Path
from typing import Any

# Точка входа для pyproject.toml


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
        "--gost", choices=["2015", "2023"], default="2015",
        help="Версия ГОСТ (по умолч. 2015)",
    )
    p_start.add_argument("--cmw", type=str, default=None, help="IP CMW-500")
    p_start.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO", help="Уровень логирования",
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
        "--connection-id", default=None, help="Идентификатор подключения",
    )

    # replay
    p_replay = sub.add_parser("replay", help="Replay JSONL-лога")
    p_replay.add_argument("log_path", help="Путь к JSONL-файлу")
    p_replay.add_argument("--scenario", default=None, help="Путь к сценарию (опционально)")

    # batch
    p_batch = sub.add_parser("batch", help="Пакетный запуск сценариев")
    p_batch.add_argument(
        "--scenario", action="append", dest="scenarios", required=True,
        help="Имя или путь к сценарию (можно указывать несколько раз)",
    )
    p_batch.add_argument("--output", default=None, help="Файл отчёта (JSON)")

    # export
    p_export = sub.add_parser("export", help="Выгрузка данных")
    p_export.add_argument(
        "data_type", choices=["packets", "connections", "scenarios"],
        help="Тип данных для выгрузки",
    )
    p_export.add_argument(
        "--format", choices=["csv", "json"], required=True, help="Формат выгрузки",
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
    if data.get("connected"):
        lines = ["🟢 CMW-500 подключён"]
        for key, value in data.items():
            if key != "connected":
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)
    else:
        return f"🔴 CMW-500 не подключён: {data.get('error', 'неизвестная ошибка')}"


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


# ===== Асинхронные обработчики =====


async def _cmd_start(args: argparse.Namespace) -> int:
    """Обработать команду start."""
    from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
    from core.engine import CoreEngine
    from core.event_bus import EventBus

    config = Config(
        gost_version=args.gost,
        tcp_port=args.port,
        cmw500=CmwConfig(ip=args.cmw) if args.cmw else CmwConfig(),
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


async def _cmd_cmw_status(args: argparse.Namespace) -> int:
    """Обработать команду cmw-status.

    Примечание: показывает конфиг CMW-500. Реальный статус
    доступен только при подключённом сервере (REPL monitor).
    """
    from core.config import Config

    config = Config()
    ip = config.cmw500.ip
    if ip:
        print(f"CMW-500: {ip} (подключение при запуске сервера)")
    else:
        print("CMW-500: не настроен (укажите --cmw IP при запуске)")
    return 0


async def _cmd_run_scenario(args: argparse.Namespace) -> int:
    """Обработать команду run-scenario."""
    from core.config import Config
    from core.engine import CoreEngine
    from core.event_bus import EventBus

    config = Config()
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    await engine.start()
    try:
        result = await engine.run_scenario(
            args.scenario_path,
            connection_id=args.connection_id,
        )
        print(_format_scenario_result(result))
        return 0 if result.get("status") == "PASS" else 1
    finally:
        await engine.stop()


async def _cmd_replay(args: argparse.Namespace) -> int:
    """Обработать команду replay."""
    from core.config import Config
    from core.engine import CoreEngine
    from core.event_bus import EventBus

    config = Config()
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    await engine.start()
    try:
        result = await engine.replay(args.log_path, args.scenario)
        print(_format_replay_result(result))
        return 0
    finally:
        await engine.stop()


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
            # Поддержка имён и полных путей
            if "/" in scenario_name or "\\" in scenario_name:
                scenario_path = scenario_name
            else:
                scenario_path = f"scenarios/{scenario_name}/"
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
    from core.config import Config
    from core.engine import CoreEngine
    from core.event_bus import EventBus

    config = Config()
    bus = EventBus()
    engine = CoreEngine(config=config, bus=bus)

    await engine.start()
    try:
        result = await engine.export(args.data_type, args.format, args.output)
        print(_format_export_result(result))
        return 0
    finally:
        await engine.stop()


async def _cmd_monitor(args: argparse.Namespace) -> int:
    """Обработать команду monitor — запустить REPL."""
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

    def __init__(self) -> None:
        super().__init__()
        self._engine: Any = None
        self._config: Any = None
        self._bus: Any = None

    def _ensure_engine(self) -> None:
        """Лениво создать CoreEngine."""
        if self._engine is None:
            from core.config import Config
            from core.engine import CoreEngine
            from core.event_bus import EventBus

            self._config = Config()
            self._bus = EventBus()
            self._engine = CoreEngine(config=self._config, bus=self._bus)

    def _run(self, coro: Any) -> Any:
        """Запустить async-корутину в REPL."""
        return asyncio.get_event_loop().run_until_complete(coro)

    def do_start(self, arg: str) -> None:
        """Запустить сервер: start [--port PORT] [--gost VERSION] [--cmw IP]"""
        if self._engine is not None and self._engine.is_running:
            print("Сервер уже запущен")
            return

        # Парсим опции из строки arg
        parts = arg.split()
        port = 3001
        gost = "2015"
        cmw_ip = None
        i = 0
        while i < len(parts):
            if parts[i] == "--port" and i + 1 < len(parts):
                port = int(parts[i + 1])
                i += 2
            elif parts[i] == "--gost" and i + 1 < len(parts):
                gost = parts[i + 1]
                i += 2
            elif parts[i] == "--cmw" and i + 1 < len(parts):
                cmw_ip = parts[i + 1]
                i += 2
            else:
                i += 1

        # Пересоздаём Engine с новыми параметрами
        from core.config import CmwConfig, Config, LogConfig, TimeoutsConfig
        from core.engine import CoreEngine
        from core.event_bus import EventBus

        self._config = Config(
            gost_version=gost,
            tcp_port=port,
            cmw500=CmwConfig(ip=cmw_ip) if cmw_ip else CmwConfig(),
            logging=LogConfig(),
            timeouts=TimeoutsConfig(),
        )
        self._bus = EventBus()
        self._engine = CoreEngine(config=self._config, bus=self._bus)

        self._run(self._engine.start())
        print(f"✅ Сервер запущен на порту {port}, ГОСТ {gost}")

    def do_stop(self, arg: str) -> None:
        """Остановить сервер: stop"""
        if self._engine is None or not self._engine.is_running:
            print("Сервер не запущен")
            return
        self._run(self._engine.stop())
        print("🔴 Сервер остановлен")

    def do_status(self, arg: str) -> None:
        """Показать статус системы: status"""
        self._ensure_engine()
        status = self._run(self._engine.get_status())
        print(_format_status(status))

    def do_cmw_status(self, arg: str) -> None:
        """Показать статус CMW-500: cmw-status"""
        self._ensure_engine()
        status = self._run(self._engine.cmw_status())
        print(_format_cmw_status(status))

    def do_run_scenario(self, arg: str) -> None:
        """Запустить сценарий: run-scenario <path> [--connection-id <id>]"""
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

        self._ensure_engine()
        if not self._engine.is_running:
            print("Сначала запустите сервер: start")
            return

        result = self._run(self._engine.run_scenario(scenario_path, connection_id))
        print(_format_scenario_result(result))

    def do_replay(self, arg: str) -> None:
        """Replay лога: replay <log_path> [--scenario <path>]"""
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

        self._ensure_engine()
        if not self._engine.is_running:
            print("Сначала запустите сервер: start")
            return

        result = self._run(self._engine.replay(log_path, scenario))
        print(_format_replay_result(result))

    def do_export(self, arg: str) -> None:
        """Выгрузка данных: export <type> --format <fmt> --output <file>"""
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

        self._ensure_engine()
        if not self._engine.is_running:
            print("Сначала запустите сервер: start")
            return

        result = self._run(self._engine.export(data_type, fmt, output))
        print(_format_export_result(result))

    def do_exit(self, arg: str) -> bool:
        """Выйти из REPL: exit"""
        if self._engine and self._engine.is_running:
            self._run(self._engine.stop())
            print("🔴 Сервер остановлен")
        return True

    def do_quit(self, arg: str) -> bool:
        """Выйти из REPL: quit"""
        return self.do_exit("")

    def do_EOF(self, arg: str) -> bool:  # noqa: N802
        """Обработка Ctrl+D."""
        print()
        return self.do_exit("")

    def emptyline(self) -> bool:
        """Пустая строка — ничего не делать."""
        return False


# ===== Точка входа =====


def main() -> None:
    """Точка входа для CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Маппинг команд на обработчики
    handlers = {
        "start": _cmd_start,
        "stop": _cmd_stop,
        "status": _cmd_status,
        "cmw-status": _cmd_cmw_status,
        "run-scenario": _cmd_run_scenario,
        "replay": _cmd_replay,
        "batch": _cmd_batch,
        "export": _cmd_export,
        "monitor": _cmd_monitor,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    exit_code = asyncio.run(handler(args))
    sys.exit(exit_code)
