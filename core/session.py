"""SessionManager, UsvConnection, UsvStateMachine, TransactionManager.

Модуль содержит:
- UsvState — enum состояний УСВ (7 состояний по ГОСТ 33465-2015)
- UsvStateMachine — конечный автомат состояний (18 переходов)
- UsvConnection — данные подключения с LRU-кэшем дубликатов
- TransactionManager — отслеживание PID↔RPID, RN↔CRN
- SessionManager — координатор подключений и FSM
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.event_bus import EventBus
from libs.egts_protocol_iface import TL_RESEND_ATTEMPTS, TL_RESPONSE_TO, IEgtsProtocol

# =============================================================================
# Состояния FSM
# =============================================================================


class UsvState(Enum):
    """Состояния УСВ с точки зрения сервера (телематической платформы).

    Таблица состояний:
    ┌────────────────┬─────────────────────────────────────────┬────────────────────┐
    │ Состояние      │ Описание                                │ Таймаут сервера    │
    ├────────────────┼─────────────────────────────────────────┼────────────────────┤
    │ DISCONNECTED   │ Нет TCP-соединения                      │ —                  │
    │ CONNECTED      │ TCP установлен, ждём первый пакет       │ 6с (NOT_AUTH_TO)   │
    │ AUTHENTICATING │ Получен TERM_IDENTITY, идёт авторизация │ 5с × 3 (RESPONSE)  │
    │ CONFIGURING    │ TID=0, ждём повторную авторизацию       │ 5с × 3 (RESPONSE)  │
    │ AUTHORIZED     │ RESULT_CODE(0) отправлен, ждём данные   │ 5с × 3 (RESPONSE)  │
    │ RUNNING        │ Основной режим — обмен данными          │ 5с × 3 (RESPONSE)  │
    │ ERROR          │ Критическая ошибка протокола            │ —                  │
    └────────────────┴─────────────────────────────────────────┴────────────────────┘
    """

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    CONFIGURING = "configuring"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    ERROR = "error"


# =============================================================================
# UsvStateMachine — FSM
# =============================================================================


class UsvStateMachine:
    """Конечный автомат состояний УСВ по ГОСТ 33465-2015.

    Реализует 18 переходов (таблица переходов):

    | Из              | В               | Триггер                        | Ссылка ГОСТ         |
    |-----------------|-----------------|--------------------------------|---------------------|
    | DISCONNECTED    | CONNECTED       | TCP connect                    | ГОСТ 6.7.2.9        |
    | CONNECTED       | AUTHENTICATING  | TERM_IDENTITY (service=1)      | ГОСТ 6.7.2.9        |
    | CONNECTED       | RUNNING         | eCall (service=10), штатное    | ГОСТ 6.7.2.9 п.1    |
    | CONNECTED       | DISCONNECTED    | Таймаут 6с                     | ГОСТ 6.8, Табл. 39  |
    | AUTHENTICATING  | CONFIGURING     | RESULT_CODE(153), TID=0        | ГОСТ 6.7.2.9        |
    | AUTHENTICATING  | AUTHORIZED      | RESULT_CODE(0)                 | ГОСТ 6.7.2.9        |
    | AUTHENTICATING  | DISCONNECTED    | RESULT_CODE(≠0,≠153)           | ГОСТ 6.7.2.9        |
    | AUTHENTICATING  | DISCONNECTED    | Таймаут 5с × 3                 | ГОСТ 5.4.1, 5.8     |
    | CONFIGURING     | AUTHENTICATING  | TERM_IDENTITY (TID>0)          | ГОСТ 6.7.2.9        |
    | CONFIGURING     | DISCONNECTED    | Таймаут 5с × 3                 | ГОСТ 5.4.1, 5.8     |
    | AUTHORIZED      | RUNNING         | Данные (service≠1)             | Логика FSM          |
    | AUTHORIZED      | AUTHENTICATING  | TERM_IDENTITY (переавторизация)| Логика FSM          |
    | RUNNING         | AUTHENTICATING  | TERM_IDENTITY (переавторизация)| Логика FSM          |
    | RUNNING         | DISCONNECTED    | Таймаут 5с × 3                 | ГОСТ 5.4.1, 5.8     |
    | RUNNING         | ERROR           | Ошибка CRC/формата             | ГОСТ 5.3, Прил. В   |
    | Любое           | DISCONNECTED    | TCP disconnect                 | —                   |
    | Любое (кроме    | ERROR           | Команда оператора              | —                   |
    | DISCONNECTED)   |                 |                                |                     |
    | ERROR           | DISCONNECTED    | TCP disconnect                 | —                   |

    Args:
        is_std_usv: Штатное УСВ (eCall-only, без авторизации)
    """

    def __init__(self, is_std_usv: bool = False) -> None:
        self._state = UsvState.DISCONNECTED
        self.is_std_usv = is_std_usv
        self._timeout_counter = 0
        self._last_transition: str | None = None

    @property
    def state(self) -> UsvState:
        """Текущее состояние FSM.

        Состояние изменяется только через _transition() — внешнему коду
        запрещено изменять _state напрямую (нарушает инкапсуляцию FSM).
        """
        return self._state

    @property
    def last_transition(self) -> str | None:
        """Причина последнего перехода (для логирования)."""
        return self._last_transition

    def _transition(self, new_state: UsvState, reason: str) -> UsvState:
        """Выполнить переход в новое состояние.

        Args:
            new_state: Целевое состояние
            reason: Причина перехода (для логирования)

        Returns:
            Новое состояние
        """
        old_state = self._state
        self._state = new_state
        self._last_transition = f"{old_state.value} → {new_state.value} ({reason})"

        # Сброс счётчика таймаутов при переходе
        if new_state != old_state:
            self._timeout_counter = 0

        return new_state

    def reset_timeout_counter(self) -> None:
        """Сбросить счётчик таймаутов.

        Вызывается при успешшем ответе от УСВ, когда FSM не переходит
        в новое состояние, но нужно сбросить счётчик ожидания.
        """
        self._timeout_counter = 0

    # ========================================================================
    # Обработчики событий
    # ========================================================================

    def on_connect(self) -> UsvState | None:
        """TCP-соединение установлено.

        Ссылка: ГОСТ 6.7.2.9

        Returns:
            Новое состояние или None
        """
        if self._state == UsvState.DISCONNECTED:
            return self._transition(UsvState.CONNECTED, "TCP connect")
        return None

    def on_disconnect(self) -> None:
        """TCP-соединение разорвано.

        Из любого состояния → DISCONNECTED
        """
        self._transition(UsvState.DISCONNECTED, "TCP disconnect")

    def on_packet(self, packet: dict[str, Any]) -> UsvState | None:
        """Обработка входящего пакета.

        Args:
            packet: Распарсенный пакет (service, tid, result_code, ...)

        Returns:
            Новое состояние или None
        """
        service = packet.get("service")

        handlers: dict[UsvState, Any] = {
            UsvState.CONNECTED: self._handle_connected,
            UsvState.AUTHENTICATING: self._handle_authenticating,
            UsvState.CONFIGURING: self._handle_configuring,
            UsvState.AUTHORIZED: self._handle_authorized,
            UsvState.RUNNING: self._handle_running,
        }

        handler = handlers.get(self._state)
        if handler is None:
            return None

        result: UsvState | None = handler(packet, service)
        return result

    def on_timeout(self) -> UsvState | None:
        """Обработка истёкшего таймаута.

        ВАЖНО: Этот метод следует вызывать ТОЛЬКО при фактическом истечении таймаута,
        а не на каждом тике таймера. Один вызов = один истёкший интервал.

        Таймауты по ГОСТ:
        - CONNECTED: EGTS_SL_NOT_AUTH_TO = 6с → DISCONNECTED
        - AUTHENTICATING/CONFIGURING/AUTHORIZED/RUNNING: TL_RESPONSE_TO = 5с × 3 → DISCONNECTED

        Returns:
            Новое состояние или None
        """
        # DISCONNECTED и ERROR — терминальные состояния, таймауты не применяются
        if self._state in (UsvState.DISCONNECTED, UsvState.ERROR):
            return None

        self._timeout_counter += 1

        if self._state == UsvState.CONNECTED:
            # 6с без TERM_IDENTITY → разрыв соединения
            return self._transition(UsvState.DISCONNECTED, "timeout EGTS_SL_NOT_AUTH_TO (6с)")

        if self._state in (
            UsvState.AUTHENTICATING,
            UsvState.CONFIGURING,
            UsvState.AUTHORIZED,
            UsvState.RUNNING,
        ):
            # 5с × 3 = 15с без ответа → разрыв соединения
            if self._timeout_counter >= TL_RESEND_ATTEMPTS:
                return self._transition(
                    UsvState.DISCONNECTED,
                    f"timeout TL_RESPONSE_TO (5с × {TL_RESEND_ATTEMPTS})",
                )
            # Таймаут не достиг лимита — продолжаем ждать
            return None

        return None

    def on_result_code_sent(self, result_code: int) -> UsvState | None:
        """Сервер отправил RESULT_CODE.

        Args:
            result_code: Код результата (0=OK, 153=ID_NOT_FOUND, 151=AUTH_DENIED, ...)

        Returns:
            Новое состояние или None
        """
        if self._state != UsvState.AUTHENTICATING:
            return None

        if result_code == 0:
            # Успешная авторизация
            return self._transition(UsvState.AUTHORIZED, "RESULT_CODE(0)")

        if result_code == 153:
            # TID=0, конфигурирование
            return self._transition(UsvState.CONFIGURING, "RESULT_CODE(153, TID=0)")

        # Ошибка авторизации (151, ...) → разрыв соединения
        return self._transition(
            UsvState.DISCONNECTED, f"RESULT_CODE({result_code}, auth error)"
        )

    def on_error(self, reason: str) -> UsvState | None:
        """Критическая ошибка протокола (CRC, формат).

        Args:
            reason: Описание ошибки

        Returns:
            Новое состояние или None
        """
        if self._state == UsvState.DISCONNECTED:
            return None
        return self._transition(UsvState.ERROR, f"protocol error: {reason}")

    def on_operator_command(self, command: str) -> UsvState | None:
        """Команда оператора (CLI/GUI).

        Args:
            command: Команда (например, "force_disconnect")

        Returns:
            Новое состояние или None
        """
        if self._state == UsvState.DISCONNECTED:
            return None

        if command == "force_disconnect":
            return self._transition(UsvState.ERROR, f"operator command: {command}")

        return None

    # ========================================================================
    # Обработчики по состояниям
    # ========================================================================

    def _handle_connected(
        self, packet: dict[str, Any], service: int | None
    ) -> UsvState | None:
        """Обработка пакета в состоянии CONNECTED.

        Переходы:
        - service=1 → AUTHENTICATING
        - service=10 (штатное УСВ) → RUNNING
        """
        if service == 1:
            # TERM_IDENTITY — начало авторизации
            return self._transition(UsvState.AUTHENTICATING, "TERM_IDENTITY (service=1)")

        if service == 10 and self.is_std_usv:
            # Штатное УСВ: eCall без авторизации
            return self._transition(UsvState.RUNNING, "eCall (service=10, штатное УСВ)")

        # Неожиданный пакет — состояние не меняется
        return None

    def _handle_authenticating(
        self, packet: dict[str, Any], service: int | None
    ) -> UsvState | None:
        """Обработка пакета в состоянии AUTHENTICATING.

        В этом состоянии сервер ждёт ответы от УСВ:
        - AUTH_INFO (subrecord_type=3) — данные авторизации от УСВ
        - RECORD_RESPONSE (subrecord_type=0x8000) — подтверждение от УСВ

        Переходы AUTHENTICATING → AUTHORIZED/CONFIGURING/DISCONNECTED
        обрабатываются через on_result_code_sent().
        """
        subrecord_type = packet.get("subrecord_type")

        if subrecord_type == 3:
            # EGTS_SR_AUTH_INFO — УСВ отправило данные авторизации
            # Сервер должен проверить credentials и отправить RESULT_CODE
            self._timeout_counter = 0
            return None

        if subrecord_type == 0x8000:
            # EGTS_SR_RECORD_RESPONSE — УСВ подтвердило получение
            # (AUTH_PARAMS или RESULT_CODE)
            rst = packet.get("record_status", 0)
            if rst != 0:
                # Ошибка на стороне УСВ — разрыв соединения
                return self._transition(
                    UsvState.DISCONNECTED,
                    f"RECORD_RESPONSE RST={rst} (ошибка УСВ)",
                )
            self._timeout_counter = 0
            return None

        # TERM_IDENTITY повторно — игнорируем
        return None

    def _handle_configuring(
        self, packet: dict[str, Any], service: int | None
    ) -> UsvState | None:
        """Обработка пакета в состоянии CONFIGURING.

        Переходы:
        - service=1, TID>0 → AUTHENTICATING (повторная авторизация)
        """
        if service == 1:
            tid = packet.get("tid")
            if tid is not None and tid > 0:
                return self._transition(
                    UsvState.AUTHENTICATING, f"TERM_IDENTITY (TID={tid})"
                )

        return None

    def _handle_authorized(
        self, packet: dict[str, Any], service: int | None
    ) -> UsvState | None:
        """Обработка пакета в состоянии AUTHORIZED.

        Переходы:
        - service≠1 → RUNNING (данные)
        - service=1 → AUTHENTICATING (переавторизация)
        """
        if service == 1:
            return self._transition(UsvState.AUTHENTICATING, "переавторизация (service=1)")

        if service is not None and service != 1:
            return self._transition(UsvState.RUNNING, f"данные (service={service})")

        return None

    def _handle_running(
        self, packet: dict[str, Any], service: int | None
    ) -> UsvState | None:
        """Обработка пакета в состоянии RUNNING.

        Переходы:
        - service=1 → AUTHENTICATING (переавторизация)
        """
        if service == 1:
            return self._transition(UsvState.AUTHENTICATING, "переавторизация (service=1)")

        return None

    def __repr__(self) -> str:
        return f"UsvStateMachine(state={self._state.value}, is_std_usv={self.is_std_usv})"


# =============================================================================
# PendingTransaction
# =============================================================================


@dataclass
class PendingTransaction:
    """Отслеживаемая транзакция (PID↔RPID, RN↔CRN).

    Attributes:
        pid: Packet ID запроса
        rn: Record Number запроса
        step_name: Имя шага сценария
        timeout: Таймаут ожидания (секунды)
        created_at: Время создания (timestamp)
    """

    pid: int | None = None
    rn: int | None = None
    step_name: str = ""
    timeout: float = TL_RESPONSE_TO
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Проверка истечения таймаута."""
        return (time.time() - self.created_at) > self.timeout

    def __repr__(self) -> str:
        return (
            f"PendingTransaction(pid={self.pid}, rn={self.rn}, "
            f"step={self.step_name!r}, timeout={self.timeout}s)"
        )


