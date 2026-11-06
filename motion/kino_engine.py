"""Kino — موتور رندر استایل «چلک روی مشکی» (chalk-on-black explainer).

این موتور از روی مهندسی معکوس نمونه‌ی `example.mp4` ساخته شده است.
مشخصات اندازه‌گیری‌شده‌ی آن نمونه:

    رزولوشن 720x1280 (9:16) · 30fps · h264
    پس‌زمینه  #000000 خالص (94.33% پیکسل‌ها دقیقاً صفر)
    خطوط      سفید خالص، ضخامت ۲–۳px در 720p، بدون هیچ رنگ تاکیدی
    هدر       نوار بالای صفحه با خط افقی + برچسب فصل در جعبه‌ی مورب (راست)
    بدنه      تصویرسازی خطی وسط کادر
    زیرنویس   پایین، ارتفاع حرف ۳۳px، کرااوکه کلمه‌به‌کلمه

استفاده:

    from agents.motion.kino_engine import KinoScene, EyeClock, Person, Label

    scene = KinoScene(duration=8.0, chapter="ترس اصلی")
    scene.add(EyeClock((360, 420), radius=92))
    scene.add(Person((360, 820), scale=1.0))
    scene.add(Label((470, 300), "باورهایت را", anchor="right"))
    scene.set_captions([(0.0, 4.0, "می‌شه و به ما دستور می‌ده")])

    scene.render("out/")   # فریم‌ها + mp4
"""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:  # فارسی‌نویسی
    import arabic_reshaper
    from bidi.algorithm import get_display

    _RESHAPE = True
except ImportError:  # pragma: no cover
    _RESHAPE = False

# ---------------------------------------------------------------- palette ----
# هیچ رنگ تاکیدی نداریم؛ نمونه ۱۰۰٪ خاکستری است (channel spread = 0.00).
BG = (0, 0, 0)
INK = (255, 255, 255)
INK_70 = (180, 180, 180)
INK_40 = (110, 110, 110)
INK_25 = (70, 70, 70)

# ---------------------------------------------------------------- metrics ----
BASE_W, BASE_H = 720, 1280
SS = 3  # supersampling برای خطوط نازک و تمیز

MARGIN = 47
HEADER_Y = 78
HEADER_TEXT = 20
RULE_Y = 96

STAGE_TOP = 170
STAGE_BOTTOM = 990
STAGE_CX, STAGE_CY = 360, 580

SUB_BASELINE = 1067
SUB_SIZE = 33
SUB_MAX_W = 0.86
STROKE = 3


def _fa(text: str) -> str:
    """شکل‌دهی فارسی + ترتیب بصری."""
    if not _RESHAPE:
        return text
    return get_display(arabic_reshaper.reshape(text))


def find_font() -> str:
    """وزیرمتن باندل‌شده در ریپو، وگرنه فونت سیستم."""
    repo = Path(__file__).resolve().parents[2]
    bundled = repo / "assets" / "fonts" / "Vazirmatn-Bold.ttf"
    if bundled.exists():
        return str(bundled)
    for cand in (
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(cand).exists():
            return cand
    raise FileNotFoundError("هیچ فونت فارسی‌ای پیدا نشد")


# ------------------------------------------------------------- easing ------
def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------ primitives ----
@dataclass
class Primitive:
    """یک عنصر قابل رسم. `t` پیشرفت ۰..۱ است."""

    at: float = 0.0      # زمان شروع (ثانیه)
    dur: float = 1.2     # مدت رسم (ثانیه)
    fade_out: Optional[float] = None  # زمان شروع محو شدن

    def progress(self, time: float) -> float:
        if time < self.at:
            return 0.0
        return ease_out((time - self.at) / self.dur) if self.dur > 0 else 1.0

    def opacity(self, time: float) -> float:
        if self.fade_out is None:
            return 1.0
        return max(0.0, 1 - (time - self.fade_out) / 0.6)


@dataclass
class Line(Primitive):
    p0: Tuple[float, float] = (0, 0)
    p1: Tuple[float, float] = (0, 0)
    width: int = STROKE
    color: Tuple[int, ...] = INK

    def draw(self, d: ImageDraw.ImageDraw, time: float, k: float) -> None:
        p = self.progress(time)
        if p <= 0:
            return
        x0, y0 = self.p0[0] * k, self.p0[1] * k
        x1, y1 = self.p1[0] * k, self.p1[1] * k
        d.line([(x0, y0), (x0 + (x1 - x0) * p, y0 + (y1 - y0) * p)],
               fill=self.color, width=int(self.width * k), joint="curve")


@dataclass
class Polyline(Primitive):
    points: List[Tuple[float, float]] = field(default_factory=list)
    width: int = STROKE
    color: Tuple[int, ...] = INK
    close: bool = False

    def draw(self, d: ImageDraw.ImageDraw, time: float, k: float) -> None:
        p = self.progress(time)
        if p <= 0 or len(self.points) < 2:
            return
        pts = [(x * k, y * k) for x, y in self.points]
        if self.close:
            pts = pts + [pts[0]]
        # طول تجمعی برای رسم نرم
        seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        total = sum(seg) or 1
        target = total * p
        acc = 0.0
        out = [pts[0]]
        for i, s in enumerate(seg):
            if acc + s <= target:
                out.append(pts[i + 1])
                acc += s
            else:
                r = (target - acc) / s if s else 0
                out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * r,
                            pts[i][1] + (pts[i + 1][1] - pts[i][1]) * r))
                break
        d.line(out, fill=self.color, width=int(self.width * k), joint="curve")


