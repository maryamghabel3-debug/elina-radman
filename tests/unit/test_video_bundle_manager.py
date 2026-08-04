import pytest
import json
from unittest.mock import MagicMock
from agents.studio.bundle_manager import VideoBundleManager

pytestmark = pytest.mark.unit


class FakeDB:
    def __init__(self):
        self.items = {}
        self.inserted = []
        self.events = []

    def get_content_by_custom_id(self, custom_id):
        return self.items.get(custom_id)

    def insert_content(self, payload):
        self.inserted.append(payload)

    def log_event(self, content_id, event_type, from_status, to_status, actor, detail=""):
        self.events.append({
            "content_id": content_id,
            "event_type": event_type,
            "to_status": to_status,
            "actor": actor,
            "detail": detail
        })


def test_bundle_creation_preserves_source_order():
    db = FakeDB()
    db.items = {
        "ELN-RAW-1": {"id": "1", "custom_id": "ELN-RAW-1", "content_type": "reel", "media_keys": ["path/1.mp4"]},
        "ELN-RAW-2": {"id": "2", "custom_id": "ELN-RAW-2", "content_type": "reel", "media_keys": ["path/2.mp4"]},
        "ELN-RAW-3": {"id": "3", "custom_id": "ELN-RAW-3", "content_type": "reel", "media_keys": ["path/3.mp4"]},
    }
    manager = VideoBundleManager(db=db)
    result = manager.create_bundle("test-bundle", ["ELN-RAW-3", "ELN-RAW-1", "ELN-RAW-2"], "owner")

    assert result["ok"] is True
    assert len(db.inserted) == 1
    inserted_item = db.inserted[0]

    # Assert media keys are ordered exactly as requested
    assert inserted_item["media_keys"] == ["path/3.mp4", "path/1.mp4", "path/2.mp4"]


def test_bundle_requires_at_least_two_source_ids():
    db = FakeDB()
    manager = VideoBundleManager(db=db)

    result = manager.create_bundle("test-bundle", ["ELN-RAW-1"], "owner")
    assert result["ok"] is False
    assert "At least two source IDs" in result["error"]
    assert len(db.inserted) == 0


def test_missing_source_id_returns_error_and_does_not_insert():
    db = FakeDB()
    db.items = {
        "ELN-RAW-1": {"id": "1", "custom_id": "ELN-RAW-1", "content_type": "reel", "media_keys": ["path/1.mp4"]},
    }
    manager = VideoBundleManager(db=db)

    result = manager.create_bundle("test-bundle", ["ELN-RAW-1", "ELN-RAW-2"], "owner")
    assert result["ok"] is False
    assert "ELN-RAW-2" in result["error"]
    assert len(db.inserted) == 0


def test_source_item_without_media_keys_returns_error():
    db = FakeDB()
    db.items = {
        "ELN-RAW-1": {"id": "1", "custom_id": "ELN-RAW-1", "content_type": "reel", "media_keys": []},
        "ELN-RAW-2": {"id": "2", "custom_id": "ELN-RAW-2", "content_type": "reel", "media_keys": ["path/2.mp4"]},
    }
    manager = VideoBundleManager(db=db)

    result = manager.create_bundle("test-bundle", ["ELN-RAW-1", "ELN-RAW-2"], "owner")
    assert result["ok"] is False
    assert "no media keys" in result["error"]
    assert len(db.inserted) == 0


def test_original_source_records_are_not_modified():
    db = FakeDB()
    db.items = {
        "ELN-RAW-1": {"id": "1", "custom_id": "ELN-RAW-1", "content_type": "reel", "media_keys": ["path/1.mp4"]},
        "ELN-RAW-2": {"id": "2", "custom_id": "ELN-RAW-2", "content_type": "reel", "media_keys": ["path/2.mp4"]},
    }
    manager = VideoBundleManager(db=db)

    result = manager.create_bundle("test-bundle", ["ELN-RAW-1", "ELN-RAW-2"], "owner")
    assert result["ok"] is True

    # Assert original items remained unchanged
    assert db.items["ELN-RAW-1"] == {"id": "1", "custom_id": "ELN-RAW-1", "content_type": "reel", "media_keys": ["path/1.mp4"]}
    assert db.items["ELN-RAW-2"] == {"id": "2", "custom_id": "ELN-RAW-2", "content_type": "reel", "media_keys": ["path/2.mp4"]}


def test_new_parent_item_has_status_needs_edit():
    db = FakeDB()
    db.items = {
        "ELN-RAW-1": {"id": "1", "custom_id": "ELN-RAW-1", "content_type": "reel", "media_keys": ["path/1.mp4"]},
        "ELN-RAW-2": {"id": "2", "custom_id": "ELN-RAW-2", "content_type": "reel", "media_keys": ["path/2.mp4"]},
    }
    manager = VideoBundleManager(db=db)

    result = manager.create_bundle("test-bundle", ["ELN-RAW-1", "ELN-RAW-2"], "owner")
    assert result["ok"] is True
    assert len(db.inserted) == 1

    inserted_item = db.inserted[0]
    assert inserted_item["status"] == "NEEDS_EDIT"
    assert inserted_item["edit_status"] == "pending"


def test_new_parent_media_keys_contains_all_source_media_keys_in_order():
    db = FakeDB()
    db.items = {
        "ELN-RAW-1": {"id": "1", "custom_id": "ELN-RAW-1", "content_type": "reel", "media_keys": ["path/1.mp4"]},
        "ELN-RAW-2": {"id": "2", "custom_id": "ELN-RAW-2", "content_type": "reel", "media_keys": ["path/2-a.mp4", "path/2-b.mp4"]},
    }
    manager = VideoBundleManager(db=db)

    result = manager.create_bundle("test-bundle", ["ELN-RAW-1", "ELN-RAW-2"], "owner")
    assert result["ok"] is True

    inserted_item = db.inserted[0]
    assert inserted_item["media_keys"] == ["path/1.mp4", "path/2-a.mp4", "path/2-b.mp4"]


def test_editor_notes_contains_bundle_name_and_source_ids():
    db = FakeDB()
    db.items = {
        "ELN-RAW-1": {"id": "1", "custom_id": "ELN-RAW-1", "content_type": "reel", "media_keys": ["path/1.mp4"]},
        "ELN-RAW-2": {"id": "2", "custom_id": "ELN-RAW-2", "content_type": "reel", "media_keys": ["path/2.mp4"]},
    }
    manager = VideoBundleManager(db=db)

    result = manager.create_bundle("my-awesome-bundle", ["ELN-RAW-1", "ELN-RAW-2"], "owner")
    assert result["ok"] is True

    inserted_item = db.inserted[0]
    editor_notes = json.loads(inserted_item["editor_notes"])

    assert editor_notes["bundle_name"] == "my-awesome-bundle"
    assert editor_notes["source_custom_ids"] == ["ELN-RAW-1", "ELN-RAW-2"]
    assert editor_notes["clip_count"] == 2
    assert editor_notes["created_by"] == "owner"
