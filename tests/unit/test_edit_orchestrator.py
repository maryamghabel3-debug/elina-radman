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


# === New Shot-Anchored SFX Timing Tests ===

def test_anchor_shot_1_end_resolves_correctly(monkeypatch):
    """anchor shot_1.end with offset -0.4 resolves correctly for known trims."""
    import agents.editing.orchestrator as orch_mod

    # Mock get_video_properties
    def fake_props(path, **kwargs):
        return {"duration": 10.0}
    monkeypatch.setattr(orch_mod, "get_video_properties", fake_props)

    # Mock VideoConcatenator to avoid needing ffmpeg
    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path
    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-anchor-1",
        "custom_id": "ELN-ANCHOR-1",
        "content_type": "reel",
        "media_keys": ["raw/v1.mp4", "raw/v2.mp4"],
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)

    # Segment 1 trimmed from 1.0 to 6.0 (dur = 5.0)
    # Segment 2 trimmed from 0.0 to 5.0 (dur = 5.0)
    video_segments = [
        {"key": "raw/v1.mp4", "start_sec": 1.0, "end_sec": 6.0},
        {"key": "raw/v2.mp4", "start_sec": 0.0, "end_sec": 5.0}
    ]
    plan_sfx = [
        {
            "query": "click",
            "anchor": "shot_1.end",
            "offset_sec": -0.4,
            "gain_db": -6
        }
    ]

    # Mock fetcher
    from agents.audio.base_provider import SoundResult
    fetched_sound = type("Fetched", (), {
        "local_path": "/tmp/fetched_click.mp3",
        "metadata": SoundResult(
            provider="freesound", external_id="1", name="click",
            license="CC0", attribution=None, duration_sec=0.5,
            download_url="", preview_url=""
        )
    })
    
    with patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher:
        fetcher_instance = MockFetcher.return_value
        fetcher_instance.fetch_best_match.return_value = fetched_sound

        result = o.render_content(
            "ELN-ANCHOR-1",
            video_segments=video_segments,
            plan_sfx=plan_sfx,
        )

        assert result["ok"] is True
        assert len(assembler.calls) == 1
        sfx_items = assembler.calls[0]["sfx_items"]
        assert len(sfx_items) == 1
        # Expected: base_time = 5.0, offset = -0.4 -> resolved = 4.6
        assert abs(sfx_items[0]["start_sec"] - 4.6) < 1e-5


def test_anchor_resolution_accounts_for_dissolve_and_freeze(monkeypatch):
    """resolution accounts for a dissolve overlap and a freeze tail."""
    import agents.editing.orchestrator as orch_mod

    def fake_props(path, **kwargs):
        return {"duration": 10.0}
    monkeypatch.setattr(orch_mod, "get_video_properties", fake_props)

    # Mock VideoConcatenator to avoid needing ffmpeg
    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path
    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-anchor-2",
        "custom_id": "ELN-ANCHOR-2",
        "content_type": "reel",
        "media_keys": ["raw/v1.mp4", "raw/v2.mp4"],
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)

    # Segment 1: dur=5.0, freeze=0.2, transition_out=dissolve (0.5s) -> active_dur = 5.2, ends at 5.2
    # Segment 2: dur=5.0, starts at 5.2 - 0.5 = 4.7, ends at 4.7 + 5.0 = 9.7
    video_segments = [
        {
            "key": "raw/v1.mp4",
            "start_sec": 0.0,
            "end_sec": 5.0,
            "freeze_tail_sec": 0.2,
            "transition_out": {"type": "dissolve", "duration_sec": 0.5}
        },
        {"key": "raw/v2.mp4", "start_sec": 0.0, "end_sec": 5.0}
    ]
    plan_sfx = [
        {"query": "sfx1", "anchor": "shot_2.start", "offset_sec": 0.1},
        {"query": "sfx2", "anchor": "shot_2.end", "offset_sec": -0.2}
    ]

    from agents.audio.base_provider import SoundResult
    fetched_sound = type("Fetched", (), {
        "local_path": "/tmp/fetched.mp3",
        "metadata": SoundResult(
            provider="freesound", external_id="1", name="sfx",
            license="CC0", attribution=None, duration_sec=0.5,
            download_url="", preview_url=""
        )
    })
    
    with patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher:
        fetcher_instance = MockFetcher.return_value
        fetcher_instance.fetch_best_match.return_value = fetched_sound

        result = o.render_content(
            "ELN-ANCHOR-2",
            video_segments=video_segments,
            plan_sfx=plan_sfx,
        )

        assert result["ok"] is True
        sfx_items = assembler.calls[0]["sfx_items"]
        assert len(sfx_items) == 2
        # SFX 1: starts at shot_2.start (4.7) + 0.1 = 4.8
        assert abs(sfx_items[0]["start_sec"] - 4.8) < 1e-5
        # SFX 2: starts at shot_2.end (9.7) - 0.2 = 9.5
        assert abs(sfx_items[1]["start_sec"] - 9.5) < 1e-5