@dataclass
class Circle(Primitive):
    center: Tuple[float, float] = (0, 0)
    radius: float = 50
    width: int = STROKE
    color: Tuple[int, ...] = INK
    fill: bool = False

    def draw(self, d: ImageDraw.ImageDraw, time: float, k: float) -> None:
        p = self.progress(time)
        if p <= 0:
            return
        cx, cy = self.center[0] * k, self.center[1] * k
        r = self.radius * k
        w = int(self.width * k)
        if self.fill:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=self.color)
            return
        # رسم قوس‌به‌قوس (۳۶۰ درجه) برای حس «کشیده شدن»
        steps = 96
        pts = []
        for i in range(int(steps * p) + 1):
            a = -math.pi / 2 + 2 * math.pi * i / steps
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        if len(pts) > 1:
            d.line(pts, fill=self.color, width=w, joint="curve")


@dataclass
class Arc(Primitive):
    center: Tuple[float, float] = (0, 0)
    radius: float = 50
    a0: float = 0
    a1: float = 180  # درجه
    width: int = STROKE
    color: Tuple[int, ...] = INK

    def draw(self, d: ImageDraw.ImageDraw, time: float, k: float) -> None:
        p = self.progress(time)
        if p <= 0:
            return
        cx, cy = self.center[0] * k, self.center[1] * k
        r = self.radius * k
        a0, a1 = math.radians(self.a0), math.radians(self.a1)
        steps = max(2, int(72 * abs(self.a1 - self.a0) / 360))
        end = a0 + (a1 - a0) * p
        pts = [(cx + r * math.cos(a0 + (end - a0) * i / steps),
                cy + r * math.sin(a0 + (end - a0) * i / steps)) for i in range(steps + 1)]
        d.line(pts, fill=self.color, width=int(self.width * k), joint="curve")


@dataclass
class Ticks(Primitive):
    """تیک‌های دور یک دایره — موتیف تکرارشونده‌ی نمونه (ساعت/چشم)."""

    center: Tuple[float, float] = (0, 0)
    radius: float = 100
    count: int = 24
    length: float = 4
    skip_every: int = 6
    width: int = STROKE
    color: Tuple[int, ...] = INK_70

    def draw(self, d: ImageDraw.ImageDraw, time: float, k: float) -> None:
        p = self.progress(time)
        if p <= 0:
            return
        cx, cy = self.center[0] * k, self.center[1] * k
        for i in range(int(self.count * p)):
            a = 2 * math.pi * i / self.count
            r0, r1 = self.radius * k, (self.radius + self.length) * k
            d.line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                    (cx + r1 * math.cos(a), cy + r1 * math.sin(a))],
                   fill=self.color, width=int(self.width * k))


