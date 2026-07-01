#!/usr/bin/env python3
"""ElinaOS Bot — Process ALL messages without losing any"""

import os
import sys
import json
import glob as g
import requests
from datetime import datetime

# Ensure the repo root is importable so `from agents...` works when this
# script is launched as `python scripts/elina_bot.py` (e.g. in GitHub Actions).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GEMINI = os.environ.get("GEMINI_API_KEY", "")

# Fail fast with a clear message instead of a raw KeyError traceback
# when required secrets are missing (e.g. misconfigured GitHub Actions).
if not TOKEN or not CHAT:
    missing = [
        n
        for n, v in (("TELEGRAM_BOT_TOKEN", TOKEN), ("TELEGRAM_CHAT_ID", CHAT))
        if not v
    ]
    print(f"❌ Missing required secret(s): {', '.join(missing)}. Skipping bot run.")
    sys.exit(0)

BASE = f"https://api.telegram.org/bot{TOKEN}"


def tg(method, data=None):
    return requests.post(f"{BASE}/{method}", json=data or {}, timeout=15).json()


def send(chat, text, parse="Markdown", reply_to=None):
    d = {"chat_id": chat, "text": text, "parse_mode": parse}
    if reply_to:
        d["reply_to_message_id"] = reply_to
    return tg("sendMessage", d)


# Read offset
OFFSET_FILE = "content/bot_offset.txt"
try:
    with open(OFFSET_FILE) as f:
        offset = int(f.read().strip() or "0")
except Exception:
    offset = 0

# Get ALL updates since last offset
print(f"📡 Offset: {offset}")
r = requests.get(f"{BASE}/getUpdates?offset={offset}&timeout=10", timeout=15).json()
updates = r.get("result", [])
print(f"📩 {len(updates)} messages")

