import os
import re
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from agents.db.supabase_client import ElinaDB

logger = logging.getLogger(__name__)


class VideoBundleManager:
    """
    Manages grouping multiple video clips into ordered editing bundles.
    """

    def __init__(self, db: Optional[ElinaDB] = None):
        self.db = db or ElinaDB()

    def create_bundle(
        self,
        bundle_name: str,
        source_custom_ids: List[str],
        actor: str,
    ) -> Dict[str, Any]:
        # 1. Validate bundle_name
        if not bundle_name or len(bundle_name) > 80:
            return {"ok": False, "error": "Bundle name must be between 1 and 80 characters."}

        # Allow letters (English/Persian), numbers, spaces, dash, underscore
        if not re.match(r"^[a-zA-Z0-9\s\-_\u0600-\u06FF]+$", bundle_name):
            return {"ok": False, "error": "Bundle name contains invalid characters."}

        # 2. Require at least two source IDs
        if not source_custom_ids or len(source_custom_ids) < 2:
            return {"ok": False, "error": "At least two source IDs are required."}

        # 3. Validate every source custom ID
        aggregated_keys = []
        for cid in source_custom_ids:
            item = self.db.get_content_by_custom_id(cid)
            if not item:
                return {"ok": False, "error": f"Content item '{cid}' does not exist."}

            keys = item.get("media_keys") or []
            if not keys:
                return {"ok": False, "error": f"Content item '{cid}' has no media keys."}

            if item.get("content_type") != "reel":
                return {"ok": False, "error": f"Content item '{cid}' is not a video/reel."}

            # Aggregate keys in the exact order of source custom IDs
            aggregated_keys.extend(keys)

        # 4. Generate bundle metadata
        internal_id = str(uuid.uuid4())
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        short_id = internal_id[:8]
        custom_id = f"ELN-BUNDLE-{date_str}-{short_id}"

        # Ensure it produces only one ELN-BUNDLE- prefix
        if custom_id.startswith("ELN-BUNDLE-ELN-BUNDLE-"):
            custom_id = custom_id.replace("ELN-BUNDLE-ELN-BUNDLE-", "ELN-BUNDLE-")

        # 5. Build editor notes
        editor_notes_dict = {
            "bundle_name": bundle_name,
            "source_custom_ids": source_custom_ids,
            "clip_count": len(source_custom_ids),
            "created_by": actor
        }
        editor_notes_str = json.dumps(editor_notes_dict, ensure_ascii=False)

        # 6. Save new parent item to DB
        db_payload = {
            "id": internal_id,
            "custom_id": custom_id,
            "content_type": "reel",
            "topic": bundle_name,
            "status": "NEEDS_EDIT",
            "edit_status": "pending",
            "source": "telegram_studio_bundle",
            "media_keys": aggregated_keys,
            "editor_notes": editor_notes_str
        }
        self.db.insert_content(db_payload)

        # 7. Log event
        self.db.log_event(
            content_id=internal_id,
            event_type="bundle_created",
            from_status=None,
            to_status="NEEDS_EDIT",
            actor=actor,
            detail=f"Created video bundle with {len(source_custom_ids)} clips."
        )

        return {
            "ok": True,
            "custom_id": custom_id,
            "bundle_name": bundle_name,
            "clip_count": len(source_custom_ids),
            "status": "NEEDS_EDIT"
        }
