"""Scene builders for vertical 1080x1920 Persian motion graphics.

Every scene is a pure function ``(background, ..., t, duration) -> PIL.Image``
so the renderer can sample arbitrary frames. Time-based effects (Ken Burns
zoom, staggered fades, slides) are all derived from ``t`` — no animation
library is required.

Text shaping always goes through engine.text (reshaper + bidi), never
through Pillow's raqm-only direction="rtl".
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
from PIL import Image, ImageDraw

from . import config, text

Background = Union[str, Path, Image.Image]


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------
def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _smoothstep(a: float) -> float:
    a = _clamp01(a)
    return a * a * (3 - 2 * a)


@lru_cache(maxsize=16)
def _cover_cached(path: str) -> Image.Image:
    """Open an image and center-crop/resize it to the 1080x1920 canvas.

    AI-generated inputs may arrive at e.g. 941x1672; LANCZOS upscaling keeps
    the upscale path identical to the verified probe-F pipeline.
    """
    img = Image.open(path).convert("RGB")
    return _cover(img)


def _cover(img: Image.Image) -> Image.Image:
    w, h = img.size
    target_ratio = config.WIDTH / config.HEIGHT
    src_ratio = w / h
    if src_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    if img.size != (config.WIDTH, config.HEIGHT):
        img = img.resize((config.WIDTH, config.HEIGHT), Image.LANCZOS)
    return img


def _base_frame(background: Background) -> Image.Image:
    if isinstance(background, (str, Path)):
        return _cover_cached(str(background)).copy()
    return _cover(background.convert("RGB"))


def ken_burns(base: Image.Image, progress: float,
              zoom_start: float = 1.0, zoom_end: float = 1.08) -> Image.Image:
    """Center zoom from zoom_start to zoom_end over ``progress`` in 0..1."""
    zoom = zoom_start + (zoom_end - zoom_start) * _clamp01(progress)
    w, h = base.size
    cw, ch = w / zoom, h / zoom
    left, top = (w - cw) / 2, (h - ch) / 2
    cropped = base.crop((left, top, left + cw, top + ch))
    return cropped.resize((config.WIDTH, config.HEIGHT), Image.LANCZOS)


@lru_cache(maxsize=4)
def _vertical_gradient(start_frac: float, max_alpha: int) -> Image.Image:
    """RGBA overlay: transparent above start_frac, darkening toward bottom."""
    alpha = np.zeros((config.HEIGHT, config.WIDTH), dtype=np.uint8)
    for y in range(config.HEIGHT):
        if y >= config.HEIGHT * start_frac:
            k = (y - config.HEIGHT * start_frac) / (
                config.HEIGHT * (1 - start_frac)
            )
            alpha[y, :] = int(max_alpha * _smoothstep(k))
    rgb = np.zeros((config.HEIGHT, config.WIDTH, 3), dtype=np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def _composite(base: Image.Image, overlay: Image.Image) -> Image.Image:
    out = base.convert("RGBA")
    out.alpha_composite(overlay)
    return out


def _alpha_layer() -> Image.Image:
    return Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))


def _fade_in(t: float, start: float, length: float) -> float:
    return _smoothstep((t - start) / length) if length > 0 else 1.0


def _draw_text_alpha(overlay: Image.Image, caption: str, font_path, size: int,
                     position, color, alpha: float,
                     align: str = "center", line_spacing: float = 1.4) -> None:
    """Draw text onto an RGBA overlay at a given global alpha."""
    if alpha <= 0 or not caption:
        return
    layer = _alpha_layer()
    text.draw_text_on_frame(
        layer, caption, font_path, size, position,
        (*color, int(255 * _clamp01(alpha))), align=align,
        line_spacing=line_spacing,
    )
    overlay.alpha_composite(layer)


# --------------------------------------------------------------------------
# Scene a) hook
# --------------------------------------------------------------------------
def scene_hook(background: Background, headline: str,
               t: float, duration: float) -> Image.Image:
    base = ken_burns(_base_frame(background), t / max(duration, 1e-6))
    frame = _composite(base, _vertical_gradient(0.35, 190))
    overlay = _alpha_layer()
    alpha = _fade_in(t, 0.0, 1.5)
    # Headline: auto-fit within a 160px side margin.
    lines = text.wrap_persian(
        headline, config.FONT_BLACK, config.WIDTH - 160,
        start_size=72, min_size=40,
    )
    block = "\n".join(line for line, _ in lines)
    size = lines[0][1] if lines else 64
    _draw_text_alpha(overlay, block, config.FONT_BLACK, size,
                     (config.WIDTH / 2, config.HEIGHT * 0.62),
                     config.COLORS["text"], alpha)
    return _composite(frame, overlay).convert("RGB")


# --------------------------------------------------------------------------
# Scene b) thought bubbles
# --------------------------------------------------------------------------
_BUBBLE_SLOTS = [
    (0.27, 0.20), (0.73, 0.27), (0.25, 0.36),
    (0.75, 0.66), (0.27, 0.75), (0.72, 0.82),
]


def scene_bubbles(background: Background, center_text: str,
                  bubbles: List[Union[str, Dict]], t: float,
                  duration: float) -> Image.Image:
    base = ken_burns(_base_frame(background), t / max(duration, 1e-6),
                     zoom_end=1.06)
    frame = _composite(base, _vertical_gradient(0.30, 170))
    overlay = _alpha_layer()
    draw = ImageDraw.Draw(overlay)

    # Fixed centre statement.
    _draw_text_alpha(overlay, center_text, config.FONT_BOLD, 52,
                     (config.WIDTH / 2, config.HEIGHT / 2),
                     config.COLORS["highlight"], _fade_in(t, 0.0, 0.8))

    for i, item in enumerate(bubbles[:len(_BUBBLE_SLOTS)]):
        appear = 1.5 * i
        alpha = _fade_in(t, appear, 0.5)
        if alpha <= 0:
            continue
        bubble_text = item["text"] if isinstance(item, dict) else item
        fx, fy = (item.get("pos", _BUBBLE_SLOTS[i])
                  if isinstance(item, dict) else _BUBBLE_SLOTS[i])
        cx, cy = config.WIDTH * fx, config.HEIGHT * fy

        lines = text.wrap_persian(
            bubble_text, config.FONT_MEDIUM, config.WIDTH * 0.42,
            start_size=34, min_size=24, line_spacing=1.3,
        )
        font_size = lines[0][1]
        probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        block_w, block_h = text._block_geometry(
            probe, lines, config.FONT_MEDIUM, 1.3
        )
        pad_x, pad_y = 28, 20
        box_w, box_h = block_w + pad_x * 2, block_h + pad_y * 2
        x0, y0 = cx - box_w / 2, cy - box_h / 2
        x1, y1 = cx + box_w / 2, cy + box_h / 2

        # Shadow + rounded bubble + accent outline.
        shadow = _alpha_layer()
        ImageDraw.Draw(shadow).rounded_rectangle(
            [x0 + 5, y0 + 7, x1 + 5, y1 + 7], radius=26,
            fill=(0, 0, 0, int(120 * alpha)),
        )
        overlay.alpha_composite(shadow)
        draw.rounded_rectangle(
            [x0, y0, x1, y1], radius=26,
            fill=(*config.COLORS["card_bg"], int(232 * alpha)),
            outline=(*config.COLORS["accent"], int(255 * alpha)),
            width=2,
        )
        ty = cy - block_h / 2
        for line, line_size in lines:
            font = text._font(str(config.FONT_MEDIUM), line_size)
            visual = text.prepare_persian(line)
            box = draw.textbbox((0, 0), visual, font=font)
            lw = box[2] - box[0]
            draw.text(
                (cx - lw / 2 - box[0], ty - box[1]), visual,
                font=font, fill=(*config.COLORS["text"], int(255 * alpha)),
            )
            ty += line_size * 1.3

    return _composite(frame, overlay).convert("RGB")


# --------------------------------------------------------------------------
# Scene c) fact vs interpretation split (stacked cards on vertical canvas)
# --------------------------------------------------------------------------
def _draw_card(overlay: Image.Image, box, tint, label: str, body: str,
               alpha: float, slide_x: float) -> None:
    x0, y0, x1, y1 = box
    x0 += slide_x
    x1 += slide_x
    if alpha <= 0:
        return
    shadow = _alpha_layer()
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x0 + 6, y0 + 10, x1 + 6, y1 + 10], radius=30,
        fill=(0, 0, 0, int(130 * alpha)),
    )
    overlay.alpha_composite(shadow)
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        [x0, y0, x1, y1], radius=30,
        fill=(*config.COLORS["card_bg"], int(238 * alpha)),
        outline=(*tint, int(255 * alpha)), width=3,
    )
    # Tinted label pill.
    label_font = text._font(str(config.FONT_BLACK), 34)
    label_visual = text.prepare_persian(label)
    lbox = draw.textbbox((0, 0), label_visual, font=label_font)
    lw, lh = lbox[2] - lbox[0], lbox[3] - lbox[1]
    pill = [x0 + 36, y0 + 30, x0 + 36 + lw + 48, y0 + 30 + lh + 26]
    draw.rounded_rectangle(
        pill, radius=18, fill=(*tint, int(235 * alpha))
    )
    draw.text(
        (pill[0] + 24 - lbox[0], pill[1] + 13 - lbox[1]),
        label_visual, font=label_font,
        fill=(12, 14, 30, int(255 * alpha)),
    )
    # Body, wrapped inside the card.
    body_lines = text.wrap_persian(
        body, config.FONT_MEDIUM, int((x1 - x0) - 72),
        start_size=40, min_size=28, line_spacing=1.45,
    )
    ty = y0 + 120
    for line, size in body_lines:
        font = text._font(str(config.FONT_MEDIUM), size)
        visual = text.prepare_persian(line)
        box = draw.textbbox((0, 0), visual, font=font)
        lw = box[2] - box[0]
        draw.text(
            ((x0 + x1) / 2 - lw / 2 - box[0], ty - box[1]),
            visual, font=font,
            fill=(*config.COLORS["text"], int(255 * alpha)),
        )
        ty += size * 1.45


def scene_split(background: Background, left_label: str, left_text: str,
                right_label: str, right_text: str,
                t: float, duration: float) -> Image.Image:
    base = ken_burns(_base_frame(background), t / max(duration, 1e-6),
                     zoom_end=1.05)
    dim = Image.new("RGBA", base.size, (6, 8, 20, 150))
    frame = _composite(base, dim)
    overlay = _alpha_layer()

    margin = 70
    top_box = (margin, 330, config.WIDTH - margin, 920)
    bottom_box = (margin, 1010, config.WIDTH - margin, 1600)

    a1 = _fade_in(t, 0.2, 0.6)
    a2 = _fade_in(t, 0.9, 0.6)
    # On a vertical canvas the "left" card lands on top; slides are mirrored
    # horizontally so motion still reads as two opposing panels.
    _draw_card(overlay, top_box, config.COLORS["success"],
               left_label, left_text, a1, int((1 - a1) * -70))
    _draw_card(overlay, bottom_box, config.COLORS["danger"],
               right_label, right_text, a2, int((1 - a2) * 70))
    return _composite(frame, overlay).convert("RGB")


# --------------------------------------------------------------------------
# Scene d) numbered card stack
# --------------------------------------------------------------------------
def scene_cards(background: Background, cards: List[Dict],
                t: float, duration: float,
                interval: float = 3.0) -> Image.Image:
    base = ken_burns(_base_frame(background), t / max(duration, 1e-6),
                     zoom_end=1.05)
    frame = _composite(base, Image.new("RGBA", base.size, (6, 8, 20, 165)))
    overlay = _alpha_layer()
    draw = ImageDraw.Draw(overlay)

    n = max(1, len(cards))
    top, bottom = 260, 1560
    gap = 30
    card_h = min(360, int((bottom - top - gap * (n - 1)) / n))
    margin = 64

    for i, card in enumerate(cards):
        alpha = _fade_in(t, i * interval, 0.55)
        if alpha <= 0:
            continue
        rise = int((1 - alpha) * 34)
        y0 = top + i * (card_h + gap) + rise
        y1 = y0 + card_h
        x0, x1 = margin, config.WIDTH - margin

        shadow = _alpha_layer()
        ImageDraw.Draw(shadow).rounded_rectangle(
            [x0 + 5, y0 + 8, x1 + 5, y1 + 8], radius=28,
            fill=(0, 0, 0, int(130 * alpha)),
        )
        overlay.alpha_composite(shadow)
        draw.rounded_rectangle(
            [x0, y0, x1, y1], radius=28,
            fill=(*config.COLORS["card_bg"], int(240 * alpha)),
            outline=(*config.COLORS["card_border"], int(255 * alpha)),
            width=2,
        )

        # Number circle.
        circle_cx, circle_cy, r = x0 + 78, y0 + 78, 44
        draw.ellipse(
            [circle_cx - r, circle_cy - r, circle_cx + r, circle_cy + r],
            fill=(*config.COLORS["accent"], int(255 * alpha)),
        )
        num_font = text._font(str(config.FONT_BLACK), 40)
        num_visual = text.prepare_persian(str(card.get("number", i + 1)))
        nbox = draw.textbbox((0, 0), num_visual, font=num_font)
        draw.text(
            (circle_cx - (nbox[2] - nbox[0]) / 2 - nbox[0],
             circle_cy - (nbox[3] - nbox[1]) / 2 - nbox[1]),
            num_visual, font=num_font,
            fill=(12, 14, 30, int(255 * alpha)),
        )

        # Title.
        title_lines = text.wrap_persian(
            card.get("title", ""), config.FONT_BOLD,
            x1 - x0 - 180, start_size=38, min_size=26, line_spacing=1.3,
        )
        ty = y0 + 34
        text_x = x0 + 146
        for line, size in title_lines:
            font = text._font(str(config.FONT_BOLD), size)
            visual = text.prepare_persian(line)
            box = draw.textbbox((0, 0), visual, font=font)
            draw.text(
                (text_x - box[0], ty - box[1]), visual, font=font,
                fill=(*config.COLORS["highlight"], int(255 * alpha)),
            )
            ty += size * 1.3

        # Body.
        body_lines = text.wrap_persian(
            card.get("body", ""), config.FONT_REGULAR,
            x1 - x0 - 72, start_size=30, min_size=22, line_spacing=1.4,
        )
        ty = max(ty + 8, y0 + 128)
        for line, size in body_lines:
            font = text._font(str(config.FONT_REGULAR), size)
            visual = text.prepare_persian(line)
            box = draw.textbbox((0, 0), visual, font=font)
            lw = box[2] - box[0]
            draw.text(
                ((x0 + x1) / 2 - lw / 2 - box[0], ty - box[1]),
                visual, font=font,
                fill=(*config.COLORS["text"], int(255 * alpha)),
            )
            ty += size * 1.4

    return _composite(frame, overlay).convert("RGB")


# --------------------------------------------------------------------------
# Scene e) outro
# --------------------------------------------------------------------------
def scene_outro(background: Background, closing_text: str,
                t: float, duration: float) -> Image.Image:
    base = ken_burns(_base_frame(background), t / max(duration, 1e-6),
                     zoom_start=1.04, zoom_end=1.1)
    # Background progressively darkens.
    dark_alpha = int(150 + 75 * _smoothstep(t / max(duration, 1e-6)))
    frame = _composite(base, Image.new("RGBA", base.size, (5, 7, 18, dark_alpha)))
    overlay = _alpha_layer()
    alpha = _fade_in(t, 0.3, max(0.1, duration * 0.5))
    lines = text.wrap_persian(
        closing_text, config.FONT_BOLD, config.WIDTH - 180,
        start_size=58, min_size=36, line_spacing=1.5,
    )
    block = "\n".join(line for line, _ in lines)
    size = lines[0][1] if lines else 48
    _draw_text_alpha(overlay, block, config.FONT_BOLD, size,
                     (config.WIDTH / 2, config.HEIGHT / 2),
                     config.COLORS["text"], alpha, line_spacing=1.5)
    # Small accent underline.
    if alpha > 0:
        draw = ImageDraw.Draw(overlay)
        w = 220
        draw.rounded_rectangle(
            [config.WIDTH / 2 - w / 2, config.HEIGHT / 2 + 170,
             config.WIDTH / 2 + w / 2, config.HEIGHT / 2 + 178],
            radius=4, fill=(*config.COLORS["accent"], int(255 * alpha)),
        )
    return _composite(frame, overlay).convert("RGB")
