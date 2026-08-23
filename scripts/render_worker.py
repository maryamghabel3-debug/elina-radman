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


def send_telegram_video(chat_id, video_url, caption=None):
    token = os.environ.get("STUDIO_BOT_TOKEN")
    if not token or not chat_id:
        logger.warning("Cannot send Telegram video: missing token or chat_id")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendVideo"
        payload = {
            "chat_id": chat_id,
            "video": video_url,
        }
        if caption:
            payload["caption"] = caption
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as exc:
        logger.warning(f"Telegram sendVideo failed: {exc}")
        return False


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
        n_shots = len(media_keys)

        # Validate every shot index is within range 1..len(media_keys)
        for shot in plan.get("shots", []):
            idx_1based = shot.get("index", 1)
            if idx_1based < 1 or idx_1based > n_shots:
                mgr = RenderJobManager()
                import datetime
                completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                db.client.table("render_jobs").update({
                    "status": "FAILED",
                    "error_message": f"SHOT_INDEX_OUT_OF_RANGE: shot {idx_1based} requested but bundle has {n_shots} shots",
                    "completed_at": completed_at
                }).eq("id", job_id).execute()

                send_telegram_message(chat_id, f"❌ رندر ناموفق بود:\nSHOT_INDEX_OUT_OF_RANGE: shot {idx_1based} requested but bundle has {n_shots} shots")
                return False

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
                seg_dict = {
                    "key": key,
                    "start_sec": shot.get("start", 0.0),
                    "end_sec": shot.get("end"),
                }
                if "transition_out" in shot:
                    seg_dict["transition_out"] = shot["transition_out"]
                if "freeze_tail_sec" in shot:
                    seg_dict["freeze_tail_sec"] = shot["freeze_tail_sec"]
                if "transform" in shot:
                    seg_dict["transform"] = shot["transform"]
                video_segments.append(seg_dict)

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
            job_id=job_id,
        )

        mgr = RenderJobManager()
        if result.get("ok"):
            output_key = result.get("output_key", "")
            mgr.mark_completed(job_id, output_key)

            # Generate short-lived signed URL
            signed_url = ""
            try:
                from agents.storage.supabase_storage import ElinaStorage
                storage = ElinaStorage()
                signed_url = storage.create_signed_url(output_key, 3600)
            except Exception as e:
                logger.warning(f"Failed to generate signed URL for notification: {e}")

            # Prepare text message
            msg = (
                f"✅ رندر تمام شد!\n"
                f"شناسه: {content_id}\n"
                f"فایل: {output_key}"
            )
            if signed_url:
                msg += f"\n\n🔗 لینک دانلود موقت (معتبر برای ۱ ساعت):\n{signed_url}"

            send_telegram_message(chat_id, msg)

            # If not in testing mode, send playable video file via sendVideo
            if signed_url and os.environ.get("ELINA_TEST_ALLOW_MOCKS") != "true":
                send_telegram_video(chat_id, signed_url, caption=f"🎬 ویدیو رندر شده {content_id}")

            logger.info(f"Job {job_id} completed successfully")
            return True
        else:
            err_msg = result.get("error", "unknown")
            mgr.mark_failed(job_id, err_msg)
            send_telegram_message(chat_id,
                f"❌ رندر ناموفق بود:\n{err_msg}"
            )
            logger.error(f"Job {job_id} failed: {err_msg}")

            # Check if this error is a terminal expected error
            is_terminal = (
                "INVALID_SOURCE_ASSET_PLACEHOLDER" in err_msg
                or "TARGET_CONTENT_NOT_FOUND" in err_msg
                or "SUPERSEDED" in err_msg
                or "SFX_PROVIDER_NOT_CONFIGURED" in err_msg
                or "SFX_FETCH_FAILED" in err_msg
                or "SFX_INVALID_PLAN_ENTRY" in err_msg
                or "MUSIC_PROVIDER_NOT_CONFIGURED" in err_msg
                or "SHOT_INDEX_OUT_OF_RANGE" in err_msg
                or "PLAN_ALL_SHOTS_REMOVED" in err_msg
                or "SFX_ANCHOR_OUT_OF_RANGE" in err_msg
                or "SFX_AUTH_FAILED" in err_msg
                or "SFX_SEARCH_REQUEST_INVALID" in err_msg
            )
            if is_terminal:
                return False
            else:
                raise RuntimeError(f"Unexpected rendering error: {err_msg}")

    except Exception as exc:
        logger.exception(f"Job {job_id} crashed")
        try:
            RenderJobManager().mark_failed(job_id, str(exc))
        except Exception as db_exc:
            logger.error(f"Failed to mark job as failed: {db_exc}")
        try:
            send_telegram_message(chat_id,
                f"❌ خطای سیستمی در رندر:\n{type(exc).__name__}: {str(exc)[:200]}"
            )
        except Exception:
            pass
        raise exc


def main():
    mgr = RenderJobManager()
    job = mgr.get_next_queued_job()
    if not job:
        logger.info("No queued render jobs found.")
        return

    try:
        success = process_job(job)
        if not success:
            logger.info("Job failed with terminal/expected error (exit 0)")
            sys.exit(0)
    except Exception as exc:
        logger.exception("Render worker job execution failed with unexpected infrastructure error (exit 1)")
        sys.exit(1)


if __name__ == "__main__":
    main()