for u in updates:
    offset = u["update_id"] + 1
    msg = u.get("message", {})
    text = msg.get("text", "")
    chat = str(msg.get("chat", {}).get("id", ""))
    mid = msg.get("message_id", 0)
    user = msg.get("from", {}).get("first_name", "")
    print(f"   [{user}] {text[:60]}")

    resp = None

    if text == "/start":
        resp = """🕊️ *الینا جان، به ElinaOS خوش اومدی!*

من سیستم مدیریت محتوات هستم:

📊 */status* — وضعیت
🎨 */content* — پست جدید
📋 */list* — صف محتوا
✅ */approve شناسه* — تأیید
🔥 */trends* — ترندها
🤖 */agents* — ایجنت‌ها
🐙 */github* — گیت‌هاب
💬 *هر پیام = چت هوشمند*"""

    elif text == "/status":
        q = len(g.glob("content/queue/*.json"))
        resp = f"""🕊️ *وضعیت سیستم*

📊 *محتوا*
• در صف: {q} فایل

🤖 *ایجنت‌ها* (۴)
• trend_hunter | content_creator
• publisher | github_manager

🔗 *اتصالات*
• Gemini: {'✅' if GEMINI else '❌'}
• Postiz: {'✅' if os.environ.get('POSTIZ_API_TOKEN') else '❌'}
• GitHub: {'✅' if os.environ.get('GH_PAT') else '❌'}

🕐 {datetime.now().strftime('%H:%M')}
💰 هزینه: ۰ تومان"""

    elif text == "/content":
        send(chat, "🎨 *در حال ساخت ۳ محتوای جدید...* ⏳", reply_to=mid)
        from agents.content_creator import ContentCreator

        cc = ContentCreator()
        pieces = cc.run(count=3)
        resp = f"✅ *{len(pieces)} محتوا ساخته شد!*\n\n"
        for p in pieces:
            resp += f"🆔 `{p['id']}`\n🏷 {p['pillar']}\n📝 {p['caption'][:80]}...\n\n"
        resp += "برای تأیید: `/approve شناسه`"
        send(chat, resp)

    elif text == "/list":
        files = sorted(g.glob("content/queue/*.json"))
        if not files:
            resp = "📭 صف خالیه. /content بزن."
        else:
            resp = "📋 *صف محتوا*\n\n"
            for fp in files[-5:]:
                with open(fp) as f:
                    pieces = json.load(f)
                for p in pieces:
                    s = {"pending_approval": "⏳", "approved": "✅", "rejected": "❌"}
                    icon = s.get(p.get("status"), "❓")
                    resp += f"{icon} `{p['id']}` — {p['pillar']}\n{p['caption'][:70]}...\n\n"

    elif text.startswith("/approve"):
        parts = text.split()
        if len(parts) > 1:
            cid = parts[1]
            found = False
            for fp in sorted(g.glob("content/queue/*.json")):
                with open(fp) as f:
                    pieces = json.load(f)
                for p in pieces:
                    if p.get("id") == cid:
                        p["status"] = "approved"
                        found = True
                with open(fp, "w") as f:
                    json.dump(pieces, f, indent=2)
                if found:
                    break
            resp = (
                f"✅ *تأیید شد!* `{cid}`\nدر حال انتشار..."
                if found
                else f"❌ `{cid}` پیدا نشد. /list"
            )
        else:
            resp = "❌ `/approve شناسه_محتوا`"

    elif text == "/reject":
        resp = "❌ `/reject شناسه_محتوا`"

    elif text == "/trends":
        send(chat, "🔥 *در حال جستجوی ترندهای واقعی...* ⏳", reply_to=mid)
        try:
            from agents.trend_hunter import TrendHunter

            th = TrendHunter()
            th.run()
            resp = "🔥 *ترندهای واقعی فشن (بر اساس محبوبیت واقعی)*\n\n"
            live = [t for t in th.trends if not t.get("curated") and not t.get("mock")]
            for t in live[:8]:
                traffic = f" — 🔎 {t['approx_traffic']}" if t.get("approx_traffic") else ""
                resp += f"• {t['name'][:70]}{traffic}\n  ↳ _{t['platform']}_\n"
            if not live:
                resp += "_(منابع زنده الان در دسترس نیستن، بعداً دوباره امتحان کن)_\n"
            resp += "\n📸 برای عکس‌های پرویو: `/topimages`"
        except Exception as e:
            print("trends error:", e)
            resp = "⚠️ خطا در دریافت ترندها. بعداً دوباره امتحان کن."

    elif text == "/topimages":
        send(chat, "📸 *در حال پیدا کردن عکس‌های پرویو...* ⏳", reply_to=mid)
        try:
            from agents.trend_hunter import TrendHunter

            th = TrendHunter()
            th.run()
            tops = th.top_images(limit=5)
            if not tops:
                resp = "⚠️ الان عکس ترندی پیدا نشد (احتمالاً محدودیت نرخ). بعداً امتحان کن."
            else:
                resp = "📸 *عکس‌هایی که بیشترین ویو رو می‌گیرن:*\n\n"
                for t in tops:
                    resp += f"🖼 *{t['name'][:60]}*\n{t.get('url') or ''}\n{t.get('image') or ''}\n\n"
        except Exception as e:
            print("topimages error:", e)
            resp = "⚠️ خطا در دریافت عکس‌ها. بعداً دوباره امتحان کن."

    elif text == "/agents":
        resp = """🤖 *ایجنت‌ها* (۴)

• *trend_hunter* — ترندها 🔥
• *content_creator* — محتوا 🎨
• *publisher* — انتشار 📤
• *github_manager* — گیت‌هاب 🐙

➕ /addagent | ➖ /delagent"""

    elif text == "/github":
        resp = """🐙 *گیت‌هاب*

📦 maryamghabel3-debug/elina-radman
📁 ۱۷ فایل | ۳ workflow | ۴ ایجنت
🔐 ۷ Secret فعال ✅"""

    elif text == "/help":
        resp = """🕊️ *راهنما*

📊 /status | 🎨 /content | 📋 /list
✅ /approve | ❌ /reject
🔥 /trends | 📸 /topimages | 🤖 /agents
🐙 /github | 📝 /diary | 📤 /publish
💬 *هر پیام = چت با Gemini*"""

    elif text == "/publish":
        send(chat, "📤 *در حال انتشار...*", reply_to=mid)
        from agents.publisher import Publisher

        r = Publisher().run()
        n = len(r.get("published", []))
        resp = f"✅ {n} محتوا منتشر شد!" if n else "⚠️ محتوای تأییدشده پیدا نشد."

    elif text.startswith("/diary"):
        # The user can save a daily journal entry about Elina's feelings to guide content generation
        entry = text.replace("/diary", "").strip()
        if not entry:
            resp = "📝 لطفاً احساس امروز رو جلوی دستور بنویس:\nمثال: `/diary امروز خیلی به خاطر اخبار غمگینم اما می‌خوام قوی باشم.`"
        else:
            diary_path = "content/elina_diary.json"
            entries = []
            if os.path.exists(diary_path):
                with open(diary_path, "r") as f:
                    entries = json.load(f)
            
            entries.append({
                "date": datetime.now().isoformat(),
                "feeling": entry
            })
            
            os.makedirs("content", exist_ok=True)
            with open(diary_path, "w") as f:
                json.dump(entries[-10:], f, indent=2) # Keep last 10 entries
                
            resp = f"📓 *خاطره ذخیره شد!*\n\nاین احساسِ تو (`{entry}`) روی پست‌هایی که امروز تولید میشه تاثیر می‌ذاره. 🤍"

    elif text.startswith("/"):
        resp = "❓ /help رو بزن"

    else:
        # AI Chat
        if GEMINI:
            try:
                import google.generativeai as genai

                genai.configure(api_key=GEMINI)
                m = genai.GenerativeModel("gemini-2.5-flash")
                p = (
                    "You are Elina Radman, a 24yo Iranian fashion influencer, clinical psychologist, "
                    "horticulturist, and social activist. You are petite, confident, vulnerable, and courageous. "
                    "Your user is your manager/friend or a close fan. You don't just dump all your feelings at once. "
                    "If you are happy, share your joy and what beautiful thing you saw or learned today. "
                    "If you are sad or thoughtful, share it authentically but with depth. "
                    "You are a virtual character powered by a real human soul behind you. "
                    "Reply in Persian, warm, highly emotional, and relatable. "
                    "Be authentic, not robotic. Keep it under 500 chars. User: " + text
                )
                resp = m.generate_content(p).text.strip()[:800]
            except Exception as e:
                print("Gemini error:", e)
                resp = "من اینجام 🤍 /help رو بزن"
        else:
            resp = "من اینجام 🤍 /help رو بزن"

    if resp:
        r = send(chat, resp, reply_to=mid)
        print(f"   → {'✅' if r.get('ok') else '❌'}")

# Save offset
with open(OFFSET_FILE, "w") as f:
    f.write(str(offset))
print(f"💾 Offset saved: {offset}")
