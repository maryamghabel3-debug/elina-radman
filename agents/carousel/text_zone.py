"""
Smart text-zone detection for full-bleed carousel slides (M23).

Chooses where the caption text + gradient should sit on a full-bleed
slide so they avoid the busiest part of the photo (e.g. a character
standing at the bottom of the frame).

Pillow + numpy only (both already in requirements) — no new
dependencies, fully deterministic.

Bands: the image is split into three horizontal bands — top 30%,
middle 40%, bottom 30%. Each band gets a "busyness" score:

    busyness = normalized edge_density + normalized luminance_variance

where edge_density is the mean of the PIL FIND_EDGES result and
luminance_variance is the variance of the grayscale values, each
normalized to roughly [0, 1] before summing.
"""

import numpy as np
from PIL import Image, ImageFilter

ZONE_TOP = "top"
ZONE_MIDDLE = "middle"
ZONE_BOTTOM = "bottom"
SUPPORTED_TEXT_ZONES = (ZONE_BOTTOM, ZONE_TOP, ZONE_MIDDLE)

# Tie-breaking preference order: bottom is most natural for captions,
# top is a good fallback, middle is the last resort.
_ZONE_PRIORITY = {ZONE_BOTTOM: 0, ZONE_TOP: 1, ZONE_MIDDLE: 2}

# Band boundaries as fractions of the (downscaled) image height.
_BANDS = (
    (ZONE_TOP, 0.0, 0.30),
    (ZONE_MIDDLE, 0.30, 0.70),
    (ZONE_BOTTOM, 0.70, 1.0),
)

# Downscale target width for speed (aspect preserved).
_DOWNSCALE_WIDTH = 200

# Max possible variance of 8-bit values (half 0, half 255) — used to
# normalize luminance_variance into roughly [0, 1].
_MAX_VARIANCE = (255.0 ** 2) / 4.0

# Default for zone_is_acceptable: below this busyness, text is expected
# to stay readable without a heavy gradient. (Measured reference points:
# a flat region scores 0.0, pure high-frequency noise ~0.15, so 0.10
# accepts only genuinely quiet zones.)
DEFAULT_ZONE_ACCEPTABLE_THRESHOLD = 0.10


def band_scores(image: Image.Image) -> dict:
    """Return {zone: busyness} for the three horizontal bands of `image`.

    Deterministic: grayscale -> downscale to ~200px wide -> per-band
    normalized edge density + normalized luminance variance.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("band_scores expects a PIL Image")

    gray = image.convert("L")
    w, h = gray.size
    scale = _DOWNSCALE_WIDTH / max(1, w)
    small_w = max(1, round(w * scale))
    small_h = max(1, round(h * scale))
    small = gray.resize((small_w, small_h), Image.LANCZOS)
    edges = small.filter(ImageFilter.FIND_EDGES)

    scores: dict = {}
    for zone, lo, hi in _BANDS:
        y0 = int(round(small_h * lo))
        y1 = int(round(small_h * hi))
        if y1 <= y0:  # degenerate (tiny) image: treat as flat
            scores[zone] = 0.0
            continue
        band = np.asarray(small.crop((0, y0, small_w, y1)), dtype=np.float64)
        # Edge density on a 2px-inset region: PIL's FIND_EDGES zero-pads the
        # image border, which creates artificial "edges" along the frame of
        # even a perfectly flat image (and would break the bottom/top/middle
        # tie-break on uniform photos). Insetting the edge band removes
        # those border artifacts; real content near the frame is still
        # counted.
        ex0 = 2 if small_w > 4 else 0
        ex1 = small_w - 2 if small_w > 4 else small_w
        ey0 = y0 + 2 if (y0 == 0 and y1 - y0 > 4) else y0
        ey1 = y1 - 2 if (y1 == small_h and y1 - y0 > 4) else y1
        edge_crop = edges.crop((ex0, ey0, ex1, ey1))
        if edge_crop.size[0] <= 1 or edge_crop.size[1] <= 1:
            edge_density = 0.0
        else:
            edge_band = np.asarray(edge_crop, dtype=np.float64)
            edge_density = float(edge_band.mean()) / 255.0
        luminance_variance = float(band.var()) / _MAX_VARIANCE
        scores[zone] = edge_density + luminance_variance
    return scores


def find_best_text_zone(image: Image.Image) -> str:
    """Return the band where caption text sits least on top of detail.

    One of "bottom" | "top" | "middle": the band with the LOWEST
    busyness score; ties break with bottom > top > middle.
    """
    scores = band_scores(image)
    return min(scores, key=lambda zone: (scores[zone], _ZONE_PRIORITY[zone]))


def zone_is_acceptable(image: Image.Image, zone: str,
                       threshold: float = DEFAULT_ZONE_ACCEPTABLE_THRESHOLD) -> bool:
    """True if `zone`'s busyness is below `threshold`, i.e. text should be
    readable there without a heavy gradient."""
    if zone not in _ZONE_PRIORITY:
        raise ValueError(
            f"unknown text zone '{zone}' (use one of {list(SUPPORTED_TEXT_ZONES)})"
        )
    return band_scores(image)[zone] < threshold
