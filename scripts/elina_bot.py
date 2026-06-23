#!/usr/bin/env python3
"""
ElinaOS Telegram Bot — Full Chat + Agent Management
Runs every 5 min via GitHub Actions — $0/month
"""
import os, sys, json, time, glob, requests
from datetime import datetime, timedelta

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN","")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID","")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY","")
BUFFER_KEY = os.environ.get("BUFFER_API_TOKEN","")
GH_PAT = os.environ.get("GH_PAT","")
REPO_OWNER = os.environ.get("REPO_OWNER","")
REPO_NAME = os.environ.get("REPO_NAME","elina-radman")

BASE = f"https://api.telegram.org/bot{TOKEN}"

# ═══ BRAND CONTEXT ═══
BRAND_FA = """الینا رادمان | اینفلوئنسر فشن | Petite Quiet Luxury
قد: ۱۵۰cm | ۴۳kg | استایل: مینیمال، کمد کپسولی، رنگ‌های خنثی
مخاطب: خانم‌های ۱۸-۳۵ ساله با قد زیر ۱۶۰cm
پلتفرم‌ها: اینستاگرام، تیک‌تاک، یوتیوب، پینترست
هشتگ: #StyledByElina"""

# ═══ HELPERS ═══
def tg(method, data=None):
    try:
        r = requests.post(f"{BASE}/{method}", json=data or {}, timeout=15)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send(chat, text, parse="Markdown", reply_to=None):
    d = {"chat_id": chat, "text": text, "parse_mode": parse}
    if reply_to: d["reply_to_message_id"] = reply_to
    return tg("sendMessage", d)

def reply(chat, text, msg_id=None): 
    return send(chat, text, reply_to=msg_id)

def ai_chat(text):
    """Use Gemini to chat intelligently"""
    if not GEMINI_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        m = genai.GenerativeModel("gemini-2.5-flash")
        p = f"""You are ElinaOS, AI assistant for Elina Radman.
{BRAND_FA}
Current user message: {text}
Reply in Persian (Farsi). Be warm, helpful, concise (under 300 chars).
You can help with: content ideas, fashion tips, agent management, system status."""
        r = m.generate_content(p)
        return r.text.strip()[:1000]
    except:
        return None

# ═══ COMMAND HANDLERS ═══

def cmd_start(chat, args, msg_id, lang="fa"):
    text = """🕊️ *به ElinaOS خوش اومدی!*

من دستیار هوشمند الینا رادمان هستم.

📊 */status* — وضعیت سیستم
🎨 */content* — ساخت پست جدید
📋 */list* — صف محتوا
🔥 */trends* — ترندهای فشن
🤖 */agents* — ایجنت‌ها
🐙 */github* — گیت‌هاب
💬 *هر پیامی* — باهات حرف می‌زنم

کافیه /status رو بزنی ✨"""
    reply(chat, text, msg_id)

def cmd_status(chat, args, msg_id, lang="fa"):
    q = len(glob.glob("content/queue/*.json"))
    pub = len(glob.glob("content/published/*.json")) if os.path.exists("content/published") else 0
    af = glob.glob("agents/*.py")
    agents = [f.split("/")[-1].replace(".py","") for f in af if not f.endswith("__init__.py") and not f.endswith("base.py")]
    
    text = f"""🕊️ *وضعیت سیستم*

📊 *محتوا*
• در صف: {q} فایل
• منتشر شده: {pub} فایل

🤖 *ایجنت‌ها* ({len(agents)})
{chr(10).join(f'• {a}' for a in agents)}

🔗 *اتصالات*
• Gemini: {'✅' if GEMINI_KEY else '❌'}
• Buffer: {'✅' if BUFFER_KEY else '❌'}
• GitHub: {'✅' if GH_PAT else '❌'}

🕐 {datetime.now().strftime('%H:%M')}"""
    reply(chat, text, msg_id)

