"""
Timed Persian subtitle rendering (TASK M16).

Subtitles are rendered as transparent PNGs using the existing TypographyEngine,
which handles Persian RTL shaping deterministically (libraqm when available,
arabic-reshaper + python-bidi otherwise). The PNGs are overlaid on the fully
composed final video by the media assembly engine using FFmpeg `overlay` with
`enable='between(t,start,end)'`.

Why PNG overlay instead of FFmpeg drawtext: drawtext has no reliable
Arabic/Persian glyph shaping or bidi reordering. All shaping, bidi ordering,
and line wrapping are therefore done in Pillow, where the output is
deterministic and font-driven.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from agents.editing.recipe_schema import SubtitleEntry
from agents.editing.typography_engine import TypographyEngine

logger = logging.getLogger(__name__)

SUPPORTED_POSITIONS = ("bottom_center", "center", "top_center")
SUPPORTED_STYLES = ("default", "hook", "whisper", "name_reveal")

# Canonical Reels output dimensions (matches the normalization profile).
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

# Instagram UI-safe top margin (status bar area) for top_center subtitles.
TOP_SAFE_MARGIN = 160

# Typed error codes
SUBTITLE_CONFIG_INVALID = "SUBTITLE_CONFIG_INVALID"
SUBTITLE_FONT_NOT_FOUND = "SUBTITLE_FONT_NOT_FOUND"

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{6})$")

# Style presets: light parameter tweaks applied on top of the entry's values.
# - hook: stronger stroke + darker box (emphasized lines)
# - whisper: smaller, lighter background (soft asides)
# - name_reveal: darker tinted box (name/intro reveals)
STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "default": {},
    "hook": {"stroke_width": 3, "background_opacity": 0.7},
    "whisper": {"font_size_factor": 0.85, "stroke_width": 1, "background_opacity": 0.3},
    "name_reveal": {"stroke_width": 2, "background_color": "#111133", "background_opacity": 0.6},
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    m = _HEX_RE.match(hex_color or "")
    if not m:
        raise ValueError(f"{SUBTITLE_CONFIG_INVALID}: color '{hex_color}' must be in #RRGGBB format")
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def parse_subtitle_entries(raw: Any) -> List[SubtitleEntry]:
    """
    Validate a raw plan subtitles list and return SubtitleEntry objects.

    Raises ValueError('SUBTITLE_CONFIG_INVALID: <reason>') on any problem.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{SUBTITLE_CONFIG_INVALID}: subtitles must be a list of entries")

    entries: List[SubtitleEntry] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} must be a dictionary")

        raw_text = item.get("text")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError(f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} text must be a non-empty string")
        text = raw_text.strip()

        try:
            start = float(item.get("start_sec", 0.0))
            end = float(item.get("end_sec", 0.0))
        except (TypeError, ValueError):
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} start_sec/end_sec must be numbers"
            )
        if start < 0:
            raise ValueError(f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} start_sec cannot be negative")
        if end <= start:
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} end_sec must be greater than start_sec"
            )

        try:
            font_size = int(item.get("font_size", 52))
            max_width_ratio = float(item.get("max_width_ratio", 0.82))
            margin_bottom = int(item.get("margin_bottom", 180))
            background_opacity = float(item.get("background_opacity", 0.55))
            fade_in = float(item.get("fade_in_sec", 0.12))
            fade_out = float(item.get("fade_out_sec", 0.12))
        except (TypeError, ValueError):
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} numeric fields must be numbers"
            )

        if not 24 <= font_size <= 120:
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} font_size must be between 24 and 120 (got {font_size})"
            )
        if not 0.3 <= max_width_ratio <= 0.95:
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} max_width_ratio must be between 0.3 and 0.95 (got {max_width_ratio})"
            )
        if not 0.0 <= background_opacity <= 1.0:
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} background_opacity must be between 0 and 1"
            )
        if fade_in < 0 or fade_out < 0:
            raise ValueError(f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} fade durations cannot be negative")
        duration = end - start
        if fade_in + fade_out > duration:
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} fade_in+fade_out "
                f"({fade_in + fade_out:.2f}s) exceeds subtitle duration ({duration:.2f}s)"
            )

        position = item.get("position", "bottom_center")
        if position not in SUPPORTED_POSITIONS:
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} position '{position}' is not supported "
                f"(use one of {list(SUPPORTED_POSITIONS)})"
            )
        style = item.get("style", "default")
        if style not in SUPPORTED_STYLES:
            raise ValueError(
                f"{SUBTITLE_CONFIG_INVALID}: subtitle {i} style '{style}' is not supported "
                f"(use one of {list(SUPPORTED_STYLES)})"
            )

        font_color = item.get("font_color", "#FFFFFF")
        background_color = item.get("background_color", "#000000")
        _hex_to_rgb(font_color)
        _hex_to_rgb(background_color)

        entries.append(SubtitleEntry(
            text=text,
            start_sec=start,
            end_sec=end,
            position=position,
            style=style,
            font_size=font_size,
            max_width_ratio=max_width_ratio,
            margin_bottom=margin_bottom,
            font_color=font_color,
            background_color=background_color,
            background_opacity=background_opacity,
            fade_in_sec=fade_in,
            fade_out_sec=fade_out,
        ))
    return entries


