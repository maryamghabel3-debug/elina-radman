import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.studio.approval import ApprovalManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
STUDIO_BOT_TOKEN = os.environ.get("STUDIO_BOT_TOKEN")


def is_owner(update: Update) -> bool:
    return str(update.effective_chat.id) == str(OWNER_CHAT_ID)


def actor_name(update: Update) -> str:
    user = update.effective_user
    return user.username or user.first_name or "unknown"


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


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(
        "دستورهای Studio Bot:\n\n"
        "/pending\n"
        "/promote ELN-...\n"
        "/approve ELN-... prime_evening|afternoon|morning|night\n"
        "/reject ELN-... دلیل\n"
        "/edit ELN-... توضیح\n"
        "/editdone ELN-...\n"
    )


def main():
    if not STUDIO_BOT_TOKEN or not OWNER_CHAT_ID:
        logger.error("Missing STUDIO_BOT_TOKEN or OWNER_CHAT_ID")
        return
    app = ApplicationBuilder().token(STUDIO_BOT_TOKEN).build()
    for cmd, handler in [
        ("pending", cmd_pending), ("promote", cmd_promote),
        ("approve", cmd_approve), ("reject", cmd_reject),
        ("edit", cmd_edit), ("editdone", cmd_editdone),
        ("help", cmd_help), ("start", cmd_help),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
    logger.info("Elina Studio Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
