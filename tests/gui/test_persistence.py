# OMEGA_EGTS GUI
import pytest
from pathlib import Path
from gui.dashboard.persistence import PersistenceManager


def test_save_load_roundtrip(tmp_path):
    pm = PersistenceManager(tmp_path)
    snap = [{"card_id": "card1", "row": 0, "col": 0, "row_span": 1, "col_span": 1}]
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
    pm.default_layout.write_text('[{"card_id": "card1", "row": 0, "col": 0, "row_span": 1, "col_span": 1}]')
    data = pm.load_layout()
    assert isinstance(data, list)
    assert len(data) == 1


def test_layout_validation_missing_key(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.save_layout([{"card_id": "card1"}])
    data = pm.load_layout()
    assert isinstance(data, list)


def test_layout_validation_negative_span(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.save_layout([{"card_id": "card1", "row": 0, "col": 0, "row_span": -1, "col_span": 1}])
    data = pm.load_layout()
    assert data == []


def test_layout_validation_negative_position(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.save_layout([{"card_id": "card1", "row": -1, "col": 0, "row_span": 1, "col_span": 1}])
    data = pm.load_layout()
    assert data == []


def test_layout_validation_string_numbers(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.save_layout([{"card_id": "card1", "row": "0", "col": "0", "row_span": "1", "col_span": "1"}])
    data = pm.load_layout()
    assert data == []


def test_state_validation_not_dict(tmp_path):
    pm = PersistenceManager(tmp_path)
    pm.state_path.write_text('["not", "a", "dict"]')
    data = pm.load_state()
    assert isinstance(data, dict)


def test_save_creates_parent_dirs(tmp_path):
    pm = PersistenceManager(tmp_path / "nested" / "dir")
    pm.save_layout([{"card_id": "card1", "row": 0, "col": 0, "row_span": 1, "col_span": 1}])
    assert pm.layout_path.exists()