# =============================================================================
# TransactionManager
# =============================================================================


class TransactionManager:
    """Отслеживание соответствий запрос-ответ (PID↔RPID, RN↔CRN).

    Методы:
        register() — зарегистрировать транзакцию
        match_response() — найти транзакцию по RPID/CRN
        cleanup_expired() — удалить истёкшие транзакции
    """

    def __init__(self) -> None:
        self._by_pid: dict[int, PendingTransaction] = {}
        self._by_rn: dict[int, PendingTransaction] = {}

    def _remove_txn(self, txn: PendingTransaction) -> None:
        """Удалить транзакцию из обоих словарей."""
        if txn.pid is not None:
            self._by_pid.pop(txn.pid, None)
        if txn.rn is not None:
            self._by_rn.pop(txn.rn, None)

    def register(
        self,
        pid: int | None = None,
        rn: int | None = None,
        step_name: str = "",
        timeout: float = TL_RESPONSE_TO,
    ) -> None:
        """Зарегистрировать новую транзакцию.

        Args:
            pid: Packet ID
            rn: Record Number
            step_name: Имя шага сценария
            timeout: Таймаут ожидания

        Raises:
            ValueError: Если PID или RN уже зарегистрирован
        """
        if pid is not None and pid in self._by_pid:
            raise ValueError(f"Дубликат PID: {pid}")
        if rn is not None and rn in self._by_rn:
            raise ValueError(f"Дубликат RN: {rn}")

        txn = PendingTransaction(
            pid=pid, rn=rn, step_name=step_name, timeout=timeout
        )

        if pid is not None:
            self._by_pid[pid] = txn
        if rn is not None:
            self._by_rn[rn] = txn

    def match_response(
        self, rpid: int | None = None, crn: int | None = None
    ) -> PendingTransaction | None:
        """Найти транзакцию по Response Packet ID или Confirm Record Number.

        Args:
            rpid: Response Packet ID
            crn: Confirm Record Number

        Returns:
            Найденная транзакция или None
        """
        txn: PendingTransaction | None = None

        if rpid is not None:
            txn = self._by_pid.pop(rpid, None)
            if txn is not None:
                self._remove_txn(txn)

        if txn is None and crn is not None:
            txn = self._by_rn.pop(crn, None)
            if txn is not None:
                self._remove_txn(txn)

        return txn

    def cleanup_expired(self) -> list[PendingTransaction]:
        """Удалить истёкшие транзакции.

        Returns:
            Список удалённых транзакций
        """
        expired: list[PendingTransaction] = []

        for pid, txn in list(self._by_pid.items()):
            if txn.is_expired:
                expired.append(txn)
                del self._by_pid[pid]
                self._remove_txn(txn)

        # Чистим orphan-записи в _by_rn (транзакции только с rn, без pid)
        for rn, txn in list(self._by_rn.items()):
            if txn.is_expired:
                expired.append(txn)
                del self._by_rn[rn]

        return expired

    def __repr__(self) -> str:
        return f"TransactionManager(pending={len(self._by_pid)})"