def test_absolute_start_sec_unaffected(monkeypatch):
    """absolute start_sec items unaffected by anchor resolution step (regression)."""
    import agents.editing.orchestrator as orch_mod

    def fake_props(path, **kwargs):
        return {"duration": 10.0}
    monkeypatch.setattr(orch_mod, "get_video_properties", fake_props)

    # Mock VideoConcatenator to avoid needing ffmpeg
    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path
    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-anchor-3",
        "custom_id": "ELN-ANCHOR-3",
        "content_type": "reel",
        "media_keys": ["raw/v1.mp4"],
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)

    plan_sfx = [
        {"query": "click", "start_sec": 3.7}
    ]

    from agents.audio.base_provider import SoundResult
    fetched_sound = type("Fetched", (), {
        "local_path": "/tmp/fetched.mp3",
        "metadata": SoundResult(
            provider="freesound", external_id="1", name="sfx",
            license="CC0", attribution=None, duration_sec=0.5,
            download_url="", preview_url=""
        )
    })
    
    with patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher:
        fetcher_instance = MockFetcher.return_value
        fetcher_instance.fetch_best_match.return_value = fetched_sound

        result = o.render_content(
            "ELN-ANCHOR-3",
            plan_sfx=plan_sfx,
        )

        assert result["ok"] is True
        sfx_items = assembler.calls[0]["sfx_items"]
        assert len(sfx_items) == 1
        assert sfx_items[0]["start_sec"] == 3.7


def test_out_of_range_anchor_raises_terminal_error(monkeypatch):
    """out-of-range anchor index or time exceeds total duration raises SFX_ANCHOR_OUT_OF_RANGE."""
    import agents.editing.orchestrator as orch_mod

    def fake_props(path, **kwargs):
        return {"duration": 10.0}
    monkeypatch.setattr(orch_mod, "get_video_properties", fake_props)

    # Mock VideoConcatenator to avoid needing ffmpeg
    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path
    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-anchor-4",
        "custom_id": "ELN-ANCHOR-4",
        "content_type": "reel",
        "media_keys": ["raw/v1.mp4"],
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)

    # 1. Shot index out of range
    plan_sfx_bad_idx = [{"query": "click", "anchor": "shot_2.start", "offset_sec": 0.0}]
    
    # 2. Resolved time exceeds total duration (which is 10.0)
    plan_sfx_bad_time = [{"query": "click", "anchor": "shot_1.end", "offset_sec": 1.5}]

    from agents.audio.base_provider import SoundResult
    fetched_sound = type("Fetched", (), {
        "local_path": "/tmp/fetched.mp3",
        "metadata": SoundResult(
            provider="freesound", external_id="1", name="sfx",
            license="CC0", attribution=None, duration_sec=0.5,
            download_url="", preview_url=""
        )
    })
    
    with patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher:
        fetcher_instance = MockFetcher.return_value
        fetcher_instance.fetch_best_match.return_value = fetched_sound

        result_idx = o.render_content("ELN-ANCHOR-4", plan_sfx=plan_sfx_bad_idx)
        assert result_idx["ok"] is False
        assert "SFX_ANCHOR_OUT_OF_RANGE" in result_idx["error"]

        result_time = o.render_content("ELN-ANCHOR-4", plan_sfx=plan_sfx_bad_time)
        assert result_time["ok"] is False
        assert "SFX_ANCHOR_OUT_OF_RANGE" in result_time["error"]


