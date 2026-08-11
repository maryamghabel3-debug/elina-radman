import os
import sys
import argparse
import logging
import datetime
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parents[1] if "__file__" in locals() else Path(".").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Note: standard logging setup is already done or can be initialized here
logging.basicConfig(level=logging.INFO, format="%(asctime)s [REPAIR] %(message)s")
logger = logging.getLogger("SupabaseRepair")

from agents.db.supabase_client import ElinaDB
from agents.studio.bundle_ids import normalize_bundle_custom_id
from agents.rendering.job_manager import RenderJobManager
from agents.editing.orchestrator import validate_video_asset

# Verify credentials exist
if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SECRET_KEY"):
    logger.error("CRITICAL: SUPABASE_URL or SUPABASE_SECRET_KEY is missing from environment.")
    sys.exit(1)


def run_diagnose(db: ElinaDB) -> Dict[str, Any]:
    logger.info("Running Supabase diagnosis...")
    try:
        # Fetch content_items
        res_items = db.client.table("content_items").select("id, custom_id, status, created_at, media_keys, content_type").execute()
        items = res_items.data or []

        # Fetch render_jobs
        res_jobs = db.client.table("render_jobs").select("id, content_id, status, plan_data, attempts, created_at, error_message, started_at").execute()
        jobs = res_jobs.data or []
    except Exception as exc:
        logger.error(f"API unreachable or unexpected database error: {exc}")
        sys.exit(1)

    all_item_custom_ids = {x.get("custom_id") for x in items}

    total_bundles = 0
    malformed_bundles = 0
    for x in items:
        cid = x.get("custom_id", "")
        if cid and "ELN-BUNDLE-" in cid:
            total_bundles += 1
            if "ELN-BUNDLE-ELN-BUNDLE-" in cid:
                malformed_bundles += 1

    active_jobs = 0
    malformed_jobs = 0
    orphan_jobs = 0
    canonical_matches = 0
    stale_jobs = 0

    now = datetime.datetime.now(datetime.timezone.utc)

    for job in jobs:
        status = job.get("status")
        if status in ["QUEUED", "IN_PROGRESS"]:
            active_jobs += 1

        cid = job.get("content_id", "")
        plan = job.get("plan_data", {}) or {}
        target_id = plan.get("target_id", "")

        # Check for malformed
        is_malformed = False
        if cid and "ELN-BUNDLE-ELN-BUNDLE-" in cid:
            is_malformed = True
        if target_id and "ELN-BUNDLE-ELN-BUNDLE-" in target_id:
            is_malformed = True
        if is_malformed:
            malformed_jobs += 1

        # Check for orphan
        canonical_cid = ""
        try:
            canonical_cid = normalize_bundle_custom_id(cid) if cid else ""
        except ValueError:
            pass

        if cid and cid not in all_item_custom_ids and canonical_cid not in all_item_custom_ids:
            orphan_jobs += 1

        # Check for canonical match
        if cid and cid != canonical_cid and canonical_cid in all_item_custom_ids:
            canonical_matches += 1

        # Check for stale IN_PROGRESS
        if status == "IN_PROGRESS" and job.get("started_at"):
            try:
                started_at = datetime.datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                if (now - started_at).total_seconds() > 3600:
                    stale_jobs += 1
            except Exception:
                pass

    summary = {
        "total_bundle_items": total_bundles,
        "malformed_duplicate_prefix_bundle_items": malformed_bundles,
        "total_active_render_jobs": active_jobs,
        "malformed_target_jobs": malformed_jobs,
        "orphan_jobs": orphan_jobs,
        "canonical_target_matches": canonical_matches,
        "stale_jobs_older_than_60m": stale_jobs
    }

    # Print sanitized summary report
    print("\n--- SANITIZED DIAGNOSTIC SUMMARY ---")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("------------------------------------\n")

    return summary


