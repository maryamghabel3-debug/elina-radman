"""Persistent global chrome: progress line, chapter tab, dot pagination.

Drawn on top of every frame so the whole video reads as one continuous
piece (the reference video's structural grammar), even across scenes.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from . import config, keyframes as kf
from .text import _font, prepare_persian

LINE_Y = 96
LINE_X0, LINE_X1 = 70, config.WIDTH - 70
DOT_Y = 1652


def _text(draw: ImageDraw.ImageDraw, text: str, font, xy, color) -> None:
    draw.text(xy, prepare_persian(text), font=font, fill=color)


def draw_chrome(frame: Image.Image, global_t: float, total_t: float,
                chapter_index: int, chapter_count: int,
                chapter_title: str) -> None:
    """chapter_index is 0-based; dots fill as chapters complete."""
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    violet = config.COLORS["violet"]
    dim = (*violet, 90)

    # --- Progress track + fill -------------------------------------------
    d.line([(LINE_X0, LINE_Y), (LINE_X1, LINE_Y)], fill=(*violet, 70), width=3)
    frac = kf.clamp01(global_t / max(total_t, 1e-6))
    fill_x = LINE_X0 + (LINE_X1 - LINE_X0) * frac
    if frac > 0:
        d.line([(LINE_X0, LINE_Y), (fill_x, LINE_Y)],
               fill=(*violet, 255), width=4)
        d.ellipse([fill_x - 7, LINE_Y - 7, fill_x + 7, LINE_Y + 7],
                  fill=(*config.COLORS["gold"], 255))

    # --- Chapter tab (top-right, RTL) ------------------------------------
    title_font = _font(str(config.FONT_BOLD), 30)
    label_font = _font(str(config.FONT_REGULAR), 24)
    title_v = prepare_persian(chapter_title)
    label_v = prepare_persian("پرونده")
    tw = d.textlength(title_v, font=title_font)
    lw = d.textlength(label_v, font=label_font)
    tab_w = int(tw + lw + 44)
    tab_h = 52
    x1, y1 = config.WIDTH - 40, 58
    x0, y0 = x1 - tab_w, y1 - tab_h
    d.rounded_rectangle([x0, y0, x1, y1], radius=14,
                        fill=(12, 14, 32, 215),
                        outline=(*violet, 180), width=2)
    d.text((x1 - 20 - tw, y0 + 9), title_v, font=title_font,
           fill=(*config.COLORS["text"], 255))
    d.text((x1 - 28 - tw - lw, y0 + 13), label_v, font=label_font,
           fill=(*config.COLORS["text_dim"], 255))

    # --- Dot pagination ---------------------------------------------------
    gap = 34
    total_w = (chapter_count - 1) * gap
    cx0 = config.WIDTH / 2 - total_w / 2
    for i in range(chapter_count):
        cx = cx0 + i * gap
        if i < chapter_index:
            d.ellipse([cx - 7, DOT_Y - 7, cx + 7, DOT_Y + 7],
                      fill=(*violet, 220))
        elif i == chapter_index:
            r = 10 + 2 * kf.breathe(global_t, speed=2.4, amount=0.18)
            d.ellipse([cx - r, DOT_Y - r, cx + r, DOT_Y + r],
                      fill=(*config.COLORS["gold"], 255))
        else:
            d.ellipse([cx - 6, DOT_Y - 6, cx + 6, DOT_Y + 6],
                      outline=(*violet, 140), width=2)

    frame.alpha_composite(layer)
