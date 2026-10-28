"""Procedural monoline icon set with self-drawing stroke reveal.

Icons are defined as normalized (0..100) stroke operations, so a single
definition renders at any size/color/width. A ``progress`` value in 0..1
reveals the operations one after another, with polylines partially drawn
by arc length - the self-drawing grammar used by the reference video.
No external icon assets or frameworks are required.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw

from . import keyframes as kf

Point = Tuple[float, float]
Op = Tuple[str, tuple]


def _rr_path(x0: float, y0: float, x1: float, y1: float,
             r: float, n: int = 6) -> List[Point]:
    """Dense point path around a rounded rectangle (perimeter polyline)."""
    corners = [
        (x1 - r, y0 + r, 270, 360),
        (x1 - r, y1 - r, 0, 90),
        (x0 + r, y1 - r, 90, 180),
        (x0 + r, y0 + r, 180, 270),
    ]
    pts: List[Point] = [(x1 - r, y0)]
    for cx, cy, a0, a1 in corners:
        for k in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append((x1 - r, y0))
    return pts


# Each op: ("poly", points, closed_hint) | ("arc", (cx,cy,r,a0,a1)) |
#          ("dot", (cx,cy,r))
def _icon_ops(name: str) -> List[Op]:
    if name == "phone":
        return [("poly", _rr_path(28, 6, 72, 94, 10), False),
                ("poly", [(44, 14), (56, 14)], False),
                ("dot", (50, 86, 2.4))]
    if name == "chat_bubble":
        return [("poly", _rr_path(10, 14, 90, 66, 12), False),
                ("poly", [(34, 66), (30, 84), (50, 66)], False),
                ("dot", (34, 40, 3.2)), ("dot", (50, 40, 3.2)),
                ("dot", (66, 40, 3.2))]
    if name == "head":
        return [("arc", (50, 42, 26, 200, 520)),
                ("poly", [(30, 88), (30, 80)], False),
                ("poly", [(70, 88), (70, 80)], False),
                ("arc", (50, 96, 26, 20, 160))]
    if name == "person":
        return [("arc", (50, 32, 16, 0, 360)),
                ("arc", (50, 92, 28, 200, 340))]
    if name == "magnifier":
        return [("arc", (42, 42, 26, 0, 360)),
                ("poly", [(61, 61), (82, 82)], False)]
    if name == "question":
        return [("arc", (50, 36, 20, 270, 630)),
                ("poly", [(50, 58), (50, 70)], False),
                ("dot", (50, 82, 3.0))]
    if name == "folder":
        return [("poly", [(8, 26), (8, 80), (92, 80), (92, 26), (44, 26),
                          (36, 16), (8, 16)], True)]
    if name == "documents":
        ops = [("poly", _rr_path(24, 20, 84, 88, 6), False)]
        for yy in (34, 48, 62):
            ops.append(("poly", [(34, yy), (74, yy)], False))
        ops += [("poly", _rr_path(16, 14, 76, 82, 6), False),
                ("poly", _rr_path(8, 8, 68, 76, 6), False)]
        return ops
    if name == "toggle":
        return [("poly", _rr_path(8, 32, 92, 68, 18), False),
                ("arc", (66, 50, 12, 0, 360))]
    if name == "arrow":
        return [("poly", [(14, 50), (84, 50)], False),
                ("poly", [(62, 30), (84, 50), (62, 70)], False)]
    if name == "check":
        return [("poly", [(18, 52), (42, 74), (84, 26)], False)]
    if name == "cross":
        return [("poly", [(26, 26), (74, 74)], False),
                ("poly", [(74, 26), (26, 74)], False)]
    if name == "spark":
        return [("poly", [(50, 8), (50, 92)], False),
                ("poly", [(8, 50), (92, 50)], False),
                ("poly", [(22, 22), (78, 78)], False),
                ("poly", [(78, 22), (22, 78)], False)]
    raise KeyError(f"unknown icon {name!r}")


ICON_NAMES = ["phone", "chat_bubble", "head", "person", "magnifier",
              "question", "folder", "documents", "toggle", "arrow",
              "check", "cross", "spark"]


def _partial_poly(draw: ImageDraw.ImageDraw, pts: List[Point], frac: float,
                  color, width: int) -> None:
    if frac <= 0 or len(pts) < 2:
        return
    seg_len = [0.0]
    for a, b in zip(pts, pts[1:]):
        seg_len.append(seg_len[-1] + math.dist(a, b))
    total = seg_len[-1] or 1.0
    cut = total * kf.clamp01(frac)
    out = [pts[0]]
    for i in range(1, len(pts)):
        if seg_len[i] <= cut:
            out.append(pts[i])
        else:
            span = seg_len[i] - seg_len[i - 1] or 1e-9
            k = (cut - seg_len[i - 1]) / span
            out.append((pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * k,
                        pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * k))
            break
    if len(out) >= 2:
        draw.line(out, fill=color, width=width, joint="curve")


def draw_icon(frame: Image.Image, name: str, cx: float, cy: float,
              size: float, color, progress: float = 1.0,
              stroke_width: float = 5.0) -> None:
    """Draw ``name`` centred at (cx, cy) fitting a ``size`` box."""
    if progress <= 0:
        return
    ops = _icon_ops(name)
    scale = size / 100.0
    width = max(2, int(stroke_width * scale * 1.6))
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    def px(x: float, y: float) -> Point:
        return (cx + (x - 50) * scale, cy + (y - 50) * scale)

    n = len(ops)
    for i, op in enumerate(ops):
        slot = kf.clamp01(progress * n - i)
        if slot <= 0:
            continue
        kind = op[0]
        if kind == "poly":
            pts = [px(x, y) for x, y in op[1]]
            _partial_poly(draw, pts, slot, (*color, 255), width)
        elif kind == "arc":
            ax, ay, r, a0, a1 = op[1]
            ccx, ccy = px(ax, ay)
            rr = r * scale
            draw.arc([ccx - rr, ccy - rr, ccx + rr, ccy + rr],
                     a0, a0 + (a1 - a0) * slot, fill=(*color, 255), width=width)
        else:
            dx, dy, r = op[1]
            ccx, ccy = px(dx, dy)
            rr = r * scale * min(1.0, slot * 1.4)
            draw.ellipse([ccx - rr, ccy - rr, ccx + rr, ccy + rr],
                         fill=(*color, 255))
    frame.alpha_composite(layer)


def dotted_leader(frame: Image.Image, p0: Point, p1: Point, color,
                  width: int = 3, dash: float = 10.0,
                  gap: float = 8.0, progress: float = 1.0) -> None:
    """Dotted leader line between two points, drawn to ``progress`` length."""
    total = math.dist(p0, p1)
    if total <= 0 or progress <= 0:
        return
    draw = ImageDraw.Draw(frame)
    ux, uy = (p1[0] - p0[0]) / total, (p1[1] - p0[1]) / total
    traveled = 0.0
    draw_to = total * kf.clamp01(progress)
    while traveled < draw_to:
        end = min(traveled + dash, draw_to)
        draw.line([(p0[0] + ux * traveled, p0[1] + uy * traveled),
                   (p0[0] + ux * end, p0[1] + uy * end)],
                  fill=(*color, 230), width=width)
        traveled += dash + gap


def rounded_chip(frame: Image.Image, cx: float, cy: float, w: float,
                 h: float, fill, outline=None, radius: float = 26,
                 alpha: int = 235, width: int = 2) -> tuple:
    """Rounded-rectangle chip; returns its pixel bounding box."""
    box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=radius,
                        fill=(*fill, alpha),
                        outline=(*outline, 255) if outline else None,
                        width=width if outline else 1)
    frame.alpha_composite(layer)
    return tuple(int(v) for v in box)
