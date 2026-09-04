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
from agents.carousel.inline_styles import split_pipes_outside_brackets
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
# M29: in-memory session lifetime — 6 hours (was 30 minutes) so an
# operator can step away and come back to the same draft.
SESSION_TIMEOUT_MINUTES = 6 * 60
# M29: durable draft lifetime — drafts older than this are not resumable.
DRAFT_MAX_AGE_DAYS = 30

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
    "/carousel_edit <شماره> | zone=بالا-راست — جای متن (zone= | title_zone= | body_zone=)\n"
    "/carousel_edit <شماره> | style=blend — استایل متن (gradient|blend)\n"
    "/carousel_edit <شماره> | size=0.85 — اندازه‌ی متن (0.7 تا 1.3)\n"
    "/carousel_layout <split|full|contain|auto> [شماره] — چیدمان اسلایدهای تصویری\n"
    "/carousel_layout zone|style|size <مقدار> [شماره] — تنظیم متن همه‌ی اسلایدهای تصویری\n"
    "/carousel_theme <قالب> — تغییر قالب و رندر مجدد\n"
    "/carousel_list — نمایش کاروسل‌های ذخیره‌شده\n"
    "/carousel_resume [custom_id] — ادامه‌ی یک پیش‌نمایش ذخیره‌شده\n"
    "Reply به یک عکس/متن قبلی + «ثبت» — ثبت دوباره\n"
    "Reply به یک اسلاید پیش‌نمایش + «جایگزین» — تعویض تصویر اسلاید\n"
    "/carousel_cancel — انصراف"
)

# M29 Persian messages for the durable draft workflow
DRAFT_SAVED_HINT_FA = "💾 پیش‌نمایش ذخیره شد"
DRAFT_NONE_FA = "❌ پیش‌نمایش ذخیره‌شده‌ای پیدا نشد."
DRAFT_EXPIRED_FA = "❌ این پیش‌نمایش منقضی شده است (بیش از {days} روز).".format(days=DRAFT_MAX_AGE_DAYS)
DRAFT_ACTIVE_SESSION_FA = "❌ یک جلسه‌ی کاروسل فعال است؛ اول /carousel_cancel بزن."
DRAFT_NOT_FOUND_ID_FA = "❌ کاروسل با شناسه‌ی «{cid}» پیدا نشد."
REPLY_NOT_RESOLVED_FA = "❌ پیام مرجع را نمی‌شود شناسایی کرد."
REPLY_WRONG_STATE_FA = "❌ این کار فقط در مرحله‌ی مربوطه ممکن است."
REPLY_REPLACE_UNKNOWN_SLIDE_FA = (
    "❌ اسلاید مرجع را پیدا نکردم؛ مستقیم روی اسلایدِ پیش‌نمایش فعلی Reply بزن."
)
REPLY_REPLACE_PENDING_FA = "حالا عکس جایگزین اسلاید {n} را بفرست."
REPLY_IMAGE_READDED_FA = "✅ عکس {n} دوباره ثبت شد."
REPLY_TEXT_READDED_FA = "✅ متن {n} دوباره ثبت شد."
SLIDE_REPLACED_FA = "✅ اسلاید {n} جایگزین شد."
DRAFT_DELETED_NOTE_FA = "💾 پیش‌نمایش ذخیره‌شده هم حذف شد."

# /carousel_layout short names -> slide image_layout values (M22A/M23)
LAYOUT_ALIASES = {
    "split": "split_panel",
    "full": "full_bleed_caption",
    "contain": "contain_caption",
    "auto": "auto",
}

# Zone tokens accepted from Telegram (M25): English canonical names +
# Persian short names and combos. Mapped to the schema values here (the
# Telegram layer only — the schema accepts the canonical names + "auto").
ZONE_ALIASES = {
    "auto": "auto",
    "top": "top", "middle": "middle", "bottom": "bottom",
    "left": "left", "right": "right",
    "top_left": "top_left", "top_right": "top_right",
    "bottom_left": "bottom_left", "bottom_right": "bottom_right",
    "middle_left": "middle_left", "middle_right": "middle_right",
    "بالا": "top", "وسط": "middle", "پایین": "bottom",
    "چپ": "left", "راست": "right",
    "بالا-چپ": "top_left", "بالا-راست": "top_right",
    "پایین-چپ": "bottom_left", "پایین-راست": "bottom_right",
    "وسط-چپ": "middle_left", "وسط-راست": "middle_right",
}

