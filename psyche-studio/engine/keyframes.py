"""Keyframes, easing curves and motion paths for the V2 motion engine.

Pure math + small interpolation helpers - no rendering here, so the modules
stay cheap to call per frame. All time inputs are seconds; progress values
are clamped to 0..1.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------
# Clamping / mapping
# --------------------------------------------------------------------------
def clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else 1.0 if x >= 1.0 else float(x)


def map_range(x: float, a: float, b: float, c: float, d: float) -> float:
    if b == a:
        return c
    return c + (d - c) * (x - a) / (b - a)


def progress(t: float, start: float, duration: float) -> float:
    """0..1 progress of a window beginning at ``start``."""
    if duration <= 0:
        return 1.0 if t >= start else 0.0
    return clamp01((t - start) / duration)


# --------------------------------------------------------------------------
# Easing curves
# --------------------------------------------------------------------------
def linear(x: float) -> float:
    return clamp01(x)


def ease_out_cubic(x: float) -> float:
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 3


def ease_in_cubic(x: float) -> float:
    x = clamp01(x)
    return x ** 3


def ease_in_out_cubic(x: float) -> float:
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1.0 - (-2 * x + 2) ** 3 / 2


def ease_out_quad(x: float) -> float:
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 2


def ease_out_back(x: float, overshoot: float = 1.70158) -> float:
    x = clamp01(x)
    c1 = overshoot
    c3 = c1 + 1.0
    return 1.0 + c3 * (x - 1.0) ** 3 + c1 * (x - 1.0) ** 2


def spring(x: float, damping: float = 9.0) -> float:
    """Damped spring that settles on 1.0 with a slight overshoot."""
    x = clamp01(x)
    if x >= 1.0:
        return 1.0
    return 1.0 - math.exp(-damping * x) * math.cos(damping * 0.65 * x)


EASINGS = {
    "linear": linear,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_cubic": ease_in_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
    "ease_out_quad": ease_out_quad,
    "ease_out_back": ease_out_back,
    "spring": spring,
}


def ease(name: str, x: float) -> float:
    return EASINGS.get(name, ease_out_cubic)(x)


# --------------------------------------------------------------------------
# Scalar keyframe track
# --------------------------------------------------------------------------
class KeyframeTrack:
    """Piecewise scalar track.

    times must be ascending; each segment may declare its own easing name.
    Values outside the track range clamp to the first/last keyframe.
    """

    def __init__(self, times: Sequence[float], values: Sequence[float],
                 easings: Optional[Sequence[str]] = None):
        if len(times) != len(values) or not times:
            raise ValueError("times/values length mismatch or empty")
        self.times = list(times)
        self.values = list(values)
        self.easings = list(easings) if easings else ["ease_out_cubic"] * (
            len(times) - 1)

    def value(self, t: float) -> float:
        if t <= self.times[0]:
            return self.values[0]
        if t >= self.times[-1]:
            return self.values[-1]
        for i in range(len(self.times) - 1):
            t0, t1 = self.times[i], self.times[i + 1]
            if t0 <= t <= t1:
                p = progress(t, t0, t1 - t0)
                return self.values[i] + (
                    self.values[i + 1] - self.values[i]
                ) * ease(self.easings[i], p)
        return self.values[-1]


def fade_window(t: float, start: float, in_dur: float = 0.35,
                exit_start: Optional[float] = None,
                exit_dur: float = 0.3) -> float:
    """Alpha 0..1 with a fade-in and optional fade-out."""
    alpha = ease_out_cubic(progress(t, start, in_dur))
    if exit_start is not None and t >= exit_start:
        alpha *= 1.0 - ease_in_cubic(progress(t, exit_start, exit_dur))
    return clamp01(alpha)


# --------------------------------------------------------------------------
# Motion paths (Catmull-Rom spline through control points)
# --------------------------------------------------------------------------
class MotionPath:
    def __init__(self, points: Sequence[Tuple[float, float]]):
        self.points = [tuple(p) for p in points]

    @staticmethod
    def _catmull_rom(p0, p1, p2, p3, u: float) -> Tuple[float, float]:
        u2, u3 = u * u, u * u * u
        out = []
        for axis in (0, 1):
            v = 0.5 * (
                2 * p1[axis]
                + (-p0[axis] + p2[axis]) * u
                + (2 * p0[axis] - 5 * p1[axis] + 4 * p2[axis] - p3[axis]) * u2
                + (-p0[axis] + 3 * p1[axis] - 3 * p2[axis] + p3[axis]) * u3
            )
            out.append(v)
        return out[0], out[1]

    def point(self, p: float) -> Tuple[float, float]:
        p = clamp01(p)
        pts = self.points
        if len(pts) == 1:
            return pts[0]
        if len(pts) == 2:
            return (pts[0][0] + (pts[1][0] - pts[0][0]) * p,
                    pts[0][1] + (pts[1][1] - pts[0][1]) * p)
        segments = len(pts) - 1
        pos = p * segments
        i = min(int(pos), segments - 1)
        u = pos - i
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[min(segments, i + 1)]
        p3 = pts[min(segments, i + 2)]
        return self._catmull_rom(p0, p1, p2, p3, u)


def breathe(t: float, speed: float = 1.6, amount: float = 1.0,
            phase: float = 0.0) -> float:
    """Continuous -1..1 sinusoidal idle motion (never settles to zero)."""
    return amount * math.sin(t * speed + phase)
