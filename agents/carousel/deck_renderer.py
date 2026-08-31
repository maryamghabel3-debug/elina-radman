"""
Ordered carousel deck renderer and export pipeline (M18B).

Builds an ordered multi-slide deck on top of the M18A slide renderer:

- deck schema + deck-level validation (2-10 slides, all slides valid)
- deterministic ordered rendering with stable zero-padded filenames
- deck-level consistency: template inheritance, deck footer inheritance,
  automatic slide numbering, soft cta-last / cover-first convention checks
- optional ordered storage upload helper (dependency-injected, no
  signed URLs, no publishing)
- optional content-item preparation helper (content_type="carousel" with
  ordered media_keys; not wired to any bot in M18B)
"""

import json
import logging
import os
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.carousel.brand_theme import TEMPLATES
from agents.carousel.schema import (
    DEFAULT_TEMPLATE,
    CarouselError,
    CarouselSlide,
    CarouselConfigError,
    parse_carousel_slide,
)
from agents.carousel.slide_renderer import CarouselSlideRenderer

logger = logging.getLogger(__name__)

# Typed deck error codes
CAROUSEL_DECK_INVALID = "CAROUSEL_DECK_INVALID"
CAROUSEL_DECK_EMPTY = "CAROUSEL_DECK_EMPTY"
CAROUSEL_DECK_RENDER_FAILED = "CAROUSEL_DECK_RENDER_FAILED"

MIN_DECK_SLIDES = 2
MAX_DECK_SLIDES = 10

STORAGE_CONTENT_TYPE = "image/png"
STORAGE_PREFIX = "carousel"


class CarouselDeckError(Exception):
    """Base class for typed carousel deck errors."""

    code: str = CAROUSEL_DECK_INVALID

    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(f"{self.code}: {detail}" if detail else self.code)


class CarouselDeckEmptyError(CarouselDeckError):
    code = CAROUSEL_DECK_EMPTY


class CarouselDeckRenderError(CarouselDeckError):
    code = CAROUSEL_DECK_RENDER_FAILED


@dataclass
class CarouselDeck:
    """An ordered multi-slide carousel deck (M18B)."""

    title: str = ""
    template: str = DEFAULT_TEMPLATE
    slides: List[CarouselSlide] = field(default_factory=list)
    deck_footer: str = ""
    output_prefix: Optional[str] = None
    visual_consistency: bool = True


def _soft_validate_order(deck: CarouselDeck) -> None:
    """Soft (log-only) convention checks: cover first, cta last.

    These are product conventions, not hard constraints; violations are
    logged as warnings and never fail the render.
    """
    if not deck.slides:
        return
    if deck.slides[0].slide_type != "cover":
        logger.warning(
            "Carousel convention: first slide is normally 'cover' (got '%s')",
            deck.slides[0].slide_type,
        )
    if deck.slides[-1].slide_type != "cta":
        logger.warning(
            "Carousel convention: last slide is normally 'cta' (got '%s')",
            deck.slides[-1].slide_type,
        )
    cta_positions = [i + 1 for i, s in enumerate(deck.slides) if s.slide_type == "cta"]
    if cta_positions and cta_positions[-1] != len(deck.slides):
        logger.warning(
            "Carousel convention: a 'cta' slide at position %d is not the last slide",
            cta_positions[-1],
        )


