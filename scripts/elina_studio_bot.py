import os
import re
import sys
import logging
import asyncio
import datetime
import json
from pathlib import Path
from typing import Optional, Dict, List
from functools import wraps

# Force unbuffered output so logs appear instantly in Render
sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.studio.approval import ApprovalManager
from agents.editing.persian_edit_interpreter import PersianEditInterpreter, format_plan_preview_fa
from agents.studio.bundle_ids import normalize_bundle_custom_id
import agents.studio.carousel_session as carousel_session

logging.basicConfig(
    level=logging.INFO,
    format="[STUDIO] %(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from agents.security.log_redaction import install_secret_redaction
install_secret_redaction()

logger = logging.getLogger(__name__)

OWNER_CHAT_ID = str(os.environ.get("OWNER_CHAT_ID", "")).strip()
STUDIO_BOT_TOKEN = str(os.environ.get("STUDIO_BOT_TOKEN", "")).strip()


def record_update():
    try:
        path = "/tmp/elina_studio_last_update.json"
        with open(path, "w") as f:
            json.dump({"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}, f)
    except Exception as e:
        logger.error(f"Failed to record update timestamp: {e}")


def record_update_decorator(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        record_update()
        return await func(update, context, *args, **kwargs)
    return wrapper


def is_owner(update: Update) -> bool:
    return str(update.effective_chat.id) == OWNER_CHAT_ID


def actor_name(update: Update) -> str:
    user = update.effective_user
    return user.username or user.first_name or "unknown"


def parse_render_command(message_text: str) -> Dict:
    """
    Parse /render command with extended syntax.

    Extended syntax (multi-line):
        /render ELN-XXX
        hook=تو تنبل نیستی
        voice=voices/voice_a.wav
        music=music/ambient_deep.mp3
        clip1=raw/shot1.mp4:0-3
        clip2=raw/shot2.mp4:1.2-4
        clip3=raw/shot3.mp4:0-

    Legacy syntax (single line):
        /render ELN-XXX hook text here

    Returns:
        {
            "custom_id": str,
            "hook": Optional[str],
            "voice_key": Optional[str],
            "music_key": Optional[str],
            "segments": List[dict],  # [{"key": str, "start_sec": float, "end_sec": Optional[float]}]
            "legacy_hook_text": Optional[str],
        }
    Raises ValueError on malformed input.
    """
    text = message_text.strip()
    if text.startswith("/render"):
        text = text[len("/render"):].strip()

    lines = text.split("\n")
    if not lines or not lines[0].strip():
        raise ValueError("Custom ID required")

    first_line = lines[0].strip()
    tokens = first_line.split()

    custom_id = tokens[0] if tokens else ""
    if not re.match(r"^ELN-[A-Za-z0-9_-]+$", custom_id):
        raise ValueError(f"Invalid custom_id format: {custom_id}")

    result = {
        "custom_id": custom_id,
        "hook": None,
        "voice_key": None,
        "music_key": None,
        "segments": [],
        "legacy_hook_text": None,
    }

    if len(tokens) > 1:
        result["legacy_hook_text"] = " ".join(tokens[1:])

    remaining_lines = lines[1:]
    for line in remaining_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if "=" not in stripped:
            continue

        key_eq, _, value = stripped.partition("=")
        key = key_eq.strip().lower()
        val = value.strip()

        if key == "hook":
            result["hook"] = val
        elif key == "voice":
            result["voice_key"] = val
        elif key == "music":
            result["music_key"] = val
        elif key.startswith("clip") and key[4:].isdigit():
            segment = _parse_clip_spec(key, val)
            if segment:
                result["segments"].append(segment)

    return result


def _parse_clip_spec(key: str, spec: str) -> Optional[Dict]:
    """
    Parse clip spec: STORAGE_KEY[:START-END]
    """
    parts = spec.split(":", 1)
    storage_key = parts[0].strip()
    if not storage_key:
        raise ValueError(f"{key}: empty storage key")

    segment = {"key": storage_key, "start_sec": 0.0, "end_sec": None}

    if len(parts) == 2:
        trim_part = parts[1].strip()
        if trim_part:
            import re
            match = re.match(r'^(-?[\d.]+)?-(-?[\d.]+)?$', trim_part)
            if not match:
                raise ValueError(f"{key}: invalid time format: {trim_part}")

            start_str = match.group(1)
            end_str = match.group(2)

            if start_str is not None and start_str != '':
                start = float(start_str)
                if start < 0:
                    raise ValueError(f"{key}: negative start_sec not allowed: {start}")
                segment["start_sec"] = start

            if end_str is not None and end_str != '':
                end = float(end_str)
                if segment["start_sec"] >= end:
                    raise ValueError(f"{key}: end_sec must be greater than start_sec")
                segment["end_sec"] = end

    return segment


@record_update_decorator
async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id == OWNER_CHAT_ID:
        await update.message.reply_text(f"✅ شما مالک هستید.\nآیدی شما: {chat_id}")
    else:
        await update.message.reply_text(f"❌ آیدی شما: {chat_id}\nتنظیم شده در سرور: {OWNER_CHAT_ID or 'NOT SET'}")


@record_update_decorator
async def cmd_start_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است. /whoami را بزنید.")
        return
    text = (
        "راهنمای Elina Studio Bot\n\n"
        "۱) ارسال فایل به استودیو\n"
        "- ویدیو، عکس، صدا یا فایل نهایی/منتخب را همین‌جا بفرست.\n"
        "- ربات آن را ذخیره می‌کند و یک شناسه ELN-RAW می‌دهد.\n\n"
        "۲) بررسی محتوا\n"
        "/pending\n"
        "نمایش محتواهای منتظر بررسی\n\n"
        "۳) انتقال به بررسی رسمی\n"
        "/promote ELN-RAW-...\n"
        "محتوا را آماده بازبینی می‌کند\n\n"
        "۴) ادیت\n"
        "/edit ELN-RAW-... توضیح ادیت\n"
        "مثال:\n"
        "/edit ELN-RAW-123 اضافه کردن تایپوگرافی و هوک اول ویدیو\n\n"
        "۵) رندر\n"
        "/render ELN-RAW-... متن هوک\n"
        "مثال:\n"
        "/render ELN-RAW-123 تو تنبل نیستی\n\n"
        "۶) تأیید و زمان‌بندی\n"
        "/approve ELN-... prime_evening\n"
        "اسلات‌ها:\n"
        "prime_evening\n"
        "afternoon\n"
        "morning\n"
        "night\n\n"
        "۷) رد محتوا\n"
        "/reject ELN-... دلیل\n\n"
        "۸) آیدی من\n"
        "/whoami\n"
        "برای بررسی OWNER_CHAT_ID\n\n"
        "۹) ساخت ویدیوی چندشاتی\n\n"
        "ابتدا تمام شات‌ها را جداگانه به همین ربات بفرست و شناسه هر کدام را نگه دار.\n\n"
        "سپس آن‌ها را به ترتیب با دستور زیر در یک بسته قرار بده:\n\n"
        "/bundle نام-پروژه ID1 ID2 ID3 ID4 ID5\n\n"
        "مثال:\n\n"
        "/bundle shot-zero ELN-RAW-001 ELN-RAW-002 ELN-RAW-003\n\n"
        "ربات یک شناسه ELN-BUNDLE به تو می‌دهد. ادیت، کات و رندر نهایی روی همان شناسه انجام می‌شود.\n\n"
        "۱۰) برنامه‌ریزی ادیت با متن فارسی\n"
        "/plan ELN-BUNDLE-...\n"
        "حالت برنامه‌ریزی را فعال می‌کند\n\n"
        "بعد از آن, برنامه را به فارسی بنویس:\n"
        "- شات اول از صفر تا ۲.۸\n"
        "- شات دوم از ۱.۲ تا ۳.۸\n"
        "- صدای اصلی قطع شود\n"
        "- هوک: ...\n\n"
        "/plan_ok\n"
        "تأیید و شروع رندر واقعی\n\n"
        "/plan_cancel\n"
        "خروج از حالت برنامه‌ریزی\n\n"
        "۱۱) ساخت کاروسل\n"
        "/carousel — شروع ساخت کاروسل (عکس+متن / عکس+موضوع / فقط موضوع)\n"
        "/carousel_list — نمایش کاروسل‌های ذخیره‌شده\n"
        "/carousel_resume [custom_id] — ادامه‌ی یک پیش‌نمایش ذخیره‌شده\n"
        "Reply به یک عکس/متن قبلی + «ثبت» — ثبت دوباره‌ی همان عکس/متن\n"
        "Reply به یک اسلایدِ پیش‌نمایش + «جایگزین» — تعویض تصویر همان اسلاید\n"
        "پیش‌نمایش‌ها به‌صورت خودکار ذخیره می‌شوند و تا ۶ ساعت (جلسه) / ۳۰ روز (پیش‌نمایش) ماندگارند.\n\n"
        "نکته:\n"
        "هیچ محتوایی بدون تأیید و زمان‌بندی شما منتشر نمی‌شود."
    )
    await update.message.reply_text(text)


@record_update_decorator
async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    items = ApprovalManager().get_pending_items()
    if not items:
        await update.message.reply_text("صف خالی است.")
        return
    lines = [f"- {i['custom_id']} | {i['content_type']} | {i['status']}" for i in items]
    await update.message.reply_text("\n".join(lines))


@record_update_decorator
async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if not context.args:
        await update.message.reply_text("استفاده: /promote ELN-RAW-...")
        return
    result = ApprovalManager().promote_to_review(context.args[0], actor_name(update))
    await update.message.reply_text(f"✅ {result.get('new_status', result.get('error'))}")


@record_update_decorator
async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /approve ELN-... prime_evening")
        return
    result = ApprovalManager().approve_and_schedule(context.args[0], context.args[1], actor_name(update))
    if result.get("ok"):
        await update.message.reply_text(f"✅ تأیید شد\nزمان: {result.get('scheduled_for')}")
    else:
        await update.message.reply_text(f"❌ {result.get('error')}")


@record_update_decorator
async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /reject ELN-... دلیل")
        return
    result = ApprovalManager().reject_item(context.args[0], " ".join(context.args[1:]), actor_name(update))
    await update.message.reply_text("🚫 رد شد" if result.get("ok") else f"❌ {result.get('error')}")


@record_update_decorator
async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /edit ELN-... توضیح")
        return
    custom_id = context.args[0]
    task = " ".join(context.args[1:])
    result = ApprovalManager().mark_needs_edit(custom_id, task, actor_name(update))

    if result.get("ok"):
        response_text = (
            f"✏️ وضعیت محتوای {custom_id} به «نیازمند ادیت» تغییر یافت.\n"
            f"توضیحات ادیت ثبت شد: {task}\n\n"
            f"راهنما: برای نوشتن برنامه ادیت و رندر واقعی، دستور زیر را ارسال کنید:\n"
            f"/plan {custom_id}"
        )
        await update.message.reply_text(response_text)
    else:
        await update.message.reply_text(f"❌ {result.get('error')}")


@record_update_decorator
async def cmd_editdone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if not context.args:
        await update.message.reply_text("استفاده: /editdone ELN-...")
        return
    result = ApprovalManager().mark_edit_done(context.args[0], actor_name(update))
    await update.message.reply_text(f"✅ ادیت تمام شد: {result['custom_id']}" if result["ok"] else f"❌ {result['error']}")


@record_update_decorator
async def cmd_render(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    text = update.message.text or ""
    actor = actor_name(update)

    try:
        parsed = parse_render_command(text)
    except ValueError as e:
        await update.message.reply_text(f"❌ ورودی نامعتبر:\n{e}")
        return

    custom_id = parsed["custom_id"]
    hook_text = parsed.get("hook") or parsed.get("legacy_hook_text")
    voice_key = parsed.get("voice_key")
    music_key = parsed.get("music_key")
    segments = parsed.get("segments") or None

    msg = await update.message.reply_text(f"⏳ در حال رندر {custom_id}...")

    def run():
        from agents.editing.orchestrator import EditOrchestrator
        return EditOrchestrator().render_content(
            custom_id=custom_id,
            hook_text=hook_text,
            actor=actor,
            video_segments=segments,
            voice_key=voice_key,
            music_key=music_key,
        )

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run)
        if result.get("ok"):
            await msg.edit_text(f"✅ رندر تمام شد.\nخروجی: {result.get('output_key')}")
        else:
            await msg.edit_text(f"❌ رندر ناموفق:\n{result.get('error')}")
    except Exception as exc:
        logger.exception("Render failed")
        await msg.edit_text(f"❌ خطای سیستمی: {exc}")


@record_update_decorator
async def cmd_bundle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return

    if not context.args or len(context.args) < 3:
        usage = (
            "❌ دستور نامعتبر است.\n"
            "راهنمای استفاده:\n"
            "/bundle نام-پروژه ID1 ID2 [ID3 ...]\n"
            "مثال:\n"
            "/bundle shot-zero ELN-RAW-001 ELN-RAW-002"
        )
        await update.message.reply_text(usage)
        return

    bundle_name = context.args[0]
    source_ids = context.args[1:]

    try:
        from agents.studio.bundle_manager import VideoBundleManager
        manager = VideoBundleManager()
        result = manager.create_bundle(
            bundle_name=bundle_name,
            source_custom_ids=source_ids,
            actor=actor_name(update)
        )

        if result.get("ok"):
            success_text = (
                "✅ بسته ویدیویی ساخته شد.\n"
                f"نام: {result['bundle_name']}\n"
                f"شناسه: {result['custom_id']}\n"
                f"تعداد شات‌ها: {result['clip_count']}\n"
                f"وضعیت: NEEDS_EDIT\n\n"
                "مرحله بعد:\n"
                "برای مشاهده یا ادیت این بسته از شناسه جدید استفاده کن."
            )
            await update.message.reply_text(success_text)
        else:
            await update.message.reply_text(
                f"❌ بسته ساخته نشد:\n{result.get('error')}"
            )
    except Exception as e:
        logger.exception("Bundle creation command failed")
        await update.message.reply_text(
            f"❌ خطای سیستم در ساخت بسته:\n{type(e).__name__}: {e}"
        )


@record_update_decorator
async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return

    if not context.args:
        await update.message.reply_text("استفاده: /plan ELN-BUNDLE-...")
        return

    target_id = normalize_bundle_custom_id(context.args[0])
    if context.chat_data is None:
        context.chat_data = {}
    context.chat_data["plan_mode"] = True
    context.chat_data["plan_target_id"] = target_id

    reply_text = (
        "📝 حالت برنامه‌ریزی ادیت فعال شد.\n"
        f"شناسه هدف: {target_id}\n"
        "حالا برنامه ادیت را به فارسی برای من بنویس.\n\n"
        "مثال:\n"
        "شات اول از صفر تا ۲.۸\n"
        "شات دوم از ۱.۲ تا ۳.۸\n"
        "صدای اصلی همه شات‌ها قطع شود\n"
        "در ثانیه ۰.۵ صدای چرخیدن کلید اضافه شود\n"
        "هوک: تو تنبل نیستی"
    )
    await update.message.reply_text(reply_text)


@record_update_decorator
async def cmd_plan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return

    if context.chat_data is not None:
        context.chat_data["plan_mode"] = False
        context.chat_data["plan_target_id"] = None
        context.chat_data["plan_preview"] = None

    await update.message.reply_text("❌ حالت برنامه‌ریزی ادیت لغو شد.")


@record_update_decorator
async def cmd_plan_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    plan = context.chat_data.get("plan_preview") if context.chat_data else None
    target_id = context.chat_data.get("plan_target_id") if context.chat_data else None

    if not plan or not target_id:
        await update.message.reply_text(
            "هیچ برنامه‌ای وجود ندارد. ابتدا /plan بزنید."
        )
        return

    errors = plan.validate()
    if errors:
        err_lines = [f"- {err}" for err in errors]
        await update.message.reply_text(
            "❌ خطا: برنامه ادیت ذخیره شده دیگر معتبر نیست:\n\n"
            + "\n".join(err_lines)
        )
        return

    target_id = normalize_bundle_custom_id(target_id)

    try:
        from agents.rendering.job_manager import RenderJobManager

        plan_dict = {
            "target_id": target_id,
            "mute_original": plan.mute_original_audio,
            "shots": [{
                "index": s.shot_index,
                "start": s.start_sec,
                "end": s.end_sec,
                "remove": s.remove,
            } for s in plan.shots],
            "sfx": [{
                "query": s.query_fa,
                "start": s.start_sec,
                "gain": s.gain_db,
                "fade_in": s.fade_in_sec,
                "fade_out": s.fade_out_sec,
            } for s in plan.sound_effects],
            "hook": plan.hook_text,
            "music": {
                "enabled": plan.music.enabled if plan.music else False,
                "query": plan.music.query_fa if plan.music else None,
                "gain_db": plan.music.gain_db if plan.music else -14,
                "explicit": plan.music.explicit if plan.music else False,
            },
        }

        mgr = RenderJobManager()

        # Idempotency / duplicate protection check
        try:
            res_existing = mgr.db.client.table("render_jobs").select("*").eq("content_id", target_id).in_("status", ["QUEUED", "IN_PROGRESS"]).execute()
            if res_existing.data:
                existing_job = res_existing.data[0]
                if existing_job.get("plan_data") == plan_dict:
                    await update.message.reply_text(
                        f"✅ رندر این برنامه قبلاً ثبت شده و در صف قرار گرفته است.\n"
                        f"شناسه کار: {existing_job.get('id')}\n"
                        f"وضعیت: در انتظار اجرا"
                    )
                    return
        except Exception as e:
            logger.error(f"Duplicate protection query failed: {e}")

        # Queue the new job (which will automatically supersede any older active jobs)
        job = mgr.queue_job(
            content_id=target_id,
            plan_data=plan_dict,
            owner_chat_id=str(OWNER_CHAT_ID),
        )

        context.chat_data.pop("plan_preview", None)
        context.chat_data.pop("plan_target_id", None)
        context.chat_data.pop("plan_mode", None)

        await update.message.reply_text(
            f"✅ رندر وارد صف شد.\n"
            f"شناسه کار: {job.get('id', 'ثبت شد')}\n"
            f"وضعیت: در انتظار اجرا\n\n"
            "سیستم هر ۵ دقیقه صف را بررسی می‌کند.\n"
            "وقتی رندر تمام شد، نتیجه برایت ارسال می‌شود."
        )
    except Exception as exc:
        logger.exception("Failed to queue render job")
        await update.message.reply_text(
            f"❌ خطا در ثبت رندر:\n{type(exc).__name__}: {str(exc)[:200]}"
        )


# ---------------------------------------------------------------------------
# M18D — Telegram Carousel Studio (owner-only conversational flow)
# All state-machine logic lives in agents/studio/carousel_session.py.
# ---------------------------------------------------------------------------

def _chat_data(context) -> Dict:
    if context.chat_data is None:
        context.chat_data = {}
    return context.chat_data


def _effective_chat_id(update) -> Optional[int]:
    """M29A: the active Telegram chat id (update.effective_chat.id).

    This is the ONLY source of carousel draft ownership. The OWNER_CHAT_ID
    env var is for permission checks only, and PTB's context.chat_id is
    the app-level conversation chat id (None here) — neither may be used
    for draft ownership.
    """
    chat = getattr(update, "effective_chat", None)
    if chat is None:
        return None
    return getattr(chat, "id", None)


def _get_carousel_session(context, update) -> Optional[Dict]:
    """Return the live (non-expired) carousel session, clearing an expired
    one in place. Never returns an expired session. Defensive against
    non-dict chat_data (pre-M18D mocks/tests) — treated as no session."""
    chat_data = _chat_data(context)
    session = carousel_session.get_session(chat_data)
    if session and carousel_session.session_expired(session):
        carousel_session.cleanup(session)
        if isinstance(chat_data, dict):
            chat_data["carousel_session"] = None
            return None
    if session:
        _ensure_persistence(update, session)
    return session


def _ensure_persistence(update, session: Dict) -> None:
    """M29/M29A: attach the durable-draft persistence context (best
    effort) so every meaningful step upserts the owner's draft, keyed by
    update.effective_chat.id. Failures (e.g. no Supabase credentials,
    unresolvable chat id) are logged and skipped — the interactive flow
    keeps working without durable drafts."""
    if not session or session.get("_persistence"):
        return
    try:
        from agents.db.supabase_client import ElinaDB
        from agents.storage.supabase_storage import ElinaStorage
        chat_id = _effective_chat_id(update)
        if chat_id is None:
            return
        carousel_session.attach_persistence(session, ElinaDB(), ElinaStorage(), chat_id)
    except Exception as exc:
        logger.warning("Carousel draft persistence unavailable: %s", exc)


def _draft_suffix(session: Dict, before_ts) -> str:
    """M29: '💾 saved' hint when the draft was upserted during this step."""
    saved_at = session.get("draft_saved_at")
    if saved_at is not None and saved_at != before_ts:
        return "\n" + carousel_session.DRAFT_SAVED_HINT_FA
    return ""


async def _send_carousel_preview(update: Update, session: Dict) -> None:
    """Send the rendered slides as an ordered media group (2-10 slides).

    M29: remembers the group's first message id / media group id so the
    reply-based «جایگزین» shortcut can map a replied slide to its index.
    """
    paths = session.get("slide_paths") or []
    media = []
    for p in paths:
        with open(p, "rb") as f:
            media.append(InputMediaPhoto(media=f))
    sent = await update.message.reply_media_group(media=media)
    session["preview_media_group_id"] = getattr(sent, "media_group_id", None)
    session["preview_first_message_id"] = getattr(sent, "message_id", None)


async def _run_carousel_build(update: Update, session: Dict) -> None:
    """Run planner + renderer (blocking) in an executor, then show preview
    or the Persian error message (session is already recovered on failure)."""
    msg = await update.message.reply_text("⏳ در حال ساخت کاروسل...")
    before = session.get("draft_saved_at")

    def run():
        return carousel_session.build_deck(session)

    try:
        loop = asyncio.get_running_loop()
        error = await loop.run_in_executor(None, run)
    except Exception as exc:
        logger.exception("Carousel build crashed")
        await msg.edit_text(f"❌ خطای سیستمی: {type(exc).__name__}: {str(exc)[:200]}")
        return
    if error:
        await msg.edit_text(error)
        return
    await msg.edit_text(
        carousel_session.build_preview_message(session) + _draft_suffix(session, before)
    )
    await _send_carousel_preview(update, session)


async def _download_message_image(message, dest_dir: str) -> Optional[str]:
    """Download a photo/document image message to dest_dir. Returns a local
    path or None."""
    file_obj = None
    ext = ".jpg"
    if message.photo:
        file_obj = await message.photo[-1].get_file()
        ext = ".jpg"
    elif message.document:
        file_obj = await message.document.get_file()
        if message.document.file_name:
            ext = Path(message.document.file_name).suffix or ".bin"
        else:
            ext = ".bin"
    if not file_obj:
        return None
    import tempfile
    fd, local_path = tempfile.mkstemp(suffix=ext, dir=dest_dir)
    os.close(fd)
    await file_obj.download_to_drive(local_path)
    return local_path


# ---------------------------------------------------------------------------
# M29: reply-based fast re-register (ثبت / جایگزین)
# ---------------------------------------------------------------------------

REPLY_ADD_WORDS = {"ثبت", "add"}
REPLY_REPLACE_WORDS = {"جایگزین", "replace"}


def _reply_word(message) -> str:
    """Normalized reply-shortcut word of a message ('' when none)."""
    text = (message.text or message.caption or "").strip()
    return text if text.lower() in REPLY_ADD_WORDS | REPLY_REPLACE_WORDS else ""


def _resolve_preview_slide_index(session: Dict, replied) -> Optional[int]:
    """Map a replied preview-slide message to its 1-based slide index.

    A media group is sent as a burst of consecutive message ids; we
    remember the group's first id, so index = replied.message_id -
    first_id + 1 (clamped to the deck size). Returns None when the
    replied message can't be mapped to a slide of the CURRENT preview
    (e.g. an older preview — message ids are not stored durably).
    """
    first_id = session.get("preview_first_message_id")
    group_id = session.get("preview_media_group_id")
    if not first_id:
        return None
    total = len(session.get("slide_paths") or [])
    in_group = (
        (group_id and getattr(replied, "media_group_id", None) == group_id)
        or getattr(replied, "message_id", None) == first_id
    )
    if not in_group:
        return None
    delta = (getattr(replied, "message_id", None) or first_id) - first_id
    index = delta + 1
    if 1 <= index <= total:
        return index
    return None


async def _reply_replace_slide(update: Update, session: Dict, message, replied) -> None:
    """«جایگزین» on a preview slide: replace that slide's source image —
    with the image in the same reply when provided, otherwise arm a
    pending replace and ask for the image."""
    if session["state"] != carousel_session.PREVIEW:
        await message.reply_text(carousel_session.REPLY_WRONG_STATE_FA)
        return
    index = _resolve_preview_slide_index(session, replied)
    if index is None:
        await message.reply_text(carousel_session.REPLY_REPLACE_UNKNOWN_SLIDE_FA)
        return
    if message.photo or message.document:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = await _download_message_image(message, tmpdir)
            if not local_path:
                await message.reply_text("❌ عکس جایگزین دریافت نشد؛ دوباره بفرست.")
                return
            before = session.get("draft_saved_at")
            error, path = carousel_session.replace_slide_image(session, index, local_path)
        if error:
            await message.reply_text(error)
        else:
            await message.reply_photo(
                open(path, "rb"),
                caption=carousel_session.SLIDE_REPLACED_FA.format(n=index)
                + _draft_suffix(session, before),
            )
        return
    session["pending_replace_slide"] = index
    await message.reply_text(carousel_session.REPLY_REPLACE_PENDING_FA.format(n=index))


async def _handle_carousel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 message) -> bool:
    """M29 reply shortcuts during an active carousel session. Returns True
    when the message was consumed (a reply to a message with a shortcut
    word), False to fall through to normal handling.

    - Reply «ثبت»/«add» to an image  -> re-add it (COLLECT_IMAGES)
    - Reply «ثبت»/«add» to a text    -> re-add the text (COLLECT_TEXTS)
    - Reply «جایگزین»/«replace» to a preview slide -> replace its image
    """
    word = _reply_word(message)
    if not word or not message.reply_to_message:
        return False
    session = _get_carousel_session(context, update)
    if not session:
        await message.reply_text("❌ جلسه کاروسل فعال نیست. اول /carousel را بزن.")
        return True

    if word.lower() in REPLY_REPLACE_WORDS:
        await _reply_replace_slide(update, session, message, message.reply_to_message)
        return True

    # «ثبت»/«add»: re-add the replied image or text
    if session["state"] not in (carousel_session.COLLECT_IMAGES,
                                carousel_session.COLLECT_TEXTS):
        await message.reply_text(carousel_session.REPLY_WRONG_STATE_FA)
        return True
    replied = message.reply_to_message
    before = session.get("draft_saved_at")
    if session["state"] == carousel_session.COLLECT_IMAGES:
        if not (replied.photo or replied.document):
            await message.reply_text(carousel_session.REPLY_NOT_RESOLVED_FA)
            return True
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = await _download_message_image(replied, tmpdir)
            if not local_path:
                await message.reply_text("❌ عکس مرجع دریافت نشد؛ دوباره بفرست.")
                return
            error = carousel_session.add_image(session, local_path)
        if error:
            await message.reply_text(error)
        else:
            n = len(session["images"])
            await message.reply_text(
                carousel_session.REPLY_IMAGE_READDED_FA.format(n=n)
                + _draft_suffix(session, before))
        return True
    # COLLECT_TEXTS: re-add the replied text (photo captions count)
    replied_text = (replied.text or replied.caption or "").strip()
    if not replied_text:
        await message.reply_text(carousel_session.REPLY_NOT_RESOLVED_FA)
        return True
    carousel_session.add_text(session, replied_text)
    n = len(session["texts"])
    await message.reply_text(
        carousel_session.REPLY_TEXT_READDED_FA.format(n=n)
        + _draft_suffix(session, before))
    return True


@record_update_decorator
async def cmd_carousel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    chat_data = _chat_data(context)
    try:
        reply = carousel_session.start_session(chat_data)
    except carousel_session.CarouselSessionActiveError as exc:
        await update.message.reply_text(exc.message_fa)
        return
    _ensure_persistence(update, chat_data.get("carousel_session") or {})
    await update.message.reply_text(reply)


@record_update_decorator
async def cmd_carousel_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    chat_data = _chat_data(context)
    session = chat_data.get("carousel_session")
    if session:
        # M29/M29A: clear the durable draft as well (best effort), keyed
        # by the active Telegram chat id
        draft_cleared = False
        persistence = session.get("_persistence")
        if persistence:
            try:
                owner_chat_id = carousel_session.normalize_owner_chat_id(
                    _effective_chat_id(update))
            except carousel_session.CarouselOwnerChatIdError:
                owner_chat_id = persistence.get("chat_id")
                logger.warning(
                    "Cannot resolve effective chat id for draft delete; "
                    "falling back to the attached chat id")
            draft_cleared = carousel_session.clear_persistent_draft(
                persistence["db"], owner_chat_id)
        carousel_session.cleanup(session)
        chat_data["carousel_session"] = None
        reply = "✅ جلسه کاروسل لغو و فایل‌های موقت پاک شد."
        if draft_cleared:
            reply += "\n" + carousel_session.DRAFT_DELETED_NOTE_FA
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text("جلسه کاروسلی فعال نیست.")


@record_update_decorator
async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    session = _get_carousel_session(context, update)
    if not session:
        await update.message.reply_text("جلسه کاروسلی فعال نیست. /carousel را بزن.")
        return
    state = session["state"]
    if state == carousel_session.COLLECT_IMAGES:
        await update.message.reply_text(carousel_session.finish_images(session))
        return
    if state == carousel_session.COLLECT_TEXTS:
        error = carousel_session.finish_texts(session)
        if error:
            await update.message.reply_text(error)
            return
        await _run_carousel_build(update, session)
        return
    await update.message.reply_text("این دستور در این مرحله کاربرد ندارد.")


@record_update_decorator
async def cmd_carousel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    session = _get_carousel_session(context, update)
    if not session or session["state"] != carousel_session.PREVIEW:
        await update.message.reply_text("اول کاروسل را بساز (پیش‌نمایش) تا بتوانی ویرایش کنی.")
        return

    raw = (update.message.text or "").strip()
    raw = re.sub(r"^/carousel_edit(@\S+)?\s*", "", raw)
    index_part, sep, new_text = raw.partition("|")
    index_str = index_part.strip().translate(carousel_session.PERSIAN_DIGITS)
    if sep:
        new_text = new_text.strip()
    else:
        # no '|' -> the whole remainder is the new title
        index_str, _, whole = raw.partition(" ")
        index_str = index_str.strip().translate(carousel_session.PERSIAN_DIGITS)
        new_text = whole.strip()
    if not index_str.isdigit():
        await update.message.reply_text("استفاده: /carousel_edit <شماره> | <متن جدید>")
        return
    index = int(index_str)
    before = session.get("draft_saved_at")

    def run():
        return carousel_session.edit_slide(session, index, new_text)

    try:
        loop = asyncio.get_running_loop()
        error, path = await loop.run_in_executor(None, run)
    except Exception as exc:
        logger.exception("Carousel edit failed")
        await update.message.reply_text(f"❌ خطا در ویرایش: {type(exc).__name__}: {str(exc)[:200]}")
        return
    if error:
        await update.message.reply_text(error)
        return
    await update.message.reply_photo(
        open(path, "rb"),
        caption=f"✅ اسلاید {index} به‌روز شد." + _draft_suffix(session, before),
    )


@record_update_decorator
async def cmd_carousel_theme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    session = _get_carousel_session(context, update)
    if not session or session["state"] != carousel_session.PREVIEW:
        await update.message.reply_text("اول کاروسل را بساز (پیش‌نمایش) تا بتوانی قالب را عوض کنی.")
        return
    if not context.args:
        from agents.carousel.brand_theme import TEMPLATES
        await update.message.reply_text(
            f"استفاده: /carousel_theme <قالب>\nقالب‌ها: {', '.join(sorted(TEMPLATES))}"
        )
        return
    template_name = context.args[0].strip()
    before = session.get("draft_saved_at")

    def run():
        return carousel_session.change_theme(session, template_name)

    try:
        loop = asyncio.get_running_loop()
        error = await loop.run_in_executor(None, run)
    except Exception as exc:
        logger.exception("Carousel theme change failed")
        await update.message.reply_text(f"❌ خطا در تغییر قالب: {type(exc).__name__}: {str(exc)[:200]}")
        return
    if error:
        await update.message.reply_text(error)
        return
    await update.message.reply_text(
        f"✅ قالب {template_name} اعمال و کاروسل دوباره رندر شد."
        + _draft_suffix(session, before)
    )
    await _send_carousel_preview(update, session)


@record_update_decorator
async def cmd_carousel_layout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """M23: /carousel_layout <split|full|contain|auto> [slide_number].
    Thin handler — all logic lives in agents/studio/carousel_session.py."""
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    session = _get_carousel_session(context, update)
    if not session:
        await update.message.reply_text("جلسه کاروسلی فعال نیست. /carousel را بزن.")
        return

    raw = (update.message.text or "").strip()
    raw = re.sub(r"^/carousel_layout(@\S+)?\s*", "", raw)
    before = session.get("draft_saved_at")

    def run():
        return carousel_session.apply_layout(session, raw)

    try:
        loop = asyncio.get_running_loop()
        reply = await loop.run_in_executor(None, run)
    except Exception as exc:
        logger.exception("Carousel layout change failed")
        await update.message.reply_text(
            f"❌ خطا در تغییر چیدمان: {type(exc).__name__}: {str(exc)[:200]}"
        )
        return
    if not reply.startswith("❌") and not reply.startswith("فرمت"):
        reply += _draft_suffix(session, before)
    await update.message.reply_text(reply)
    # Show the result when the layout was applied to a previewed deck
    if reply.startswith("✅") and session.get("state") == carousel_session.PREVIEW:
        await _send_carousel_preview(update, session)


@record_update_decorator
async def cmd_carousel_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """M29: list the owner's resumable carousel drafts/content items."""
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    # M29A: draft ownership comes from the active Telegram chat id —
    # never context.chat_id / OWNER_CHAT_ID env
    chat_id = _effective_chat_id(update)
    try:
        owner_chat_id = carousel_session.normalize_owner_chat_id(chat_id)
    except carousel_session.CarouselOwnerChatIdError:
        await update.message.reply_text(carousel_session.OWNER_CHAT_ID_UNRESOLVED_FA)
        return

    def run():
        from agents.db.supabase_client import ElinaDB
        return carousel_session.list_carousels_fa(ElinaDB(), owner_chat_id)

    try:
        loop = asyncio.get_running_loop()
        reply = await loop.run_in_executor(None, run)
    except Exception as exc:
        logger.exception("Carousel list failed")
        await update.message.reply_text(
            f"❌ خطا در نمایش فهرست: {type(exc).__name__}: {str(exc)[:150]}"
        )
        return
    await update.message.reply_text(reply)


@record_update_decorator
async def cmd_carousel_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """M29: resume the latest saved carousel draft, or a specific one by
    custom_id (/carousel_resume ELN-CAR-...)."""
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    chat_data = _chat_data(context)
    custom_id = context.args[0].strip() if context.args else None
    # M29A: draft ownership comes from the active Telegram chat id
    chat_id = _effective_chat_id(update)
    try:
        owner_chat_id = carousel_session.normalize_owner_chat_id(chat_id)
    except carousel_session.CarouselOwnerChatIdError:
        await update.message.reply_text(carousel_session.OWNER_CHAT_ID_UNRESOLVED_FA)
        return

    def run():
        from agents.db.supabase_client import ElinaDB
        from agents.storage.supabase_storage import ElinaStorage
        return carousel_session.resume_carousel_draft(
            chat_data, ElinaDB(), ElinaStorage(), owner_chat_id, custom_id)

    try:
        loop = asyncio.get_running_loop()
        message_fa, error = await loop.run_in_executor(None, run)
    except Exception as exc:
        logger.exception("Carousel resume failed")
        await update.message.reply_text(
            f"❌ خطا در بازیابی: {type(exc).__name__}: {str(exc)[:150]}"
        )
        return
    if error:
        await update.message.reply_text(error)
        return
    session = chat_data.get("carousel_session")
    await update.message.reply_text(message_fa)
    if session and session.get("state") == carousel_session.PREVIEW:
        await _send_carousel_preview(update, session)


@record_update_decorator
async def cmd_carousel_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return
    chat_data = _chat_data(context)
    session = chat_data.get("carousel_session")
    if not session or session["state"] != carousel_session.PREVIEW:
        await update.message.reply_text("هنوز کاروسلی برای تأیید ساخته نشده است.")
        return

    msg = await update.message.reply_text("⏳ در حال ذخیره کاروسل...")

    def run():
        from agents.db.supabase_client import ElinaDB
        from agents.storage.supabase_storage import ElinaStorage
        return carousel_session.finalize(session, ElinaStorage(), ElinaDB())

    try:
        loop = asyncio.get_running_loop()
        error, info = await loop.run_in_executor(None, run)
    except Exception as exc:
        logger.exception("Carousel finalize crashed")
        await msg.edit_text(f"❌ خطای سیستمی: {type(exc).__name__}: {str(exc)[:200]}")
        return
    if error:
        await msg.edit_text(error)
        return
    carousel_session.cleanup(session)
    chat_data["carousel_session"] = None
    await msg.edit_text(carousel_session.confirm_message(info))


@record_update_decorator
async def handle_studio_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return

    try:
        message = update.message
        if not message:
            return

        # M29: reply-based fast re-register (ثبت / جایگزین) — handled
        # before any normal intake so a reply never double-registers.
        if await _handle_carousel_reply(update, context, message):
            return

        is_plain_text = (
            not message.video
            and not message.photo
            and not message.document
            and not message.audio
            and not message.voice
        )

        if is_plain_text:
            # M18D: active carousel session intercepts plain text (mode
            # selection / slide texts / topic). Without a session the code
            # below is exactly the pre-M18D behavior.
            session = _get_carousel_session(context, update)
            if session:
                state = session["state"]
                text = message.text or ""
                if state == carousel_session.MODE_SELECT:
                    await message.reply_text(carousel_session.select_mode(session, text))
                    return
                if state == carousel_session.COLLECT_TEXTS:
                    before = session.get("draft_saved_at")
                    carousel_session.add_text(session, text)
                    await message.reply_text(
                        f"✅ متن {len(session['texts'])} ثبت شد.\n"
                        "برای بدنه: عنوان | بدنه\n"
                        "وقتی تمام شد /done بزن."
                        + _draft_suffix(session, before)
                    )
                    return
                if state == carousel_session.COLLECT_TOPIC:
                    error = carousel_session.set_topic(session, text)
                    if error:
                        await message.reply_text(error)
                        return
                    await _run_carousel_build(update, session)
                    return
                if state in (carousel_session.PREVIEW, carousel_session.BUILDING):
                    await message.reply_text(
                        "کاروسل در حال آماده‌سازی/پیش‌نمایش است.\n"
                        "برای ادامه:\n/carousel_ok — تأیید و ذخیره\n"
                        "/carousel_edit <شماره> | <متن جدید>\n"
                        "/carousel_theme <قالب>\n/carousel_cancel — انصراف"
                    )
                    return
                # any other state: fall through to normal handling

            plan_mode = False
            if context.chat_data and context.chat_data.get("plan_mode"):
                plan_mode = True

            if plan_mode:
                text = message.text or ""
                interpreter = PersianEditInterpreter()
                plan = interpreter.parse(text)

                target_id = context.chat_data.get("plan_target_id")
                plan.target_custom_id = normalize_bundle_custom_id(target_id)
                plan.target_mode = "custom_id"

                errors = plan.validate()
                if errors:
                    err_lines = [f"- {err}" for err in errors]
                    err_msg = (
                        "⚠️ برنامه ادیت وارد شده دارای خطا است و قابل ثبت نیست:\n\n"
                        + "\n".join(err_lines)
                        + "\n\nلطفاً برنامه اصلاح شده را مجدداً وارد کنید."
                    )
                    await message.reply_text(err_msg)
                    return

                context.chat_data["plan_preview"] = plan

                preview_text = format_plan_preview_fa(plan)
                reply = preview_text + "\n\nبرای ادامه:\n/plan_ok\nیا\n/plan_cancel"
                await message.reply_text(reply)
            else:
                reply = (
                    "برای ارسال فایل، ویدیو یا عکس بفرست.\n"
                    "برای برنامه‌ریزی ادیت اول /plan ELN-BUNDLE-... را بزن."
                )
                await message.reply_text(reply)
            return

        # M18D: collect carousel images while a session is in COLLECT_IMAGES.
        # Without an active session the intake path below is unchanged.
        carousel_session_active = _get_carousel_session(context, update)

        # M29: answering a «جایگزین» prompt — the replacement image arrives
        # as a plain photo/document during PREVIEW.
        if (
            carousel_session_active
            and carousel_session_active["state"] == carousel_session.PREVIEW
            and carousel_session_active.get("pending_replace_slide")
            and (message.photo or message.document)
        ):
            index = carousel_session_active["pending_replace_slide"]
            carousel_session_active["pending_replace_slide"] = None
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = await _download_message_image(message, tmpdir)
                if not local_path:
                    await message.reply_text("❌ عکس جایگزین دریافت نشد؛ دوباره بفرست.")
                    return
                before = carousel_session_active.get("draft_saved_at")
                error, path = carousel_session.replace_slide_image(
                    carousel_session_active, index, local_path
                )
            if error:
                carousel_session_active["pending_replace_slide"] = index  # retry
                await message.reply_text(error)
            else:
                await message.reply_photo(
                    open(path, "rb"),
                    caption=carousel_session.SLIDE_REPLACED_FA.format(n=index)
                    + _draft_suffix(carousel_session_active, before),
                )
            return

        if (
            carousel_session_active
            and carousel_session_active["state"] == carousel_session.COLLECT_IMAGES
            and (message.photo or message.document or message.video or message.audio or message.voice)
        ):
            if message.photo or message.document:
                try:
                    import tempfile
                    with tempfile.TemporaryDirectory() as tmpdir:
                        local_path = await _download_message_image(message, tmpdir)
                        if not local_path:
                            await message.reply_text("❌ عکس دریافت نشد؛ دوباره بفرست.")
                            return
                        before = carousel_session_active.get("draft_saved_at")
                        error = carousel_session.add_image(
                            carousel_session_active, local_path
                        )
                        if error:
                            await message.reply_text(error)
                        else:
                            n = len(carousel_session_active["images"])
                            await message.reply_text(
                                f"✅ عکس {n} ثبت شد.\n"
                                f"حداقل {carousel_session.MIN_IMAGES}، "
                                f"حداکثر {carousel_session.MAX_IMAGES} عکس.\n"
                                "وقتی تمام شد /done بزن."
                                + _draft_suffix(carousel_session_active, before)
                            )
                except Exception as e:
                    logger.exception("Carousel image download failed")
                    await message.reply_text(
                        f"❌ خطا در دریافت عکس: {type(e).__name__}: {str(e)[:150]}"
                    )
            else:
                await message.reply_text(
                    "این مرحله فقط عکس می‌خواهد. ویدیو/صدا را بعد از ساخت کاروسل بفرست."
                )
            return

        file_obj = None
        ext = ".txt"

        if message.video:
            file_obj = await message.video.get_file()
            ext = ".mp4"
        elif message.photo:
            file_obj = await message.photo[-1].get_file()
            ext = ".jpg"
        elif message.document:
            file_obj = await message.document.get_file()
            ext = Path(message.document.file_name).suffix if message.document.file_name else ".bin"
        elif message.audio:
            file_obj = await message.audio.get_file()
            ext = Path(message.audio.file_name).suffix if message.audio.file_name else ".mp3"
        elif message.voice:
            file_obj = await message.voice.get_file()
            ext = ".ogg"

        caption = message.caption or message.text or ""

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, f"temp_studio{ext}")

            if file_obj:
                await file_obj.download_to_drive(local_path)
            else:
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(caption)
                caption = "Text-only intake"
                ext = ".txt"

            from agents.intake.telegram_intake import IntakeProcessor
            processor = IntakeProcessor()
            result = processor.process_incoming_media(
                local_file_path=local_path,
                file_ext=ext,
                caption=caption,
                telegram_message_id=str(message.message_id),
                sender_name=actor_name(update),
                source="telegram_studio_upload"
            )

            response_text = (
                f"✅ فایل وارد استودیو شد.\n"
                f"شناسه: {result['custom_id']}\n"
                f"وضعیت: RAW_RECEIVED\n"
                f"مرحله بعد:\n"
                f"/promote {result['custom_id']}\n"
                f"یا اگر نیاز به ادیت دارد:\n"
                f"/edit {result['custom_id']} توضیح ادیت"
            )
            await message.reply_text(response_text)

    except Exception as e:
        logger.exception("Studio media handler failed")
        try:
            await update.message.reply_text(
                f"❌ خطا در پردازش فایل:\n{type(e).__name__}: {str(e)[:200]}\n\n"
                "لطفاً چند دقیقه صبر کنید و دوباره امتحان کنید."
            )
        except Exception as reply_err:
            logger.error(f"Failed to send reply text after handler crash: {reply_err}")


async def post_init(application):
    logger.info(f"Bot initialized. Sending startup message to {OWNER_CHAT_ID}...")
    try:
        await application.bot.send_message(chat_id=OWNER_CHAT_ID, text="🎬 Studio Bot روشن شد. /help را بزنید.")
        logger.info("Startup message sent successfully.")
        with open("/tmp/elina_studio_startup.json", "w") as f:
            json.dump({"ok": True, "error": None}, f)
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")
        with open("/tmp/elina_studio_startup.json", "w") as f:
            json.dump({"ok": False, "error": str(e)}, f)


def main():
    if not STUDIO_BOT_TOKEN or not OWNER_CHAT_ID:
        logger.error("CRITICAL: STUDIO_BOT_TOKEN or OWNER_CHAT_ID is missing!")
        sys.exit(1)

    logger.info("Initializing Studio Bot application...")

    # post_init is the safe way to run async code on startup without hanging the event loop
    app = ApplicationBuilder().token(STUDIO_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("start", cmd_start_help))
    app.add_handler(CommandHandler("help", cmd_start_help))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("promote", cmd_promote))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("edit", cmd_edit))
    app.add_handler(CommandHandler("editdone", cmd_editdone))
    app.add_handler(CommandHandler("render", cmd_render))
    app.add_handler(CommandHandler("bundle", cmd_bundle))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("plan_cancel", cmd_plan_cancel))
    app.add_handler(CommandHandler("plan_ok", cmd_plan_ok))
    app.add_handler(CommandHandler("carousel", cmd_carousel))
    app.add_handler(CommandHandler("carousel_cancel", cmd_carousel_cancel))
    app.add_handler(CommandHandler("carousel_ok", cmd_carousel_ok))
    app.add_handler(CommandHandler("carousel_list", cmd_carousel_list))
    app.add_handler(CommandHandler("carousel_resume", cmd_carousel_resume))
    app.add_handler(CommandHandler("carousel_edit", cmd_carousel_edit))
    app.add_handler(CommandHandler("carousel_theme", cmd_carousel_theme))
    app.add_handler(CommandHandler("carousel_layout", cmd_carousel_layout))
    app.add_handler(CommandHandler("done", cmd_done))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_studio_media))

    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