def overlay_position(entry: SubtitleEntry) -> Tuple[str, str]:
    """
    FFmpeg overlay x/y expressions for a subtitle position.

    Expressed with the main video's W/H and overlay's w/h so the result stays
    correct if the canonical output dimensions ever change.
    """
    if entry.position == "center":
        return "(W-w)/2", "(H-h)/2"
    if entry.position == "top_center":
        return "(W-w)/2", str(TOP_SAFE_MARGIN)
    # bottom_center (default): keep above the Instagram UI-safe region
    return "(W-w)/2", f"H-h-{int(entry.margin_bottom)}"


class SubtitleRenderer:
    """Renders SubtitleEntry objects to transparent RGBA PNGs for overlay use."""

    def __init__(self, engine: Optional[TypographyEngine] = None, canvas_width: int = CANVAS_WIDTH):
        if engine is None:
            # Existing font resolution order:
            # ELINA_FONT_PRIMARY_PATH -> (repo has no bundled font asset)
            try:
                engine = TypographyEngine()
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"{SUBTITLE_FONT_NOT_FOUND}: no Persian-capable font available "
                    f"(set ELINA_FONT_PRIMARY_PATH to a valid .ttf/.otf); {exc}"
                ) from exc
        self.engine = engine
        self.canvas_width = canvas_width

    # --- Measurement helpers (mirror TypographyEngine's own metrics) ---

    def _prepare_line(self, line: str) -> str:
        """Apply the same per-line preparation the engine uses in fallback mode."""
        if self.engine.active_render_mode == "fallback":
            return self.engine._prepare_text_fallback(line)
        return line

    def _line_metrics(
        self,
        draw: ImageDraw.ImageDraw,
        font: ImageFont.FreeTypeFont,
        line: str,
        stroke_width: int = 0,
    ) -> Tuple[float, float]:
        # Measured with the SAME stroke_width used for rendering so the
        # canvas sizing matches TypographyEngine's own overflow checks.
        if self.engine.active_render_mode == "raqm":
            bbox = draw.textbbox(
                (0, 0), line, font=font, direction="rtl", language="fa",
                stroke_width=stroke_width,
            )
        else:
            bbox = draw.textbbox((0, 0), self._prepare_line(line), font=font, stroke_width=stroke_width)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def wrap_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: float,
        stroke_width: int = 2,
    ) -> List[str]:
        """Word-wrap text so every line (as shaped for rendering) fits max_width."""
        probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        lines: List[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            width, _ = self._line_metrics(draw, font, candidate, stroke_width=stroke_width)
            if not current or width <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def render(self, entry: SubtitleEntry, output_path: str) -> str:
        """
        Render one subtitle entry to a transparent RGBA PNG with a
        semi-transparent rounded background box behind the shaped RTL text.
        Returns the output path.
        """
        preset = STYLE_PRESETS.get(entry.style, {})
        font_size = max(24, min(120, int(round(entry.font_size * preset.get("font_size_factor", 1.0)))))
        stroke_width = int(preset.get("stroke_width", 2))
        background_opacity = float(preset.get("background_opacity", entry.background_opacity))
        background_color = _hex_to_rgb(preset.get("background_color", entry.background_color))
        font_color = _hex_to_rgb(entry.font_color)

        try:
            font = ImageFont.truetype(self.engine.font_path, font_size)
        except IOError as exc:
            raise RuntimeError(
                f"{SUBTITLE_FONT_NOT_FOUND}: failed to load font '{self.engine.font_path}': {exc}"
            ) from exc

        max_width = entry.max_width_ratio * self.canvas_width
        lines = self.wrap_text(entry.text, font, max_width, stroke_width=stroke_width)

        probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        line_heights: List[float] = []
        max_line_w = 0.0
        for line in lines:
            w, h = self._line_metrics(draw, font, line, stroke_width=stroke_width)
            line_heights.append(h + 10)  # same 10px spacing as TypographyEngine
            max_line_w = max(max_line_w, w)

        pad = max(12, int(font_size * 0.5))
        total_h = sum(line_heights)
        # 5% width buffer absorbs minor shaping-drift between measurement and
        # the engine's own textbbox pass; padding forms the background box margin.
        canvas_w = int(max_line_w * 1.05) + 2 * pad
        canvas_h = int(total_h) + 2 * pad

        text_layer_path = output_path + ".text.png"
        try:
            self.engine.render_text_to_png(
                text="\n".join(lines),
                output_path=text_layer_path,
                font_size=font_size,
                canvas_size=(canvas_w, canvas_h),
                color=font_color + (255,),
                stroke_width=int(preset.get("stroke_width", 2)),
                stroke_color=(0, 0, 0, 255),
                safe_margin=pad,
            )
            text_layer = Image.open(text_layer_path).convert("RGBA")

            bg = Image.new("RGBA", text_layer.size, (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg)
            radius = min(18, min(bg.size) // 5)
            bg_draw.rounded_rectangle(
                [0, 0, bg.size[0] - 1, bg.size[1] - 1],
                radius=radius,
                fill=background_color + (int(round(background_opacity * 255)),),
            )
            final = Image.alpha_composite(bg, text_layer)
            final.save(output_path, "PNG")
        finally:
            if os.path.exists(text_layer_path):
                os.unlink(text_layer_path)

        logger.info(
            "Rendered subtitle '%s' (%d lines) to %s", entry.text[:40], len(lines), output_path
        )
        return output_path