def cmd_content(chat, args, msg_id, lang="fa"):
    reply(chat, "🎨 *در حال ساخت محتوا...*\nلطفاً ۱۰ ثانیه صبر کن ⏳", msg_id)
    try:
        from agents.content_creator import ContentCreator
        cc = ContentCreator()
        pieces = cc.run(count=3)
        text = f"✅ *{len(pieces)} محتوا ساخته شد!*\n\n"
        for p in pieces:
            text += f"🆔 `{p['id']}`\n🏷 {p['pillar']}\n📝 {p['caption'][:100]}...\n\n"
        text += "برای تأیید: `/approve شناسه`"
        send(chat, text)
    except Exception as e:
        send(chat, f"❌ خطا: {str(e)[:200]}")

def cmd_list(chat, args, msg_id, lang="fa"):
    files = sorted(glob.glob("content/queue/*.json"))
    if not files:
        reply(chat, "📭 صف خالیه. /content بزن.", msg_id)
        return
    text = "📋 *صف محتوا*\n\n"
    for fp in files[-5:]:
        with open(fp) as f:
            pieces = json.load(f)
        for p in pieces:
            s = {"pending_approval":"⏳","approved":"✅","rejected":"❌","published":"📤"}
            icon = s.get(p.get("status",""),"❓")
            text += f"{icon} `{p['id']}` — {p['pillar']}\n{p['caption'][:80]}...\n\n"
    reply(chat, text, msg_id)

def cmd_approve(chat, args, msg_id, lang="fa"):
    if not args:
        reply(chat, "کاربرد: `/approve شناسه_محتوا`\nمثال: `/approve elina-20260623-peti`", msg_id)
        return
    cid = args[0]
    found = False
    for fp in sorted(glob.glob("content/queue/*.json")):
        with open(fp) as f: pieces = json.load(f)
        for p in pieces:
            if p.get("id") == cid:
                p["status"] = "approved"
                p["approved_at"] = datetime.now().isoformat()
                found = True
        with open(fp,"w") as f: json.dump(pieces, f, indent=2)
        if found: break
    
    if found:
        reply(chat, f"✅ *تأیید شد!*\n`{cid}`\n\nدر حال انتشار...", msg_id)
        # Publish immediately
        try:
            from agents.publisher import Publisher
            pub = Publisher()
            pub.run()
            send(chat, "📤 انتشار انجام شد!")
        except Exception as e:
            send(chat, f"⚠️ انتشار ناموفق: {str(e)[:100]}")
    else:
        reply(chat, f"❌ محتوای `{cid}` پیدا نشد.", msg_id)

def cmd_reject(chat, args, msg_id, lang="fa"):
    if not args:
        reply(chat, "کاربرد: `/reject شناسه_محتوا`", msg_id)
        return
    cid = args[0]
    for fp in sorted(glob.glob("content/queue/*.json")):
        with open(fp) as f: pieces = json.load(f)
        for p in pieces:
            if p.get("id") == cid: p["status"] = "rejected"
        with open(fp,"w") as f: json.dump(pieces, f, indent=2)
    reply(chat, f"❌ رد شد: `{cid}`", msg_id)

def cmd_trends(chat, args, msg_id, lang="fa"):
    try:
        from agents.trend_hunter import TrendHunter
        th = TrendHunter()
        trends = th.run()
        text = "🔥 *ترندهای جدید فشن*\n\n"
        for t in trends[:5]:
            text += f"• *{t['name']}*\n  {t['platform']} | {t['format']} | زحمت: {t['effort']}\n\n"
        reply(chat, text, msg_id)
    except Exception as e:
        reply(chat, f"❌ {e}", msg_id)

def cmd_agents(chat, args, msg_id, lang="fa"):
    af = sorted(glob.glob("agents/*.py"))
    agents = [f.split("/")[-1].replace(".py","") for f in af if not f.endswith("__init__.py") and not f.endswith("base.py")]
    text = f"🤖 *ایجنت‌ها* ({len(agents)})\n\n"
    for a in agents:
        text += f"• *{a}* — `/agent {a}` جزئیات\n"
    text += "\n➕ `/addagent` | ➖ `/delagent نام`"
    reply(chat, text, msg_id)

