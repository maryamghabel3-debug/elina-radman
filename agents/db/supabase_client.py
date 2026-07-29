import os
import logging
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

    def get_due_items(self, now_iso: str, limit: int = 1):
        response = (
            self.client.table("content_items")
            .select("*")
            .eq("status", "SCHEDULED")
            .neq("scheduled_for", None)
            .lte("scheduled_for", now_iso)
            .neq("approved_at", None)
            .neq("approved_by", None)
            .order("scheduled_for", desc=False)
            .limit(limit)
            .execute()
        )
        return response.data or []
