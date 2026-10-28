"""Style A — paper-cut.

Layered paper cutouts on a cream sheet: grain, torn thought clouds, soft
shadows, stop-motion 12 fps micro-jitter on foreground paper, word chips that
slap on with overshoot and slight rotation. Camera/parallax stay smooth.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from engine.skins import base
from engine.skins.base import (W, H, FPS, SAFE_TOP, SUB_Y, font, persian,
                               text_size, draw_persian, rounded_shadow,
                               ease_out_back, ease_out, jitter_12fps,
                               grain_layer)

CREAM = (244, 235, 221)
PAPER_LIGHT = (250, 244, 233)
PAPER_DARK = (231, 219, 201)
INK = (27, 27, 47)
INDIGO = (59, 63, 143)
VIOLET = (124, 111, 224)
CORAL = (255, 122, 102)
MUSTARD = (242, 181, 68)
MINT = (108, 205, 176)

ROLE_FILL = {"trigger": MUSTARD, "negative": CORAL, "reality": MINT,
             "structure": VIOLET, "ambient": PAPER_LIGHT}
ROLE_TEXT = {"trigger": INK, "negative": (255, 255, 255), "reality": INK,
             "structure": (255, 255, 255), "ambient": INK}


class PaperCut:
    def __init__(self, duration: float):
        self.duration = duration
        self._prerender()

    # ----------------------------- assets ---------------------------------
    def _prerender(self) -> None:
        bg = Image.new("RGBA", (W, H), CREAM + (255,))
        d = ImageDraw.Draw(bg)
        # layered paper sheets, slightly rotated, with soft shadows
        sheet = Image.new("RGBA", (980, 1500), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sheet)
        sd.rounded_rectangle([0, 0, 980, 1500], 48, fill=PAPER_LIGHT + (255,))
        sh = rounded_shadow((980, 1500), 48, blur=22, alpha=55)
        pad = 66
        bg.alpha_composite(sh.rotate(-1.2, resample=Image.BICUBIC, expand=True),
                           (60 - pad + 14, 180 - pad + 18))
        bg.alpha_composite(sheet.rotate(-1.2, resample=Image.BICUBIC, expand=True),
                           (60, 180))
        sheet2 = Image.new("RGBA", (860, 760), (0, 0, 0, 0))
        ImageDraw.Draw(sheet2).rounded_rectangle(
            [0, 0, 860, 760], 40, fill=PAPER_DARK + (120,))
        bg.alpha_composite(sheet2.rotate(1.6, resample=Image.BICUBIC, expand=True),
                           (180, 980))
        bg.alpha_composite(grain_layer(W, H, sigma=10, alpha=14, seed=11), (0, 0))
        self.bg = bg
        # ambient floating paper confetti (shape, size, color, orbit params)
        rng = random.Random(21)
        self.floaters = []
        for _ in range(14):
            shape = rng.choice(["circle", "tri", "strip"])
            size = rng.randint(18, 46)
            color = rng.choice([VIOLET, CORAL, MUSTARD, MINT, INDIGO])
            self.floaters.append({
                "shape": shape, "size": size, "color": color,
                "x": rng.randint(60, W - 60), "y": rng.randint(300, H - 260),
                "spd": rng.uniform(0.15, 0.45), "ph": rng.uniform(0, 6.28),
                "amp": rng.randint(14, 38)})

    # ----------------------------- pieces ---------------------------------
    @staticmethod
    @lru_cache(maxsize=64)
    def _chip(text: str, role: str, size: int, key: int) -> Image.Image:
        from engine.text import wrap_persian
        from engine import config
        fnt_path = base.FONT_K if size >= 80 else base.FONT_B
        max_w = int(W * 0.84) - 92
        wrapped = wrap_persian(text, fnt_path, max_w, start_size=size,
                               min_size=34)
        lines = [(ln, font(fnt_path, sz)) for ln, sz in wrapped]
        line_h = max(int(f.size * 1.34) for _, f in lines)
        tw = max(text_size(ln, f)[0] for ln, f in lines)
        th = line_h * len(lines)
        pad_x, pad_y = 46, 30
        w, h = tw + 2 * pad_x, th + 2 * pad_y
        img = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
        shadow = rounded_shadow((w, h), 34, blur=12, alpha=80)
        img.alpha_composite(shadow, (40 - 36, 40 - 36))
        panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        pd.rounded_rectangle([0, 0, w, h], 34,
                             fill=ROLE_FILL[role] + (255,))
        # torn paper highlight strip along the bottom edge
        pd.rounded_rectangle([0, h - 14, w, h], 8,
                             fill=(255, 255, 255, 38))
        img.alpha_composite(panel, (40, 40))
        d = ImageDraw.Draw(img)
        for k, (ln, f) in enumerate(lines):
            draw_persian(d, (40 + w / 2, 40 + pad_y + line_h * (k + 0.5)),
                         ln, f, ROLE_TEXT[role])
        return img

    def _thought_cloud(self, text: str, role: str, size: int) -> Image.Image:
        from engine.text import wrap_persian
        max_w = int(W * 0.80) - 140
        wrapped = wrap_persian(text, base.FONT_B, max_w,
                               start_size=size, min_size=32)
        lines = [(ln, font(base.FONT_B, sz)) for ln, sz in wrapped]
        line_h = max(int(f.size * 1.36) for _, f in lines)
        tw = max(text_size(ln, f)[0] for ln, f in lines)
        w = tw + 140
        h = line_h * len(lines) + 110
        img = Image.new("RGBA", (w + 90, h + 90), (0, 0, 0, 0))
        shadow = rounded_shadow((w, h), 70, blur=14, alpha=75)
        img.alpha_composite(shadow, (45 - 42, 45 - 42))
        cloud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cloud)
        fill = (CORAL if role == "negative" else PAPER_LIGHT) + (255,)
        cd.rounded_rectangle([0, 30, w, h], 60, fill=fill)
        # two small top bumps only, fully inside the sheet
        for cx, cy, r in ((78, 34, 34), (w - 96, 30, 42)):
            cd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
        # little thought tail bubbles (bottom-right, RTL reading side)
        for k, r in enumerate((18, 11, 7)):
            cx = w - 70 - k * 30
            cy = h + 4 + k * 22
            cd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
        img.alpha_composite(cloud, (45, 45))
        txt_color = (255, 255, 255) if role == "negative" else INK
        d = ImageDraw.Draw(img)
        for k, (ln, f) in enumerate(lines):
            draw_persian(d, (45 + w / 2,
                             45 + 52 + line_h * (k + 0.5)), ln, f, txt_color)
        return img

    def _phone(self, t: float, driver_state) -> Image.Image:
        pw, ph = 470, 760
        img = Image.new("RGBA", (pw + 120, ph + 160), (0, 0, 0, 0))
        sh = rounded_shadow((pw, ph), 70, blur=18, alpha=90)
        img.alpha_composite(sh, (60 - 54, 50 - 54))
        body = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        bd = ImageDraw.Draw(body)
        bd.rounded_rectangle([0, 0, pw, ph], 70, fill=INK + (255,))
        bd.rounded_rectangle([22, 22, pw - 22, ph - 22], 52,
                             fill=PAPER_LIGHT + (255,))
        bd.rounded_rectangle([pw / 2 - 60, 44, pw / 2 + 60, 58], 8,
                             fill=PAPER_DARK + (255,))
        img.alpha_composite(body, (60, 50))
        # chat bubble carrying the trigger word when it impacts
        for age, imp in driver_state.impacts:
            if imp.role == "trigger" and imp.kind == "word" and age < 2.5:
                chip = self._chip(imp.text, "trigger", 72, hash(imp.text) % 99)
                p = ease_out_back(min(age / 0.35, 1))
                chip = chip.resize((max(2, int(chip.width * p)), max(2, int(chip.height * p))))
                img.alpha_composite(chip, (60 + pw // 2 - chip.width // 2,
                                           50 + 240 - chip.height // 2))
        return img

    # ----------------------------- frame ----------------------------------
    def draw(self, st) -> Image.Image:
        frame = self.bg.copy()
        d = ImageDraw.Draw(frame)
        t = st.t
        # smooth parallax floaters (camera layer stays smooth; only foreground
        # paper gets the 12 fps jitter)
        for k, fl in enumerate(self.floaters):
            x = fl["x"] + fl["amp"] * math.sin(t * fl["spd"] + fl["ph"])
            y = fl["y"] + fl["amp"] * 0.6 * math.cos(t * fl["spd"] * 0.8 + fl["ph"])
            r = fl["size"] // 2
            col = fl["color"] + (200,)
            if fl["shape"] == "circle":
                d.ellipse([x - r, y - r, x + r, y + r], fill=col)
            elif fl["shape"] == "tri":
                d.polygon([(x, y - r), (x + r, y + r), (x - r, y + r)], fill=col)
            else:
                d.rounded_rectangle([x - r * 1.6, y - r // 2, x + r * 1.6,
                                     y + r // 2], 8, fill=col)

        # paper phone for the hook / باشه section (first ~14 s)
        if t < 14.5:
            phone = self._phone(t, st)
            bob = int(10 * math.sin(t * 1.3))
            frame.alpha_composite(phone, (W // 2 - phone.width // 2,
                                          560 + bob - phone.height // 2))

        # impact chips slapping onto the sheet
        slot_y = 980
        for k, (age, imp) in enumerate(st.impacts):
            if age > 0.75 or imp.kind != "word":
                continue
            chip = self._chip(imp.text, imp.role or "structure", 92, k)
            p = ease_out_back(min(age / 0.32, 1))
            rot = -6 * (1 - min(age / 0.4, 1))
            chip = chip.resize((max(2, int(chip.width * p)), max(2, int(chip.height * p)))) \
                       .rotate(rot, expand=True, resample=Image.BICUBIC)
            jx, jy = jitter_12fps(t, k + 5, amp=2)
            cx = min(max(20, W // 2 - chip.width // 2 + jx), W - 20 - chip.width)
            frame.alpha_composite(chip, (cx, slot_y - chip.height // 2 + jy))
            slot_y += 150

        # current phrase: thought cloud for negatives, paper chip otherwise
        if st.phrase:
            role = st.phrase.get("role") or "ambient"
            size = 48 if len(st.phrase["text"]) > 48 else 56
            if role == "negative":
                panel = self._thought_cloud(st.phrase["text"], "negative", size)
            else:
                panel = self._chip(st.phrase["text"], role, size,
                                   st.phrase["phrase_id"])
            age = st.phrase_age
            p = ease_out_back(min(age / 0.4, 1)) if age < 0.5 else 1.0
            jx, jy = jitter_12fps(t, st.phrase["phrase_id"], amp=3)
            panel = panel.resize((max(2, int(panel.width * p)), max(2, int(panel.height * p))))
            y = 1260 if t < 14.5 else 760
            px = min(max(20, W // 2 - panel.width // 2 + jx), W - 20 - panel.width)
            py = min(max(SAFE_TOP, y - panel.height // 2 + jy),
                     SUB_Y - 40 - panel.height)
            frame.alpha_composite(panel, (px, py))

        # subtitle (light, no heavy pill): ink text with a thin paper rule
        if st.subtitle:
            fnt = font(base.FONT_M, 38)
            tw, th = text_size(st.subtitle, fnt)
            tw = min(tw, int(W * 0.86))
            draw_persian(d, (W / 2, SUB_Y), st.subtitle, fnt, INK)
            d.rounded_rectangle([W / 2 - tw / 2, SUB_Y + th / 2 + 14,
                                 W / 2 + tw / 2, SUB_Y + th / 2 + 20],
                                4, fill=VIOLET + (220,))

        # paper progress strip (top) and chapter dots
        d.rounded_rectangle([120, 120, W - 120, 134], 7, fill=PAPER_DARK + (255,))
        d.rounded_rectangle([120, 120, 120 + int((W - 240) * st.progress), 134],
                            7, fill=INDIGO + (255,))
        for k in range(7):
            cx = W - 150 - k * 56
            on = st.progress * 7 >= k
            d.ellipse([cx - 9, 168 - 9, cx + 9, 168 + 9],
                      fill=MUSTARD + (255,) if on else PAPER_DARK + (255,))
        return frame.convert("RGB")
