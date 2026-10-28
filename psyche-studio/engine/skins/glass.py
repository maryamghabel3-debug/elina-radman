"""Style B — dark-glass kinetic.

Near-black premium gradient, warm orange bloom, perspective floor grid,
content-hugging frosted glass panels, metallic silver typography, orange
glow stamp-ins and an RTL progress bar. Faster, denser motion than a
typical dark-glass recipe: every phrase gets a kinetic event.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from engine import config
from engine.skins import base
from engine.skins.base import (W, H, FPS, SAFE_TOP, SUB_Y, font, persian,
                               text_size, draw_persian, ease_out_back,
                               ease_out, grain_layer)

TOP_BG = (5, 5, 8)
BOT_BG = (16, 17, 22)
ORANGE = (217, 119, 87)
GLASS = (46, 41, 42, 140)          # rgba(46,41,42,0.55)
BORDER = (255, 255, 255, 26)       # rgba(255,255,255,0.10)
SILVER_HI = (245, 247, 250)
SILVER_LO = (167, 172, 184)
ROLE_GLOW = {"trigger": (242, 181, 68), "negative": (255, 122, 102),
             "reality": (108, 205, 176), "structure": (124, 111, 224)}


def _vertical_gradient(size, top, bottom):
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(size[1]):
        p = y / max(1, size[1] - 1)
        px_row = tuple(int(top[k] * (1 - p) + bottom[k] * p) for k in range(3))
        for x in range(size[0]):
            px[x, y] = px_row
    return img


class GlassKinetic:
    def __init__(self, duration: float):
        self.duration = duration
        self._prerender()

    def _prerender(self):
        self.bg = _vertical_gradient((W, H), TOP_BG, BOT_BG).convert("RGBA")
        # warm orange bloom sprite
        bloom = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bloom)
        for r, a in ((440, 18), (340, 26), (240, 34), (150, 44)):
            bd.ellipse([450 - r, 450 - r, 450 + r, 450 + r],
                       fill=ORANGE + (a,))
        self.bloom = bloom.filter(ImageFilter.GaussianBlur(60))
        # orange glow for stamp-ins
        glow = Image.new("RGBA", (700, 700), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for r, a in ((330, 30), (240, 46), (150, 66), (80, 90)):
            gd.ellipse([350 - r, 350 - r, 350 + r, 350 + r],
                       fill=ORANGE + (a,))
        self.glow = glow.filter(ImageFilter.GaussianBlur(34))
        rng = random.Random(33)
        self.particles = [{"x": rng.randint(40, W - 40), "y": rng.randint(260, H - 200),
                           "spd": rng.uniform(0.2, 0.6), "ph": rng.uniform(0, 6.28),
                           "r": rng.choice([2, 3, 4])} for _ in range(26)]
        self.bg.alpha_composite(grain_layer(W, H, sigma=7, alpha=9, seed=5), (0, 0))

    # ----------------------------- pieces ---------------------------------
    @lru_cache(maxsize=48)
    def metallic_text(self, text: str, size: int, black: bool = False):
        fnt = font(base.FONT_K if black else base.FONT_B, size)
        tw, th = text_size(text, fnt)
        pad = 18
        img = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
        mask = Image.new("L", img.size, 0)
        draw_persian(ImageDraw.Draw(mask), (img.width / 2, img.height / 2),
                     text, fnt, 255)
        grad = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gp = grad.load()
        for y in range(img.height):
            p = y / max(1, img.height - 1)
            c = tuple(int(SILVER_HI[k] * (1 - p) + SILVER_LO[k] * p)
                      for k in range(3)) + (255,)
            for x in range(img.width):
                gp[x, y] = c
        img = Image.composite(grad, img, mask)
        return img

    def glass_panel(self, text: str, role: str | None, size: int) -> Image.Image:
        # wrap to content-hugging width (max 84 % of frame); auto-shrinks size
        from engine.text import wrap_persian
        max_w = int(W * 0.84) - 96
        wrapped = wrap_persian(text, str(config.FONT_BOLD), max_w,
                               start_size=size, min_size=34)
        lines = [(ln, font(base.FONT_B, sz)) for ln, sz in wrapped]
        line_h = max(int(fnt.size * 1.42) for _, fnt in lines)
        tw = max(text_size(ln, fnt)[0] for ln, fnt in lines)
        w, h = tw + 96, line_h * len(lines) + 64
        img = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0))
        panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        pd.rounded_rectangle([0, 0, w, h], 36, fill=GLASS,
                             outline=BORDER, width=2)
        # top sheen
        pd.rounded_rectangle([2, 2, w - 2, h // 2], 34,
                             fill=(255, 255, 255, 10))
        accent = ROLE_GLOW.get(role, ORANGE)
        pd.rounded_rectangle([0, 0, 10, h], 6, fill=accent + (235,))
        img.alpha_composite(panel, (12, 12))
        d = ImageDraw.Draw(img)
        for k, (ln, fnt) in enumerate(lines):
            draw_persian(d, (w / 2 + 12, 32 + line_h * (k + 0.5)),
                         ln, fnt, SILVER_HI)
        return img

    # ----------------------------- frame ----------------------------------
    def draw(self, st) -> Image.Image:
        frame = self.bg.copy()
        d = ImageDraw.Draw(frame)
        t = st.t
        # drifting bloom
        bx = int(W * 0.62 + 90 * math.sin(t * 0.21))
        by = int(H * 0.26 + 70 * math.cos(t * 0.17))
        frame.alpha_composite(self.bloom, (bx - 450, by - 450))

        # perspective floor grid, scrolling toward viewer (kept subtle so
        # lines never fight the typography)
        vp = (W // 2, 640)
        for k in range(-6, 7):
            x_bottom = W // 2 + k * 210
            d.line([vp, (x_bottom, H)], fill=(255, 255, 255, 14), width=2)
        scroll = (t * 0.55) % 1.0
        for k in range(12):
            p = ((k + scroll) / 12) ** 2.2
            y = int(vp[1] + p * (H - vp[1]))
            a = int(10 + 26 * p)
            d.line([(0, y), (W, y)], fill=(255, 255, 255, a), width=2)
        # center scrim: keeps the content band readable above the grid
        scrim = Image.new("RGBA", (W, 760), (0, 0, 0, 0))
        sd = ImageDraw.Draw(scrim)
        sd.rounded_rectangle([60, 0, W - 60, 760], 60, fill=(8, 8, 12, 120))
        frame.alpha_composite(scrim, (0, 620))

        # particles, pulsing on visual beats
        pulse = max(0.0, 1.0 - abs(st.beat_phase) / 0.5)
        for k, pt in enumerate(self.particles):
            x = pt["x"] + 16 * math.sin(t * pt["spd"] + pt["ph"])
            y = (pt["y"] - t * 24 * pt["spd"]) % (H - 260) + 240
            r = pt["r"] + int(2.2 * pulse)
            a = 90 + int(120 * pulse)
            d.ellipse([x - r, y - r, x + r, y + r], fill=ORANGE + (a,))

        # stamp-in key word impacts with glow (dark halo keeps grid off text)
        slot_y = 880
        for age, imp in st.impacts:
            if age > 0.8 or imp.kind != "word":
                continue
            halo = Image.new("RGBA", (620, 260), (0, 0, 0, 0))
            ImageDraw.Draw(halo).rounded_rectangle(
                [0, 0, 620, 260], 50, fill=(5, 5, 9, 150))
            frame.alpha_composite(halo, (W // 2 - 310, slot_y - 130))
            txt = self.metallic_text(imp.text, 108, black=True)
            p = ease_out_back(min(age / 0.30, 1))
            txt = txt.resize((max(2, int(txt.width * p)), max(2, int(txt.height * p))))
            glow_a = max(0.0, 1.0 - age / 0.8)
            gs = int(420 * (0.8 + 0.4 * p))
            glow = self.glow.resize((gs, gs))
            frame.alpha_composite(glow,
                                  (W // 2 - gs // 2, slot_y - gs // 2))
            frame.alpha_composite(txt, (W // 2 - txt.width // 2,
                                        slot_y - txt.height // 2))
            slot_y += 170

        # current phrase inside a content-hugging glass panel
        if st.phrase:
            role = st.phrase.get("role")
            size = 50 if len(st.phrase["text"]) > 46 else 58
            panel = self.glass_panel(st.phrase["text"], role, size)
            age = st.phrase_age
            p = ease_out(min(age / 0.32, 1))
            panel = panel.resize((max(2, int(panel.width * p)), max(2, int(panel.height * p))))
            y = 1210 if t < 14.5 else 720
            px = min(max(20, W // 2 - panel.width // 2), W - 20 - panel.width)
            py = min(max(SAFE_TOP, y - panel.height // 2),
                     SUB_Y - 40 - panel.height)
            frame.alpha_composite(panel, (px, py))

        # subtitle, silver and pill-free, around y 1480
        if st.subtitle:
            fnt = font(base.FONT_M, 38)
            draw_persian(d, (W / 2, SUB_Y), st.subtitle, fnt, SILVER_LO)

        # RTL progress bar: fill grows from the RIGHT edge
        x0, x1, y0, y1 = 120, W - 120, 118, 130
        d.rounded_rectangle([x0, y0, x1, y1], 6, fill=(255, 255, 255, 22))
        fill_w = int((x1 - x0) * st.progress)
        if fill_w > 0:
            d.rounded_rectangle([x1 - fill_w, y0, x1, y1], 6, fill=ORANGE + (255,))
        # chapter dots, right-aligned
        for k in range(7):
            cx = x1 - k * 56
            on = st.progress * 7 >= k
            d.ellipse([cx - 8, 160, cx + 8, 176],
                      fill=ORANGE + (255,) if on else (255, 255, 255, 60))
        return frame.convert("RGB")
