"""Probe F — render-speed benchmark for a realistic motion-graphics frame.

Each of 100 frames (1080x1920) contains:
  1. a background photo with a Ken Burns zoom (center crop + resize, 1.0->1.12)
  2. a dark vertical gradient overlay (precomputed once)
  3. one Persian text line (arabic-reshaper + python-bidi, Vazirmatn Bold)

Two resampling filters are benchmarked: LANCZOS (quality) and BILINEAR
(fast). Total wall time, per-frame time, and an extrapolation to 2700
frames (90 s at 30 fps) are printed. No video is encoded — this isolates
the Pillow/numpy frame-generation cost.
"""
import time
from pathlib import Path

import arabic_reshaper
import numpy as np
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
BG_PATH = HERE.parent / "assets" / "images" / "probe_e_vertical.jpg"
FONT_PATH = HERE.parent / "assets" / "fonts" / "Vazirmatn-Bold.ttf"

W, H, N = 1080, 1920, 100
TEXT = "ذهن شما کارهای نیمه‌تمام را فراموش نمی‌کند"

font = ImageFont.truetype(FONT_PATH, 58)
_reshaper = arabic_reshaper.ArabicReshaper(
    configuration={"delete_harakat": False}
)
visual = get_display(_reshaper.reshape(TEXT))

src = Image.open(BG_PATH).convert("RGB")
sw, sh = src.size
target_aspect = W / H
base_cw = float(sw)
base_ch = sw / target_aspect
if base_ch > sh:
    base_ch = float(sh)
    base_cw = sh * target_aspect

# Dark gradient overlay, built ONCE (alpha 0 -> 150 toward the bottom)
alpha = np.zeros((H, W), dtype=np.uint8)
for y in range(H):
    alpha[y, :] = int(150 * max(0.0, (y - H * 0.45) / (H * 0.55)))
gradient = Image.fromarray(
    np.dstack([np.zeros((H, W, 3), dtype=np.uint8), alpha]), "RGBA"
)

bbox_dummy = ImageDraw.Draw(Image.new("RGB", (4, 4))).textbbox(
    (0, 0), visual, font=font
)
text_w = bbox_dummy[2] - bbox_dummy[0]
text_x = (W - text_w) // 2 - bbox_dummy[0]
text_y = H - 260

stage_times = {"crop_resize": 0.0, "overlay": 0.0, "text": 0.0}


def make_frame(i: int, resample) -> Image.Image:
    z = 1.0 + 0.12 * (i / (N - 1))
    cw, ch = base_cw / z, base_ch / z
    left, top = (sw - cw) / 2, (sh - ch) / 2

    t0 = time.perf_counter()
    im = src.crop((left, top, left + cw, top + ch)).resize((W, H), resample)
    t1 = time.perf_counter()

    im = im.convert("RGBA")
    im.alpha_composite(gradient)
    t2 = time.perf_counter()

    draw = ImageDraw.Draw(im)
    draw.text((text_x, text_y), visual, font=font, fill=(245, 240, 232))
    t3 = time.perf_counter()

    stage_times["crop_resize"] += t1 - t0
    stage_times["overlay"] += t2 - t1
    stage_times["text"] += t3 - t2
    return im.convert("RGB")


# Warm-up (font caches, allocator) — excluded from timing
for i in range(3):
    make_frame(i, Image.LANCZOS)
stage_times = {k: 0.0 for k in stage_times}

for label, resample in (("LANCZOS", Image.LANCZOS), ("BILINEAR", Image.BILINEAR)):
    stage_times = {k: 0.0 for k in stage_times}
    t_start = time.perf_counter()
    for i in range(N):
        make_frame(i, resample)
    total = time.perf_counter() - t_start
    per_frame = total / N
    print(f"--- {label} ---")
    print(f"total for {N} frames : {total:.3f} s")
    print(f"per frame            : {per_frame*1000:.1f} ms")
    print(f"extrapolated 2700    : {per_frame*2700:.1f} s "
          f"({per_frame*2700/60:.1f} min)")
    if label == "LANCZOS":
        for k, v in stage_times.items():
            print(f"  stage {k:12}: {v/N*1000:6.1f} ms/frame "
                  f"({v/total*100:4.1f}% of total)")
