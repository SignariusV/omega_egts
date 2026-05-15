# OMEGA_EGTS GUI
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScenarioInfo:
    name: str
    path: Path
    json_file: Path


def scan_scenarios(scenarios_dir: Path) -> list[ScenarioInfo]:
    if not scenarios_dir.exists():
        return []
    info = []
    for entry in scenarios_dir.iterdir():
        if entry.is_dir():
            json_file = entry / "scenario.json"
            if json_file.exists():
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    name = data.get("name", entry.name)
                    info.append(ScenarioInfo(name, entry, json_file))
                except (json.JSONDecodeError, OSError):
                    pass
    return info


def get_default_scenarios_path() -> Optional[Path]:
    root = Path(__file__).parent.parent.parent
    candidates = [
        root / "scenarios",
        root / "tests" / "scenarios",
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None