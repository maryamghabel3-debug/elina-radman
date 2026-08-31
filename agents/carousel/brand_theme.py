"""
Brand Book V2 palette and carousel template themes (M18A).

The palette is encoded verbatim from docs/BRAND-BOOK-V2.md (section
"پالت رنگی"). Brand color rules from the same document are encoded as
template defaults below:

- default backgrounds are dark (ink_black / deep_charcoal / midnight_blue)
- default typography is bone_white on dark
- dried_blood is reserved for danger/wound/climax accents and is never a
  template default accent
- antique_gold stays restrained (thin rules, small marks)
- no generic pastel wellness styling, no ornamental motifs without meaning

This module is data-only: layout/rendering lives in slide_renderer.py.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

# Brand Book V2 palette (exact hex values)
PALETTE: Dict[str, str] = {
    # primary
    "ink_black": "#101014",
    "deep_charcoal": "#1A1A22",
    "midnight_blue": "#161C2D",
    "bone_white": "#E9E3DA",
    # accent
    "antique_gold": "#B89B65",
    "dried_blood": "#762F35",
    "muted_saffron": "#B9853B",
    "oxidized_teal": "#355E61",
    # hope
    "warm_cream": "#F1E9DC",
    "dawn_gray": "#B8B4B0",
}


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    """Convert '#RRGGBB' (or a palette key) to an (r, g, b) tuple."""
    color = PALETTE.get(value, value)
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        raise ValueError(f"Invalid color '{value}': use a palette key or #RRGGBB")
    try:
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    except ValueError as exc:
        raise ValueError(f"Invalid color '{value}': not a #RRGGBB hex value") from exc


def palette_rgb(name: str) -> Tuple[int, int, int]:
    """Resolve a palette key to RGB (unknown keys are rejected)."""
    if name not in PALETTE:
        raise ValueError(f"Unknown palette color '{name}' (known: {sorted(PALETTE)})")
    return hex_to_rgb(PALETTE[name])


@dataclass(frozen=True)
class TemplateTheme:
    """A carousel template: colors + overlay + typography scale.

    overlay_alpha is the default full-bleed image overlay darkness (0..1)
    used so text stays readable on top of any source photo.
    """

    name: str
    background: str          # palette key
    text: str                # palette key
    secondary_text: str      # palette key (eyebrow/footer/author)
    accent: str              # palette key (default slide accent)
    surface: str             # palette key (panels under text on images)
    overlay_alpha: float     # 0..1
    title_size: int          # starting title font size
    body_size: int           # starting body font size
    min_title_size: int
    min_body_size: int


TEMPLATES: Dict[str, TemplateTheme] = {
    # Dark default: quiet, psychological, gold kept restrained
    "psychological_dark": TemplateTheme(
        name="psychological_dark",
        background="ink_black",
        text="bone_white",
        secondary_text="dawn_gray",
        accent="antique_gold",
        surface="deep_charcoal",
        overlay_alpha=0.62,
        title_size=104,
        body_size=46,
        min_title_size=60,
        min_body_size=32,
    ),
    # Editorial dark blue with teal accent
    "midnight_editorial": TemplateTheme(
        name="midnight_editorial",
        background="midnight_blue",
        text="bone_white",
        secondary_text="dawn_gray",
        accent="oxidized_teal",
        surface="ink_black",
        overlay_alpha=0.58,
        title_size=100,
        body_size=44,
        min_title_size=58,
        min_body_size=32,
    ),
    # Hope/light: warm cream ground, ink text, saffron accent
    # (dried_blood intentionally NOT a default accent here)
    "warm_cream": TemplateTheme(
        name="warm_cream",
        background="warm_cream",
        text="ink_black",
        secondary_text="dawn_gray",
        accent="muted_saffron",
        surface="bone_white",
        overlay_alpha=0.45,
        title_size=96,
        body_size=44,
        min_title_size=56,
        min_body_size=32,
    ),
    # Photo-first: dark chrome, quiet gray accent, lighter overlay
    "minimal_photo": TemplateTheme(
        name="minimal_photo",
        background="deep_charcoal",
        text="bone_white",
        secondary_text="dawn_gray",
        accent="dawn_gray",
        surface="ink_black",
        overlay_alpha=0.5,
        title_size=92,
        body_size=42,
        min_title_size=56,
        min_body_size=30,
    ),
}


def get_template(name: str) -> TemplateTheme:
    """Return the TemplateTheme for a supported template name."""
    try:
        return TEMPLATES[name]
    except KeyError:
        raise ValueError(
            f"Unsupported template '{name}' (supported: {sorted(TEMPLATES)})"
        )