def cmd_agent(chat, args, msg_id, lang="fa"):
    if not args:
        reply(chat, "کاربرد: `/agent نام_ایجنت`\nمثال: `/agent trend_hunter`", msg_id)
        return
    name = args[0]
    fp = f"agents/{name}.py"
    if not os.path.exists(fp):
        reply(chat, f"❌ ایجنت `{name}` پیدا نشد.", msg_id)
        return
    with open(fp) as f:
        content = f.read()
    # Extract docstring
    in_doc = False
    doc = ""
    for l in content.split("\n"):
        if '"""' in l:
            if in_doc: break
            in_doc = True; continue
        if in_doc: doc += l + "\n"
    reply(chat, f"🤖 *{name}*\n\n{doc}\n📏 {len(content)} بایت", msg_id)

def cmd_addagent(chat, args, msg_id, lang="fa"):
    if not GH_PAT:
        reply(chat, "❌ GitHub PAT تنظیم نشده.", msg_id)
        return
    reply(chat, """➕ *افزودن ایجنت جدید*

فرمت:
`/addagent_done نام ایجنت | توضیحات | کد`

مثال:
`/addagent_done engagement | پاسخ به کامنت‌ها | pass`

⚠️ بعد از افزودن، گیت‌هاب redeploy می‌کنه.""", msg_id)

def cmd_addagent_done(chat, args, msg_id, lang="fa"):
    if not args:
        reply(chat, "فرمت: `/addagent_done نام | توضیحات | کد`", msg_id)
        return
    text = " ".join(args)
    parts = text.split("|",2)
    if len(parts) < 2:
        reply(chat, "❌ فرمت اشتباه. نیاز: نام | توضیحات | کد", msg_id)
        return
    name = parts[0].strip()
    desc = parts[1].strip() if len(parts) > 1 else ""
    code = parts[2].strip() if len(parts) > 2 else "pass"
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        result = gm.add_agent(name, desc, code)
        if "error" in result:
            reply(chat, f"❌ {result}", msg_id)
        else:
            reply(chat, f"✅ ایجنت *{name}* اضافه شد!\n📍 `{result['path']}`", msg_id)
    except Exception as e:
        reply(chat, f"❌ {e}", msg_id)

def cmd_delagent(chat, args, msg_id, lang="fa"):
    if not args:
        reply(chat, "کاربرد: `/delagent نام_ایجنت`\n⚠️ ایجنت‌های base، github_manager و __init__ محافظت شده‌اند.", msg_id)
        return
    name = args[0]
    if name in ["base","__init__","github_manager"]:
        reply(chat, f"🔒 ایجنت `{name}` محافظت شده و قابل حذف نیست.", msg_id)
        return
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        result = gm.remove_agent(name)
        if "error" in result:
            reply(chat, f"❌ {result}", msg_id)
        else:
            reply(chat, f"➖ ایجنت *{name}* حذف شد!", msg_id)
    except Exception as e:
        reply(chat, f"❌ {e}", msg_id)

def cmd_github(chat, args, msg_id, lang="fa"):
    if not GH_PAT:
        reply(chat, "❌ GitHub PAT تنظیم نشده.", msg_id)
        return
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        status = gm.repo_status()
        agents_list = gm.list_agents()
        text = f"🐙 *گیت‌هاب*\n\n📦 {status.get('name','?')}\n⭐ {status.get('stars','?')} ستاره\n🕐 {status.get('updated','?')[:10]}\n🤖 {agents_list.get('count','?')} ایجنت"
        reply(chat, text, msg_id)
    except Exception as e:
        reply(chat, f"❌ {e}", msg_id)

def cmd_ghfile(chat, args, msg_id, lang="fa"):
    if not args:
        reply(chat, "کاربرد: `/ghfile مسیر_فایل`\nمثال: `/ghfile agents/publisher.py`", msg_id)
        return
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        result = gm.get_file(args[0])
        if "error" in result:
            reply(chat, f"❌ {result}", msg_id)
        else:
            reply(chat, f"📄 *{args[0]}*\n\n```python\n{result['content'][:3000]}\n```", msg_id)
    except Exception as e:
        reply(chat, f"❌ {e}", msg_id)

