"""M30 — Still image -> vertical MP4 reel segment.

Converts a single uploaded image into a standard vertical MP4 so it can sit
between real video segments inside an ordinary video bundle:

    1080x1920, 30 fps (CFR), H.264 yuv420p, SAR 1:1, DAR 9:16,
    silent AAC stereo 48 kHz audio, optional deterministic slow zoom.

Fit modes (the image is NEVER stretched):
    contain — the whole image is preserved; the unused canvas area is
              filled with a blurred + darkened copy of the same image
    cover   — aspect-preserving crop that fills the whole canvas

Motion modes (smooth, deterministic zoom around the frame center):
    none     — static frame
    zoom_in  — slow zoom from start_scale to end_scale
    zoom_out — slow zoom from end_scale to start_scale

The zoom is implemented with FFmpeg ``zoompan`` on a 4x pre-scaled frame so
the per-frame motion stays sub-pixel smooth. Scales are zoom factors
relative to the fitted 1080x1920 frame (1.0 = the full fitted frame).

Deliberately independent of the render pipeline: this module does NOT use
DirectorAgent._create_real_video, Concatenator, or the render worker.
"""

import logging
import math
import os
import subprocess
from typing import List

logger = logging.getLogger(__name__)


class StillImageClipError(ValueError):
    """Invalid arguments or a failed still-image clip build."""


VALID_MOTIONS = ("none", "zoom_in", "zoom_out")
VALID_FITS = ("contain", "cover")


