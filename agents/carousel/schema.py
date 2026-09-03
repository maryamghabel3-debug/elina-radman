"""
Carousel slide schema and validation (M18A).

Defines the CarouselSlide data model, the canonical carousel canvas
(1080x1350, Instagram 4:5), per-type text limits, and typed error codes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Canonical static carousel canvas (Instagram portrait 4:5)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350

SUPPORTED_SLIDE_TYPES = ("cover", "title_body", "quote", "bullet_list", "image_text", "image_overlay", "cta")
SUPPORTED_TEMPLATES = ("psychological_dark", "midnight_editorial", "warm_cream", "minimal_photo")
DEFAULT_TEMPLATE = "psychological_dark"

# Typed error codes
CAROUSEL_SLIDE_CONFIG_INVALID = "CAROUSEL_SLIDE_CONFIG_INVALID"
CAROUSEL_IMAGE_NOT_FOUND = "CAROUSEL_IMAGE_NOT_FOUND"
CAROUSEL_FONT_NOT_FOUND = "CAROUSEL_FONT_NOT_FOUND"
CAROUSEL_TEXT_OVERFLOW = "CAROUSEL_TEXT_OVERFLOW"
CAROUSEL_RENDER_FAILED = "CAROUSEL_RENDER_FAILED"


class CarouselError(Exception):
    """Base class for typed carousel errors (carries a machine-readable code)."""

    code: str = CAROUSEL_RENDER_FAILED

    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(f"{self.code}: {detail}" if detail else self.code)


class CarouselConfigError(CarouselError):
    code = CAROUSEL_SLIDE_CONFIG_INVALID


class CarouselImageError(CarouselError):
    code = CAROUSEL_IMAGE_NOT_FOUND


class CarouselFontError(CarouselError):
    code = CAROUSEL_FONT_NOT_FOUND


class CarouselTextOverflowError(CarouselError):
    code = CAROUSEL_TEXT_OVERFLOW


class CarouselRenderError(CarouselError):
    code = CAROUSEL_RENDER_FAILED


# Per-slide-type text limits (phone-readable; enforced at parse time)
TEXT_LIMITS: Dict[str, Dict[str, int]] = {
    "cover":       {"title": 60, "body": 80},
    "title_body":  {"title": 80, "body": 240},
    "quote":       {"title": 180, "body": 0},
    "bullet_list": {"title": 80, "body": 0, "bullet": 64},
    "image_text":  {"title": 60, "body": 140},
    "image_overlay": {"title": 60, "body": 140},
    "cta":         {"title": 60, "body": 80},
}
MIN_BULLETS = 2
MAX_BULLETS = 5


@dataclass
class CarouselSlide:
    """One static branded carousel slide (M18A).

    template=None means "inherit from the parent deck" (M18B); standalone
    rendering falls back to DEFAULT_TEMPLATE.
    """

    slide_type: str
    title: str = ""
    body: str = ""
    bullets: List[str] = field(default_factory=list)
    image_path: Optional[str] = None
    eyebrow: str = ""
    footer: str = ""
    template: Optional[str] = None
    accent: str = "antique_gold"
    slide_number: Optional[int] = None


def _as_str(value: Any, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CarouselConfigError(f"'{name}' must be a string")
    return value


def parse_carousel_slide(raw: Dict[str, Any]) -> CarouselSlide:
    """
    Validate a raw slide dict and return a CarouselSlide.

    Raises CarouselConfigError (code CAROUSEL_SLIDE_CONFIG_INVALID) on any
    invalid value. Unknown keys are ignored for forward compatibility.
    """
    if not isinstance(raw, dict):
        raise CarouselConfigError("slide must be a dictionary")

    slide_type = raw.get("slide_type")
    if slide_type not in SUPPORTED_SLIDE_TYPES:
        raise CarouselConfigError(
            f"slide_type '{slide_type}' is not supported (use one of {list(SUPPORTED_SLIDE_TYPES)})"
        )

    template = raw.get("template")
    if template is not None:
        if not isinstance(template, str) or template not in SUPPORTED_TEMPLATES:
            raise CarouselConfigError(
                f"template '{template}' is not supported (use one of {list(SUPPORTED_TEMPLATES)})"
            )

    accent = raw.get("accent", "antique_gold")
    # Imported lazily to avoid a circular import at module load
    from agents.carousel.brand_theme import PALETTE

    if accent not in PALETTE:
        raise CarouselConfigError(
            f"accent '{accent}' is not a Brand Book V2 palette color (use one of {sorted(PALETTE)})"
        )

    title = _as_str(raw.get("title"), "title").strip()
    body = _as_str(raw.get("body"), "body").strip()
    eyebrow = _as_str(raw.get("eyebrow"), "eyebrow").strip()
    footer = _as_str(raw.get("footer"), "footer").strip()
    image_path = raw.get("image_path")
    if image_path is not None and not isinstance(image_path, str):
        raise CarouselConfigError("'image_path' must be a string or null")

    slide_number = raw.get("slide_number")
    if slide_number is not None:
        if not isinstance(slide_number, int) or isinstance(slide_number, bool) or slide_number < 1:
            raise CarouselConfigError("'slide_number' must be a positive integer or null")

    limits = TEXT_LIMITS[slide_type]
    if len(title) > limits.get("title", 0):
        raise CarouselConfigError(
            f"{slide_type} title is {len(title)} chars; maximum is {limits['title']}"
        )
    if len(body) > limits.get("body", 0):
        raise CarouselConfigError(
            f"{slide_type} body is {len(body)} chars; maximum is {limits['body']}"
        )
    if eyebrow and len(eyebrow) > 40:
        raise CarouselConfigError(f"eyebrow is {len(eyebrow)} chars; maximum is 40")
    if footer and len(footer) > 60:
        raise CarouselConfigError(f"footer is {len(footer)} chars; maximum is 60")

    # Per-type required fields and bullet rules
    if slide_type == "cover" and not title:
        raise CarouselConfigError("cover slide requires a non-empty title")
    if slide_type == "title_body" and (not title or not body):
        raise CarouselConfigError("title_body slide requires non-empty title and body")
    if slide_type == "quote" and not title:
        raise CarouselConfigError("quote slide requires a non-empty title (the quote text)")
    if slide_type == "cta" and not title:
        raise CarouselConfigError("cta slide requires a non-empty title (the single action)")

    raw_bullets = raw.get("bullets", [])
    if not isinstance(raw_bullets, list):
        raise CarouselConfigError("'bullets' must be a list of strings")
    bullets = [b.strip() for b in (raw_bullets or []) if isinstance(b, str) and b.strip()]
    if slide_type == "bullet_list":
        if not (MIN_BULLETS <= len(bullets) <= MAX_BULLETS):
            raise CarouselConfigError(
                f"bullet_list requires {MIN_BULLETS}-{MAX_BULLETS} bullets (got {len(bullets)})"
            )
        bullet_limit = limits["bullet"]
        for i, b in enumerate(bullets):
            if len(b) > bullet_limit:
                raise CarouselConfigError(
                    f"bullet {i} is {len(b)} chars; maximum is {bullet_limit}"
                )
        if not title:
            raise CarouselConfigError("bullet_list slide requires a non-empty title")
    elif bullets:
        raise CarouselConfigError(f"'bullets' is only supported by slide_type 'bullet_list'")

    if slide_type in ("image_text", "image_overlay"):
        if not image_path:
            raise CarouselConfigError(f"{slide_type} slide requires 'image_path'")
        if not title and not body:
            raise CarouselConfigError(f"{slide_type} slide requires a non-empty title and/or body")

    return CarouselSlide(
        slide_type=slide_type,
        title=title,
        body=body,
        bullets=bullets,
        image_path=image_path,
        eyebrow=eyebrow,
        footer=footer,
        template=template,
        accent=accent,
        slide_number=slide_number,
    )
