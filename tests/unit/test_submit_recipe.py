import pytest
import os
import sys
import json
import tempfile
from unittest.mock import patch, MagicMock
from scripts.submit_recipe import validate_recipe, main

pytestmark = pytest.mark.unit


class FakeDB:
    def __init__(self, item=None):
        self.item = item or {
            "id": "uuid-1",
            "custom_id": "ELN-CINEMATIC-123",
            "media_keys": ["raw/v1.mp4", "raw/v2.mp4", "raw/v3.mp4"],
            "status": "NEEDS_EDIT",
        }

    def get_content_by_custom_id(self, custom_id):
        if custom_id == self.item["custom_id"]:
            return dict(self.item)
        return None


def test_validate_valid_recipe(monkeypatch):
    """A valid full cinematic recipe passes validation and can be queued."""
    db = FakeDB()
    monkeypatch.setattr("scripts.submit_recipe.ElinaDB", lambda: db)

    valid_recipe = {
        "target_id": "ELN-CINEMATIC-123",
        "shots": [
            {"index": 1, "start": 0.0, "end": 2.0, "transition_out": {"type": "dissolve", "duration_sec": 0.5}},
            {"index": 2, "remove": True},
            {"index": 3, "freeze_tail_sec": 0.2, "transform": {"scale": 1.1, "x": 0, "y": 0}}
        ],
        "sfx": [
            {"query": "swoosh", "anchor": "shot_2.start", "offset_sec": -0.1},
            {"query": "ding", "start_sec": 4.5}
        ],
        "mute_original": False,
        "hook": "تست هوک مستقیم",
        "music": {"enabled": True, "query": "dramatic"}
    }

    # Should not raise any exception
    validate_recipe(valid_recipe)


def test_validate_invalid_shot_index(monkeypatch):
    """An invalid shot index is rejected before queue."""
    db = FakeDB()
    monkeypatch.setattr("scripts.submit_recipe.ElinaDB", lambda: db)

    invalid_recipe = {
        "target_id": "ELN-CINEMATIC-123",
        "shots": [
            {"index": 4}  # index out of range (max index 3)
        ]
    }

    with pytest.raises(ValueError, match="SHOT_INDEX_OUT_OF_RANGE"):
        validate_recipe(invalid_recipe)


def test_validate_invalid_transition(monkeypatch):
    """An invalid transition type is rejected before queue."""
    db = FakeDB()
    monkeypatch.setattr("scripts.submit_recipe.ElinaDB", lambda: db)

    invalid_recipe = {
        "target_id": "ELN-CINEMATIC-123",
        "shots": [
            {"index": 1, "transition_out": {"type": "crazy_zoom"}}
        ]
    }

    with pytest.raises(ValueError, match="TRANSITION_TYPE_INVALID"):
        validate_recipe(invalid_recipe)


def test_validate_all_shots_removed(monkeypatch):
    """Rejecting when all shots are removed."""
    db = FakeDB()
    monkeypatch.setattr("scripts.submit_recipe.ElinaDB", lambda: db)

    invalid_recipe = {
        "target_id": "ELN-CINEMATIC-123",
        "shots": [
            {"index": 1, "remove": True},
            {"index": 2, "remove": True},
            {"index": 3, "remove": True}
        ]
    }

    with pytest.raises(ValueError, match="PLAN_ALL_SHOTS_REMOVED"):
        validate_recipe(invalid_recipe)


def test_validate_invalid_sfx_anchor(monkeypatch):
    """Invalid SFX anchor is rejected before queue."""
    db = FakeDB()
    monkeypatch.setattr("scripts.submit_recipe.ElinaDB", lambda: db)

    invalid_recipe = {
        "target_id": "ELN-CINEMATIC-123",
        "shots": [
            {"index": 1},
            {"index": 2}
        ],
        "sfx": [
            {"query": "click", "anchor": "shot_3.start"}  # 3 is out of range since only 2 kept shots
        ]
    }

    with pytest.raises(ValueError, match="SFX_ANCHOR_OUT_OF_RANGE"):
        validate_recipe(invalid_recipe)


def test_submit_script_main_happy_path(monkeypatch):
    """Test script execution end-to-end with valid recipe queues job correctly."""
    db = FakeDB()
    monkeypatch.setattr("scripts.submit_recipe.ElinaDB", lambda: db)
    monkeypatch.setenv("OWNER_CHAT_ID", "12345")

    valid_recipe = {
        "target_id": "ELN-CINEMATIC-123",
        "shots": [
            {"index": 1, "transition_out": {"type": "dissolve", "duration_sec": 0.5}}
        ],
        "sfx": [
            {"query": "swoosh", "anchor": "shot_1.end", "offset_sec": -0.1}
        ]
    }

    mock_job = {"id": "job-injection-123"}
    mock_mgr = MagicMock()
    mock_mgr.queue_job.return_value = mock_job
    monkeypatch.setattr("scripts.submit_recipe.RenderJobManager", lambda: mock_mgr)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(valid_recipe, tmp)
        tmp_name = tmp.name

    try:
        monkeypatch.setattr(sys, "argv", ["scripts/submit_recipe.py", tmp_name])
        with pytest.raises(SystemExit) as sysexit:
            main()
        assert sysexit.value.code == 0
        mock_mgr.queue_job.assert_called_once_with(
            content_id="ELN-CINEMATIC-123",
            plan_data=valid_recipe,
            owner_chat_id="12345"
        )
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
