import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from agents.db.supabase_client import ElinaDB

logger = logging.getLogger(__name__)

PUBLISHING_SLOTS = {
    "prime_evening": {"start_hour": 20, "minute": 30},
    "afternoon": {"start_hour": 13, "minute": 30},
    "morning": {"start_hour": 9, "minute": 30},
    "night": {"start_hour": 21, "minute": 30},
}


class ApprovalManager:
    def __init__(self):
        self.db = ElinaDB()

    def get_pending_items(self) -> List[Dict[str, Any]]:
        response = (
            self.db.client.table("content_items")
            .select("id,custom_id,content_type,caption_fa,status,target_persona,topic,created_at")
            .in_("status", ["RAW_RECEIVED", "NEEDS_EDIT", "READY_FOR_REVIEW"])
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return response.data or []

    def promote_to_review(self, custom_id: str, actor: str) -> Dict[str, Any]:
        item = self.db.get_content_by_custom_id(custom_id)
        if not item:
            return {"ok": False, "error": f"Item not found: {custom_id}"}
        self.db.update_status(item["id"], "READY_FOR_REVIEW")
        self.db.log_event(item["id"], "promoted_to_review", item["status"], "READY_FOR_REVIEW", actor)
        return {"ok": True, "custom_id": custom_id, "new_status": "READY_FOR_REVIEW"}

    def approve_and_schedule(self, custom_id: str, slot_name: str, actor: str) -> Dict[str, Any]:
        item = self.db.get_content_by_custom_id(custom_id)
        if not item:
            return {"ok": False, "error": f"Item not found: {custom_id}"}
        slot = PUBLISHING_SLOTS.get(slot_name)
        if not slot:
            return {"ok": False, "error": f"Unknown slot: {slot_name}"}
        now = datetime.now(timezone.utc)
        scheduled = now.replace(hour=slot["start_hour"], minute=slot["minute"], second=0, microsecond=0)
        if scheduled <= now:
            scheduled += timedelta(days=1)
        self.db.update_status(item["id"], "APPROVED", {
            "scheduled_slot": slot_name,
            "scheduled_for": scheduled.isoformat(),
            "approved_by": actor,
            "approved_at": now.isoformat(),
        })
        self.db.log_event(item["id"], "approved_and_scheduled", item["status"], "APPROVED", actor, f"slot={slot_name}")
        return {"ok": True, "custom_id": custom_id, "new_status": "APPROVED", "scheduled_for": scheduled.isoformat(), "slot": slot_name}

    def reject_item(self, custom_id: str, reason: str, actor: str) -> Dict[str, Any]:
        item = self.db.get_content_by_custom_id(custom_id)
        if not item:
            return {"ok": False, "error": f"Item not found: {custom_id}"}
        self.db.update_status(item["id"], "REJECTED", {"rejection_reason": reason})
        self.db.log_event(item["id"], "rejected", item["status"], "REJECTED", actor, reason)
        return {"ok": True, "custom_id": custom_id, "new_status": "REJECTED"}

    def mark_needs_edit(self, custom_id: str, edit_task: str, actor: str) -> Dict[str, Any]:
        item = self.db.get_content_by_custom_id(custom_id)
        if not item:
            return {"ok": False, "error": f"Item not found: {custom_id}"}
        self.db.update_status(item["id"], "NEEDS_EDIT", {"edit_status": "pending", "editor_notes": edit_task})
        self.db.log_event(item["id"], "edit_requested", item["status"], "NEEDS_EDIT", actor, edit_task)
        return {"ok": True, "custom_id": custom_id, "new_status": "NEEDS_EDIT"}

    def mark_edit_done(self, custom_id: str, actor: str) -> Dict[str, Any]:
        item = self.db.get_content_by_custom_id(custom_id)
        if not item:
            return {"ok": False, "error": f"Item not found: {custom_id}"}
        self.db.update_status(item["id"], "READY_FOR_REVIEW", {"edit_status": "done"})
        self.db.log_event(item["id"], "edit_done", item["status"], "READY_FOR_REVIEW", actor)
        return {"ok": True, "custom_id": custom_id, "new_status": "READY_FOR_REVIEW"}
