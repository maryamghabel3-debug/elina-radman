"""Kinetic typography for the V2 motion engine.

All Persian text goes through text.prepare_persian (arabic-reshaper +
python-bidi); direction="rtl" is never used (no raqm in this Pillow build).
Words are laid out right-to-left manually so staggered reveals preserve
Persian reading order. Every entrance includes motion (scale pop, slide,
blur decay or wipe) plus an alpha fade - static text does not exist here.
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config, keyframes as kf
from .text import _font, prepare_persian, wrap_persian, _block_geometry

_CLAUSE_SPLIT = re.compile(r"[.؟!؛,،]")


def subtitle_chunking(text: str, max_words: int = 6) -> List[str]:
    """Split narration into 3-6 word cues, preferring clause boundaries."""
    cues: List[str] = []
    for clause in _CLAUSE_SPLIT.split(text or ""):
        words = clause.split()
        if not words:
            continue
        for i in range(0, len(words), max_words):
            chunk = " ".join(words[i:i + max_words]).strip()
            if chunk:
                cues.append(chunk)
    return cues


# --------------------------------------------------------------------------
# Low-level transformed text layers
# --------------------------------------------------------------------------
def _measure(word: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    img = Image.new("RGBA", (8, 8))
    box = ImageDraw.Draw(img).textbbox((0, 0), prepare_persian(word), font=font)
    return box[2] - box[0], box[3] - box[1]


def text_layer(text: str, font: ImageFont.FreeTypeFont, color,
               blur: float = 0.0) -> Image.Image:
    """Tight RGBA layer containing one shaped text run."""
    visual = prepare_persian(text)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    box = probe.textbbox((0, 0), visual, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    pad = int(max(10, blur * 3)) + 8
    layer = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((pad - box[0], pad - box[1]), visual,
                               font=font, fill=(*color, 255))
    if blur > 0.2:
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))
    return layer


def _paste(layer: Image.Image, frame: Image.Image, cx: float, cy: float,
           scale: float, alpha: float, rotation: float = 0.0) -> None:
    if alpha <= 0.01:
        return
    if scale != 1.0:
        nw = max(1, int(layer.width * scale))
        nh = max(1, int(layer.height * scale))
        layer = layer.resize((nw, nh), Image.LANCZOS)
    if rotation:
        layer = layer.rotate(rotation, expand=True, resample=Image.BICUBIC)
    if alpha < 0.999:
        a = layer.getchannel("A").point(lambda v: int(v * kf.clamp01(alpha)))
        layer.putalpha(a)
    frame.alpha_composite(layer, (int(cx - layer.width / 2),
                                  int(cy - layer.height / 2)))


def _rtl_slots(words: Sequence[str], font: ImageFont.FreeTypeFont,
               center_x: float, gap: int = 14) -> List[Tuple[str, float, int]]:
    """Return (word, slot_center_x, width) laid out right-to-left."""
    widths = [_measure(w, font)[0] for w in words]
    total = sum(widths) + gap * (len(words) - 1)
    right = center_x + total / 2
    slots = []
    cursor = right
    for word, width in zip(words, widths):
        slot_cx = cursor - width / 2
        slots.append((word, slot_cx, width))
        cursor -= width + gap
    return slots


# --------------------------------------------------------------------------
# Entrance / exit primitives
# --------------------------------------------------------------------------
def word_burst(frame: Image.Image, text: str, center: Tuple[float, float],
               t: float, start: float, font, color,
               stagger: float = 0.11, entrance: float = 0.55,
               rise: int = 30) -> bool:
    """Staggered overshoot pop + rise + fade, RTL word order."""
    words = text.split()
    slots = _rtl_slots(words, font, center[0])
    active = False
    for i, (word, cx, _w) in enumerate(slots):
        local = t - (start + i * stagger)
        if local < 0:
            continue
        active = True
        p = kf.clamp01(local / entrance)
        scale = 0.55 + 0.45 * kf.ease_out_back(p)
        alpha = kf.ease_out_quad(p)
        cy = center[1] + (1 - kf.ease_out_cubic(p)) * rise
        _paste(text_layer(word, font, color), frame, cx, cy, scale, alpha)
    return active


def phrase_reveal(frame: Image.Image, text: str,
                  center: Tuple[float, float], t: float, start: float,
                  font, color, mode: str = "slide",
                  duration: float = 0.7, stagger: float = 0.09) -> bool:
    """Phrase entrance with slide / fade / blur-in / wipe variants."""
    words = text.split()
    slots = _rtl_slots(words, font, center[0])
    active = False
    for i, (word, cx, _w) in enumerate(slots):
        local = t - (start + i * stagger)
        if local < 0:
            continue
        active = True
        p = kf.clamp01(local / duration)
        e = kf.ease_out_cubic(p)
        if mode == "fade":
            _paste(text_layer(word, font, color), frame, cx, center[1],
                   1.0, e)
        elif mode == "blur":
            blur = 10.0 * (1 - e)
            _paste(text_layer(word, font, color, blur=blur), frame, cx,
                   center[1], 0.96 + 0.04 * e, e)
        elif mode == "wipe":
            layer = text_layer(word, font, color)
            reveal = int(layer.width * e)
            if reveal <= 0:
                continue
            # RTL: reveal from the right edge of the layer.
            cropped = layer.crop((layer.width - reveal, 0,
                                  layer.width, layer.height))
            frame.alpha_composite(cropped,
                                  (int(cx - layer.width / 2 + layer.width - reveal),
                                   int(center[1] - layer.height / 2)))
        else:  # slide (default): rises from below
            cy = center[1] + (1 - e) * 36
            _paste(text_layer(word, font, color), frame, cx, cy,
                   0.92 + 0.08 * kf.ease_out_back(p), e)
    return active


def emphasis_pulse(frame: Image.Image, text: str,
                   center: Tuple[float, float], t: float, start: float,
                   font, color, peak_scale: float = 1.12,
                   duration: float = 0.75) -> bool:
    """Impact word: overshoot pop to peak_scale then settle to persistent 1.0."""
    if t < start:
        return False
    p = kf.clamp01((t - start) / duration)
    if p < 1.0:
        # Quick overshoot then settle.
        scale = 1.0 + (peak_scale - 1.0) * math_sin_bump(p)
        alpha = kf.ease_out_quad(min(1.0, p * 2.2))
    else:
        scale, alpha = 1.0, 1.0
    _paste(text_layer(text, font, color), frame, center[0], center[1],
           scale, alpha)
    return True


def math_sin_bump(p: float) -> float:
    import math
    return math.sin(min(1.0, p) * math.pi)


def text_exit(frame: Image.Image, text: str, center: Tuple[float, float],
              t: float, start: float, font, color,
              duration: float = 0.35, drift: int = 40) -> bool:
    """Fade + upward drift used when a phrase must leave before the next."""
    if t < start:
        phrase_reveal(frame, text, center, t, start - 1.0, font, color,
                      mode="fade", duration=0.4)
        return True
    p = kf.clamp01((t - start) / duration)
    if p >= 1.0:
        return False
    _paste(text_layer(text, font, color), frame, center[0],
           center[1] - drift * kf.ease_in_cubic(p), 1.0, 1.0 - p)
    return True


def type_on(frame: Image.Image, text: str, center: Tuple[float, float],
            t: float, start: float, font, color,
            duration: float = 0.9) -> bool:
    """Word-by-word type-on (keeps Persian shaping intact per word)."""
    words = text.split()
    n = max(1, int(kf.clamp01((t - start) / duration) * len(words)))
    shown = " ".join(words[:n])
    if not shown:
        return False
    slots = _rtl_slots(words[:n], font, center[0])
    last_cx = slots[-1][1]
    _paste(text_layer(shown, font, color), frame, center[0], center[1],
           1.0, kf.ease_out_quad(kf.clamp01((t - start) / 0.25)))
    # Blinking caret near the latest (leftmost) word.
    import math
    if int((t - start) * 2) % 2 == 0 and n < len(words):
        caret_x = last_cx - _measure(words[n - 1], font)[0] / 2 - 10
        d = ImageDraw.Draw(frame)
        d.rounded_rectangle([caret_x - 3, center[1] - font.size * 0.55,
                             caret_x + 3, center[1] + font.size * 0.55],
                            radius=3, fill=(*color, 220))
    return True


# --------------------------------------------------------------------------
# Clean, light subtitle style (no heavy pill; reference-style readability)
# --------------------------------------------------------------------------
def draw_subtitle_clean(frame: Image.Image, text: str) -> None:
    if not text or not text.strip():
        return
    style = config.SUBTITLE_STYLE
    lines = wrap_persian(text, style["font_path"], style["max_width"],
                         start_size=style["font_size"],
                         min_size=style["min_font_size"],
                         line_spacing=style["line_spacing"])
    if not lines:
        return
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    block_w, block_h = _block_geometry(probe, lines, style["font_path"],
                                       style["line_spacing"])
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    pad_x, pad_y = 26, 14
    x0 = (config.WIDTH - block_w) / 2 - pad_x
    y0 = 1712 - block_h / 2 - pad_y
    od.rounded_rectangle([x0, y0, x0 + block_w + 2 * pad_x,
                          y0 + block_h + 2 * pad_y],
                         radius=18, fill=(8, 10, 24, 120))
    frame.alpha_composite(overlay)
    d = ImageDraw.Draw(frame)
    y = 1712 - block_h / 2
    for line, size in lines:
        font = _font(str(style["font_path"]), size)
        visual = prepare_persian(line)
        box = d.textbbox((0, 0), visual, font=font)
        x = (config.WIDTH - (box[2] - box[0])) / 2 - box[0]
        d.text((x, y - box[1]), visual, font=font,
               fill=config.COLORS["text"])
        y += size * style["line_spacing"]
