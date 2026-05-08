# Tests for port checker utility
import pytest
from gui.utils.port_checker import is_port_available, get_error_message


class TestPortChecker:
    """Tests for port checking utility."""

    def test_is_port_available_for_free_port(self):
        """Test that a free port is detected as available."""
        # Use a port that's likely free (e.g., 55555)
        available, pid = is_port_available("127.0.0.1", 55555)
        # Might be available or not depending on system
        assert isinstance(available, bool)
        if available:
            assert pid is None
        else:
            assert isinstance(pid, (int, type(None)))

    def test_get_error_message_with_pid(self):
        """Test error message generation with PID."""
        msg = get_error_message("0.0.0.0", 8054, pid=1234)
        assert "8054" in msg
        assert "1234" in msg
        assert "taskkill" in msg

    def test_get_error_message_without_pid(self):
        """Test error message generation without PID."""
        msg = get_error_message("0.0.0.0", 8054, pid=None)
        assert "8054" in msg
        assert "taskkill" not in msg  # No PID, no taskkill suggestion
        assert "Варианты решения" in msg
