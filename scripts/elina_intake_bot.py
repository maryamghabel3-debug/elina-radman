import os
import sys
import logging
import tempfile
import datetime
import json
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from agents.intake.telegram_intake import IntakeProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from agents.security.log_redaction import install_secret_redaction
install_secret_redaction()

logger = logging.getLogger(__name__)

RAW_CHAT_ID = os.environ.get("RAW_CHAT_ID")


def record_update():
    try:
        path = "/tmp/elina_intake_last_update.json"
        with open(path, "w") as f:
            json.dump({"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}, f)
    except Exception as e:
        logger.error(f"Failed to record update timestamp: {e}")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_update()
    if not update.message or str(update.message.chat_id) != str(RAW_CHAT_ID):
        return

    processor = IntakeProcessor()
    caption = update.message.caption or update.message.text
    sender = update.message.from_user.username or update.message.from_user.first_name
    msg_id = update.message.message_id

    file_obj = None
    ext = ".txt"

    if update.message.video:
        file_obj = await update.message.video.get_file()
        ext = ".mp4"
    elif update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
        ext = ".jpg"
    elif update.message.document:
        file_obj = await update.message.document.get_file()
        ext = Path(update.message.document.file_name).suffix if update.message.document.file_name else ".bin"

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, f"temp_intake{ext}")

        if file_obj:
            await file_obj.download_to_drive(local_path)
        else:
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(caption or "")
            caption = "Text-only intake"
            ext = ".txt"

        try:
            result = processor.process_incoming_media(
                local_file_path=local_path,
                file_ext=ext,
                caption=caption,
                telegram_message_id=msg_id,
                sender_name=sender
            )
            await update.message.reply_text(
                f"✅ محتوا بایگانی شد.\nشناسه: {result['custom_id']}\nوضعیت: {result['status']}"
            )
        except Exception as e:
            logger.error(f"Error processing intake: {e}", exc_info=True)
            await update.message.reply_text(f"❌ خطا در پردازش سیستم: {str(e)}")


def main():
    token = os.environ.get("INTAKE_BOT_TOKEN")
    if not token or not RAW_CHAT_ID:
        logger.error("Missing INTAKE_BOT_TOKEN or RAW_CHAT_ID in environment.")
        return

    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_media))

    logger.info("Elina Intake Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