def cmd_ghedit(chat, args, msg_id, lang="fa"):
    if not args or len(args) < 2:
        reply(chat, "کاربرد: `/ghedit مسیر_فایل | کد_جدید`\nفایل رو از گیت‌هاب می‌خونه، ویرایش می‌کنه و push می‌کنه.", msg_id)
        return
    txt = " ".join(args)
    parts = txt.split("|",1)
    if len(parts) < 2:
        reply(chat, "❌ فرمت: `/ghedit مسیر | کد_جدید`", msg_id)
        return
    try:
        from agents.github_manager import GitHubManager
        gm = GitHubManager()
        result = gm.update_file(parts[0].strip(), parts[1].strip())
        if "error" in result:
            reply(chat, f"❌ {result}", msg_id)
        else:
            reply(chat, f"✅ *{parts[0].strip()}* آپدیت شد!", msg_id)
    except Exception as e:
        reply(chat, f"❌ {e}", msg_id)

def cmd_publish(chat, args, msg_id, lang="fa"):
    reply(chat, "📤 *در حال انتشار...*", msg_id)
    try:
        from agents.publisher import Publisher
        p = Publisher()
        result = p.run()
        if "error" in result:
            send(chat, f"❌ {result['error']}")
        else:
            n = len(result.get("published",[]))
            send(chat, f"✅ {n} محتوا منتشر شد!")
    except Exception as e:
        send(chat, f"❌ {e}")

def cmd_help(chat, args, msg_id, lang="fa"):
    text = """🕊️ *راهنمای ElinaOS*

📊 *محتوا*
/content — ساخت ۳ پست جدید
/list — دیدن صف محتوا
/approve شناسه — تأیید و انتشار
/reject شناسه — رد کردن
/publish — انتشار دستی

🔥 *تحلیل*
/trends — ترندهای فشن
/status — وضعیت سیستم

🤖 *ایجنت‌ها*
/agents — لیست همه
/agent نام — جزئیات
/addagent — افزودن جدید
/delagent نام — حذف

🐙 *گیت‌هاب*
/github — وضعیت ریپو
/ghfile مسیر — نمایش فایل
/ghedit مسیر | کد — ویرایش فایل

💬 *چت*
هر پیامی که / نداشته باشه رو می‌فهمم و جواب می‌دم ✨"""
    reply(chat, text, msg_id)

# ═══ PROCESS MESSAGES ═══
COMMANDS = {
    "start": cmd_start, "status": cmd_status, "content": cmd_content,
    "list": cmd_list, "approve": cmd_approve, "reject": cmd_reject,
    "trends": cmd_trends, "agents": cmd_agents, "agent": cmd_agent,
    "addagent": cmd_addagent, "addagent_done": cmd_addagent_done,
    "delagent": cmd_delagent, "github": cmd_github, "ghfile": cmd_ghfile,
    "ghedit": cmd_ghedit, "publish": cmd_publish, "help": cmd_help,
}

def process(msg):
    text = msg.get("text","")
    chat = str(msg.get("chat",{}).get("id",""))
    msg_id = msg.get("message_id")
    user = msg.get("from",{}).get("first_name","")
    
    print(f"📩 [{user}] {text[:80]}")
    
    if text.startswith("/"):
        parts = text[1:].replace("@ElinaRA_bot","").split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        fn = COMMANDS.get(cmd)
        if fn:
            fn(chat, args, msg_id)
        else:
            reply(chat, f"❓ دستور /{cmd} رو نمی‌شناسم.\n/help رو بزن.", msg_id)
    else:
        # Chat mode
        ai = ai_chat(text)
        if ai:
            reply(chat, ai, msg_id)
        else:
            reply(chat, f"👋 سلام {user} جان!\n\nمن ElinaOS هستم، دستیار الینا رادمان.\n/help رو بزن تا ببینی چیکار می‌تونم برات انجام بدم 🤍", msg_id)

def main():
    if not TOKEN:
        print("No TELEGRAM_BOT_TOKEN")
        return
    
    # Poll for messages
    offset_file = "content/bot_offset.txt"
    offset = 0
    if os.path.exists(offset_file):
        with open(offset_file) as f:
            offset = int(f.read().strip() or 0)
    
    r = requests.get(f"{BASE}/getUpdates?offset={offset}&timeout=10", timeout=15)
    updates = r.json().get("result",[])
    
    for u in updates:
        offset = u["update_id"] + 1
        msg = u.get("message")
        if msg:
            process(msg)
    
    # Save offset
    with open(offset_file,"w") as f:
        f.write(str(offset))
    
    print(f"Processed {len(updates)} messages. Offset: {offset}")

if __name__ == "__main__":
    main()
