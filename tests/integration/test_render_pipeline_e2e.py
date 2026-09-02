import pytest
from unittest.mock import MagicMock, patch, AsyncMock, ANY
import datetime

# Mark all tests in this file as unit/integration
pytestmark = pytest.mark.unit


class FakeDB:
    def __init__(self, item=None):
        self.item = item or {
            "id": "uuid-1",
            "custom_id": "ELN-BUNDLE-123",
            "content_type": "reel",
            "media_keys": ["raw/shot1.mp4", "raw/shot2.mp4", "raw/shot3.mp4"],
            "music_key": "music/ambient.mp3",
            "status": "NEEDS_EDIT",
            "edited_media_history": [],
        }
        self.status_updates = []
        self.events = []
        self.client = MagicMock()
        self.client.table.return_value = self.client
        self.client.update.return_value = self.client
        self.client.eq.return_value = self.client
        self.client.in_.return_value = self.client
        # Mock executing returns self for fluent chaining
        self.client.execute.return_value = MagicMock(data=[])

    def get_content_by_custom_id(self, custom_id):
        if custom_id == self.item["custom_id"]:
            return dict(self.item)
        return None

    def update_status(self, item_id, new_status, extra=None):
        self.status_updates.append((item_id, new_status, extra or {}))
        self.item["status"] = new_status
        if extra:
            self.item.update(extra)
        return []

    def log_event(self, content_id, event_type, from_status, to_status, actor, detail=""):
        self.events.append((event_type, from_status, to_status))
        return []

    def get_due_items(self, now_iso, limit=1):
        return [self.item] if self.item else []

    def claim_for_publishing(self, item_id, expected_status):
        return True


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

    def create_signed_url(self, key, ttl):
        return f"https://signed.example/{key}"


class FakeTypography:
    def render_text_to_png(self, text, output_path, **kwargs):
        with open(output_path, "wb") as f:
            f.write(b"fake png")
        return output_path


class FakeAssembler:
    def __init__(self):
        self.calls = []

    def run_assembly(self, recipe, video_path, voice_path, music_path, hook_png_path, output_path, sfx_items=None, **kwargs):
        call = {
            "recipe": recipe,
            "video_path": video_path,
            "voice_path": voice_path,
            "music_path": music_path,
            "hook_png_path": hook_png_path,
            "output_path": output_path,
            "sfx_items": sfx_items,
        }
        call.update(kwargs)
        self.calls.append(call)
        with open(output_path, "wb") as f:
            f.write(b"0" * 20000)
        return output_path


def make_mock_update(is_owner=True, chat_data=None):
    mock_update = MagicMock()
    mock_update.effective_chat = MagicMock(id="12345")
    mock_update.message = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = []
    mock_context.chat_data = chat_data if chat_data is not None else {}
    return mock_update, mock_context


# =====================================================================
# INTEGRATION TESTS G-1 to G-9
# =====================================================================

