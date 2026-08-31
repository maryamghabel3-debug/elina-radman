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

Only standard library + Pillow + existing typography utilities are used.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from agents.editing.typography_engine import TypographyEngine
from agents.carousel.brand_theme import TemplateTheme, get_template, hex_to_rgb, palette_rgb
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
            except FileNotFoundError as exc:
                raise CarouselFontError(
                    "no Persian-capable font available "
                    "(set ELINA_FONT_PRIMARY_PATH to a valid .ttf/.otf)"
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

        font, lines, size = self._fit_block(draw, slide.title, text_width, H * 0.37,
                                            theme.title_size, theme.min_title_size, 4)
        block_h = len(lines) * size * LINE_SPACING
        title_y = H * 0.31
        self._draw_block(draw, lines, font, size, title_y, text_width, center_x=center_x, fill=text_fill)

        rule_y = title_y + block_h + int(round(H * 0.03))
        self._accent_rule(draw, rule_y, center_x, accent)

        if slide.body:
            body_font, body_lines, body_size = self._fit_block(
                draw, slide.body, text_width, H * 0.14,
                theme.body_size, theme.min_body_size, 2,
            )
            self._draw_block(draw, body_lines, body_font, body_size, rule_y + H * 0.05,
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

        title_font, title_lines, title_size = self._fit_block(
            draw, slide.title, text_width, H * 0.27, theme.title_size, theme.min_title_size, 3)
        title_bottom = self._draw_block(draw, title_lines, title_font, title_size, H * 0.20,
                                        text_width, right_edge=text_right, fill=text_fill)

        rule_y = title_bottom + int(round(H * 0.03))
        self._accent_rule(draw, rule_y, text_right - (W * RULE_WIDTH_FRAC) / 2, accent)

        body_font, body_lines, body_size = self._fit_block(
            draw, slide.body, text_width, H * 0.36, theme.body_size, theme.min_body_size, 7)
        self._draw_block(draw, body_lines, body_font, body_size, rule_y + H * 0.05,
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
        font, lines, size = self._fit_block(
            draw, slide.title, text_width, H * 0.52,
            max(64, int(theme.title_size * 0.75)), max(44, int(theme.min_title_size * 0.8)), 6)
        block_h = len(lines) * size * LINE_SPACING
        quote_y = H * 0.22 + (H * 0.52 - block_h) / 2
        self._draw_block(draw, lines, font, size, quote_y, text_width,
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

        title_font, title_lines, title_size = self._fit_block(
            draw, slide.title, text_width, H * 0.18,
            int(theme.title_size * 0.85), theme.min_title_size, 2)
        title_bottom = self._draw_block(draw, title_lines, title_font, title_size, H * 0.15,
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
        accent = palette_rgb(slide.accent)
        text_fill = palette_rgb(theme.text)
        text_width = W - 2 * M

        # Deterministic split: image region top 65%, text panel bottom 35%
        image_h = int(round(H * 0.65))
        self._place_cover_image(img, self._load_image(slide.image_path), 0, 0, W, image_h,
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

        title_font, title_lines, title_size = self._fit_block(
            draw, slide.title, text_width, panel_h * 0.30,
            int(theme.title_size * 0.62), max(30, int(theme.min_title_size * 0.6)), 2)
        title_bottom = self._draw_block(draw, title_lines, title_font, title_size, title_y,
                                        text_width, right_edge=text_right, fill=text_fill)

        if slide.body:
            rule_y = title_bottom + int(round(panel_h * 0.04))
            self._accent_rule(draw, rule_y, text_right - (W * RULE_WIDTH_FRAC) / 2, accent)
            body_font, body_lines, body_size = self._fit_block(
                draw, slide.body, text_width, panel_h * 0.34,
                int(theme.body_size * 0.85), max(26, int(theme.min_body_size * 0.75)), 3)
            self._draw_block(draw, body_lines, body_font, body_size, rule_y + panel_h * 0.05,
                             text_width, right_edge=text_right, fill=text_fill)

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
        font, lines, size = self._fit_block(draw, slide.title, text_width, H * 0.20,
                                            max(theme.title_size, 100), theme.min_title_size, 2)
        block_h = len(lines) * size * LINE_SPACING
        title_y = H * 0.36
        self._draw_block(draw, lines, font, size, title_y, text_width, center_x=center_x, fill=text_fill)

        rule_y = title_y + block_h + int(round(H * 0.03))
        self._accent_rule(draw, rule_y, center_x, accent)

        if slide.body:
            body_font, body_lines, body_size = self._fit_block(
                draw, slide.body, text_width, H * 0.10,
                theme.body_size, theme.min_body_size, 2)
            self._draw_block(draw, body_lines, body_font, body_size, rule_y + H * 0.05,
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
