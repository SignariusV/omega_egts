"""Shared pytest fixtures for OMEGA_EGTS tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# Project root fixture
@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).resolve().parent.parent


# Temp directory fixture
@pytest.fixture
def tmp_log_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for log files."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


# Mock event bus fixture
@pytest.fixture
def mock_event_bus() -> AsyncMock:
    """Return a mock EventBus with async methods."""
    bus = AsyncMock()
    bus.emit = AsyncMock()
    bus.on = MagicMock()
    bus.off = MagicMock()
    return bus


# Sample config fixture
@pytest.fixture
def sample_config_dict() -> dict:
    """Return a sample configuration dictionary."""
    return {
        "gost_version": "2015",
        "tcp_port": 3001,
        "tcp_host": "0.0.0.0",
        "cmw500": {
            "ip": "192.168.1.100",
            "timeout": 5,
            "retries": 3,
            "sms_send_timeout": 10,
            "status_poll_interval": 2,
        },
        "timeouts": {
            "TL_RESPONSE_TO": 5,
            "TL_RESEND_ATTEMPTS": 3,
            "TL_RECONNECT_TO": 30,
            "EGTS_SL_NOT_AUTH_TO": 6,
        },
        "logging": {
            "level": "INFO",
            "dir": "./logs",
            "rotation": "daily",
            "max_size_mb": 100,
            "retention_days": 30,
        },
    }


# Sample EGTS packet fixture (minimal valid structure placeholder)
@pytest.fixture
def sample_raw_packet() -> bytes:
    """Return a sample raw EGTS packet bytes (placeholder for now)."""
    # Will be replaced with actual valid EGTS packet once protocol lib is implemented
    return b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"


# Mock asyncio stream reader/writer
@pytest.fixture
def mock_stream_pair():
    """Return mock (reader, writer) pair for TCP connection tests."""
    reader = AsyncMock()
    writer = AsyncMock()
    writer.get_extra_info = MagicMock(return_value=("127.0.0.1", 12345))
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    return reader, writer


# Mock connection
@pytest.fixture
def mock_connection(mock_stream_pair):
    """Return a mock UsvConnection-like object."""
    reader, writer = mock_stream_pair
    conn = MagicMock()
    conn.reader = reader
    conn.writer = writer
    conn.connection_id = "test-conn-id"
    conn.fsm = MagicMock()
    conn.protocol = None
    conn.transaction_mgr = MagicMock()
    conn.tid = None
    conn.imei = None
    conn.imsi = None
    conn._seen_pids = {}
    conn.get_response = MagicMock(return_value=None)
    conn.add_pid_response = MagicMock()
    return conn
