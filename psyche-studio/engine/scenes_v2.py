"""V2 motion-graphics scene systems for Project 001.

Reusable components (all driven by per-frame time, no static holds):
  * phone_chat      - phone mockup, glow, type-on bubble, ticks/typing dots
  * thought_spiral  - orbiting negative-thought chips with connectors
  * compare         - two-column icon diagram with self-drawing connectors
  * head_transform  - message travels along a motion path into a head icon
  * steps           - full-canvas step chapters with a mini-dock
  * outro_v2        - beat reveal + icon assembly badge

Scenes are factories returning (frame_callable, metadata). Chrome and
subtitles are applied globally by the render orchestrator.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFilter

from . import config, icons, keyframes as kf, kinetic, backgrounds
from .text import _font, prepare_persian

C = config.COLORS
IMAGE_DIR = Path(config.ASSETS_DIR) / "images" / "bashe"
Frame = Image.Image


def F(size: int, weight: str = "medium"):
    paths = {
        "regular": config.FONT_REGULAR, "medium": config.FONT_MEDIUM,
        "bold": config.FONT_BOLD, "black": config.FONT_BLACK,
    }
    return _font(str(paths[weight]), size)


# --------------------------------------------------------------------------
# Shared small components
# --------------------------------------------------------------------------
def bump(t: float, start: float, period: float, n: int,
         width: float = 0.45) -> float:
    """Triangular periodic pulse, 0..1..0, used for reinforcement beats."""
    best = 0.0
    for k in range(n):
        d = abs(t - (start + k * period))
        best = max(best, max(0.0, 1.0 - d / width))
    return best


def pulse_ring(frame: Frame, cx: float, cy: float, base_r: float,
               t: float, phase: float, color) -> None:
    """Continuously expanding/contracting stroked ring (never static)."""
    k = (t * 0.85 + phase) % 1.0
    rr = base_r + 30.0 * k
    alpha = int(130 * (1.0 - k))
    ImageDraw.Draw(frame).ellipse(
        [cx - rr, cy - rr, cx + rr, cy + rr],
        outline=(*color, alpha), width=3)


def place_layer(layer: Image.Image, frame: Frame, cx: float, cy: float,
                scale: float = 1.0, alpha: float = 1.0,
                rotation: float = 0.0) -> None:
    if alpha <= 0.01:
        return
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)),
                              max(1, int(layer.height * scale))),
                             Image.LANCZOS)
    if rotation:
        layer = layer.rotate(rotation, expand=True, resample=Image.BICUBIC)
    if alpha < 0.999:
        layer.putalpha(layer.getchannel("A").point(
            lambda v: int(v * kf.clamp01(alpha))))
    frame.alpha_composite(layer, (int(cx - layer.width / 2),
                                  int(cy - layer.height / 2)))


def chip_layer(text: str, font, w: float, h: float, fill, outline,
               text_color, radius: int = 26) -> Image.Image:
    w, h = int(w), int(h)
    layer = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    box = [20, 20, 20 + w, 20 + h]
    d.rounded_rectangle(box, radius=radius, fill=(*fill, 238),
                        outline=(*outline, 255), width=3)
    visual = prepare_persian(text)
    tb = d.textbbox((0, 0), visual, font=font)
    d.text((20 + w / 2 - (tb[2] - tb[0]) / 2 - tb[0],
            20 + h / 2 - (tb[3] - tb[1]) / 2 - tb[1]),
           visual, font=font, fill=(*text_color, 255))
    return layer


def tag_layer(text: str, font, color) -> Image.Image:
    d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    visual = prepare_persian(text)
    tb = d0.textbbox((0, 0), visual, font=font)
    w, h = tb[2] - tb[0], tb[3] - tb[1]
    layer = Image.new("RGBA", (w + 44, h + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([0, 0, w + 44, h + 30], radius=16,
                        fill=(*color, 245))
    d.text((22 - tb[0], 15 - tb[1]), visual, font=font,
           fill=(12, 14, 30, 255))
    return layer


def phone_mockup(frame: Frame, t: float, rise_start: float,
                 cx: float, cy: float, w: float = 380,
                 h: float = 700) -> Tuple[float, float, float, float]:
    """Spring-rise phone with pulsing violet glow; returns the screen box."""
    p = kf.progress(t, rise_start, 0.75)
    if p <= 0:
        return (cx - w / 2 + 22, cy - h / 2 + 60,
                cx + w / 2 - 22, cy + h / 2 - 40)
    rise = (1 - kf.spring(p)) * 260
    alpha = kf.ease_out_quad(p)
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    # Glow
    glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pulse = 0.75 + 0.25 * math.sin(t * 2.2)
    gd.ellipse([cx - w * 0.75, cy - h * 0.55 + rise,
                cx + w * 0.75, cy + h * 0.55 + rise],
               fill=(*C["violet"], int(60 * pulse * alpha)))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    layer.alpha_composite(glow)
    d = ImageDraw.Draw(layer)
    x0, y0 = cx - w / 2, cy - h / 2 + rise
    x1, y1 = cx + w / 2, cy + h / 2 + rise
    d.rounded_rectangle([x0, y0, x1, y1], radius=46,
                        fill=(10, 12, 30, int(245 * alpha)),
                        outline=(*C["violet"], int(255 * alpha)), width=4)
    d.rounded_rectangle([x0 + 20, y0 + 58, x1 - 20, y1 - 42], radius=28,
                        fill=(*C["card_bg"], int(255 * alpha)),
                        outline=(*C["card_border"], int(200 * alpha)), width=2)
    d.rounded_rectangle([cx - 46, y0 + 20, cx + 46, y0 + 32], radius=6,
                        fill=(*C["text_dim"], int(220 * alpha)))
    frame.alpha_composite(layer)
    return (x0 + 22, y0 + 60, x1 - 22, y1 - 44)


def typing_dots(frame: Frame, cx: float, cy: float, t: float, color) -> None:
    d = ImageDraw.Draw(frame)
    for i in range(3):
        r = 5 + 3 * max(0.0, math.sin(t * 6 - i * 0.7))
        d.ellipse([cx - 26 + i * 26 - r, cy - r, cx - 26 + i * 26 + r,
                   cy + r], fill=(*color, 230))


def sent_ticks(frame: Frame, x: float, y: float, t: float,
               start: float) -> None:
    p = kf.progress(t, start, 0.35)
    if p <= 0:
        return
    col = C["success"]
    d = ImageDraw.Draw(frame)
    for off in (0, 9):
        d.line([(x + off, y), (x + 6 + off, y + 8), (x + 18 + off, y - 6)],
               fill=(*col, int(255 * p)), width=4)


# --------------------------------------------------------------------------
# Scene 1 - Hook
# --------------------------------------------------------------------------
def make_hook(cues: List[dict], duration: float) -> Tuple[Callable, dict]:
    bg = backgrounds.AnimatedBackground(IMAGE_DIR / "img_hook.png", seed=11,
                                        dim=0.42, particles=48)

    def render(t: float, duration: float) -> Frame:
        frame = bg.render(t, duration).convert("RGBA")
        icons.draw_icon(frame, "question", 540, 300, 150, C["violet"],
                        progress=kf.progress(t, 0.35, 0.8), stroke_width=5)
        pulse_ring(frame, 540, 300, 88, t, 0.0, C["violet"])
        sx0, sy0, sx1, sy1 = phone_mockup(frame, t, 0.15, 540, 900)
        # Type-on trigger word inside the phone.
        c1, c2, c3 = (cues + [{}, {}, {}])[:3]
        t2 = c2.get("start", 1.7)
        kinetic.type_on(frame, "باشه", (540, (sy0 + sy1) / 2 - 40),
                        t, t2, F(56, "black"), C["gold"], duration=0.7)
        if t > t2 + 0.75:
            kinetic.emphasis_pulse(frame, "باشه",
                                   (540, (sy0 + sy1) / 2 - 40), t,
                                   t2 + 0.75, F(56, "black"), C["gold"],
                                   peak_scale=1.1, duration=0.6)
        typing_dots(frame, 540, (sy0 + sy1) / 2 + 60, t, C["text_dim"])
        if t1 := c1.get("start"):
            kinetic.word_burst(frame, c1["text"], (540, 1430), t, t1,
                               F(46, "bold"), C["text"], stagger=0.12)
        if t3 := c3.get("start"):
            kinetic.word_burst(frame, c3["text"], (540, 1530), t, t3,
                               F(46, "bold"), C["text"], stagger=0.12)
        return frame.convert("RGB")

    return render, {"active_layers": 6,
                    "impact_texts": ["باشه"],
                    "ambient": ["parallax", "particles", "glow pulse",
                                "breathing dots"]}


# --------------------------------------------------------------------------
# Scene 2 - Thought storm / scene 4 - alternative explanations
# --------------------------------------------------------------------------
def make_storm(cues: List[dict], duration: float, center_word: str,
               phrases: List[str], phrase_color, img: str,
               impact_extra: List[str], seed: int,
               badge: bool = True) -> Tuple[Callable, dict]:
    bg = backgrounds.AnimatedBackground(IMAGE_DIR / img, seed=seed,
                                        dim=0.52, particles=58)
    slots = [(0.27, 0.24), (0.74, 0.31), (0.25, 0.64), (0.75, 0.73)]
    fonts = [F(34, "bold") for _ in phrases]

    def render(t: float, duration: float) -> Frame:
        frame = bg.render(t, duration).convert("RGBA")
        ccx, ccy = 540, 800
        # Breathing center word.
        scale = 1.0 + 0.05 * math.sin(t * 1.8)
        place_layer(kinetic.text_layer(center_word, F(64, "black"), C["gold"]),
                    frame, ccx, ccy, scale,
                    kf.fade_window(t, 0.2, 0.5))
        for i, (phrase, (fx, fy)) in enumerate(zip(phrases, slots)):
            start = 0.8 + i * 1.55
            p = kf.progress(t, start, 0.55)
            if p <= 0:
                continue
            cx = config.WIDTH * fx + 14 * math.sin(t * 1.1 + i * 1.7)
            cy = config.HEIGHT * fy + 10 * math.cos(t * 0.9 + i * 1.3)
            # Connector draws first.
            icons.dotted_leader(frame, (ccx, ccy), (cx, cy), C["violet"],
                                width=2, progress=kf.progress(t, start, 0.4))
            pop = 0.6 + 0.4 * kf.ease_out_back(p)
            pulse = 1.0 + 0.07 * bump(t, start + 2.2, 1.9, 6)
            layer = chip_layer(phrase, fonts[i], 330, 96, C["card_bg"],
                               phrase_color, C["text"])
            place_layer(layer, frame, cx, cy, pop * pulse,
                        kf.ease_out_quad(p),
                        rotation=2.5 * math.sin(i * 2.1) * (1 - p))
            if badge and t > start + 0.55:
                bd = tag_layer("؟", F(26, "bold"), C["danger"])
                place_layer(bd, frame, cx + 150, cy - 42,
                            kf.ease_out_back(kf.progress(t, start + 0.55, 0.35)),
                            kf.fade_window(t, start + 0.55, 0.3))
        return frame.convert("RGB")

    return render, {"active_layers": 6,
                    "impact_texts": [center_word] + impact_extra,
                    "ambient": ["parallax", "particles", "orbit float",
                                "breathing center", "reinforcement pulses"]}


# --------------------------------------------------------------------------
# Scene 3 - Compare diagram
# --------------------------------------------------------------------------
def make_compare(cues: List[dict], duration: float) -> Tuple[Callable, dict]:
    bg = backgrounds.AnimatedBackground(IMAGE_DIR / "img_min_a.png", 
                                        dim=0.62, particles=50)
    rows = [("person", "لحن صدا"), ("head", "حالت چهره"), ("spark", "زبان بدن")]

    def render(t: float, duration: float) -> Frame:
        frame = bg.render(t, duration).convert("RGBA")
        d = ImageDraw.Draw(frame)
        # Self-drawing divider.
        dp = kf.progress(t, 0.3, 0.6)
        d.line([(540, 300), (540, 300 + 1080 * dp)],
               fill=(*C["violet"], 220), width=3)
        # Right column: text message (RTL first).
        if c := (cues[0] if cues else {}):
            kinetic.phrase_reveal(frame, "پیام متنی", (800, 360), t,
                                  c.get("start", 0.5), F(44, "black"),
                                  C["danger"], mode="slide")
        icons.draw_icon(frame, "chat_bubble", 800, 560, 200, C["danger"],
                        progress=kf.progress(t, 1.0, 0.9), stroke_width=5)
        gold_t = cues[2]["start"] if len(cues) > 2 else 2.4
        kinetic.emphasis_pulse(frame, "فقط چند کلمه", (800, 800), t, gold_t,
                               F(40, "bold"), C["gold"], peak_scale=1.1)
        # Left column: in-person conversation.
        if cues:
            kinetic.phrase_reveal(frame, "مکالمه‌ی حضوری", (280, 360), t,
                                  cues[0].get("start", 0.5) + 0.4,
                                  F(44, "black"), C["success"], mode="blur")
        for i, (icon_name, label) in enumerate(rows):
            start = 2.6 + i * 1.7
            p = kf.progress(t, start, 0.6)
            if p <= 0:
                continue
            cy = 620 + i * 250 + 6 * math.sin(t * 1.25 + i * 1.4)
            icons.dotted_leader(frame, (470, cy), (360, cy), C["success"],
                                width=2, progress=p)
            icons.draw_icon(frame, icon_name, 250, cy, 120, C["success"],
                            progress=p, stroke_width=5)
            pulse_ring(frame, 250, cy, 72, t, i * 0.33, C["success"])
            kinetic.phrase_reveal(frame, label, (330, cy + 90), t, start + 0.2,
                                  F(32, "medium"), C["text"], mode="fade",
                                  duration=0.5)
            if t > start + 1.0:
                icons.draw_icon(frame, "check", 430, cy - 60, 56,
                                C["success"],
                                progress=kf.progress(t, start + 1.0, 0.4),
                                stroke_width=6)
        return frame.convert("RGB")

    return render, {"active_layers": 6,
                    "impact_texts": ["فقط چند کلمه", "پیام متنی",
                                     "مکالمه‌ی حضوری"],
                    "ambient": ["parallax", "particles", "stroke reveals",
                                "staggered nodes"]}


# --------------------------------------------------------------------------
# Scene 5 - Head transform
# --------------------------------------------------------------------------
def make_head_transform(cues: List[dict], duration: float) -> Tuple[Callable, dict]:
    bg = backgrounds.AnimatedBackground(IMAGE_DIR / "img_min_b.png", seed=31,
                                        dim=0.64, particles=50)
    path = kf.MotionPath([(760, 880), (620, 760), (460, 760), (330, 860)])

    def render(t: float, duration: float) -> Frame:
        frame = bg.render(t, duration).convert("RGBA")
        split = 8.6
        if t < split:
            sx0, sy0, sx1, sy1 = phone_mockup(frame, t, 0.2, 770, 900,
                                               w=340, h=620)
            c1 = cues[0] if cues else {"start": 0.6}
            kinetic.type_on(frame, "باشه", (770, (sy0 + sy1) / 2 - 30),
                            t, c1.get("start", 0.7), F(50, "black"),
                            C["text"], duration=0.7)
            sent_ticks(frame, sx1 - 70, sy1 - 90, t, 2.0)
            if cues:
                place_layer(tag_layer("واقعیت", F(28, "bold"), C["success"]),
                            frame, 640, 560,
                            kf.ease_out_back(kf.progress(t, 2.4, 0.45)),
                            kf.fade_window(t, 2.4, 0.4))
            icons.draw_icon(frame, "check", 560, 560, 48, C["success"],
                            progress=kf.progress(t, 2.7, 0.4), stroke_width=6)
        else:
            # Phase B: head + interpretation.
            hp = kf.progress(t, split, 0.9)
            head_cy = 860 + 8 * math.sin(t * 1.1)
            icons.draw_icon(frame, "head", 300, head_cy, 320, C["violet"],
                            progress=hp, stroke_width=5)
            pulse_ring(frame, 300, head_cy, 175, t, 0.2, C["violet"])
            t_interp = split + 1.2
            if t > t_interp:
                layer = chip_layer("حتماً از من ناراحته", F(34, "bold"),
                                   430, 110, C["card_bg"], C["danger"],
                                   C["text"])
                breathe = 1.0 + 0.03 * math.sin(t * 1.8)
                place_layer(layer, frame, 640, 760,
                            kf.ease_out_back(kf.progress(t, t_interp, 0.5))
                            * breathe,
                            kf.fade_window(t, t_interp, 0.45))
                place_layer(tag_layer("تفسیر", F(28, "bold"), C["danger"]),
                            frame, 620, 640,
                            kf.ease_out_back(kf.progress(t, t_interp + 0.4, 0.4)),
                            kf.fade_window(t, t_interp + 0.4, 0.4))
        # Traveling message + dotted path across the split.
        icons.dotted_leader(frame, (760, 880), (330, 860), C["gold"],
                            width=3, dash=12, gap=9,
                            progress=kf.progress(t, 7.4, 1.6))
        if 7.6 <= t <= 9.8:
            mp = kf.progress(t, 7.6, 2.2)
            px, py = path.point(mp)
            place_layer(kinetic.text_layer("باشه", F(30, "bold"), C["gold"]),
                        frame, px, py, 1.05 - 0.35 * mp, 1.0)
        # Impact term.
        mind_t = next((c["start"] for c in cues if "ذهن‌خوانی" in c.get("text", "")),
                      13.4)
        if t > mind_t - 0.2:
            kinetic.word_burst(frame, "ذهن‌خوانی", (540, 1400), t, mind_t,
                               F(58, "black"), C["gold"], stagger=0.14)
        # Quick flash at the phase boundary (scale-cut energy).
        flash = max(0.0, 1.0 - abs(t - split) / 0.35)
        if flash > 0:
            ImageDraw.Draw(frame).rectangle(
                [0, 0, config.WIDTH, config.HEIGHT],
                fill=(*C["violet"], int(45 * flash)))
        return frame.convert("RGB")

    return render, {"active_layers": 7,
                    "impact_texts": ["واقعیت", "تفسیر", "ذهن‌خوانی", "باشه"],
                    "ambient": ["parallax", "particles", "path travel",
                                "phase flash", "stroke reveals"]}


# --------------------------------------------------------------------------
# Scene 6 - Three steps with mini-dock
# --------------------------------------------------------------------------
STEPS = [
    ("۱", "magnifier", "واقعیت چیه؟", "فقط چیزی که واقعاً اتفاق افتاده"),
    ("۲", "head", "داستان ذهنم چیه؟", "حدس‌هایی که ذهنم می‌سازه"),
    ("۳", "question", "اقدام سالم چیه؟", "به جای حدس، سؤال بپرس"),
]


def make_steps(cues: List[dict], duration: float) -> Tuple[Callable, dict]:
    bg = backgrounds.AnimatedBackground(IMAGE_DIR / "img_min_b.png", seed=41,
                                        dim=0.66, particles=46)
    chapter = duration / 3.0

    def render(t: float, duration: float) -> Frame:
        frame = bg.render(t, duration).convert("RGBA")
        idx = min(2, int(t // chapter))
        local = t - idx * chapter
        numeral, icon_name, title, body = STEPS[idx]
        # Chapter entrance: quick scale-cut settle.
        settle = kf.ease_out_cubic(kf.progress(local, 0.0, 0.45))
        scale = 1.12 - 0.12 * settle
        content = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        icons.draw_icon(content, icon_name, 540, 480, 260, C["violet"],
                        progress=kf.progress(local, 0.15, 0.8), stroke_width=5)
        numeral_breathe = 1.0 + 0.045 * math.sin(local * 2.3)
        place_layer(kinetic.text_layer(numeral, F(110, "black"), C["gold"]),
                    content, 540, 760,
                    kf.ease_out_back(kf.progress(local, 0.1, 0.5))
                    * numeral_breathe,
                    kf.fade_window(local, 0.1, 0.4))
        pulse_ring(content, 540, 480, 140, local, idx * 0.4, C["violet"])
        kinetic.phrase_reveal(content, title, (540, 960), local, 0.55,
                              F(56, "black"), C["success"] if idx == 0
                              else C["violet"], mode="slide", duration=0.6)
        kinetic.word_burst(content, body, (540, 1120), local, 1.35,
                           F(38, "medium"), C["text"], stagger=0.12)
        # Cue-driven reinforcement pulse keeps the title alive after entrance.
        cue_starts = [c["start"] - idx * chapter for c in cues
                      if idx * chapter <= c["start"] < (idx + 1) * chapter]
        title_pulse = 1.0
        if cue_starts:
            title_pulse += 0.05 * bump(local, cue_starts[0] + 1.2, 1.8, 4)
        place_layer(content, frame, 540, config.HEIGHT / 2,
                    scale * title_pulse,
                    kf.ease_out_quad(kf.progress(local, 0.0, 0.4)))
        # Mini-dock of completed steps.
        d = ImageDraw.Draw(frame)
        for k in range(3):
            cx = 540 + (k - 1) * 150
            cy = 1480
            if k < idx:
                d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34],
                          fill=(*C["violet"], 230))
                tb = d.textbbox((0, 0), prepare_persian(STEPS[k][0]),
                                font=F(34, "black"))
                d.text((cx - (tb[2] - tb[0]) / 2 - tb[0],
                        cy - (tb[3] - tb[1]) / 2 - tb[1]),
                       prepare_persian(STEPS[k][0]), font=F(34, "black"),
                       fill=(12, 14, 30, 255))
            elif k == idx:
                d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34],
                          outline=(*C["gold"], 255), width=4)
            else:
                d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34],
                          outline=(*C["violet"], 120), width=2)
        return frame.convert("RGB")

    return render, {"active_layers": 6,
                    "impact_texts": [s[2] for s in STEPS],
                    "ambient": ["parallax", "particles", "chapter scale-cut",
                                "stroke reveals", "mini-dock"]}


# --------------------------------------------------------------------------
# Scene 7 - Outro v2
# --------------------------------------------------------------------------
def make_outro(cues: List[dict], duration: float) -> Tuple[Callable, dict]:
    bg = backgrounds.AnimatedBackground(IMAGE_DIR / "img_outro.png", seed=53,
                                        dim=0.42, particles=50,
                                        zoom=(1.03, 1.09))
    badge_icons = ["magnifier", "head", "question"]

    def render(t: float, duration: float) -> Frame:
        frame = bg.render(t, duration).convert("RGBA")
        c1 = cues[0].get("start", 0.3) if cues else 0.3
        c2 = cues[1].get("start", 2.2) if len(cues) > 1 else 2.2
        kinetic.word_burst(frame, "هر فکری که از ذهنت می‌گذره", (540, 560),
                           t, c1, F(48, "bold"), C["text"], stagger=0.1)
        kinetic.word_burst(frame, "حقیقت نیست.", (540, 680), t, c2,
                           F(54, "black"), C["gold"], stagger=0.12)
        # Icon assembly into a badge: the outline only begins forming once
        # the first icon has arrived, so no empty rectangle ever shows.
        d = ImageDraw.Draw(frame)
        badge_p = kf.progress(t, 6.55, 1.0)
        if badge_p > 0:
            d.rounded_rectangle([300, 880, 780, 1120], radius=40,
                                outline=(*C["violet"], int(230 * badge_p)),
                                width=4)
        for i, name in enumerate(badge_icons):
            start = 6.4 + i * 0.7
            fly = kf.progress(t, start, 0.7)
            if fly <= 0:
                continue
            cx = 400 + i * 140
            cy = (1000 - (1 - kf.ease_out_back(fly)) * 240
                  + 6 * math.sin(t * 1.4 + i * 1.3))
            icons.draw_icon(frame, name, cx, cy, 110, C["violet"],
                            progress=fly, stroke_width=5)
            if fly >= 1.0:
                pulse_ring(frame, cx, 1000, 62, t, i * 0.33, C["violet"])
        # Closing gentle breathing on the headline.
        if t > 4.5:
            s = 1.0 + 0.02 * math.sin(t * 1.4)
            place_layer(kinetic.text_layer("حقیقت نیست.", F(54, "black"),
                        C["gold"]), frame, 540, 680, s, 1.0)
        return frame.convert("RGB")

    return render, {"active_layers": 5,
                    "impact_texts": ["حقیقت نیست."],
                    "ambient": ["parallax", "particles", "icon fly-in",
                                "badge draw", "breathing headline"]}