# =============================================================================
# UsvConnection
# =============================================================================


@dataclass
class UsvConnection:
    """Состояние одного подключения УСВ.

    Attributes:
        connection_id: Уникальный идентификатор подключения
        remote_ip: IP-адрес клиента
        remote_port: Порт клиента
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        fsm: Конечный автомат состояний
        protocol: Реализация EGTS-протокола
        transaction_mgr: Менеджер транзакций
        tid: Terminal ID (из TERM_IDENTITY)
        imei: IMEI устройства
        imsi: IMSI SIM-карты
        next_pid: Следующий Packet ID для отправки
        next_rn: Следующий Record Number для отправки
    """

    connection_id: str
    remote_ip: str = ""
    remote_port: int = 0
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    fsm: UsvStateMachine | None = None
    protocol: IEgtsProtocol | None = None
    transaction_mgr: TransactionManager | None = None

    tid: int | None = None
    imei: str | None = None
    imsi: str | None = None

    next_pid: int = 0
    next_rn: int = 0

    # LRU-кэш для дубликатов PID
    _seen_pids: OrderedDict[int, bytes] = field(default_factory=OrderedDict)
    MAX_SEEN_PIDS: int = 65536

    def add_pid_response(self, pid: int, response: bytes) -> None:
        """Сохранить RESPONSE для PID в LRU-кэш.

        Args:
            pid: Packet ID
            response: Байты RESPONSE-пакета
        """
        if pid in self._seen_pids:
            self._seen_pids.move_to_end(pid)
        self._seen_pids[pid] = response

        # Eviction oldest
        if len(self._seen_pids) > self.MAX_SEEN_PIDS:
            self._seen_pids.popitem(last=False)

    def get_response(self, pid: int) -> bytes | None:
        """Получить RESPONSE для PID из LRU-кэша.

        Args:
            pid: Packet ID

        Returns:
            Байты RESPONSE или None
        """
        if pid in self._seen_pids:
            self._seen_pids.move_to_end(pid)
            return self._seen_pids[pid]
        return None

    @property
    def usv_id(self) -> str:
        """Идентификатор УСВ (TID если есть, иначе connection_id)."""
        return str(self.tid) if self.tid is not None else self.connection_id


