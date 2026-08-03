import os
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from agents.db.supabase_client import ElinaDB
from agents.storage.supabase_storage import ElinaStorage
from agents.editing.recipe_schema import EditRecipe
from agents.editing.typography_engine import TypographyEngine
from agents.editing.media_assembly import MediaAssemblyEngine, run_qc_checks
from agents.editing.concatenator import VideoConcatenator

logger = logging.getLogger(__name__)


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
                    type("VSC", (), {"key": s["key"], "start_sec": s.get("start_sec", 0.0), "end_sec": s.get("end_sec")})()
                    for s in video_segments
                ]
                recipe.input_media.video_keys = []

            if voice_key:
                recipe.input_media.voice_key = voice_key

            if music_key:
                recipe.input_media.music_key = music_key

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
                    local_segments.append({
                        "path": str(vpath),
                        "start_sec": seg.start_sec,
                        "end_sec": seg.end_sec,
                    })

                # Concatenate segments (with optional trimming)
                VideoConcatenator().concat_segments(local_segments, str(base_video))

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
                )

                qc_errors = run_qc_checks(str(output_video), recipe)
                if qc_errors:
                    self.db.update_status(item["id"], "EDIT_FAILED", {"last_error": "; ".join(qc_errors)})
                    self.db.log_event(item["id"], "edit_failed", "EDIT_RENDERING", "EDIT_FAILED", actor, "; ".join(qc_errors))
                    return {"ok": False, "error": "; ".join(qc_errors)}

                output_key = f"edited/{custom_id}/final.mp4"
                self.storage.upload_file(str(output_video), output_key, content_type="video/mp4")

            self.db.update_status(item["id"], "READY_FOR_REVIEW", {
                "media_keys": [output_key],
                "edit_status": "done",
            })
            self.db.log_event(item["id"], "edit_done", "EDIT_RENDERING", "READY_FOR_REVIEW", actor, output_key)
            return {"ok": True, "custom_id": custom_id, "output_key": output_key, "status": "READY_FOR_REVIEW"}

        except Exception as exc:
            logger.exception("Edit failed for %s", custom_id)
            self.db.update_status(item["id"], "EDIT_FAILED", {"last_error": str(exc)})
            self.db.log_event(item["id"], "edit_failed", "EDIT_RENDERING", "EDIT_FAILED", actor, str(exc))
            return {"ok": False, "error": str(exc)}
