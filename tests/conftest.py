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


# Config file fixture
@pytest.fixture
def sample_config_file(project_root: Path) -> Path:
    """Return the path to the default settings.json."""
    return project_root / "config" / "settings.json"


# Credentials file fixture
@pytest.fixture
def sample_credentials_file(project_root: Path) -> Path:
    """Return the path to the credentials.json template."""
    return project_root / "config" / "credentials.json"


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
def sample_config_dict() -> dict[str, object]:
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


# Sample credentials fixture
@pytest.fixture
def sample_credentials() -> list[dict[str, str]]:
    """Return sample credentials data."""
    return [
        {
            "imei": "351234567890123",
            "imsi": "250011234567890",
            "term_code": "TEST001",
            "auth_key": "test-key-001",
            "device_id": "USV-001",
            "description": "Test device 1",
        },
        {
            "imei": "351234567890124",
            "imsi": "250011234567891",
            "term_code": "TEST002",
            "auth_key": "test-key-002",
            "device_id": "USV-002",
            "description": "Test device 2",
        },
    ]


# Sample EGTS packet fixture (minimal valid structure placeholder)
@pytest.fixture
def sample_raw_packet() -> bytes:
    """Return a sample raw EGTS packet bytes (placeholder for now)."""
    # Will be replaced with actual valid EGTS packet once protocol lib is implemented
    return b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"


# Mock asyncio stream reader/writer
@pytest.fixture
def mock_stream_pair() -> tuple[AsyncMock, MagicMock]:
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
def mock_connection(mock_stream_pair: tuple[AsyncMock, MagicMock]) -> MagicMock:
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
