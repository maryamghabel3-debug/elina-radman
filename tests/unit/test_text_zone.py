"""
Unit tests for smart text-zone detection (M23).

Synthetic test images are built with PIL (solid regions + noise regions) —
no binary fixtures are committed.
"""

import numpy as np
from PIL import Image

import pytest

from agents.carousel.text_zone import (
    DEFAULT_ZONE_ACCEPTABLE_THRESHOLD,
    find_best_text_zone,
    zone_is_acceptable,
)

pytestmark = pytest.mark.unit

W, H = 800, 1000  # 4:5-ish canvas for the synthetic sources
SEED = 7


def make_image(size=(W, H), fill=(128, 128, 128), noise_rects=(), seed=SEED):
    """Solid base color + optional uniform-noise rectangles (x0, y0, x1, y1)."""
    w, h = size
    arr = np.full((h, w, 3), fill, dtype=np.uint8)
    rng = np.random.default_rng(seed)
    for (x0, y0, x1, y1) in noise_rects:
        arr[y0:y1, x0:x1] = rng.integers(
            0, 256, size=(y1 - y0, x1 - x0, 3), dtype=np.uint8
        )
    return Image.fromarray(arr)


# === A. busy bottom + flat top -> "top" ===

def test_A_busy_bottom_flat_top_selects_top():
    # Noise in the bottom 30% band, everything else flat
    img = make_image(noise_rects=[(0, 700, W, H)])
    assert find_best_text_zone(img) == "top"


# === B. flat bottom -> "bottom" ===

def test_B_flat_bottom_selects_bottom():
    # Noise in the top band only; bottom is flat and wins the tie-break
    img = make_image(noise_rects=[(0, 0, W, 300)])
    assert find_best_text_zone(img) == "bottom"


# === C. uniform flat image -> "bottom" (tie-break preference) ===

def test_C_uniform_flat_selects_bottom_by_preference():
    img = make_image(fill=(40, 70, 110))
    # All three bands must score exactly 0.0 on a uniform image (no border
    # artifacts leaking into the edge statistic)
    from agents.carousel.text_zone import band_scores
    assert band_scores(img) == {"top": 0.0, "middle": 0.0, "bottom": 0.0}
    assert find_best_text_zone(img) == "bottom"


# === D. detail everywhere except the middle -> "middle" ===

def test_D_detail_everywhere_except_middle_selects_middle():
    # Noise in the top and bottom bands; the middle band stays flat
    img = make_image(noise_rects=[(0, 0, W, 250), (0, 750, W, H)])
    assert find_best_text_zone(img) == "middle"


# === E. zone_is_acceptable: flat zone passes, noisy zone fails ===

def test_E_zone_is_acceptable_flat_passes_noisy_fails():
    flat = make_image(fill=(90, 90, 90))
    assert zone_is_acceptable(flat, "bottom") is True
    assert zone_is_acceptable(flat, "top") is True

    noisy = make_image(noise_rects=[(0, 0, W, H)])
    assert zone_is_acceptable(noisy, "bottom") is False
    assert zone_is_acceptable(noisy, "top") is False
    assert zone_is_acceptable(noisy, "middle") is False

    # The threshold is configurable: a very high one accepts even noise
    assert zone_is_acceptable(noisy, "bottom", threshold=10.0) is True

    # A zone with only mild detail sits in between (deterministic image)
    mild = make_image(noise_rects=[(0, 700, W, H)])  # bottom band noisy
    assert zone_is_acceptable(mild, "top") is True
    assert zone_is_acceptable(mild, "bottom") is False


# === determinism + invalid input ===

def test_F_detection_is_deterministic():
    img = make_image(noise_rects=[(0, 0, W, 300), (0, 750, W, H)])
    assert find_best_text_zone(img) == find_best_text_zone(img)


def test_G_invalid_zone_rejected():
    flat = make_image()
    with pytest.raises(ValueError):
        zone_is_acceptable(flat, "sideways")
    # The default threshold is a sane absolute value in (0, 1)
    assert 0.0 < DEFAULT_ZONE_ACCEPTABLE_THRESHOLD < 1.0
