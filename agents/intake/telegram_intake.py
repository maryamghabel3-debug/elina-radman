import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from agents.db.supabase_client import ElinaDB
from agents.storage.supabase_storage import ElinaStorage

logger = logging.getLogger(__name__)


class IntakeProcessor:
    """Processes raw media from Telegram and stores it in Supabase."""

    def __init__(self):
        self.db = ElinaDB()
        self.storage = ElinaStorage()

    def process_incoming_media(
        self,
        local_file_path: str,
        file_ext: str,
        caption: Optional[str],
        telegram_message_id: str,
        sender_name: str
    ) -> Dict[str, Any]:
        internal_id = str(uuid.uuid4())
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        short_id = internal_id[:8]
        custom_id = f"ELN-RAW-{date_str}-{short_id}"

        # 1. Upload to Storage
        storage_path = f"intake/{date_str}/{custom_id}{file_ext}"
        self.storage.upload_file(local_file_path, storage_path)

        # 2. Determine type
        content_type = "single_post"
        if file_ext.lower() in [".mp4", ".mov", ".webm"]:
            content_type = "reel"

        # 3. Save to DB
        db_payload = {
            "id": internal_id,
            "custom_id": custom_id,
            "content_type": content_type,
            "caption_fa": caption or "",
            "status": "RAW_RECEIVED",
            "media_keys": [storage_path],
            "source": "telegram_intake",
            "telegram_message_id": str(telegram_message_id)
        }
        self.db.insert_content(db_payload)

        # 4. Log Event
        self.db.log_event(
            content_id=internal_id,
            event_type="intake_received",
            from_status=None,
            to_status="RAW_RECEIVED",
            actor=sender_name,
            detail=f"Received via Telegram. Saved to {storage_path}"
        )

        return {
            "custom_id": custom_id,
            "storage_path": storage_path,
            "status": "RAW_RECEIVED"
        }
