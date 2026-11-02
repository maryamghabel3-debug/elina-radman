#!/usr/bin/env python3
"""Geometry / framing QA for the V2 stills.

Verifies the two claims that are easy to fake by eye:
  * Eli is fully inside the 9:16 safe area (y 250–1500) and never touches a
    frame edge (no cropping);
  * Eli is the highest-contrast object in the frame.

Eli is found by colour: the character is the only strongly violet thing in the
scene (the room is coral in the warm variant, teal in the cool variant), so a
violet-hue mask isolates it without hand-drawn boxes.

Usage: python3 scripts/frame-check.py IMAGE [IMAGE ...]
"""
import json
import sys

import numpy as np
from PIL import Image

SAFE_TOP = 250
SAFE_BOTTOM = 1500
EDGE_MARGIN = 6  # px; Eli must not come closer than this to any edge


def hsv(arr):
    rgb = arr.astype(np.float32) / 255.0
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    diff = mx - mn
    sat = np.where(mx > 0, diff / np.maximum(mx, 1e-6), 0.0)
    val = mx
    # hue in degrees
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue = np.zeros_like(mx)
    nz = diff > 1e-6
    idx = (mx == r) & nz
    hue[idx] = (60 * (((g - b) / np.maximum(diff, 1e-6))[idx] % 6))
    idx = (mx == g) & nz
    hue[idx] = 60 * ((b - r) / np.maximum(diff, 1e-6) + 2)[idx]
    idx = (mx == b) & nz
    hue[idx] = 60 * ((r - g) / np.maximum(diff, 1e-6) + 4)[idx]
    return hue, sat, val


def eli_mask(arr):
    """violet / purple: hue 250–305 deg, reasonably saturated"""
    hue, sat, val = hsv(arr)
    return (hue >= 248) & (hue <= 310) & (sat > 0.22) & (val > 0.12)


def check(path):
    arr = np.array(Image.open(path).convert("RGB"))
    h, w = arr.shape[:2]
    mask = eli_mask(arr)
    pix = int(mask.sum())
    if pix < 500:
        return {"file": path, "error": "could not find a violet character mask"}

    ys, xs = np.where(mask)
    top, bottom = int(ys.min()), int(ys.max())
    left, right = int(xs.min()), int(xs.max())

    inside_safe = top >= SAFE_TOP and bottom <= SAFE_BOTTOM
    uncropped = left > EDGE_MARGIN and right < w - EDGE_MARGIN and top > EDGE_MARGIN and bottom < h - EDGE_MARGIN

    # contrast: mean saturation inside the mask vs outside it
    hue, sat, val = hsv(arr)
    luma = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    inside = mask
    outside = ~mask
    res = {
        "file": path,
        "character_pixels": pix,
        "bbox": {"top": top, "bottom": bottom, "left": left, "right": right},
        "height_pct": round(100 * (bottom - top) / h, 1),
        "width_pct": round(100 * (right - left) / w, 1),
        "inside_safe_area_250_1500": bool(inside_safe),
        "not_cropped_by_edges": bool(uncropped),
        "char_saturation": round(float(sat[inside].mean()), 3),
        "bg_saturation": round(float(sat[outside].mean()), 3),
        "char_luma": round(float(luma[inside].mean()), 1),
        "bg_luma": round(float(luma[outside].mean()), 1),
        "char_contrast_ratio": round(float((luma[inside].mean() + 5) / (luma[outside].mean() + 5)), 2),
        "frame_saturation_mean": round(float(sat.mean()), 3),
        "frame_luma_std": round(float(luma.std()), 1),
        "frame_luma_p05": round(float(np.percentile(luma, 5)), 1),
    }
    return res


def main(argv):
    out = [check(p) for p in argv[1:]]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