@dataclass
class Person(Primitive):
    """سیلوئت آدمک کوچک — پرتکرارترین عنصر نمونه."""

    center: Tuple[float, float] = (0, 0)
    scale: float = 1.0
    width: int = STROKE
    color: Tuple[int, ...] = INK
    arms: str = "down"

    def draw(self, d: ImageDraw.ImageDraw, time: float, k: float) -> None:
        p = self.progress(time)
        if p <= 0:
            return
        s = self.scale * k
        cx, cy = self.center[0] * k, self.center[1] * k
        w = int(self.width * k)

        # ---- تناسب اندازه‌گیری‌شده از نمونه: فرد ۵۷×۱۱۳ px در 720p ----
        #  سر 0–27٪ · شانه 28٪ · کمر 60٪ · باسن 66٪ · پا 66–100٪
        H = 113.0 * s
        TOP = cy - H / 2
        BOT = cy + H / 2

        f_head  = 0.27   # پایان سر
        f_sh    = 0.29   # شانه
        f_waist = 0.60
        f_hip   = 0.66

        hw  = 12.5 * s                 # نیم‌عرض سر (۲۵/۵۷)
        head_bot = TOP + H * f_head
        sh_y     = TOP + H * f_sh
        waist_y  = TOP + H * f_waist
        hip_y    = TOP + H * f_hip

        sh_hw   = 27.0 * s             # شانه پهن (۵۴/۵۷)
        body_hw = 19.0 * s             # نیم‌عرض بدن
        arm_hw  = 26.0 * s             # بازو، بیرون بدن
        leg_hw  = 20.5 * s             # بیرونی‌ترین لبه‌ی پا
        gap_hw  = 4.0 * s              # نیم‌فاصله‌ی بین دو پا

        def L(a, b):
            d.line([a, b], fill=self.color, width=w, joint="curve")

        # ۱) سر — بیضی، کمی بلندتر از دایره
        ht = head_bot - TOP
        d.ellipse([cx - hw, TOP, cx + hw, TOP + ht], outline=self.color, width=w)
        if p <= 0.15:
            return
        # ۲) گردن — خیلی کوتاه
        L((cx, head_bot - 1.0 * s), (cx, sh_y))
        if p <= 0.3:
            return
        # ۳) شانه — گنبد کم‌ارتفاع از چپ به راست
        sh_pts = [(cx - sh_hw + (2 * sh_hw) * i / 16,
                   sh_y + 4.0 * s * math.sin(math.pi * i / 16)) for i in range(17)]
        d.line(sh_pts, fill=self.color, width=w, joint="curve")
        if p <= 0.45:
            return
        # ۴) پهلو — از شانه به کمر
        L((cx - sh_hw + 2.0 * s, sh_y + 3.0 * s), (cx - body_hw, waist_y))
        L((cx + sh_hw - 2.0 * s, sh_y + 3.0 * s), (cx + body_hw, waist_y))
        if p <= 0.6:
            return
        # ۵) بازو — عمودی، چسبیده و کمی جدا
        L((cx - arm_hw, sh_y + 4.0 * s), (cx - arm_hw + 0.5 * s, waist_y + 2.0 * s))
        L((cx + arm_hw, sh_y + 4.0 * s), (cx + arm_hw - 0.5 * s, waist_y + 2.0 * s))
        if p <= 0.8:
            return
        # ۶) کمر → باسن (بستن بدن)
        L((cx - body_hw, waist_y), (cx - leg_hw, hip_y))
        L((cx + body_hw, waist_y), (cx + leg_hw, hip_y))
        # ۷) پاها — دو ستون تا کف
        L((cx - leg_hw, hip_y), (cx - leg_hw, BOT))
        L((cx - gap_hw, hip_y), (cx - gap_hw, BOT))
        L((cx + leg_hw, hip_y), (cx + leg_hw, BOT))
        L((cx + gap_hw, hip_y), (cx + gap_hw, BOT))
        # بالای شکاف
        L((cx - gap_hw, hip_y), (cx + gap_hw, hip_y))


