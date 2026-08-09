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
        """
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
        res = self.db.client.table("render_jobs").select("*").eq("status", "QUEUED").order("created_at", ascending=True).limit(1).execute()
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

        if attempts >= max_attempts:
            updates["status"] = "FAILED"
            completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            updates["completed_at"] = completed_at
        else:
            updates["status"] = "QUEUED"

        res = self.db.client.table("render_jobs").update(updates).eq("id", job_id).execute()
        if res.data:
            return res.data[0]
        return {}
