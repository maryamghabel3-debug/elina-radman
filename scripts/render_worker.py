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


def process_job(job):
    job_id = job["id"]
    content_id = job["plan_data"].get("target_id", job["content_id"])
    plan = job["plan_data"]
    chat_id = job.get("owner_chat_id")

    logger.info(f"Processing render job {job_id} for {content_id}")

    try:
        from agents.editing.orchestrator import EditOrchestrator

        clip_timings = []
        for shot in plan.get("shots", []):
            clip_timings.append({
                "start_sec": shot.get("start", 0),
                "end_sec": shot.get("end"),
            })

        orchestrator = EditOrchestrator()
        result = orchestrator.render_content(
            custom_id=content_id,
            hook_text=plan.get("hook", ""),
            actor="render_worker",
            clip_timings=clip_timings if clip_timings else None,
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
        else:
            mgr.mark_failed(job_id, result.get("error", "unknown"))
            send_telegram_message(chat_id,
                f"❌ رندر ناموفق بود:\n{result.get('error', 'خطای نامشخص')}"
            )
            logger.error(f"Job {job_id} failed: {result.get('error')}")

    except Exception as exc:
        logger.exception(f"Job {job_id} crashed")
        RenderJobManager().mark_failed(job_id, str(exc))
        send_telegram_message(chat_id,
            f"❌ خطای سیستمی در رندر:\n{type(exc).__name__}: {str(exc)[:200]}"
        )


def main():
    mgr = RenderJobManager()
    job = mgr.get_next_queued_job()
    if not job:
        logger.info("No queued render jobs found.")
        return

    process_job(job)


if __name__ == "__main__":
    main()
