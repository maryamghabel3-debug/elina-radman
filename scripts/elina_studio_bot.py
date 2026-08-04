import os
import sys
import logging
import asyncio
from pathlib import Path

# Force unbuffered output so logs appear instantly in Render
sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.studio.approval import ApprovalManager
from agents.editing.orchestrator import EditOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="[STUDIO] %(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

OWNER_CHAT_ID = str(os.environ.get("OWNER_CHAT_ID", "")).strip()
STUDIO_BOT_TOKEN = str(os.environ.get("STUDIO_BOT_TOKEN", "")).strip()

def is_owner(update: Update) -> bool:
    return str(update.effective_chat.id) == OWNER_CHAT_ID

def actor_name(update: Update) -> str:
    user = update.effective_user
    return user.username or user.first_name or "unknown"

async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id == OWNER_CHAT_ID:
        await update.message.reply_text(f"✅ شما مالک هستید.\nآیدی شما: {chat_id}")
    else:
        await update.message.reply_text(f"❌ آیدی شما: {chat_id}\nتنظیم شده در سرور: {OWNER_CHAT_ID or 'NOT SET'}")

async def cmd_start_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("⛔ دسترسی فقط برای مالک است. برای بررسی آیدی خود /whoami را بزنید.")
        return
    text = (
        "دستورهای Studio Bot:\n\n"
        "/pending\n"
        "/promote ELN-RAW-...\n"
        "/approve ELN-... prime_evening|afternoon|morning|night\n"
        "/reject ELN-... دلیل\n"
        "/edit ELN-... توضیح\n"
        "/editdone ELN-...\n"
        "/render ELN-RAW-... [متن هوک]\n"
        "/whoami\n"
    )
    await update.message.reply_text(text)

async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    items = ApprovalManager().get_pending_items()
    if not items:
        await update.message.reply_text("صف خالی است.")
        return
    lines = [f"- {i['custom_id']} | {i['content_type']} | {i['status']}" for i in items]
    await update.message.reply_text("\n".join(lines))

async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if not context.args:
        await update.message.reply_text("استفاده: /promote ELN-RAW-...")
        return
    result = ApprovalManager().promote_to_review(context.args[0], actor_name(update))
    await update.message.reply_text(f"✅ {result.get('new_status', result.get('error'))}")

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

async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /reject ELN-... دلیل")
        return
    result = ApprovalManager().reject_item(context.args[0], " ".join(context.args[1:]), actor_name(update))
    await update.message.reply_text("🚫 رد شد" if result.get("ok") else f"❌ {result.get('error')}")

async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /edit ELN-... توضیح")
        return
    result = ApprovalManager().mark_needs_edit(context.args[0], " ".join(context.args[1:]), actor_name(update))
    await update.message.reply_text("✏️ نیازمند ادیت" if result.get("ok") else f"❌ {result.get('error')}")

async def cmd_editdone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if not context.args:
        await update.message.reply_text("استفاده: /editdone ELN-...")
        return
    result = ApprovalManager().mark_edit_done(context.args[0], actor_name(update))
    await update.message.reply_text("✅ ادیت تمام شد" if result.get("ok") else f"❌ {result.get('error')}")

async def cmd_render(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    if not context.args:
        await update.message.reply_text("استفاده: /render ELN-RAW-...")
        return
    custom_id = context.args[0]
    hook_text = " ".join(context.args[1:]) if len(context.args) > 1 else None
    msg = await update.message.reply_text(f"⏳ در حال رندر {custom_id}...")

    def run():
        return EditOrchestrator().render_content(custom_id, hook_text=hook_text, actor=actor_name(update))

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

async def post_init(application):
    logger.info(f"Bot initialized. Sending startup message to {OWNER_CHAT_ID}...")
    try:
        await application.bot.send_message(chat_id=OWNER_CHAT_ID, text="🎬 Studio Bot روشن شد. /help را بزنید.")
        logger.info("Startup message sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

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

    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