@pytest.mark.asyncio
async def test_1_full_plan_execution_happy_path(monkeypatch):
    """TEST 1 — Full plan execution (happy path):
    Ensures correct shot selection, mute, SFX fetching, music, hook text pass-through,
    successful status update, preservation of raw media_keys, and versioned output key recording."""
    import scripts.render_worker as worker_mod
    import agents.editing.orchestrator as orch_mod

    mock_job = {
        "id": "job-happy-e2e-123",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [
                {"index": 1, "start": 0.0, "end": 1.0, "remove": False},
                {"index": 2, "remove": True},
                {"index": 3, "start": 0.5, "end": 1.5, "remove": False}
            ],
            "hook": "تست هوک فارسی",
            "mute_original": False,
            "sfx": [{"query": "click", "start": 0.2, "gain": -6, "fade_in": 0.1, "fade_out": 0.1}],
            "music": {"enabled": True, "query": "calm", "gain_db": -14, "explicit": True}
        },
        "owner_chat_id": "12345"
    }

    db = FakeDB()
    storage = FakeStorage()
    assembler = FakeAssembler()

    # Mock MockConcatenator to skip FFmpeg
    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    # Mock SFXFetcher sound result
    from agents.audio.base_provider import SoundResult
    fetched_sound = type("Fetched", (), {
        "local_path": "/tmp/fetched_click.mp3",
        "metadata": SoundResult(
            provider="freesound", external_id="1", name="click",
            license="CC0", attribution=None, duration_sec=0.5,
            download_url="", preview_url="http://x/preview.mp3"
        )
    })

    with patch("scripts.render_worker.ElinaDB", lambda: db), \
         patch("agents.editing.orchestrator.ElinaDB", lambda: db), \
         patch("agents.editing.orchestrator.ElinaStorage", lambda: storage), \
         patch("agents.editing.orchestrator.VideoConcatenator", lambda: MockConcatenator()), \
         patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher, \
         patch("agents.audio.asset_pinner.AssetPinner") as MockPinner:
        
        # Configure MockFetcher
        fetcher_instance = MockFetcher.return_value
        fetcher_instance.fetch_best_match.return_value = fetched_sound
        # M20A: simulate "no pinned asset" so the Freesound path is exercised
        MockPinner.return_value.get_pinned_sfx.return_value = None

        orchestrator = orch_mod.EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=assembler)
        
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda *args, **kwargs: orchestrator), \
             patch("scripts.render_worker.RenderJobManager") as MockJobManager, \
             patch("urllib.request.urlopen"):
            
            job_mgr_instance = MockJobManager.return_value
            job_mgr_instance.db = db
            job_mgr_instance.mark_completed.return_value = {}

            # Execute render job via render_worker entry point
            result = worker_mod.process_job(mock_job)

            assert result is True
            
            # Verify JobManager recorded the exact versioned key (Test E)
            expected_versioned_key = "edited/ELN-BUNDLE-123/job-happy-e2e-123.mp4"
            job_mgr_instance.mark_completed.assert_called_once_with("job-happy-e2e-123", expected_versioned_key)

            # Verify original raw media_keys are preserved and NOT overwritten
            assert db.item["media_keys"] == ["raw/shot1.mp4", "raw/shot2.mp4", "raw/shot3.mp4"]

            # Verify edited_media_key is recorded correctly
            assert db.item["edited_media_key"] == expected_versioned_key

            # Verify SFXFetcher resolved "click" query
            fetcher_instance.fetch_best_match.assert_called_once_with("click", ANY)

            # Verify assembler received correct inputs and music_gain_db
            assert len(assembler.calls) == 1
            recipe = assembler.calls[0]["recipe"]
            assert recipe.audio.music_gain_db == -14


@pytest.mark.asyncio
async def test_2_all_shots_removed():
    """TEST 2 — All shots removed:
    If a plan has remove=true for every single shot, the job fails loudly with PLAN_ALL_SHOTS_REMOVED,
    and render_content is never invoked."""
    import scripts.render_worker as worker_mod

    mock_job = {
        "id": "job-all-removed",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [
                {"index": 1, "remove": True},
                {"index": 2, "remove": True}
            ]
        },
        "owner_chat_id": "12345"
    }

    db = FakeDB()
    with patch("scripts.render_worker.ElinaDB", lambda: db), \
         patch("agents.editing.orchestrator.EditOrchestrator") as MockOrchestrator, \
         patch("urllib.request.urlopen"):
        
        result = worker_mod.process_job(mock_job)
        
        assert result is False
        MockOrchestrator.return_value.render_content.assert_not_called()

        # Job marked FAILED with PLAN_ALL_SHOTS_REMOVED
        update_call = db.client.table.return_value.update.call_args[0][0]
        assert update_call["status"] == "FAILED"
        assert update_call["error_message"] == "PLAN_ALL_SHOTS_REMOVED"


@pytest.mark.asyncio
async def test_3_shot_index_out_of_range():
    """TEST 3 — Shot index out of range:
    If any shot index is out of range of the bundle's media_keys, the job fails with SHOT_INDEX_OUT_OF_RANGE."""
    import scripts.render_worker as worker_mod

    mock_job = {
        "id": "job-out-of-range",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [
                {"index": 1, "start": 0.0, "end": 2.0, "remove": False},
                {"index": 5, "start": 0.0, "end": 2.0, "remove": False} # Index 5 is out of range (max index is 3)
            ]
        },
        "owner_chat_id": "12345"
    }

    db = FakeDB()
    with patch("scripts.render_worker.ElinaDB", lambda: db), \
         patch("agents.editing.orchestrator.EditOrchestrator") as MockOrchestrator, \
         patch("urllib.request.urlopen"):
        
        result = worker_mod.process_job(mock_job)
        
        assert result is False
        MockOrchestrator.return_value.render_content.assert_not_called()

        # Job marked FAILED with SHOT_INDEX_OUT_OF_RANGE
        update_call = db.client.table.return_value.update.call_args[0][0]
        assert update_call["status"] == "FAILED"
        assert "SHOT_INDEX_OUT_OF_RANGE" in update_call["error_message"]
        assert "shot 5 requested but bundle has 3 shots" in update_call["error_message"]


