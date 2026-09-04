import os
import logging
import datetime
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class ElinaDB:
    """Adapter for Supabase Database operations."""

    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SECRET_KEY")

        if not url or not key:
            raise ValueError(
                "Supabase credentials (SUPABASE_URL, SUPABASE_SECRET_KEY) "
                "are missing from environment."
            )

        self.client: Client = create_client(url, key)

    def insert_content(self, data: dict) -> list:
        """Insert a new content item into the queue."""
        response = self.client.table("content_items").insert(data).execute()
        return response.data

    def get_content_by_id(self, item_id: str) -> dict | None:
        """Fetch a single content item by UUID."""
        response = (
            self.client.table("content_items")
            .select("*")
            .eq("id", item_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def get_content_by_custom_id(self, custom_id: str) -> dict | None:
        """Fetch a single content item by custom_id (e.g., ELN-RAW-...)."""
        response = (
            self.client.table("content_items")
            .select("*")
            .eq("custom_id", custom_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def get_items_by_status(self, status: str, limit: int = 20) -> list:
        """Fetch content items with a given status."""
        response = (
            self.client.table("content_items")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return response.data

    def get_due_items(self, now_iso: str, limit: int = 1):
        """Fetch due items for publishing: SCHEDULED or RETRY_PENDING, with approval metadata."""
        response = (
            self.client.table("content_items")
            .select("*")
            .in_("status", ["SCHEDULED", "RETRY_PENDING"])
            .not_.is_("scheduled_for", "null")
            .lte("scheduled_for", now_iso)
            .not_.is_("approved_at", "null")
            .not_.is_("approved_by", "null")
            .order("scheduled_for", desc=False)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def claim_for_publishing(self, item_id: str, expected_status: str) -> bool:
        """Atomically claim a content item for publishing to prevent double publish."""
        response = (
            self.client.table("content_items")
            .update({"status": "PUBLISHING"})
            .eq("id", item_id)
            .eq("status", expected_status)
            .execute()
        )
        # True only if exactly one record was updated
        return bool(response.data and len(response.data) == 1)

    def update_status(self, item_id: str, new_status: str, extra: dict | None = None) -> list:
        """Update the status (and optional extra fields) of a content item."""
        payload = {"status": new_status}
        if extra:
            payload.update(extra)
        response = (
            self.client.table("content_items")
            .update(payload)
            .eq("id", item_id)
            .execute()
        )
        return response.data

    def log_event(
        self,
        content_id: str,
        event_type: str,
        from_status: str = "",
        to_status: str = "",
        actor: str = "system",
        detail: str = "",
    ) -> list:
        """Log an event in the audit trail."""
        data = {
            "content_id": content_id,
            "event_type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "actor": actor,
            "detail": detail,
        }
        response = self.client.table("content_events").insert(data).execute()
        return response.data

    # ------------------------------------------------------------------
    # Carousel drafts (M29): one durable draft row per owner chat
    # ------------------------------------------------------------------

    def upsert_carousel_draft(self, owner_chat_id: int, draft: dict) -> list:
        """Insert or update the owner's carousel draft row.

        `draft` is the full draft dict; 'title'/'custom_id'/'status' are
        promoted to top-level columns (used for listing), the rest is
        stored in the draft JSONB column.
        """
        payload = {
            "owner_chat_id": owner_chat_id,
            "title": draft.get("title") or "",
            "custom_id": draft.get("custom_id"),
            "status": draft.get("status") or "draft",
            "draft": {
                k: v for k, v in draft.items()
                if k not in ("title", "custom_id", "status")
            },
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        response = (
            self.client.table("carousel_drafts")
            .upsert(payload, on_conflict="owner_chat_id")
            .execute()
        )
        return response.data

    def get_carousel_draft(self, owner_chat_id: int) -> dict | None:
        """Fetch the owner's carousel draft row (or None)."""
        response = (
            self.client.table("carousel_drafts")
            .select("*")
            .eq("owner_chat_id", owner_chat_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def list_carousel_drafts(self, limit: int = 10) -> list:
        """Recent carousel drafts across owners (newest first)."""
        response = (
            self.client.table("carousel_drafts")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data

    def delete_carousel_draft(self, owner_chat_id: int) -> list:
        """Delete the owner's carousel draft row (cancel)."""
        response = (
            self.client.table("carousel_drafts")
            .delete()
            .eq("owner_chat_id", owner_chat_id)
            .execute()
        )
        return response.data
