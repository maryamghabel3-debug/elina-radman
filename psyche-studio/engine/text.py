"""Persian text shaping, wrapping and frame drawing.

ARCHITECTURE CONSTRAINT (verified in probe A/B):
  * libraqm is NOT available in this Pillow build, so direction="rtl"
    raises KeyError and must never be used.
  * The only supported path is:
        arabic-reshaper (delete_harakat=False) -> python-bidi -> plain draw
  * delete_harakat=False is mandatory: the default config silently drops
    Persian diacritics (e.g. the kasra in روشِ).
  * ZWNJ (U+200C) is consumed into glyph forms during reshape; its visual
    effect (preventing joins, as in نیمه‌تمام) is preserved.
  * Persian (۰-۹) and Western (0-9) digits pass through unchanged and are
    positioned correctly by the bidi algorithm.
"""
from functools import lru_cache
from typing import List, Optional, Tuple, Union

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

from . import config

# One reshaper instance, configured to keep harakat (kasra/ezafe/etc.).
_RESHAPER = arabic_reshaper.ArabicReshaper(
    configuration={"delete_harakat": False}
)

Position = Union[str, Tuple[float, float]]


def prepare_persian(text: str) -> str:
    """Return the visual-order string Pillow can draw with a plain LTR call.

    Safe on empty/whitespace input. Never combine the result with
    direction="rtl" — that double-reverses the text.
    """
    if not text:
        return ""
    reshaped = _RESHAPER.reshape(text)
    return get_display(reshaped)


@lru_cache(maxsize=64)
def _font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path), size)


def _line_width(text: str, font_path, size: int) -> int:
    """Width of a logical Persian text line after shaping/bidi."""
    visual = prepare_persian(text)
    img = Image.new("RGB", (8, 8))
    return ImageDraw.Draw(img).textlength(visual, font=_font(str(font_path), size))


def wrap_persian(
    text: str,
    font_path,
    max_width: int,
    start_size: int = 64,
    min_size: int = 32,
    line_spacing: float = 1.4,
) -> List[Tuple[str, int]]:
    """Wrap Persian text to fit ``max_width``, auto-shrinking the font.

    Returns a list of ``(logical_line_text, font_size)`` tuples. Wrapping is
    done on the *logical* text (word boundaries), width is measured on the
    shaped visual form. If a single word is too wide even at ``min_size`` it
    is hard-split on characters.
    """
    text = (text or "").strip()
    if not text:
        return []

    def greedy(size: int) -> List[str]:
        words = text.split()
        lines: List[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if _line_width(candidate, font_path, size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    size = start_size
    while size >= min_size:
        lines = greedy(size)
        if all(_line_width(line, font_path, size) <= max_width for line in lines):
            return [(line, size) for line in lines]
        size -= 2

    # At the minimum size, hard-split any still-overflowing line on chars.
    final_lines: List[str] = []
    for line in greedy(min_size):
        if _line_width(line, font_path, min_size) <= max_width:
            final_lines.append(line)
            continue
        current = ""
        for ch in line:
            candidate = ch if not current else current + ch
            if _line_width(candidate, font_path, min_size) <= max_width:
                current = candidate
            else:
                final_lines.append(current)
                current = ch
        if current:
            final_lines.append(current)
    return [(line, min_size) for line in final_lines]


def _block_geometry(
    draw: ImageDraw.ImageDraw,
    lines: List[Tuple[str, int]],
    font_path,
    line_spacing: float,
) -> Tuple[int, int]:
    """Total (width, height) of a multi-line text block."""
    width = 0
    height = 0
    for line, size in lines:
        font = _font(str(font_path), size)
        visual = prepare_persian(line)
        box = draw.textbbox((0, 0), visual, font=font)
        width = max(width, box[2] - box[0])
        height += int(size * line_spacing)
    return width, height


def draw_text_on_frame(
    frame: Image.Image,
    text: str,
    font_path,
    size: int,
    position: Position,
    color,
    align: str = "center",
    line_spacing: float = 1.4,
) -> None:
    """Draw a (possibly multi-line) Persian text block onto ``frame`` in place.

    ``position`` may be a keyword ("top", "center", "bottom") or an exact
    ``(x, y)`` tuple. With a tuple, ``align`` decides what the point anchors:
    "center" -> block centre, "right"/"left" -> that horizontal edge, and the
    y is the block top in all edge cases.
    """
    if not text:
        return
    logical_lines = text.split("\n")
    lines = [(line, size) for line in logical_lines if line.strip()]
    if not lines:
        return

    draw = ImageDraw.Draw(frame)
    block_w, block_h = _block_geometry(draw, lines, font_path, line_spacing)

    if position == "top":
        anchor_x, anchor_y = config.WIDTH / 2, 170
        align = "center"
    elif position == "bottom":
        anchor_x, anchor_y = config.WIDTH / 2, config.HEIGHT - 380
        align = "center"
    elif position == "center":
        anchor_x, anchor_y = config.WIDTH / 2, config.HEIGHT / 2
        align = "center"
    else:
        anchor_x, anchor_y = float(position[0]), float(position[1])

    if align == "center":
        top = anchor_y - block_h / 2
    else:
        top = anchor_y

    y = top
    for line, line_size in lines:
        font = _font(str(font_path), line_size)
        visual = prepare_persian(line)
        box = draw.textbbox((0, 0), visual, font=font)
        line_w = box[2] - box[0]
        if align == "center":
            x = anchor_x - line_w / 2 - box[0]
        elif align == "right":
            x = anchor_x - line_w - box[0]
        else:  # "left"
            x = anchor_x - box[0]
        draw.text((x, y - box[1]), visual, font=font, fill=color)
        y += line_size * line_spacing


def draw_subtitle(frame: Image.Image, text: str) -> None:
    """Burn a subtitle in the bottom safe area with a translucent dark box.

    Auto-wraps via :func:`wrap_persian` and always goes through
    :func:`prepare_persian` for shaping.
    """
    if not text or not text.strip():
        return
    style = config.SUBTITLE_STYLE
    lines = wrap_persian(
        text,
        style["font_path"],
        style["max_width"],
        start_size=style["font_size"],
        min_size=style["min_font_size"],
        line_spacing=style["line_spacing"],
    )
    if not lines:
        return

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    # Measure the block to size the background box.
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    block_w, block_h = _block_geometry(
        probe, lines, style["font_path"], style["line_spacing"]
    )
    pad_x, pad_y = style["padding_x"], style["padding_y"]
    box_w = block_w + pad_x * 2
    box_h = block_h + pad_y * 2
    x0 = (config.WIDTH - box_w) / 2
    y0 = style["center_y"] - box_h / 2
    x1, y1 = x0 + box_w, y0 + box_h

    odraw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=style["box_radius"],
        fill=(*style["box_color"], style["box_opacity"]),
    )
    frame_rgba = frame.convert("RGBA")
    frame_rgba.alpha_composite(overlay)

    # Draw the text itself on the composited frame.
    y = style["center_y"] - block_h / 2
    draw = ImageDraw.Draw(frame_rgba)
    for line, size in lines:
        font = _font(str(style["font_path"]), size)
        visual = prepare_persian(line)
        box = draw.textbbox((0, 0), visual, font=font)
        line_w = box[2] - box[0]
        x = (config.WIDTH - line_w) / 2 - box[0]
        draw.text((x, y - box[1]), visual, font=font, fill=style["text_color"])
        y += size * style["line_spacing"]

    # Propagate pixels back into the caller's frame (RGB).
    frame.paste(frame_rgba.convert("RGB"), (0, 0))
