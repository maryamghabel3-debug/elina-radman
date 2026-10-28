"""250-400 ms scene transitions operating on two adjacent RGB frames.

Pure PIL compositing - no encoder support needed. The orchestrator keeps
only the previous scene's final frame in memory (one frame), so streaming
rendering stays memory-safe.
"""
from __future__ import annotations

from PIL import Image, ImageFilter

from . import config, keyframes as kf

DURATION = 0.32


def _rgba(frame: Image.Image) -> Image.Image:
    return frame.convert("RGBA")


def swipe(prev: Image.Image, cur: Image.Image, p: float,
          direction: int = 1) -> Image.Image:
    """New scene slides in horizontally while the old one slides out."""
    w = config.WIDTH
    shift = int((1 - kf.ease_out_cubic(p)) * w * direction)
    canvas = Image.new("RGBA", cur.size, (8, 10, 26, 255))
    old = _rgba(prev)
    if -shift != 0:
        canvas.alpha_composite(old, (-shift, 0))
    canvas.alpha_composite(_rgba(cur), (shift, 0))
    return canvas.convert("RGB")


def whip_pan(prev: Image.Image, cur: Image.Image, p: float,
             direction: int = -1) -> Image.Image:
    """Fast directional blur + slide, like a quick camera whip."""
    w = config.WIDTH
    e = kf.ease_in_out_cubic(p)
    shift = int((1 - e) * w * 0.55 * direction)
    blur_r = 7 * (1 - p)
    canvas = Image.new("RGBA", cur.size, (8, 10, 26, 255))
    canvas.alpha_composite(_rgba(prev), (shift // 2, 0))
    new = _rgba(cur)
    if blur_r > 0.4:
        new = new.filter(ImageFilter.GaussianBlur(radius=blur_r))
    canvas.alpha_composite(new, (-shift, 0))
    return canvas.convert("RGB")


def scale_cut(prev: Image.Image, cur: Image.Image, p: float) -> Image.Image:
    """New scene scales from 1.10 with a quick fade over the old frame."""
    e = kf.ease_out_cubic(p)
    scale = 1.10 - 0.10 * e
    base = _rgba(prev)
    new = _rgba(cur)
    nw, nh = int(config.WIDTH * scale), int(config.HEIGHT * scale)
    zoomed = new.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - config.WIDTH) // 2, (nh - config.HEIGHT) // 2
    zoomed = zoomed.crop((left, top, left + config.WIDTH,
                          top + config.HEIGHT))
    zoomed.putalpha(zoomed.getchannel("A").point(lambda v: int(v * e)))
    base.alpha_composite(zoomed)
    return base.convert("RGB")


def mask_reveal(prev: Image.Image, cur: Image.Image, p: float) -> Image.Image:
    """Expanding circular reveal from the canvas center."""
    base = _rgba(prev)
    new = _rgba(cur)
    diag = (config.WIDTH ** 2 + config.HEIGHT ** 2) ** 0.5
    radius = diag * 0.55 * kf.ease_out_cubic(p)
    mask = Image.new("L", cur.size, 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    cx, cy = config.WIDTH / 2, config.HEIGHT / 2
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=255)
    base.paste(new, (0, 0), mask)
    return base.convert("RGB")


KINDS = {"swipe": swipe, "whip_pan": whip_pan,
         "scale_cut": scale_cut, "mask_reveal": mask_reveal}


def apply(kind: str, prev: Image.Image, cur: Image.Image, p: float,
          direction: int = 1) -> Image.Image:
    if kind in ("swipe", "whip_pan"):
        return KINDS[kind](prev, cur, p, direction)
    return KINDS[kind](prev, cur, p)