# Slides that support caption composition (M25 zones/style/scale)
_PHOTO_SLIDE_TYPES = ("cover", "image_text", "image_overlay")


def normalize_zone_token(value: str) -> Optional[str]:
    """Map an English or Persian zone token to its canonical value, or None
    when the token is not a recognized zone (M25)."""
    v = (value or "").strip()
    if not v:
        return None
    if v in ZONE_ALIASES:
        return ZONE_ALIASES[v]
    low = v.lower()
    if low in ZONE_ALIASES:
        return ZONE_ALIASES[low]
    return None


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
        # M29: durable draft workflow
        "_persistence": None,          # {"db", "storage", "chat_id"} (best-effort)
        "uploaded_image_keys": {},     # local image path -> storage key
        "draft_history": [],           # finalized versions [{custom_id, title, ...}]
        "custom_id": None,             # set on finalize
        "content_item_id": None,       # set on finalize
        "draft_saved_at": None,        # time.time() of last successful draft save
        "preview_media_group_id": None,  # set when the preview media group is sent
        "preview_first_message_id": None,
        "pending_replace_slide": None,   # slide index awaiting a replacement image
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
# M29: durable draft persistence, resume, and reply-based re-register
# ---------------------------------------------------------------------------

def attach_persistence(session: Dict[str, Any], db: Any, storage: Any,
                       chat_id: Any) -> None:
    """Attach the best-effort persistence context (db/storage owner).

    Once attached, every meaningful step upserts the owner's durable draft
    so the carousel survives bot restarts. Persistence failures never
    break the interactive flow (logged and skipped).
    """
    session["_persistence"] = {"db": db, "storage": storage, "chat_id": chat_id}


def _deck_to_dict(deck: Optional[CarouselDeck]) -> Optional[Dict[str, Any]]:
    if deck is None:
        return None
    from dataclasses import asdict
    return asdict(deck)


def _dict_to_deck(d: Dict[str, Any]) -> CarouselDeck:
    slides = [CarouselSlide(**s) for s in d.get("slides", [])]
    return CarouselDeck(
        title=d.get("title", ""),
        template=d.get("template", "psychological_dark"),
        slides=slides,
        deck_footer=d.get("deck_footer", ""),
    )


def _draft_status(session: Dict[str, Any]) -> str:
    return "finalized" if session.get("custom_id") else "draft"


