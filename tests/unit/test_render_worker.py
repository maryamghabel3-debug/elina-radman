import pytest
from unittest.mock import MagicMock, patch, ANY
from scripts.render_worker import process_job

pytestmark = pytest.mark.unit


def test_process_job_success():
    mock_job = {
        "id": "job-1",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [
                {"index": 1, "start": 0.0, "end": 2.5},
                {"index": 2, "start": 1.2, "end": 4.0}
            ],
            "hook": "متن هوک"
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4", "path/2.mp4", "path/3.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen") as mock_urlopen:
                    process_job(mock_job)

                    # Assert get_content_by_custom_id was called
                    mock_db.get_content_by_custom_id.assert_called_once_with("ELN-BUNDLE-123")

                    # Assert render_content was called with translated video_segments!
                    assert len(mock_orchestrator_calls) == 1
                    call = mock_orchestrator_calls[0]
                    assert call["custom_id"] == "ELN-BUNDLE-123"
                    assert call["hook_text"] == "متن هوک"
                    assert call["video_segments"] == [
                        {"key": "path/1.mp4", "start_sec": 0.0, "end_sec": 2.5},
                        {"key": "path/2.mp4", "start_sec": 1.2, "end_sec": 4.0}
                    ]

                    # Assert job manager marked completed and telegram notified
                    instance.mark_completed.assert_called_once_with("job-1", "edited/final.mp4")
                    mock_urlopen.assert_called_once()


def test_process_job_skips_removed_shots():
    """Shots marked remove=True in plan_data must be excluded from video_segments."""
    mock_job = {
        "id": "job-2",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [
                {"index": 1, "start": 0.0, "end": 2.5, "remove": False},
                {"index": 2, "start": 0.0, "end": None, "remove": True},
                {"index": 3, "start": 1.2, "end": 4.0, "remove": False},
            ],
            "hook": "متن هوک"
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4", "path/2.mp4", "path/3.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen"):
                    result = process_job(mock_job)

                    assert result is True
                    assert len(mock_orchestrator_calls) == 1
                    call = mock_orchestrator_calls[0]
                    # Removed shot (index 2) must NOT appear in video_segments
                    assert call["video_segments"] == [
                        {"key": "path/1.mp4", "start_sec": 0.0, "end_sec": 2.5},
                        {"key": "path/3.mp4", "start_sec": 1.2, "end_sec": 4.0},
                    ]
                    instance.mark_completed.assert_called_once_with("job-2", "edited/final.mp4")


def test_process_job_all_shots_removed_fails_with_typed_error():
    """A plan that removes every shot must fail with PLAN_ALL_SHOTS_REMOVED instead
    of silently rendering the full bundle."""
    mock_job = {
        "id": "job-3",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [
                {"index": 1, "start": 0.0, "end": None, "remove": True},
                {"index": 2, "start": 0.0, "end": None, "remove": True},
            ],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4", "path/2.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen") as mock_urlopen:
                    result = process_job(mock_job)

                    assert result is False
                    # Orchestrator must never be called
                    assert mock_orchestrator_calls == []

                    # Job marked FAILED with typed PLAN_ALL_SHOTS_REMOVED error
                    update_call = mock_db.client.table.return_value.update.call_args[0][0]
                    assert update_call["status"] == "FAILED"
                    assert update_call["error_message"] == "PLAN_ALL_SHOTS_REMOVED"

                    # Telegram notified in Persian
                    import json as _json
                    sent_text = _json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))["text"]
                    assert "PLAN_ALL_SHOTS_REMOVED" in sent_text
                    assert "رندر ناموفق بود" in sent_text


def test_process_job_passes_mute_original_from_plan():
    """plan_data.mute_original must reach render_content (keep original audio)."""
    mock_job = {
        "id": "job-4",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "mute_original": False,
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
            "hook": "متن هوک"
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4", "path/2.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen"):
                    result = process_job(mock_job)

                    assert result is True
                    call = mock_orchestrator_calls[0]
                    assert call["mute_original"] is False


def test_process_job_defaults_mute_original_true():
    """Legacy plan_data without mute_original must default to muted (True)."""
    mock_job = {
        "id": "job-5",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen"):
                    result = process_job(mock_job)

                    assert result is True
                    call = mock_orchestrator_calls[0]
                    assert call["mute_original"] is True


def test_process_job_passes_plan_sfx_to_render_content():
    """plan_data.sfx entries must reach render_content so the worker can
    resolve them into actual sound files."""
    mock_job = {
        "id": "job-6",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
            "sfx": [{"query": "صدای کلید", "start": 1.5, "gain": -6, "fade_in": 0.1, "fade_out": 0.3}],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen"):
                    result = process_job(mock_job)

                    assert result is True
                    call = mock_orchestrator_calls[0]
                    assert call["plan_sfx"] == [
                        {"query": "صدای کلید", "start": 1.5, "gain": -6, "fade_in": 0.1, "fade_out": 0.3}
                    ]


def test_process_job_passes_none_plan_sfx_when_absent():
    """Jobs without sfx must pass plan_sfx=None (no resolution attempt)."""
    mock_job = {
        "id": "job-7",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen"):
                    process_job(mock_job)

                    call = mock_orchestrator_calls[0]
                    assert call["plan_sfx"] is None


def test_process_job_passes_plan_music_to_render_content():
    """plan_data.music must reach render_content."""
    mock_job = {
        "id": "job-8",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
            "music": {"enabled": True, "query": "موسیقی آرام", "gain_db": -14, "explicit": True},
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen"):
                    result = process_job(mock_job)

                    assert result is True
                    call = mock_orchestrator_calls[0]
                    assert call["plan_music"] == {
                        "enabled": True, "query": "موسیقی آرام", "gain_db": -14, "explicit": True
                    }


def test_process_job_passes_none_plan_music_when_absent():
    """Jobs without music must pass plan_music=None."""
    mock_job = {
        "id": "job-9",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {"target_id": "ELN-BUNDLE-123", "shots": [{"index": 1, "start": 0.0, "end": 3.0}]},
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}

                with patch("urllib.request.urlopen"):
                    process_job(mock_job)

                    call = mock_orchestrator_calls[0]
                    assert call["plan_music"] is None


def test_process_job_records_exact_versioned_key():
    """Test E — Job records exact key:
    render_worker path: render_jobs.output_key equals the uploaded versioned key."""
    mock_job = {
        "id": "job-versioned-123",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    class MockOrchestrator:
        def render_content(self, **kwargs):
            # Simulate returning a versioned output key
            return {"ok": True, "output_key": "edited/ELN-BUNDLE-123/job-versioned-123.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}

                with patch("urllib.request.urlopen"):
                    result = process_job(mock_job)

                    assert result is True
                    # Assert job manager marked completed with the exact versioned key!
                    instance.mark_completed.assert_called_once_with(
                        "job-versioned-123",
                        "edited/ELN-BUNDLE-123/job-versioned-123.mp4"
                    )


def test_process_job_passes_job_id_to_render_content():
    """Test F — Worker passes job_id:
    render_worker calls render_content with the job's id."""
    mock_job = {
        "id": "my-mock-job-id",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 3.0}],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value

                with patch("urllib.request.urlopen"):
                    process_job(mock_job)

                    assert len(mock_orchestrator_calls) == 1
                    call = mock_orchestrator_calls[0]
                    # Assert job_id is passed to render_content
                    assert call["job_id"] == "my-mock-job-id"


def test_process_job_shot_index_out_of_range():
    """Test: shot index out of range -> FAILED with SHOT_INDEX_OUT_OF_RANGE."""
    mock_job = {
        "id": "job-range-err",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [
                {"index": 1, "start": 0.0, "end": 2.5, "remove": False},
                {"index": 3, "start": 0.0, "end": 2.5, "remove": False}, # out of range (max index 2)
            ],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4", "path/2.mp4"] # only 2 shots
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value

                with patch("urllib.request.urlopen") as mock_urlopen:
                    result = process_job(mock_job)

                    assert result is False
                    # Orchestrator must NOT be called
                    assert mock_orchestrator_calls == []

                    # Assert database status updated to FAILED with typed error message
                    mock_db.client.table.return_value.update.assert_called()
                    call_arg = mock_db.client.table.return_value.update.call_args[0][0]
                    assert call_arg["status"] == "FAILED"
                    assert "SHOT_INDEX_OUT_OF_RANGE" in call_arg["error_message"]
                    assert "shot 3 requested but bundle has 2 shots" in call_arg["error_message"]


def test_process_job_sends_signed_url():
    """Test: if signed URL generation is available, message includes signed URL."""
    mock_job = {
        "id": "job-1",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 2.5}],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    class MockOrchestrator:
        def render_content(self, **kwargs):
            return {"ok": True, "output_key": "edited/final.mp4"}

    class MockStorage:
        def create_signed_url(self, key, ttl):
            return f"https://signed.example/{key}"

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("agents.storage.supabase_storage.ElinaStorage", lambda: MockStorage()):
                with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                    instance = MockJobManager.return_value
                    instance.mark_completed.return_value = {}

                    with patch("urllib.request.urlopen") as mock_urlopen:
                        result = process_job(mock_job)

                        assert result is True
                        mock_urlopen.assert_called_once()
                        
                        # Verify that the sent text contains the signed URL
                        import json as _json
                        sent_payload = _json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
                        assert "https://signed.example/edited/final.mp4" in sent_payload["text"]
                        assert "🔗 لینک دانلود موقت" in sent_payload["text"]


def test_process_job_terminal_error_exits_cleanly():
    """Test A — terminal error exits cleanly:
    Given a job that triggers SHOT_INDEX_OUT_OF_RANGE,
    assert it returns False and does NOT raise any exception (exit 0 path)."""
    mock_job = {
        "id": "job-range-err",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 5, "start": 0.0, "end": 2.5}], # out of range (max index 2)
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4", "path/2.mp4"]
    }

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
            instance = MockJobManager.return_value

            with patch("urllib.request.urlopen"):
                result = process_job(mock_job)

                assert result is False # completed with False but does NOT raise!


def test_process_job_unexpected_error_raises_exception():
    """Test B — unexpected error still surfaces:
    Given a job where an unexpected exception occurs (e.g. database client raises),
    assert it re-raises the exception so the worker exits 1."""
    mock_job = {
        "id": "job-unexpected",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 2.5}],
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    # Database call raises an unexpected exception
    mock_db.get_content_by_custom_id.side_effect = Exception("Supabase DB crash")

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
            instance = MockJobManager.return_value
            instance.mark_failed.return_value = {}

            with patch("urllib.request.urlopen"):
                with pytest.raises(Exception) as excinfo:
                    process_job(mock_job)
                
                assert "Supabase DB crash" in str(excinfo.value)


def test_process_job_forwards_plan_voice():
    """plan_data with a 'voice' field must be forwarded to
    orchestrator.render_content as plan_voice (M15 wiring)."""
    voice_plan = {"text": "سلام", "voice": "farid", "rate": "-10%", "gain_db": -3, "start_sec": 0.5}
    mock_job = {
        "id": "job-voice",
        "content_id": "ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 2.5}],
            "hook": "متن هوک",
            "voice": voice_plan,
        },
        "owner_chat_id": "12345",
    }

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.return_value = {
        "id": "item-123",
        "custom_id": "ELN-BUNDLE-123",
        "media_keys": ["path/1.mp4"]
    }

    mock_orchestrator_calls = []
    class MockOrchestrator:
        def render_content(self, **kwargs):
            mock_orchestrator_calls.append(kwargs)
            return {"ok": True, "output_key": "edited/final.mp4"}

    with patch("scripts.render_worker.ElinaDB", lambda: mock_db):
        with patch("agents.editing.orchestrator.EditOrchestrator", lambda: MockOrchestrator()):
            with patch("scripts.render_worker.RenderJobManager") as MockJobManager:
                instance = MockJobManager.return_value
                instance.mark_completed.return_value = {}
                instance.mark_failed.return_value = {}
                with patch("urllib.request.urlopen"):
                    process_job(mock_job)

    assert len(mock_orchestrator_calls) == 1
    call = mock_orchestrator_calls[0]
    assert call["plan_voice"] == voice_plan
    instance.mark_completed.assert_called_once_with("job-voice", "edited/final.mp4")
