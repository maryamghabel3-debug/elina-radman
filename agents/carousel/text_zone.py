"""
Smart text-zone detection for full-bleed carousel slides (M23, extended M25).

Chooses where caption text should sit on a full-bleed slide so it avoids
the busiest part of the photo (e.g. a character standing at the bottom
of the frame).

Pillow + numpy only (both already in requirements) — no new
dependencies, fully deterministic.

M23 (bands, legacy): the image is split into three horizontal bands —
top 30%, middle 40%, bottom 30%. Each band gets a "busyness" score:

    busyness = normalized edge_density + normalized luminance_variance

where edge_density is the mean of the PIL FIND_EDGES result and
luminance_variance is the variance of the grayscale values, each
normalized to roughly [0, 1] before summing.

M25 (grid, default): a 3x3 grid of cells. The least-busy cell wins;
"merged" regions are also candidates when a whole row/column is calm
(all three cells below the acceptable threshold) — a calm row returns
the band (top/middle/bottom), a calm column returns left/right. Corners
are usually emptier than full bands, which the legacy 3-band algorithm
could never express (it returned "top" for every portrait photo whose
character occupied the center/bottom).

The edge statistic uses a 2px inset: PIL's FIND_EDGES zero-pads the
image border, which creates artificial "edges" along the frame of even
a perfectly flat image (and would break the tie-break on uniform
photos). Insetting removes those border artifacts; real content near
the frame is still counted.
"""

import numpy as np
from PIL import Image, ImageFilter, ImageStat

ZONE_TOP = "top"
ZONE_MIDDLE = "middle"
ZONE_BOTTOM = "bottom"

# The 3x3 grid cells (M25)
ZONES_3x3 = (
    "top_left", "top_center", "top_right",
    "middle_left", "middle_center", "middle_right",
    "bottom_left", "bottom_center", "bottom_right",
)
# Everything the detector can return (9 cells + 3 rows + 2 columns)
ALL_TEXT_ZONES = ZONES_3x3 + ("top", "middle", "bottom", "left", "right")
# Values accepted on slides by the schema: "auto" + the 10 addressable
# zones. (middle_center is detector-internal only.)
SUPPORTED_TEXT_ZONES = (
    "auto",
    "top", "middle", "bottom", "left", "right",
    "top_left", "top_right", "bottom_left", "bottom_right",
    "middle_left", "middle_right",
)

# Grid tie-breaking preference (M25): calm merged rows/columns are
# preferred over cells of equal busyness (a wider block reads better);
# among cells: bottom_center > top_center > bottom_right > bottom_left
# > top_right > top_left > middle_*.
ZONE_GRID_PRIORITY = {
    "bottom": 0, "top": 1, "middle": 2,
    "left": 3, "right": 4,
    "bottom_center": 5, "top_center": 6, "bottom_right": 7, "bottom_left": 8,
    "top_right": 9, "top_left": 10,
    "middle_center": 11, "middle_right": 12, "middle_left": 13,
}

# Legacy 3-band tie-break (mode="bands"): bottom > top > middle
_BAND_PRIORITY = {ZONE_BOTTOM: 0, ZONE_TOP: 1, ZONE_MIDDLE: 2}

# Region geometry as fractions (rows/columns of the 3x3 grid)
_ROW_FRACS = {"top": (0.0, 1 / 3), "middle": (1 / 3, 2 / 3), "bottom": (2 / 3, 1.0)}
# Column names in cell identifiers use "center" (top_center, ...)
_COL_FRACS = {"left": (0.0, 1 / 3), "center": (1 / 3, 2 / 3), "right": (2 / 3, 1.0)}
_ROW_CELLS = {
    "top": ("top_left", "top_center", "top_right"),
    "middle": ("middle_left", "middle_center", "middle_right"),
    "bottom": ("bottom_left", "bottom_center", "bottom_right"),
}
_COL_CELLS = {
    "left": ("top_left", "middle_left", "bottom_left"),
    "right": ("top_right", "middle_right", "bottom_right"),
}

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


def _downscaled_edges(image: Image.Image):
    """Grayscale + downscale to ~200px wide, plus the FIND_EDGES result."""
    if not isinstance(image, Image.Image):
        raise TypeError("expected a PIL Image")
    gray = image.convert("L")
    w, h = gray.size
    scale = _DOWNSCALE_WIDTH / max(1, w)
    small_w = max(1, round(w * scale))
    small_h = max(1, round(h * scale))
    small = gray.resize((small_w, small_h), Image.LANCZOS)
    edges = small.filter(ImageFilter.FIND_EDGES)
    return small, edges, small_w, small_h


def _region_busyness(small, edges, small_w, small_h, box) -> float:
    """Busyness of a (x0, y0, x1, y1) box on the downscaled image."""
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:  # degenerate region: treat as flat
        return 0.0
    region = np.asarray(small.crop((x0, y0, x1, y1)), dtype=np.float64)
    # Edge density on a 2px-inset region where the box touches the image
    # frame (border-artifact fix, see module docstring).
    ex0 = x0 + 2 if (x0 == 0 and x1 - x0 > 4) else x0
    ex1 = x1 - 2 if (x1 == small_w and x1 - x0 > 4) else x1
    ey0 = y0 + 2 if (y0 == 0 and y1 - y0 > 4) else y0
    ey1 = y1 - 2 if (y1 == small_h and y1 - y0 > 4) else y1
    edge_crop = edges.crop((ex0, ey0, ex1, ey1))
    if edge_crop.size[0] <= 1 or edge_crop.size[1] <= 1:
        edge_density = 0.0
    else:
        edge_density = float(np.asarray(edge_crop, dtype=np.float64).mean()) / 255.0
    luminance_variance = float(region.var()) / _MAX_VARIANCE
    return edge_density + luminance_variance


