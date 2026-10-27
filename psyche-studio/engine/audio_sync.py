"""Audio duration probing and SRT subtitle handling.

No ffprobe is bundled with imageio-ffmpeg, so duration is read from the
``ffmpeg -i`` banner on stderr (the Duration: line is printed even when no
output file is requested).
"""
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import imageio_ffmpeg

_DURATION_RE = re.compile(
    r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)"
)
_TIMESTAMP_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


def _ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def get_audio_duration(audio_path) -> float:
    """Return media duration in seconds by parsing ffmpeg's stderr banner."""
    cmd = [_ffmpeg_exe(), "-hide_banner", "-i", str(audio_path)]
    proc = subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
    )
    # ffmpeg exits non-zero when no output is requested; parse anyway.
    match = _DURATION_RE.search(proc.stderr or "")
    if not match:
        raise RuntimeError(
            f"Could not read duration from {audio_path}: "
            f"{(proc.stderr or '')[-400:]}"
        )
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _timestamp_to_seconds(value: str) -> float:
    match = _TIMESTAMP_RE.match(value.strip())
    if not match:
        raise ValueError(f"Unparseable SRT timestamp: {value!r}")
    h, m, s, ms = match.groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_srt(srt_path) -> List[Dict]:
    """Parse a standard SRT file into ``[{start, end, text}, ...]``.

    Multi-line cue text is joined with a single space. Index lines and
    blank separators are ignored.
    """
    raw = Path(srt_path).read_text(encoding="utf-8-sig")
    subtitles: List[Dict] = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timing_idx = next(
            (i for i, line in enumerate(lines) if "-->" in line), None
        )
        if timing_idx is None:
            continue
        start_raw, end_raw = lines[timing_idx].split("-->")
        text = " ".join(lines[timing_idx + 1:]).strip()
        subtitles.append({
            "start": _timestamp_to_seconds(start_raw),
            "end": _timestamp_to_seconds(end_raw),
            "text": text,
        })
    return sorted(subtitles, key=lambda cue: cue["start"])


def get_active_subtitles(
    subtitles: List[Dict], t: float
) -> Optional[str]:
    """Return the cue text active at time ``t`` seconds, else None."""
    for cue in subtitles:
        if cue["start"] <= t <= cue["end"]:
            return cue["text"]
    return None