def _build_draft_dict(session: Dict[str, Any], uploaded: Dict[str, str],
                      history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The draft dict shape stored in carousel_drafts.draft (M29)."""
    deck = session.get("deck")
    return {
        "mode": session.get("mode"),
        "template": session.get("template", "psychological_dark"),
        "topic": session.get("topic", ""),
        "slide_count": session.get("slide_count", DEFAULT_SLIDE_COUNT),
        "pending_image_layout": session.get("pending_image_layout"),
        "images_keys": [uploaded[l] for l in session.get("images", [])
                        if uploaded.get(l)],
        "texts": [dict(t) for t in session.get("texts", [])],
        "deck": _deck_to_dict(deck) if deck is not None else None,
        "media_keys": session.get("media_keys", []),
        "history": history,
        "custom_id": session.get("custom_id"),
        "content_item_id": session.get("content_item_id"),
        "status": _draft_status(session),
        "title": session.get("deck_title") or (deck.title if deck else ""),
    }


def save_carousel_draft(session: Dict[str, Any], db: Any, storage: Any,
                        chat_id: Any) -> Dict[str, Any]:
    """Build the draft dict from the session, upload any NEW source images
    to storage, and upsert the owner's draft row. Returns the draft dict.

    The draft is what makes a carousel resumable after a bot restart:
    ordered image storage keys, ordered slide texts, the deck dict (with
    per-slide layout/zone/size/style/template), rendered media keys once
    finalized, and the history of finalized versions.
    """
    # Upload source images not yet in storage (tracked per local path)
    uploaded: Dict[str, str] = session.setdefault("uploaded_image_keys", {})
    for local in session.get("images", []):
        if local in uploaded or not os.path.exists(local):
            continue
        key = f"carousel/drafts/{chat_id}/{os.path.basename(local)}"
        ext = os.path.splitext(local)[1].lower()
        content_type = "image/png" if ext == ".png" else "image/jpeg"
        storage.upload_file(local, key, content_type=content_type)
        uploaded[local] = key

    # Keep the server-side history intact when this session knows none
    # (a brand-new session must not wipe earlier finalized versions)
    history = session.get("draft_history", [])
    if not history:
        try:
            existing = db.get_carousel_draft(chat_id) or {}
            history = (existing.get("draft") or {}).get("history", []) or []
        except Exception:
            history = []
        session["draft_history"] = history

    draft = _build_draft_dict(session, uploaded, history)
    db.upsert_carousel_draft(chat_id, draft)
    session["draft_saved_at"] = time.time()
    return draft


def _maybe_persist(session: Dict[str, Any]) -> None:
    """Best-effort draft upsert after a meaningful step. Persistence
    problems are logged and never interrupt the interactive flow."""
    p = session.get("_persistence")
    if not p:
        return
    try:
        save_carousel_draft(session, p["db"], p["storage"], p["chat_id"])
    except Exception as exc:
        logger.warning("Carousel draft persist failed (continuing without it): %s", exc)


def draft_expired(updated_at: Optional[str]) -> bool:
    """True when a draft's updated_at is older than DRAFT_MAX_AGE_DAYS
    (or unparsable)."""
    if not updated_at:
        return True
    try:
        updated = datetime.datetime.fromisoformat(updated_at)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=datetime.timezone.utc)
        age = datetime.datetime.now(datetime.timezone.utc) - updated
        return age.days >= DRAFT_MAX_AGE_DAYS
    except (TypeError, ValueError):
        return True


def _find_draft_snapshot(record: Dict[str, Any], custom_id: str) -> Dict[str, Any]:
    """Find the draft snapshot for a custom_id: the current record or one
    of the history entries (newest first)."""
    if record.get("custom_id") == custom_id:
        d = dict(record.get("draft") or {})
        d["custom_id"] = record.get("custom_id")
        d["content_item_id"] = (record.get("draft") or {}).get("content_item_id")
        return d
    for entry in (record.get("draft") or {}).get("history", []) or []:
        if entry.get("custom_id") == custom_id:
            return dict(entry.get("draft") or {})
    return {}


def resume_carousel_draft(
    chat_data: Dict[str, Any],
    db: Any,
    storage: Any,
    chat_id: Any,
    custom_id: Optional[str] = None,
    renderer: Optional["CarouselDeckRenderer"] = None,
) -> Tuple[str, Optional[str]]:
    """Restore a saved carousel draft into a fresh session in chat_data.

    - custom_id=None: resume the owner's latest non-expired draft.
    - custom_id given: resume that specific version (current or history).
    Returns (confirmation_fa, error_fa) — error_fa is None on success.

    Restore rules:
    - images are downloaded from storage keys into a fresh work dir
    - slide texts / deck fields (template, layout, zone, size, style)
      are restored from the draft
    - PREVIEW if a deck exists (re-rendered locally — the renderer is
      deterministic); otherwise COLLECT_* so the operator continues
    """
    active = get_session(chat_data)
    if active:
        return "", DRAFT_ACTIVE_SESSION_FA

    try:
        record = db.get_carousel_draft(chat_id)
    except Exception as exc:
        logger.exception("Draft read failed")
        return "", f"❌ خواندن پیش‌نمایش ممکن نشد: {type(exc).__name__}"
    if not record:
        return "", DRAFT_NONE_FA
    if draft_expired(record.get("updated_at")):
        return "", DRAFT_EXPIRED_FA

    if custom_id:
        snapshot = _find_draft_snapshot(record, custom_id)
        if not snapshot:
            return "", DRAFT_NOT_FOUND_ID_FA.format(cid=custom_id)
        draft = snapshot
    else:
        draft = dict(record.get("draft") or {})
        draft["custom_id"] = record.get("custom_id")
        draft["content_item_id"] = (record.get("draft") or {}).get("content_item_id")

    images_keys = draft.get("images_keys") or []
    session = new_session()
    session["mode"] = draft.get("mode")
    session["template"] = draft.get("template", "psychological_dark")
    session["topic"] = draft.get("topic", "")
    session["slide_count"] = draft.get("slide_count", DEFAULT_SLIDE_COUNT)
    session["pending_image_layout"] = draft.get("pending_image_layout")
    session["texts"] = [dict(t) for t in draft.get("texts", [])]
    session["custom_id"] = draft.get("custom_id")
    session["content_item_id"] = draft.get("content_item_id")
    session["draft_history"] = (record.get("draft") or {}).get("history", []) or []

    # Restore source images from storage into the fresh work dir
    session["images"] = []
    for key in images_keys:
        local = os.path.join(session["work_dir"], os.path.basename(key))
        try:
            storage.download_file(key, local)
        except Exception as exc:
            logger.exception("Draft image restore failed for %s", key)
            cleanup(session)
            return "", f"❌ بازیابی عکس‌ها از ذخیره‌گاه ممکن نشد: {type(exc).__name__}"
        session["images"].append(local)
        session["uploaded_image_keys"][local] = key

    deck_dict = draft.get("deck")
    if deck_dict:
        # Remap deck slide image paths to the freshly downloaded files
        # (basenames are preserved by the draft upload keys)
        for s in deck_dict.get("slides", []):
            if s.get("image_path"):
                s["image_path"] = os.path.join(
                    session["work_dir"], os.path.basename(s["image_path"]))
        deck = _dict_to_deck(deck_dict)
        try:
            from agents.carousel.deck_renderer import CarouselDeckRenderer
            renderer = renderer or CarouselDeckRenderer()
            out_dir = os.path.join(session["work_dir"], "slides")
            paths = renderer.render_deck(deck, out_dir)
        except Exception as exc:
            logger.exception("Draft deck re-render failed")
            cleanup(session)
            return "", f"❌ بازسازی پیش‌نمایش ممکن نشد: {type(exc).__name__}"
        session["deck"] = deck
        session["slide_paths"] = list(paths)
        session["deck_title"] = deck.title
        session["media_keys"] = draft.get("media_keys") or []
        session["_renderer"] = renderer
        session["state"] = PREVIEW
    else:
        # No deck yet: continue collecting from where the draft stopped
        mode = session["mode"]
        if mode in (None, ""):
            cleanup(session)
            return "", "❌ پیش‌نمایش ناقص است؛ دوباره از /carousel شروع کن."
        if not session["images"]:
            session["state"] = COLLECT_IMAGES
        elif mode == "text_overlay" and len(session["texts"]) < len(session["images"]):
            session["state"] = COLLECT_TEXTS
        else:
            # All inputs present (or image_deck/ai_planned awaiting topic
            # completion): let the operator finish and rebuild via /done
            session["state"] = COLLECT_TOPIC if mode != "text_overlay" else COLLECT_TEXTS

    attach_persistence(session, db, storage, chat_id)
    chat_data["carousel_session"] = session

    if session["state"] == PREVIEW:
        what = f"✅ پیش‌نمایش بازیابی شد.\nعکس‌ها: {len(session['images'])} | " \
               f"اسلایدها: {len(session['slide_paths'])} | قالب: {session['template']}"
    else:
        stage = {COLLECT_IMAGES: "جمع‌آوری عکس",
                 COLLECT_TEXTS: "جمع‌آوری متن",
                 COLLECT_TOPIC: "دریافت موضوع"}.get(session["state"], "ادامه")
        what = (f"✅ پیش‌نمایش بازیابی شد ({stage}).\nحالت: {session['mode']} | "
                f"عکس‌ها: {len(session['images'])} | متن‌ها: {len(session['texts'])}")
    if custom_id:
        what += f"\nشناسه: {custom_id}"
    return what, None


def list_carousels_fa(db: Any, chat_id: Any) -> str:
    """Persian list of the owner's resumable carousels (current draft +
    recent finalized versions)."""
    record = db.get_carousel_draft(chat_id)
    if not record:
        return DRAFT_NONE_FA
    draft = record.get("draft") or {}
    slide_count = len((draft.get("deck") or {}).get("slides", [])) or len(draft.get("images_keys", []) or [])
    lines = ["📚 کاروسل‌های ذخیره‌شده شما:"]
    status_fa = {"draft": "در حال ساخت", "finalized": "ذخیره‌شده"}.get(
        record.get("status") or "draft", record.get("status") or "draft")
    lines.append(
        f"• {record.get('title') or '—'}\n"
        f"  وضعیت: {status_fa} | اسلایدها: {slide_count} | "
        f"به‌روزرسانی: {record.get('updated_at', '—')}"
    )
    if record.get("custom_id"):
        lines.append(f"  شناسه: {record['custom_id']}")
    for entry in (draft.get("history", []) or [])[-5:][::-1]:
        title = entry.get("title") or "—"
        lines.append(
            f"• {title} | {entry.get('custom_id', '—')} | "
            f"{entry.get('status', 'finalized')} | {entry.get('updated_at', '—')}"
        )
    lines.append("\n/carousel_resume — ادامه‌ی آخرین پیش‌نمایش\n"
                 "/carousel_resume <custom_id> — بازگشت به یک نسخه‌ی خاص")
    return "\n".join(lines)


def replace_slide_image(session: Dict[str, Any], index: int,
                        local_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Replace slide `index`'s source image with local_path and re-render
    that slide in place (M29 reply-based replace). Returns
    (error_message, updated_path)."""
    deck: Optional[CarouselDeck] = session.get("deck")
    if not deck:
        return "هنوز کاروسلی ساخته نشده است.", None
    total = len(deck.slides)
    if not (1 <= index <= total):
        return f"❌ شماره اسلاید نامعتبر است (۱ تا {total}).", None
    slide = deck.slides[index - 1]
    if not slide.image_path:
        return "❌ این اسلاید تصویر ندارد.", None
    if not local_path or not os.path.exists(local_path):
        return "❌ عکس جایگزین دریافت نشد.", None

    ext = os.path.splitext(local_path)[1].lower()
    if ext not in IMAGE_EXTS:
        ext = ".jpg"
    new_path = os.path.join(session["work_dir"], f"replace_{index:02d}{ext}")
    try:
        shutil.copyfile(local_path, new_path)
    except OSError as exc:
        logger.error("Slide image replace failed: %s", exc)
        return "❌ جایگزینی عکس ممکن نشد؛ دوباره بفرست.", None

    old_path = slide.image_path
    slide.image_path = new_path
    # Keep the draft image list consistent (same position)
    images = session.get("images", [])
    if old_path in images:
        images[images.index(old_path)] = new_path

    path = session["slide_paths"][index - 1]
    renderer = session.get("_renderer")
    try:
        if renderer is not None and hasattr(renderer, "slide_renderer"):
            renderer.slide_renderer.render(slide, path)
        else:
            from agents.carousel.slide_renderer import CarouselSlideRenderer
            CarouselSlideRenderer().render(slide, path)
    except Exception as exc:
        slide.image_path = old_path  # roll back on render failure
        logger.exception("Slide re-render after replace failed")
        return f"❌ رندر مجدد اسلاید ناکام بود: {type(exc).__name__}", None
    _maybe_persist(session)
    return None, path


