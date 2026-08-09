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
