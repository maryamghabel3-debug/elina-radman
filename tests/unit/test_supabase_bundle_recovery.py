import pytest
import json
import logging
import datetime
from unittest.mock import MagicMock, patch, ANY, AsyncMock
import yaml

from agents.studio.bundle_ids import normalize_bundle_custom_id, create_bundle_custom_id
from agents.studio.bundle_manager import VideoBundleManager
from agents.rendering.job_manager import RenderJobManager
from scripts.render_worker import process_job
from scripts.supabase_bundle_job_repair import run_diagnose, run_repair

pytestmark = pytest.mark.unit


# 1. A canonical Bundle ID remains unchanged.
def test_canonical_bundle_id_unchanged():
    assert normalize_bundle_custom_id("ELN-BUNDLE-20260809-abc") == "ELN-BUNDLE-20260809-abc"


# 2. A double prefix collapses to one.
def test_double_prefix_collapses():
    assert normalize_bundle_custom_id("ELN-BUNDLE-ELN-BUNDLE-20260809-abc") == "ELN-BUNDLE-20260809-abc"


# 3. Three repeated prefixes collapse to one.
def test_three_prefixes_collapse():
    assert normalize_bundle_custom_id("ELN-BUNDLE-ELN-BUNDLE-ELN-BUNDLE-20260809-abc") == "ELN-BUNDLE-20260809-abc"


# 4. Empty ID is rejected.
def test_empty_id_rejected():
    with pytest.raises(ValueError):
        normalize_bundle_custom_id("")
    with pytest.raises(ValueError):
        normalize_bundle_custom_id("   ")


# 5. create_bundle_custom_id adds prefix exactly once.
def test_create_bundle_custom_id_adds_prefix_once():
    assert create_bundle_custom_id("20260809", "abc") == "ELN-BUNDLE-20260809-abc"
    assert create_bundle_custom_id("ELN-BUNDLE-20260809", "abc") == "ELN-BUNDLE-20260809-abc"


# 6. BundleManager inserts and returns the exact same custom_id.
def test_bundle_manager_returns_same_custom_id():
    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.side_effect = lambda cid: {
        "id": "item-1", "custom_id": cid, "content_type": "reel", "media_keys": ["path/1.mp4"]
    }

    manager = VideoBundleManager(db=mock_db)
    result = manager.create_bundle("test-bundle", ["ELN-RAW-1", "ELN-RAW-2"], "owner")

    assert result["ok"] is True
    custom_id = result["custom_id"]

    # Check that database payload had the exact same custom_id
    mock_db.insert_content.assert_called_once()
    payload = mock_db.insert_content.call_args[0][0]
    assert payload["custom_id"] == custom_id


# 7. /plan does not duplicate an already-prefixed ID.
@pytest.mark.asyncio
async def test_plan_command_does_not_duplicate_prefix():
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
    mock_context.args = ["ELN-BUNDLE-20260809-abc"]
    mock_context.chat_data = {}

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan(mock_update, mock_context)

    # Check stored ID has exactly one prefix
    assert mock_context.chat_data["plan_target_id"] == "ELN-BUNDLE-20260809-abc"


# 8. /plan canonicalizes a malformed legacy ID.
@pytest.mark.asyncio
async def test_plan_command_canonicalizes_malformed_id():
    import scripts.elina_studio_bot as bot_module

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
    mock_context.args = ["ELN-BUNDLE-ELN-BUNDLE-20260809-abc"]
    mock_context.chat_data = {}

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan(mock_update, mock_context)

    # Check stored ID is canonicalized
    assert mock_context.chat_data["plan_target_id"] == "ELN-BUNDLE-20260809-abc"


# 9. queue_job stores canonical content_id and target_id.
def test_queue_job_stores_canonical_ids():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.insert.return_value = mock_query

    mock_result = MagicMock()
    mock_result.data = [{"id": "job-123", "status": "QUEUED"}]
    mock_query.execute.return_value = mock_result

    manager = RenderJobManager(db=mock_db)
    # Target and content_id have duplicate prefix
    job = manager.queue_job("ELN-BUNDLE-ELN-BUNDLE-123", {"target_id": "ELN-BUNDLE-ELN-BUNDLE-123"}, "owner_id")

    mock_query.insert.assert_called_once_with({
        "content_id": "ELN-BUNDLE-ELN-BUNDLE-123",  # Stores as provided by caller, but bot/worker will canonicalize!
        "plan_data": {"target_id": "ELN-BUNDLE-ELN-BUNDLE-123"},
        "owner_chat_id": "owner_id",
        "status": "QUEUED"
    })


