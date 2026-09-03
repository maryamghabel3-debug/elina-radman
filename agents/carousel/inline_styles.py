"""
Per-word inline styling markup for carousel slide text (M26).

Markup format (works in carousel slide TITLES and BODIES only — video
subtitles stay plain):

    [word|color=#B89B65]
    [word|size=1.3]
    [word|color=#B89B65,size=1.3]

Behavior:
- Text outside [...] renders with the default style.
- Text inside [...] renders with the specified overrides:
  * color: a #RRGGBB hex string, applied to that word/phrase only
  * size: a float multiplier relative to the current font size
    (1.0 = same, 1.3 = 30% larger, 0.8 = 20% smaller)
- Multiple words can be inside one bracket ([خودِ کاذب|color=#B89B65])
  and multiple styled segments are allowed in one line; unstyled text
  between styled segments renders normally.

Fallbacks (never crash on bad markup):
- No [...] markup -> a single plain segment (byte-identical rendering).
- Malformed markup (missing '|' or ']', unknown/bad attributes, nested
  brackets) -> the WHOLE text is treated as plain and a warning is
  logged.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# size multiplier sanity bounds (guards against typos like size=13)
MIN_SIZE_MULTIPLIER = 0.2
MAX_SIZE_MULTIPLIER = 3.0

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ATTR_SPLIT_RE = re.compile(r"^\s*([A-Za-z_]+)\s*=\s*([^,\s]+)\s*$")


@dataclass
class TextSegment:
    """A run of text with optional inline style overrides (M26).

    color: "#RRGGBB" (upper-cased) or None; size_multiplier: 1.0 =
    unchanged, applied relative to the current (base) font size.
    """

    text: str
    color: Optional[str] = None
    size_multiplier: float = 1.0


def parse_inline_styles(text: str) -> List[TextSegment]:
    """Parse [phrase|attrs] inline markup into TextSegments.

    Returns a single plain segment when the text has no markup (or the
    markup is malformed — whole text falls back to plain, with a
    warning). Adjacent plain segments are merged.
    """
    text = text or ""
    if "[" not in text:
        return [TextSegment(text)]

    pos = 0
    segments: List[TextSegment] = []
    valid = True
    found_any = False

    while pos < len(text):
        open_idx = text.find("[", pos)
        if open_idx == -1:
            if pos < len(text):
                segments.append(TextSegment(text[pos:]))
            break
        close_idx = text.find("]", open_idx)
        if close_idx == -1:  # unclosed bracket
            valid = False
            break
        inner = text[open_idx + 1:close_idx]
        if "|" not in inner:  # missing '|' (also covers empty brackets)
            valid = False
            break
        phrase, attrs = inner.split("|", 1)
        if not phrase.strip() or "[" in phrase or "]" in phrase:
            valid = False
            break
        color: Optional[str] = None
        size_multiplier = 1.0
        for attr in attrs.split(","):
            m = _ATTR_SPLIT_RE.match(attr)
            if not m:
                valid = False
                break
            key, value = m.group(1).lower(), m.group(2)
            if key == "color":
                if not _COLOR_RE.match(value):
                    valid = False
                    break
                color = value.upper()
            elif key == "size":
                try:
                    size_multiplier = float(value)
                except ValueError:
                    valid = False
                    break
                if not (MIN_SIZE_MULTIPLIER <= size_multiplier <= MAX_SIZE_MULTIPLIER):
                    valid = False
                    break
            else:
                valid = False
                break
        if not valid:
            break
        if pos < open_idx:
            segments.append(TextSegment(text[pos:open_idx]))
        segments.append(TextSegment(phrase, color, size_multiplier))
        found_any = True
        pos = close_idx + 1

    if not valid or not found_any:
        logger.warning(
            "Malformed inline style markup in slide text; rendering as "
            "plain text: %r", text[:120],
        )
        return [TextSegment(text)]

    # Merge adjacent plain segments so the renderer sees one run of
    # unstyled text.
    merged: List[TextSegment] = []
    for seg in segments:
        plain = seg.color is None and seg.size_multiplier == 1.0
        if merged and plain and (
            merged[-1].color is None and merged[-1].size_multiplier == 1.0
        ):
            merged[-1] = TextSegment(merged[-1].text + seg.text)
        else:
            merged.append(seg)
    return merged


def has_inline_styles(text: str) -> bool:
    """True when `text` contains at least one VALID styled segment with an
    actual override (fast check so unmarked text takes the plain path)."""
    text = text or ""
    if "[" not in text:
        return False
    return any(
        seg.color is not None or seg.size_multiplier != 1.0
        for seg in parse_inline_styles(text)
    )
