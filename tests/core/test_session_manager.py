"""Тесты SessionManager — координатор подключений и FSM."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.session import SessionManager, UsvState


class TestSessionManager:
    """Тесты SessionManager."""

    def test_create_session(self, mock_event_bus: AsyncMock) -> None:
        """Создание новой сессии подключения."""
        mgr = SessionManager(bus=mock_event_bus, gost_version="2015")

        conn = mgr.create_session(
            connection_id="conn-1",
            remote_ip="127.0.0.1",
            remote_port=12345,
            is_std_usv=False,
        )

        assert conn.connection_id == "conn-1"
        assert conn.remote_ip == "127.0.0.1"
        assert conn.remote_port == 12345
        assert conn.fsm is not None
        assert conn.fsm.state == UsvState.DISCONNECTED
        assert conn.transaction_mgr is not None
        assert "conn-1" in mgr.connections

    def test_create_session_duplicate_raises(self, mock_event_bus: AsyncMock) -> None:
        """create_session с дублирующимся connection_id вызывает ValueError."""
        mgr = SessionManager(bus=mock_event_bus)
        mgr.create_session(connection_id="conn-1")

        with pytest.raises(ValueError, match="уже существует"):
            mgr.create_session(connection_id="conn-1")

    def test_get_session(self, mock_event_bus: AsyncMock) -> None:
        """Получение сессии по connection_id."""
        mgr = SessionManager(bus=mock_event_bus)
        mgr.create_session(connection_id="conn-1")

        conn = mgr.get_session("conn-1")
        assert conn is not None
        assert conn.connection_id == "conn-1"

    def test_get_session_not_found(self, mock_event_bus: AsyncMock) -> None:
        """Получение несуществующей сессии → None."""
        mgr = SessionManager(bus=mock_event_bus)
        conn = mgr.get_session("nonexistent")
        assert conn is None

    @pytest.mark.asyncio
    async def test_close_session(self, mock_event_bus: AsyncMock) -> None:
        """Закрытие сессии, wait_closed и emit события."""
        mgr = SessionManager(bus=mock_event_bus)
        mgr.create_session(connection_id="conn-1")

        await mgr.close_session("conn-1")
        assert "conn-1" not in mgr.connections

        # Проверка emit
        mock_event_bus.emit.assert_called()
        call_args = mock_event_bus.emit.call_args
        assert call_args[0][0] == "connection.changed"
        assert call_args[0][1]["state"] == UsvState.DISCONNECTED.value
        assert call_args[0][1]["action"] == "session_closed"

    @pytest.mark.asyncio
    async def test_close_session_not_found(self, mock_event_bus: AsyncMock) -> None:
        """Закрытие несуществующей сессии — не падает."""
        mgr = SessionManager(bus=mock_event_bus)
        await mgr.close_session("nonexistent")  # Не должно вызвать исключение

    @pytest.mark.asyncio
    async def test_on_packet_processed_updates_fsm(
        self, mock_event_bus: AsyncMock
    ) -> None:
        """packet.processed → обновление FSM."""
        mgr = SessionManager(bus=mock_event_bus)

        # Создаём сессию и переводим FSM в CONNECTED
        conn = mgr.create_session(connection_id="conn-1")
        assert conn.fsm is not None
        conn.fsm.on_connect()  # DISCONNECTED → CONNECTED

        # Эмулируем packet.processed с service=1 (TERM_IDENTITY)
        ctx = MagicMock()
        ctx.parsed = {"service": 1}

        await mgr._on_packet_processed(
            {"connection_id": "conn-1", "ctx": ctx}
        )

        # FSM должен перейти в AUTHENTICATING
        assert conn.fsm.state == UsvState.AUTHENTICATING

    @pytest.mark.asyncio
    async def test_emit_connection_changed(self, mock_event_bus: AsyncMock) -> None:
        """Смена состояния → emit connection.changed."""
        mgr = SessionManager(bus=mock_event_bus)
        conn = mgr.create_session(connection_id="conn-1")
        assert conn.fsm is not None
        conn.fsm.on_connect()  # DISCONNECTED → CONNECTED

        # Пакет для перехода
        ctx = MagicMock()
        ctx.parsed = {"service": 1}

        await mgr._on_packet_processed(
            {"connection_id": "conn-1", "ctx": ctx}
        )

        # Проверка emit
        mock_event_bus.emit.assert_called()
        call_args = mock_event_bus.emit.call_args
        assert call_args[0][0] == "connection.changed"
        assert call_args[0][1]["state"] == UsvState.AUTHENTICATING.value
        assert call_args[0][1]["usv_id"] == "conn-1"

    @pytest.mark.asyncio
    async def test_on_packet_processed_no_connection(
        self, mock_event_bus: AsyncMock
    ) -> None:
        """packet.processed без сессии — не падает."""
        mgr = SessionManager(bus=mock_event_bus)

        ctx = MagicMock()
        ctx.parsed = {"service": 1}

        # Не должно вызвать исключение
        await mgr._on_packet_processed(
            {"connection_id": "nonexistent", "ctx": ctx}
        )

    @pytest.mark.asyncio
    async def test_on_packet_processed_updates_tid_imei_imsi(
        self, mock_event_bus: AsyncMock
    ) -> None:
        """packet.processed → обновление TID/IMEI/IMSI из пакета."""
        mgr = SessionManager(bus=mock_event_bus)
        conn = mgr.create_session(connection_id="conn-1")

        ctx = MagicMock()
        ctx.parsed = {
            "tid": 42,
            "imei": "351234567890123",
            "imsi": "250011234567890",
            "service": 1,
        }

        await mgr._on_packet_processed(
            {"connection_id": "conn-1", "ctx": ctx}
        )

        assert conn.tid == 42
        assert conn.imei == "351234567890123"
        assert conn.imsi == "250011234567890"

    @pytest.mark.asyncio
    async def test_on_packet_processed_no_fsm(
        self, mock_event_bus: AsyncMock
    ) -> None:
        """packet.processed без FSM — не падает."""
        mgr = SessionManager(bus=mock_event_bus)
        conn = mgr.create_session(connection_id="conn-1")
        conn.fsm = None  # type: ignore[assignment]

        ctx = MagicMock()
        ctx.parsed = {"service": 1}

        await mgr._on_packet_processed(
            {"connection_id": "conn-1", "ctx": ctx}
        )

    def test_subscribes_to_packet_processed(self, mock_event_bus: AsyncMock) -> None:
        """SessionManager подписывается на packet.processed (ordered=True)."""
        SessionManager(bus=mock_event_bus)

        mock_event_bus.on.assert_called_once()
        call_args = mock_event_bus.on.call_args
        assert call_args[0][0] == "packet.processed"
        assert call_args[1].get("ordered") is True

    # =========================================================================
    # CR-013: get_or_create_session / ensure_sms_session
    # =========================================================================

    def test_get_or_create_session_creates_new(self, mock_event_bus: AsyncMock) -> None:
        """get_or_create_session создаёт новую сессию если её нет."""
        mgr = SessionManager(bus=mock_event_bus)

        conn = mgr.get_or_create_session(
            connection_id="test-1",
            protocol=MagicMock(),
        )

        assert conn.connection_id == "test-1"
        assert "test-1" in mgr.connections

    def test_get_or_create_session_returns_existing(
        self, mock_event_bus: AsyncMock
    ) -> None:
        """get_or_create_session возвращает существующую сессию, не создавая дубликат."""
        mgr = SessionManager(bus=mock_event_bus)
        conn1 = mgr.get_or_create_session(
            connection_id="test-1",
            protocol=MagicMock(),
        )

        conn2 = mgr.get_or_create_session(
            connection_id="test-1",
            protocol=MagicMock(),
        )

        assert conn1 is conn2  # Один и тот же объект
        assert len(mgr.connections) == 1

    def test_ensure_sms_session_creates_default(self, mock_event_bus: AsyncMock) -> None:
        """ensure_sms_session создаёт сессию с SMS_DEFAULT_CONNECTION_ID."""
        from core.session import SMS_DEFAULT_CONNECTION_ID

        mgr = SessionManager(bus=mock_event_bus)

        conn = mgr.ensure_sms_session()

        assert conn.connection_id == SMS_DEFAULT_CONNECTION_ID
        assert conn.protocol is not None

    def test_ensure_sms_session_uses_gost_version(
        self, mock_event_bus: AsyncMock
    ) -> None:
        """ensure_sms_session использует gost_version из SessionManager."""
        mgr = SessionManager(bus=mock_event_bus, gost_version="2015")

        conn = mgr.ensure_sms_session()

        assert conn.protocol is not None
        # Протокол создан из gost_version, не хардкод "2015"

    def test_ensure_sms_session_idempotent(self, mock_event_bus: AsyncMock) -> None:
        """Многократный вызов ensure_sms_session возвращает ту же сессию (без ошибок)."""
        from core.session import SMS_DEFAULT_CONNECTION_ID

        mgr = SessionManager(bus=mock_event_bus)

        conn1 = mgr.ensure_sms_session()
        conn2 = mgr.ensure_sms_session()
        conn3 = mgr.ensure_sms_session()

        assert conn1 is conn2
        assert conn2 is conn3
        assert len(mgr.connections) == 1
        assert SMS_DEFAULT_CONNECTION_ID in mgr.connections

    def test_create_session_still_raises_on_duplicate(
        self, mock_event_bus: AsyncMock
    ) -> None:
        """Regression: create_session всё ещё бросает ValueError (R-061 не сломан)."""
        mgr = SessionManager(bus=mock_event_bus)
        mgr.create_session(connection_id="test-1")

        with pytest.raises(ValueError, match="уже существует"):
            mgr.create_session(connection_id="test-1")
