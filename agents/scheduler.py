import os
import logging
from datetime import datetime, timezone, timedelta

from agents.db.supabase_client import ElinaDB
from agents.storage.supabase_storage import ElinaStorage
from agents.publishers.base_publisher import PublishResult

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
SIGNED_URL_TTL_SECONDS = 3600
MAX_ITEMS_PER_RUN = int(os.environ.get("PUBLISH_MAX_ITEMS_PER_RUN", "1"))
PUBLISH_RETRY_DELAY_MINUTES = int(os.environ.get("PUBLISH_RETRY_DELAY_MINUTES", "30"))


class PublishScheduler:
    """
    Reads SCHEDULED (and RETRY_PENDING) items due for publishing from Supabase,
    creates short-lived signed URLs, publishes via Instagram Graph API,
    and updates statuses. Fail-safe: content is never lost.
    Only SCHEDULED status with approval metadata is publishable.
    Includes atomic claim to prevent double publish and live kill switch.
    """

    def __init__(self, db=None, storage=None, publisher=None):
        self.db = db or ElinaDB()
        self.storage = storage or ElinaStorage()
        # Lazy publisher: do not create unless needed and live enabled
        self._injected_publisher = publisher
        self._publisher = None

    def _is_live_enabled(self) -> bool:
        val = os.environ.get("PUBLISH_LIVE_ENABLED", "false")
        return str(val).lower() == "true"

    def _get_publisher(self):
        """Lazy initialization of InstagramGraphPublisher only when needed."""
        if self._injected_publisher:
            return self._injected_publisher
        if self._publisher is None:
            # Only create when live enabled
            if not self._is_live_enabled():
                return None
            # Import here to avoid requiring env vars when queue empty
            from agents.publishers.instagram_graph import InstagramGraphPublisher
            self._publisher = InstagramGraphPublisher()
        return self._publisher

    def run_once(self) -> dict:
        # Kill switch check before any heavy initialization
        if not self._is_live_enabled():
            print("Live publishing is disabled.")
            return {"checked": 0, "published": 0, "failed": 0, "retry": 0, "skipped": 0}

        now_iso = datetime.now(timezone.utc).isoformat()
        due_items = self.db.get_due_items(now_iso, limit=MAX_ITEMS_PER_RUN)
        summary = {"checked": len(due_items), "published": 0, "failed": 0, "retry": 0, "skipped": 0}

        if not due_items:
            # Queue empty, no need for publisher
            return summary

        for item in due_items:
            # Guard: only SCHEDULED or RETRY_PENDING with approval metadata should be processed
            # get_due_items already filters SCHEDULED/RETRY_PENDING, but double-check status
            if item.get("status") not in ("SCHEDULED", "RETRY_PENDING"):
                summary["skipped"] += 1
                continue
            if not item.get("approved_at") or not item.get("approved_by") or not item.get("scheduled_for"):
                self.db.log_event(item["id"], "skipped_missing_approval_metadata", item.get("status", ""), item.get("status", ""), "scheduler", "Missing approved_at/approved_by/scheduled_for")
                summary["skipped"] += 1
                continue
            result = self._process_item(item)
            summary[result] += 1

        return summary

    def _process_item(self, item: dict) -> str:
        item_id = item["id"]
        custom_id = item.get("custom_id", item_id)
        content_type = item.get("content_type", "reel")
        caption = self._build_caption(item)
        expected_status = item.get("status", "SCHEDULED")

        # Prioritize edited_media_key over raw media_keys
        edited_key = item.get("edited_media_key")
        media_keys = []
        if edited_key is not None:
            edited_key_str = str(edited_key).strip()
            if edited_key_str:
                media_keys = [edited_key_str]
                logger.info("Using edited_media_key for publishing content item %s: %s", custom_id, edited_key_str)
            else:
                logger.warning("edited_media_key exists but is empty/whitespace for item %s. Falling back to media_keys.", custom_id)
                media_keys = item.get("media_keys") or []
        else:
            media_keys = item.get("media_keys") or []

        # Story handling: manual publish required, not FAILED
        if content_type == "story":
            self.db.update_status(item_id, "MANUAL_PUBLISH_REQUIRED", {
                "last_error": "MANUAL_STORY_REQUIRED: Story must be published manually"
            })
            self.db.log_event(item_id, "manual_story_required", item.get("status", ""), "MANUAL_PUBLISH_REQUIRED", "scheduler", "Story type requires manual publish")
            logger.info("Story %s requires manual publish", custom_id)
            return "skipped"

        if not media_keys:
            self._fail(item, "NO_MEDIA", "Item has no media_keys")
            return "failed"

        # Atomic claim to prevent double publish
        claimed = self.db.claim_for_publishing(item_id, expected_status)
        if not claimed:
            self.db.log_event(item_id, "publishing_claim_skipped", item.get("status", ""), item.get("status", ""), "scheduler", "Another worker claimed the item")
            return "skipped"

        # Now we have claimed, safe to create signed URLs and publisher
        publisher = self._get_publisher()
        if publisher is None:
            # Should not happen because we checked live enabled earlier, but safety
            print("Live publishing is disabled.")
            # Revert claim? For safety, set back to SCHEDULED
            self.db.update_status(item_id, expected_status)
            return "skipped"

        try:
            if content_type == "reel":
                url = self.storage.create_signed_url(media_keys[0], SIGNED_URL_TTL_SECONDS)
                result = publisher.publish_reel(url, caption)
            elif content_type == "carousel":
                urls = [self.storage.create_signed_url(k, SIGNED_URL_TTL_SECONDS) for k in media_keys]
                result = publisher.publish_carousel(urls, caption)
            else:
                url = self.storage.create_signed_url(media_keys[0], SIGNED_URL_TTL_SECONDS)
                result = publisher.publish_image(url, caption)
        except Exception as exc:
            # Network or runtime exception -> treat as retryable
            return self._retry(item, "EXCEPTION", str(exc))

        if result.success:
            self.db.update_status(item_id, "PUBLISHED", {
                "platform_media_id": result.media_id,
                "published_url": result.permalink,
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
            self.db.log_event(item_id, "published", "PUBLISHING", "PUBLISHED", "scheduler", f"media_id={result.media_id}")
            logger.info("Published %s -> %s", custom_id, result.media_id)
            return "published"

        # Handle manual story requirement from publisher
        if result.error_code == "MANUAL_STORY_REQUIRED":
            self.db.update_status(item_id, "MANUAL_PUBLISH_REQUIRED", {
                "last_error": result.error_message,
            })
            self.db.log_event(item_id, "manual_publish_required", "PUBLISHING", "MANUAL_PUBLISH_REQUIRED", "scheduler", result.error_message)
            return "skipped"

        if result.retryable:
            return self._retry(item, result.error_code, result.error_message)

        self._fail(item, result.error_code, result.error_message)
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
            self._fail(item, code, f"Max attempts reached: {message}")
            return "failed"
        # Schedule next retry after delay
        now = datetime.now(timezone.utc)
        next_scheduled = now + timedelta(minutes=PUBLISH_RETRY_DELAY_MINUTES)
        self.db.update_status(item["id"], "RETRY_PENDING", {
            "attempts": attempts,
            "last_error": f"{code}: {message}",
            "scheduled_for": next_scheduled.isoformat(),
        })
        self.db.log_event(item["id"], "retry_scheduled", "PUBLISHING", "RETRY_PENDING", "scheduler", f"{code}: {message}")
        return "retry"

    def _fail(self, item: dict, code, message):
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

    # Live kill switch check before any publisher initialization
    live_enabled = os.environ.get("PUBLISH_LIVE_ENABLED", "false")
    if str(live_enabled).lower() != "true":
        print("Live publishing is disabled.")
        sys.exit(0)

    scheduler = PublishScheduler()
    summary = scheduler.run_once()
    logging.getLogger(__name__).info("Scheduler summary: %s", summary)


if __name__ == "__main__":
    main()
