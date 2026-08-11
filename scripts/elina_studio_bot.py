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
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.studio.approval import ApprovalManager
from agents.editing.persian_edit_interpreter import PersianEditInterpreter, format_plan_preview_fa
from agents.studio.bundle_ids import normalize_bundle_custom_id

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
        "بعد از آن، برنامه را به فارسی بنویس:\n"
        "- شات اول از صفر تا ۲.۸\n"
        "- شات دوم از ۱.۲ تا ۳.۸\n"
        "- صدای اصلی قطع شود\n"
        "- هوک: ...\n\n"
        "/plan_ok\n"
        "تأیید و شروع رندر واقعی\n\n"
        "/plan_cancel\n"
        "خروج از حالت برنامه‌ریزی\n\n"
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
    await update.message.reply_text("✅ ادیت تمام شد" if result.get("ok") else f"❌ {result.get('error')}")


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

    target_id = normalize_bundle_custom_id(target_id)

    try:
        from agents.rendering.job_manager import RenderJobManager

        plan_dict = {
            "target_id": target_id,
            "mute_original": plan.mute_original_audio,
            "shots": [{"index": s.shot_index, "start": s.start_sec, "end": s.end_sec} for s in plan.shots],
            "sfx": [{"query": s.query_fa, "start": s.start_sec, "gain": s.gain_db} for s in plan.sound_effects],
            "hook": plan.hook_text,
            "music_enabled": plan.music.enabled if plan.music else False,
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


@record_update_decorator
async def handle_studio_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است.")
        return

    try:
        message = update.message
        if not message:
            return

        is_plain_text = (
            not message.video
            and not message.photo
            and not message.document
            and not message.audio
            and not message.voice
        )

        if is_plain_text:
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

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_studio_media))

    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
