"""LipSyncStudio Agent (added 2026-07-06, real-tool integration).

WHY THIS EXISTS: DirectorAgent's "custom_talking_head" workflow (see
video_generator.py) claims to use SadTalker/LongCat to make Elina's photo
actually talk, but the real code just applies a Ken Burns zoom effect to a
static photo -- there is no actual mouth movement / lip-sync anywhere in
the codebase. This was found by directly reading video_generator.py's
run_managed_project(): the "custom_talking_head" branch only sets an output
filename and falls through to the same _create_real_video() zoom-only
fallback every other workflow uses.

This module closes that gap with a REAL, working, free lip-sync call:
  1. vinthony/SadTalker (the model referenced in existing docs) is
     currently down (verified live: Hugging Face reports BUILD_ERROR on
     the public Space as of 2026-07-06) -- confirmed via a direct
     gradio_client connection attempt, not assumed.
  2. fffiloni/LatentSync (ByteDance's LatentSync, a 2025 SOTA open-source
     lip-sync model -- reported by real users to beat Wav2Lip/SadTalker in
     blind comparisons) IS live and reachable, confirmed via a real
     `Client("fffiloni/LatentSync").view_api()` call that returned a valid
     endpoint: predict(input_video_path, input_audio_path,
     api_name="/generate_lip_sync_video") -> result (a video file).

Unlike SadTalker (photo + audio -> talking video), LatentSync takes an
EXISTING VIDEO + audio and re-syncs the mouth to match the audio. This
actually fits ElinaOS's real pipeline better than SadTalker would have:
DirectorAgent._create_real_video() already turns Elina's reference photo
into a short Ken-Burns MP4, and FacelessStudio already generates a real
edge-tts voiceover -- this module is the missing middle step that takes
those two REAL existing outputs and produces one video where Elina's mouth
actually matches the narration, instead of a silent zoom with a text
overlay pretending to be a talking-head video.

Usage (free, no cost beyond a free Hugging Face account for HF_TOKEN):
    from .lip_sync_studio import LipSyncStudio
    result = LipSyncStudio().sync(video_path, audio_path)
    # result: {"video_path": "...", "ok": True} or {"ok": False, "error": ...}
"""

import os
import shutil
from datetime import datetime

from .base import Agent

_OUT_DIR = "content/videos"

# Tried in order. IMPORTANT REAL-WORLD FINDING (verified live, 2026-07-06):
# fffiloni/LatentSync IS reachable but its app.py hard-codes a ZeroGPU
# duration request (180s) that EXCEEDS the free/anonymous quota (Hugging
# Face's own docs: 60s for logged-out users, up from there only with a paid
# Pro account) -- this is a limit baked into that specific Space's code, not
# something this module's caller can work around by sending shorter
# clips/audio. So the default first choice is
# manavisrani07/gradio-lipsync-wav2lip, a CPU-only Wav2Lip Space (confirmed
# live via a real Client(...).view_api() call) which has no GPU-quota wall
# at all, at the cost of Wav2Lip's slightly lower mouth-shape fidelity
# compared to LatentSync. LatentSync is kept as a second attempt for
# accounts with a Hugging Face PRO token (raises the ZeroGPU quota enough
# to satisfy that Space's 180s request) -- see docs/LIP-SYNC-SETUP.md.
# vinthony/SadTalker (the model actually named in this repo's older docs)
# is currently down (verified live: reports BUILD_ERROR) and kept last in
# case the Space owner fixes it later.
_SPACES_IN_TRY_ORDER = [
    {"space": "manavisrani07/gradio-lipsync-wav2lip", "api_name": "/generate",
     "mode": "wav2lip_cpu"},
    {"space": "fffiloni/LatentSync", "api_name": "/generate_lip_sync_video",
     "mode": "video_audio"},
    {"space": "vinthony/SadTalker", "api_name": "/predict", "mode": "image_audio"},
]



class LipSyncStudio(Agent):
    def __init__(self):
        super().__init__("LipSyncStudio", "Real lip-sync via free Hugging Face Spaces (LatentSync/SadTalker)")
        os.makedirs(_OUT_DIR, exist_ok=True)
        self.hf_token = os.environ.get("HF_TOKEN", "")

    def sync(self, video_path: str, audio_path: str, source_image: str = "") -> dict:
        """Takes a real rendered video (or a source photo) + a real audio
        file and returns a new video with the mouth actually synced to the
        audio. Tries each configured Space in order; if every one fails
        (offline, quota, network), returns {'ok': False, 'error': ...} so
        the caller can fall back to the silent zoom video rather than crash
        the whole pipeline -- lip-sync is an enhancement, not a hard
        dependency, exactly like every other optional agent in this repo."""
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        if not (video_path and os.path.exists(video_path)) and not (source_image and os.path.exists(source_image)):
            return {"ok": False, "error": "no_source_video_or_image"}
        if not (audio_path and os.path.exists(audio_path)):
            return {"ok": False, "error": "no_audio_path"}

        try:
            from gradio_client import Client, handle_file
        except ImportError:
            self.log("gradio_client not installed -- skipping lip-sync", "error")
            return {"ok": False, "error": "gradio_client_not_installed"}

        last_error = ""
        for cfg in _SPACES_IN_TRY_ORDER:
            if cfg["mode"] in ("video_audio", "wav2lip_cpu") and not (video_path and os.path.exists(video_path)):
                continue  # these Spaces need a pre-rendered video, not just a photo
            try:
                self.log(f"Trying lip-sync via {cfg['space']}...")
                client = Client(cfg["space"], token=self.hf_token or None)
                if cfg["mode"] == "wav2lip_cpu":
                    result = client.predict(
                        video=handle_file(video_path),
                        audio=handle_file(audio_path),
                        checkpoint="wav2lip_gan",
                        api_name=cfg["api_name"],
                    )
                elif cfg["mode"] == "video_audio":
                    result = client.predict(
                        input_video_path=handle_file(video_path),
                        input_audio_path=handle_file(audio_path),
                        api_name=cfg["api_name"],
                    )
                else:
                    result = client.predict(
                        source_image=handle_file(source_image or video_path),
                        driven_audio=handle_file(audio_path),
                        api_name=cfg["api_name"],
                    )

                # gradio_client returns either a filepath string or a dict
                # with a "video" key depending on the Space's output schema.
                result_path = result if isinstance(result, str) else (result or {}).get("video", "")
                if result_path and os.path.exists(result_path):
                    ts = datetime.now().strftime("%Y%m%d%H%M%S")
                    out_path = os.path.join(_OUT_DIR, f"lipsync_{ts}.mp4")
                    shutil.copy(result_path, out_path)
                    self.log(f"✅ Lip-sync succeeded via {cfg['space']}: {out_path}")
                    return {"ok": True, "video_path": out_path, "provider": cfg["space"]}
                last_error = f"{cfg['space']}: empty/missing result path"
            except Exception as e:
                last_error = f"{cfg['space']}: {e}"
                self.log(f"Lip-sync via {cfg['space']} failed: {e}", "warning")
                continue

        self.log(f"All lip-sync providers failed: {last_error}", "error")
        return {"ok": False, "error": last_error}

    def run(self, video_path: str = "", audio_path: str = "", source_image: str = "") -> dict:
        return self.sync(video_path, audio_path, source_image)