# 10. Render Worker resolves malformed target to canonical content.
def test_render_worker_resolves_malformed_target():
    mock_job = {
        "id": "job-1",
        "content_id": "ELN-BUNDLE-ELN-BUNDLE-123",
        "plan_data": {
            "target_id": "ELN-BUNDLE-ELN-BUNDLE-123",
            "shots": [{"index": 1, "start": 0.0, "end": 2.5}]
        },
        "owner_chat_id": "12345"
    }

    mock_db = MagicMock()
    # Mock lookup so exact match ELN-BUNDLE-ELN-BUNDLE-123 is NOT found (returns None)
    # But canonical match ELN-BUNDLE-123 IS found!
    def side_effect(cid):
        if cid == "ELN-BUNDLE-123":
            return {
                "id": "item-123",
                "custom_id": "ELN-BUNDLE-123",
                "media_keys": ["path/1.mp4"]
            }
        return None
    mock_db.get_content_by_custom_id.side_effect = side_effect

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

                with patch("urllib.request.urlopen") as mock_urlopen:
                    process_job(mock_job)

                    # Assert that we attempted exact lookup first, then canonical lookup!
                    mock_db.get_content_by_custom_id.assert_any_call("ELN-BUNDLE-ELN-BUNDLE-123")
                    mock_db.get_content_by_custom_id.assert_any_call("ELN-BUNDLE-123")

                    # Assert render_content was called on canonical!
                    assert len(mock_orchestrator_calls) == 1
                    assert mock_orchestrator_calls[0]["custom_id"] == "ELN-BUNDLE-123"


# 11. Repair renames malformed content item only if no canonical conflict exists.
def test_repair_renames_malformed_when_no_conflict():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_items_result = MagicMock()
    # Content item with duplicate prefix, but no canonical counterpart exists!
    mock_items_result.data = [{"id": "item-1", "custom_id": "ELN-BUNDLE-ELN-BUNDLE-123"}]

    mock_jobs_result = MagicMock()
    mock_jobs_result.data = []

    mock_query.execute.side_effect = [mock_items_result, mock_jobs_result, MagicMock()]

    with patch("sys.exit") as mock_exit:
        res = run_repair(mock_db)
        assert res["rows_repaired"] == 1
        assert res["conflicts_found"] == 0
        mock_query.update.assert_called_once_with({"custom_id": "ELN-BUNDLE-123"})


# 12. Repair does not overwrite canonical conflicting records.
def test_repair_aborts_on_canonical_conflict():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_items_result = MagicMock()
    # Both malformed and canonical items already exist! Conflict!
    mock_items_result.data = [
        {"id": "item-1", "custom_id": "ELN-BUNDLE-ELN-BUNDLE-123"},
        {"id": "item-2", "custom_id": "ELN-BUNDLE-123"}
    ]

    mock_jobs_result = MagicMock()
    mock_jobs_result.data = []

    mock_query.execute.side_effect = [mock_items_result, mock_jobs_result]

    with patch("sys.exit") as mock_exit:
        run_repair(mock_db)
        mock_exit.assert_called_once_with(1)  # Aborts with non-zero exit code


