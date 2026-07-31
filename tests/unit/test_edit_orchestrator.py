import pytest
from agents.editing.orchestrator import EditOrchestrator

pytestmark = pytest.mark.unit


class FakeDB:
    def __init__(self, item=None):
        self.item = item or {
            "id": "uuid-1",
            "custom_id": "ELN-RAW-TEST",
            "content_type": "reel",
            "media_keys": ["raw/video.mp4"],
            "status": "NEEDS_EDIT",
        }
        self.status_updates = []
        self.events = []

    def get_content_by_custom_id(self, custom_id):
        if custom_id == self.item["custom_id"]:
            return dict(self.item)
        return None

    def update_status(self, item_id, new_status, extra=None):
        self.status_updates.append((new_status, extra or {}))
        return []

    def log_event(self, content_id, event_type, from_status, to_status, actor, detail=""):
        self.events.append(event_type)
        return []


class FakeStorage:
    def __init__(self):
        self.downloads = []
        self.uploads = []

    def download_file(self, storage_path, local_path):
        self.downloads.append((storage_path, local_path))
        with open(local_path, "wb") as f:
            f.write(b"0" * 20000)
        return local_path

    def upload_file(self, local_file_path, destination_path, content_type=None):
        self.uploads.append((local_file_path, destination_path, content_type))
        return destination_path


class FakeTypography:
    def render_text_to_png(self, text, output_path, **kwargs):
        with open(output_path, "wb") as f:
            f.write(b"fake png")
        return output_path


class FakeAssembler:
    def run_assembly(self, recipe, video_path, voice_path, music_path, hook_png_path, output_path):
        # Write 20KB to pass QC "nearly empty" check (0.01 MB = 10KB)
        with open(output_path, "wb") as f:
            f.write(b"0" * 20000)
        return output_path


def test_build_recipe_from_item_requires_media():
    db = FakeDB(item={"id": "uuid-1", "custom_id": "ELN-RAW-TEST", "content_type": "reel", "media_keys": []})
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    with pytest.raises(ValueError):
        o.build_recipe_from_item(db.item, hook_text="سلام")


def test_render_content_success_with_hook(monkeypatch):
    db = FakeDB()
    storage = FakeStorage()
    o = EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content("ELN-RAW-TEST", hook_text="تو تنبل نیستی", actor="tester")
    assert result["ok"] is True
    assert result["status"] == "READY_FOR_REVIEW"
    assert storage.downloads
    assert storage.uploads
    statuses = [s[0] for s in db.status_updates]
    assert "EDIT_RENDERING" in statuses
    assert "READY_FOR_REVIEW" in statuses


def test_render_content_not_found():
    db = FakeDB()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content("NOPE", hook_text="سلام")
    assert result["ok"] is False


def test_render_content_handles_assembler_failure():
    class BadAssembler:
        def run_assembly(self, *args, **kwargs):
            raise RuntimeError("render failed")

    db = FakeDB()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=BadAssembler())
    result = o.render_content("ELN-RAW-TEST", hook_text="سلام")
    assert result["ok"] is False
    statuses = [s[0] for s in db.status_updates]
    assert "EDIT_FAILED" in statuses
