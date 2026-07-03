"""
ELINA OS — Daily Content Generator
Uses Google Gemini API (FREE) to create scripts + captions
Runs on GitHub Actions — $0/month
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Make the repo root importable so we can share config with the agents package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents import content_config as cfg

# Shared, canonical brand/pillar/tag definitions (single source of truth)
BRAND = cfg.BRAND
TONE = cfg.TONE
AUDIENCE = cfg.AUDIENCE
# The daily job focuses on the first five core fashion pillars
PILLARS = cfg.PILLARS[:5]
TAGS = cfg.TAGS
BASE_TAGS = cfg.BASE_TAGS


def load_trends():
    """Fetch current fashion trends (cached in TrendHunter). Returns [] on error."""
    try:
        from agents.trend_hunter import TrendHunter

        th = TrendHunter()
        th.run()
        return th.trend_summary(limit=6)
    except Exception as e:
        print(f"Trend load skipped: {e}")
        return []


def run_deep_analysis():
    """Deep, AI-driven reverse-engineering of what's trending, so the rest of the
    daily pipeline can mimic it.

    1. Analyses top trending PHOTOS (outfit / pose / camera / lighting / palette)
       -> content/trend_visuals.json (feeds PromptEngineer's photo prompts).
    2. Reverse-engineers top trending VIDEOS (topic / hook / structure / why it
       went viral) -> content/trend_videos.json.
    3. Turns the video teardowns into ready-to-shoot video ideas queued for
       approval (content/queue/video-*.json).

    Every step is wrapped so a single failure never breaks the daily run. Set
    SKIP_DEEP_ANALYSIS=1 to skip entirely (e.g. to save API quota).
    """
    if os.environ.get("SKIP_DEEP_ANALYSIS") == "1":
        print("   ⏭  Deep analysis skipped (SKIP_DEEP_ANALYSIS=1)")
        return []

    # 1) Deep photo analysis
    try:
        from agents.trend_visual_analyzer import TrendVisualAnalyzer

        rep = TrendVisualAnalyzer().run(limit=4)
        print(
            f"   🔬 Analyzed {rep.get('images_analyzed', 0)} photos "
            f"({rep.get('deep_analyzed', 0)} deep) — "
            f"aesthetics: {rep.get('trending_aesthetics', [])}"
        )
    except Exception as e:
        print(f"   ⚠️  Photo analysis skipped: {e}")

    # 2) Video reverse-engineering
    try:
        from agents.trend_video_analyzer import TrendVideoAnalyzer

        vrep = TrendVideoAnalyzer().run(limit=3)
        print(f"   🎬 Reverse-engineered {vrep.get('videos_analyzed', 0)} viral videos")
    except Exception as e:
        print(f"   ⚠️  Video analysis skipped: {e}")

    # 3) Build video ideas from the teardowns
    video_ideas = []
    try:
        from agents.content_creator import ContentCreator

        video_ideas = ContentCreator().create_video_ideas(limit=3)
        if video_ideas:
            print(f"   🎥 Created {len(video_ideas)} video ideas from teardowns")
    except Exception as e:
        print(f"   ⚠️  Video idea generation skipped: {e}")

    return video_ideas


def load_visual_signals():
    """Read the reverse-engineered aesthetics/products from the deep photo
    analysis so captions can reference what's visually trending. Returns ''."""
    try:
        from agents.trend_visual_analyzer import TrendVisualAnalyzer

        rep = TrendVisualAnalyzer.load_latest_palette()
        if not rep:
            return ""
        bits = []
        if rep.get("trending_aesthetics"):
            bits.append("aesthetics: " + ", ".join(rep["trending_aesthetics"][:2]))
        if rep.get("trending_standout_products"):
            bits.append("hot pieces: " + ", ".join(rep["trending_standout_products"][:2]))
        return "; ".join(bits)
    except Exception:
        return ""


def generate(pillar, trends=None, visual_signals=""):
    api_key = os.environ.get("GEMINI_API_KEY", "")

    trend_line = ""
    if trends:
        trend_line = f"- Currently trending in fashion: {', '.join(trends[:5])}. Weave in ONE if relevant.\n"
    if visual_signals:
        trend_line += f"- Trending visuals right now ({visual_signals}). Reference subtly if it fits.\n"

    memory_ctx = ""
    try:
        from agents.memory_engine import MemoryEngine
        memory_ctx = "\n" + MemoryEngine().retrieve_context(pillar) + "\n"
    except Exception as e:
        print(f"MemoryEngine skipped: {e}")

    prompt = f"""You are {BRAND}. Tone: {TONE}. Audience: {AUDIENCE}.{memory_ctx}
Create an Instagram/TikTok caption (3-4 short lines) for content pillar: {pillar}.

Rules:
- Warm, helpful, relatable voice
- Include outfit or tip details referencing your philosophy/memory if applicable
{trend_line}- End with an engaging question
- Use 🕊️🤍✨ sparingly (max 2 emojis)
- NO hashtags (added separately)
- Keep lines short for mobile reading

Caption:"""

    caption = ""
    if api_key:
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            resp = model.generate_content(prompt)
            caption = resp.text.strip()
        except Exception as e:
            print(f"Gemini: {e}")

    if not caption:
        caption = cfg.fallback_for(pillar)

    # Fetch affiliate item recommendation for monetization
    affiliate_data = {}
    try:
        from agents.product_hunter import ProductHunter
        hunter = ProductHunter()
        affiliate_data = hunter.get_recommendation(pillar=pillar)
    except Exception as e:
        print(f"ProductHunter skipped: {e}")

    caption_fa = ""
    if api_key and caption:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model_fa = genai.GenerativeModel("gemini-2.5-flash")
            resp_fa = model_fa.generate_content(f"Translate and adapt this fashion influencer caption into warm, elegant Persian (Farsi) matching Elina Radman's voice:\n{caption}\nPersian:")
            caption_fa = resp_fa.text.strip()
        except Exception:
            pass
    if not caption_fa:
        caption_fa = f"استایل امروز الینا در تم {pillar} 🤍✨ نظر شما درباره این ست چیه؟"

    pid = f"elina-{datetime.now().strftime('%Y%m%d')}-{pillar[:4]}"
    return {
        "id": pid,
        "pillar": pillar,
        "caption": caption,
        "caption_fa": caption_fa,
        "hashtags": f"{TAGS.get(pillar, '')} {BASE_TAGS}",
        "platforms": ["instagram", "tiktok", "pinterest"],
        "trends_used": (trends or [])[:5],
        "affiliate_item": affiliate_data.get("name", ""),
        "affiliate_link": affiliate_data.get("affiliate_link", ""),
        "affiliate_cta": affiliate_data.get("cta", ""),
        "status": "pending_approval",
        "created_at": datetime.now().isoformat(),
        "scheduled_for": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        + "T10:00:00",
    }


def add_images(pieces):
    """Generate 5-shot carousel photos & short videos for each piece with high fashion styling logic."""
    try:
        from agents.prompt_engineer import PromptEngineerAgent
        pe = PromptEngineerAgent()
    except Exception:
        pe = None

    for p in pieces:
        concept = (p.get("caption") or "").split("\n")[0][:180] or p.get("pillar", "fashion")
        if pe:
            p["carousel_prompts"] = pe.generate_5_shot_carousel_prompts(concept, p.get("styling_logic_fa", ""))
            if not p.get("image_prompt") and p["carousel_prompts"]:
                p["image_prompt"] = p["carousel_prompts"][0]["prompt"]
            if not p.get("video_prompt"):
                p["video_prompt"] = pe.generate_cinematic_json_script(concept)
        p["styling_logic_fa"] = (
            f"👗 **منطق استایلینگ فشن (چرا این ست؟):** انتخابی لوکس و هوشمندانه متناسب با تم `{p['pillar']}`. "
            f"ترکیب خطوط عمودی، شلوار فاق‌بلند و برش‌های دقیق باعث می‌شود اندام پتیت الینا (۱۵۰ سانتی‌متر) بسیار کشیده‌تر و باابهت دیده شود. "
            f"هماهنگی بافت پارچه با کفش و اکسسوری‌ها، استایلی بی‌نقص و مجله‌ای می‌سازد."
        )

    # Also generate a real faceless short video clip for the first piece
    try:
        from agents.faceless_studio import FacelessStudio
        fs = FacelessStudio()
        for p in pieces[:1]:
            v_res = fs.run(p.get("pillar", "Quiet Luxury"))
            if v_res.get("video_path") and os.path.exists(v_res["video_path"]):
                p["video_path"] = v_res["video_path"]
                print(f"   🎬 Generated video short for {p['id']}")
    except Exception as e:
        print(f"   ⚠️ FacelessStudio skipped: {e}")

    if os.environ.get("IMAGES_OFF") == "1":
        print("   ⏭  Image generation skipped (IMAGES_OFF=1)")
        return
    try:
        from agents.image_studio import ImageStudio
    except Exception as e:
        print(f"   ⚠️  ImageStudio unavailable: {e}")
        return
    studio = ImageStudio()
    for p_idx, p in enumerate(pieces):
        concept = (p.get("caption") or "").split("\n")[0][:180] or p.get("pillar", "fashion")
        p["carousel_paths"] = []
        try:
            # For the first post piece, generate all 5 shots (full_body, portrait_detail, flat_lay, street_movement, candid_lifestyle)
            shots = p.get("carousel_prompts", [])[:5] if p_idx == 0 else p.get("carousel_prompts", [])[:3]
            if not shots:
                shots = [{"title_fa": "نمای اصلی", "prompt": concept}]
            for idx, shot in enumerate(shots):
                r = studio.generate(shot["prompt"])
                if r.get("path"):
                    p["carousel_paths"].append({"path": r["path"], "title": shot["title_fa"]})
                    if idx == 0:
                        p["image"] = r["path"]
                        p["image_provider"] = r.get("provider")
                        p["used_reference"] = r.get("used_reference", False)
                        p["image_warning"] = r.get("warning", "")
                    print(f"   🎨 shot {idx+1}/{len(shots)} ({shot['title_fa'][:20]}) via {r.get('provider')}")
        except Exception as e:
            print(f"   ⚠️  carousel generation error for {p['id']}: {e}")


def notify_telegram(pieces, video_ideas=None):
    video_ideas = video_ideas or []
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Telegram not configured")
        return
    try:
        import requests

        n_photos = sum(1 for p in pieces if p.get("image"))
        msg = (
            f"📋 *{len(pieces)} محتوای آماده + {n_photos} عکس + "
            f"{len(video_ideas)} ایده ویدیویی!*\n\n"
        )
        for p in pieces:
            cam = "🖼" if p.get("image") else "📝"
            aff = f"\n🛍 افیلیت: `{p.get('affiliate_item', '')}`" if p.get("affiliate_item") else ""
            msg += f"🆔 `{p['id']}`\n🏷 {p['pillar']}\n{cam} {p['caption'][:80]}...{aff}\n\n"
        for v in video_ideas:
            hook = (v.get("hook") or "")[:70]
            inspired = (v.get("inspired_by") or "")[:50]
            msg += f"🎥 `{v['id']}`\n🪝 {hook}\n💡 از: {inspired}\n\n"
        msg += "برای تأیید: `/approve شناسه`"
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
        # Send actual generated photos & videos with full styling logic and prompts
        for p in pieces:
            img = p.get("image")
            if img and os.path.exists(img):
                try:
                    photo_cap = f"📸 پست روزانه: `{p['id']}` ({p['pillar']})\n\n"
                    if p.get("caption_fa"):
                        photo_cap += f"🇮🇷 **کپشن فارسی:**\n{p['caption_fa'][:200]}\n\n"
                    photo_cap += f"🇬🇧 **Caption (EN):**\n{p['caption'][:200]}\n\n"
                    if p.get("affiliate_item"):
                        photo_cap += f"🛍 محصول افیلیت: {p['affiliate_item']}\n🔗 {p.get('affiliate_link', '')}\n"
                    photo_cap += f"\n👉 انتشار خودکار: `/approve {p['id']}`"
                    with open(img, "rb") as fh:
                        requests.post(
                            f"https://api.telegram.org/bot{token}/sendPhoto",
                            data={"chat_id": chat_id, "caption": photo_cap[:1000]},
                            files={"photo": fh},
                            timeout=60,
                        )
                    # Send additional carousel shots (portrait detail, flat lay without Elina, etc.)
                    for c_shot in p.get("carousel_paths", [])[1:]:
                        if os.path.exists(c_shot["path"]):
                            with open(c_shot["path"], "rb") as c_fh:
                                requests.post(
                                    f"https://api.telegram.org/bot{token}/sendPhoto",
                                    data={"chat_id": chat_id, "caption": f"🖼 {c_shot['title']}"},
                                    files={"photo": c_fh},
                                    timeout=60,
                                )
                    # Send generated short video if exists
                    vpath = p.get("video_path")
                    if vpath and os.path.exists(vpath):
                        with open(vpath, "rb") as vh:
                            v_res = requests.post(
                                f"https://api.telegram.org/bot{token}/sendVideo",
                                data={"chat_id": chat_id, "caption": f"🎬 ویدیوی ریلز تولیدشده برای پست `{p['id']}`"},
                                files={"video": vh},
                                timeout=120,
                            ).json()
                            print(f"   📤 sendVideo result for {p['id']}: {v_res.get('ok')}")
                    # Send detailed styling logic and 5-shot carousel prompts
                    prompt_msg = f"🎨 **گزارش تخصصی استایلینگ و ۵ پرامپت کاروسل برای پست `{p['id']}`:**\n\n"
                    prompt_msg += f"{p.get('styling_logic_fa', '')}\n\n"
                    for s_p in p.get("carousel_prompts", [])[:3]:
                        prompt_msg += f"🖼 **{s_p['title_fa']}:**\n```\n{s_p['prompt']}\n```\n\n"
                    if p.get("video_prompt"):
                        vp = p.get("video_prompt", "")[:400] + "..." if len(p.get("video_prompt", "")) > 400 else p.get("video_prompt", "")
                        prompt_msg += f"🎬 **پرامپت ویدیویی:**\n```\n{vp}\n```"
                    requests.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": prompt_msg[:4000], "parse_mode": "Markdown"},
                        timeout=20,
                    )
                except Exception as e:
                    print(f"photo send error: {e}")
        print("Telegram sent")
    except Exception as e:
        print(f"Telegram error: {e}")


