"""
Deterministic static carousel slide renderer (M18A).

Renders branded Persian carousel slides (1080x1350 PNG) with Pillow:

- Persian RTL typography reuses the existing TypographyEngine shaping
  (libraqm when available, arabic-reshaper + python-bidi fallback) and its
  font resolution (ELINA_FONT_PRIMARY_PATH). Naive text reversal is never
  used.
- Brand Book V2 palettes/templates come from brand_theme.py.
- Source images are cover-cropped (aspect preserved, never stretched) with
  a dark gradient overlay behind text.
- Text is wrapped deterministically and auto-shrunk within configured
  minimums; if it still cannot fit, CAROUSEL_TEXT_OVERFLOW is raised.
- Default starting font sizes are reduced (M26) so everyday decks do not
  need manual size=0.75; text_scale still multiplies the starts.
- Slide titles/bodies support per-word inline styling (M26):
  [word|color=#B89B65] / [word|size=1.3] / [word|color=#B89B65,size=1.3].
  Unmarked text renders byte-identically to the plain path; malformed
  markup falls back to plain (with a warning).

Only standard library + Pillow + numpy + existing typography utilities
are used.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from agents.editing.typography_engine import TypographyEngine
from agents.editing.font_resolver import FontNotFoundError
from agents.carousel.brand_theme import TemplateTheme, get_template, hex_to_rgb, palette_rgb
from agents.carousel.text_zone import (
    ZONE_GRID_PRIORITY,
    ZONES_3x3,
    cell_scores,
    find_best_text_zone,
    zone_luminance,
)
from agents.carousel.inline_styles import (
    TextSegment,  # noqa: F401  (re-exported for callers/tests)
    has_inline_styles,
    parse_inline_styles,
)
from agents.carousel.schema import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DEFAULT_TEMPLATE,
    CarouselConfigError,
    CarouselFontError,
    CarouselImageError,
    CarouselRenderError,
    CarouselSlide,
    CarouselTextOverflowError,
    parse_carousel_slide,
)

logger = logging.getLogger(__name__)

# Strong RTL codepoint ranges (Arabic, Arabic Supplement, presentation forms)
_RTL_RANGES = (
    (0x0600, 0x06FF),   # Arabic + Arabic Supplement
    (0x0750, 0x077F),   # Arabic extended (Persian-specific letters)
    (0xFB50, 0xFDFF),   # Arabic Presentation Forms A/B
    (0xFE70, 0xFEFF),   # Arabic Presentation Forms - Extended
)


def _is_rtl_line(text: str) -> bool:
    """True if the line contains any strong RTL character.

    LTR-dominant lines (handles like '@elina', digits, Latin) are drawn
    left-to-right instead of being forced into RTL paragraph order.
    """
    for ch in text:
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _RTL_RANGES):
            return True
    return False

# Layout constants (fractions of the canvas so any canvas size works;
# values are tuned for the canonical 1080x1350 carousel canvas).
MARGIN_FRAC = 0.083          # safe margin on all sides (~90px @1080)
LINE_SPACING = 1.3           # vertical line pitch as a multiple of font size
FONT_STEP = 4                # auto-shrink step (px at 1080 canvas)
MIN_ABS_SIZE = 12            # never shrink below this (px at 1080 canvas)
RULE_WIDTH_FRAC = 0.14       # accent rule width
RULE_THICKNESS = 4


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Scale `img` to cover the target box and center-crop.

    Preserves the source aspect ratio and never stretches: the scale factor
    is max(target_w/src_w, target_h/src_h), then the center region is kept.
    """
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _vertical_gradient(width: int, height: int, top_alpha: float, bottom_alpha: float,
                       color: Tuple[int, int, int] = (16, 16, 20)) -> Image.Image:
    """A vertical dark gradient overlay (for readability behind text)."""
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    top_alpha = max(0.0, min(1.0, top_alpha))
    bottom_alpha = max(0.0, min(1.0, bottom_alpha))
    for y in range(height):
        t = y / max(1, height - 1)
        alpha = round(255 * (top_alpha + (bottom_alpha - top_alpha) * t))
        draw.line([(0, y), (width, y)], fill=(color[0], color[1], color[2], alpha))
    return overlay


def _middle_band_gradient(width: int, height: int, peak_alpha: float,
                          color: Tuple[int, int, int] = (16, 16, 20)) -> Image.Image:
    """A horizontal band gradient: transparent at both ends, peaking in the
    middle (for middle-zone captions, M23)."""
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    peak_alpha = max(0.0, min(1.0, peak_alpha))
    for y in range(height):
        t = y / max(1, height - 1)
        alpha = round(255 * peak_alpha * (1.0 - abs(2.0 * t - 1.0)))
        draw.line([(0, y), (width, y)], fill=(color[0], color[1], color[2], alpha))
    return overlay


def _local_gradient(width: int, height: int, direction: str, peak_alpha: float,
                    color: Tuple[int, int, int] = (16, 16, 20)) -> Image.Image:
    """A localized readability patch sized to a text block + padding (M25):
    transparent-to-peak vertical gradient. direction: "top" (peak at the
    top edge), "bottom" (peak at the bottom edge), "middle" (peak in the
    center)."""
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    peak_alpha = max(0.0, min(1.0, peak_alpha))
    for y in range(height):
        t = y / max(1, height - 1)
        if direction == "top":
            a = peak_alpha * (1.0 - t)
        elif direction == "bottom":
            a = peak_alpha * t
        else:
            a = peak_alpha * (1.0 - abs(2.0 * t - 1.0))
        alpha = round(255 * a)
        draw.line([(0, y), (width, y)], fill=(color[0], color[1], color[2], alpha))
    return overlay


# Carousel aspect ratio (4:5) used by the "auto" image_layout choice (M22A)
CANVAS_ASPECT_RATIO = CANVAS_WIDTH / CANVAS_HEIGHT
# Relative tolerance: sources within +/-10% of the canvas ratio are
# full-bleed; wider/taller sources are letterboxed instead.
AUTO_FULL_BLEED_TOLERANCE = 0.10


def choose_auto_image_layout(source_w: int, source_h: int) -> str:
    """Deterministic "auto" choice for image_text slides (M22A).

    A source close to the carousel ratio (1080x1350 = 4:5) loses little to a
    cover crop -> "full_bleed_caption". A very wide or very tall source
    would lose too much of the photo -> "contain_caption" (letterboxed,
    nothing cropped).
    """
    if source_w <= 0 or source_h <= 0:
        raise CarouselConfigError("source image size must be positive")
    src_aspect = source_w / source_h
    if abs(src_aspect - CANVAS_ASPECT_RATIO) <= AUTO_FULL_BLEED_TOLERANCE * CANVAS_ASPECT_RATIO:
        return "full_bleed_caption"
    return "contain_caption"


# ---------------------------------------------------------------------------
# M25 text composition: zone geometry + rebalanced photo typography
# ---------------------------------------------------------------------------