def parse_carousel_deck(raw: Dict[str, Any]) -> CarouselDeck:
    """
    Validate a raw deck dict and return a CarouselDeck.

    Raises:
    - CarouselDeckEmptyError (CAROUSEL_DECK_EMPTY) when the deck has no slides
    - CarouselDeckError (CAROUSEL_DECK_INVALID) for wrong slide counts,
      unsupported deck template, or any invalid child slide
    """
    if not isinstance(raw, dict):
        raise CarouselDeckError("deck must be a dictionary")

    title = raw.get("title") or ""
    if not isinstance(title, str):
        raise CarouselDeckError("'title' must be a string")

    template = raw.get("template", DEFAULT_TEMPLATE)
    if not isinstance(template, str) or template not in TEMPLATES:
        raise CarouselDeckError(
            f"deck template '{template}' is not supported (use one of {sorted(TEMPLATES)})"
        )

    deck_footer = raw.get("deck_footer") or ""
    if not isinstance(deck_footer, str):
        raise CarouselDeckError("'deck_footer' must be a string")

    output_prefix = raw.get("output_prefix")
    if output_prefix is not None and not isinstance(output_prefix, str):
        raise CarouselDeckError("'output_prefix' must be a string or null")

    visual_consistency = raw.get("visual_consistency", True)
    if not isinstance(visual_consistency, bool):
        raise CarouselDeckError("'visual_consistency' must be a boolean")

    raw_slides = raw.get("slides")
    if raw_slides is None:
        raise CarouselDeckEmptyError("deck has no slides")
    if not isinstance(raw_slides, list):
        raise CarouselDeckError("'slides' must be a list")
    if len(raw_slides) == 0:
        raise CarouselDeckEmptyError("deck has no slides")
    if len(raw_slides) < MIN_DECK_SLIDES:
        raise CarouselDeckError(
            f"deck requires at least {MIN_DECK_SLIDES} slides (got {len(raw_slides)})"
        )
    if len(raw_slides) > MAX_DECK_SLIDES:
        raise CarouselDeckError(
            f"deck allows at most {MAX_DECK_SLIDES} slides (got {len(raw_slides)})"
        )

    slides: List[CarouselSlide] = []
    for i, s in enumerate(raw_slides):
        try:
            slides.append(parse_carousel_slide(s))
        except CarouselConfigError as exc:
            raise CarouselDeckError(f"slide {i + 1}: {exc.detail}") from exc

    deck = CarouselDeck(
        title=title,
        template=template,
        slides=slides,
        deck_footer=deck_footer,
        output_prefix=output_prefix,
        visual_consistency=visual_consistency,
    )
    _soft_validate_order(deck)
    return deck


def _validate_deck_instance(deck: CarouselDeck) -> None:
    """Minimal re-validation for decks passed as dataclasses (not parsed)."""
    if not deck.slides:
        raise CarouselDeckEmptyError("deck has no slides")
    if len(deck.slides) < MIN_DECK_SLIDES:
        raise CarouselDeckError(
            f"deck requires at least {MIN_DECK_SLIDES} slides (got {len(deck.slides)})"
        )
    if len(deck.slides) > MAX_DECK_SLIDES:
        raise CarouselDeckError(
            f"deck allows at most {MAX_DECK_SLIDES} slides (got {len(deck.slides)})"
        )


