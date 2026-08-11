import os
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1] if "__file__" in locals() else Path(".").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [HYGIENE] %(message)s")
logger = logging.getLogger("QueueHygiene")

from agents.db.supabase_client import ElinaDB


def main():
    db = ElinaDB()
    # 1. Fetch active render jobs (status in QUEUED, IN_PROGRESS)
    res_jobs = db.client.table("render_jobs").select("*").in_("status", ["QUEUED", "IN_PROGRESS"]).execute()
    jobs = res_jobs.data or []

    logger.info(f"Found {len(jobs)} active render jobs in queue.")

    for job in jobs:
        cid = job.get("content_id")
        # 2. Check content_item status
        item = db.get_content_by_custom_id(cid)
        if not item:
            logger.info(f"Cancelling job {job['id']}: content item '{cid}' does not exist.")
            db.client.table("render_jobs").update({
                "status": "FAILED",
                "error_message": "ORPHANED_JOB_CONTENT_NOT_ACTIVE"
            }).eq("id", job["id"]).execute()
            continue

        item_status = item.get("status")
        # If content item is in a terminal state
        if item_status not in ["NEEDS_EDIT", "EDIT_RENDERING", "RAW_RECEIVED", "NEEDS_REVIEW"]:
            logger.info(f"Cancelling job {job['id']}: content item '{cid}' is in terminal state '{item_status}'.")
            db.client.table("render_jobs").update({
                "status": "FAILED",
                "error_message": "ORPHANED_JOB_CONTENT_NOT_ACTIVE"
            }).eq("id", job["id"]).execute()

    logger.info("Queue hygiene check complete.")


if __name__ == "__main__":
    main()
