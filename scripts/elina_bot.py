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


def send_photo(chat, photo_path, caption=""):
    """Upload a local image file to the chat."""
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": chat, "caption": caption[:1000]}
            return requests.post(
                f"{BASE}/sendPhoto", data=data, files=files, timeout=60
            ).json()
    except Exception as e:
        print("send_photo error:", e)
        return {"ok": False}


def download_telegram_file(file_id: str, out_path: str) -> bool:
    """Download a file Telegram is hosting (photo/video) to a local path."""
    try:
        info = tg("getFile", {"file_id": file_id})
        if not info.get("ok"):
            print("getFile failed:", info)
            return False
        file_path = info["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print(f"file download HTTP {r.status_code}")
            return False
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print("download_telegram_file error:", e)
        return False


def find_queue_piece(piece_id: str):
    """Search every content/queue/*.json for a piece with this id.
    Returns (filepath, pieces_list, index) or (None, None, None)."""
    for fp in sorted(g.glob("content/queue/*.json")):
        try:
            with open(fp) as f:
                pieces = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for i, p in enumerate(pieces):
            if p.get("id") == piece_id:
                return fp, pieces, i
    return None, None, None


def setup_bot_commands():
    """Register the bot command menu with Telegram so users see all commands when tapping the '/' button."""
    commands = [
        {"command": "run_all", "description": "🚀 اجرای کامل خط تولید (ترند، افیلیت، عکس، ویدیو، پرامپت و کپشن)"},
        {"command": "status", "description": "📊 نمایش وضعیت سیستم و صف محتوا"},
        {"command": "content", "description": "🎨 ساخت ۳ پست جدید در صف تأیید"},
        {"command": "list", "description": "📋 مشاهده لیست محتواهای در انتظار"},
        {"command": "trends", "description": "🔥 جستجو و نمایش ترندهای روز فشن"},
        {"command": "topimages", "description": "📸 نمایش پرویو عکس‌های وایرال"},
        {"command": "photo", "description": "🎨 ساخت عکس جدید از الینا"},
        {"command": "analyze", "description": "🔬 تحلیل عمیق بصری و استایلینگ عکس‌ها"},
        {"command": "reverse", "description": "🎬 مهندسی معکوس ویدیوهای وایرال"},
        {"command": "makevideos", "description": "🎥 ساخت ایده‌های ویدیویی جدید"},
        {"command": "agents", "description": "🤖 نمایش لیست ایجنت‌های هوشمند"},
        {"command": "github", "description": "🐙 وضعیت مخزن و گیت‌هاب اکشنز"},
        {"command": "diary", "description": "📝 ثبت احساس و خاطره امروز الینا"},
        {"command": "setphoto", "description": "🖼 ثبت عکس دستی برای یک پست (بفرست + caption: /setphoto شناسه)"},
        {"command": "setvideo", "description": "🎬 ثبت ویدیوی دستی برای یک پست (بفرست + caption: /setvideo شناسه)"},
        {"command": "publish", "description": "📤 انتشار محتواهای تأییدشده"},
        {"command": "help", "description": "🕊️ نمایش راهنمای کامل دستورات"}
    ]
    res = tg("setMyCommands", {"commands": commands})
    if res.get("ok"):
        print("✅ Telegram bot menu commands updated successfully")
    else:
        print("⚠️ Could not update bot menu commands:", res)

setup_bot_commands()


# Read offset
OFFSET_FILE = "content/bot_offset.txt"
try:
    with open(OFFSET_FILE) as f:
        offset = int(f.read().strip() or "0")
except Exception:
    offset = 0


def save_offset(value):
    """Persist the offset locally after each message so a crash mid-run does not
    cause already-answered messages to be processed again."""
    try:
        os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
        with open(OFFSET_FILE, "w") as f:
            f.write(str(value))
    except Exception as e:
        print("offset save error:", e)


# Get ALL updates since last offset
print(f"📡 Offset: {offset}")
r = requests.get(f"{BASE}/getUpdates?offset={offset}&timeout=10", timeout=15).json()
updates = r.get("result", [])
print(f"📩 {len(updates)} messages")

for u in updates:
    offset = u["update_id"] + 1
    save_offset(offset)  # persist progress immediately (crash-safe)
    msg = u.get("message", {})
    text = msg.get("text", "") or msg.get("caption", "")
    photos = msg.get("photo") or []
    video = msg.get("video") or msg.get("document")
    chat = str(msg.get("chat", {}).get("id", ""))
    mid = msg.get("message_id", 0)
    user = msg.get("from", {}).get("first_name", "")
    print(f"   [{user}] {text[:60]}{' [photo]' if photos else ''}{' [video]' if video else ''}")

    resp = None

    # ------------------------------------------------------------------ #
    # Manual photo/video upload: reply to / caption a photo or video with
    # `/setphoto <piece_id>` or `/setvideo <piece_id>` (or just send it with
    # that as the caption) to attach a manually-made image/video (e.g. made
    # by hand on Gemini/another site) to a queued post instead of relying on
    # the automated (and currently quota-limited) ImageStudio/FacelessStudio.
    # ------------------------------------------------------------------ #
    if (photos or video) and text and (text.startswith("/setphoto") or text.startswith("/setvideo")):
        is_video = text.startswith("/setvideo")
        piece_id = text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) > 1 else ""
        if not piece_id:
            resp = (
                "❌ فرمت درست: عکس/ویدیو رو بفرست و در قسمت caption بنویس:\n"
                "`/setphoto شناسه_پست` یا `/setvideo شناسه_پست`\n\n"
                "شناسه پست رو از `/list` می‌تونی ببینی."
            )
        else:
            fp, pieces, idx = find_queue_piece(piece_id)
            if fp is None:
                resp = f"❌ پستی با شناسه `{piece_id}` پیدا نشد. `/list` رو بزن."
            else:
                ext = ".mp4" if is_video else ".jpg"
                out_dir = "content/videos" if is_video else "content/images"
                out_path = os.path.join(out_dir, f"manual_{piece_id}{ext}")
                file_id = (
                    (video or {}).get("file_id")
                    if is_video
                    else photos[-1]["file_id"]  # largest resolution is last
                )
                ok = download_telegram_file(file_id, out_path)
                if ok:
                    field = "video_path" if is_video else "image"
                    pieces[idx][field] = out_path
                    if not is_video:
                        pieces[idx]["image_provider"] = "manual_upload"
                        pieces[idx]["used_reference"] = True
                        pieces[idx]["image_warning"] = ""
                    with open(fp, "w") as f:
                        json.dump(pieces, f, indent=2, ensure_ascii=False)
                    kind = "ویدیو" if is_video else "عکس"
                    resp = f"✅ {kind} دستی برای پست `{piece_id}` ثبت شد!\nبرای انتشار: `/approve {piece_id}`"
                else:
                    resp = "⚠️ دانلود فایل از تلگرام ناموفق بود. دوباره امتحان کن."

    elif text == "/start":
        resp = """🕊️ *الینا جان، به ElinaOS خوش اومدی!*

من سیستم مدیریت محتوات هستم:

🚀 */run_all* — اجرای کامل چرخه روزانه (ترند، افیلیت، عکس، ویدیو، پرامپت و کپشن دوزبانه)
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

    elif text == "/run_all":
        send(chat, "🚀 *در حال اجرای کامل خط تولید الینا...* ⏳\n_(جستجوی ترند، یافتن لباس افیلیت، تولید عکس، و نگارش کپشن و پرامپت دوزبانه)_", reply_to=mid)
        try:
            import scripts.generate as gen_mod
            gen_mod.main()
            resp = "✅ *خط تولید روزانه کامل اجرا شد و تمام محتواها همراه با پرامپت‌های انگلیسی و توضیحات فارسی در تلگرام ارسال گردید!*"
        except Exception as e:
            print("run_all error:", e)
            resp = f"⚠️ خطا در اجرای کامل خط تولید: {str(e)[:200]}"

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

    elif text.startswith("/photo"):
        # /photo [gemini] [concept]  → generates a real photo of Elina.
        # Add the word 'gemini' to force Gemini-only (no Pollinations fallback),
        # which is the way to verify face consistency.
        concept = text.replace("/photo", "", 1).strip()
        force_gemini = False
        if concept.lower().startswith("gemini"):
            force_gemini = True
            concept = concept[6:].strip()
        if not concept:
            concept = "wearing a tailored camel blazer in a sunlit cafe, editorial fashion"
        mode = " (Gemini only)" if force_gemini else ""
        send(chat, f"🎨 *در حال ساخت عکس الینا...*{mode} ⏳\n_{concept[:80]}_", reply_to=mid)
        try:
            from agents.image_studio import ImageStudio

            r = ImageStudio().generate(
                concept, prefer="gemini" if force_gemini else "auto",
                allow_pollinations=not force_gemini,
            )
            if r.get("path"):
                prov = r.get("provider")
                extra = ""
                if prov == "gemini":
                    extra = f"\n✅ چهره از عکس مرجع (مدل: {r.get('working_model')})"
                elif r.get("gemini_error"):
                    extra = f"\n⚠️ Gemini کار نکرد → Pollinations. علت:\n{str(r['gemini_error'])[:300]}"
                send_photo(chat, r["path"], caption=f"🖼 {concept[:180]}\n(via {prov}){extra}")
                resp = None
            else:
                ge = r.get("gemini_error", "")
                resp = f"⚠️ ساخت عکس ناموفق بود.\nGemini: {str(ge)[:400]}"
        except Exception as e:
            print("photo error:", e)
            resp = f"⚠️ خطا در ساخت عکس: {str(e)[:200]}"

    elif text == "/analyze":
        send(chat, "🔬 *در حال تحلیل عمیق عکس‌های ترند...* ⏳\n(لباس، ژست، دوربین، نور)", reply_to=mid)
        try:
            from agents.trend_visual_analyzer import TrendVisualAnalyzer

            rep = TrendVisualAnalyzer().run(limit=4)
            deep_n = rep.get("deep_analyzed", 0)
            resp = "🔬 *تحلیل عمیق عکس‌های ترند*\n\n"
            resp += f"🖼 تحلیل‌شده: {rep.get('images_analyzed', 0)} عکس"
            resp += f" ({deep_n} با AI بینایی)\n\n"
            if rep.get("trending_aesthetics"):
                resp += f"👗 *استایل‌های ترند:* {', '.join(rep['trending_aesthetics'])}\n"
            if rep.get("trending_standout_products"):
                resp += f"⭐ *محصولات شاخص:* {', '.join(rep['trending_standout_products'][:3])}\n"
            if rep.get("trending_camera_angles"):
                resp += f"🎥 *زاویه دوربین:* {', '.join(rep['trending_camera_angles'])}\n"
            if rep.get("dominant_tones"):
                resp += f"🎨 *رنگ‌های غالب:* {', '.join(rep['dominant_tones'])}\n"
            if deep_n == 0:
                resp += "\n_برای تحلیل کامل AI، `GEMINI_API_KEY` رو ست کن._"
        except Exception as e:
            print("analyze error:", e)
            resp = "⚠️ خطا در تحلیل عکس‌ها. بعداً دوباره امتحان کن."

    elif text == "/reverse":
        send(chat, "🎬 *در حال مهندسی معکوس ویدیوهای وایرال...* ⏳", reply_to=mid)
        try:
            from agents.trend_video_analyzer import TrendVideoAnalyzer

            rep = TrendVideoAnalyzer().run(limit=3)
            n = rep.get("videos_analyzed", 0)
            if n == 0:
                resp = "⚠️ ویدیوی ترندی پیدا نشد. `YOUTUBE_API_KEY` رو ست کن تا فعال بشه."
            else:
                resp = f"🎬 *مهندسی معکوس {n} ویدیوی وایرال*\n\n"
                for a in rep.get("analyses", []):
                    meta = a.get("meta", {})
                    td = a.get("teardown", {})
                    resp += f"📹 *{(meta.get('title') or '')[:55]}*\n"
                    if meta.get("views"):
                        resp += f"👁 {meta['views']:,} بازدید | تعامل {td.get('engagement_rate_pct', '?')}%\n"
                    if td.get("hook"):
                        resp += f"🪝 هوک: {str(td['hook'])[:90]}\n"
                    why = td.get("why_it_went_viral")
                    if why:
                        first = why[0] if isinstance(why, list) else why
                        resp += f"🔥 چرا وایرال شد: {str(first)[:90]}\n"
                    resp += "\n"
                resp += "برای ساخت ویدیو بر اساس این‌ها: `/makevideos`"
        except Exception as e:
            print("reverse error:", e)
            resp = "⚠️ خطا در مهندسی معکوس ویدیوها. بعداً دوباره امتحان کن."

    elif text == "/makevideos":
        send(chat, "🎥 *در حال ساخت ایده‌های ویدیو از تحلیل‌ها...* ⏳", reply_to=mid)
        try:
            from agents.content_creator import ContentCreator

            pieces = ContentCreator().create_video_ideas(limit=3)
            if not pieces:
                resp = "⚠️ اول `/reverse` رو بزن تا ویدیوها تحلیل بشن."
            else:
                resp = f"🎥 *{len(pieces)} ایده ویدیو ساخته شد!*\n\n"
                for p in pieces:
                    resp += f"🆔 `{p['id']}`\n🪝 {str(p.get('hook') or '')[:70]}\n"
                    resp += f"💡 الهام از: {str(p.get('inspired_by') or '')[:50]}\n\n"
                resp += "برای تأیید: `/approve شناسه`"
        except Exception as e:
            print("makevideos error:", e)
            resp = "⚠️ خطا در ساخت ویدیوها. بعداً دوباره امتحان کن."

    elif text == "/agents":
        agent_files = sorted(
            os.path.basename(a)[:-3]
            for a in g.glob("agents/*.py")
            if os.path.basename(a) not in ("__init__.py", "base.py", "content_config.py")
        )
        resp = f"🤖 *ایجنت‌ها* ({len(agent_files)})\n\n"
        resp += "\n".join(f"• *{name}*" for name in agent_files)

    elif text == "/github":
        # Count things dynamically instead of hardcoding stale numbers
        n_workflows = len(g.glob(".github/workflows/*.yml"))
        n_agents = len(
            [
                a
                for a in g.glob("agents/*.py")
                if os.path.basename(a) not in ("__init__.py", "base.py", "content_config.py")
            ]
        )
        owner = os.environ.get("REPO_OWNER", "maryamghabel3-debug")
        repo = os.environ.get("REPO_NAME", "elina-radman")
        resp = f"""🐙 *گیت‌هاب*

