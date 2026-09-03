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


# === M25 — 3x3 grid, merged regions, debug helpers ===

from agents.carousel.text_zone import (
    ZONES_3x3,
    band_scores,
    cell_scores,
    zone_luminance,
    zone_scores,
)


def test_grid_picks_corner_for_centered_character():
    # A cross-shaped character through the center: no full row/column is
    # calm, so a corner cell wins (deterministic tie-break: bottom_right).
    img = make_image(noise_rects=[(W // 2 - 60, 0, W // 2 + 60, H),
                                  (0, H // 2 - 60, W, H // 2 + 60)])
    zone = find_best_text_zone(img, mode="grid")
    assert zone in ("top_left", "top_right", "bottom_left", "bottom_right")
    assert zone == "bottom_right"


def test_grid_picks_band_when_full_row_calm():
    # A busy bar through the MIDDLE row only: top and bottom rows are fully
    # calm -> a calm row is returned (bottom wins the tie-break).
    img = make_image(noise_rects=[(0, H // 2 - 80, W, H // 2 + 80)])
    assert find_best_text_zone(img, mode="grid") == "bottom"


def test_grid_picks_side_when_column_calm():
    # A busy bar through the middle COLUMN: left and right columns are
    # fully calm -> a side column is returned (left wins the tie-break).
    img = make_image(noise_rects=[(W // 2 - 80, 0, W // 2 + 80, H)])
    assert find_best_text_zone(img, mode="grid") in ("left", "right")
    assert find_best_text_zone(img, mode="grid") == "left"


def test_bands_mode_unchanged_legacy():
    # mode="bands" keeps the exact M23 3-band behavior
    assert find_best_text_zone(make_image(noise_rects=[(0, 700, W, H)]),
                               mode="bands") == "top"
    assert find_best_text_zone(make_image(fill=(40, 70, 110)),
                               mode="bands") == "bottom"
    assert find_best_text_zone(make_image(noise_rects=[(0, 0, W, 300)]),
                               mode="bands") == "bottom"
    with pytest.raises(ValueError):
        find_best_text_zone(make_image(), mode="diag")


def test_zone_scores_returns_all_regions():
    img = make_image(noise_rects=[(0, 0, W, 300)])
    s = zone_scores(img)
    assert set(s) == set(ZONES_3x3) | {"top", "middle", "bottom", "left", "right"}
    # Row/column scores = worst cell of the region
    assert s["top"] == max(s["top_left"], s["top_center"], s["top_right"])
    assert s["left"] == max(s["top_left"], s["middle_left"], s["bottom_left"])
    # The full-width noise hits both top-row cells; the bottom-right cell
    # stays perfectly flat
    assert s["top_left"] > 0.0
    assert s["top_right"] > 0.0
    assert cell_scores(img)["bottom_right"] == 0.0
    # band_scores (legacy 30/40/30) is a separate, stable statistic
    bands = band_scores(img)
    assert bands["top"] > bands["bottom"]


def test_zone_is_acceptable_region_generic():
    flat = make_image(fill=(90, 90, 90))
    assert zone_is_acceptable(flat, "bottom_left") is True
    assert zone_is_acceptable(flat, "right") is True
    noisy_bottom = make_image(noise_rects=[(0, 700, W, H)])
    assert zone_is_acceptable(noisy_bottom, "bottom") is False
    assert zone_is_acceptable(noisy_bottom, "bottom_right") is False
    assert zone_is_acceptable(noisy_bottom, "top") is True
    assert zone_is_acceptable(noisy_bottom, "right") is False  # bottom_right noisy
    with pytest.raises(ValueError):
        zone_is_acceptable(flat, "sideways")


def test_zone_luminance_dark_and_bright():
    dark = make_image(fill=(20, 30, 60))
    light = make_image(fill=(220, 220, 220))
    assert zone_luminance(dark, "bottom") < 128
    assert zone_luminance(light, "top_right") >= 128
