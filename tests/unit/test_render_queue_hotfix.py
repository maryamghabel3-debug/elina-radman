import os
import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock, patch, ANY

from agents.editing.orchestrator import validate_video_asset
from agents.rendering.job_manager import RenderJobManager
from scripts.supabase_bundle_job_repair import run_repair

pytestmark = pytest.mark.unit


# 1. invalid placeholder asset rejected before FFmpeg
def test_invalid_placeholder_asset_rejected(tmp_path):
    local_path = tmp_path / "clip.mp4"
    # Write synthetic mock placeholder (repeating '0's)
    local_path.write_bytes(b"0" * 20000)

    # By default, without test bypass, mock files must be rejected!
    with patch.dict(os.environ, {"ELINA_TEST_ALLOW_MOCKS": "false"}):
        assert validate_video_asset(str(local_path)) is False

    # Under test bypass mode, mock files are allowed
    with patch.dict(os.environ, {"ELINA_TEST_ALLOW_MOCKS": "true"}):
        assert validate_video_asset(str(local_path)) is True


# 2. repaired job with invalid assets is NOT requeued
def test_repaired_job_with_invalid_assets_not_requeued(tmp_path):
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_items_result = MagicMock()
    mock_items_result.data = [{
        "id": "item-1",
        "custom_id": "ELN-BUNDLE-123",
        "content_type": "reel",
        "media_keys": ["path/1.mp4"]
    }]
    mock_items_result.execute.return_value = mock_items_result

    mock_jobs_result = MagicMock()
    mock_jobs_result.data = [{
        "id": "job-1",
        "content_id": "ELN-BUNDLE-ELN-BUNDLE-123",
        "status": "QUEUED",
        "plan_data": {"target_id": "ELN-BUNDLE-ELN-BUNDLE-123"},
        "attempts": 0
    }]
    mock_jobs_result.execute.return_value = mock_jobs_result

    mock_query.select.side_effect = [mock_items_result, mock_jobs_result]

    # Mock storage to write a placeholder file
    mock_storage = MagicMock()
    def download_side_effect(key, local_path):
        with open(local_path, "wb") as f:
            f.write(b"0" * 20000)
    mock_storage.download_file.side_effect = download_side_effect

    with patch("agents.storage.supabase_storage.ElinaStorage", lambda: mock_storage):
        with patch.dict(os.environ, {"ELINA_TEST_ALLOW_MOCKS": "false"}):
            with patch("sys.exit") as mock_exit:
                res = run_repair(mock_db)

                # Confirms it was NOT requeued (jobs_requeued is 0)
                assert res["jobs_requeued"] == 0

                # Check that the job status was marked as FAILED with INVALID_SOURCE_ASSET_PLACEHOLDER
                mock_query.update.assert_called_with({
                    "status": "FAILED",
                    "error_message": "INVALID_SOURCE_ASSET_PLACEHOLDER"
                })


# 3. new job supersedes/cancels older competing jobs
def test_new_job_supersedes_older_competing_jobs():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.in_.return_value = mock_query
    mock_query.insert.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = [{"id": "job-new", "status": "QUEUED"}]
    mock_query.execute.return_value = mock_result

    manager = RenderJobManager(db=mock_db)
    job = manager.queue_job("ELN-BUNDLE-123", {"target_id": "ELN-BUNDLE-123"}, "owner_id")

    # Verify update was called to mark QUEUED/IN_PROGRESS competing jobs as FAILED/SUPERSEDED
    mock_query.update.assert_any_call({
        "status": "FAILED",
        "error_message": "SUPERSEDED_BY_NEWER_RENDER_JOB"
    })
    mock_query.eq.assert_any_call("content_id", "ELN-BUNDLE-123")
    mock_query.in_.assert_any_call("status", ["QUEUED", "IN_PROGRESS"])


# 4. duplicate /plan_ok does not create multiple active jobs
@pytest.mark.asyncio
async def test_duplicate_plan_ok_does_not_create_multiple_jobs():
    import scripts.elina_studio_bot as bot_module

    # Setup chat_data containing the same plan_preview as the existing active job
    from agents.editing.persian_edit_interpreter import PersianEditPlan
    plan = PersianEditPlan(
        target_mode="custom_id",
        target_custom_id="ELN-BUNDLE-123",
        hook_text="تست",
        confidence=1.0
    )
    chat_data = {"plan_mode": True, "plan_preview": plan, "plan_target_id": "ELN-BUNDLE-123"}

    # Mock Update and Context
    mock_user = MagicMock()
    mock_user.username = "tester"
    mock_user.first_name = "Test"

    mock_chat = MagicMock()
    mock_chat.id = "12345"

    mock_message = MagicMock()
    mock_message.chat = mock_chat
    mock_message.chat_id = "12345"
    mock_message.from_user = mock_user
    mock_message.reply_text = AsyncMock()

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = []
    mock_context.chat_data = chat_data

    # Mock RenderJobManager so it returns an already existing identical active job
    mock_job_manager = MagicMock()
    mock_query = MagicMock()
    mock_job_manager.db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.in_.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = [{
        "id": "job-existing-123",
        "status": "QUEUED",
        "plan_data": {
            "target_id": "ELN-BUNDLE-123",
            "mute_original": True,
            "shots": [],
            "sfx": [],
            "hook": "تست",
            "music": {"enabled": False, "query": None, "gain_db": -14, "explicit": False}
        }
    }]
    mock_query.execute.return_value = mock_result

    with patch("agents.rendering.job_manager.RenderJobManager", lambda: mock_job_manager):
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_plan_ok(mock_update, mock_context)

        # Assert queue_job was NOT called!
        mock_job_manager.queue_job.assert_not_called()

        # Confirm reply contains identical job ID message
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "قبلاً ثبت شده" in reply_text
        assert "job-existing-123" in reply_text


# 5. /edit flow messaging or behavior matches reality
@pytest.mark.asyncio
async def test_edit_command_guidance_response():
    import scripts.elina_studio_bot as bot_module

    # Mock Update and Context
    mock_user = MagicMock()
    mock_user.username = "tester"
    mock_user.first_name = "Test"

    mock_chat = MagicMock()
    mock_chat.id = "12345"

    mock_message = MagicMock()
    mock_message.chat = mock_chat
    mock_message.chat_id = "12345"
    mock_message.from_user = mock_user
    mock_message.reply_text = AsyncMock()

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = ["ELN-BUNDLE-123", "اضافه کردن هوک اول ویدیو"]

    mock_approval_manager = MagicMock()
    mock_approval_manager.mark_needs_edit.return_value = {
        "ok": True,
        "custom_id": "ELN-BUNDLE-123"
    }

    with patch("scripts.elina_studio_bot.ApprovalManager", lambda: mock_approval_manager):
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_edit(mock_update, mock_context)

    # Assert reply contains the clear guidance on `/plan`
    mock_update.message.reply_text.assert_called_once()
    reply_text = mock_update.message.reply_text.call_args[0][0]
    assert "نیازمند ادیت" in reply_text
    assert "برای نوشتن برنامه ادیت" in reply_text
    assert "/plan ELN-BUNDLE-123" in reply_text
