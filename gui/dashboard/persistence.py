# OMEGA_EGTS GUI
import json
import logging
from pathlib import Path


logger = logging.getLogger(__name__)


class PersistenceManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.layout_path = base_dir / "layout.json"
        self.state_path = base_dir / "state.json"
        self.default_layout = base_dir / "resources/defaults/layout_default.json"
        self.default_state = base_dir / "resources/defaults/state_default.json"

    def save_layout(self, snapshot: list[dict]) -> None:
        try:
            self.layout_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.layout_path, 'w') as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            logger.error("Failed to save layout: %s", e)

    def load_layout(self) -> list[dict]:
        if not self.layout_path.exists():
            return self._load_default(self.default_layout, is_layout=True)
        try:
            with open(self.layout_path) as f:
                data = json.load(f)
            self._validate_layout(data)
            return data
        except Exception as e:
            logger.warning("Could not load layout, using default: %s", e)
            return self._load_default(self.default_layout, is_layout=True)

    def save_state(self, states: dict) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, 'w') as f:
                json.dump(states, f, indent=2)
        except Exception as e:
            logger.error("Failed to save state: %s", e)

    def load_state(self) -> dict:
        if not self.state_path.exists():
            return self._load_default(self.default_state, is_layout=False)
        try:
            with open(self.state_path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"State must be a dict, got {type(data).__name__}")
            return data
        except Exception as e:
            logger.warning("Could not load state, using default: %s", e)
            return self._load_default(self.default_state, is_layout=False)

    def _load_default(self, path: Path, is_layout: bool) -> list[dict] | dict:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            if is_layout:
                try:
                    self._validate_layout(data)
                except ValueError as e:
                    logger.warning("Invalid default layout, ignoring: %s", e)
                    return []
            return data
        return [] if is_layout else {}

    def _validate_layout(self, data: list) -> None:
        if not isinstance(data, list):
            raise ValueError("Layout must be a list")
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Layout item must be a dict")
            if 'card_id' not in item:
                raise ValueError("Missing required key: card_id")
            if not isinstance(item['card_id'], str):
                raise ValueError(f"card_id must be a string, got {type(item['card_id']).__name__}")
            for req in ('row', 'col', 'row_span', 'col_span'):
                if req not in item:
                    raise ValueError(f"Missing required key: {req}")
                if not isinstance(item[req], int):
                    raise ValueError(f"{req} must be an int, got {type(item[req]).__name__}")
                if item[req] < 1 and req in ('row_span', 'col_span'):
                    raise ValueError(f"{req} must be >= 1, got {item[req]}")
                if item[req] < 0 and req in ('row', 'col'):
                    raise ValueError(f"{req} must be >= 0, got {item[req]}")

    def reset_to_defaults(self) -> None:
        """Delete saved layout and state files to reset to defaults."""
        for path in (self.layout_path, self.state_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass