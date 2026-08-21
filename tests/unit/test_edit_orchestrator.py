import pytest
from unittest.mock import patch
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


def test_render_content_with_multiple_video_keys(monkeypatch):
    """Test that multiple video_keys result in multiple downloads and concat."""
    import agents.editing.orchestrator as orch_mod

    # Mock VideoConcatenator to avoid needing ffmpeg
    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            # Create output file
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB(item={
        "id": "uuid-multi",
        "custom_id": "ELN-MULTI-TEST",
        "content_type": "reel",
        "media_keys": ["raw/clip1.mp4", "raw/clip2.mp4", "raw/clip3.mp4"],
        "voice_key": "audio/voice.mp3",
        "music_key": "audio/music.mp3",
        "status": "NEEDS_EDIT",
    })
    storage = FakeStorage()
    o = EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content("ELN-MULTI-TEST", actor="tester")
    assert result["ok"] is True
    # Should have downloaded 3 videos + 1 voice + 1 music = 5 downloads
    assert len(storage.downloads) == 5
    video_downloads = [d for d in storage.downloads if "clip_" in d[1] or "base_video" in d[1]]
    assert len(video_downloads) >= 3


def test_render_content_with_video_segments(monkeypatch):
    """Test that item with video_segments downloads each key with correct start/end."""
    import agents.editing.orchestrator as orch_mod

    captured_segments = []

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            captured_segments.extend(segments)
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB(item={
        "id": "uuid-segments",
        "custom_id": "ELN-SEG-TEST",
        "content_type": "reel",
        "video_segments": [
            {"key": "raw/clip1.mp4", "start": 1.2, "end": 5.8},
            {"key": "raw/clip2.mp4", "start": 0.0, "end": 4.0},
            {"key": "raw/clip3.mp4", "start": 2.5},
        ],
        "voice_key": "audio/voice.mp3",
        "status": "NEEDS_EDIT",
    })
    storage = FakeStorage()
    o = EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content("ELN-SEG-TEST", actor="tester")
    assert result["ok"] is True
    # Should have downloaded 3 segments + 1 voice = 4 downloads
    assert len(storage.downloads) == 4
    # Verify segments were captured with correct start/end
    assert len(captured_segments) == 3
    assert captured_segments[0]["start_sec"] == 1.2
    assert captured_segments[0]["end_sec"] == 5.8
    assert captured_segments[1]["start_sec"] == 0.0
    assert captured_segments[1]["end_sec"] == 4.0
    assert captured_segments[2]["start_sec"] == 2.5
    assert captured_segments[2]["end_sec"] is None


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


def test_orchestrator_passes_sfx_items_to_assembler():
    db = FakeDB(item={
        "id": "uuid-sfx",
        "custom_id": "ELN-SFX-TEST",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "status": "NEEDS_EDIT",
        "sound_effects": [
            {
                "key": "sfx/boom.mp3",
                "start": 1.5,
                "volume": -3,
                "fade_in": 0.5,
                "fade_out": 0.2,
                "attribution": "Creative Commons Boom",
            }
        ]
    })
    storage = FakeStorage()
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=assembler)
    result = o.render_content("ELN-SFX-TEST", actor="tester")

    assert result["ok"] is True
    assert len(assembler.calls) == 1
    passed_sfx = assembler.calls[0]["sfx_items"]
    assert passed_sfx is not None
    assert len(passed_sfx) == 1

    # Assert transformed fields
    sfx0 = passed_sfx[0]
    assert "sfx_0.mp3" in sfx0["path"]
    assert sfx0["start_sec"] == 1.5
    assert sfx0["gain_db"] == -3
    assert sfx0["fade_in_sec"] == 0.5
    assert sfx0["fade_out_sec"] == 0.2
    assert sfx0["attribution"] == "Creative Commons Boom"

    # Assert download was called for the SFX
    assert any("sfx/boom.mp3" in d[0] for d in storage.downloads)


def test_render_content_keep_original_audio(monkeypatch):
    """mute_original=False must keep base audio: concat keep_audio=True and
    assembly use_base_audio=True."""
    import agents.editing.orchestrator as orch_mod

    concat_calls = []

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            concat_calls.append(kwargs)
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())
    # Simulate the concat stage producing a base video that carries audio
    monkeypatch.setattr(orch_mod, "get_video_properties", lambda path: {"has_audio": True})

    db = FakeDB()
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)
    result = o.render_content("ELN-RAW-TEST", actor="tester", mute_original=False)

    assert result["ok"] is True
    assert concat_calls == [{"keep_audio": True}]
    assert len(assembler.calls) == 1
    assert assembler.calls[0]["use_base_audio"] is True


def test_render_content_mute_original_default(monkeypatch):
    """Default mute_original=True must keep current behavior: base audio dropped."""
    import agents.editing.orchestrator as orch_mod

    concat_calls = []

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            concat_calls.append(kwargs)
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB()
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)
    result = o.render_content("ELN-RAW-TEST", actor="tester")

    assert result["ok"] is True
    assert concat_calls == [{"keep_audio": False}]
    assert len(assembler.calls) == 1
    assert assembler.calls[0]["use_base_audio"] is False


def test_render_content_resolves_plan_sfx_queries(monkeypatch):
    """plan_sfx queries must be fetched via SFXFetcher and passed to the assembler."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    from agents.audio.base_provider import SoundResult
    fetched_sound = type("Fetched", (), {
        "local_path": "/tmp/fetched_sfx.mp3",
        "metadata": SoundResult(
            provider="freesound", external_id="42", name="key click",
            license="Creative Commons 0", attribution=None,
            duration_sec=1.2, download_url="", preview_url="http://x/preview.mp3",
        ),
    })

    with patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher:
        instance = MockFetcher.return_value
        instance.fetch_best_match.return_value = fetched_sound

        db = FakeDB()
        assembler = FakeAssembler()
        o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)
        result = o.render_content(
            "ELN-RAW-TEST",
            actor="tester",
            plan_sfx=[{"query": "صدای کلید", "start": 1.5, "gain": -6, "fade_in": 0.1, "fade_out": 0.3}],
        )

    assert result["ok"] is True
    instance.fetch_best_match.assert_called_once()
    query_arg = instance.fetch_best_match.call_args[0][0]
    assert query_arg == "صدای کلید"

    assert len(assembler.calls) == 1
    passed_sfx = assembler.calls[0]["sfx_items"]
    assert passed_sfx is not None
    assert len(passed_sfx) == 1
    sfx0 = passed_sfx[0]
    assert sfx0["path"] == "/tmp/fetched_sfx.mp3"
    assert sfx0["start_sec"] == 1.5
    assert sfx0["gain_db"] == -6
    assert sfx0["fade_in_sec"] == 0.1
    assert sfx0["fade_out_sec"] == 0.3


def test_render_content_plan_sfx_provider_not_configured(monkeypatch):
    """Missing SFX provider must fail with typed SFX_PROVIDER_NOT_CONFIGURED."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    with patch("agents.audio.sfx_fetcher.SFXFetcher", side_effect=ValueError("Missing FREESOUND_API_KEY")):
        db = FakeDB()
        o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
        result = o.render_content(
            "ELN-RAW-TEST",
            actor="tester",
            plan_sfx=[{"query": "صدای کلید", "start": 1.5, "gain": -6}],
        )

    assert result["ok"] is False
    assert "SFX_PROVIDER_NOT_CONFIGURED" in result["error"]
    statuses = [s[0] for s in db.status_updates]
    assert "EDIT_FAILED" in statuses


def test_render_content_plan_sfx_fetch_failed(monkeypatch):
    """No match for an SFX query must fail with typed SFX_FETCH_FAILED."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    with patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher:
        instance = MockFetcher.return_value
        instance.fetch_best_match.return_value = None

        db = FakeDB()
        o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
        result = o.render_content(
            "ELN-RAW-TEST",
            actor="tester",
            plan_sfx=[{"query": "صدای غیرموجود", "start": 0.0, "gain": 0}],
        )

    assert result["ok"] is False
    assert "SFX_FETCH_FAILED" in result["error"]


def test_render_content_plan_music_requested_with_asset(monkeypatch):
    """Music requested + item music_key present -> renders with music, no error."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB(item={
        "id": "uuid-music",
        "custom_id": "ELN-MUSIC-TEST",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "music_key": "music/ambient.mp3",
        "status": "NEEDS_EDIT",
    })
    storage = FakeStorage()
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=assembler)
    result = o.render_content(
        "ELN-MUSIC-TEST",
        actor="tester",
        plan_music={"enabled": True, "query": "موسیقی آرام", "gain_db": -14, "explicit": True},
    )

    assert result["ok"] is True
    # Music downloaded and passed to the assembler
    assert any("music/ambient.mp3" in d[0] for d in storage.downloads)
    assert assembler.calls[0]["music_path"] is not None
    assert assembler.calls[0]["music_path"].endswith("music.mp3")


def test_render_content_plan_music_requested_without_asset():
    """Music requested but no asset available -> typed MUSIC_PROVIDER_NOT_CONFIGURED."""
    db = FakeDB()  # no music_key on the item
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content(
        "ELN-RAW-TEST",
        actor="tester",
        plan_music={"enabled": True, "query": "موسیقی آرام", "gain_db": -14, "explicit": True},
    )

    assert result["ok"] is False
    assert "MUSIC_PROVIDER_NOT_CONFIGURED" in result["error"]
    statuses = [s[0] for s in db.status_updates]
    assert "EDIT_FAILED" in statuses


def test_render_content_plan_explicit_no_music_drops_item_music(monkeypatch):
    """Explicit no-music ('بدون موسیقی') must override an item-level music_key."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB(item={
        "id": "uuid-nomusic",
        "custom_id": "ELN-NOMUSIC-TEST",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "music_key": "music/ambient.mp3",
        "status": "NEEDS_EDIT",
    })
    storage = FakeStorage()
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=assembler)
    result = o.render_content(
        "ELN-NOMUSIC-TEST",
        actor="tester",
        plan_music={"enabled": False, "query": None, "gain_db": -14, "explicit": True},
    )

    assert result["ok"] is True
    # Item music must NOT be downloaded or passed to the assembler
    assert not any("music/ambient.mp3" in d[0] for d in storage.downloads)
    assert assembler.calls[0]["music_path"] is None


def test_render_content_plan_music_not_explicit_ignored(monkeypatch):
    """A plan that never mentions music must not affect the render."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content(
        "ELN-RAW-TEST",
        actor="tester",
        plan_music={"enabled": False, "query": None, "gain_db": -14, "explicit": False},
    )
    assert result["ok"] is True


def test_render_preserve_source_media_keys(monkeypatch):
    """Test A, B, C, E: Successful render does not touch raw media_keys,
    updates edited_media_key and appends to edited_media_history."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    # Set up item with existing edited_media_history to test appending (Test E)
    item = {
        "id": "uuid-preserve",
        "custom_id": "ELN-PRESERVE-TEST",
        "content_type": "reel",
        "media_keys": ["raw/shot1.mp4", "raw/shot2.mp4"],
        "edited_media_history": ["edited/ELN-PRESERVE-TEST/old_final.mp4"],
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content("ELN-PRESERVE-TEST", actor="tester")

    assert result["ok"] is True
    output_key = result["output_key"]
    assert output_key.startswith("edited/ELN-PRESERVE-TEST/render-")

    # Find the READY_FOR_REVIEW update
    ready_update = [u for u in db.status_updates if u[0] == "READY_FOR_REVIEW"]
    assert len(ready_update) == 1
    status, extra = ready_update[0]

    # Test A: Successful render update payload does NOT contain media_keys
    assert "media_keys" not in extra

    # Test B: Successful render update payload DOES contain edited_media_key equal to the uploaded output key
    assert extra["edited_media_key"] == output_key

    # Test C: Original content record's media_keys remain unchanged in the fake db
    assert db.item["media_keys"] == ["raw/shot1.mp4", "raw/shot2.mp4"]

    # Test E: edited_media_history contains both old and new output keys
    assert extra["edited_media_history"] == [
        "edited/ELN-PRESERVE-TEST/old_final.mp4",
        output_key
    ]


def test_render_jobs_output_key_intact():
    """Test D: render_jobs output_key remains equal to the uploaded output key."""
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = [{"id": "job-1", "status": "COMPLETED", "output_key": "edited/out.mp4"}]
    mock_query.execute.return_value = mock_result

    from agents.rendering.job_manager import RenderJobManager
    manager = RenderJobManager(db=mock_db)
    job = manager.mark_completed("job-1", "edited/out.mp4")

    assert job["status"] == "COMPLETED"
    assert job["output_key"] == "edited/out.mp4"


def test_render_content_versioned_key_with_job_id(monkeypatch):
    """Test A — Versioned key with job_id:
    render_content called with job_id="abc123" -> output key is edited/{custom_id}/{job_id}.mp4"""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content("ELN-RAW-TEST", actor="tester", job_id="abc123")

    assert result["ok"] is True
    assert result["output_key"] == "edited/ELN-RAW-TEST/abc123.mp4"


def test_render_content_fallback_without_job_id(monkeypatch):
    """Test B — Fallback without job_id:
    render_content called without job_id -> output key matches pattern edited/{custom_id}/render-<timestamp>.mp4"""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    result = o.render_content("ELN-RAW-TEST", actor="tester")

    assert result["ok"] is True
    output_key = result["output_key"]
    assert output_key.startswith("edited/ELN-RAW-TEST/render-")
    assert output_key.endswith(".mp4")


def test_render_content_consecutive_produces_different_keys(monkeypatch):
    """Test C — Two renders produce different keys:
    Two consecutive render_content calls for the same custom_id -> two DIFFERENT output keys"""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    
    result1 = o.render_content("ELN-RAW-TEST", actor="tester")
    import time
    # sleep briefly to ensure timestamp is different if using millisecond timestamps
    time.sleep(0.01)
    result2 = o.render_content("ELN-RAW-TEST", actor="tester")

    assert result1["ok"] is True
    assert result2["ok"] is True
    assert result1["output_key"] != result2["output_key"]


def test_render_content_history_accumulates_versioned_keys(monkeypatch):
    """Test D — History accumulates:
    After multiple renders, edited_media_key points to the newest versioned key,
    and edited_media_history accumulates all generated output keys without overwriting them."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-history",
        "custom_id": "ELN-HISTORY-TEST",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "edited_media_history": [],
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())
    
    # Render 1
    res1 = o.render_content("ELN-HISTORY-TEST", actor="tester", job_id="job1")
    assert res1["ok"] is True
    key1 = res1["output_key"]
    assert key1 == "edited/ELN-HISTORY-TEST/job1.mp4"

    # Simulate database state update before Render 2
    db.item["edited_media_history"] = [key1]
    db.item["edited_media_key"] = key1

    # Render 2
    res2 = o.render_content("ELN-HISTORY-TEST", actor="tester", job_id="job2")
    assert res2["ok"] is True
    key2 = res2["output_key"]
    assert key2 == "edited/ELN-HISTORY-TEST/job2.mp4"

    # Find READY_FOR_REVIEW updates
    updates = [u for u in db.status_updates if u[0] == "READY_FOR_REVIEW"]
    assert len(updates) == 2
    
    extra1 = updates[0][1]
    assert extra1["edited_media_key"] == key1
    assert extra1["edited_media_history"] == [key1]

    extra2 = updates[1][1]
    assert extra2["edited_media_key"] == key2
    assert extra2["edited_media_history"] == [key1, key2]


def test_render_content_music_gain_db_propagation(monkeypatch):
    """Test E — render_worker/orchestrator propagation:
    Given plan_music.gain_db, assert it reaches media_assembly in the expected
    music object/config."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-gain",
        "custom_id": "ELN-RAW-TEST",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "music_key": "music/ambient.mp3",
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)
    result = o.render_content(
        "ELN-RAW-TEST",
        actor="tester",
        plan_music={"enabled": True, "query": "موسیقی آرام", "gain_db": -18, "explicit": True},
    )

    assert result["ok"] is True
    assert len(assembler.calls) == 1
    # Check that recipe's music_gain_db is set to -18!
    recipe = assembler.calls[0]["recipe"]
    assert recipe.audio.music_gain_db == -18
