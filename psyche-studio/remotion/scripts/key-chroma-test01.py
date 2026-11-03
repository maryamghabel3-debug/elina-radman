#!/usr/bin/env python3
"""Key flat green sources for EliElinaTest01 into 1080x1920 RGBA layers."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/eli_elina_test01"
SRC = OUT / "source_chroma"
DST = OUT / "assets"
DST.mkdir(parents=True, exist_ok=True)
FILES = [
    ("elina_chair_concerned_source.png", "elina_chair_concerned.png"),
    ("elina_chair_neutral_source.png", "elina_chair_neutral.png"),
    ("eli_excited_source.png", "eli_excited.png"),
    ("eli_curious_source.png", "eli_curious.png"),
    ("eli_suspicious_source.png", "eli_suspicious.png"),
]


def smoothstep(lo, hi, x):
    t = np.clip((x - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def key(source: Path, target: Path):
    image = Image.open(source).convert("RGB")
    rgb = np.asarray(image, dtype=np.float32)
    h, w, _ = rgb.shape
    border = np.concatenate((rgb[:8].reshape(-1, 3), rgb[-8:].reshape(-1, 3), rgb[:, :8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)))
    matte_color = np.median(border, axis=0)
    distance = np.sqrt(np.sum((rgb - matte_color[None, None, :]) ** 2, axis=2))
    alpha = smoothstep(30.0, 112.0, distance)
    alpha = np.asarray(Image.fromarray(np.uint8(alpha * 255), "L").filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255
    out = rgb.copy()
    other = np.maximum(out[:, :, 0], out[:, :, 2])
    green_excess = np.maximum(0.0, out[:, :, 1] - other - 3.0)
    out[:, :, 1] -= green_excess * 0.97
    rgba = np.dstack([np.uint8(np.clip(out, 0, 255)), np.uint8(np.clip(alpha * 255, 0, 255))])
    Image.fromarray(rgba, "RGBA").resize((1080, 1920), Image.Resampling.LANCZOS).save(target, optimize=True)
    print(f"{source.name}: {w}x{h}; sampled key {matte_color.round().tolist()}; "
          f"opaque={(alpha > .98).mean():.3f}; transparent={(alpha < .02).mean():.3f}; -> {target.name}")


for source_name, target_name in FILES:
    key(SRC / source_name, DST / target_name)

room_src = OUT / "source_images/room_plate_source.png"
Image.open(room_src).convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS).save(DST / "room_plate.png", quality=95)
print("room_plate.png: upscaled to 1080x1920 with Lanczos")
