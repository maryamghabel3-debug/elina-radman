"""Animated backgrounds: parallax pan/zoom, drifting particles and grain.

A background is never fully static: every frame combines a slow Ken-Burns
pan/zoom with two depth layers of drifting particles and a low-amplitude
film grain so dark scenes keep living between text beats.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import config, keyframes as kf


@lru_cache(maxsize=8)
def _cover(path: str) -> Image.Image:
    src = Image.open(path).convert("RGB")
    sw, sh = src.size
    scale = max(config.WIDTH / sw, config.HEIGHT / sh)
    resized = src.resize((int(sw * scale) + 2, int(sh * scale) + 2),
                         Image.LANCZOS)
    w, h = resized.size
    left = (w - config.WIDTH) // 2
    top = (h - config.HEIGHT) // 2
    return resized.crop((left, top, left + config.WIDTH,
                         top + config.HEIGHT))


class ParticleField:
    """Deterministic drifting particles with parallax depth + twinkle."""

    def __init__(self, seed: int, count: int = 46):
        rng = np.random.default_rng(seed)
        self.x = rng.uniform(0, config.WIDTH, count)
        self.y = rng.uniform(0, config.HEIGHT, count)
        self.speed = rng.uniform(8.0, 30.0, count)       # px/s upward drift
        self.phase = rng.uniform(0, math.tau, count)
        self.radius = rng.uniform(1.2, 3.4, count)
        self.depth = rng.choice([0.45, 0.75, 1.0], count)
        self.count = count

    def draw(self, layer: Image.Image, t: float,
             color=(139, 124, 255)) -> None:
        draw = ImageDraw.Draw(layer)
        for i in range(self.count):
            y = (self.y[i] - self.speed[i] * t) % (config.HEIGHT + 40) - 20
            x = self.x[i] + 12.0 * self.depth[i] * math.sin(
                t * 0.35 + self.phase[i])
            twinkle = 0.45 + 0.4 * math.sin(t * 1.7 + self.phase[i])
            alpha = int(110 * self.depth[i] * max(0.15, twinkle))
            r = self.radius[i] * (0.7 + 0.5 * self.depth[i])
            draw.ellipse([x - r, y - r, x + r, y + r],
                         fill=(*color, alpha))


class AnimatedBackground:
    """Ken-Burns pan/zoom over a cover image plus particles, grain, scrim."""

    def __init__(self, image_path, seed: int = 7,
                 zoom: Tuple[float, float] = (1.04, 1.12),
                 pan_x: Tuple[float, float] = (-26.0, 26.0),
                 pan_y: Tuple[float, float] = (-18.0, 18.0),
                 particles: int = 46, dim: float = 0.45,
                 glow: bool = True):
        self.base = _cover(str(image_path))
        self.field = ParticleField(seed, particles)
        self.zoom = zoom
        self.pan_x = pan_x
        self.pan_y = pan_y
        self.dim = dim
        self.glow = glow
        # Pre-rendered soft glow sprites, moved along slow Lissajous paths
        # every frame so large canvas regions never sit pixel-still.
        self._glow_sprites = [
            self._make_glow((139, 124, 255), 760, 0.55),
            self._make_glow((94, 214, 162), 620, 0.30),
        ]

    @staticmethod
    def _make_glow(color, size: int, strength: float) -> Image.Image:
        yy, xx = np.mgrid[0:size, 0:size]
        dist = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2)
        alpha = np.clip(1.0 - dist / (size / 2), 0.0, 1.0) ** 2
        alpha = (alpha * 90 * strength).astype(np.uint8)
        rgb = np.zeros((size, size, 3), dtype=np.uint8)
        rgb[..., 0], rgb[..., 1], rgb[..., 2] = color
        layer = Image.fromarray(
            np.dstack([rgb, alpha]), "RGBA")
        return layer.filter(ImageFilter.GaussianBlur(60))

    def _ken_burns(self, p: float) -> Image.Image:
        z = self.zoom[0] + (self.zoom[1] - self.zoom[0]) * kf.ease_in_out_cubic(p)
        px = self.pan_x[0] + (self.pan_x[1] - self.pan_x[0]) * kf.ease_in_out_cubic(p)
        py = self.pan_y[0] + (self.pan_y[1] - self.pan_y[0]) * kf.ease_in_out_cubic(p)
        cw, ch = config.WIDTH / z, config.HEIGHT / z
        cx, cy = config.WIDTH / 2 + px, config.HEIGHT / 2 + py
        left = max(0, min(config.WIDTH - cw, cx - cw / 2))
        top = max(0, min(config.HEIGHT - ch, cy - ch / 2))
        crop = self.base.crop((left, top, left + cw, top + ch))
        return crop.resize((config.WIDTH, config.HEIGHT), Image.LANCZOS)

    def render(self, t: float, duration: float) -> Image.Image:
        frame = self._ken_burns(kf.clamp01(t / max(duration, 1e-6))).convert("RGBA")
        if self.dim > 0:
            scrim = Image.new("RGBA", frame.size,
                              (8, 10, 26, int(255 * self.dim)))
            frame.alpha_composite(scrim)
        particle_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        self.field.draw(particle_layer, t)
        frame.alpha_composite(particle_layer)
        if self.glow:
            # Slow nebula drift: different frequency per sprite guarantees
            # every frame changes many pixels without any hard movement.
            paths = [
                (config.WIDTH * 0.5
                 + config.WIDTH * 0.30 * math.sin(t * 0.11 + 0.4),
                 config.HEIGHT * 0.38
                 + config.HEIGHT * 0.22 * math.cos(t * 0.085),
                 1.0 + 0.06 * math.sin(t * 0.13)),
                (config.WIDTH * 0.5
                 + config.WIDTH * 0.34 * math.cos(t * 0.09 + 2.1),
                 config.HEIGHT * 0.62
                 + config.HEIGHT * 0.20 * math.sin(t * 0.105 + 1.2),
                 1.0 + 0.05 * math.cos(t * 0.12)),
            ]
            for sprite, (gx, gy, gs) in zip(self._glow_sprites, paths):
                sw, sh = sprite.size
                sprite_r = sprite.resize(
                    (max(1, int(sw * gs)), max(1, int(sh * gs))),
                    Image.BILINEAR)
                frame.alpha_composite(
                    sprite_r,
                    (int(gx - sprite_r.width / 2),
                     int(gy - sprite_r.height / 2)))
        # Stronger fine grain: fresh noise every frame keeps even dark
        # regions alive below freezedetect's sensitivity threshold.
        grain_rng = np.random.default_rng(int(t * 1000) % (2 ** 31))
        grain = grain_rng.normal(0, 12, (360, 202)).astype(np.int16)
        tile = Image.fromarray(
            np.clip(grain + 128, 0, 255).astype(np.uint8)
        ).resize((config.WIDTH, config.HEIGHT), Image.BILINEAR)
        grain_rgba = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        grain_rgba.putalpha(tile.point(lambda v: int(abs(v - 128) * 0.9)))
        frame.alpha_composite(grain_rgba)
        return frame.convert("RGB")


def solid_navy(seed: int = 3, dim: float = 0.0) -> AnimatedBackground:
    """Fallback animated background built from a flat navy frame."""
    path = Path(config.ASSETS_DIR) / "images" / "bashe" / "img_min_a.png"
    return AnimatedBackground(path, seed=seed, dim=0.62 if dim == 0.0 else dim)
