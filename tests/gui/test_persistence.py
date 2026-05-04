# OMEGA_EGTS GUI
import pytest
from pathlib import Path
from gui.dashboard.persistence import PersistenceManager


def test_save_load_roundtrip(tmp_path):
    pm = PersistenceManager(tmp_path)
    snap = [{"id": 1, "row": 0, "col": 0, "row_span": 1, "col_span": 1}]
    pm.save_layout(snap)
    assert pm.load_layout() == snap


def test_corrupted_json_fallback(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.layout_path.write_text("not json")
    data = pm.load_layout()
    assert isinstance(data, list)


def test_state_save_load_roundtrip(tmp_path):
    pm = PersistenceManager(tmp_path)
    state = {"card1": {"collapsed": True}, "card2": {"filter": "test"}}
    pm.save_state(state)
    loaded = pm.load_state()
    assert loaded == state


def test_state_corrupted_fallback(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.state_path.write_text("{ broken")
    data = pm.load_state()
    assert isinstance(data, dict)


def test_missing_layout_returns_default(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.default_layout.parent.mkdir(parents=True, exist_ok=True)
    pm.default_layout.write_text('[{"id": 0, "row": 0, "col": 0, "row_span": 1, "col_span": 1}]')
    data = pm.load_layout()
    assert isinstance(data, list)
    assert len(data) == 1


def test_layout_validation_missing_key(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.save_layout([{"id": 1}])
    data = pm.load_layout()
    assert isinstance(data, list)