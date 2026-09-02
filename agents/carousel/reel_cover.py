"""
Reel cover generator (M18E) — 1080x1920 (9:16) branded covers for Reels.

This is a thin OPT-IN adapter on top of the existing M18A carousel slide
renderer: `CarouselSlideRenderer` already accepts a `canvas_size` parameter
and all its layouts are canvas-fraction based (font scale is width-based),
so a 1080x1920 cover reuses the exact same engine, brand theme, Persian
shaping, and overflow protection with zero renderer changes.

Nothing in the default render pipeline calls this module — covers are only
produced when a caller explicitly uses `ReelCoverRenderer` (or
`extract_first_frame` to prepare a source frame).
"""

import os
import shutil
import subprocess
from typing import Optional, Tuple

from agents.carousel.brand_theme import PALETTE, TEMPLATES
from agents.carousel.schema import (
    DEFAULT_TEMPLATE,
    CarouselConfigError,
    CarouselImageError,
    CarouselSlide,
    CarouselTextOverflowError,
    parse_carousel_slide,
)
from agents.carousel.slide_renderer import CarouselSlideRenderer

# Canonical Reel cover canvas (Instagram 9:16)
REEL_COVER_WIDTH = 1080
REEL_COVER_HEIGHT = 1920
REEL_COVER_SIZE: Tuple[int, int] = (REEL_COVER_WIDTH, REEL_COVER_HEIGHT)

# Text limits (same philosophy as the M18A cover slide type)
REEL_COVER_TITLE_MAX = 60
REEL_COVER_EYEBROW_MAX = 40


def extract_first_frame(video_path: str, output_path: str,
                        ffmpeg_path: str = "ffmpeg") -> str:
    """
    Extract the first frame of a video as a JPEG (e.g. to use as a reel
    cover background). Raises CarouselImageError for missing/invalid input.
    """
    if not video_path or not os.path.exists(video_path):
        raise CarouselImageError(f"video not found: {video_path}")
    if not shutil.which(ffmpeg_path):
        raise CarouselImageError(f"ffmpeg not available: {ffmpeg_path}")
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    cmd = [
        ffmpeg_path, "-y", "-v", "error",
        "-i", video_path,
        "-frames:v", "1", "-q:v", "2",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        err = (result.stderr or "").strip()[-200:]
        raise CarouselImageError(f"could not extract first frame: {err}")
    return output_path


class ReelCoverRenderer:
    """
    Opt-in 9:16 Reel cover generator.

    Reuses `CarouselSlideRenderer` with a 1080x1920 canvas; cover-style
    layout only (short title, optional eyebrow, optional full-bleed image
    with dark gradient overlay). Overflow protection, Persian shaping, and
    brand themes are inherited from the M18A renderer.
    """

    def __init__(self, engine=None, font_path: Optional[str] = None,
                 canvas_size: Tuple[int, int] = REEL_COVER_SIZE):
        self.slide_renderer = CarouselSlideRenderer(
            engine=engine,
            font_path=font_path,
            canvas_size=canvas_size,
        )

    def render_cover(
        self,
        title: str,
        output_path: str,
        template: str = DEFAULT_TEMPLATE,
        eyebrow: str = "",
        image_path: Optional[str] = None,
        accent: str = "antique_gold",
    ) -> str:
        """
        Render a branded reel cover to `output_path` (PNG). Returns the path.

        - title: required, non-empty, max 60 chars (short thumbnail title)
        - template: one of the Brand Book V2 templates
        - eyebrow: optional short kicker, max 40 chars
        - image_path: optional source image (cover-cropped, gradient
          overlay) — e.g. a video first frame via extract_first_frame()
          or a character asset
        - accent: any Brand Book V2 palette color

        Raises:
        - CarouselConfigError for invalid inputs (typed, before rendering)
        - CarouselImageError for a missing/unreadable image
        - CarouselTextOverflowError if the title cannot fit (M18A
          protection; the title cap makes this rare, but it is never
          clipped silently)
        """
        title = (title or "").strip()
        if not title:
            raise CarouselConfigError("reel cover title must be a non-empty string")
        if len(title) > REEL_COVER_TITLE_MAX:
            raise CarouselConfigError(
                f"reel cover title is {len(title)} chars; maximum is {REEL_COVER_TITLE_MAX}"
            )
        eyebrow = (eyebrow or "").strip()
        if len(eyebrow) > REEL_COVER_EYEBROW_MAX:
            raise CarouselConfigError(
                f"reel cover eyebrow is {len(eyebrow)} chars; maximum is {REEL_COVER_EYEBROW_MAX}"
            )
        if template not in TEMPLATES:
            raise CarouselConfigError(
                f"template '{template}' is not supported (use one of {sorted(TEMPLATES)})"
            )
        if accent not in PALETTE:
            raise CarouselConfigError(
                f"accent '{accent}' is not a Brand Book V2 palette color "
                f"(use one of {sorted(PALETTE)})"
            )
        if image_path is not None and not isinstance(image_path, str):
            raise CarouselConfigError("'image_path' must be a string or None")
        if not isinstance(output_path, str) or not output_path.lower().endswith(".png"):
            raise CarouselConfigError("output_path must end with .png")

        # Validate through the same M18A schema gate as carousel slides
        parse_carousel_slide({
            "slide_type": "cover",
            "title": title,
            "eyebrow": eyebrow,
            "image_path": image_path,
            "accent": accent,
            "template": template,
        })

        slide = CarouselSlide(
            slide_type="cover",
            title=title,
            eyebrow=eyebrow,
            image_path=image_path,
            accent=accent,
            template=template,
        )
        return self.slide_renderer.render(slide, output_path)
