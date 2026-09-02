import logging
import datetime
from datetime import timezone
from typing import Optional, Dict, Any

from agents.db.supabase_client import ElinaDB

logger = logging.getLogger(__name__)

# Terminal error codes: jobs failing with one of these are never retried.
# (VOICE_GENERATION_FAILED and RENDER_TIMEOUT are intentionally absent —
# they are transient and must stay retryable while attempts remain.)
TERMINAL_ERROR_CODES = (
    "INVALID_SOURCE_ASSET_PLACEHOLDER",
    "TARGET_CONTENT_NOT_FOUND",
    "SUPERSEDED",
    "SFX_PROVIDER_NOT_CONFIGURED",
    "SFX_FETCH_FAILED",
    "SFX_INVALID_PLAN_ENTRY",
    "MUSIC_PROVIDER_NOT_CONFIGURED",
    "SHOT_INDEX_OUT_OF_RANGE",
    "SFX_ANCHOR_OUT_OF_RANGE",
    "SFX_AUTH_FAILED",
    "SFX_SEARCH_REQUEST_INVALID",
    # Voice generation: plan-data/validation errors are terminal.
    "VOICE_TEXT_EMPTY",
    "VOICE_TEXT_TOO_LONG",
    "VOICE_UNSUPPORTED",
    "VOICE_RATE_INVALID",
    "VOICE_INVALID_PLAN_ENTRY",
    # Carousel studio: config/font errors are terminal.
    "SUBTITLE_CONFIG_INVALID",
    "SUBTITLE_FONT_NOT_FOUND",
    "VOICE_SUBTITLE_SYNC_CONFIG_INVALID",
)


def is_terminal_error_message(message: str) -> bool:
    """True when the error message contains a terminal (never-retry) code."""
    msg = message or ""
    return any(code in msg for code in TERMINAL_ERROR_CODES)


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
        Return oldest QUEUED job or None. The claim is atomic: a conditional
        UPDATE guarded by status='QUEUED' (see claim_next_job).
        """
        return self.claim_next_job()

    def claim_next_job(self, max_candidates: int = 5) -> Optional[dict]:
        """
        Atomically claim the next QUEUED job.

        The claim is a conditional UPDATE (WHERE id=<candidate> AND
        status='QUEUED'). If two runners race, only one update matches; the
        loser gets zero rows and moves to the next candidate (bounded by
        max_candidates). A zero-row update is NEVER treated as a successful
        claim.

        Note: `attempts` is intentionally NOT incremented here — the existing
        semantics (increment on failure in mark_failed) are preserved, so
        max_attempts still bounds the number of failure retries.
        """
        for _ in range(max(1, int(max_candidates))):
            res = self.db.client.table("render_jobs").select("*").eq("status", "QUEUED").order("created_at", desc=False).limit(1).execute()
            if not res.data:
                return None
            candidate = res.data[0]

            started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            update_res = self.db.client.table("render_jobs").update({
                "status": "IN_PROGRESS",
                "started_at": started_at,
            }).eq("id", candidate["id"]).eq("status", "QUEUED").execute()

            if update_res.data:
                logger.info(f"Claimed job {candidate.get('id')} (content {candidate.get('content_id')})")
                return update_res.data[0]
            # Lost the race to another runner (or the job vanished) — try next.
            logger.info(f"Claim for job {candidate.get('id')} lost the race; trying next candidate")
        logger.warning(f"No job could be claimed after {max_candidates} candidates")
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

        # Terminal error check (never retry) — shared with the worker loop
        is_terminal = is_terminal_error_message(error_message)

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

    def recover_stale_jobs(self, stale_minutes: int = 30) -> Dict[str, list]:
        """
        Recover jobs stuck in IN_PROGRESS (e.g. the runner was killed
        mid-render and the job would otherwise stay IN_PROGRESS forever).

        A job is stale when started_at is older than `stale_minutes`. Every
        recovery update is a guarded conditional update
        (status='IN_PROGRESS' AND started_at < cutoff), so a job that
        legitimately just finished is never clobbered.

        - attempts < max_attempts -> back to QUEUED with
          error_message=RECOVERED_FROM_STALE_IN_PROGRESS
        - otherwise -> FAILED with RENDER_STALE_ABANDONED

        Returns {"recovered": [...], "abandoned": [...]} (job dicts); the
        caller is responsible for owner notifications.
        """
        cutoff = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=int(stale_minutes))
        ).isoformat()
        res = (
            self.db.client.table("render_jobs")
            .select("*")
            .eq("status", "IN_PROGRESS")
            .lt("started_at", cutoff)
            .execute()
        )
        stale_jobs = res.data or []
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        recovered: list = []
        abandoned: list = []
        for job in stale_jobs:
            attempts = job.get("attempts") or 0
            max_attempts = job.get("max_attempts") or 3
            if attempts < max_attempts:
                update = {
                    "status": "QUEUED",
                    "error_message": "RECOVERED_FROM_STALE_IN_PROGRESS",
                }
                bucket = recovered
            else:
                update = {
                    "status": "FAILED",
                    "error_message": "RENDER_STALE_ABANDONED",
                    "completed_at": now,
                }
                bucket = abandoned
            update_res = (
                self.db.client.table("render_jobs")
                .update(update)
                .eq("id", job["id"])
                .eq("status", "IN_PROGRESS")
                .lt("started_at", cutoff)
                .execute()
            )
            if update_res.data:
                bucket.append(update_res.data[0])
                logger.info(
                    f"Stale job {job.get('id')} "
                    + ("recovered to QUEUED" if bucket is recovered else "abandoned as FAILED")
                )
            else:
                logger.info(
                    f"Stale recovery for job {job.get('id')} lost the race (job moved on)"
                )
        return {"recovered": recovered, "abandoned": abandoned}