class CarouselDeckRenderer:
    """Renders an ordered CarouselDeck to deterministic PNG files."""

    def __init__(
        self,
        slide_renderer: Optional[CarouselSlideRenderer] = None,
        engine=None,
        font_path: Optional[str] = None,
        canvas_size: Optional[tuple] = None,
    ):
        if slide_renderer is None:
            kwargs = {}
            if engine is not None:
                kwargs["engine"] = engine
            if font_path is not None:
                kwargs["font_path"] = font_path
            if canvas_size is not None:
                kwargs["canvas_size"] = canvas_size
            slide_renderer = CarouselSlideRenderer(**kwargs)
        self.slide_renderer = slide_renderer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_slide_filename(self, index: int, slide: CarouselSlide,
                             prefix: Optional[str] = None) -> str:
        """Deterministic zero-padded filename, e.g. '01_cover.png'."""
        base = f"{index:02d}_{slide.slide_type}.png"
        clean_prefix = (prefix or "").strip()
        return f"{clean_prefix}_{base}" if clean_prefix else base

    def render_deck(self, deck: "CarouselDeck | Dict[str, Any]", output_dir: str) -> List[str]:
        """
        Render every slide in deck order into output_dir.

        Applies deck-level consistency (template inheritance, deck footer
        inheritance, automatic slide numbering) and returns the ordered
        list of local PNG paths. Raises CarouselDeckRenderError wrapping
        the underlying slide error when any slide fails.
        """
        if isinstance(deck, dict):
            deck = parse_carousel_deck(deck)
        elif not isinstance(deck, CarouselDeck):
            raise CarouselDeckError("deck must be a CarouselDeck or a dict")
        else:
            _validate_deck_instance(deck)

        if not isinstance(output_dir, str) or not output_dir:
            raise CarouselDeckError("output_dir must be a non-empty path")

        prepared = self._prepare_slides(deck)
        os.makedirs(output_dir, exist_ok=True)

        paths: List[str] = []
        for i, slide in enumerate(prepared, start=1):
            filename = self.build_slide_filename(i, slide, deck.output_prefix)
            out_path = os.path.join(output_dir, filename)
            try:
                self.slide_renderer.render(slide, out_path)
            except CarouselError as exc:
                raise CarouselDeckRenderError(
                    f"slide {i} ({slide.slide_type}) failed: {exc.detail or exc}"
                ) from exc
            paths.append(out_path)
        return paths

    def upload_deck_to_storage(
        self,
        paths: List[str],
        custom_id: str,
        storage: Any,
    ) -> List[str]:
        """
        Upload ordered rendered PNGs to `carousel/<custom_id>/<filename>`.

        The `storage` object must implement upload_file(local, dest,
        content_type) — dependency-injected, so the deck renderer stays
        decoupled from Supabase. Returns the ordered storage keys.
        No signed URLs, no publishing.
        """
        if not paths:
            raise CarouselDeckError("no paths to upload")
        if not custom_id or not isinstance(custom_id, str):
            raise CarouselDeckError("custom_id is required")
        if not hasattr(storage, "upload_file"):
            raise CarouselDeckError("storage must implement upload_file(local, dest, content_type)")

        keys: List[str] = []
        for i, local_path in enumerate(paths, start=1):
            if not os.path.exists(local_path):
                raise CarouselDeckRenderError(f"file not found before upload: {local_path}")
            filename = os.path.basename(local_path)
            key = f"{STORAGE_PREFIX}/{custom_id}/{filename}"
            storage.upload_file(local_path, key, content_type=STORAGE_CONTENT_TYPE)
            keys.append(key)
        return keys

    # ------------------------------------------------------------------
    # Deck-level consistency
    # ------------------------------------------------------------------

    def _prepare_slides(self, deck: CarouselDeck) -> List[CarouselSlide]:
        """Return slide copies with deck-level inheritance applied:
        template inheritance, deck footer inheritance, auto slide numbers."""
        prepared: List[CarouselSlide] = []
        for i, slide in enumerate(deck.slides, start=1):
            s = deepcopy(slide)
            if s.template is None:
                s.template = deck.template
            if not s.footer and deck.deck_footer:
                s.footer = deck.deck_footer
            if s.slide_number is None:
                s.slide_number = i
            prepared.append(s)
        return prepared


def prepare_carousel_content_item(
    db: Any,
    custom_id: str,
    media_keys: List[str],
    title: str = "",
    template: str = DEFAULT_TEMPLATE,
    caption_fa: str = "",
    source: str = "carousel_studio",
    status: str = "READY_FOR_REVIEW",
) -> Dict[str, Any]:
    """
    Create a 'carousel' content item holding the ordered slide media keys.

    The scheduler already knows how to publish 'carousel' items from an
    ordered media_keys list; this helper only prepares the item. It is NOT
    wired to any bot/Telegram command and does not schedule or publish.
    The `db` object must implement insert_content(dict).
    """
    if not custom_id or not isinstance(custom_id, str):
        raise CarouselDeckError("custom_id is required")
    if not media_keys:
        raise CarouselDeckEmptyError("media_keys must not be empty")
    if not hasattr(db, "insert_content"):
        raise CarouselDeckError("db must implement insert_content(data)")

    metadata = {
        "deck_title": title,
        "deck_template": template,
        "slide_count": len(media_keys),
        "created_by": "carousel_deck_renderer",
    }
    payload = {
        "id": str(uuid.uuid4()),
        "custom_id": custom_id,
        "content_type": "carousel",
        "caption_fa": caption_fa,
        "status": status,
        "media_keys": list(media_keys),
        "source": source,
        "editor_notes": json.dumps(metadata, ensure_ascii=False),
    }
    db.insert_content(payload)
    logger.info(
        "Prepared carousel content item %s with %d ordered slides",
        custom_id, len(media_keys),
    )
    return payload
