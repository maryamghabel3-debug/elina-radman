"""
Automatic timed-subtitle synchronization from voice narration (TASK M17).

Turns a Persian narration into short, Instagram-readable timed subtitles:

- the narration text is chunked into phrase cues (clause punctuation +
  word-count heuristics, 1-2 lines per card, no one-word orphan tail);
- cue timings come from edge-tts word-boundary timing when a clean 1:1
  alignment with the source words is available;
- otherwise a SOFT FALLBACK distributes the cues proportionally over the
  generated audio duration (a timing gap must never fail the render);
- the voice track's start_sec offset is applied to every cue.

Manual plan subtitles always win: this module is only consulted when the
plan has no subtitles and the voice config enables auto_subtitles.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from agents.editing.recipe_schema import SubtitleEntry
from agents.editing.subtitle_renderer import SUPPORTED_POSITIONS, SUPPORTED_STYLES

logger = logging.getLogger(__name__)

# Typed config error (terminal): only for invalid auto-subtitle *config*.
# Recoverable timing-extraction gaps use the soft fallback instead.
VOICE_SUBTITLE_SYNC_CONFIG_INVALID = "VOICE_SUBTITLE_SYNC_CONFIG_INVALID"

# Chunking heuristics (keep cues short and readable at 1080x1920)
MAX_WORDS_PER_CUE = 8
# A cue shorter than this gets merged/grown so fades fit and it stays visible
MIN_CUE_SEC = 0.20
DEFAULT_FADE_SEC = 0.12
# Last-resort speech-rate estimate when neither boundaries nor ffprobe
# produced a duration: ~0.45s per Persian word.
_ESTIMATED_SEC_PER_WORD = 0.45

# Persian clause punctuation: strong sentence end + soft clause separators.
# Covers both standard and full-width-ish variants actually used in the
# content corpus, plus their Latin lookalikes.
_STRONG_PUNCT = set("؟!.؟")
_SOFT_PUNCT = set("،؛,;")


def _clause_end_kind(word: str):
    """Return 'strong' / 'soft' / None depending on the trailing punctuation."""
    core = word.strip()
    if not core:
        return None
    if core[-1] in _STRONG_PUNCT:
        return "strong"
    if core[-1] in _SOFT_PUNCT:
        return "soft"
    return None


def _chunk_ends_strong(chunk: List[str]) -> bool:
    return _clause_end_kind(chunk[-1]) == "strong"


def chunk_persian_text(text: str) -> List[List[str]]:
    """
    Split narration text into readable word-chunks (1-2 lines each).

    Prefers clause punctuation boundaries, caps chunk length at
    MAX_WORDS_PER_CUE words, and merges a one-word orphan tail into the
    previous chunk when that does not overflow the cap. An orphan is never
    merged into a chunk that already ends a full sentence (strong
    punctuation): a lone word after a sentence end is a new sentence and
    stays its own cue.
    """
    words = text.split()
    if not words:
        return []

    chunks: List[List[str]] = []
    current: List[str] = []
    for word in words:
        current.append(word)
        if _clause_end_kind(word) or len(current) >= MAX_WORDS_PER_CUE:
            chunks.append(current)
            current = []
    if current:
        if (
            len(current) == 1
            and chunks
            and not _chunk_ends_strong(chunks[-1])
            and len(chunks[-1]) + 1 <= MAX_WORDS_PER_CUE + 2
        ):
            chunks[-1].extend(current)  # avoid a mid-sentence one-word orphan card
        else:
            chunks.append(current)
    return chunks


def parse_voice_auto_subtitle_config(plan_voice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the auto-subtitle fields of a plan voice config.

    Returns {"enabled": bool, "style": str, "position": str}.
    Raises ValueError('VOICE_SUBTITLE_SYNC_CONFIG_INVALID: <reason>') on any
    invalid value. Absent fields keep existing behavior (disabled, defaults).
    """
    if not isinstance(plan_voice, dict):
        raise ValueError(f"{VOICE_SUBTITLE_SYNC_CONFIG_INVALID}: plan voice must be a dictionary")

    raw_enabled = plan_voice.get("auto_subtitles", False)
    if not isinstance(raw_enabled, bool):
        raise ValueError(
            f"{VOICE_SUBTITLE_SYNC_CONFIG_INVALID}: auto_subtitles must be a boolean (true/false)"
        )

    style = plan_voice.get("subtitle_style", "default")
    if not isinstance(style, str) or style not in SUPPORTED_STYLES:
        raise ValueError(
            f"{VOICE_SUBTITLE_SYNC_CONFIG_INVALID}: subtitle_style '{style}' is not supported "
            f"(use one of {list(SUPPORTED_STYLES)})"
        )

    position = plan_voice.get("subtitle_position", "bottom_center")
    if not isinstance(position, str) or position not in SUPPORTED_POSITIONS:
        raise ValueError(
            f"{VOICE_SUBTITLE_SYNC_CONFIG_INVALID}: subtitle_position '{position}' is not supported "
            f"(use one of {list(SUPPORTED_POSITIONS)})"
        )

    return {"enabled": raw_enabled, "style": style, "position": position}


