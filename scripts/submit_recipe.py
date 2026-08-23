#!/usr/bin/env python
import os
import sys
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.rendering.job_manager import RenderJobManager
from agents.db.supabase_client import ElinaDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SubmitRecipe")


def validate_recipe(plan_data: dict) -> None:
    content_id = plan_data.get("target_id") or plan_data.get("content_id")
    if not content_id:
        raise ValueError("content_id/target_id is required.")

    db = ElinaDB()
    item = db.get_content_by_custom_id(content_id)
    if not item:
        raise ValueError(f"TARGET_CONTENT_NOT_FOUND: target_id '{content_id}' not found in database")

    media_keys = item.get("media_keys", [])
    n_shots = len(media_keys)

    # Check index range and construct video_segments
    video_segments = []
    for shot in plan_data.get("shots", []):
        idx_1based = shot.get("index", 1)
        if idx_1based < 1 or idx_1based > n_shots:
            raise ValueError(f"SHOT_INDEX_OUT_OF_RANGE: shot {idx_1based} requested but bundle has {n_shots} shots")
        if not shot.get("remove"):
            video_segments.append(shot)

    if not video_segments:
        raise ValueError("PLAN_ALL_SHOTS_REMOVED")

    # Validate transition_out, freeze_tail_sec, transform on shots
    for i, shot in enumerate(plan_data.get("shots", [])):
        trans = shot.get("transition_out")
        if trans is not None:
            if not isinstance(trans, dict):
                raise ValueError("TRANSITION_TYPE_INVALID: transition_out must be a dictionary")
            t_type = trans.get("type", "hard_cut")
            if t_type not in ("hard_cut", "dissolve", "fade_black"):
                raise ValueError(f"TRANSITION_TYPE_INVALID: invalid type '{t_type}'")

        freeze_sec = shot.get("freeze_tail_sec")
        if freeze_sec is not None:
            try:
                f_val = float(freeze_sec)
                if f_val < 0.0 or f_val > 1.0:
                    raise ValueError("FREEZE_DURATION_INVALID: freeze_tail_sec must be between 0.0 and 1.0")
            except ValueError as ve:
                if "FREEZE_DURATION_INVALID" in str(ve):
                    raise
                raise ValueError("FREEZE_DURATION_INVALID: freeze_tail_sec must be a float")

        transform = shot.get("transform")
        if transform is not None:
            if not isinstance(transform, dict):
                raise ValueError("TRANSFORM_INVALID: transform must be a dictionary")
            if len(transform) > 0:
                scale = transform.get("scale")
                x = transform.get("x")
                y = transform.get("y")
                if scale is None or x is None or y is None:
                    raise ValueError("TRANSFORM_INVALID: transform must contain scale, x, and y")
                try:
                    s_val = float(scale)
                    if s_val < 0.8 or s_val > 1.5:
                        raise ValueError("TRANSFORM_INVALID: scale must be between 0.8 and 1.5")
                except ValueError as ve:
                    if "TRANSFORM_INVALID" in str(ve):
                        raise
                    raise ValueError("TRANSFORM_INVALID: scale must be a float")
                try:
                    int(x)
                    int(y)
                except ValueError:
                    raise ValueError("TRANSFORM_INVALID: x and y offsets must be integers")

    # Validate SFX anchors
    for sfx in plan_data.get("sfx", []):
        anchor_str = sfx.get("anchor")
        if anchor_str:
            if not anchor_str.startswith("shot_") or "." not in anchor_str:
                raise ValueError("SFX_ANCHOR_OUT_OF_RANGE: invalid anchor format")
            try:
                parts = anchor_str.split(".")
                shot_part = parts[0]
                point_part = parts[1]

                shot_idx_1based = int(shot_part.split("_")[1])
                if shot_idx_1based < 1 or shot_idx_1based > len(video_segments):
                    raise ValueError(f"SFX_ANCHOR_OUT_OF_RANGE: shot_{shot_idx_1based} out of range (kept shots: {len(video_segments)})")

                if point_part not in ("start", "end"):
                    raise ValueError("SFX_ANCHOR_OUT_OF_RANGE: anchor point must be start or end")
            except (IndexError, ValueError) as exc:
                if "SFX_ANCHOR_OUT_OF_RANGE" in str(exc):
                    raise
                raise ValueError(f"SFX_ANCHOR_OUT_OF_RANGE: malformed anchor '{anchor_str}'") from exc


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/submit_recipe.py <path_to_json_file>", file=sys.stderr)
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f"Error: file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            plan_data = json.load(f)
    except Exception as e:
        print(f"Error: failed to parse JSON file: {e}", file=sys.stderr)
        sys.exit(1)

    # Perform existing plan validations
    try:
        validate_recipe(plan_data)
    except Exception as e:
        print(f"Validation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure OWNER_CHAT_ID is set
    owner_chat_id = os.environ.get("OWNER_CHAT_ID")
    if not owner_chat_id:
        print("Error: OWNER_CHAT_ID environment variable is missing", file=sys.stderr)
        sys.exit(1)

    # Queue the job
    try:
        mgr = RenderJobManager()
        content_id = plan_data.get("target_id") or plan_data.get("content_id")
        job = mgr.queue_job(
            content_id=content_id,
            plan_data=plan_data,
            owner_chat_id=str(owner_chat_id)
        )
        print(f"SUCCESS: Job {job.get('id')} queued successfully for content {content_id}")
        sys.exit(0)
    except Exception as e:
        print(f"Error: failed to queue job in database: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