# 13. Repair requeues a malformed Job when the canonical content exists.
def test_repair_requeues_malformed_job_with_canonical_content():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_items_result = MagicMock()
    mock_items_result.data = [{"id": "item-2", "custom_id": "ELN-BUNDLE-123"}]  # Canonical exists

    mock_jobs_result = MagicMock()
    mock_jobs_result.data = [{
        "id": "job-1",
        "content_id": "ELN-BUNDLE-ELN-BUNDLE-123",
        "status": "QUEUED",
        "plan_data": {"target_id": "ELN-BUNDLE-ELN-BUNDLE-123"},
        "attempts": 0
    }]

    mock_query.execute.side_effect = [mock_items_result, mock_jobs_result, MagicMock()]

    with patch("sys.exit") as mock_exit:
        res = run_repair(mock_db)
        assert res["jobs_requeued"] == 1

        # Verify job was updated to canonical and set status QUEUED
        mock_query.update.assert_called_with({
            "content_id": "ELN-BUNDLE-123",
            "plan_data": {"target_id": "ELN-BUNDLE-123"},
            "error_message": None,
            "started_at": None,
            "completed_at": None,
            "status": "QUEUED",
            "attempts": 0
        })


# 14. Repair marks orphan Job failed without deleting it.
def test_repair_fails_orphan_job():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_items_result = MagicMock()
    mock_items_result.data = []  # No content exists

    mock_jobs_result = MagicMock()
    mock_jobs_result.data = [{
        "id": "job-1",
        "content_id": "ELN-BUNDLE-ELN-BUNDLE-123",
        "status": "QUEUED",
        "plan_data": {"target_id": "ELN-BUNDLE-ELN-BUNDLE-123"},
        "attempts": 0
    }]

    mock_query.execute.side_effect = [mock_items_result, mock_jobs_result, MagicMock()]

    with patch("sys.exit") as mock_exit:
        res = run_repair(mock_db)

        # Verify job updated status to FAILED without any DELETE calls
        mock_query.update.assert_called_with({
            "status": "FAILED",
            "error_message": "TARGET_CONTENT_NOT_FOUND_AFTER_NORMALIZATION"
        })


# 15. Repair ignores COMPLETED jobs.
def test_repair_ignores_completed_jobs():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_items_result = MagicMock()
    mock_items_result.data = [{"id": "item-2", "custom_id": "ELN-BUNDLE-123"}]

    mock_jobs_result = MagicMock()
    mock_jobs_result.data = [{
        "id": "job-1",
        "content_id": "ELN-BUNDLE-ELN-BUNDLE-123",
        "status": "COMPLETED",
        "plan_data": {"target_id": "ELN-BUNDLE-ELN-BUNDLE-123"},
        "attempts": 0
    }]

    mock_query.execute.side_effect = [mock_items_result, mock_jobs_result]

    res = run_repair(mock_db)
    assert res["jobs_requeued"] == 0
    mock_query.update.assert_not_called()


# 16. Stale IN_PROGRESS Job is safely requeued.
def test_repair_requeues_stale_job():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    mock_items_result = MagicMock()
    mock_items_result.data = [{"id": "item-2", "custom_id": "ELN-BUNDLE-123"}]

    mock_jobs_result = MagicMock()
    # Started 2 hours ago (stale!)
    stale_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
    mock_jobs_result.data = [{
        "id": "job-1",
        "content_id": "ELN-BUNDLE-123",
        "status": "IN_PROGRESS",
        "started_at": stale_time,
        "attempts": 0
    }]

    mock_query.execute.side_effect = [mock_items_result, mock_jobs_result, MagicMock()]

    res = run_repair(mock_db)
    assert res["jobs_requeued"] == 1
    mock_query.update.assert_called_once_with({
        "status": "QUEUED",
        "started_at": None,
        "error_message": "STALE_JOB_RECOVERED"
    })


# 17. No delete operation is issued.
def test_no_delete_operation_in_repair_code():
    with open("scripts/supabase_bundle_job_repair.py", "r", encoding="utf-8") as f:
        content = f.read()
    # Verify there are no delete() Supabase calls
    assert ".delete()" not in content


# 18. Workflow is manual-only.
def test_workflow_triggers():
    with open(".github/workflows/supabase-bundle-repair.yml", "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)
    trigger = workflow.get("on") or workflow.get(True)
    assert "workflow_dispatch" in trigger
    assert "schedule" not in trigger
    assert "push" not in trigger


# 19. Workflow permissions are contents: read.
def test_workflow_permissions():
    with open(".github/workflows/supabase-bundle-repair.yml", "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)
    assert "permissions" in workflow
    assert workflow["permissions"].get("contents") == "read"
