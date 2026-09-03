"""
Conversational carousel studio session state machine (M18D).

Holds all non-Telegram logic of the Studio Bot's /carousel flow so the bot
file stays a thin transport layer (owner gating, file download, media group
sends). Everything here is synchronous and mockable: planner, renderer,
storage, and db are injected where used.

States:
    MODE_SELECT  -> COLLECT_IMAGES -> (COLLECT_TEXTS ->) BUILDING -> PREVIEW
                                   -> COLLECT_TOPIC -> BUILDING -> PREVIEW

Session data lives in context.chat_data["carousel_session"] as a plain dict,
kept separate from the /plan flow keys (plan_mode/plan_target_id/plan_preview)
so the two flows never collide.
"""

import datetime
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from agents.carousel.brand_theme import TEMPLATES
from agents.carousel.character_assets import LocalCharacterAssetProvider
from agents.carousel.deck_renderer import (
    CarouselDeck,
    CarouselDeckRenderer,
    prepare_carousel_content_item,
)
from agents.carousel.planner import (
    CarouselPlanner,
    CarouselCharacterAssetsError,
    CarouselPlanConfigError,
    CarouselPlanGenerationError,
)
from agents.carousel.schema import (
    SUPPORTED_TEXT_ZONES,
    CarouselError,
    CarouselSlide,
    CarouselTextOverflowError,
    parse_carousel_slide,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODE_SELECT = "MODE_SELECT"
COLLECT_IMAGES = "COLLECT_IMAGES"
COLLECT_TEXTS = "COLLECT_TEXTS"
COLLECT_TOPIC = "COLLECT_TOPIC"
BUILDING = "BUILDING"
PREVIEW = "PREVIEW"

MODE_BY_INDEX = {"1": "text_overlay", "2": "image_deck", "3": "ai_planned"}
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

MIN_IMAGES = 2
MAX_IMAGES = 10
MIN_SLIDES = 3
MAX_SLIDES = 10
DEFAULT_SLIDE_COUNT = 6
SESSION_TIMEOUT_MINUTES = 30

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Content-item status for an approved, awaiting-schedule carousel. Reuses the
# existing convention: /promote moves items to READY_FOR_REVIEW, where they
# wait for /approve <slot> -> SCHEDULED.
APPROVED_STATUS = "READY_FOR_REVIEW"

MODE_MENU_FA = (
    "حالت ساخت کاروسل فعال شد.\n\n"
    "یک گزینه انتخاب کن:\n"
    "۱) عکس و متن می‌دهم\n"
    "۲) عکس می‌دهم + موضوع\n"
    "۳) فقط موضوع، الینا خودش بسازد"
)

IMAGES_INSTRUCTIONS_FA = (
    f"حالا عکس‌ها را یکی‌یکی بفرست (حداقل {MIN_IMAGES}، حداکثر {MAX_IMAGES}).\n"
    "وقتی تمام شد /done بزن."
)

TEXTS_INSTRUCTIONS_FA_TEMPLATE = (
    "حالا {n} متن اسلاید را به ترتیب بفرست (هر پیام = یک اسلاید).\n"
    "برای داشتن بدنه: عنوان | بدنه\n"
    "وقتی تمام شد /done بزن."
)

TOPIC_INSTRUCTIONS_FA = (
    "حالا موضوع را بفرست.\n"
    "(اختیاری: موضوع | تعداد اسلاید — پیش‌فرض ۶، بین ۳ تا ۱۰)"
)

PREVIEW_COMMANDS_FA = (
    "برای ادامه:\n"
    "/carousel_ok — تأیید و ذخیره\n"
    "/carousel_edit <شماره> | <متن جدید> — ویرایش یک اسلاید\n"
    "/carousel_edit <شماره> | layout=full — چیدمان (split|full|contain|auto)\n"
    "/carousel_edit <شماره> | zone=top — جای متن (top|middle|bottom)\n"
    "/carousel_layout <layout> [شماره] — چیدمان اسلایدهای تصویری\n"
    "/carousel_theme <قالب> — تغییر قالب و رندر مجدد\n"
    "/carousel_cancel — انصراف"
)

# /carousel_layout short names -> slide image_layout values (M22A/M23)
LAYOUT_ALIASES = {
    "split": "split_panel",
    "full": "full_bleed_caption",
    "contain": "contain_caption",
    "auto": "auto",
}


class CarouselSessionActiveError(Exception):
    """A live carousel session already exists."""

    def __init__(self, message_fa: str):
        self.message_fa = message_fa
        super().__init__(message_fa)


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def new_session() -> Dict[str, Any]:
    work_dir = tempfile.mkdtemp(prefix="elina_carousel_")
    return {
        "state": MODE_SELECT,
        "mode": None,
        "images": [],          # local paths, received order
        "texts": [],           # [{"title": str, "body": str}]
        "topic": "",
        "slide_count": DEFAULT_SLIDE_COUNT,
        "template": "psychological_dark",
        "created_at": time.time(),
        "work_dir": work_dir,
        # M23: /carousel_layout issued during a COLLECT state is stored here
        # and applied to all image slides at build time
        "pending_image_layout": None,
        # populated at build time (in-memory only)
        "deck": None,          # CarouselDeck
        "slide_paths": [],     # ordered rendered PNGs
        "deck_title": "",
        "caption": "",
        "hashtags": [],
        "provider_used": None,
        "_renderer": None,     # CarouselDeckRenderer instance (in-memory)
    }


def session_expired(session: Any) -> bool:
    """A session is expired when older than SESSION_TIMEOUT_MINUTES.
    Anything that is not a well-formed session dict (e.g. mock artifacts or
    corrupted state) is treated as expired so it gets cleared, never crashes."""
    if not isinstance(session, dict):
        return True
    try:
        age_min = (time.time() - float(session.get("created_at", 0))) / 60.0
    except (TypeError, ValueError):
        return True
    return age_min > SESSION_TIMEOUT_MINUTES


def cleanup(session: Dict[str, Any]) -> None:
    work_dir = session.get("work_dir")
    if work_dir and os.path.isdir(work_dir):
        shutil.rmtree(work_dir, ignore_errors=True)
    session["work_dir"] = None


def start_session(chat_data: Dict[str, Any]) -> str:
    """
    Create a fresh session in chat_data and return the Persian reply text.
    Raises CarouselSessionActiveError if a live session already exists
    (an expired one is cleared first, with a notice in the reply).
    """
    prefix = ""
    session = chat_data.get("carousel_session")
    if session:
        if session_expired(session):
            cleanup(session)
            chat_data["carousel_session"] = None
            session = None
            prefix = "⏱️ جلسه کاروسل قبلی به دلیل بی‌حرکتی پاک شد.\n\n"
        else:
            raise CarouselSessionActiveError(
                "یک جلسه کاروسل فعال است. اول /carousel_cancel بزن تا از đầu شروع کنیم."
            )
    chat_data["carousel_session"] = new_session()
    return prefix + MODE_MENU_FA


def get_session(chat_data: Any) -> Optional[Dict[str, Any]]:
    """Return the carousel session dict, or None. Only real dicts count as
    sessions (defensive against mock/corrupted chat_data artifacts)."""
    if not isinstance(chat_data, dict):
        return None
    session = chat_data.get("carousel_session")
    return session if isinstance(session, dict) else None


def maybe_clear_expired(chat_data: Dict[str, Any]) -> bool:
    """Clear an expired session in place. Returns True if it was cleared."""
    session = get_session(chat_data)
    if session and session_expired(session):
        cleanup(session)
        chat_data["carousel_session"] = None
        return True
    return False


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

def select_mode(session: Dict[str, Any], raw_text: str) -> str:
    """MODE_SELECT only. Accepts 1/2/3 or Persian ۱/۲/۳. Returns the reply."""
    if session["state"] != MODE_SELECT:
        return "این مرحله دیگر فعال نیست. برای شروع دوباره /carousel_cancel و بعد /carousel بزن."
    digit = (raw_text or "").strip().translate(PERSIAN_DIGITS)
    mode = MODE_BY_INDEX.get(digit)
    if not mode:
        return "یک گزینه انتخاب کن: ۱، ۲ یا ۳"
    session["mode"] = mode
    if mode == "ai_planned":
        session["state"] = COLLECT_TOPIC
        return TOPIC_INSTRUCTIONS_FA
    session["state"] = COLLECT_IMAGES
    return IMAGES_INSTRUCTIONS_FA


def add_image(session: Dict[str, Any], local_path: str) -> Optional[str]:
    """Copy an image into the session work dir (order preserved).
    Returns a Persian error message, or None on success."""
    ext = os.path.splitext(local_path)[1].lower()
    if ext not in IMAGE_EXTS:
        return "فقط عکس قبول می‌شود (jpg / png / webp)."
    if not os.path.exists(local_path):
        return "فایل عکس پیدا نشد؛ دوباره بفرست."
    if len(session["images"]) >= MAX_IMAGES:
        return f"حداکثر {MAX_IMAGES} عکس. برای شروع دوباره /carousel_cancel بزن."
    target = os.path.join(session["work_dir"], f"img_{len(session['images']):02d}{ext}")
    try:
        shutil.copyfile(local_path, target)
    except OSError as exc:
        logger.error("Failed to stage carousel image: %s", exc)
        return "دریافت عکس ناموفق بود؛ دوباره بفرست."
    session["images"].append(target)
    return None


def finish_images(session: Dict[str, Any]) -> Optional[str]:
    """/done while COLLECT_IMAGES. Returns error message or instructions."""
    if session["state"] != COLLECT_IMAGES:
        return "این دستور در این مرحله کاربرد ندارد."
    if len(session["images"]) < MIN_IMAGES:
        return (
            f"حداقل {MIN_IMAGES} عکس لازم است؛ الان {len(session['images'])} عکس داری."
        )
    if session["mode"] == "text_overlay":
        session["state"] = COLLECT_TEXTS
        session["texts"] = []
        return TEXTS_INSTRUCTIONS_FA_TEMPLATE.format(n=len(session["images"]))
    # image_deck
    session["state"] = COLLECT_TOPIC
    return TOPIC_INSTRUCTIONS_FA


def parse_slide_text(raw: str) -> Dict[str, str]:
    """Parse 'title' or 'title | body' (split on the FIRST |)."""
    title, _, body = (raw or "").partition("|")
    title = title.strip()
    if not title:
        # No usable title before '|': treat the whole message as the title.
        return {"title": (raw or "").strip(), "body": ""}
    return {"title": title, "body": body.strip()}


def add_text(session: Dict[str, Any], raw: str) -> Dict[str, str]:
    """COLLECT_TEXTS: append one slide text (order preserved)."""
    entry = parse_slide_text(raw)
    session["texts"].append(entry)
    return entry


def finish_texts(session: Dict[str, Any]) -> Optional[str]:
    """/done while COLLECT_TEXTS. Returns error message or None (-> BUILDING)."""
    if session["state"] != COLLECT_TEXTS:
        return "این دستور در این مرحله کاربرد ندارد."
    n_images, n_texts = len(session["images"]), len(session["texts"])
    if n_texts != n_images:
        return (
            f"تعداد متن ({n_texts}) با تعداد عکس ({n_images}) برابر نیست؛ "
            f"دقیقاً {n_images} متن لازم دارم. متن‌های باقی‌مانده را بفرست و "
            "دوباره /done بزن."
        )
    session["state"] = BUILDING
    return None


def set_topic(session: Dict[str, Any], raw: str) -> Optional[str]:
    """COLLECT_TOPIC: 'topic' or 'topic | count'. Returns error or None."""
    if session["state"] != COLLECT_TOPIC:
        return "این مرحله دیگر فعال نیست."
    text = (raw or "").strip()
    if not text:
        return "موضوع خالی است؛ موضوع را دوباره بفرست."
    topic, sep, count_part = text.partition("|")
    topic = topic.strip()
    if not topic:
        return "موضوع خالی است؛ موضوع را دوباره بفرست."
    slide_count = DEFAULT_SLIDE_COUNT
    if sep:
        count_str = count_part.strip().translate(PERSIAN_DIGITS)
        if not count_str.isdigit():
            return "تعداد اسلاید نامعتبر است؛ عددی بین ۳ تا ۱۰ بده."
        slide_count = int(count_str)
        if not (MIN_SLIDES <= slide_count <= MAX_SLIDES):
            return f"تعداد اسلاید باید بین {MIN_SLIDES} تا {MAX_SLIDES} باشد."
    session["topic"] = topic
    session["slide_count"] = slide_count
    session["state"] = BUILDING
    return None


def recover_after_failure(session: Dict[str, Any]) -> None:
    """Return the session to its mode's collection state so the user can fix
    the problematic input and trigger a rebuild (images are preserved)."""
    if session["mode"] == "text_overlay":
        session["state"] = COLLECT_TEXTS
        session["texts"] = []
    else:
        session["state"] = COLLECT_TOPIC
        session["topic"] = ""


def _recovery_hint(session: Dict[str, Any]) -> str:
    if session["mode"] == "text_overlay":
        return "متن‌ها را دوباره (به ترتیب) بفرست و /done بزن."
    return "موضوع را دوباره بفرست تا دوباره بسازم."


# ---------------------------------------------------------------------------
# Build (planner + renderer)
# ---------------------------------------------------------------------------

def build_deck(
    session: Dict[str, Any],
    planner: Optional[CarouselPlanner] = None,
    renderer: Optional[CarouselDeckRenderer] = None,
    character_provider=None,
) -> Optional[str]:
    """
    Run the planner for the session's mode, then render the deck into the
    session work dir. On success: fills deck/slide_paths/caption/hashtags and
    sets state=PREVIEW; returns None. On failure: recovers the session and
    returns a Persian error message (never raises for typed planner errors).
    """
    mode = session.get("mode")
    planner = planner or CarouselPlanner()
    try:
        if mode == "text_overlay":
            result = planner.plan(
                mode="text_overlay",
                image_paths=list(session["images"]),
                slide_texts=[dict(t) for t in session["texts"]],
                template=session["template"],
            )
        elif mode == "image_deck":
            result = planner.plan(
                mode="image_deck",
                topic=session["topic"],
                image_paths=list(session["images"]),
                template=session["template"],
            )
        else:  # ai_planned (default)
            provider = character_provider if character_provider is not None \
                else LocalCharacterAssetProvider()
            result = planner.plan(
                session["topic"],
                slide_count=session["slide_count"],
                template=session["template"],
                character_asset_provider=provider,
            )

        # M23: a /carousel_layout issued during a COLLECT state is applied
        # to all image slides now, before the first render.
        pending_layout = session.get("pending_image_layout")
        if pending_layout:
            for s in result.deck.slides:
                if s.slide_type == "image_text":
                    s.image_layout = pending_layout
            session["pending_image_layout"] = None

        renderer = renderer or session.get("_renderer") or CarouselDeckRenderer()
        out_dir = os.path.join(session["work_dir"], "slides")
        os.makedirs(out_dir, exist_ok=True)
        paths = renderer.render_deck(result.deck, out_dir)

        session["deck"] = result.deck
        session["slide_paths"] = list(paths)
        session["deck_title"] = result.deck.title
        session["caption"] = result.caption or ""
        session["hashtags"] = list(result.hashtags or [])
        session["provider_used"] = getattr(result, "provider_used", None)
        session["_renderer"] = renderer
        session["state"] = PREVIEW
        return None
    except CarouselPlanConfigError as exc:
        recover_after_failure(session)
        return f"❌ ورودی کاروسل ناقص است: {exc.detail}\n{_recovery_hint(session)}"
    except CarouselPlanGenerationError as exc:
        recover_after_failure(session)
        return (
            "❌ تولید متن کاروسل این بار ممکن نشد (خطای موقتی). "
            f"جزئیات: {exc.detail}\n{_recovery_hint(session)}"
        )
    except CarouselCharacterAssetsError as exc:
        recover_after_failure(session)
        return (
            "❌ تصویر شخصیت برای اسلایدها پیدا نشد: "
            "فایل‌های شخصیت را در content/assets/characters/ قرار بده.\n"
            f"{_recovery_hint(session)}"
        )
    except CarouselTextOverflowError as exc:
        recover_after_failure(session)
        match = re.search(r"slide (\d+)", str(exc))
        n = match.group(1) if match else "؟"
        return (
            f"❌ متن اسلاید {n} جا نمی‌شود؛ آن را کوتاه‌تر کن.\n"
            f"{_recovery_hint(session)}"
        )
    except CarouselError as exc:
        recover_after_failure(session)
        return f"❌ خطا در ساخت کاروسل: {exc.detail or exc}\n{_recovery_hint(session)}"
    except Exception as exc:
        logger.exception("Carousel build failed")
        recover_after_failure(session)
        return (
            f"❌ خطای سیستمی در ساخت کاروسل: {type(exc).__name__}: {str(exc)[:200]}\n"
            f"{_recovery_hint(session)}"
        )


def build_preview_message(session: Dict[str, Any]) -> str:
    """Summary message shown before the media group in PREVIEW."""
    deck = session.get("deck")
    lines = [
        "🎨 پیش‌نمایش کاروسل:",
        f"عنوان: {session.get('deck_title') or (deck.title if deck else '—')}",
        f"تعداد اسلاید: {len(session.get('slide_paths') or [])}",
        f"قالب: {session.get('template')}",
    ]
    if session.get("caption"):
        lines.append(f"کپشن: {session['caption']}")
    lines.append("")
    lines.append(PREVIEW_COMMANDS_FA)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Preview editing
# ---------------------------------------------------------------------------

def _revalidate_and_rerender(
    session: Dict[str, Any],
    slide: CarouselSlide,
    index: int,
    rollback,
) -> Tuple[Optional[str], Optional[str]]:
    """Re-validate the edited slide through the M18A schema, then re-render
    ONLY that slide in place. `rollback()` restores the previous state on
    failure. Returns (error_message, updated_path); error_message None on
    success."""
    try:
        # Re-validate the edited slide through the M18A schema
        parse_carousel_slide({
            "slide_type": slide.slide_type,
            "title": slide.title,
            "body": slide.body,
            "bullets": slide.bullets,
            "image_path": slide.image_path,
            "image_layout": slide.image_layout,
            "text_zone": slide.text_zone,
            "eyebrow": slide.eyebrow,
            "footer": slide.footer,
            "template": slide.template,
            "accent": slide.accent,
            "slide_number": slide.slide_number,
        })
    except CarouselError as exc:
        rollback()
        code = getattr(exc, "code", "")
        return f"❌ ویرایش انجام نشد: {exc.detail or exc} ({code})".strip(" ()"), None

    renderer = session.get("_renderer")
    path = session["slide_paths"][index - 1]
    try:
        if renderer is not None and hasattr(renderer, "slide_renderer"):
            renderer.slide_renderer.render(slide, path)
        else:
            from agents.carousel.slide_renderer import CarouselSlideRenderer
            CarouselSlideRenderer().render(slide, path)
    except CarouselError as exc:
        rollback()
        return f"❌ رندر اسلاید ناکام بود: {exc.detail or exc}", None
    except Exception as exc:
        rollback()
        logger.exception("Slide re-render failed")
        return f"❌ خطا در رندر اسلاید: {type(exc).__name__}: {str(exc)[:150]}", None
    return None, path


def edit_slide(
    session: Dict[str, Any],
    index: int,
    new_text: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Edit slide `index` (1-based).

    Accepted forms (M23 extends title|body with layout/zone tokens;
    mixing text + layout in one command is not supported):
    - "<title> | <body>" or "<title>" — replace title (and body)
    - "layout=split|full|contain|auto" — change the slide's image layout
    - "zone=top|middle|bottom" — set the caption text zone

    Re-renders ONLY that slide (documented choice: single-slide re-render is
    faster and the layout is per-slide independent).
    Returns (error_message, updated_path); error_message None on success.
    """
    deck: Optional[CarouselDeck] = session.get("deck")
    if not deck:
        return "هنوز کاروسلی ساخته نشده است.", None
    total = len(deck.slides)
    if not (1 <= index <= total):
        return f"❌ شماره اسلاید نامعتبر است (۱ تا {total}).", None
    slide = deck.slides[index - 1]
    text = (new_text or "").strip()

    if text.startswith("layout="):
        value = text[len("layout="):].strip().lower()
        layout = LAYOUT_ALIASES.get(value)
        if layout is None:
            return "❌ نام layout نامعتبر است. گزینه‌ها: split | full | contain | auto", None
        if slide.slide_type != "image_text":
            return "❌ چیدمان فقط برای اسلایدهای تصویری (image_text) کاربرد دارد.", None
        old_layout = slide.image_layout
        slide.image_layout = layout

        def _rollback_layout():
            slide.image_layout = old_layout

        return _revalidate_and_rerender(session, slide, index, _rollback_layout)

    if text.startswith("zone="):
        value = text[len("zone="):].strip().lower()
        if value not in SUPPORTED_TEXT_ZONES:
            return "❌ نام zone نامعتبر است. گزینه‌ها: top | middle | bottom", None
        if slide.slide_type not in ("image_text", "image_overlay"):
            return "❌ zone فقط برای اسلایدهای تمام‌صفحه (تصویری) کاربرد دارد.", None
        old_zone = slide.text_zone
        slide.text_zone = value

        def _rollback_zone():
            slide.text_zone = old_zone

        return _revalidate_and_rerender(session, slide, index, _rollback_zone)

    title, sep, body = text.partition("|")
    title = title.strip()
    if not title:
        return "❌ متن جدید اسلاید خالی است.", None
    body = body.strip() if sep else None

    old_title, old_body = slide.title, slide.body
    slide.title = title
    if body and slide.slide_type in ("title_body", "image_text", "image_overlay"):
        slide.body = body

    def _rollback_text():
        slide.title, slide.body = old_title, old_body

    return _revalidate_and_rerender(session, slide, index, _rollback_text)


def apply_layout(
    session: Dict[str, Any],
    raw_text: str,
) -> str:
    """
    Handle /carousel_layout <layout> [slide_number] (M23).

    - layout: split | full | contain | auto (mapped to the image_layout
      values split_panel / full_bleed_caption / contain_caption / auto)
    - slide_number given: apply to that slide only (PREVIEW)
    - omitted: apply to ALL non-cover image slides in the draft
    - valid during PREVIEW (re-renders the affected slides) or a COLLECT
      state (stored in the session and applied to all image slides at
      build time)

    Returns the Persian confirmation/error message.
    """
    state = session.get("state")
    if state not in (COLLECT_IMAGES, COLLECT_TEXTS, COLLECT_TOPIC, PREVIEW):
        return "این دستور الان کاربرد ندارد. اول کاروسل ساخته شود."

    tokens = (raw_text or "").split()
    if not tokens:
        return "فرمت: /carousel_layout <split|full|contain|auto> [شماره‌ی اسلاید]"
    layout = LAYOUT_ALIASES.get(tokens[0].strip().lower())
    if layout is None:
        return "❌ نام layout نامعتبر است. گزینه‌ها: split | full | contain | auto"

    slide_num = None
    if len(tokens) >= 2:
        num_text = tokens[1].strip().translate(PERSIAN_DIGITS)
        if not num_text.isdigit():
            return "❌ شماره‌ی اسلاید نامعتبر است."
        slide_num = int(num_text)

    deck: Optional[CarouselDeck] = session.get("deck")
    if deck is None:
        # COLLECT state: no deck yet — remember it for build time
        if slide_num is not None:
            session["pending_image_layout"] = layout
            return (
                "شماره‌ی اسلاید فقط بعد از ساخت (پیش‌نمایش) معنا دارد؛ "
                f"چیدمان «{layout}» برای همه‌ی اسلایدهای تصویری ذخیره شد."
            )
        session["pending_image_layout"] = layout
        return (
            f"✅ چیدمان «{layout}» ذخیره شد؛ بعد از ساخت روی همه‌ی "
            "اسلایدهای تصویری اعمال می‌شود."
        )

    if slide_num is not None:
        if not (1 <= slide_num <= len(deck.slides)):
            return f"❌ شماره اسلاید نامعتبر است (۱ تا {len(deck.slides)})."
        slide = deck.slides[slide_num - 1]
        if slide.slide_type != "image_text":
            return "❌ چیدمان فقط برای اسلایدهای تصویری (image_text) کاربرد دارد."
        targets = [slide_num]
    else:
        targets = [i for i, s in enumerate(deck.slides, 1) if s.slide_type == "image_text"]
        if not targets:
            return "اسلاید تصویری (image_text) برای اعمال چیدمان پیدا نشد."

    renderer = session.get("_renderer")
    failed = []
    for i in targets:
        s = deck.slides[i - 1]
        s.image_layout = layout
        path = session["slide_paths"][i - 1]
        try:
            if renderer is not None and hasattr(renderer, "slide_renderer"):
                renderer.slide_renderer.render(s, path)
            else:
                from agents.carousel.slide_renderer import CarouselSlideRenderer
                CarouselSlideRenderer().render(s, path)
        except Exception as exc:
            logger.exception("Layout re-render failed for slide %s", i)
            failed.append(i)
    if failed:
        return f"❌ رندر مجدد اسلاید {' و '.join(str(n) for n in failed)} ناکام بود."

    if slide_num is not None:
        return f"✅ چیدمان «{layout}» روی اسلاید {slide_num} اعمال شد."
    return f"✅ چیدمان «{layout}» روی {len(targets)} اسلاید تصویری اعمال شد."


def change_theme(
    session: Dict[str, Any],
    template_name: str,
    renderer: Optional[CarouselDeckRenderer] = None,
) -> Optional[str]:
    """Validate + re-render the whole deck with a new template.
    Returns an error message or None on success."""
    if template_name not in TEMPLATES:
        return (
            f"❌ قالب '{template_name}' معتبر نیست.\n"
            f"قالب‌ها: {', '.join(sorted(TEMPLATES))}"
        )
    deck: Optional[CarouselDeck] = session.get("deck")
    if not deck:
        return "هنوز کاروسلی ساخته نشده است.", None
    deck.template = template_name
    session["template"] = template_name
    renderer = renderer or session.get("_renderer")
    try:
        for i, slide in enumerate(deck.slides):
            if slide.template is not None:
                # explicit per-slide template is preserved
                continue
            if renderer is not None and hasattr(renderer, "slide_renderer"):
                renderer.slide_renderer.render(slide, session["slide_paths"][i])
            else:
                from agents.carousel.slide_renderer import CarouselSlideRenderer
                CarouselSlideRenderer().render(slide, session["slide_paths"][i])
    except CarouselError as exc:
        return f"❌ رندر با قالب جدید ناکام بود: {exc.detail or exc}"
    except Exception as exc:
        logger.exception("Theme re-render failed")
        return f"❌ خطا در رندر با قالب جدید: {type(exc).__name__}: {str(exc)[:150]}"
    return None


# ---------------------------------------------------------------------------
# Finalize (upload + content item)
# ---------------------------------------------------------------------------

def generate_custom_id() -> str:
    """Existing style: ELN-CAR-YYYYMMDD-xxxxxxxx."""
    date_str = datetime.date.today().strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:8]
    return f"ELN-CAR-{date_str}-{short_id}"


def finalize(
    session: Dict[str, Any],
    storage: Any,
    db: Any,
    custom_id: Optional[str] = None,
    renderer: Optional[CarouselDeckRenderer] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Upload the ordered PNGs and create the carousel content item
    (content_type="carousel", ordered media_keys, status READY_FOR_REVIEW —
    the same awaiting-schedule state /promote produces for other items).
    Returns (error, info) where info = {custom_id, media_keys, payload}.
    """
    paths = session.get("slide_paths") or []
    if not paths:
        return "هنوز کاروسلی برای ذخیره ساخته نشده است.", None
    cid = custom_id or generate_custom_id()
    renderer = renderer or session.get("_renderer") or CarouselDeckRenderer()
    try:
        keys = renderer.upload_deck_to_storage(paths, cid, storage)
        deck: Optional[CarouselDeck] = session.get("deck")
        payload = prepare_carousel_content_item(
            db,
            cid,
            media_keys=keys,
            title=session.get("deck_title") or (deck.title if deck else ""),
            template=session.get("template", "psychological_dark"),
            caption_fa=session.get("caption", ""),
            status=APPROVED_STATUS,
        )
        return None, {
            "custom_id": cid,
            "media_keys": keys,
            "payload": payload,
            "status": APPROVED_STATUS,
        }
    except CarouselError as exc:
        return f"❌ ذخیره کاروسل ناکام بود: {exc.detail or exc}", None
    except Exception as exc:
        logger.exception("Carousel finalize failed")
        return (
            f"❌ خطا در ذخیره کاروسل: {type(exc).__name__}: {str(exc)[:200]}",
            None,
        )


def confirm_message(info: Dict[str, Any]) -> str:
    """Persian success message with the existing next steps."""
    cid = info["custom_id"]
    return (
        "✅ کاروسل تأیید و ذخیره شد.\n"
        f"شناسه: {cid}\n"
        f"تعداد اسلاید: {len(info['media_keys'])}\n"
        f"وضعیت: {info['status']}\n\n"
        "مرحله بعد:\n"
        f"/promote {cid}\n"
        f"سپس /approve {cid} <اسلات>"
    )
