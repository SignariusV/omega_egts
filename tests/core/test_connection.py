"""Тесты UsvConnection — подключение с LRU-кэшем дубликатов."""

from collections import OrderedDict

from core.session import UsvConnection


class TestUsvConnection:
    """Тесты UsvConnection dataclass."""

    def test_create_connection(self) -> None:
        """Создание подключения с параметрами по умолчанию."""
        conn = UsvConnection(connection_id="conn-1")
        assert conn.connection_id == "conn-1"
        assert conn.remote_ip == ""
        assert conn.remote_port == 0
        assert conn.reader is None
        assert conn.writer is None
        assert conn.fsm is None
        assert conn.protocol is None
        assert conn.transaction_mgr is None
        assert conn.tid is None
        assert conn.imei is None
        assert conn.imsi is None
        assert conn.next_pid == 0
        assert conn.next_rn == 0
        assert conn._seen_pids == OrderedDict()

    def test_add_and_get_response(self) -> None:
        """Добавление RESPONSE и получение из кэша."""
        conn = UsvConnection(connection_id="conn-1")
        response = b"\x01\x02\x03"

        conn.add_pid_response(pid=5, response=response)
        result = conn.get_response(pid=5)

        assert result == response

    def test_get_response_not_found(self) -> None:
        """Получение несуществующего RESPONSE → None."""
        conn = UsvConnection(connection_id="conn-1")
        result = conn.get_response(pid=999)
        assert result is None

    def test_lru_eviction(self) -> None:
        """LRU: при превышении MAX_SEEN_PIDS удаляется oldest."""
        conn = UsvConnection(connection_id="conn-1")
        conn.MAX_SEEN_PIDS = 3  # Уменьшаем для теста

        # Добавляем 3 RESPONSE
        conn.add_pid_response(pid=1, response=b"resp1")
        conn.add_pid_response(pid=2, response=b"resp2")
        conn.add_pid_response(pid=3, response=b"resp3")

        assert conn.get_response(pid=1) == b"resp1"
        assert conn.get_response(pid=2) == b"resp2"
        assert conn.get_response(pid=3) == b"resp3"

        # Добавляем 4-й — должен удалить oldest (pid=1)
        conn.add_pid_response(pid=4, response=b"resp4")

        assert conn.get_response(pid=1) is None  # Evicted
        assert conn.get_response(pid=2) == b"resp2"
        assert conn.get_response(pid=3) == b"resp3"
        assert conn.get_response(pid=4) == b"resp4"

    def test_move_to_end(self) -> None:
        """Повторный get_response → move_to_end (обновление LRU)."""
        conn = UsvConnection(connection_id="conn-1")
        conn.MAX_SEEN_PIDS = 3

        conn.add_pid_response(pid=1, response=b"resp1")
        conn.add_pid_response(pid=2, response=b"resp2")
        conn.add_pid_response(pid=3, response=b"resp3")

        # Обращаемся к pid=1 — он становится самым новым
        conn.get_response(pid=1)

        # Добавляем pid=4 — теперь должен удалиться pid=2 (oldest)
        conn.add_pid_response(pid=4, response=b"resp4")

        assert conn.get_response(pid=1) == b"resp1"  # Сохранился
        assert conn.get_response(pid=2) is None  # Evicted
        assert conn.get_response(pid=3) == b"resp3"
        assert conn.get_response(pid=4) == b"resp4"

    def test_update_existing_pid(self) -> None:
        """Обновление RESPONSE для существующего PID."""
        conn = UsvConnection(connection_id="conn-1")

        conn.add_pid_response(pid=1, response=b"old")
        conn.add_pid_response(pid=1, response=b"new")

        result = conn.get_response(pid=1)
        assert result == b"new"

    def test_usv_id_with_tid(self) -> None:
        """usv_id возвращает TID если он установлен."""
        conn = UsvConnection(connection_id="conn-1")
        conn.tid = 42

        assert conn.usv_id == "42"

    def test_usv_id_without_tid(self) -> None:
        """usv_id возвращает connection_id если TID нет."""
        conn = UsvConnection(connection_id="conn-1")
        conn.tid = None

        assert conn.usv_id == "conn-1"
