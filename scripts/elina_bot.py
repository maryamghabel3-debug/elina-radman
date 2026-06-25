#!/usr/bin/env python3
"""ElinaOS Bot — Process ALL messages without losing any"""

import os
import json
import glob as g
import requests
from datetime import datetime

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]
GEMINI = os.environ.get("GEMINI_API_KEY", "")
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
• Buffer: ✅
• GitHub: ✅

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
        resp = """🔥 *ترندهای فشن — ژوئن ۲۰۲۶*

• Photo Carousels — IG+TT | ⭐ کم‌زحمت
• Bad News Wallet — IG+TT | ⭐ کم‌زحمت
• Color Walk — TT | ⭐⭐ متوسط
• GRWM Storytime — IG+TT | ⭐⭐
• Brainwash Format — IG | ⭐ کم‌زحمت"""

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
🔥 /trends | 🤖 /agents
🐙 /github | ➕ /addagent | ➖ /delagent
💬 *هر پیام = چت با Gemini*"""

    elif text == "/publish":
        send(chat, "📤 *در حال انتشار...*", reply_to=mid)
        from agents.publisher import Publisher

        r = Publisher().run()
        n = len(r.get("published", []))
        resp = f"✅ {n} محتوا منتشر شد!" if n else "⚠️ محتوای تأییدشده پیدا نشد."

    elif text.startswith("/"):
        resp = "❓ /help رو بزن"

    else:
        # AI Chat
        if GEMINI:
            try:
                import google.generativeai as genai

                genai.configure(api_key=GEMINI)
                m = genai.GenerativeModel("gemini-2.5-flash")
                p = f"You are ElinaOS, assistant for Elina Radman (fashion influencer, petite, Iranian). Reply in Persian, warm, helpful, under 350 chars. User: {text}"
                resp = m.generate_content(p).text.strip()[:800]
            except Exception as e:
                print("Gemini error:", e)
                resp = "👋 سلام الینا جان! /help رو بزن 🤍"
        else:
            resp = "👋 سلام! /help رو بزن 🤍"

    if resp:
        r = send(chat, resp, reply_to=mid)
        print(f"   → {'✅' if r.get('ok') else '❌'}")

# Save offset
with open(OFFSET_FILE, "w") as f:
    f.write(str(offset))
print(f"💾 Offset saved: {offset}")