@dataclass
class Label(Primitive):
    """برچسب متنی کنار شکل، با خط راهنما."""

    pos: Tuple[float, float] = (0, 0)
    text: str = ""
    size: int = 22
    anchor: str = "right"   # right | left | center
    color: Tuple[int, ...] = INK
    leader_to: Optional[Tuple[float, float]] = None

    def draw(self, d: ImageDraw.ImageDraw, time: float, k: float, font: ImageFont.FreeTypeFont) -> None:
        p = self.progress(time)
        if p <= 0:
            return
        if self.leader_to:
            Line(p0=self.leader_to, p1=self.pos, width=STROKE, at=self.at, dur=self.dur).draw(d, time, k)
        shaped = _fa(self.text)
        x, y = self.pos[0] * k, self.pos[1] * k
        if self.anchor == "right":
            d.text((x, y), shaped, font=font, fill=self.color, anchor="rs")
        elif self.anchor == "left":
            d.text((x, y), shaped, font=font, fill=self.color, anchor="ls")
        else:
            d.text((x, y), shaped, font=font, fill=self.color, anchor="ms")


# ------------------------------------------------------------- the scene ----
class KinoScene:
    def __init__(self, duration: float = 10.0, chapter: str = "", fps: int = 30):
        self.duration = duration
        self.chapter = chapter
        self.fps = fps
        self.items: List[Primitive] = []
        self.captions: List[Tuple[float, float, str]] = []
        self._font_cache: dict = {}

    # -- construction --------------------------------------------------
    def add(self, item: Primitive) -> "KinoScene":
        self.items.append(item)
        return self

    def extend(self, items: Sequence[Primitive]) -> "KinoScene":
        self.items.extend(items)
        return self

    def set_captions(self, captions: Sequence[Tuple[float, float, str]]) -> "KinoScene":
        self.captions = list(captions)
        return self

    # -- fonts ---------------------------------------------------------
    def _font(self, px: int, k: float) -> ImageFont.FreeTypeFont:
        key = (px, round(k, 3))
        if key not in self._font_cache:
            self._font_cache[key] = ImageFont.truetype(find_font(), int(px * k))
        return self._font_cache[key]

    # -- drawing -------------------------------------------------------
    def _draw_header(self, d: ImageDraw.ImageDraw, k: float) -> None:
        w = BASE_W * k
        y = RULE_Y * k
        # خط افقی هدر
        d.line([(MARGIN * k, y), (w - MARGIN * k, y)], fill=INK_40, width=max(1, int(1.2 * k)))
        if not self.chapter:
            return
        f_small = self._font(15, k)
        f_main = self._font(HEADER_TEXT, k)
        label = _fa("پرونده")
        chapter = _fa(self.chapter)
        # جعبه‌ی مورب سمت راست (RTL)
        pad = 12 * k
        tw = d.textlength(chapter, font=f_main)
        sw = d.textlength(label, font=f_small)
        box_w = tw + sw + pad * 3
        x1 = w - MARGIN * k
        x0 = x1 - box_w
        top = HEADER_Y * k - 22 * k
        bot = HEADER_Y * k + 10 * k
        d.line([(x0, bot), (x0 + 9 * k, top), (x1, top)], fill=INK_70, width=max(1, int(1.4 * k)))
        d.line([(x1, top), (x1, bot)], fill=INK_70, width=max(1, int(1.4 * k)))
        d.text((x1 - pad, HEADER_Y * k), chapter, font=f_main, fill=INK, anchor="rm")
        d.text((x0 + pad * 0.7, HEADER_Y * k), label, font=f_small, fill=INK_40, anchor="rm")

    def _draw_karaoke(self, d: ImageDraw.ImageDraw, k: float, text: str,
                      t_local: float, t_total: float) -> None:
        """زیرنویس کرااوکه: کلمه‌ی جاری سفید، بقیه خاکستری."""
        words = text.split()
        if not words:
            return
        f = self._font(SUB_SIZE, k)
        gap = d.textlength(" ", font=f)
        shaped = [_fa(wd) for wd in words]
        widths = [d.textlength(s, font=f) for s in shaped]
        total = sum(widths) + gap * (len(words) - 1)
        max_w = BASE_W * SUB_MAX_W * k
        if total > max_w:  # کوچک‌سازی خودکار
            f = self._font(int(SUB_SIZE * max_w / total), k)
            widths = [d.textlength(s, font=f) for s in shaped]
            gap = d.textlength(" ", font=f)
            total = sum(widths) + gap * (len(words) - 1)

        # کدام کلمه فعال است
        idx = int(min(len(words) - 1, max(0, (t_local / max(t_total, 1e-6)) * len(words))))
        x = (BASE_W * k + total) / 2          # شروع از راست
        y = SUB_BASELINE * k
        for i, s in enumerate(shaped):
            x -= widths[i]
            col = INK if i <= idx else INK_40
            d.text((x, y), s, font=f, fill=col, anchor="ls")
            x -= gap

    def frame(self, time: float) -> Image.Image:
        W, H = BASE_W * SS, BASE_H * SS
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        k = SS

        self._draw_header(d, k)

        for it in self.items:
            op = it.opacity(time)
            if op <= 0:
                continue
            if isinstance(it, Label):
                f = self._font(it.size, k)
                if op < 1.0:
                    tmp = Image.new("RGB", (W, H), BG)
                    td = ImageDraw.Draw(tmp)
                    it.draw(td, time, k, f)
                    img.paste(Image.blend(img, tmp, op))
                else:
                    it.draw(d, time, k, f)
            else:
                it.draw(d, time, k)

        for (t0, t1, text) in self.captions:
            if t0 <= time <= t1:
                self._draw_karaoke(d, k, text, time - t0, t1 - t0)

        return img.resize((BASE_W, BASE_H), Image.LANCZOS)

    # -- rendering -----------------------------------------------------
    def render(self, out_dir: str | Path, ffmpeg: Optional[str] = None,
               audio: Optional[str] = None) -> Path:
        out_dir = Path(out_dir)
        frames_dir = out_dir / "frames"
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        frames_dir.mkdir(parents=True, exist_ok=True)

        n = int(self.duration * self.fps)
        for i in range(n):
            self.frame(i / self.fps).save(frames_dir / f"{i:05d}.png")

        mp4 = out_dir / f"{out_dir.name}.mp4"
        ff = ffmpeg or shutil.which("ffmpeg") or _bundled_ffmpeg()
        cmd = [ff, "-y", "-loglevel", "error",
               "-framerate", str(self.fps), "-i", str(frames_dir / "%05d.png")]
        if audio:
            cmd += ["-i", audio, "-shortest", "-c:a", "aac", "-b:a", "128k"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                "-preset", "medium", str(mp4)]
        subprocess.run(cmd, check=True)
        return mp4


