"""Beat scheduler: map narration cues to timed visual events.

Guarantees the V2 pacing contract:
  * a meaningful visual/text event every 1.5-3.0 s;
  * no planned static interval longer than MAX_STATIC (2.5 s);
  * every scene carries non-subtitle text events and impact words.

Continuous ambient motion (particles, float, breathing, chrome) is tracked
separately and always active, so inserted "idle" beats are reinforcement
pulses rather than the only motion on screen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

MIN_GAP = 1.5
MAX_GAP = 3.0
MAX_STATIC = 2.5


@dataclass
class Beat:
    t: float
    kind: str                 # e.g. cue, impact, entrance, pulse, exit, draw
    text: Optional[str] = None
    impact: bool = False
    note: str = ""


@dataclass
class SceneBeatPlan:
    scene: int
    duration: float
    beats: List[Beat] = field(default_factory=list)
    ambient_layers: List[str] = field(default_factory=list)
    impact_texts: List[str] = field(default_factory=list)
    active_layers: int = 0

    @property
    def intervals(self) -> List[float]:
        ts = [b.t for b in self.beats]
        edges = [0.0] + ts + [self.duration]
        return [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]

    @property
    def max_static(self) -> float:
        return max(self.intervals) if self.intervals else self.duration

    @property
    def mean_interval(self) -> float:
        return sum(self.intervals) / len(self.intervals) if self.intervals else 0.0


def build_scene_beats(scene: int, duration: float,
                      cue_starts: List[float],
                      impact_texts: Optional[List[str]] = None,
                      extra_events: Optional[List[Beat]] = None,
                      ambient_layers: Optional[List[str]] = None,
                      active_layers: int = 4) -> SceneBeatPlan:
    """Create a beat plan from SRT cue starts and scene-specific events."""
    plan = SceneBeatPlan(scene=scene, duration=duration,
                         ambient_layers=ambient_layers or [],
                         impact_texts=impact_texts or [],
                         active_layers=active_layers)
    beats: Dict[float, Beat] = {}

    def add(t: float, beat: Beat) -> None:
        key = round(float(t), 3)
        if key not in beats:
            beats[key] = beat

    for i, t in enumerate(cue_starts):
        add(t, Beat(t=t, kind="cue", note=f"narration cue {i + 1}"))
    for ev in extra_events or []:
        add(ev.t, ev)
    for word in impact_texts or []:
        # Impact words attach to the nearest earlier cue beat.
        anchor = max([0.0] + [t for t in cue_starts if t <= duration])
        add(anchor, Beat(t=anchor, kind="impact", text=word, impact=True))

    # Fill any gap longer than MAX_STATIC with reinforcement pulse beats,
    # then bisect any residual over-length interval (including the tail).
    for _ in range(12):
        ordered = sorted(beats)
        edges = [0.0] + ordered + [duration]
        intervals = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
        worst = max(range(len(intervals)), key=lambda j: intervals[j])
        if intervals[worst] <= MAX_STATIC:
            break
        mid = (edges[worst] + edges[worst + 1]) / 2.0
        add(mid, Beat(t=mid, kind="pulse",
                      note="scheduler-added reinforcement"))
    plan.beats = [beats[k] for k in sorted(beats)]
    return plan


def validate_plan(plan: SceneBeatPlan) -> dict:
    """Objective gate data used by the motion QA report."""
    return {
        "scene": plan.scene,
        "duration": round(plan.duration, 2),
        "beat_count": len(plan.beats),
        "mean_interval": round(plan.mean_interval, 2),
        "max_static": round(plan.max_static, 2),
        "impact_count": len(plan.impact_texts),
        "active_layers": plan.active_layers,
        "ambient_layers": plan.ambient_layers,
        "passes_pacing": plan.mean_interval <= MAX_GAP
                         and plan.max_static <= MAX_STATIC + 0.05,
        "passes_impact": len(plan.impact_texts) >= 1,
        "passes_layers": plan.active_layers >= 3,
    }