📦 {owner}/{repo}
🔧 {n_workflows} workflow | 🤖 {n_agents} ایجنت
🔐 اسرار در GitHub Secrets"""

    elif text == "/help":
        resp = """🕊️ *راهنما*

🚀 /run_all (اجرای کامل خط تولید و ارسال گزارش‌های دوزبانه)
📊 /status | 🎨 /content | 📋 /list
✅ /approve | ❌ /reject
🔥 /trends | 📸 /topimages
🎨 /photo | 🔬 /analyze | 🎬 /reverse | 🎥 /makevideos
🖼 /setphoto شناسه (عکس دستی رو بفرست + این رو caption بذار)
🎬 /setvideo شناسه (ویدیوی دستی رو بفرست + این رو caption بذار)
🤖 /agents | 🐙 /github | 📝 /diary | 📤 /publish
💬 *هر پیام = چت با Gemini*"""

    elif text == "/publish":
        send(chat, "📤 *در حال انتشار...*", reply_to=mid)
        # Auto-route to Zernio (cloud) if configured, else Postiz.
        if os.environ.get("ZERNIO_API_KEY"):
            from agents.publisher_zernio import ZernioPublisher

            r = ZernioPublisher().run()
        else:
            from agents.publisher import Publisher

            r = Publisher().run()
        if r.get("error") == "no_token":
            resp = "⚠️ هیچ سرویس انتشاری تنظیم نشده. `ZERNIO_API_KEY` رو ست کن."
        elif r.get("error") == "no_accounts":
            resp = "⚠️ هیچ اکانتی در Zernio وصل نشده. اول اکانت‌ها رو وصل کن."
        else:
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

# Save offset locally...
save_offset(offset)
print(f"💾 Offset saved: {offset}")

# ...and CONFIRM it server-side with Telegram. Calling getUpdates with this
# offset tells Telegram those updates are handled, so they are dropped from the
# server queue even if committing the offset file back to git later fails. This
# is the key defense against re-processing the same messages.
if updates:
    try:
        requests.get(f"{BASE}/getUpdates?offset={offset}&timeout=1", timeout=10)
        print("✅ Offset confirmed with Telegram")
    except Exception as e:
        print("offset confirm error:", e)