def _bundled_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError("ffmpeg پیدا نشد؛ نصب کنید یا imageio-ffmpeg بدهید")


# ------------------------------------------------------------- presets ------
def eye_clock(center: Tuple[float, float], radius: float = 92, at: float = 0.0) -> List[Primitive]:
    """موتیف مکرر نمونه: دایره‌ی چشم/ساعت با تیک و پیکان پایین."""
    cx, cy = center
    return [
        Circle(center=(cx, cy), radius=radius, at=at, dur=1.4),
        Circle(center=(cx, cy), radius=radius * 0.62, at=at + 0.25, dur=1.1),
        Circle(center=(cx, cy), radius=radius * 0.17, fill=True, at=at + 0.7, dur=0.35),
        Circle(center=(cx - radius * 0.07, cy - radius * 0.07),
               radius=radius * 0.055, fill=True, color=BG, at=at + 0.95, dur=0.25),
        Ticks(center=(cx, cy), radius=radius + 9, count=28, length=5, at=at + 0.5, dur=1.6),
        Line(p0=(cx, cy + radius + 22), p1=(cx, cy + radius + 150), at=at + 1.2, dur=0.9),
    ]


# --------------------------------------------------------- SVG path --------
_PATH_TOKEN = __import__("re").compile(r"[MLCQZmlcqz]|-?\d*\.?\d+")