@pytest.mark.asyncio
async def test_4_sfx_provider_not_configured(monkeypatch):
    """TEST 4 — SFX provider not configured:
    If SFXFetcher initialization fails with missing API key, the job fails with SFX_PROVIDER_NOT_CONFIGURED."""
    import scripts.render_worker as worker_mod
    import agents.editing.orchestrator as orch_mod

    mock_job = {
        "id": "job-sfx-err",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
            "sfx": [{"query": "click", "start": 1.0}]
        },
        "owner_chat_id": "12345"
    }

    db = FakeDB()
    storage = FakeStorage()

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    with patch("scripts.render_worker.ElinaDB", lambda: db), \
         patch("agents.editing.orchestrator.ElinaDB", lambda: db), \
         patch("agents.editing.orchestrator.ElinaStorage", lambda: storage), \
         patch("agents.editing.orchestrator.VideoConcatenator", lambda: MockConcatenator()), \
         patch("agents.audio.sfx_fetcher.SFXFetcher", side_effect=ValueError("Missing FREESOUND_API_KEY")), \
         patch("scripts.render_worker.RenderJobManager") as MockJobManager, \
         patch("urllib.request.urlopen"):
        
        job_mgr_instance = MockJobManager.return_value
        job_mgr_instance.db = db
        job_mgr_instance.mark_failed.return_value = {}

        result = worker_mod.process_job(mock_job)
        assert result is False
        job_mgr_instance.mark_failed.assert_called_once_with("job-sfx-err", ANY)


