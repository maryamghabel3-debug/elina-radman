import os
import sys
import json
import logging
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.rendering.job_manager import RenderJobManager, is_terminal_error_message
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
                if "brightness_keyframes" in shot:
                    seg_dict["brightness_keyframes"] = shot["brightness_keyframes"]
                if "visual_adjustments" in shot:
                    seg_dict["visual_adjustments"] = shot["visual_adjustments"]
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
            plan_voice=plan.get("voice"),
            plan_subtitles=plan.get("subtitles"),
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
                or "VOICE_TEXT_EMPTY" in err_msg
                or "VOICE_TEXT_TOO_LONG" in err_msg
                or "VOICE_UNSUPPORTED" in err_msg
                or "VOICE_RATE_INVALID" in err_msg
                or "VOICE_INVALID_PLAN_ENTRY" in err_msg
                or "SUBTITLE_CONFIG_INVALID" in err_msg
                or "SUBTITLE_FONT_NOT_FOUND" in err_msg
                or "VOICE_SUBTITLE_SYNC_CONFIG_INVALID" in err_msg
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


class RenderJobTimeout(Exception):
    """Raised when a job exceeds the per-job timeout (RENDER_JOB_TIMEOUT_SECONDS)."""


def run_with_timeout(func: Callable[[], Any], timeout_seconds: float) -> Any:
    """
    Run func() with a hard timeout, test-friendly (thread-based, works on any
    platform; unlike signal.alarm it is trivial to mock and does not depend on
    the main thread).

    On timeout, raises RenderJobTimeout. The worker thread is a daemon thread:
    pure Python cannot force-kill it, but it cannot block the run summary or
    the next job, and the process exits cleanly at the end of the run.
    """
    box: Dict[str, Any] = {}

    def target():
        try:
            box["value"] = func()
        except BaseException as exc:  # re-raised on the main thread
            box["error"] = exc

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        raise RenderJobTimeout(f"job exceeded {timeout_seconds}s timeout")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def run_render_run(
    mgr: RenderJobManager,
    max_jobs: int = 5,
    max_run_seconds: float = 1500,
    job_timeout_seconds: float = 900,
    stale_minutes: int = 30,
    clock: Optional[Callable[[], float]] = None,
    process: Callable[[dict], bool] = None,
) -> Dict[str, Any]:
    """
    One worker run: stale IN_PROGRESS recovery, then a claim/process loop.

    Stops when the queue is empty, max_jobs is reached, or the run time
    budget (max_run_seconds) is exceeded. Returns a run summary dict; the
    caller maps it to the exit-code policy (all processed -> 0, any
    infrastructure error -> 1).
    """
    clock = clock or time.monotonic
    process = process or process_job
    run_start = clock()
    summary: Dict[str, Any] = {
        "claimed": 0, "completed": 0, "failed_terminal": 0,
        "failed_retryable": 0, "timeouts": 0,
    }
    infra_error = False

    # --- Stale IN_PROGRESS recovery (guarded conditional updates) ---
    try:
        stale = mgr.recover_stale_jobs(stale_minutes)
    except Exception as exc:
        logger.exception("Stale job recovery failed (infrastructure error)")
        return {**summary, "infra_error": True, "recovery_error": str(exc)}
    for job in stale.get("abandoned", []):
        chat_id = job.get("owner_chat_id")
        if chat_id:
            send_telegram_message(
                chat_id,
                f"⚠️ رندر {job.get('content_id')} به دلیل قطعی رانر ناتمام ماند و دیگر تکرار نمی‌شود:\n"
                "RENDER_STALE_ABANDONED",
            )
    logger.info(
        "Stale recovery: %d recovered to QUEUED, %d abandoned as FAILED",
        len(stale.get("recovered", [])), len(stale.get("abandoned", [])),
    )

    # --- Claim/process loop ---
    while summary["claimed"] < int(max_jobs):
        if clock() - run_start >= float(max_run_seconds):
            logger.warning(
                "Run time budget (%ss) reached; stopping before claiming more jobs",
                max_run_seconds,
            )
            break
        try:
            job = mgr.get_next_queued_job()
        except Exception as exc:
            logger.exception("Job claim failed (infrastructure error)")
            infra_error = True
            break
        if job is None:
            break
        summary["claimed"] += 1
        try:
            success = run_with_timeout(lambda: process(job), job_timeout_seconds)
            if success:
                summary["completed"] += 1
            else:
                # Expected terminal failure: process_job already marked it
                # FAILED and sent the Persian notification.
                summary["failed_terminal"] += 1
        except RenderJobTimeout:
            logger.error("Job %s timed out after %ss", job.get("id"), job_timeout_seconds)
            # Retryable while attempts remain (mark_failed decides).
            try:
                mgr.mark_failed(
                    job["id"],
                    "RENDER_TIMEOUT: job exceeded RENDER_JOB_TIMEOUT_SECONDS",
                )
            except Exception as exc:
                logger.error("Failed to mark timed-out job %s: %s", job.get("id"), exc)
            if job.get("owner_chat_id"):
                send_telegram_message(
                    job["owner_chat_id"],
                    "❌ رندر ناموفق بود:\nRENDER_TIMEOUT (زمان مجاز رندر تمام شد)",
                )
            summary["timeouts"] += 1
        except Exception as exc:
            # Unexpected infrastructure/content error: process_job already
            # marked the job (terminal vs requeued) and notified the owner
            # before re-raising.
            logger.exception("Job %s failed with an unexpected error", job.get("id"))
            infra_error = True
            if is_terminal_error_message(str(exc)):
                summary["failed_terminal"] += 1
            else:
                summary["failed_retryable"] += 1

    logger.info(
        "Run summary: claimed=%d completed=%d failed_terminal=%d "
        "failed_retryable=%d timeouts=%d infra_error=%s",
        summary["claimed"], summary["completed"], summary["failed_terminal"],
        summary["failed_retryable"], summary["timeouts"], infra_error,
    )
    return {**summary, "infra_error": infra_error}


def main():
    max_jobs = int(os.environ.get("RENDER_WORKER_MAX_JOBS_PER_RUN", "5"))
    max_run_seconds = float(os.environ.get("RENDER_WORKER_MAX_RUN_SECONDS", "1500"))
    job_timeout_seconds = float(os.environ.get("RENDER_JOB_TIMEOUT_SECONDS", "900"))
    stale_minutes = int(os.environ.get("RENDER_STALE_JOB_MINUTES", "30"))

    mgr = RenderJobManager()
    summary = run_render_run(
        mgr,
        max_jobs=max_jobs,
        max_run_seconds=max_run_seconds,
        job_timeout_seconds=job_timeout_seconds,
        stale_minutes=stale_minutes,
    )
    if not summary["claimed"] and not summary["infra_error"]:
        logger.info("No queued render jobs found.")
        return
    # Exit-code policy (preserved per run):
    #   0 = all claimed jobs processed (including expected terminal failures)
    #   1 = any infrastructure error (DB/network/unexpected exception)
    sys.exit(1 if summary["infra_error"] else 0)


if __name__ == "__main__":
    main()
