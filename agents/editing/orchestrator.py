import os
import tempfile
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

from agents.db.supabase_client import ElinaDB
from agents.storage.supabase_storage import ElinaStorage
from agents.editing.recipe_schema import EditRecipe, VideoSegmentConfig
from agents.editing.typography_engine import TypographyEngine
from agents.editing.media_assembly import MediaAssemblyEngine, run_qc_checks
from agents.editing.concatenator import VideoConcatenator, get_video_properties

logger = logging.getLogger(__name__)


def validate_video_asset(path: str, ffprobe_binary: str = "ffprobe") -> bool:
    logger.info(f"Running asset sanity check on {path}...")
    if not path or not os.path.exists(path):
        logger.warning(f"Sanity check failed: File does not exist: {path}")
        return False
    if os.path.getsize(path) == 0:
        logger.warning(f"Sanity check failed: File is zero bytes: {path}")
        return False

    # Check for test mock bypass
    if os.environ.get("ELINA_TEST_ALLOW_MOCKS") == "true":
        return True

    try:
        # Check if the file contains mock placeholder bytes (repeating '0's)
        with open(path, "rb") as f:
            head = f.read(100)
            if head and all(b == 48 for b in head):
                logger.warning(f"Sanity check failed: Detected mock placeholder file at {path}")
                return False
    except Exception:
        pass

    try:
        result = subprocess.run(
            [
                ffprobe_binary,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "csv=p=0",
                path
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            logger.warning(f"Sanity check failed: No valid video stream or ffprobe error on {path}")
            return False
        return True
    except Exception as e:
        logger.warning(f"Sanity check failed: Exception running ffprobe on {path}: {e}")
        return False


class EditOrchestrator:
    """
    Coordinates the complete edit flow:
    Supabase DB -> Storage download -> typography PNG -> media assembly -> QC -> Storage upload -> DB update.
    """

    def __init__(
        self,
        db: Optional[ElinaDB] = None,
        storage: Optional[ElinaStorage] = None,
        typography: Optional[TypographyEngine] = None,
        assembler: Optional[MediaAssemblyEngine] = None,
    ):
        self.db = db or ElinaDB()
        self.storage = storage or ElinaStorage()
        self.typography = typography
        self.assembler = assembler or MediaAssemblyEngine()

    def build_recipe_from_item(self, item: Dict[str, Any], hook_text: Optional[str] = None) -> EditRecipe:
        media_keys = item.get("media_keys") or []
        video_segments = item.get("video_segments", [])

        if not media_keys and not video_segments:
            raise ValueError("content item has no media_keys or video_segments")

        recipe_data = {
            "content_id": item["id"],
            "project_type": "reel" if item.get("content_type") == "reel" else "preview",
            "preset": "elina_cinematic_reel",
            "input_media": {
                "video_keys": media_keys,
                "video_segments": video_segments,
                "image_keys": [],
                "voice_key": item.get("voice_key"),
                "music_key": item.get("music_key"),
            },
            "hook": {
                "enabled": bool(hook_text),
                "text": hook_text or "",
                "style": "hook_bold_center",
                "start_sec": 0.0,
                "end_sec": 3.0,
            },
            "export": {
                "resolution": "1080x1920",
                "fps": 30,
                "format": "mp4",
                "max_size_mb": 50,
            },
        }
        recipe = EditRecipe.from_dict(recipe_data)
        errors = recipe.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return recipe

    def render_content(
        self,
        custom_id: str,
        hook_text: Optional[str] = None,
        actor: str = "editor",
        video_segments: Optional[List[Dict[str, Any]]] = None,
        voice_key: Optional[str] = None,
        music_key: Optional[str] = None,
        mute_original: bool = True,
        plan_sfx: Optional[List[Dict[str, Any]]] = None,
        plan_music: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        item = self.db.get_content_by_custom_id(custom_id)
        if not item:
            return {"ok": False, "error": f"Item not found: {custom_id}"}

        original_status = item.get("status")
        self.db.update_status(item["id"], "EDIT_RENDERING")
        self.db.log_event(item["id"], "edit_rendering_started", original_status, "EDIT_RENDERING", actor)

        try:
            recipe = self.build_recipe_from_item(item, hook_text=hook_text)

            # Apply overrides if provided (from /render command)
            if video_segments:
                # Convert dicts to VideoSegmentConfig-like dicts
                recipe.input_media.video_segments = [
                    VideoSegmentConfig(
                        key=s["key"],
                        start_sec=s.get("start_sec", 0.0),
                        end_sec=s.get("end_sec"),
                        transition_out=s.get("transition_out"),
                        freeze_tail_sec=s.get("freeze_tail_sec"),
                        transform=s.get("transform")
                    )
                    for s in video_segments
                ]
                recipe.input_media.video_keys = []

            if voice_key:
                recipe.input_media.voice_key = voice_key

            if music_key:
                recipe.input_media.music_key = music_key

            # Propagate plan_music gain_db to recipe
            if plan_music and isinstance(plan_music, dict):
                if "gain_db" in plan_music and plan_music["gain_db"] is not None:
                    recipe.audio.music_gain_db = plan_music["gain_db"]

            # Honor the music instruction from the Persian edit plan. Never
            # silently ignore it: if the user explicitly asks for music but no
            # music asset is available (no music provider is implemented in the
            # stack), fail with a typed error instead of rendering without it.
            if plan_music and isinstance(plan_music, dict) and plan_music.get("explicit"):
                if plan_music.get("enabled"):
                    if not recipe.input_media.music_key:
                        raise RuntimeError(
                            "MUSIC_PROVIDER_NOT_CONFIGURED: plan requests music but no "
                            "music_key asset is available and no music provider is implemented"
                        )
                else:
                    # User explicitly said no music: drop any item-level music asset
                    recipe.input_media.music_key = None

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                base_video = tmp / "base_video.mp4"
                output_video = tmp / "output.mp4"
                hook_png = tmp / "hook.png"

                # Download all videos and concatenate if multiple using segments
                segments = recipe.input_media.video_segments
                if not segments:
                    # Convert video_keys to segments if no segments provided
                    video_keys = recipe.input_media.video_keys
                    if not video_keys:
                        raise ValueError("No video_segments or video_keys available for rendering")
                    segments = [{"key": vk} for vk in video_keys]

                # Download all segment files and build local segment dicts
                local_segments = []
                for idx, seg in enumerate(segments):
                    vpath = tmp / f"clip_{idx}.mp4"
                    self.storage.download_file(seg.key, str(vpath))

                    # Asset sanity gate
                    if not validate_video_asset(str(vpath)):
                        raise ValueError("INVALID_SOURCE_ASSET_PLACEHOLDER")

                    local_segments.append({
                        "path": str(vpath),
                        "start_sec": seg.start_sec,
                        "end_sec": seg.end_sec,
                        "transition_out": getattr(seg, "transition_out", None),
                        "freeze_tail_sec": getattr(seg, "freeze_tail_sec", None),
                        "transform": getattr(seg, "transform", None),
                    })

                # Concatenate segments (with optional trimming). Keep the
                # original audio only when the user's plan asked for it.
                keep_audio = not mute_original
                VideoConcatenator().concat_segments(local_segments, str(base_video), keep_audio=keep_audio)

                # The concat stage may fall back to video-only when no segment
                # carries audio; only mix base audio when it actually exists.
                use_base_audio = False
                if keep_audio:
                    base_props = get_video_properties(str(base_video))
                    use_base_audio = bool(base_props.get("has_audio", False))

                # Download voice track if present
                voice_path = None
                if recipe.input_media.voice_key:
                    voice_path = str(tmp / "voice.mp3")
                    self.storage.download_file(recipe.input_media.voice_key, voice_path)

                # Download music track if present
                music_path = None
                if recipe.input_media.music_key:
                    music_path = str(tmp / "music.mp3")
                    self.storage.download_file(recipe.input_media.music_key, music_path)

                # Process sound effects if available
                sfx_items = []
                raw_sfx_list = getattr(recipe, "sound_effects", None) or item.get("sound_effects") or item.get("sfx_items")
                if raw_sfx_list:
                    for s_idx, sfx in enumerate(raw_sfx_list):
                        if not isinstance(sfx, dict):
                            continue

                        sfx_key = sfx.get("key") or sfx.get("storage_key")
                        sfx_path = sfx.get("path") or sfx.get("local_path")

                        local_path = None
                        if sfx_key:
                            ext = os.path.splitext(sfx_key)[1] or ".mp3"
                            local_path = str(tmp / f"sfx_{s_idx}{ext}")
                            self.storage.download_file(sfx_key, local_path)
                        elif sfx_path and not os.path.exists(sfx_path):
                            try:
                                ext = os.path.splitext(sfx_path)[1] or ".mp3"
                                local_path = str(tmp / f"sfx_{s_idx}{ext}")
                                self.storage.download_file(sfx_path, local_path)
                            except Exception:
                                local_path = sfx_path
                        else:
                            local_path = sfx_path or ""

                        start_sec = float(sfx.get("start_sec", sfx.get("start", sfx.get("start_time", 0.0))))
                        gain_db = int(sfx.get("gain_db", sfx.get("gain", sfx.get("volume", 0))))
                        fade_in_sec = float(sfx.get("fade_in_sec", sfx.get("fade_in", 0.0)))
                        fade_out_sec = float(sfx.get("fade_out_sec", sfx.get("fade_out", 0.0)))
                        attribution = sfx.get("attribution")

                        sfx_items.append({
                            "path": local_path,
                            "start_sec": start_sec,
                            "gain_db": gain_db,
                            "fade_in_sec": fade_in_sec,
                            "fade_out_sec": fade_out_sec,
                            "attribution": attribution,
                        })

                # Resolve SFX requested by the Persian edit plan (query -> sound
                # file). Never silently skip: if the SFX provider is not
                # configured or no sound matches, fail with a typed error.
                if plan_sfx:
                    try:
                        from agents.audio.sfx_fetcher import SFXFetcher
                        fetcher = SFXFetcher()
                    except ValueError as exc:
                        raise RuntimeError(f"SFX_PROVIDER_NOT_CONFIGURED: {exc}")

                    for sfx_idx, sfx in enumerate(plan_sfx):
                        if not isinstance(sfx, dict):
                            raise RuntimeError(f"SFX_INVALID_PLAN_ENTRY: {sfx!r}")
                        query = (sfx.get("query") or "").strip()
                        if not query:
                            raise RuntimeError("SFX_INVALID_PLAN_ENTRY: empty query")

                        local_path = str(tmp / f"plan_sfx_{sfx_idx}.mp3")
                        try:
                            fetched = fetcher.fetch_best_match(query, local_path)
                        except Exception as exc:
                            raise RuntimeError(f"SFX_FETCH_FAILED: {exc}") from exc
                        if fetched is None:
                            raise RuntimeError(f"SFX_FETCH_FAILED: no match for '{query}'")

                        sfx_items.append({
                            "path": fetched.local_path,
                            "start_sec": float(sfx.get("start_sec", sfx.get("start", 0.0))),
                            "gain_db": int(sfx.get("gain_db", sfx.get("gain", 0))),
                            "fade_in_sec": float(sfx.get("fade_in_sec", sfx.get("fade_in", 0.0))),
                            "fade_out_sec": float(sfx.get("fade_out_sec", sfx.get("fade_out", 0.0))),
                            "attribution": getattr(fetched.metadata, "attribution", None),
                        })

                # Render hook PNG if requested
                hook_png_path = None
                if recipe.hook.enabled:
                    if not self.typography:
                        self.typography = TypographyEngine()
                    self.typography.render_text_to_png(
                        text=recipe.hook.text,
                        output_path=str(hook_png),
                        font_size=72,
                        canvas_size=(1080, 300),
                    )
                    hook_png_path = str(hook_png)

                # Assemble video
                self.assembler.run_assembly(
                    recipe=recipe,
                    video_path=str(base_video),
                    voice_path=voice_path,
                    music_path=music_path,
                    hook_png_path=hook_png_path,
                    output_path=str(output_video),
                    sfx_items=sfx_items if sfx_items else None,
                    use_base_audio=use_base_audio,
                )

                qc_errors = run_qc_checks(str(output_video), recipe)
                if qc_errors:
                    self.db.update_status(item["id"], "EDIT_FAILED", {"last_error": "; ".join(qc_errors)})
                    self.db.log_event(item["id"], "edit_failed", "EDIT_RENDERING", "EDIT_FAILED", actor, "; ".join(qc_errors))
                    return {"ok": False, "error": "; ".join(qc_errors)}

                import datetime
                if job_id:
                    output_key = f"edited/{custom_id}/{job_id}.mp4"
                else:
                    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:-3]
                    output_key = f"edited/{custom_id}/render-{timestamp}.mp4"
                self.storage.upload_file(str(output_video), output_key, content_type="video/mp4")

            import datetime
            last_rendered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            history = item.get("edited_media_history") or []
            if not isinstance(history, list):
                history = []
            if output_key not in history:
                history.append(output_key)

            self.db.update_status(item["id"], "READY_FOR_REVIEW", {
                "edited_media_key": output_key,
                "edited_media_history": history,
                "last_rendered_at": last_rendered_at,
                "edit_status": "done",
            })
            self.db.log_event(item["id"], "edit_done", "EDIT_RENDERING", "READY_FOR_REVIEW", actor, output_key)
            return {"ok": True, "custom_id": custom_id, "output_key": output_key, "status": "READY_FOR_REVIEW"}

        except Exception as exc:
            logger.exception("Edit failed for %s", custom_id)
            self.db.update_status(item["id"], "EDIT_FAILED", {"last_error": str(exc)})
            self.db.log_event(item["id"], "edit_failed", "EDIT_RENDERING", "EDIT_FAILED", actor, str(exc))
            return {"ok": False, "error": str(exc)}
