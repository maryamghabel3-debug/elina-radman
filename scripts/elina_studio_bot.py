import os
import re
import asyncio
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, List
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.studio.approval import ApprovalManager
from agents.editing.orchestrator import EditOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
STUDIO_BOT_TOKEN = os.environ.get("STUDIO_BOT_TOKEN")


def is_owner(update: Update) -> bool:
    return str(update.effective_chat.id) == str(OWNER_CHAT_ID)


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

    Examples:
        "raw/shot1.mp4:0-3"     -> start=0.0, end=3.0
        "raw/shot2.mp4:1.2-4"   -> start=1.2, end=4.0
        "raw/shot3.mp4:0-"      -> start=0.0, end=None
        "raw/shot4.mp4"         -> start=0.0, end=None (no trim)
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


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    mgr = ApprovalManager()
    items = mgr.get_pending_items()
    if not items:
        await update.message.reply_text("محتوای منتظر بررسی وجود ندارد.")
        return
    lines = []
    for item in items:
        preview = (item.get("caption_fa") or "")[:60]
        lines.append(f"- {item['custom_id']} | {item['content_type']} | {item['status']}\n  {preview}")
    await update.message.reply_text("\n\n".join(lines))


async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if len(context.args) < 1:
        await update.message.reply_text("استفاده: /promote ELN-RAW-...")
        return
    result = ApprovalManager().promote_to_review(context.args[0], actor_name(update))
    await update.message.reply_text(f"✅ {result['new_status']}" if result["ok"] else f"❌ {result['error']}")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /approve ELN-... prime_evening")
        return
    result = ApprovalManager().approve_and_schedule(context.args[0], context.args[1], actor_name(update))
    if result["ok"]:
        await update.message.reply_text(f"✅ تأیید شد\nزمان: {result['scheduled_for']}\nاسلات: {result['slot']}")
    else:
        await update.message.reply_text(f"❌ {result['error']}")


async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /reject ELN-... دلیل")
        return
    reason = " ".join(context.args[1:])
    result = ApprovalManager().reject_item(context.args[0], reason, actor_name(update))
    await update.message.reply_text(f"🚫 رد شد: {result['custom_id']}" if result["ok"] else f"❌ {result['error']}")


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /edit ELN-... توضیح")
        return
    task = " ".join(context.args[1:])
    result = ApprovalManager().mark_needs_edit(context.args[0], task, actor_name(update))
    await update.message.reply_text(f"✏️ نیازمند ادیت: {result['custom_id']}" if result["ok"] else f"❌ {result['error']}")


async def cmd_editdone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if len(context.args) < 1:
        await update.message.reply_text("استفاده: /editdone ELN-...")
        return
    result = ApprovalManager().mark_edit_done(context.args[0], actor_name(update))
    await update.message.reply_text(f"✅ ادیت تمام شد: {result['custom_id']}" if result["ok"] else f"❌ {result['error']}")


async def cmd_render(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

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
        orchestrator = EditOrchestrator()
        return orchestrator.render_content(
            custom_id=custom_id,
            hook_text=hook_text,
            actor=actor,
            video_segments=segments,
            voice_key=voice_key,
            music_key=music_key,
        )

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, run)
        if result.get("ok"):
            await msg.edit_text(
                f"✅ رندر تمام شد\nID: {result['custom_id']}\nStatus: {result['status']}\nOutput: {result.get('output_key','')}"
            )
        else:
            await msg.edit_text(f"❌ رندر ناموفق:\n{result.get('error')}")
    except Exception as exc:
        logger.exception("render failed")
        await msg.edit_text(f"❌ خطای سیستمی:\n{type(exc).__name__}: {exc}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text(
            "⛔ دسترسی فقط برای مالک است. /whoami را بزنید."
        )
        return
    await update.message.reply_text(
        "دستورهای Studio Bot:\n\n"
        "/pending\n"
        "/promote ELN-...\n"
        "/approve ELN-... prime_evening|afternoon|morning|night\n"
        "/reject ELN-... دلیل\n"
        "/edit ELN-... توضیح\n"
        "/editdone ELN-...\n"
        "/render ELN-... [متن هوک] — رندر ادیت‌شده با هوک فارسی\n"
    )


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    configured = str(OWNER_CHAT_ID or "NOT SET")
    if chat_id == configured:
        await update.message.reply_text(
            f"✅ شما مالک هستید.\nآیدی شما: {chat_id}\n"
            "ربات باید به همه دستورات جواب بدهد."
        )
    else:
        await update.message.reply_text(
            "❌ آیدی شما با تنظیمات سرور یکی نیست.\n"
            f"آیدی واقعی شما: {chat_id}\n"
            f"آیدی تنظیم‌شده در سرور: {configured}\n\n"
            "راه حل: در پنل Render مقدار OWNER_CHAT_ID را به "
            f"{chat_id} تغییر دهید و Save کنید."
        )


async def post_init(application):
    """
    On startup, send proactive message to OWNER_CHAT_ID.
    """
    try:
        await application.bot.send_message(
            chat_id=OWNER_CHAT_ID,
            text="🎬 Studio Bot روشن شد. /help را بزنید."
        )
        logger.info("Sent startup message to owner %s", OWNER_CHAT_ID)
    except Exception as e:
        logger.error("Failed to send proactive startup message to owner %s: %s", OWNER_CHAT_ID, e)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Log Telegram-related errors.
    """
    logger.error("Exception while handling an update:", exc_info=context.error)


def main():
    if not STUDIO_BOT_TOKEN:
        logger.error("CRITICAL: STUDIO_BOT_TOKEN is missing!")
        sys.exit(1)
    if not OWNER_CHAT_ID:
        logger.error("CRITICAL: OWNER_CHAT_ID is missing!")
        sys.exit(1)

    app = (
        ApplicationBuilder()
        .token(STUDIO_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_error_handler(error_handler)

    for cmd, handler in [
        ("pending", cmd_pending), ("promote", cmd_promote),
        ("approve", cmd_approve), ("reject", cmd_reject),
        ("edit", cmd_edit), ("editdone", cmd_editdone),
        ("render", cmd_render),
        ("help", cmd_help), ("start", cmd_help),
        ("whoami", cmd_whoami),
    ]:
        app.add_handler(CommandHandler(cmd, handler))

    logger.info("Elina Studio Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
