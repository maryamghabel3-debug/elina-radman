import pytest
from unittest.mock import MagicMock, patch
from agents.rendering.job_manager import RenderJobManager

pytestmark = pytest.mark.unit


def test_queue_job_creates_queued_record():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.insert.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = [{"id": "job-123", "status": "QUEUED"}]
    mock_query.execute.return_value = mock_result

    manager = RenderJobManager(db=mock_db)
    job = manager.queue_job("ELN-1", {"shots": []}, "owner_id")

    assert job["id"] == "job-123"
    assert job["status"] == "QUEUED"
    mock_db.client.table.assert_called_with("render_jobs")
    mock_query.insert.assert_called_once_with({
        "content_id": "ELN-1",
        "plan_data": {"shots": []},
        "owner_chat_id": "owner_id",
        "status": "QUEUED"
    })


def test_get_next_queued_job_returns_oldest():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.update.return_value = mock_query

    mock_result_select = MagicMock()
    mock_result_select.data = [{"id": "job-1", "status": "QUEUED", "created_at": "some-time"}]

    mock_result_update = MagicMock()
    mock_result_update.data = [{"id": "job-1", "status": "IN_PROGRESS"}]

    mock_query.execute.side_effect = [mock_result_select, mock_result_update]

    manager = RenderJobManager(db=mock_db)
    job = manager.get_next_queued_job()

    assert job is not None
    assert job["id"] == "job-1"
    assert job["status"] == "IN_PROGRESS"
    mock_query.order.assert_called_once_with("created_at", desc=False)


def test_get_next_queued_job_returns_none_when_empty():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = []
    mock_query.execute.return_value = mock_result

    manager = RenderJobManager(db=mock_db)
    job = manager.get_next_queued_job()

    assert job is None


def test_mark_completed_sets_status():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = [{"id": "job-1", "status": "COMPLETED", "output_key": "edited/out.mp4"}]
    mock_query.execute.return_value = mock_result

    manager = RenderJobManager(db=mock_db)
    job = manager.mark_completed("job-1", "edited/out.mp4")

    assert job["status"] == "COMPLETED"
    assert job["output_key"] == "edited/out.mp4"


def test_mark_failed_increments_attempts():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.update.return_value = mock_query

    mock_result_select = MagicMock()
    mock_result_select.data = [{"id": "job-1", "attempts": 0, "max_attempts": 3, "status": "IN_PROGRESS"}]

    mock_result_update = MagicMock()
    mock_result_update.data = [{"id": "job-1", "attempts": 1, "status": "QUEUED"}]

    mock_query.execute.side_effect = [mock_result_select, mock_result_update]

    manager = RenderJobManager(db=mock_db)
    job = manager.mark_failed("job-1", "error")

    assert job["attempts"] == 1
    assert job["status"] == "QUEUED"


def test_mark_failed_sets_failed_at_max_attempts():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.update.return_value = mock_query

    mock_result_select = MagicMock()
    mock_result_select.data = [{"id": "job-1", "attempts": 2, "max_attempts": 3, "status": "IN_PROGRESS"}]

    mock_result_update = MagicMock()
    mock_result_update.data = [{"id": "job-1", "attempts": 3, "status": "FAILED"}]

    mock_query.execute.side_effect = [mock_result_select, mock_result_update]

    manager = RenderJobManager(db=mock_db)
    job = manager.mark_failed("job-1", "error")

    assert job["attempts"] == 3
    assert job["status"] == "FAILED"


def test_mark_failed_sfx_errors_are_terminal():
    """SFX provider/fetch errors must not be requeued (no pointless retries)."""
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.select.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = [{"id": "job-1", "attempts": 0, "max_attempts": 3}]
    mock_query.execute.return_value = mock_result

    manager = RenderJobManager(db=mock_db)

    for error in ["SFX_PROVIDER_NOT_CONFIGURED: Missing FREESOUND_API_KEY", "SFX_FETCH_FAILED: no match for 'x'", "SFX_INVALID_PLAN_ENTRY: bad"]:
        mock_query.reset_mock()
        mock_query.update.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.execute.return_value = mock_result

        manager.mark_failed("job-1", error)

        update_call = mock_query.update.call_args[0][0]
        assert update_call["status"] == "FAILED"
        assert update_call["attempts"] == 1


def test_mark_failed_music_error_is_terminal():
    """MUSIC_PROVIDER_NOT_CONFIGURED must not be requeued."""
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.select.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = [{"id": "job-1", "attempts": 0, "max_attempts": 3}]
    mock_query.execute.return_value = mock_result

    manager = RenderJobManager(db=mock_db)
    manager.mark_failed("job-1", "MUSIC_PROVIDER_NOT_CONFIGURED: plan requests music but no asset")

    update_call = mock_query.update.call_args[0][0]
    assert update_call["status"] == "FAILED"
