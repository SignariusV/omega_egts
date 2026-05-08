# OMEGA_EGTS GUI Tests
"""Test that settings persist across app restarts."""

import json
from pathlib import Path

from core.config import Config


def test_config_from_file_loads_saved_settings(tmp_path):
    """Test that Config.from_file() correctly loads saved settings."""
    # Create a custom settings.json in tmp_path
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_file = config_dir / "settings.json"

    custom_config = {
        "gost_version": "2023",
        "tcp_port": 12345,
        "tcp_host": "10.0.0.5",
        "cmw500": {
            "ip": "192.168.1.200",
            "simulate": True,
            "timeout": 10.0,
        },
        "timeouts": {
            "tl_response_to": 15.0,
        },
        "logging": {
            "level": "DEBUG",
        }
    }
    settings_file.write_text(json.dumps(custom_config, indent=2), encoding="utf-8")

    # Load config from file
    loaded = Config.from_file(str(settings_file))

    # Verify all values
    assert loaded.gost_version == "2023", f"gost_version mismatch: {loaded.gost_version}"
    assert loaded.tcp_port == 12345, f"tcp_port mismatch: {loaded.tcp_port}"
    assert loaded.tcp_host == "10.0.0.5", f"tcp_host mismatch: {loaded.tcp_host}"
    assert loaded.cmw500.ip == "192.168.1.200", f"cmw500.ip mismatch: {loaded.cmw500.ip}"
    assert loaded.cmw500.simulate == True, f"cmw500.simulate mismatch"
    assert loaded.timeouts.tl_response_to == 15.0, f"timeouts.tl_response_to mismatch"
    assert loaded.logging.level == "DEBUG", f"logging.level mismatch"

    print("✓ Config.from_file() correctly loads all nested values")


def test_main_window_loads_config_from_file(tmp_path, monkeypatch):
    """Test that MainWindow loads config from settings.json."""
    # Create a custom settings.json
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_file = config_dir / "settings.json"

    custom_config = {
        "gost_version": "2023",
        "tcp_port": 9999,
    }
    settings_file.write_text(json.dumps(custom_config, indent=2), encoding="utf-8")

    # Mock the PROJECT_ROOT in main_window to point to tmp_path
    # main_window.py calculates: Path(__file__).resolve().parent.parent
    # __file__ = gui/main_window.py -> parent = gui/ -> parent.parent = OMEGA_EGTS/
    # We need to make PROJECT_ROOT = tmp_path

    import gui.main_window as mw_module
    original_path = mw_module.Path

    # Mock Path to return tmp_path when calculating project root
    class MockPath:
        def __init__(self, *args, **kwargs):
            if args and args[0] == __file__:
                self._actual = original_path(*args, **kwargs)
            else:
                self._actual = original_path(*args, **kwargs)

        def resolve(self):
            # If this is main_window.py, return tmp_path/gui/main_window.py
            if hasattr(self._actual, 'name') and 'main_window.py' in str(self._actual):
                return MockPath(tmp_path / "gui" / "main_window.py")
            return MockPath(self._actual.resolve())

        @property
        def parent(self):
            return MockPath(self._actual.parent)

        def __truediv__(self, other):
            return self._actual.__truediv__(other)

        def __repr__(self):
            return f"MockPath({self._actual!r})"

        def exists(self):
            return self._actual.exists()

        def is_absolute(self):
            return self._actual.is_absolute()

        def __add__(self, other):
            return MockPath(self._actual.__add__(other))

    monkeypatch.setattr(mw_module, 'Path', MockPath)

    # Now create MainWindow - it should load from our settings.json
    from gui.main_window import MainWindow
    window = MainWindow()

    # Verify config was loaded
    assert window._config.tcp_port == 9999, \
        f"MainWindow didn't load saved port. Got: {window._config.tcp_port}"

    print("✓ MainWindow loads config from settings.json")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
