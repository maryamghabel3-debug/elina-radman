import logging
import datetime
from datetime import timezone
from typing import Optional, Dict, Any

from agents.db.supabase_client import ElinaDB

logger = logging.getLogger(__name__)


class RenderJobManager:
    """
    Manages Render Jobs inside Supabase 'render_jobs' table.
    """

    def __init__(self, db: Optional[ElinaDB] = None):
        self.db = db or ElinaDB()

    def queue_job(self, content_id: str, plan_data: dict, owner_chat_id: str) -> dict:
        """
        Insert a new render job with status QUEUED. Return job dict.
        Older competing active jobs for the same content_id are marked as FAILED/SUPERSEDED.
        """
        # Mark older active jobs for the same content_id as FAILED/SUPERSEDED
        try:
            self.db.client.table("render_jobs").update({
                "status": "FAILED",
                "error_message": "SUPERSEDED_BY_NEWER_RENDER_JOB"
            }).eq("content_id", content_id).in_("status", ["QUEUED", "IN_PROGRESS"]).execute()
            logger.info(f"Superseded older active render jobs for content_id '{content_id}'")
        except Exception as e:
            logger.error(f"Failed to supersede older jobs for '{content_id}': {e}")

        # Insert new queued job
        res = self.db.client.table("render_jobs").insert({
            "content_id": content_id,
            "plan_data": plan_data,
            "owner_chat_id": str(owner_chat_id),
            "status": "QUEUED"
        }).execute()
        if res.data:
            return res.data[0]
        return {}

    def get_next_queued_job(self) -> Optional[dict]:
        """
        Return oldest QUEUED job or None. Mark it IN_PROGRESS atomically.
        """
        res = self.db.client.table("render_jobs").select("*").eq("status", "QUEUED").order("created_at", desc=False).limit(1).execute()
        if not res.data:
            return None
        job = res.data[0]

        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        update_res = self.db.client.table("render_jobs").update({
            "status": "IN_PROGRESS",
            "started_at": started_at
        }).eq("id", job["id"]).execute()

        if update_res.data:
            return update_res.data[0]
        return None

    def mark_completed(self, job_id: str, output_key: str) -> dict:
        """
        Set status COMPLETED, output_key, completed_at.
        """
        completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        res = self.db.client.table("render_jobs").update({
            "status": "COMPLETED",
            "output_key": output_key,
            "completed_at": completed_at
        }).eq("id", job_id).execute()
        if res.data:
            return res.data[0]
        return {}

    def mark_failed(self, job_id: str, error_message: str) -> dict:
        """
        Increment attempts. If attempts >= max_attempts set FAILED, else QUEUED again.
        Jobs with terminal error reasons are marked as FAILED immediately with no retries.
        """
        res_get = self.db.client.table("render_jobs").select("*").eq("id", job_id).execute()
        if not res_get.data:
            return {}
        job = res_get.data[0]

        attempts = (job.get("attempts") or 0) + 1
        max_attempts = job.get("max_attempts") or 3

        updates = {
            "attempts": attempts,
            "error_message": error_message,
        }

        # Terminal error check (never retry)
        is_terminal = (
            "INVALID_SOURCE_ASSET_PLACEHOLDER" in error_message
            or "TARGET_CONTENT_NOT_FOUND" in error_message
            or "SUPERSEDED" in error_message
            or "SFX_PROVIDER_NOT_CONFIGURED" in error_message
            or "SFX_FETCH_FAILED" in error_message
            or "SFX_INVALID_PLAN_ENTRY" in error_message
            or "MUSIC_PROVIDER_NOT_CONFIGURED" in error_message
            or "SHOT_INDEX_OUT_OF_RANGE" in error_message
            or "SFX_ANCHOR_OUT_OF_RANGE" in error_message
            or "SFX_AUTH_FAILED" in error_message
            or "SFX_SEARCH_REQUEST_INVALID" in error_message
            # Voice generation: plan-data/validation errors are terminal.
            # VOICE_GENERATION_FAILED is intentionally NOT terminal: it usually
            # means a transient network issue and the job should be retried.
            or "VOICE_TEXT_EMPTY" in error_message
            or "VOICE_TEXT_TOO_LONG" in error_message
            or "VOICE_UNSUPPORTED" in error_message
            or "VOICE_RATE_INVALID" in error_message
            or "VOICE_INVALID_PLAN_ENTRY" in error_message
            or "SUBTITLE_CONFIG_INVALID" in error_message
            or "SUBTITLE_FONT_NOT_FOUND" in error_message
            or "VOICE_SUBTITLE_SYNC_CONFIG_INVALID" in error_message
        )

        if is_terminal or attempts >= max_attempts:
            updates["status"] = "FAILED"
            completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            updates["completed_at"] = completed_at
        else:
            updates["status"] = "QUEUED"

        res = self.db.client.table("render_jobs").update(updates).eq("id", job_id).execute()
        if res.data:
            return res.data[0]
        return {}