def test_mixed_absolute_and_anchored_items(monkeypatch):
    """mixed absolute + anchored items in one plan are all resolved correctly."""
    import agents.editing.orchestrator as orch_mod

    def fake_props(path, **kwargs):
        return {"duration": 10.0}
    monkeypatch.setattr(orch_mod, "get_video_properties", fake_props)

    # Mock VideoConcatenator to avoid needing ffmpeg
    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path
    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    item = {
        "id": "uuid-anchor-5",
        "custom_id": "ELN-ANCHOR-5",
        "content_type": "reel",
        "media_keys": ["raw/v1.mp4", "raw/v2.mp4"],
        "status": "NEEDS_EDIT",
    }
    db = FakeDB(item=item)
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=assembler)

    video_segments = [
        {"key": "raw/v1.mp4", "start_sec": 0.0, "end_sec": 5.0},
        {"key": "raw/v2.mp4", "start_sec": 0.0, "end_sec": 5.0}
    ]
    plan_sfx = [
        {"query": "click1", "start_sec": 1.5},
        {"query": "click2", "anchor": "shot_2.start", "offset_sec": -0.5}
    ]

    from agents.audio.base_provider import SoundResult
    fetched_sound = type("Fetched", (), {
        "local_path": "/tmp/fetched.mp3",
        "metadata": SoundResult(
            provider="freesound", external_id="1", name="sfx",
            license="CC0", attribution=None, duration_sec=0.5,
            download_url="", preview_url=""
        )
    })
    
    with patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher:
        fetcher_instance = MockFetcher.return_value
        fetcher_instance.fetch_best_match.return_value = fetched_sound

        result = o.render_content(
            "ELN-ANCHOR-5",
            video_segments=video_segments,
            plan_sfx=plan_sfx,
        )

        assert result["ok"] is True
        sfx_items = assembler.calls[0]["sfx_items"]
        assert len(sfx_items) == 2
        # SFX 1 (absolute): 1.5
        assert sfx_items[0]["start_sec"] == 1.5
        # SFX 2 (anchored): base_time (5.0) - 0.5 = 4.5
        assert abs(sfx_items[1]["start_sec"] - 4.5) < 1e-5


# === New Plan Voice (M15 Persian TTS) Tests ===

class FakeVoiceGenerator:
    """Stands in for VoiceGenerator: records calls and writes a fake mp3."""
    instances = []

    def __init__(self, *args, **kwargs):
        self.calls = []
        FakeVoiceGenerator.instances.append(self)

    async def generate(self, text, voice="dilara", rate="+0%", output_path=None):
        self.calls.append({"text": text, "voice": voice, "rate": rate, "output_path": output_path})
        with open(output_path, "wb") as f:
            f.write(b"FAKE-TTS-AUDIO")
        return output_path