def _parse_svg_path(d: str) -> List[List[Tuple[float, float]]]:
    """پارسر مینیمال SVG path: M/L/C/Q/Z.

    برای بازسازی دقیق آیکون‌ها لازم است؛ سیلوئت‌های دست‌ساز (مثل `Person`)
    هرگز به اندازه‌ی مسیر اصلی دقیق نمی‌شوند. مسیر را از Figma/Illustrator
    به‌صورت «Export SVG» بگیرید و مقدار `d` را اینجا بدهید.
    """
    import re
    toks = re.findall(r"[MLCQZmlcqz]|-?\d*\.?\d+", d)
    subpaths: List[List[Tuple[float, float]]] = []
    cur: List[Tuple[float, float]] = []
    i, cmd = 0, None
    x = y = 0.0
    start_x = start_y = 0.0
    while i < len(toks):
        t = toks[i]
        if t.upper() in "MLCQZ":
            cmd = t
            i += 1
            if cmd.upper() == "Z":
                if cur:
                    cur.append((start_x, start_y))
                    subpaths.append(cur)
                    cur = []
                continue
            continue
        def num():
            nonlocal i
            v = float(toks[i]); i += 1
            return v
        if cmd in ("M", "m"):
            nx, ny = num(), num()
            x, y = (nx, ny) if cmd == "M" else (x + nx, y + ny)
            if cur:
                subpaths.append(cur)
            cur = [(x, y)]
            start_x, start_y = x, y
            cmd = "L" if cmd == "M" else "l"
        elif cmd in ("L", "l"):
            nx, ny = num(), num()
            x, y = (nx, ny) if cmd == "L" else (x + nx, y + ny)
            cur.append((x, y))
        elif cmd in ("C", "c"):
            pts = [num() for _ in range(6)]
            if cmd == "c":
                pts = [pts[0] + x, pts[1] + y, pts[2] + x, pts[3] + y, pts[4] + x, pts[5] + y]
            x0, y0 = x, y
            for k in range(1, 13):
                tt = k / 12
                mt = 1 - tt
                bx = (mt**3) * x0 + 3 * (mt**2) * tt * pts[0] + 3 * mt * (tt**2) * pts[2] + (tt**3) * pts[4]
                by = (mt**3) * y0 + 3 * (mt**2) * tt * pts[1] + 3 * mt * (tt**2) * pts[3] + (tt**3) * pts[5]
                cur.append((bx, by))
            x, y = pts[4], pts[5]
        elif cmd in ("Q", "q"):
            pts = [num() for _ in range(4)]
            if cmd == "q":
                pts = [pts[0] + x, pts[1] + y, pts[2] + x, pts[3] + y]
            x0, y0 = x, y
            for k in range(1, 13):
                tt = k / 12
                mt = 1 - tt
                bx = (mt**2) * x0 + 2 * mt * tt * pts[0] + (tt**2) * pts[2]
                by = (mt**2) * y0 + 2 * mt * tt * pts[1] + (tt**2) * pts[3]
                cur.append((bx, by))
            x, y = pts[2], pts[3]
        else:
            i += 1
    if cur:
        subpaths.append(cur)
    return subpaths


@dataclass
class SvgPath(Primitive):
    """رسم مسیر SVG با انیمیشن خط‌کشی — راه دقیق بازسازی آیکون‌ها.

    مثال:
        SvgPath(d="M 10 10 L 50 10 L 50 50 Z", origin=(300, 400), scale=2.0)
    """

    d: str = ""
    origin: Tuple[float, float] = (0, 0)
    scale: float = 1.0
    width: int = STROKE
    color: Tuple[int, ...] = INK

    def draw(self, d: ImageDraw.ImageDraw, time: float, k: float) -> None:
        p = self.progress(time)
        if p <= 0:
            return
        subpaths = _parse_svg_path(self.d)
        segs = []
        for sp in subpaths:
            pts = [(self.origin[0] * k + x * self.scale * k,
                    self.origin[1] * k + y * self.scale * k) for x, y in sp]
            segs.append(pts)
        total = sum(math.dist(pts[i], pts[i + 1]) for pts in segs for i in range(len(pts) - 1)) or 1
        target = total * p
        acc = 0.0
        for pts in segs:
            out = [pts[0]]
            for i in range(len(pts) - 1):
                sg = math.dist(pts[i], pts[i + 1])
                if acc + sg <= target:
                    out.append(pts[i + 1]); acc += sg
                else:
                    r = (target - acc) / sg if sg else 0
                    out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * r,
                                pts[i][1] + (pts[i + 1][1] - pts[i][1]) * r))
                    acc = target
                    break
            if len(out) > 1:
                d.line(out, fill=self.color, width=int(self.width * k), joint="curve")
            if acc >= target:
                break
