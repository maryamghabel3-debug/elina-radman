"""
Reliable Persian font resolution (runtime font fix).

Persian rendering (typography, subtitles, carousel) must always be able to
find a Persian-capable font without depending on /tmp or a manual download.

Resolution order (first loadable candidate wins):
  A. explicit font_path (if valid)
  B. ELINA_FONT_PRIMARY_PATH (if valid; a configured-but-missing file logs a
     warning and continues to the fallbacks — it must NOT fail before the
     fallbacks are tried)
  C. repo-bundled font: assets/fonts/Vazirmatn-Bold.ttf (official Vazirmatn
     v33.003, SIL OFL — see assets/fonts/OFL-Vazirmatn.txt)
  D. known system Persian-capable fonts (first loadable wins)

A candidate is "valid" only if Pillow can actually load it
(ImageFont.truetype), so a corrupt or incompatible file also falls through
to the next candidate.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from PIL import ImageFont

logger = logging.getLogger(__name__)

# C. Repo-bundled fallback (official Vazirmatn v33.003, SIL OFL 1.1)
REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_FONT_PATH = REPO_ROOT / "assets" / "fonts" / "Vazirmatn-Bold.ttf"

# D. Known system Persian-capable fonts (best effort; first loadable wins)
SYSTEM_PERSIAN_FONT_CANDIDATES: List[str] = [
    # Debian/Ubuntu: fonts-hosny-amiri (full Persian coverage)
    "/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Regular.ttf",
    # Noto Arabic families (Persian-capable), common distro locations
    "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    # Vazirmatn if installed system-wide
    "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf",
]


class FontNotFoundError(Exception):
    """No Persian-capable font could be resolved from any candidate."""

    code = "PERSIAN_FONT_NOT_FOUND"

    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(f"{self.code}: {detail}" if detail else self.code)


def _is_loadable_font(path: str) -> bool:
    """A candidate is valid only if Pillow can actually load it."""
    try:
        ImageFont.truetype(str(path), 40)
        return True
    except Exception:
        return False


def resolve_persian_font(explicit_path: Optional[str] = None) -> str:
    """
    Resolve a Persian-capable font path (order A -> D, see module docstring).

    Returns an absolute font path. Raises FontNotFoundError when no candidate
    can be loaded by Pillow.
    """
    candidates: List[str] = []
    if explicit_path:
        candidates.append(str(explicit_path))
    env_path = (os.environ.get("ELINA_FONT_PRIMARY_PATH") or "").strip()
    if env_path:
        candidates.append(env_path)
    candidates.append(str(BUNDLED_FONT_PATH))
    candidates.extend(SYSTEM_PERSIAN_FONT_CANDIDATES)

    explicit = str(explicit_path) if explicit_path else None
    tried: List[str] = []
    for candidate in candidates:
        if not candidate or candidate in tried:
            continue
        tried.append(candidate)
        if not os.path.exists(candidate):
            # A user-provided path (explicit or env) that is missing deserves
            # a warning; bundled/system candidates are silent best-effort.
            if candidate in (explicit, env_path or None):
                logger.warning(
                    "Persian font path %s does not exist; continuing to fallback",
                    candidate,
                )
            continue
        if _is_loadable_font(candidate):
            return os.path.abspath(candidate)
        logger.warning(
            "Persian font candidate %s is not loadable by Pillow; continuing",
            candidate,
        )

    raise FontNotFoundError(
        "no Persian-capable font available (tried: " + "; ".join(tried) + ")"
    )
