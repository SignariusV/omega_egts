# OMEGA_EGTS GUI
import json
from pathlib import Path
from typing import Any


class PersistenceManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.layout_path = base_dir / "layout.json"
        self.state_path = base_dir / "state.json"
        self.default_layout = base_dir / "resources/defaults/layout_default.json"
        self.default_state = base_dir / "resources/defaults/state_default.json"

    def save_layout(self, snapshot: list[dict]):
        with open(self.layout_path, 'w') as f:
            json.dump(snapshot, f, indent=2)

    def load_layout(self) -> list[dict]:
        if not self.layout_path.exists():
            return self._load_default(self.default_layout)
        try:
            with open(self.layout_path) as f:
                data = json.load(f)
            self._validate_layout(data)
            return data
        except Exception:
            return self._load_default(self.default_layout)

    def save_state(self, states: dict):
        with open(self.state_path, 'w') as f:
            json.dump(states, f, indent=2)

    def load_state(self) -> dict:
        if not self.state_path.exists():
            return self._load_default(self.default_state)
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except Exception:
            return self._load_default(self.default_state)

    def _load_default(self, path: Path):
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return [] if 'layout' in str(path) else {}

    def _validate_layout(self, data: list):
        if not isinstance(data, list):
            raise ValueError("Layout must be a list")
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Layout item must be a dict")
            required = ['id', 'row', 'col', 'row_span', 'col_span']
            for key in required:
                if key not in item:
                    raise ValueError(f"Missing required key: {key}")