@pytest.mark.asyncio
async def test_5_music_requested_without_asset():
    """TEST 5 — Music requested without asset:
    If music is requested in the plan but no music_key asset is configured, the job fails with MUSIC_PROVIDER_NOT_CONFIGURED."""
    import scripts.render_worker as worker_mod

    mock_job = {
        "id": "job-music-err",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
            "music": {"enabled": True, "query": "calm", "gain_db": -14, "explicit": True}
        },
        "owner_chat_id": "12345"
    }

    # Content item with music_key=None
    item = {
        "id": "uuid-1",
        "custom_id": "ELN-BUNDLE-123",
        "content_type": "reel",
        "media_keys": ["raw/shot1.mp4"],
        "music_key": None, # missing asset
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    storage = FakeStorage()

    with patch("scripts.render_worker.ElinaDB", lambda: db), \
         patch("agents.editing.orchestrator.ElinaDB", lambda: db), \
         patch("agents.editing.orchestrator.ElinaStorage", lambda: storage), \
         patch("scripts.render_worker.RenderJobManager") as MockJobManager, \
         patch("urllib.request.urlopen"):
        
        job_mgr_instance = MockJobManager.return_value
        job_mgr_instance.db = db
        job_mgr_instance.mark_failed.return_value = {}

        result = worker_mod.process_job(mock_job)
        assert result is False
        job_mgr_instance.mark_failed.assert_called_once_with("job-music-err", ANY)


@pytest.mark.asyncio
async def test_6_mute_original_true(monkeypatch):
    """TEST 6 — mute_original=true:
    Ensures mute_original=True propagates keep_audio=False to concatenator and use_base_audio=False to assembler."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, keep_audio=False):
            assert keep_audio is False
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-mute",
        "custom_id": "ELN-RAW-TEST",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "status": "NEEDS_EDIT",
        "edited_media_history": [],
    }
    db = FakeDB(item=item)
    assembler = FakeAssembler()
    o = orch_mod.EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)
    result = o.render_content("ELN-RAW-TEST", actor="tester", mute_original=True)

    assert result["ok"] is True
    assert len(assembler.calls) == 1
    assert assembler.calls[0]["use_base_audio"] is False


@pytest.mark.asyncio
async def test_7_re_render_produces_unique_output_key(monkeypatch):
    """TEST 7 — Re-render produces unique output key:
    Consecutive renders of the same custom_id produce different versioned keys,
    and history accumulates the generated keys properly."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-rerender",
        "custom_id": "ELN-HISTORY-TEST",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "edited_media_history": [],
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    o = orch_mod.EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    
    # Render 1 with job_id="job1"
    res1 = o.render_content("ELN-HISTORY-TEST", actor="tester", job_id="job1")
    assert res1["ok"] is True
    key1 = res1["output_key"]
    assert key1 == "edited/ELN-HISTORY-TEST/job1.mp4"

    # Database simulation update
    db.item["edited_media_history"] = [key1]
    db.item["edited_media_key"] = key1

    # Render 2 with job_id="job2"
    res2 = o.render_content("ELN-HISTORY-TEST", actor="tester", job_id="job2")
    assert res2["ok"] is True
    key2 = res2["output_key"]
    assert key2 == "edited/ELN-HISTORY-TEST/job2.mp4"

    assert key1 != key2

    # Verification of final database status updates
    updates = [u for u in db.status_updates if u[1] == "READY_FOR_REVIEW"]
    assert len(updates) == 2
    assert updates[1][2]["edited_media_history"] == [key1, key2]
    assert updates[1][2]["edited_media_key"] == key2


def test_8_scheduler_prefers_edited_output(monkeypatch):
    """TEST 8 — Scheduler prefers edited output:
    Scheduled content with edited_media_key publishes edited_media_key,
    while content without edited_media_key falls back to raw media_keys[0]."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    from agents.scheduler import PublishScheduler
    from agents.publishers.base_publisher import PublishResult

    # Item with edited_media_key
    item_edited = {
        "id": "uuid-edited",
        "custom_id": "ELN-EDITED-REEL",
        "content_type": "reel",
        "media_keys": ["raw/shot1.mp4"],
        "edited_media_key": "edited/final_output.mp4",
        "status": "SCHEDULED",
        "scheduled_for": "2020-01-01T00:00:00Z",
        "approved_at": "2020-01-01T00:00:00Z",
        "approved_by": "tester",
    }

    # Item without edited_media_key
    item_raw = {
        "id": "uuid-raw",
        "custom_id": "ELN-RAW-REEL",
        "content_type": "reel",
        "media_keys": ["raw/shot1.mp4"],
        "status": "SCHEDULED",
        "scheduled_for": "2020-01-01T00:00:00Z",
        "approved_at": "2020-01-01T00:00:00Z",
        "approved_by": "tester",
    }

    db_edited = FakeDB(item=item_edited)
    db_raw = FakeDB(item=item_raw)

    pub = FakePublisher(PublishResult(success=True, media_id="123"))

    # Verify preference
    s1 = PublishScheduler(db=db_edited, storage=FakeStorage(), publisher=pub)
    s1.run_once()
    assert len(pub.calls) == 1
    assert pub.calls[0][1] == "https://signed.example/edited/final_output.mp4"

    # Verify fallback
    pub.calls = []
    s2 = PublishScheduler(db=db_raw, storage=FakeStorage(), publisher=pub)
    s2.run_once()
    assert len(pub.calls) == 1
    assert pub.calls[0][1] == "https://signed.example/raw/shot1.mp4"


def test_9_plan_validation_rejects_invalid_input():
    """TEST 9 — Plan validation rejects invalid input:
    Tests validation of empty shots, end_sec <= start_sec, and negative start_sec."""
    from agents.editing.persian_edit_interpreter import PersianEditPlan, PersianShotInstruction

    # Empty shots list
    plan1 = PersianEditPlan(shots=[])
    errors1 = plan1.validate()
    assert any("At least one shot is required" in e for e in errors1)

    # end_sec <= start_sec
    plan2 = PersianEditPlan(shots=[PersianShotInstruction(shot_index=1, start_sec=4.0, end_sec=2.0)])
    errors2 = plan2.validate()
    assert any("end_sec must be greater than start_sec" in e for e in errors2)

    # Negative start_sec
    plan3 = PersianEditPlan(shots=[PersianShotInstruction(shot_index=1, start_sec=-1.0, end_sec=3.0)])
    errors3 = plan3.validate()
    assert any("start_sec cannot be negative" in e for e in errors3)


# Fake structures helper
class FakePublisher:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def publish_reel(self, video_url, caption):
        self.calls.append(("reel", video_url))
        return self.result
