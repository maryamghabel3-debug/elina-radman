"""Shared state machine and PIL helpers for the V3 style-test skins."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from engine import config, text as ptext

W, H = 1080, 1920
FPS = 30
SAFE_TOP, SAFE_BOTTOM = 250, 1500
SUB_Y = 1480

FONT_R = str(config.FONT_REGULAR)
FONT_M = str(config.FONT_MEDIUM)
FONT_B = str(config.FONT_BOLD)
FONT_K = str(config.FONT_BLACK)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def persian(text: str) -> str:
    return ptext.prepare_persian(text)


def text_size(txt: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    b = fnt.getbbox(persian(txt))
    return b[2] - b[0], b[3] - b[1]


def draw_persian(draw: ImageDraw.ImageDraw, xy, txt: str, fnt, fill,
                 anchor: str = "mm") -> None:
    draw.text(xy, persian(txt), font=fnt, fill=fill, anchor=anchor)


def rounded_shadow(size: tuple[int, int], radius: int, blur: float = 14.0,
                   alpha: int = 70) -> Image.Image:
    """Soft drop-shadow sprite for a rounded rectangle."""
    pad = blur * 3
    sh = Image.new("RGBA", (size[0] + 2 * pad, size[1] + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.rounded_rectangle([pad, pad, pad + size[0], pad + size[1]],
                        radius=radius, fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


def paste_shadowed(base: Image.Image, panel: Image.Image, pos: tuple[int, int],
                   shadow: Image.Image, pad: float) -> None:
    base.alpha_composite(shadow, (int(pos[0] - pad), int(pos[1] - pad)))
    base.alpha_composite(panel, pos)


def grain_layer(w: int, h: int, sigma: int, alpha: int, seed: int = 3) -> Image.Image:
    rng = np.random.default_rng(seed)
    g = rng.normal(0, sigma, (h, w)).clip(-255, 255).astype("int16")
    arr = np.zeros((h, w, 4), dtype="uint8")
    arr[..., 0] = arr[..., 1] = arr[..., 2] = 128
    arr[..., 3] = np.clip(np.abs(g), 0, 255).astype("uint8")
    img = Image.fromarray(arr, "RGBA")
    return img.point(lambda p: min(p, alpha)) if alpha < 255 else img


def ease_out_back(p: float) -> float:
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def ease_out(p: float) -> float:
    return 1 - (1 - min(max(p, 0), 1)) ** 3


@dataclass
class Impact:
    t: float
    text: str
    role: str | None
    kind: str  # 'word' | 'phrase'
    reliability: str


@dataclass
class FrameState:
    t: float
    duration: float
    phrase: dict | None
    phrase_age: float
    subtitle: str | None
    impacts: list  # list[(age, Impact)]
    beat_phase: float
    progress: float
    recent_phrases: list = field(default_factory=list)


class TimelineDriver:
    """Turns timeline.json events into per-frame skin state."""

    def __init__(self, events: list[dict], duration: float):
        self.events = sorted(events, key=lambda e: e["t"])
        self.phrases = [e for e in self.events if e["type"] == "phrase"]
        self.impacts = []
        for e in self.phrases:
            if e.get("is_key"):
                self.impacts.append(Impact(e["t"], e["text"], e["role"], "phrase",
                                           e["reliability"]))
            for w in e.get("words", []):
                if w.get("is_key"):
                    self.impacts.append(Impact(w["t"], w["text"], w["role"], "word",
                                               w["reliability"]))
        self.impacts.sort(key=lambda i: i.t)
        self.beats = [e["t"] for e in self.events if e["type"] == "visual_beat"]
        self.duration = duration

    def state(self, t: float) -> FrameState:
        cur, age = None, 0.0
        for e in self.phrases:
            if e["t"] <= t:
                cur, age = e, t - e["t"]
        recent = [e for e in self.phrases if t - 1.6 <= e["t"] <= t + 0.05][-3:]
        impacts = [(t - i.t, i) for i in self.impacts if 0 <= t - i.t <= 0.75]
        nearest_beat = min(self.beats, key=lambda b: abs(b - t)) if self.beats else t
        return FrameState(
            t=t, duration=self.duration, phrase=cur, phrase_age=age,
            subtitle=cur["text"] if cur else None, impacts=impacts,
            beat_phase=t - nearest_beat, progress=min(1.0, t / self.duration),
            recent_phrases=recent)


def jitter_12fps(t: float, key: int, amp: int = 3) -> tuple[int, int]:
    """Stop-motion micro-jitter, held on 12 fps steps and deterministic."""
    step = int(t * 12)
    rng = random.Random(step * 1009 + key)
    return rng.randint(-amp, amp), rng.randint(-amp, amp)
