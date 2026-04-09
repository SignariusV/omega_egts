"""Тесты TransactionManager — отслеживание PID↔RPID, RN↔CRN."""

from __future__ import annotations

import time

import pytest

from core.session import PendingTransaction, TransactionManager

# =============================================================================
# PendingTransaction
# =============================================================================


class TestPendingTransaction:
    """Тесты PendingTransaction dataclass."""

    def test_create_transaction(self) -> None:
        """Создание транзакции с параметрами по умолчанию."""
        txn = PendingTransaction(pid=5, rn=3, step_name="auth_step")
        assert txn.pid == 5
        assert txn.rn == 3
        assert txn.step_name == "auth_step"
        assert txn.timeout == 5  # TL_RESPONSE_TO
        assert txn.is_expired is False

    def test_transaction_expires(self) -> None:
        """Транзакция истекает после timeout."""
        txn = PendingTransaction(pid=1, timeout=0.1)
        assert txn.is_expired is False

        time.sleep(0.15)
        assert txn.is_expired is True

    def test_repr(self) -> None:
        """Представление транзакции."""
        txn = PendingTransaction(pid=5, rn=3, step_name="test", timeout=10.0)
        repr_str = repr(txn)
        assert "pid=5" in repr_str
        assert "rn=3" in repr_str
        assert "step='test'" in repr_str
        assert "timeout=10.0" in repr_str


# =============================================================================
# TransactionManager
# =============================================================================


class TestTransactionManager:
    """Тесты TransactionManager."""

    def test_register_by_pid(self) -> None:
        """Регистрация транзакции по PID."""
        mgr = TransactionManager()
        mgr.register(pid=5, step_name="auth", timeout=10.0)

        txn = mgr.match_response(rpid=5)
        assert txn is not None
        assert txn.pid == 5
        assert txn.step_name == "auth"

    def test_register_by_rn(self) -> None:
        """Регистрация транзакции по RN."""
        mgr = TransactionManager()
        mgr.register(rn=3, step_name="telemetry", timeout=5.0)

        txn = mgr.match_response(crn=3)
        assert txn is not None
        assert txn.rn == 3
        assert txn.step_name == "telemetry"

    def test_match_by_rpid(self) -> None:
        """Поиск транзакции по Response Packet ID."""
        mgr = TransactionManager()
        mgr.register(pid=10, rn=7, step_name="step1")

        txn = mgr.match_response(rpid=10)
        assert txn is not None
        assert txn.pid == 10

        # Транзакция удалена после match
        txn2 = mgr.match_response(rpid=10)
        assert txn2 is None

    def test_match_by_crn(self) -> None:
        """Поиск транзакции по Confirm Record Number."""
        mgr = TransactionManager()
        mgr.register(pid=10, rn=7, step_name="step1")

        txn = mgr.match_response(crn=7)
        assert txn is not None
        assert txn.rn == 7

    def test_no_match(self) -> None:
        """Нет совпадений → None."""
        mgr = TransactionManager()
        mgr.register(pid=5)

        txn = mgr.match_response(rpid=999)
        assert txn is None

        txn = mgr.match_response(crn=999)
        assert txn is None

    def test_match_removes_from_both_maps(self) -> None:
        """Match удаляет транзакцию из обоих словарей."""
        mgr = TransactionManager()
        mgr.register(pid=10, rn=20, step_name="step1")

        # Match по PID
        txn = mgr.match_response(rpid=10)
        assert txn is not None

        # RN тоже удалён — match_response удаляет из _by_rn через txn.rn
        txn2 = mgr.match_response(crn=20)
        assert txn2 is None

    def test_cleanup_expired(self) -> None:
        """Удаление истёкших транзакций."""
        mgr = TransactionManager()

        # Создаём транзакции и вручную ставим created_at в прошлое
        mgr.register(pid=1, step_name="fast", timeout=1.0)
        mgr.register(pid=2, step_name="slow", timeout=100.0)

        # Делаем pid=1 истёкшим (ставим created_at давно)
        txn1 = mgr._by_pid[1]
        txn1.created_at = 1000.0  # Давным-давно

        expired = mgr.cleanup_expired()
        assert len(expired) == 1
        assert expired[0].step_name == "fast"

        # pid=2 всё ещё активна
        txn = mgr.match_response(rpid=2)
        assert txn is not None
        assert txn.step_name == "slow"

    def test_cleanup_removes_from_both_maps(self) -> None:
        """cleanup_expired удаляет из обоих словарей."""
        mgr = TransactionManager()
        mgr.register(pid=1, rn=10, step_name="test", timeout=1.0)

        # Делаем истёкшей
        txn = mgr._by_pid[1]
        txn.created_at = 1000.0

        expired = mgr.cleanup_expired()
        assert len(expired) == 1

        # Оба словаря пусты
        assert 1 not in mgr._by_pid
        assert 10 not in mgr._by_rn

    def test_cleanup_orphan_rn_only_transaction(self) -> None:
        """cleanup_expired удаляет транзакции, зарегистрированные только по rn."""
        mgr = TransactionManager()
        mgr.register(rn=99, step_name="orphan", timeout=1.0)

        # Проверяем, что она в _by_rn, но не в _by_pid
        assert 99 in mgr._by_rn
        assert len(mgr._by_pid) == 0

        # Делаем истёкшей
        txn = mgr._by_rn[99]
        txn.created_at = 1000.0

        expired = mgr.cleanup_expired()
        assert len(expired) == 1
        assert expired[0].step_name == "orphan"
        assert 99 not in mgr._by_rn

    def test_remove_txn_helper(self) -> None:
        """_remove_txn удаляет из обоих словарей."""
        mgr = TransactionManager()
        mgr.register(pid=5, rn=50, step_name="test")

        txn = mgr._by_pid[5]
        mgr._remove_txn(txn)

        assert 5 not in mgr._by_pid
        assert 50 not in mgr._by_rn

    def test_repr(self) -> None:
        """Представление менеджера."""
        mgr = TransactionManager()
        mgr.register(pid=1)
        mgr.register(pid=2)

        assert "pending=2" in repr(mgr)

    def test_duplicate_pid_raises(self) -> None:
        """Повторная регистрация того же PID вызывает ValueError."""
        mgr = TransactionManager()
        mgr.register(pid=5, step_name="first")

        with pytest.raises(ValueError, match="Дубликат PID"):
            mgr.register(pid=5, step_name="second")

    def test_duplicate_rn_raises(self) -> None:
        """Повторная регистрация того же RN вызывает ValueError."""
        mgr = TransactionManager()
        mgr.register(rn=10, step_name="first")

        with pytest.raises(ValueError, match="Дубликат RN"):
            mgr.register(rn=10, step_name="second")