def clear_persistent_draft(db: Any, chat_id: Any) -> bool:
    """Best-effort deletion of the owner's durable draft (M29 cancel).
    Returns True when deleted (or nothing to delete); False on failure."""
    try:
        db.delete_carousel_draft(chat_id)
        return True
    except Exception as exc:
        logger.warning("Draft delete failed (continuing): %s", exc)
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
        _maybe_persist(session)
        return TOPIC_INSTRUCTIONS_FA
    session["state"] = COLLECT_IMAGES
    _maybe_persist(session)
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
    _maybe_persist(session)
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
    """Parse 'title' or 'title | body'.

    Splits on the FIRST '|' that is OUTSIDE inline markup brackets (M27A),
    so M26 markup like "[کلمه|color=#B89B65]" keeps its internal pipe. The
    body keeps everything after that first split (including further pipes),
    matching the previous plain behavior.
    """
    parts = split_pipes_outside_brackets(raw or "")
    title = parts[0].strip()
    if not title:
        # No usable title before '|': treat the whole message as the title.
        return {"title": (raw or "").strip(), "body": ""}
    body = "|".join(parts[1:]).strip() if len(parts) > 1 else ""
    return {"title": title, "body": body}


def add_text(session: Dict[str, Any], raw: str) -> Dict[str, str]:
    """COLLECT_TEXTS: append one slide text (order preserved)."""
    entry = parse_slide_text(raw)
    session["texts"].append(entry)
    _maybe_persist(session)
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
    _maybe_persist(session)
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
        _maybe_persist(session)  # M29: preview built -> durable draft
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
            "title_zone": slide.title_zone,
            "body_zone": slide.body_zone,
            "text_style": slide.text_style,
            "text_scale": slide.text_scale,
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
    _maybe_persist(session)  # M29: edit applied -> durable draft
    return None, path