# Block width fractions by zone kind (M25): center zones get 70% of the
# canvas, side/corner zones are limited to 45% and anchored to their side.
_CENTER_ZONE_FRAC = 0.70
_SIDE_ZONE_FRAC = 0.45
# M26: reduced default starting sizes — operators no longer need to send
# size=0.75 for everyday decks. text_scale still multiplies these
# starting sizes (behavior unchanged).
# Photo-slide title (full_bleed_caption / image_overlay / composed cover):
# ~25% smaller than the M25 default (104 * 0.78 = 81 on psychological_dark
# -> 104 * 0.585 = 60).
_COMP_TITLE_FACTOR = 0.585
# Photo-slide body: 64% of the reduced title start size — keeps the
# title/body balance inside the 60-65% target range (54 -> 38 on
# psychological_dark).
_COMP_BODY_RATIO = 0.64
# Legacy cover (no composition options): ~25% smaller title and ~15%
# smaller body than the M18A theme defaults (104/46 -> 78/39).
_COVER_TITLE_FACTOR = 0.75
_COVER_BODY_FACTOR = 0.85
# Readability patch padding around the text block (canvas fractions)
_PATCH_PADDING_FRAC = 0.04
# Per-part fit limits (canvas height fractions, max 3 lines each)
_TITLE_MAX_HEIGHT_FRAC = 0.28
_BODY_MAX_HEIGHT_FRAC = 0.20
_TOP_ZONE_Y_FRAC = 0.08
# Blend-mode (M25) dual soft shadow: light halo + dark outline alphas
_BLEND_LIGHT_HALO = (245, 243, 238, 60)
_BLEND_DARK_SHADOW = (12, 12, 16, 110)

# Zone geometry: every addressable zone maps to a grid row (top/middle/
# bottom) and a grid column (left/center/right).
_ZONE_ROW_OF = {zone: zone.split("_")[0] for zone in ZONES_3x3}
_ZONE_ROW_OF.update({"top": "top", "middle": "middle", "bottom": "bottom"})
_ZONE_COL_OF = {zone: zone.split("_")[1] for zone in ZONES_3x3}
# Row zones span the center column; column zones sit in the middle row.
_ZONE_COL_OF.update({"top": "center", "middle": "center", "bottom": "center",
                     "left": "left", "right": "right"})
_ZONE_ROW_OF.update({"left": "middle", "right": "middle"})
_ROW_IDX = {"top": 0, "middle": 1, "bottom": 2}
_COL_IDX = {"left": 0, "center": 1, "right": 2}


def _zone_row(zone: str) -> str:
    return _ZONE_ROW_OF[zone]


def _zone_col(zone: str) -> str:
    return _ZONE_COL_OF[zone]


def _zone_is_side(zone: str) -> bool:
    return _ZONE_COL_OF[zone] in ("left", "right")


def _cells_adjacent(a: str, b: str) -> bool:
    """True when two grid cells share an edge (diagonals are allowed)."""
    ra, ca = _ROW_IDX[_zone_row(a)], _COL_IDX[_zone_col(a)]
    rb, cb = _ROW_IDX[_zone_row(b)], _COL_IDX[_zone_col(b)]
    return abs(ra - rb) + abs(ca - cb) == 1


@dataclass
class TextFit:
    """Result of CarouselSlideRenderer._fit_text (M26).

    plain=True: the legacy wrapped text (font/lines/size) — rendered
    byte-identically through _draw_block. plain=False: an inline-styled
    layout (rich_lines: list of lines, each a list of
    (text, color, eff_size, width) units).
    """

    plain: bool
    size: int
    height: float
    font: Optional[Any] = None
    lines: Optional[List[str]] = None
    rich_lines: Optional[List[List[Tuple[str, Optional[str], int, float]]]] = None