def _valid_boundary(b: Dict[str, Any]) -> bool:
    try:
        start, end = float(b["start_sec"]), float(b["end_sec"])
    except (KeyError, TypeError, ValueError):
        return False
    return end > start >= 0


def build_auto_subtitle_entries(
    text: str,
    word_boundaries: Optional[List[Dict[str, float]]],
    audio_duration_sec: Optional[float],
    start_offset_sec: float = 0.0,
    style: str = "default",
    position: str = "bottom_center",
    font_size: int = 52,
) -> List[SubtitleEntry]:
    """
    Build SubtitleEntry cues from narration text + timing metadata.

    word_boundaries: one {"start_sec", "end_sec"} per spoken word, in
    utterance order (from edge-tts WordBoundary events); None/[] or a count
    that does not match the word count triggers proportional fallback.

    audio_duration_sec: ffprobe duration of the generated audio (0.0/None
    when unavailable); only used by the fallback and the last-resort
    estimate.

    This function never raises for timing gaps: it degrades to the
    proportional fallback and logs what it did.
    """
    text = (text or "").strip()
    chunks = chunk_persian_text(text)
    if not chunks:
        return []

    words = text.split()
    n_words = len(words)

    # Word-index range covered by each chunk
    ranges: List[tuple] = []
    idx = 0
    for chunk in chunks:
        ranges.append((idx, idx + len(chunk)))
        idx += len(chunk)

    have_timing = (
        word_boundaries is not None
        and len(word_boundaries) == n_words
        and all(_valid_boundary(b) for b in word_boundaries)
    )

    total = audio_duration_sec if (audio_duration_sec or 0) > 0 else None
    if have_timing:
        total = max(total or 0.0, word_boundaries[-1]["end_sec"])
        logger.info(
            "Auto subtitles: using edge-tts word-boundary timing over %.2fs (%d words, %d cues)",
            total, n_words, len(chunks),
        )
    else:
        if word_boundaries:
            logger.warning(
                "Auto subtitles: word-boundary count (%d) does not match word count (%d); "
                "falling back to proportional timing",
                len(word_boundaries), n_words,
            )
        if total is None:
            total = n_words * _ESTIMATED_SEC_PER_WORD
            logger.warning(
                "Auto subtitles: no audio duration available; estimating %.2fs "
                "(%.2fs per word) for proportional timing",
                total, _ESTIMATED_SEC_PER_WORD,
            )
        else:
            logger.warning(
                "Auto subtitles: no usable word-boundary metadata; "
                "falling back to proportional timing over %.2fs",
                total,
            )

    entries: List[SubtitleEntry] = []
    for chunk, (ws, we) in zip(chunks, ranges):
        if have_timing:
            start = word_boundaries[ws]["start_sec"]
            end = word_boundaries[we - 1]["end_sec"]
        else:
            start = total * (ws / n_words)
            end = total * (we / n_words)

        # Keep every cue at least MIN_CUE_SEC long and inside the audio span
        if end - start < MIN_CUE_SEC:
            end = start + MIN_CUE_SEC
        if end > total:
            start = max(0.0, total - MIN_CUE_SEC)
            end = total

        # Apply the voice track offset (narration may start later than t=0)
        start += start_offset_sec
        end += start_offset_sec

        duration = end - start
        # Fades must satisfy the M16 constraint fade_in + fade_out <= duration
        fade = min(DEFAULT_FADE_SEC, duration / 2)

        entries.append(SubtitleEntry(
            text=" ".join(chunk),
            start_sec=round(start, 3),
            end_sec=round(end, 3),
            position=position,
            style=style,
            font_size=font_size,
            fade_in_sec=round(fade, 3),
            fade_out_sec=round(fade, 3),
        ))
    return entries