def run_repair(db: ElinaDB) -> Dict[str, Any]:
    logger.info("Running Supabase non-destructive repair...")

    # 1. Fetch tables
    try:
        res_items = db.client.table("content_items").select("id, custom_id, status, created_at, media_keys, content_type").execute()
        items = res_items.data or []

        res_jobs = db.client.table("render_jobs").select("id, content_id, status, plan_data, attempts, created_at, error_message, started_at").execute()
        jobs = res_jobs.data or []
    except Exception as exc:
        logger.error(f"Failed to fetch tables for repair: {exc}")
        sys.exit(1)

    all_item_custom_ids = {x.get("custom_id") for x in items}

    rows_repaired = 0
    jobs_requeued = 0
    conflicts_found = 0

    # A. Repair malformed content_items custom_id
    for item in items:
        cid = item.get("custom_id", "")
        if cid and "ELN-BUNDLE-ELN-BUNDLE-" in cid:
            canonical_cid = normalize_bundle_custom_id(cid)
            if canonical_cid not in all_item_custom_ids:
                # Safe to rename
                logger.info(f"Renaming content item {item['id']} from malformed '{cid}' to canonical '{canonical_cid}'")
                try:
                    db.client.table("content_items").update({"custom_id": canonical_cid}).eq("id", item["id"]).execute()
                    all_item_custom_ids.remove(cid)
                    all_item_custom_ids.add(canonical_cid)
                    rows_repaired += 1
                except Exception as e:
                    logger.error(f"Failed to rename content item {item['id']}: {e}")
                    sys.exit(1)
            else:
                logger.warning(f"BUNDLE_ID_CONFLICT: Canonical ID '{canonical_cid}' already exists. Cannot safely rename malformed '{cid}' in content item {item['id']}")
                conflicts_found += 1
                sys.exit(1)  # Stop on ambiguous canonical ID conflict

    # B. Repair malformed render_jobs
    now = datetime.datetime.now(datetime.timezone.utc)
    for job in jobs:
        # Never modify COMPLETED jobs
        if job.get("status") == "COMPLETED":
            continue

        cid = job.get("content_id", "")
        plan = job.get("plan_data", {}) or {}
        target_id = plan.get("target_id", "")

        is_malformed = (cid and "ELN-BUNDLE-ELN-BUNDLE-" in cid) or (target_id and "ELN-BUNDLE-ELN-BUNDLE-" in target_id)

        if is_malformed:
            canonical_cid = normalize_bundle_custom_id(cid) if cid else ""
            if canonical_cid in all_item_custom_ids:
                # Retrieve the content item to get its media_keys and validate assets!
                matching_item = next((it for it in items if it.get("custom_id") == canonical_cid), None)
                media_keys = (matching_item.get("media_keys") if matching_item else []) or []

                # Validate source assets
                from agents.storage.supabase_storage import ElinaStorage
                storage = ElinaStorage()
                assets_valid = True

                with tempfile.TemporaryDirectory() as tmpdir:
                    for mkey in media_keys:
                        local_path = os.path.join(tmpdir, "temp_val.mp4")
                        try:
                            storage.download_file(mkey, local_path)
                            if not validate_video_asset(local_path):
                                assets_valid = False
                                break
                        except Exception:
                            assets_valid = False
                            break

                if assets_valid:
                    # Proceed to update and requeue
                    plan["target_id"] = canonical_cid
                    attempts = job.get("attempts") or 0
                    max_attempts = job.get("max_attempts") or 3

                    # Reset attempts only when previous error was TARGET_CONTENT_NOT_FOUND or Item not found
                    err = job.get("error_message") or ""
                    if attempts >= max_attempts and ("TARGET_CONTENT_NOT_FOUND" in err or "Item not found" in err):
                        attempts = 0

                    updates = {
                        "content_id": canonical_cid,
                        "plan_data": plan,
                        "error_message": None,
                        "started_at": None,
                        "completed_at": None,
                        "status": "QUEUED",
                        "attempts": attempts
                    }
                    logger.info(f"Requeuing malformed job {job['id']} with canonical target '{canonical_cid}'")
                    try:
                        db.client.table("render_jobs").update(updates).eq("id", job["id"]).execute()
                        jobs_requeued += 1
                    except Exception as e:
                        logger.error(f"Failed to update malformed job {job['id']}: {e}")
                        sys.exit(1)
                else:
                    # Mark as FAILED with terminal reason INVALID_SOURCE_ASSET_PLACEHOLDER
                    updates = {
                        "status": "FAILED",
                        "error_message": "INVALID_SOURCE_ASSET_PLACEHOLDER"
                    }
                    logger.warning(f"Repair: Mark job {job['id']} as FAILED because some/all source assets are invalid/placeholders.")
                    try:
                        db.client.table("render_jobs").update(updates).eq("id", job["id"]).execute()
                    except Exception as e:
                        logger.error(f"Failed to set job {job['id']} as FAILED: {e}")
                        sys.exit(1)
            else:
                # Canonical content item does not exist, set FAILED
                updates = {
                    "status": "FAILED",
                    "error_message": "TARGET_CONTENT_NOT_FOUND_AFTER_NORMALIZATION"
                }
                logger.info(f"Marking orphan job {job['id']} as FAILED because canonical target '{canonical_cid}' does not exist.")
                try:
                    db.client.table("render_jobs").update(updates).eq("id", job["id"]).execute()
                except Exception as e:
                    logger.error(f"Failed to fail orphan job {job['id']}: {e}")
                    sys.exit(1)

        # C. Repair stale IN_PROGRESS jobs
        elif job.get("status") == "IN_PROGRESS" and job.get("started_at"):
            try:
                started_at = datetime.datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                if (now - started_at).total_seconds() > 3600:
                    canonical_cid = normalize_bundle_custom_id(cid) if cid else ""
                    if canonical_cid in all_item_custom_ids:
                        updates = {
                            "status": "QUEUED",
                            "started_at": None,
                            "error_message": "STALE_JOB_RECOVERED"
                        }
                        logger.info(f"Requeuing stale job {job['id']} with canonical target '{canonical_cid}'")
                        db.client.table("render_jobs").update(updates).eq("id", job["id"]).execute()
                        jobs_requeued += 1
                    else:
                        updates = {
                            "status": "FAILED",
                            "error_message": "TARGET_CONTENT_NOT_FOUND"
                        }
                        logger.info(f"Failing stale orphan job {job['id']}")
                        db.client.table("render_jobs").update(updates).eq("id", job["id"]).execute()
            except Exception as e:
                logger.error(f"Failed to handle stale job {job['id']}: {e}")
                sys.exit(1)

    result = {
        "ok": True,
        "rows_repaired": rows_repaired,
        "jobs_requeued": jobs_requeued,
        "conflicts_found": conflicts_found
    }

    print("\n--- REPAIR RESULT REPORT ---")
    for k, v in result.items():
        print(f"{k}: {v}")
    print("----------------------------\n")

    return result


def main():
    parser = argparse.ArgumentParser(description="Supabase Bundle and Render Job Repair")
    parser.add_argument("--mode", required=True, choices=["diagnose", "repair"], help="Operation mode")
    args = parser.parse_args()

    db = ElinaDB()

    if args.mode == "diagnose":
        run_diagnose(db)
    elif args.mode == "repair":
        run_repair(db)


if __name__ == "__main__":
    main()