def _cell_box(w: int, h: int, cell: str):
    row, col = cell.split("_", 1)
    rlo, rhi = _ROW_FRACS[row]
    clo, chi = _COL_FRACS[col]
    y0 = int(round(h * rlo))
    y1 = int(round(h * rhi))
    x0 = int(round(w * clo))
    x1 = int(round(w * chi))
    return (x0, y0, x1, y1)


def band_scores(image: Image.Image) -> dict:
    """Return {zone: busyness} for the three legacy horizontal bands
    (top 30% / middle 40% / bottom 30%)."""
    small, edges, w, h = _downscaled_edges(image)
    bands = (("top", 0.0, 0.30), ("middle", 0.30, 0.70), ("bottom", 0.70, 1.0))
    scores = {}
    for zone, lo, hi in bands:
        y0 = int(round(h * lo))
        y1 = int(round(h * hi))
        scores[zone] = _region_busyness(small, edges, w, h, (0, y0, w, y1))
    return scores


def cell_scores(image: Image.Image) -> dict:
    """Return {cell: busyness} for the 3x3 grid (M25)."""
    small, edges, w, h = _downscaled_edges(image)
    return {cell: _region_busyness(small, edges, w, h, _cell_box(w, h, cell))
            for cell in ZONES_3x3}


def zone_scores(image: Image.Image) -> dict:
    """Debug helper (M25): per-region busyness for every addressable
    region — the 9 grid cells, the 3 rows (worst cell of the row) and
    the 2 side columns (worst cell of the column).

    For the legacy 3-band scores (full-width 30/40/30 bands) use
    band_scores().
    """
    cells = cell_scores(image)
    scores = dict(cells)
    for row, cells_row in _ROW_CELLS.items():
        scores[row] = max(cells[c] for c in cells_row)
    for col, cells_col in _COL_CELLS.items():
        scores[col] = max(cells[c] for c in cells_col)
    return scores


def find_best_text_zone(image: Image.Image, mode: str = "grid") -> str:
    """Return the zone where caption text sits least on top of detail.

    mode="grid" (default, M25): the least-busy grid cell, unless a whole
    row/column is calm (all three cells below the acceptable
    threshold) — then the merged region is a candidate and wins on the
    tie-break preference (rows: bottom > top > middle; columns:
    left > right; merged regions beat cells of equal busyness).

    mode="bands" (legacy M23): the least-busy of the three full-width
    bands, ties break bottom > top > middle.
    """
    if mode == "bands":
        scores = band_scores(image)
        return min(scores, key=lambda z: (scores[z], _BAND_PRIORITY[z]))
    if mode != "grid":
        raise ValueError(f"unknown zone mode '{mode}' (use 'bands' or 'grid')")

    cells = cell_scores(image)
    candidates = dict(cells)
    for row, cells_row in _ROW_CELLS.items():
        row_scores = [cells[c] for c in cells_row]
        if all(s < DEFAULT_ZONE_ACCEPTABLE_THRESHOLD for s in row_scores):
            candidates[row] = max(row_scores)
    for col, cells_col in _COL_CELLS.items():
        col_scores = [cells[c] for c in cells_col]
        if all(s < DEFAULT_ZONE_ACCEPTABLE_THRESHOLD for s in col_scores):
            candidates[col] = max(col_scores)
    return min(candidates, key=lambda z: (candidates[z], ZONE_GRID_PRIORITY[z]))


def zone_is_acceptable(image: Image.Image, zone: str,
                       threshold: float = DEFAULT_ZONE_ACCEPTABLE_THRESHOLD) -> bool:
    """True if `zone`'s busyness is below `threshold`, i.e. text should be
    readable there without a heavy gradient.

    Region-generic (M25): `zone` may be any of the 9 grid cells, a row
    (top/middle/bottom) or a column (left/right); merged regions use the
    worst cell of the region.
    """
    if zone in ZONES_3x3:
        return cell_scores(image)[zone] < threshold
    if zone in _ROW_CELLS:
        cells = cell_scores(image)
        return all(cells[c] < threshold for c in _ROW_CELLS[zone])
    if zone in _COL_CELLS:
        cells = cell_scores(image)
        return all(cells[c] < threshold for c in _COL_CELLS[zone])
    raise ValueError(
        f"unknown text zone '{zone}' (use one of {list(ALL_TEXT_ZONES)})"
    )


def zone_luminance(image: Image.Image, zone: str) -> float:
    """Mean luminance (0-255) of a zone region on `image` (M25 blend
    mode: picks the text color). Region-generic like zone_is_acceptable."""
    w, h = image.size
    if zone in ZONES_3x3:
        x0, y0, x1, y1 = _cell_box(w, h, zone)
    elif zone in _ROW_CELLS:
        rlo, rhi = _ROW_FRACS[zone]
        x0, x1 = 0, w
        y0, y1 = int(h * rlo), int(h * rhi)
    else:  # column
        clo, chi = _COL_FRACS[zone]
        x0, x1 = int(w * clo), int(w * chi)
        y0, y1 = 0, h
    x1 = max(x0 + 1, min(w, x1))
    y1 = max(y0 + 1, min(h, y1))
    region = image.crop((x0, y0, x1, y1)).convert("L").resize((32, 32))
    return float(ImageStat.Stat(region).mean[0])