class CarouselSlideRenderer:
    """Renders CarouselSlide objects to deterministic branded PNG files."""

    def __init__(
        self,
        engine: Optional[TypographyEngine] = None,
        font_path: Optional[str] = None,
        canvas_size: Optional[Tuple[int, int]] = None,
    ):
        # Font resolution reuses the existing typography system:
        # explicit font_path > ELINA_FONT_PRIMARY_PATH.
        if engine is None:
            try:
                engine = TypographyEngine(font_path=font_path)
            except (FileNotFoundError, FontNotFoundError) as exc:
                raise CarouselFontError(
                    "no Persian-capable font available "
                    "(check ELINA_FONT_PRIMARY_PATH or the bundled "
                    "assets/fonts/Vazirmatn-Bold.ttf)"
                ) from exc
        self.engine = engine
        self.canvas_size = tuple(canvas_size) if canvas_size else (CANVAS_WIDTH, CANVAS_HEIGHT)
        self._scale = self.canvas_size[0] / CANVAS_WIDTH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, slide: "CarouselSlide | Dict[str, Any]", output_path: str) -> str:
        """Render one slide to a PNG at output_path. Returns output_path."""
        if isinstance(slide, dict):
            slide = parse_carousel_slide(slide)
        elif not isinstance(slide, CarouselSlide):
            raise CarouselConfigError("slide must be a CarouselSlide or a dict")
        if not isinstance(output_path, str) or not output_path.lower().endswith(".png"):
            raise CarouselConfigError("output_path must end with .png")

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        try:
            img = self.build_slide(slide)
            # Final output: sRGB-compatible 8-bit RGB PNG
            img.convert("RGB").save(output_path, "PNG")
            return output_path
        except (CarouselConfigError, CarouselImageError, CarouselFontError, CarouselTextOverflowError):
            raise
        except Exception as exc:
            raise CarouselRenderError(f"slide render failed: {exc}") from exc

    def build_slide(self, slide: CarouselSlide) -> Image.Image:
        """Build the slide as an in-memory RGBA image (used by render/tests)."""
        if not isinstance(slide, CarouselSlide):
            raise CarouselConfigError("build_slide expects a parsed CarouselSlide")
        # template=None means "no explicit choice": inherit (deck) or fall
        # back to the default template when rendering a standalone slide.
        theme = get_template(slide.template or DEFAULT_TEMPLATE)
        W, H = self.canvas_size
        M = max(24, round(W * MARGIN_FRAC))

        img = Image.new("RGBA", (W, H), palette_rgb(theme.background) + (255,))
        draw = ImageDraw.Draw(img)

        text_right = W - M
        text_width = W - 2 * M

        if slide.slide_type == "cover":
            self._layout_cover(draw, img, slide, theme, W, H, M)
        elif slide.slide_type == "title_body":
            self._layout_title_body(draw, img, slide, theme, W, H, M, text_right, text_width)
        elif slide.slide_type == "quote":
            self._layout_quote(draw, img, slide, theme, W, H, M, text_right)
        elif slide.slide_type == "bullet_list":
            self._layout_bullet_list(draw, img, slide, theme, W, H, M, text_right, text_width)
        elif slide.slide_type == "image_text":
            self._layout_image_text(draw, img, slide, theme, W, H, M, text_right, text_width)
        elif slide.slide_type == "image_overlay":
            self._layout_image_overlay(draw, img, slide, theme, W, H, M)
        elif slide.slide_type == "cta":
            self._layout_cta(draw, img, slide, theme, W, H, M, text_width)
        else:  # pragma: no cover - guarded by parse_carousel_slide
            raise CarouselConfigError(f"unknown slide_type '{slide.slide_type}'")

        self._draw_footer(draw, slide, theme, W, H, M)
        return img

    # ------------------------------------------------------------------
    # Text measurement / layout primitives (stroke/shape-aware)
    # ------------------------------------------------------------------

    def _line_layout(self, draw: ImageDraw.ImageDraw, line: str, font) -> Tuple[str, float, Dict[str, str]]:
        """Return (prepared_text, width, draw-kwargs) for one line, matching
        exactly what TypographyEngine renders (raqm or fallback).

        LTR-dominant lines (no strong RTL characters) are measured/drawn
        plain so handles like '@elina' are not reordered by the RTL engine.
        """
        if not _is_rtl_line(line):
            width = draw.textlength(line, font=font)
            return line, width, {}
        if self.engine.active_render_mode == "raqm":
            width = draw.textlength(line, font=font, direction="rtl", language="fa")
            return line, width, {"direction": "rtl", "language": "fa"}
        prepared = self.engine._prepare_text_fallback(line)
        width = draw.textlength(prepared, font=font)
        return prepared, width, {}

    def _line_height(self, draw: ImageDraw.ImageDraw, line: str, font) -> int:
        if not _is_rtl_line(line):
            bbox = draw.textbbox((0, 0), line, font=font)
        elif self.engine.active_render_mode == "raqm":
            bbox = draw.textbbox((0, 0), line, font=font, direction="rtl", language="fa")
        else:
            bbox = draw.textbbox((0, 0), self.engine._prepare_text_fallback(line), font=font)
        return bbox[3] - bbox[1]

    def wrap_text(self, text: str, font_size: int, max_width: float) -> List[str]:
        """Deterministic word wrap (public for tests/tooling)."""
        probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        font = ImageFont.truetype(self.engine.font_path, font_size)
        words = (text or "").split()
        lines: List[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or self._line_layout(draw, candidate, font)[1] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _fit_block(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: float,
        max_height: float,
        start_size: int,
        min_size: int,
        max_lines: int,
    ) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
        """
        Fit `text` into max_width x max_height with at most max_lines,
        shrinking the font by FONT_STEP until it fits or min_size is hit.
        Returns (font, wrapped_lines, size); raises CarouselTextOverflowError
        if the text cannot fit at the minimum size.
        """
        start_size = max(min_size, int(round(start_size * self._scale)))
        min_size = max(int(MIN_ABS_SIZE * self._scale), int(round(min_size * self._scale)))
        step = max(2, int(round(FONT_STEP * self._scale)))

        size = start_size
        while size > min_size:
            font = ImageFont.truetype(self.engine.font_path, size)
            lines = self.wrap_text(text, size, max_width)
            if len(lines) <= max_lines and len(lines) * size * LINE_SPACING <= max_height:
                return font, lines, size
            size -= step

        font = ImageFont.truetype(self.engine.font_path, min_size)
        lines = self.wrap_text(text, min_size, max_width)
        if len(lines) <= max_lines and len(lines) * min_size * LINE_SPACING <= max_height:
            return font, lines, min_size
        raise CarouselTextOverflowError(
            f"text '{text[:40]}...' does not fit: needs {len(lines)} lines at "
            f"{min_size}px in a {int(max_width)}x{int(max_height)} box (max {max_lines} lines)"
        )

    def _draw_block(
        self,
        draw: ImageDraw.ImageDraw,
        lines: List[str],
        font,
        size: int,
        y: float,
        region_width: float,
        right_edge: Optional[float] = None,
        center_x: Optional[float] = None,
        fill: Tuple[int, int, int] = (255, 255, 255),
        stroke_width: int = 0,
        stroke_fill: Optional[Tuple[int, int, int]] = None,
    ) -> float:
        """Draw wrapped lines (RTL-aware). Right-aligns when right_edge is
        given (RTL document flow), otherwise centers in the region.
        Returns the y position below the block."""
        pitch = size * LINE_SPACING
        cursor_y = y
        for line in lines:
            prepared, width, kwargs = self._line_layout(draw, line, font)
            if right_edge is not None:
                x = right_edge - width
            elif center_x is not None:
                x = center_x - width / 2
            else:
                x = region_width
            draw.text(
                (x, cursor_y), prepared, font=font, fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
                **kwargs,
            )
            cursor_y += pitch
        return cursor_y

    # ------------------------------------------------------------------
    # M26 inline-styled ("rich") text: [word|color=#RRGGBB,size=1.3]
    # ------------------------------------------------------------------

    def _fit_text(self, draw: ImageDraw.ImageDraw, text: str, max_width: float,
                  max_height: float, start_size: int, min_size: int,
                  max_lines: int) -> "TextFit":
        """Like _fit_block, but understands M26 inline markup.

        Without markup this delegates to _fit_block (byte-identical
        rendering); with valid styled segments it lays the text out as
        inline units, auto-shrinking the BASE size with the same overflow
        protection."""
        if not has_inline_styles(text):
            font, lines, size = self._fit_block(draw, text, max_width, max_height,
                                                start_size, min_size, max_lines)
            return TextFit(plain=True, size=size,
                           height=len(lines) * size * LINE_SPACING,
                           font=font, lines=lines)
        segments = parse_inline_styles(text)
        laid, size = self._fit_rich(draw, text, segments, max_width, max_height,
                                    start_size, min_size, max_lines)
        height = sum(max(u[2] for u in line) * LINE_SPACING for line in laid)
        return TextFit(plain=False, size=size, height=height, rich_lines=laid)

    def _fit_rich(self, draw: ImageDraw.ImageDraw, text: str,
                  segments: List[TextSegment], max_width: float, max_height: float,
                  start_size: int, min_size: int, max_lines: int):
        """Auto-shrink the BASE size until the styled units fit into
        max_width x max_height with at most max_lines (same protection as
        _fit_block). Returns (lines, size) where each line is a list of
        (text, color, eff_size, width) units."""
        start_size = max(min_size, int(round(start_size * self._scale)))
        min_size = max(int(MIN_ABS_SIZE * self._scale), int(round(min_size * self._scale)))
        step = max(2, int(round(FONT_STEP * self._scale)))

        def _fits(size: int):
            laid = self._rich_layout(draw, segments, size, max_width)
            if laid is None:
                return None
            if len(laid) > max_lines:
                return None
            height = sum(max(u[2] for u in line) * LINE_SPACING for line in laid)
            if height > max_height:
                return None
            return laid

        size = start_size
        while True:
            laid = _fits(size)
            if laid is not None:
                return laid, size
            if size <= min_size:
                break
            size -= step
        laid = _fits(min_size)
        if laid is not None:
            return laid, min_size
        n = len(self._rich_layout(draw, segments, min_size, max_width) or [])
        raise CarouselTextOverflowError(
            f"text '{(text or '')[:40]}...' does not fit: needs {n} lines at "
            f"{min_size}px in a {int(max_width)}x{int(max_height)} box (max {max_lines} lines)"
        )

    def _rich_units(self, draw: ImageDraw.ImageDraw, segments: List[TextSegment],
                    size: int, max_width: float):
        """Flatten styled segments into drawable units, word-splitting a
        styled phrase that is wider than max_width. Returns the unit list
        ((text, color, eff_size, width)), or None when a single word still
        does not fit."""
        units = []
        for seg in segments:
            if not seg.text:
                continue
            eff_size = max(1, int(round(size * seg.size_multiplier)))
            font = ImageFont.truetype(self.engine.font_path, eff_size)
            width = self._line_layout(draw, seg.text, font)[1]
            if width <= max_width:
                units.append([seg.text, seg.color, eff_size, width])
                continue
            words = [w for w in seg.text.split(" ") if w]
            for i, word in enumerate(words):
                word_width = self._line_layout(draw, word, font)[1]
                if word_width > max_width:
                    return None
                if i > 0:  # keep the intra-phrase word spacing
                    sp_width = self._line_layout(draw, " ", font)[1]
                    units.append([" ", None, eff_size, sp_width])
                units.append([word, seg.color, eff_size, word_width])
        return units

    def _rich_layout(self, draw: ImageDraw.ImageDraw, segments: List[TextSegment],
                     size: int, max_width: float):
        """Flow the styled units into lines that fit max_width (a styled
        segment that does not fit wraps to the next line). Returns the
        trimmed line list, or None when no layout exists at this size."""
        units = self._rich_units(draw, segments, size, max_width)
        if units is None:
            return None
        lines = []
        cur = []
        cur_w = 0.0
        for unit in units:
            if cur and cur_w + unit[3] > max_width:
                lines.append(cur)
                cur = []
                cur_w = 0.0
            cur.append(unit)
            cur_w += unit[3]
        if cur:
            lines.append(cur)
        trimmed = []
        for line in lines:
            while line and line[0][0] == " ":
                line = line[1:]
            while line and line[-1][0] == " ":
                line = line[:-1]
            if line:
                trimmed.append(line)
        return trimmed or None

    def _draw_rich(self, draw: ImageDraw.ImageDraw, laid, y: float, region_width: float,
                   right_edge: Optional[float] = None, center_x: Optional[float] = None,
                   fill: Tuple[int, int, int] = (255, 255, 255)) -> float:
        """Draw a rich layout: units flow right-to-left (RTL); each unit is
        shaped and drawn with its own font size and color (default `fill`
        when the unit has no override). Mirrors _draw_block alignment
        semantics. Returns the y position below the block."""
        cursor_y = y
        for line in laid:
            total_w = sum(u[3] for u in line)
            if right_edge is not None:
                x_cursor = right_edge
            elif center_x is not None:
                x_cursor = center_x + total_w / 2
            else:
                x_cursor = region_width
            for text, color, eff_size, width in line:
                font = ImageFont.truetype(self.engine.font_path, eff_size)
                prepared, _, kwargs = self._line_layout(draw, text, font)
                x = x_cursor - width
                unit_fill = hex_to_rgb(color) if color is not None else fill
                draw.text((x, cursor_y), prepared, font=font, fill=unit_fill, **kwargs)
                x_cursor -= width
            cursor_y += max(u[2] for u in line) * LINE_SPACING
        return cursor_y

    def _draw_fit(self, draw: ImageDraw.ImageDraw, fit: "TextFit", y: float,
                  region_width: float, right_edge: Optional[float] = None,
                  center_x: Optional[float] = None,
                  fill: Tuple[int, int, int] = (255, 255, 255),
                  stroke_width: int = 0,
                  stroke_fill: Optional[Tuple[int, int, int]] = None) -> float:
        """Draw a TextFit: plain -> the exact M18A path (byte-identical);
        rich -> the M26 inline-styled path."""
        if not fit.plain:
            return self._draw_rich(draw, fit.rich_lines, y, region_width,
                                   right_edge=right_edge, center_x=center_x, fill=fill)
        return self._draw_block(draw, fit.lines, fit.font, fit.size, y, region_width,
                                right_edge=right_edge, center_x=center_x, fill=fill,
                                stroke_width=stroke_width, stroke_fill=stroke_fill)

    def _draw_rich_composed(self, draw, laid, y: float, x0: int, width: int,
                            align: str, center_x: float, fill,
                            blend: bool, ldraw=None) -> float:
        """Draw a rich layout with the M25 composition alignment (center /
        right-anchored / left-anchored blocks) and, in blend mode, the
        dual soft shadow per unit. Returns the y below the block."""
        cursor_y = y
        for line in laid:
            total_w = sum(u[3] for u in line)
            if align == "center":
                x_cursor = center_x + total_w / 2
            else:  # right / left_anchored: lines right-aligned in the block
                x_cursor = x0 + width
            for text, color, eff_size, unit_w in line:
                font = ImageFont.truetype(self.engine.font_path, eff_size)
                prepared, _, kwargs = self._line_layout(draw, text, font)
                x = x_cursor - unit_w
                unit_fill = hex_to_rgb(color) if color is not None else fill
                if blend:
                    self._draw_blend_text(ldraw, x, cursor_y, prepared, font,
                                          eff_size, unit_fill, kwargs)
                else:
                    draw.text((x, cursor_y), prepared, font=font,
                              fill=unit_fill, **kwargs)
                x_cursor -= unit_w
            cursor_y += max(u[2] for u in line) * LINE_SPACING
        return cursor_y

    def _accent_rule(self, draw: ImageDraw.ImageDraw, y: float, center_x: float,
                     accent: Tuple[int, int, int], width_frac: float = RULE_WIDTH_FRAC):
        """Restrained accent rule (thin, short — gold kept restrained)."""
        w = max(24, int(round(self.canvas_size[0] * width_frac)))
        draw.rectangle([center_x - w / 2, y, center_x + w / 2, y + RULE_THICKNESS], fill=accent)

    # ------------------------------------------------------------------
    # Image handling
    # ------------------------------------------------------------------

    def _load_image(self, path: str) -> Image.Image:
        if not path or not os.path.exists(path):
            raise CarouselImageError(f"image not found: {path}")
        try:
            img = Image.open(path)
            img.load()
            if img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGB")
            return img
        except CarouselImageError:
            raise
        except Exception as exc:
            raise CarouselImageError(f"could not load image '{path}': {exc}") from exc

    def _place_cover_image(self, img: Image.Image, source: Image.Image,
                           x: int, y: int, w: int, h: int, overlay_alpha: float,
                           gradient: bool = True):
        """Cover-crop `source` into the (x, y, w, h) box and optionally add a
        dark gradient (or flat) overlay for text readability."""
        cropped = _cover_crop(source, w, h).convert("RGBA")
        img.alpha_composite(cropped, (x, y))
        if overlay_alpha > 0:
            if gradient:
                overlay = _vertical_gradient(w, h, overlay_alpha * 0.7, overlay_alpha + 0.18)
            else:
                overlay = Image.new("RGBA", (w, h), (16, 16, 20, round(255 * min(0.92, overlay_alpha))))
            img.alpha_composite(overlay, (x, y))

    # ------------------------------------------------------------------
    # Per-type layouts (all coordinates are canvas fractions -> deterministic)
    # ------------------------------------------------------------------

    def _layout_cover(self, draw, img, slide: CarouselSlide, theme: TemplateTheme, W, H, M):
        # M25: a cover with any composition option (text_zone auto/explicit,
        # title/body zone, blend style, or a manual text scale) uses the same
        # composition path as photo slides; otherwise the legacy layout is
        # kept byte-identical (pre-M25 output).
        if slide.image_path and not self._cover_is_legacy(slide):
            source = self._load_image(slide.image_path)
            self._place_cover_image(img, source, 0, 0, W, H,
                                    theme.overlay_alpha, gradient=True)
            self._render_composition(draw, img, slide, theme, W, H, M, source)
            return

        accent = palette_rgb(slide.accent)
        if slide.image_path:
            self._place_cover_image(img, self._load_image(slide.image_path), 0, 0, W, H,
                                    theme.overlay_alpha, gradient=True)
            text_fill = palette_rgb(theme.text)
        else:
            text_fill = palette_rgb(theme.text)

        text_width = W - 2 * M
        center_x = W / 2

        if slide.eyebrow:
            size = max(20, int(round(34 * self._scale)))
            font = ImageFont.truetype(self.engine.font_path, size)
            self._draw_block(draw, [slide.eyebrow], font, size, H * 0.235, text_width,
                             center_x=center_x, fill=accent)

        title_fit = self._fit_text(draw, slide.title, text_width, H * 0.37,
                                   int(round(theme.title_size * _COVER_TITLE_FACTOR)),
                                   theme.min_title_size, 4)
        block_h = title_fit.height
        title_y = H * 0.31
        self._draw_fit(draw, title_fit, title_y, text_width, center_x=center_x, fill=text_fill)

        rule_y = title_y + block_h + int(round(H * 0.03))
        self._accent_rule(draw, rule_y, center_x, accent)

        if slide.body:
            body_fit = self._fit_text(
                draw, slide.body, text_width, H * 0.14,
                int(round(theme.body_size * _COVER_BODY_FACTOR)),
                theme.min_body_size, 2,
            )
            self._draw_fit(draw, body_fit, rule_y + H * 0.05,
                           text_width, center_x=center_x,
                           fill=palette_rgb(theme.secondary_text))

    def _layout_title_body(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                           W, H, M, text_right, text_width):
        accent = palette_rgb(slide.accent)
        text_fill = palette_rgb(theme.text)

        # Eyebrow with a short accent mark at the RTL (right) edge
        if slide.eyebrow:
            size = max(20, int(round(32 * self._scale)))
            font = ImageFont.truetype(self.engine.font_path, size)
            bar_w = int(round(W * 0.055))
            draw.rectangle([text_right - bar_w, H * 0.125, text_right, H * 0.125 + RULE_THICKNESS], fill=accent)
            self._draw_block(draw, [slide.eyebrow], font, size, H * 0.15, text_width,
                             right_edge=text_right, fill=accent)
        else:
            bar_w = int(round(W * 0.055))
            draw.rectangle([text_right - bar_w, H * 0.13, text_right, H * 0.13 + RULE_THICKNESS], fill=accent)

        title_fit = self._fit_text(
            draw, slide.title, text_width, H * 0.27, theme.title_size, theme.min_title_size, 3)
        title_bottom = self._draw_fit(draw, title_fit, H * 0.20,
                                      text_width, right_edge=text_right, fill=text_fill)

        rule_y = title_bottom + int(round(H * 0.03))
        self._accent_rule(draw, rule_y, text_right - (W * RULE_WIDTH_FRAC) / 2, accent)

        body_fit = self._fit_text(
            draw, slide.body, text_width, H * 0.36, theme.body_size, theme.min_body_size, 7)
        self._draw_fit(draw, body_fit, rule_y + H * 0.05,
                       text_width, right_edge=text_right, fill=text_fill)

    def _layout_quote(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                      W, H, M, text_right):
        accent = palette_rgb(slide.accent)
        text_fill = palette_rgb(theme.text)
        # Restrained vertical accent line at the RTL edge
        line_x = text_right
        draw.rectangle([line_x, H * 0.22, line_x + RULE_THICKNESS, H * 0.52], fill=accent)

        right_edge = text_right - int(round(W * 0.05))
        text_width = right_edge - M
        quote_fit = self._fit_text(
            draw, slide.title, text_width, H * 0.52,
            max(64, int(theme.title_size * 0.75)), max(44, int(theme.min_title_size * 0.8)), 6)
        block_h = quote_fit.height
        quote_y = H * 0.22 + (H * 0.52 - block_h) / 2
        self._draw_fit(draw, quote_fit, quote_y, text_width,
                       right_edge=right_edge, fill=text_fill)

        if slide.footer:
            size = max(20, int(round(34 * self._scale)))
            font = ImageFont.truetype(self.engine.font_path, size)
            self._draw_block(draw, [slide.footer], font, size, H * 0.79, text_width,
                             right_edge=right_edge, fill=palette_rgb(theme.secondary_text))

    def _layout_bullet_list(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                            W, H, M, text_right, text_width):
        accent = palette_rgb(slide.accent)
        text_fill = palette_rgb(theme.text)

        title_fit = self._fit_text(
            draw, slide.title, text_width, H * 0.18,
            int(theme.title_size * 0.85), theme.min_title_size, 2)
        title_bottom = self._draw_fit(draw, title_fit, H * 0.15,
                                      text_width, right_edge=text_right, fill=text_fill)
        rule_y = title_bottom + int(round(H * 0.025))
        self._accent_rule(draw, rule_y, text_right - (W * RULE_WIDTH_FRAC) / 2, accent)

        bullets_top = rule_y + int(round(H * 0.045))
        region_h = H * 0.72 - bullets_top
        right_edge = text_right - int(round(W * 0.045))
        bullet_width = right_edge - M

        # Fit each bullet (start -> min), then verify the stack fits.
        fits = []
        for bullet in slide.bullets:
            font, lines, size = self._fit_block(
                draw, bullet, bullet_width, 10 ** 9, theme.body_size, theme.min_body_size, 2)
            fits.append((font, lines, size))

        spacing = int(round(H * 0.028))
        total_h = sum(len(lines) * size * LINE_SPACING for _, lines, size in fits) + spacing * (len(fits) - 1)
        if total_h > region_h:
            raise CarouselTextOverflowError(
                f"{len(slide.bullets)} bullets do not fit in the slide at minimum sizes "
                f"(need {int(total_h)}px, have {int(region_h)}px)"
            )

        y = bullets_top
        marker = max(8, int(round(12 * self._scale)))
        for (font, lines, size), bullet in zip(fits, slide.bullets):
            # Bullet marker at the RTL edge, aligned with the first line
            draw.rectangle([right_edge - marker, y + size * 0.35,
                            right_edge, y + size * 0.35 + marker], fill=accent)
            y = self._draw_block(draw, lines, font, size, y, bullet_width,
                                 right_edge=right_edge - marker - int(round(W * 0.02)),
                                 fill=text_fill) + spacing

    def _layout_image_text(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                           W, H, M, text_right, text_width):
        """image_text dispatcher (M22A): routes on slide.image_layout.

        None / "split_panel" -> legacy 65/35 layout (byte-identical to the
        M18A implementation, so stored decks render exactly as before);
        "full_bleed_caption" / "contain_caption" -> photo-preserving
        layouts; "auto" -> deterministic aspect-based choice.
        """
        source = self._load_image(slide.image_path)
        layout = self._resolve_image_layout(slide, source.size)
        if layout == "full_bleed_caption":
            self._layout_full_bleed_caption(draw, img, slide, theme, W, H, M, source)
        elif layout == "contain_caption":
            self._layout_contain_caption(draw, img, slide, theme, W, H, M, source)
        else:
            self._layout_split_panel(draw, img, slide, theme, W, H, M,
                                     text_right, text_width, source)

    def _resolve_image_layout(self, slide: CarouselSlide, source_size: Tuple[int, int]) -> str:
        """Effective image_text layout for a slide (deterministic)."""
        layout = slide.image_layout or "split_panel"
        if layout == "auto":
            return choose_auto_image_layout(*source_size)
        return layout

    # ------------------------------------------------------------------
    # M25 text composition (full_bleed_caption / image_overlay / cover)
    # ------------------------------------------------------------------

    def _cover_is_legacy(self, slide: CarouselSlide) -> bool:
        """M25: a cover with NO composition option set keeps the legacy
        layout (byte-identical to pre-M25 output)."""
        return (
            slide.text_zone is None
            and slide.title_zone is None
            and slide.body_zone is None
            and (slide.text_style or "gradient") == "gradient"
            and (slide.text_scale if slide.text_scale is not None else 1.0) == 1.0
        )

    def _resolve_part_zones(self, slide: CarouselSlide, source: Image.Image):
        """Resolve the title/body zones for a composition slide (M25).

        Precedence: an explicit title_zone/body_zone wins for its part;
        slide.text_zone is the fallback for both. When both parts fall
        back to auto, two least-busy NON-ADJACENT grid cells are chosen
        (the title gets the higher/more prominent one); a single part
        falls back to a single auto-detected zone.
        """
        tz = slide.title_zone if slide.title_zone is not None else slide.text_zone
        bz = slide.body_zone if slide.body_zone is not None else slide.text_zone
        tz_auto = tz in (None, "auto")
        bz_auto = bz in (None, "auto")
        has_title = bool(slide.title)
        has_body = bool(slide.body)

        t_z = b_z = None
        if tz_auto and bz_auto and has_title and has_body:
            t_z, b_z = self._auto_split_zones(source)
        else:
            if has_title:
                t_z = tz if not tz_auto else find_best_text_zone(source)
            if has_body:
                b_z = bz if not bz_auto else find_best_text_zone(source)
        return t_z, b_z

    def _auto_split_zones(self, source: Image.Image) -> Tuple[str, str]:
        """Pick the two least-busy non-adjacent grid cells for the
        title/body split (M25). The title gets the higher/more prominent
        cell (top row first; ties by grid tie-break priority)."""
        scores = cell_scores(source)
        cells = list(ZONES_3x3)
        best = None
        for i in range(len(cells)):
            for j in range(i + 1, len(cells)):
                a, b = cells[i], cells[j]
                if _cells_adjacent(a, b):
                    continue
                key = (scores[a] + scores[b],
                       ZONE_GRID_PRIORITY[a], ZONE_GRID_PRIORITY[b])
                if best is None or key < best[0]:
                    best = (key, a, b)
        a, b = best[1], best[2]
        ra, rb = _ROW_IDX[_zone_row(a)], _ROW_IDX[_zone_row(b)]
        if rb < ra or (rb == ra and ZONE_GRID_PRIORITY[b] < ZONE_GRID_PRIORITY[a]):
            a, b = b, a
        return a, b

    def _render_composition(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                            W, H, M, source: Image.Image):
        """M25: place title/body (each in its own zone) with localized
        readability treatments — a small gradient patch sized to the text
        block (gradient style) or a soft dual shadow (blend style)."""
        t_z, b_z = self._resolve_part_zones(slide, source)
        self._render_caption_parts(draw, img, slide, theme, W, H, M, source, t_z, b_z)

    def _caption_block_box(self, zone: str, W: int, H: int, M: int,
                           block_w: int, block_h: int):
        """(x0, y0, align) for a caption block in `zone`. align:
        "center" (centered), "right" (right-anchored, lines right-aligned),
        "left_anchored" (left-anchored block, lines still right-aligned
        for RTL reading order)."""
        row = _zone_row(zone)
        col = _zone_col(zone)
        if row == "top":
            y0 = int(round(H * _TOP_ZONE_Y_FRAC))
        elif row == "bottom":
            footer_size = max(18, int(round(30 * self._scale)))
            y0 = H - M - footer_size - int(round(H * 0.035)) - block_h
        else:
            y0 = (H - block_h) // 2
        if col == "left":
            x0 = M
            align = "left_anchored"
        elif col == "right":
            x0 = W - M - block_w
            align = "right"
        else:
            x0 = (W - block_w) // 2
            align = "center"
        return x0, y0, align

    @staticmethod
    def _block_line_x(align: str, x0: int, block_w: int, line_w: float,
                      center_x: float) -> float:
        if align == "center":
            return center_x - line_w / 2
        # right / left_anchored: lines right-aligned within the block
        return x0 + block_w - line_w

    def _blend_title_font_path(self) -> Optional[str]:
        """Blend mode uses a lighter title weight when a Regular Vazirmatn
        is bundled next to the primary font; otherwise keeps the primary
        (Bold) font."""
        primary = self.engine.font_path or ""
        d = os.path.dirname(primary)
        if not d:
            return None
        for name in ("Vazirmatn-Regular.ttf", "Vazirmatn-Regular.woff2",
                     "Vazirmatn-Variable.ttf", "Vazirmatn-Light.ttf"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
        return None

    def _draw_blend_text(self, ldraw: ImageDraw.ImageDraw, x: float, y: float,
                         prepared: str, font, size: int, fill, kwargs: Dict[str, str]):
        """Dual soft shadow for blend mode (M25): a light halo pass, a dark
        outline pass, then the text itself. Drawn on an RGBA layer so the
        semi-transparent strokes composite (Pillow only)."""
        light_w = max(6, size // 10)
        dark_w = max(2, size // 25)
        ldraw.text((x, y), prepared, font=font, fill=_BLEND_LIGHT_HALO,
                   stroke_width=light_w, stroke_fill=_BLEND_LIGHT_HALO, **kwargs)
        ldraw.text((x, y), prepared, font=font, fill=_BLEND_DARK_SHADOW,
                   stroke_width=dark_w, stroke_fill=_BLEND_DARK_SHADOW, **kwargs)
        ldraw.text((x, y), prepared, font=font,
                   fill=fill if len(fill) == 4 else fill + (255,), **kwargs)

    def _render_caption_parts(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                              W, H, M, source: Image.Image, title_zone, body_zone):
        """Render the caption parts. When title and body share a zone they
        are drawn as one stacked block (eyebrow + title + accent rule +
        body, single patch); otherwise each part gets its own zone, block
        and localized treatment (the eyebrow travels with the title, or
        with the body when there is no title)."""
        has_title = bool(slide.title)
        has_body = bool(slide.body)
        if has_title and has_body and title_zone == body_zone:
            self._render_caption_block(draw, img, slide, theme, W, H, M, source,
                                       title_zone, "stack")
        else:
            if has_title:
                self._render_caption_block(draw, img, slide, theme, W, H, M, source,
                                           title_zone, "title")
            if has_body:
                self._render_caption_block(draw, img, slide, theme, W, H, M, source,
                                           body_zone, "body")

    def _render_caption_block(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                              W, H, M, source: Image.Image, zone: str, which: str):
        """Fit + place one caption block (M25) in `zone`.

        which: "stack" (eyebrow+title+rule+body), "title" (eyebrow+title)
        or "body". Uses the reduced photo typography defaults (M26:
        title *0.585 of the theme size, body = 64% of the title start),
        scaled by slide.text_scale. Titles/bodies support M26 inline
        markup ([word|color=...,size=...])."""
        side = _zone_is_side(zone)
        width = int(round(W * (_SIDE_ZONE_FRAC if side else _CENTER_ZONE_FRAC)))
        text_scale = slide.text_scale if slide.text_scale is not None else 1.0
        style = slide.text_style or "gradient"
        accent = palette_rgb(slide.accent)
        gap = int(round(H * 0.02))
        blend = style == "blend"
        title_font_path = self._blend_title_font_path() if blend else None

        # M26 reduced defaults (text_scale still multiplies the starts)
        t_start = int(theme.title_size * _COMP_TITLE_FACTOR * text_scale)
        b_start = int(round(t_start * _COMP_BODY_RATIO))

        items: List[Tuple[str, Any, float]] = []  # (kind, payload, h)
        eyebrow = ""
        if which == "stack" or which == "title" or not slide.title:
            eyebrow = slide.eyebrow
        if eyebrow:
            eb_size = max(20, int(round(34 * self._scale)))
            items.append(("eyebrow", ([eyebrow],
                                       ImageFont.truetype(self.engine.font_path, eb_size),
                                       eb_size),
                          eb_size * LINE_SPACING))
        if which in ("stack", "title"):
            t_fit = self._fit_text(draw, slide.title, width,
                                   H * _TITLE_MAX_HEIGHT_FRAC,
                                   t_start, theme.min_title_size, 3)
            if title_font_path is not None and t_fit.plain:
                t_fit.font = ImageFont.truetype(title_font_path, t_fit.size)
            items.append(("title", t_fit, t_fit.height))
        if which in ("stack", "body"):
            b_fit = self._fit_text(draw, slide.body, width,
                                   H * _BODY_MAX_HEIGHT_FRAC,
                                   b_start, theme.min_body_size, 3)
            items.append(("body", b_fit, b_fit.height))
        if not items:
            return

        rule_h = RULE_THICKNESS if which == "stack" else 0
        total_h = sum(h for *_, h in items)
        if len(items) > 1:
            total_h += gap * (len(items) - 1)
        if rule_h:
            total_h += rule_h
        total_h = int(round(total_h))

        x0, y0, align = self._caption_block_box(zone, W, H, M, width, total_h)
        block_cx = x0 + width / 2
        center_x = W / 2

        # Localized readability treatment (gradient style only)
        if not blend:
            pad = int(round(H * _PATCH_PADDING_FRAC))
            px0 = max(0, x0 - pad)
            py0 = max(0, y0 - pad)
            pw = min(W - px0, width + 2 * pad)
            ph = min(H - py0, total_h + 2 * pad)
            peak = max(0.80, theme.overlay_alpha + 0.18)
            patch = _local_gradient(pw, ph, _zone_row(zone), peak)
            img.alpha_composite(patch, (px0, py0))

        # Colors
        if blend:
            zone_lum = zone_luminance(source, zone)
            zone_color = palette_rgb("bone_white") if zone_lum < 128 \
                else palette_rgb("ink_black")
            colors = {"eyebrow": accent, "title": zone_color, "body": zone_color}
        else:
            colors = {"eyebrow": accent,
                      "title": palette_rgb(theme.text),
                      "body": palette_rgb(theme.secondary_text)}

        layer = None
        ldraw = None
        if blend:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ldraw = ImageDraw.Draw(layer)
        target = ldraw if ldraw is not None else draw

        y = y0
        prev_kind = None
        for kind, payload, _ in items:
            if prev_kind is not None:
                if prev_kind == "title" and kind == "body" and rule_h:
                    self._accent_rule(target, y + gap, block_cx, accent)
                    y += gap * 2 + rule_h
                else:
                    y += gap
            if kind == "eyebrow":
                lines, font, size = payload
                for line in lines:
                    prepared, line_w, kwargs = self._line_layout(target, line, font)
                    x = self._block_line_x(align, x0, width, line_w, center_x)
                    if blend:
                        self._draw_blend_text(ldraw, x, y, prepared, font, size,
                                              colors[kind], kwargs)
                    else:
                        target.text((x, y), prepared, font=font,
                                    fill=colors[kind], **kwargs)
                    y += size * LINE_SPACING
            elif not payload.plain:
                y = self._draw_rich_composed(ldraw if blend else target,
                                             payload.rich_lines, y, x0, width,
                                             align, center_x, colors[kind],
                                             blend, ldraw)
            else:
                for line in payload.lines:
                    prepared, line_w, kwargs = self._line_layout(target, line,
                                                                 payload.font)
                    x = self._block_line_x(align, x0, width, line_w, center_x)
                    if blend:
                        self._draw_blend_text(ldraw, x, y, prepared, payload.font,
                                              payload.size, colors[kind], kwargs)
                    else:
                        target.text((x, y), prepared, font=payload.font,
                                    fill=colors[kind], **kwargs)
                    y += payload.size * LINE_SPACING
            prev_kind = kind
        if layer is not None:
            img.alpha_composite(layer)

    def _layout_split_panel(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                            W, H, M, text_right, text_width, source):
        """Legacy M18A layout: image region top 65%, opaque panel bottom 35%."""
        accent = palette_rgb(slide.accent)
        text_fill = palette_rgb(theme.text)
        text_width = W - 2 * M

        # Deterministic split: image region top 65%, text panel bottom 35%
        image_h = int(round(H * 0.65))
        self._place_cover_image(img, source, 0, 0, W, image_h,
                                theme.overlay_alpha * 0.55, gradient=True)
        panel = Image.new("RGBA", (W, H - image_h), palette_rgb(theme.background) + (255,))
        img.alpha_composite(panel, (0, image_h))

        panel_top = image_h
        panel_h = H - panel_top

        if slide.eyebrow:
            size = max(18, int(round(28 * self._scale)))
            font = ImageFont.truetype(self.engine.font_path, size)
            self._draw_block(draw, [slide.eyebrow], font, size, panel_top + panel_h * 0.10,
                             text_width, right_edge=text_right, fill=accent)
            title_y = panel_top + panel_h * 0.22
        else:
            title_y = panel_top + panel_h * 0.12

        title_fit = self._fit_text(
            draw, slide.title, text_width, panel_h * 0.30,
            int(theme.title_size * 0.62), max(30, int(theme.min_title_size * 0.6)), 2)
        title_bottom = self._draw_fit(draw, title_fit, title_y,
                                      text_width, right_edge=text_right, fill=text_fill)

        if slide.body:
            rule_y = title_bottom + int(round(panel_h * 0.04))
            self._accent_rule(draw, rule_y, text_right - (W * RULE_WIDTH_FRAC) / 2, accent)
            body_fit = self._fit_text(
                draw, slide.body, text_width, panel_h * 0.34,
                int(theme.body_size * 0.85), max(26, int(theme.min_body_size * 0.75)), 3)
            self._draw_fit(draw, body_fit, rule_y + panel_h * 0.05,
                           text_width, right_edge=text_right, fill=text_fill)

    def _layout_full_bleed_caption(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                                   W, H, M, source):
        """Full-bleed caption (M22A + M23 + M25): cover-crop the source
        across the full canvas (aspect preserved, never stretched), then
        the M25 composition — per-zone readability patches (or blend
        shadows), rebalanced typography, split title/body zones. No
        opaque text panel. Footer/slide number stay in their fixed bottom
        positions."""
        self._place_cover_image(img, source, 0, 0, W, H, theme.overlay_alpha, gradient=True)
        self._render_composition(draw, img, slide, theme, W, H, M, source)

    def _layout_contain_caption(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                                W, H, M, source):
        """Contain caption (M22A): the complete source image, uncropped and
        un-stretched, centered on the canvas; unused space is filled with a
        blurred + darkened version of the same image (Pillow only); a soft
        bottom gradient carries the caption (no opaque panel)."""
        # Background: blurred, darkened cover-crop of the same source
        bg = _cover_crop(source, W, H)
        if bg.mode != "RGB":
            bg = bg.convert("RGB")
        bg = bg.filter(ImageFilter.GaussianBlur(radius=max(4, int(round(W * 0.01)))))
        bg = Image.blend(bg, Image.new("RGB", bg.size, (16, 16, 20)), 0.45)
        img.alpha_composite(bg.convert("RGBA"))

        # Foreground: contain-fit (min scale -> no edge crop), centered
        src_w, src_h = source.size
        scale = min(W / src_w, H / src_h)
        fit_w = max(1, round(src_w * scale))
        fit_h = max(1, round(src_h * scale))
        fitted = source.resize((fit_w, fit_h), Image.LANCZOS)
        if fitted.mode != "RGBA":
            fitted = fitted.convert("RGBA")
        img.alpha_composite(fitted, ((W - fit_w) // 2, (H - fit_h) // 2))

        # contain_caption keeps bottom-only captions (M23 decision): its
        # letterbox already keeps the caption off the photo, and bottom is
        # the natural caption position — slide.text_zone is ignored here.
        self._draw_caption(draw, img, slide, theme, W, H, M, "bottom",
                           0.58 if slide.body else 0.46)

    def _draw_caption(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                      W, H, M, zone: str, gradient_frac: float):
        """Gradient + caption stack ([eyebrow] title [accent rule] body)
        inside the requested text zone (M23):

        - "bottom": soft gradient rising from the bottom edge, text
          bottom-aligned above the footer (the original M22 behavior).
        - "top": mirrored gradient from the top edge, text in the top safe
          area (eyebrow first, then title/body).
        - "middle": soft horizontal band gradient centered vertically,
          text centered in the band.

        Footer and slide number always stay in their fixed bottom
        positions (painted by _draw_footer)."""
        accent = palette_rgb(slide.accent)
        text_fill = palette_rgb(theme.text)
        text_width = W - 2 * M
        center_x = W / 2
        peak = max(0.80, theme.overlay_alpha + 0.18)

        gap = int(round(H * 0.02))
        stack: List[Tuple[str, Any, Any, int, float]] = []
        if slide.eyebrow:
            eb_size = max(20, int(round(34 * self._scale)))
            stack.append(("eyebrow", [slide.eyebrow],
                          ImageFont.truetype(self.engine.font_path, eb_size),
                          eb_size, eb_size * LINE_SPACING))
        if slide.title:
            ti_fit = self._fit_text(
                draw, slide.title, text_width, H * 0.25,
                theme.title_size, theme.min_title_size, 3)
            stack.append(("title", ti_fit, ti_fit.size, ti_fit.height))
        if slide.body:
            bo_fit = self._fit_text(
                draw, slide.body, text_width, H * 0.18,
                theme.body_size, theme.min_body_size, 3)
            stack.append(("body", bo_fit, bo_fit.size, bo_fit.height))

        total_h = sum(h for *_, h in stack)
        if len(stack) > 1:
            total_h += gap * (len(stack) - 1)
        if slide.title and slide.body:
            total_h += gap + RULE_THICKNESS  # accent rule between title and body

        if zone == "top":
            grad = _vertical_gradient(W, int(round(H * gradient_frac)), peak, 0.0)
            img.alpha_composite(grad, (0, 0))
            y = int(round(H * 0.08))
        elif zone == "middle":
            band_h = max(int(round(H * 0.25)),
                         int(round(total_h)) + 2 * int(round(H * 0.06)))
            grad = _middle_band_gradient(W, band_h, peak)
            img.alpha_composite(grad, (0, (H - band_h) // 2))
            y = (H - total_h) // 2
        else:  # "bottom" — original M22 behavior (byte-identical)
            bottom_h = int(round(H * gradient_frac))
            grad = _vertical_gradient(W, bottom_h, 0.0, peak)
            img.alpha_composite(grad, (0, H - bottom_h))
            # Block bottom sits above the footer line (same bottom zone as
            # the other types; _draw_footer paints footer + page number
            # below it).
            footer_size = max(18, int(round(30 * self._scale)))
            y = H - M - footer_size - int(round(H * 0.035)) - total_h

        for item in stack:
            kind = item[0]
            if kind == "eyebrow":
                _, lines, font, size, _ = item
                y = self._draw_block(draw, lines, font, size, y, text_width,
                                     center_x=center_x, fill=accent)
                y += gap
            elif kind == "title":
                _, fit, _, _ = item
                y = self._draw_fit(draw, fit, y, text_width,
                                   center_x=center_x, fill=text_fill)
                if slide.body:
                    self._accent_rule(draw, y + gap, center_x, accent)
                    y += gap * 2 + RULE_THICKNESS
            else:  # body
                _, fit, _, _ = item
                y = self._draw_fit(draw, fit, y, text_width, center_x=center_x,
                                   fill=palette_rgb(theme.secondary_text))

    def _layout_image_overlay(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                              W, H, M):
        """M22 full-bleed slide type — M25 composition path: full-bleed
        image (same cover crop as 'cover', aspect preserved, never
        stretched) + per-zone readability treatment. Same rendering as
        image_text's full_bleed_caption layout."""
        source = self._load_image(slide.image_path)
        self._place_cover_image(img, source, 0, 0, W, H,
                                theme.overlay_alpha, gradient=True)
        self._render_composition(draw, img, slide, theme, W, H, M, source)

    def _layout_cta(self, draw, img, slide: CarouselSlide, theme: TemplateTheme,
                    W, H, M, text_width):
        accent = palette_rgb(slide.accent)
        text_fill = palette_rgb(theme.text)
        center_x = W / 2

        if slide.eyebrow:
            size = max(20, int(round(32 * self._scale)))
            font = ImageFont.truetype(self.engine.font_path, size)
            self._draw_block(draw, [slide.eyebrow], font, size, H * 0.30, text_width,
                             center_x=center_x, fill=accent)

        # One clear action, centered
        title_fit = self._fit_text(draw, slide.title, text_width, H * 0.20,
                                   max(theme.title_size, 100), theme.min_title_size, 2)
        block_h = title_fit.height
        title_y = H * 0.36
        self._draw_fit(draw, title_fit, title_y, text_width, center_x=center_x, fill=text_fill)

        rule_y = title_y + block_h + int(round(H * 0.03))
        self._accent_rule(draw, rule_y, center_x, accent)

        if slide.body:
            body_fit = self._fit_text(
                draw, slide.body, text_width, H * 0.10,
                theme.body_size, theme.min_body_size, 2)
            self._draw_fit(draw, body_fit, rule_y + H * 0.05,
                           text_width, center_x=center_x,
                           fill=palette_rgb(theme.secondary_text))

    # ------------------------------------------------------------------
    # Footer / page number
    # ------------------------------------------------------------------

    def _draw_footer(self, draw, slide: CarouselSlide, theme: TemplateTheme, W, H, M):
        secondary = palette_rgb(theme.secondary_text)
        size = max(18, int(round(30 * self._scale)))
        font = ImageFont.truetype(self.engine.font_path, size)
        y = H - M - size
        # For quote slides the footer is the author/source line and is already
        # placed with the quote; the bottom zone then carries only the page
        # number (no duplicated text).
        if slide.footer and slide.slide_type != "quote":
            prepared, width, kwargs = self._line_layout(draw, slide.footer, font)
            draw.text((W - M - width, y), prepared, font=font, fill=secondary, **kwargs)
        if slide.slide_number is not None:
            # Page numbers are plain LTR digits, bottom-left
            draw.text((M, y), str(slide.slide_number), font=font, fill=secondary)