def main():
    print("🕊️ ELINA OS — Generating content...")
    os.makedirs("content/queue", exist_ok=True)

    # 1) Deep reverse-engineering of trending photos + videos FIRST, so the
    #    photo prompts and captions below are grounded in fresh analysis.
    print("🔬 Running deep trend analysis...")
    video_ideas = run_deep_analysis()

    # 2) Trend topics for caption grounding
    trends = load_trends()
    if trends:
        print(f"   🔥 Grounding in {len(trends)} live trends")

    # 3) Daily photo/caption pieces (grounded in trends + deep visual signals)
    visual_signals = load_visual_signals()
    if visual_signals:
        print(f"   🎨 Visual signals: {visual_signals}")
    pieces = [
        generate(PILLARS[i % len(PILLARS)], trends=trends, visual_signals=visual_signals)
        for i in range(3)
    ]
    for p in pieces:
        print(f"   ✅ {p['id']} — {p['pillar']}")

    # 4) Generate a real photo for each piece
    print("🎨 Generating photos...")
    add_images(pieces)

    fp = f"content/queue/{datetime.now().strftime('%Y%m%d')}.json"
    with open(fp, "w") as f:
        json.dump(pieces, f, indent=2)

    total = len(pieces) + len(video_ideas)
    print(f"📁 {fp} | 📋 {len(pieces)} captions + 🎥 {len(video_ideas)} video ideas ready")
    notify_telegram(pieces, video_ideas)


if __name__ == "__main__":
    main()