def edit_slide(
    session: Dict[str, Any],
    index: int,
    new_text: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Edit slide `index` (1-based).

    Accepted forms (M23/M25 extend title|body with option tokens; one
    token per command, mixing text + options is not supported):
    - "<title> | <body>" or "<title>" — replace title (and body)
    - "layout=split|full|contain|auto" — change the slide's image layout
    - "zone=<zone>" — set the caption text zone (English or Persian alias)
    - "title_zone=<zone>" / "body_zone=<zone>" — split placement (M25)
    - "style=gradient|blend" — caption style (M25)
    - "size=0.7..1.3" — manual text size scale (M25)

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

    if text.startswith("title_zone=") or text.startswith("body_zone="):
        attr = "title_zone" if text.startswith("title_zone=") else "body_zone"
        zone = normalize_zone_token(text.split("=", 1)[1])
        if zone is None:
            return (f"❌ نام {attr} نامعتبر است. گزینه‌ها: بالا | وسط | پایین | "
                    "چپ | راست و ترکیب‌ها (مثل پایین-راست)"), None
        if slide.slide_type not in _PHOTO_SLIDE_TYPES:
            return "❌ zone فقط برای اسلایدهای تصویری (کاور/تصویر) کاربرد دارد.", None
        old = getattr(slide, attr)
        setattr(slide, attr, zone)

        def _rollback_zone():
            setattr(slide, attr, old)

        return _revalidate_and_rerender(session, slide, index, _rollback_zone)

    if text.startswith("zone="):
        zone = normalize_zone_token(text[len("zone="):])
        if zone is None:
            return ("❌ نام zone نامعتبر است. گزینه‌ها: بالا | وسط | پایین | "
                    "چپ | راست و ترکیب‌ها (مثل پایین-راست)"), None
        if slide.slide_type not in _PHOTO_SLIDE_TYPES:
            return "❌ zone فقط برای اسلایدهای تصویری (کاور/تصویر) کاربرد دارد.", None
        old_zone = slide.text_zone
        slide.text_zone = zone

        def _rollback_zone():
            slide.text_zone = old_zone

        return _revalidate_and_rerender(session, slide, index, _rollback_zone)

    if text.startswith("style="):
        value = text[len("style="):].strip().lower()
        if value not in ("gradient", "blend"):
            return "❌ نام style نامعتبر است. گزینه‌ها: gradient | blend", None
        if slide.slide_type not in _PHOTO_SLIDE_TYPES:
            return "❌ style فقط برای اسلایدهای تصویری (کاور/تصویر) کاربرد دارد.", None
        old_style = slide.text_style
        slide.text_style = value

        def _rollback_style():
            slide.text_style = old_style

        return _revalidate_and_rerender(session, slide, index, _rollback_style)

    if text.startswith("size="):
        value = text[len("size="):].strip().translate(PERSIAN_DIGITS)
        try:
            scale = float(value)
        except ValueError:
            return "❌ مقدار size نامعتبر است (مثلاً 0.85).", None
        if not (0.7 <= scale <= 1.3):
            return "❌ size باید بین 0.7 تا 1.3 باشد.", None
        if slide.slide_type not in _PHOTO_SLIDE_TYPES:
            return "❌ size فقط برای اسلایدهای تصویری (کاور/تصویر) کاربرد دارد.", None
        old_scale = slide.text_scale
        slide.text_scale = scale

        def _rollback_scale():
            slide.text_scale = old_scale

        return _revalidate_and_rerender(session, slide, index, _rollback_scale)

    # Split title/body on the FIRST '|' OUTSIDE inline markup brackets
    # (M27A), so marked-up titles/bodies keep their internal pipes.
    parts = split_pipes_outside_brackets(text)
    title = parts[0].strip()
    if not title:
        return "❌ متن جدید اسلاید خالی است.", None
    body = "|".join(parts[1:]).strip() if len(parts) > 1 else None

    old_title, old_body = slide.title, slide.body
    slide.title = title
    if body and slide.slide_type in ("title_body", "image_text", "image_overlay"):
        slide.body = body

    def _rollback_text():
        slide.title, slide.body = old_title, old_body

    return _revalidate_and_rerender(session, slide, index, _rollback_text)


def _parse_slide_num(token: str) -> Tuple[Optional[int], Optional[str]]:
    """(number, error) for an optional trailing slide-number token."""
    num_text = (token or "").strip().translate(PERSIAN_DIGITS)
    if not num_text.isdigit():
        return None, "❌ شماره‌ی اسلاید نامعتبر است."
    return int(num_text), None


def apply_layout(
    session: Dict[str, Any],
    raw_text: str,
) -> str:
    """
    Handle /carousel_layout (M23 + M25). Forms:

    - "<layout> [slide_number]"
        layout: split | full | contain | auto (mapped to the image_layout
        values split_panel / full_bleed_caption / contain_caption / auto).
        Applied to image_text slides: one slide, or all non-cover image
        slides when omitted.
    - "zone <zone> [slide_number]"     — caption text zone (M25)
    - "style gradient|blend [number]"  — caption style (M25)
    - "size 0.7..1.3 [number]"         — text size scale (M25)

    zone/style/size apply to ALL photo slides (cover + image_text +
    image_overlay), or one slide when a number is given. The plain layout
    form is valid during a COLLECT state (stored, applied to all image
    slides at build time); zone/style/size require the PREVIEW state.
    Re-renders the affected slides. Returns the Persian message.
    """
    state = session.get("state")
    if state not in (COLLECT_IMAGES, COLLECT_TEXTS, COLLECT_TOPIC, PREVIEW):
        return "این دستور الان کاربرد ندارد. اول کاروسل ساخته شود."

    tokens = (raw_text or "").split()
    if not tokens:
        return ("فرمت: /carousel_layout <split|full|contain|auto> [شماره] | "
                "zone <zone> | style gradient|blend | size 0.7..1.3")

    first = tokens[0].strip().lower()
    deck: Optional[CarouselDeck] = session.get("deck")

    # The plain layout form has no value token: "/carousel_layout full 3"
    # -> layout=full, slide 3. The zone/style/size forms have a value:
    # "/carousel_layout zone bottom_right 3" -> zone, value, slide 3.
    num_token_index = 1
    if first in LAYOUT_ALIASES:
        attr, value, value_name = "image_layout", LAYOUT_ALIASES[first], first
        targets_types = ("image_text",)
        label = "چیدمان"
    elif first == "zone":
        if len(tokens) < 2:
            return "فرمت: /carousel_layout zone <zone> [شماره]"
        value = normalize_zone_token(tokens[1])
        if value is None:
            return ("❌ نام zone نامعتبر است. گزینه‌ها: بالا | وسط | پایین | "
                    "چپ | راست و ترکیب‌ها (مثل پایین-راست)")
        if deck is None:
            return "این تنظیم بعد از ساخت (پیش‌نمایش) اعمال می‌شود."
        attr, value_name, targets_types = "text_zone", tokens[1].strip(), _PHOTO_SLIDE_TYPES
        label = "zone"
        num_token_index = 2
    elif first == "style":
        if len(tokens) < 2:
            return "فرمت: /carousel_layout style gradient|blend [شماره]"
        value = tokens[1].strip().lower()
        if value not in ("gradient", "blend"):
            return "❌ نام style نامعتبر است. گزینه‌ها: gradient | blend"
        if deck is None:
            return "این تنظیم بعد از ساخت (پیش‌نمایش) اعمال می‌شود."
        attr, value_name, targets_types = "text_style", value, _PHOTO_SLIDE_TYPES
        label = "style"
        num_token_index = 2
    elif first == "size":
        if len(tokens) < 2:
            return "فرمت: /carousel_layout size 0.7..1.3 [شماره]"
        try:
            value = float(tokens[1].strip().translate(PERSIAN_DIGITS))
        except ValueError:
            return "❌ مقدار size نامعتبر است (مثلاً 0.85)."
        if not (0.7 <= value <= 1.3):
            return "❌ size باید بین 0.7 تا 1.3 باشد."
        if deck is None:
            return "این تنظیم بعد از ساخت (پیش‌نمایش) اعمال می‌شود."
        attr, value_name, targets_types = "text_scale", value, _PHOTO_SLIDE_TYPES
        label = "size"
        num_token_index = 2
    else:
        return ("❌ نام layout نامعتبر است. گزینه‌ها: split | full | contain | auto | "
                "zone | style | size")

    slide_num = None
    if len(tokens) > num_token_index:
        slide_num, err = _parse_slide_num(tokens[num_token_index])
        if err:
            return err

    if deck is None:
        # COLLECT state: only the plain layout form is supported — remember
        # it for build time (applied to all image slides).
        session["pending_image_layout"] = value
        _maybe_persist(session)  # M29: pending layout survives restarts
        if slide_num is not None:
            return (
                "شماره‌ی اسلاید فقط بعد از ساخت (پیش‌نمایش) معنا دارد؛ "
                f"چیدمان «{value_name}» برای همه‌ی اسلایدهای تصویری ذخیره شد."
            )
        return (
            f"✅ چیدمان «{value_name}» ذخیره شد؛ بعد از ساخت روی همه‌ی "
            "اسلایدهای تصویری اعمال می‌شود."
        )

    if slide_num is not None:
        if not (1 <= slide_num <= len(deck.slides)):
            return f"❌ شماره اسلاید نامعتبر است (۱ تا {len(deck.slides)})."
        slide = deck.slides[slide_num - 1]
        if slide.slide_type not in targets_types:
            return f"❌ {label} فقط برای اسلایدهای تصویری کاربرد دارد."
        targets = [slide_num]
    else:
        targets = [i for i, s in enumerate(deck.slides, 1)
                   if s.slide_type in targets_types]
        if not targets:
            return "اسلاید تصویری برای اعمال پیدا نشد."

    renderer = session.get("_renderer")
    failed = []
    for i in targets:
        s = deck.slides[i - 1]
        setattr(s, attr, value)
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

    _maybe_persist(session)  # M29: layout/zone/size change -> durable draft
    if slide_num is not None:
        return f"✅ {label} «{value_name}» روی اسلاید {slide_num} اعمال شد."
    return f"✅ {label} «{value_name}» روی {len(targets)} اسلاید تصویری اعمال شد."


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
    _maybe_persist(session)  # M29: theme change -> durable draft
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
        # M29: mark the durable draft as finalized and remember this
        # version in its history so /carousel_resume <custom_id> can load
        # it back into an editable session later.
        session["custom_id"] = cid
        session["content_item_id"] = payload.get("id")
        session["media_keys"] = list(keys)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        history = session.get("draft_history", []) or []
        history.append({
            "custom_id": cid,
            "title": session.get("deck_title") or (deck.title if deck else ""),
            "status": "finalized",
            "updated_at": now_iso,
            "draft": _build_draft_dict(
                session, session.get("uploaded_image_keys", {}), history),
        })
        session["draft_history"] = history
        _maybe_persist(session)
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
