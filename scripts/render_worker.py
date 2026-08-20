import os
import sys
import json
import logging
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.rendering.job_manager import RenderJobManager
from agents.db.supabase_client import ElinaDB
from agents.studio.bundle_ids import normalize_bundle_custom_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RenderWorker")


def send_telegram_message(chat_id, text):
    token = os.environ.get("STUDIO_BOT_TOKEN")
    if not token or not chat_id:
        logger.warning("Cannot send Telegram notification: missing token or chat_id")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        logger.warning(f"Telegram notification failed: {exc}")


def process_job(job) -> bool:
    job_id = job["id"]
    content_id = job["plan_data"].get("target_id", job["content_id"])
    plan = job["plan_data"]
    chat_id = job.get("owner_chat_id")

    logger.info(f"Processing render job {job_id} for {content_id}")

    try:
        db = ElinaDB()
        item = db.get_content_by_custom_id(content_id)
        canonical_id = normalize_bundle_custom_id(content_id)

        if not item and canonical_id != content_id:
            # Try the canonical target ID
            item = db.get_content_by_custom_id(canonical_id)
            if item:
                content_id = canonical_id
                plan["target_id"] = canonical_id
                # Update job in DB
                db.client.table("render_jobs").update({
                    "content_id": canonical_id,
                    "plan_data": plan
                }).eq("id", job_id).execute()

        if not item:
            mgr = RenderJobManager()
            import datetime
            completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            db.client.table("render_jobs").update({
                "status": "FAILED",
                "error_message": "TARGET_CONTENT_NOT_FOUND",
                "completed_at": completed_at
            }).eq("id", job_id).execute()

            send_telegram_message(chat_id, f"❌ رندر ناموفق بود:\nTARGET_CONTENT_NOT_FOUND")
            return False

        media_keys = item.get("media_keys") if item else []

        # Map shots to video_segments, skipping shots the user asked to remove.
        # Shot indices refer to the original clip positions, so filtering on the
        # remove flag does not shift the indices of the remaining shots.
        video_segments = []
        for shot in plan.get("shots", []):
            if shot.get("remove"):
                logger.info(f"Shot {shot.get('index')} is marked for removal; skipping in render")
                continue
            idx = shot.get("index", 1) - 1  # 0-based index
            if idx < len(media_keys):
                key = media_keys[idx]
                video_segments.append({
                    "key": key,
                    "start_sec": shot.get("start", 0.0),
                    "end_sec": shot.get("end"),
                })

        # A plan that removes every shot leaves nothing to render: fail loudly
        # with a typed error instead of silently rendering the full bundle.
        if plan.get("shots") and not video_segments:
            mgr = RenderJobManager()
            import datetime
            completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            db.client.table("render_jobs").update({
                "status": "FAILED",
                "error_message": "PLAN_ALL_SHOTS_REMOVED",
                "completed_at": completed_at
            }).eq("id", job_id).execute()

            send_telegram_message(chat_id, "❌ رندر ناموفق بود:\nPLAN_ALL_SHOTS_REMOVED")
            return False

        from agents.editing.orchestrator import EditOrchestrator
        orchestrator = EditOrchestrator()
        result = orchestrator.render_content(
            custom_id=content_id,
            hook_text=plan.get("hook", ""),
            actor="render_worker",
            video_segments=video_segments if video_segments else None,
            mute_original=plan.get("mute_original", True),
            plan_sfx=plan.get("sfx") or None,
            plan_music=plan.get("music"),
        )

        mgr = RenderJobManager()
        if result.get("ok"):
            mgr.mark_completed(job_id, result.get("output_key", ""))
            send_telegram_message(chat_id,
                f"✅ رندر تمام شد!\n"
                f"شناسه: {content_id}\n"
                f"فایل: {result.get('output_key', 'در Supabase ذخیره شد')}"
            )
            logger.info(f"Job {job_id} completed successfully")
            return True
        else:
            mgr.mark_failed(job_id, result.get("error", "unknown"))
            send_telegram_message(chat_id,
                f"❌ رندر ناموفق بود:\n{result.get('error', 'خطای نامشخص')}"
            )
            logger.error(f"Job {job_id} failed: {result.get('error')}")
            return False

    except Exception as exc:
        logger.exception(f"Job {job_id} crashed")
        RenderJobManager().mark_failed(job_id, str(exc))
        send_telegram_message(chat_id,
            f"❌ خطای سیستمی در رندر:\n{type(exc).__name__}: {str(exc)[:200]}"
        )
        return False


def main():
    mgr = RenderJobManager()
    job = mgr.get_next_queued_job()
    if not job:
        logger.info("No queued render jobs found.")
        return

    success = process_job(job)
    if not success:
        logger.error("Render worker job execution failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
