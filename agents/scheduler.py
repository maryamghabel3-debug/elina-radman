import os
import logging
from datetime import datetime, timezone

from agents.db.supabase_client import ElinaDB
from agents.storage.supabase_storage import ElinaStorage
from agents.publishers.instagram_graph import InstagramGraphPublisher

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
SIGNED_URL_TTL_SECONDS = 3600


class PublishScheduler:
    """
    Reads APPROVED items due for publishing from Supabase,
    creates short-lived signed URLs, publishes via Instagram Graph API,
    and updates statuses. Fail-safe: content is never lost.
    """

    def __init__(self, db=None, storage=None, publisher=None):
        self.db = db or ElinaDB()
        self.storage = storage or ElinaStorage()
        self.publisher = publisher or InstagramGraphPublisher()

    def run_once(self) -> dict:
        now_iso = datetime.now(timezone.utc).isoformat()
        due_items = self.db.get_due_items(now_iso)
        summary = {"checked": len(due_items), "published": 0, "failed": 0, "retry": 0}

        for item in due_items:
            result = self._process_item(item)
            summary[result] += 1

        return summary

    def _process_item(self, item: dict) -> str:
        item_id = item["id"]
        custom_id = item.get("custom_id", item_id)
        content_type = item.get("content_type", "reel")
        caption = self._build_caption(item)
        media_keys = item.get("media_keys") or []

        if not media_keys:
            self._fail(item, "NO_MEDIA", "Item has no media_keys", retryable=False)
            return "failed"

        self.db.update_status(item_id, "PUBLISHING")
        self.db.log_event(item_id, "publishing_started", "APPROVED", "PUBLISHING", "scheduler")

        try:
            if content_type == "reel":
                url = self.storage.create_signed_url(media_keys[0], SIGNED_URL_TTL_SECONDS)
                result = self.publisher.publish_reel(url, caption)
            elif content_type == "carousel":
                urls = [self.storage.create_signed_url(k, SIGNED_URL_TTL_SECONDS) for k in media_keys]
                result = self.publisher.publish_carousel(urls, caption)
            else:
                url = self.storage.create_signed_url(media_keys[0], SIGNED_URL_TTL_SECONDS)
                result = self.publisher.publish_image(url, caption)
        except Exception as exc:
            self._fail(item, "EXCEPTION", str(exc), retryable=True)
            return "retry"

        if result.success:
            self.db.update_status(item_id, "PUBLISHED", {
                "platform_media_id": result.media_id,
                "published_url": result.permalink,
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
            self.db.log_event(item_id, "published", "PUBLISHING", "PUBLISHED", "scheduler", f"media_id={result.media_id}")
            logger.info("Published %s -> %s", custom_id, result.media_id)
            return "published"

        if result.retryable:
            self._retry(item, result.error_code, result.error_message)
            return "retry"

        self._fail(item, result.error_code, result.error_message, retryable=False)
        return "failed"

    def _build_caption(self, item: dict) -> str:
        caption = item.get("caption_fa") or ""
        hashtags = item.get("hashtags") or []
        if hashtags:
            caption = caption.rstrip() + "\n\n" + " ".join(hashtags)
        return caption

    def _retry(self, item: dict, code, message):
        attempts = (item.get("attempts") or 0) + 1
        if attempts >= MAX_ATTEMPTS:
            self._fail(item, code, f"Max attempts reached: {message}", retryable=False)
            return
        self.db.update_status(item["id"], "RETRY_PENDING", {
            "attempts": attempts,
            "last_error": f"{code}: {message}",
        })
        self.db.log_event(item["id"], "retry_scheduled", "PUBLISHING", "RETRY_PENDING", "scheduler", f"{code}: {message}")

    def _fail(self, item: dict, code, message, retryable: bool):
        self.db.update_status(item["id"], "FAILED", {
            "last_error": f"{code}: {message}",
        })
        self.db.log_event(item["id"], "publish_failed", item.get("status", ""), "FAILED", "scheduler", f"{code}: {message}")
        logger.error("Publish failed %s: %s %s", item.get("custom_id"), code, message)


def main():
    import sys
    from pathlib import Path
    from dotenv import load_dotenv

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    load_dotenv(project_root / ".env")

    logging.basicConfig(level=logging.INFO)
    scheduler = PublishScheduler()
    summary = scheduler.run_once()
    logger.info("Scheduler summary: %s", summary)


if __name__ == "__main__":
    main()
