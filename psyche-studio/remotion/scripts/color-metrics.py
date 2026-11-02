#!/usr/bin/env python3
"""Simple, honest colour metrics for frames and videos.

Two things are measured:

  1. saturation / contrast of the whole frame  (is the image washed out?)
  2. contrast between the character region and the background region
     (does the character pop out of the room?)

Usage:
    python3 scripts/color-metrics.py IMAGE [IMAGE ...]
    python3 scripts/color-metrics.py --video FILE.mp4 --samples 6

Metrics (all on 0..255 sRGB):
    sat_mean   mean HSV saturation of the frame (0..1)
              -> "washed out" shows up here
    sat_p90    90th percentile saturation, i.e. how vivid the vivid parts are
    lum_std    standard deviation of luma (contrast / how flat the lighting is)
    lum_p05/p95  shadow and highlight endpoints (do we have clear darks?)
"""
import json
import subprocess
import sys

import numpy as np

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def rgb_to_hsv(rgb):
    """rgb: float array (..., 3) in 0..1 -> h, s, v"""
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    diff = mx - mn
    sat = np.where(mx > 0, diff / np.maximum(mx, 1e-6), 0.0)
    return sat, mx


def frame_metrics(arr):
    rgb = arr[..., :3].astype(np.float32) / 255.0
    sat, val = rgb_to_hsv(rgb)
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    return {
        "sat_mean": float(sat.mean()),
        "sat_p90": float(np.percentile(sat, 90)),
        "lum_std": float(luma.std() * 255),
        "lum_p05": float(np.percentile(luma, 5) * 255),
        "lum_p95": float(np.percentile(luma, 95) * 255),
        "lum_mean": float(luma.mean() * 255),
    }


def bg_metrics(arr, box):
    """saturation/contrast of a background region, given as (x0, y0, x1, y1) fractions"""
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = [int(round(v)) for v in (box[0] * w, box[1] * h, box[2] * w, box[3] * h)]
    return frame_metrics(arr[y0:y1, x0:x1])


def character_contrast(arr, char_box, bg_boxes):
    """How much the character's colours differ from the background's.

    Returns the mean CIE-ish colour distance between the character region and
    each background region, plus the luminance separation.
    """
    h, w = arr.shape[:2]

    def crop(box):
        x0, y0, x1, y1 = [int(round(v)) for v in (box[0] * w, box[1] * h, box[2] * w, box[3] * h)]
        return arr[y0:y1, x0:x1, :3].astype(np.float32)

    ch = crop(char_box)
    ch_mean = ch.reshape(-1, 3).mean(axis=0)
    ch_luma = 0.2126 * ch_mean[0] + 0.7152 * ch_mean[1] + 0.0722 * ch_mean[2]

    distances = []
    lumas = []
    for box in bg_boxes:
        bg = crop(box).reshape(-1, 3).mean(axis=0)
        distances.append(float(np.linalg.norm(ch_mean - bg)))
        bg_luma = 0.2126 * bg[0] + 0.7152 * bg[1] + 0.0722 * bg[2]
        lumas.append(float(ch_luma - bg_luma))
    return {
        "char_bg_color_distance": float(np.mean(distances)),
        "char_minus_bg_luma": float(np.mean(lumas)),
    }


def load_image(path):
    if Image is not None:
        return np.array(Image.open(path).convert("RGB"))
    raise SystemExit("Pillow is required: pip install pillow")


def video_frames(path, samples, ffmpeg="ffmpeg"):
    """Return `samples` evenly spaced frames as numpy arrays."""
    out = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "error", "-i", path, "-vf", "fps=1", "-f", "image2pipe",
         "-vcodec", "ppm", "-"],
        capture_output=True, check=True,
    ).stdout
    frames, pos = [], 0
    while True:
        if pos >= len(out):
            break
        # PPM header: P6\n<w> <h>\n255\n
        try:
            assert out[pos:pos + 2] == b"P6"
        except AssertionError:
            break
        nl1 = out.index(b"\n", pos)
        nl2 = out.index(b"\n", nl1 + 1)
        nl3 = out.index(b"\n", nl2 + 1)
        w, h = map(int, out[nl1 + 1:nl2].split())
        data = np.frombuffer(out[nl3 + 1:nl3 + 1 + w * h * 3], dtype=np.uint8)
        frames.append(data.reshape(h, w, 3))
        pos = nl3 + 1 + w * h * 3
    if not frames:
        return []
    step = max(1, len(frames) // samples)
    return frames[::step][:samples]


def main(argv):
    ffmpeg = "ffmpeg"
    samples = 5
    args = [a for a in argv[1:]]
    if "--video" in args:
        i = args.index("--video")
        path = args[i + 1]
        del args[i:i + 2]
        if "--samples" in args:
            j = args.index("--samples")
            samples = int(args[j + 1])
            del args[j:j + 2]
        frames = video_frames(path, samples, ffmpeg)
        if not frames:
            raise SystemExit(f"could not decode {path}")
        per = [frame_metrics(f) for f in frames]
        out = {k: float(np.mean([p[k] for p in per])) for k in per[0]}
        out["frames_sampled"] = len(per)
        print(json.dumps(out, indent=2))
        return 0

    for path in args:
        arr = load_image(path)
        print(json.dumps({"file": path, **frame_metrics(arr)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