# =============================================================================
# SessionManager
# =============================================================================


class SessionManager:
    """Координатор подключений УСВ.

    Управляет:
    - Создание/закрытие сессий
    - Обновление FSM при обработке пакетов
    - Подписка на packet.processed (ordered=True)

    Args:
        bus: EventBus для подписки на события
        gost_version: Версия ГОСТ (2015/2023)
    """

    def __init__(self, bus: EventBus, gost_version: str = "2015") -> None:
        self.bus = bus
        self.connections: dict[str, UsvConnection] = {}
        self.gost_version = gost_version

        # Подписка на packet.processed (ordered=True для FSM)
        self.bus.on("packet.processed", self._on_packet_processed, ordered=True)

    def create_session(
        self,
        connection_id: str,
        remote_ip: str = "",
        remote_port: int = 0,
        reader: asyncio.StreamReader | None = None,
        writer: asyncio.StreamWriter | None = None,
        protocol: IEgtsProtocol | None = None,
        is_std_usv: bool = False,
    ) -> UsvConnection:
        """Создать новую сессию подключения.

        Args:
            connection_id: Уникальный идентификатор
            remote_ip: IP клиента
            remote_port: Порт клиента
            reader: StreamReader
            writer: StreamWriter
            protocol: EGTS-протокол
            is_std_usv: Штатное УСВ (eCall-only)

        Returns:
            Новый объект UsvConnection

        Raises:
            ValueError: Если сессия с таким connection_id уже существует
        """
        if connection_id in self.connections:
            raise ValueError(f"Сессия {connection_id} уже существует")

        # Автоматическое создание протокола, если не передан (CR-008)
        if protocol is None:
            from libs.egts_protocol_iface import create_protocol

            protocol = create_protocol(self.gost_version)

        fsm = UsvStateMachine(is_std_usv=is_std_usv)
        txn_mgr = TransactionManager()

        conn = UsvConnection(
            connection_id=connection_id,
            remote_ip=remote_ip,
            remote_port=remote_port,
            reader=reader,
            writer=writer,
            fsm=fsm,
            protocol=protocol,
            transaction_mgr=txn_mgr,
        )

        self.connections[connection_id] = conn
        return conn

    def get_session(self, connection_id: str) -> UsvConnection | None:
        """Получить сессию по connection_id.

        Args:
            connection_id: Идентификатор подключения

        Returns:
            UsvConnection или None
        """
        return self.connections.get(connection_id)

    async def close_session(self, connection_id: str) -> None:
        """Закрыть сессию, дождаться закрытия writer, эмитить событие.

        Args:
            connection_id: Идентификатор подключения
        """
        conn = self.connections.pop(connection_id, None)
        if conn and conn.writer and not conn.writer.is_closing():
            conn.writer.close()
            with contextlib.suppress(asyncio.TimeoutError, OSError):
                await asyncio.wait_for(conn.writer.wait_closed(), timeout=2.0)

        if conn:
            await self.bus.emit(
                "connection.changed",
                {
                    "usv_id": conn.usv_id,
                    "state": UsvState.DISCONNECTED.value,
                    "action": "session_closed",
                },
            )

    async def _on_packet_processed(self, data: dict[str, Any]) -> None:
        """Обработчик события packet.processed — обновление FSM.

        Args:
            data: Данные события (ctx, connection_id)
        """
        connection_id: str | None = data.get("connection_id")
        ctx = data.get("ctx")

        if connection_id is None:
            return

        conn = self.connections.get(connection_id)
        if conn is None or conn.fsm is None:
            return

        # Извлечение parsed данных из контекста
        parsed: dict[str, Any] = {}
        if ctx is not None:
            raw_parsed = getattr(ctx, "parsed", None)
            if raw_parsed is not None:
                # ctx.parsed может быть ParseResult или dict
                if hasattr(raw_parsed, "packet"):
                    # ParseResult — извлекаем данные из packet и extra
                    parsed = dict(getattr(raw_parsed, "extra", {}) or {})
                    if raw_parsed.packet is not None and raw_parsed.packet.records:
                        # Берём service_type из первой записи
                        parsed.setdefault("service", raw_parsed.packet.records[0].service_type)
                        # Извлекаем данные из подзаписей первой записи
                        for sr in raw_parsed.packet.records[0].subrecords:
                            if isinstance(sr.data, dict):
                                parsed.update(sr.data)
                elif isinstance(raw_parsed, dict):
                    parsed = raw_parsed
                # Для ParseResult без пакета — оставляем пустой dict

        # Пакет без service — ошибка парсинга, FSM не обрабатывает
        if "service" not in parsed:
            return

        # Обновление TID/IMEI/IMSI из пакета
        if "tid" in parsed:
            conn.tid = parsed["tid"]
        if "imei" in parsed:
            conn.imei = parsed["imei"]
        if "imsi" in parsed:
            conn.imsi = parsed["imsi"]

        # Передача пакета в FSM
        new_state = conn.fsm.on_packet(parsed)

        # Emit connection.changed при смене состояния
        if new_state is not None:
            try:
                await self.bus.emit(
                    "connection.changed",
                    {
                        "connection_id": conn.connection_id,
                        "usv_id": conn.usv_id,
                        "state": new_state.value,
                        "action": "state_transition",
                        "reason": f"FSM: {conn.fsm.last_transition}",
                    },
                )
            except Exception:
                # Ошибка в subscriber не должна блокировать FSM
                # (contextlib.suppress не работает с async — SIM105 false positive)
                pass