def test_render_content_plan_voice_generates_and_wires_assembly(monkeypatch):
    """Test G: plan_data with voice field -> orchestrator calls VoiceGenerator,
    uploads the file to voice/{custom_id}/{job_id}.mp3, and passes the local
    voice path + gain/start into the assembly step."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    FakeVoiceGenerator.instances = []
    db = FakeDB(item={
        "id": "uuid-voice-g",
        "custom_id": "ELN-VOICE-G",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "status": "NEEDS_EDIT",
    })
    storage = FakeStorage()
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=assembler)

    with patch("agents.audio.voice_generator.VoiceGenerator", FakeVoiceGenerator):
        result = o.render_content(
            "ELN-VOICE-G",
            actor="tester",
            job_id="jobvoice1",
            plan_voice={
                "text": "سلام، این ویدیو درباره‌ی تو است.",
                "voice": "farid",
                "rate": "-10%",
                "gain_db": -3,
                "start_sec": 1.5,
            },
        )

    assert result["ok"] is True
    # VoiceGenerator called once with the plan values
    assert len(FakeVoiceGenerator.instances) == 1
    gen_call = FakeVoiceGenerator.instances[0].calls[0]
    assert gen_call["text"] == "سلام، این ویدیو درباره‌ی تو است."
    assert gen_call["voice"] == "farid"
    assert gen_call["rate"] == "-10%"
    # Generated file uploaded to voice/{custom_id}/{job_id}.mp3
    voice_uploads = [u for u in storage.uploads if u[1].startswith("voice/ELN-VOICE-G/")]
    assert len(voice_uploads) == 1
    assert voice_uploads[0][1] == "voice/ELN-VOICE-G/jobvoice1.mp3"
    assert voice_uploads[0][2] == "audio/mpeg"
    # Local voice path passed to the assembly
    call = assembler.calls[0]
    assert call["voice_path"] is not None
    assert call["voice_path"].endswith("voice_tts.mp3")
    # gain/start carried into the recipe audio config; voice_key recorded
    recipe = call["recipe"]
    assert recipe.audio.voice_gain_db == -3
    assert recipe.audio.voice_start_sec == 1.5
    assert recipe.input_media.voice_key == "voice/ELN-VOICE-G/jobvoice1.mp3"


def test_render_content_without_plan_voice_unchanged(monkeypatch):
    """Test H: plan_data without voice field -> zero behavior change:
    VoiceGenerator never called, item voice asset downloaded and used."""
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    db = FakeDB(item={
        "id": "uuid-voice-h",
        "custom_id": "ELN-VOICE-H",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "voice_key": "audio/voice.mp3",
        "status": "NEEDS_EDIT",
    })
    storage = FakeStorage()
    assembler = FakeAssembler()
    o = EditOrchestrator(db=db, storage=storage, typography=FakeTypography(), assembler=assembler)

    with patch("agents.audio.voice_generator.VoiceGenerator") as MockGen:
        result = o.render_content("ELN-VOICE-H", actor="tester")

    assert result["ok"] is True
    MockGen.assert_not_called()
    # Old behavior: item voice asset downloaded and passed to the assembly
    assert any("audio/voice.mp3" in d[0] for d in storage.downloads)
    assert assembler.calls[0]["voice_path"].endswith("voice.mp3")
    # No voice storage upload
    assert not any(u[1].startswith("voice/") for u in storage.uploads)
    # Recipe audio config untouched
    assert assembler.calls[0]["recipe"].audio.voice_gain_db is None
    assert assembler.calls[0]["recipe"].audio.voice_start_sec is None


def test_render_content_plan_voice_generation_failure_is_typed(monkeypatch):
    """Voice generation failure after retries fails the job with the typed error."""
    import agents.editing.orchestrator as orch_mod
    from agents.audio.voice_generator import VoiceGenerationError

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())

    class FailingVoiceGenerator:
        async def generate(self, text, voice="dilara", rate="+0%", output_path=None):
            raise VoiceGenerationError("VOICE_TEXT_TOO_LONG", "text is 5000 characters; maximum is 2000")

    db = FakeDB()
    o = EditOrchestrator(db=db, storage=FakeStorage(), typography=FakeTypography(), assembler=FakeAssembler())

    with patch("agents.audio.voice_generator.VoiceGenerator", FailingVoiceGenerator):
        result = o.render_content(
            "ELN-RAW-TEST",
            actor="tester",
            plan_voice={"text": "خ" * 5000},
        )

    assert result["ok"] is False
    assert "VOICE_TEXT_TOO_LONG" in result["error"]
    statuses = [s[0] for s in db.status_updates]
    assert "EDIT_FAILED" in statuses