class StillImageClipBuilder:
    """Builds a standard vertical MP4 clip from a single still image."""

    OUTPUT_WIDTH = 1080
    OUTPUT_HEIGHT = 1920
    OUTPUT_FPS = 30
    VALID_MOTIONS = VALID_MOTIONS
    VALID_FITS = VALID_FITS
    MIN_DURATION_SEC = 0.5
    MAX_DURATION_SEC = 300.0
    MIN_ZOOM_SCALE = 1.0
    MAX_ZOOM_SCALE = 4.0
    IMAGE_EXTENSIONS = (
        ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif", ".gif",
    )

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def is_image_media_key(cls, media_key: str) -> bool:
        """True when a storage path points at a still image."""
        ext = os.path.splitext(str(media_key or ""))[1].lower()
        return ext in cls.IMAGE_EXTENSIONS

    # ------------------------------------------------------------------
    # Argument validation / normalization
    # ------------------------------------------------------------------

    @classmethod
    def normalize_duration(cls, duration_sec) -> float:
        try:
            d = float(duration_sec)
        except (TypeError, ValueError):
            raise StillImageClipError(
                f"duration_sec must be a number of seconds, got: {duration_sec!r}"
            )
        if not math.isfinite(d) or d < cls.MIN_DURATION_SEC or d > cls.MAX_DURATION_SEC:
            raise StillImageClipError(
                f"duration_sec must be between {cls.MIN_DURATION_SEC} and "
                f"{cls.MAX_DURATION_SEC} seconds, got: {d}"
            )
        return d

    @classmethod
    def normalize_motion(cls, motion: str) -> str:
        if not isinstance(motion, str) or motion.strip().lower() not in cls.VALID_MOTIONS:
            raise StillImageClipError(
                f"motion must be one of {list(cls.VALID_MOTIONS)}, got: {motion!r}"
            )
        return motion.strip().lower()

    @classmethod
    def normalize_fit(cls, fit: str) -> str:
        if not isinstance(fit, str) or fit.strip().lower() not in cls.VALID_FITS:
            raise StillImageClipError(
                f"fit must be one of {list(cls.VALID_FITS)}, got: {fit!r}"
            )
        return fit.strip().lower()

    @classmethod
    def normalize_scale(cls, name: str, value) -> float:
        try:
            s = float(value)
        except (TypeError, ValueError):
            raise StillImageClipError(f"{name} must be a number, got: {value!r}")
        if (
            not math.isfinite(s)
            or s < cls.MIN_ZOOM_SCALE
            or s > cls.MAX_ZOOM_SCALE
        ):
            raise StillImageClipError(
                f"{name} must be between {cls.MIN_ZOOM_SCALE} and "
                f"{cls.MAX_ZOOM_SCALE}, got: {s}"
            )
        return s

    @classmethod
    def frame_count(cls, duration_sec: float) -> int:
        return max(1, int(round(cls.normalize_duration(duration_sec) * cls.OUTPUT_FPS)))

    # ------------------------------------------------------------------
    # FFmpeg filtergraph / command construction (pure, testable)
    # ------------------------------------------------------------------

    def _fit_base_filters(self, fit: str) -> str:
        """[0:v] -> [base]: the fitted 1080x1920 still (never stretched)."""
        w, h = self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT
        if fit == "cover":
            # Scale to cover the canvas (aspect preserved), center-crop.
            return (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={w}:{h},setsar=1,format=yuv420p[base]"
            )
        # contain: blurred + darkened copy fills the canvas, the whole
        # image is overlaid centered.
        return (
            f"[0:v]split=2[fgsrc][bgsrc];"
            f"[bgsrc]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{h},boxblur=24:3,eq=brightness=-0.35[bgbg];"
            f"[fgsrc]scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos[fgimg];"
            f"[bgbg][fgimg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[base]"
        )

    def _zoom_tail(self, motion: str, start_scale: float, end_scale: float,
                   frames: int) -> str:
        """[base] -> [outv]: deterministic zoom (or static) at OUTPUT_FPS."""
        w, h, fps = self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT, self.OUTPUT_FPS
        if motion == "none":
            z = f"{start_scale:.6f}"
        elif frames <= 1:
            z = f"{end_scale:.6f}" if motion == "zoom_in" else f"{start_scale:.6f}"
        else:
            if motion == "zoom_in":
                a, b = start_scale, end_scale
            else:  # zoom_out: start zoomed-in, ease back to start_scale
                a, b = end_scale, start_scale
            z = f"({a:.6f}+({b:.6f}-{a:.6f})*on/{frames - 1})"
        # Pre-scale 4x so zoompan operates with sub-pixel precision
        # (smooth, deterministic motion).
        return (
            f"[base]scale={w * 4}:{h * 4}:flags=lanczos,"
            f"zoompan=z='{z}':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2'"
            f":d={frames}:s={w}x{h}:fps={fps},setsar=1,format=yuv420p[outv]"
        )

    def build_filtergraph(
        self,
        fit: str = "contain",
        motion: str = "zoom_in",
        start_scale: float = 1.0,
        end_scale: float = 1.05,
        duration_sec: float = 3.0,
    ) -> str:
        """Compose the full -filter_complex graph (validates all arguments)."""
        fit = self.normalize_fit(fit)
        motion = self.normalize_motion(motion)
        start_scale = self.normalize_scale("start_scale", start_scale)
        end_scale = self.normalize_scale("end_scale", end_scale)
        frames = self.frame_count(duration_sec)
        return self._fit_base_filters(fit) + ";" + self._zoom_tail(
            motion, start_scale, end_scale, frames
        )

    def build_command(
        self,
        image_path: str,
        output_path: str,
        duration_sec: float = 3.0,
        motion: str = "zoom_in",
        fit: str = "contain",
        start_scale: float = 1.0,
        end_scale: float = 1.05,
    ) -> List[str]:
        """Compose the full ffmpeg argv (validates all arguments)."""
        graph = self.build_filtergraph(
            fit=fit,
            motion=motion,
            start_scale=start_scale,
            end_scale=end_scale,
            duration_sec=duration_sec,
        )
        w, h, fps = self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT, self.OUTPUT_FPS
        frames = self.frame_count(duration_sec)
        # Finite silent audio (input-side -t): an infinite anullsrc +
        # -shortest is racy under load; bounding the audio to the exact
        # clip duration makes the output deterministic.
        audio_dur = frames / fps
        cmd = [
            self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
            "-i", image_path,
            # Silent stereo 48 kHz source for the AAC track
            "-f", "lavfi", "-t", f"{audio_dur:.6f}",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-filter_complex", graph,
            "-map", "[outv]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", str(fps), "-vsync", "cfr",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
            "-shortest", "-movflags", "+faststart",
            output_path,
        ]
        return cmd

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def build(
        self,
        image_path: str,
        output_path: str,
        duration_sec: float = 3.0,
        motion: str = "zoom_in",
        fit: str = "contain",
        start_scale: float = 1.0,
        end_scale: float = 1.05,
    ) -> str:
        """Build the vertical MP4 clip and return the output path.

        Raises StillImageClipError on invalid arguments or ffmpeg failure.
        """
        if not image_path or not os.path.isfile(image_path):
            raise StillImageClipError(f"source image not found: {image_path!r}")

        cmd = self.build_command(
            image_path,
            output_path,
            duration_sec=duration_sec,
            motion=motion,
            fit=fit,
            start_scale=start_scale,
            end_scale=end_scale,
        )

        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        logger.info("still_image_clip: building %s -> %s", image_path, output_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if result.returncode != 0 or not os.path.isfile(output_path):
            err_tail = (result.stderr or "")[-2000:]
            raise StillImageClipError(
                f"FFmpeg still-image clip build failed: {err_tail}"
            )
        return output_path
