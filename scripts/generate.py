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

    prompt = f"""You are {BRAND}. Tone: {TONE}. Audience: {AUDIENCE}.
Create an Instagram/TikTok caption (3-4 short lines) for content pillar: {pillar}.

Rules:
- Warm, helpful, relatable voice
- Include outfit or tip details
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

    pid = f"elina-{datetime.now().strftime('%Y%m%d')}-{pillar[:4]}"
    return {
        "id": pid,
        "pillar": pillar,
        "caption": caption,
        "hashtags": f"{TAGS.get(pillar, '')} {BASE_TAGS}",
        "platforms": ["instagram", "tiktok", "pinterest"],
        "trends_used": (trends or [])[:5],
        "status": "pending_approval",
        "created_at": datetime.now().isoformat(),
        "scheduled_for": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        + "T10:00:00",
    }


def notify_telegram(pieces, video_ideas=None):
    video_ideas = video_ideas or []
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Telegram not configured")
        return
    try:
        import requests

        msg = f"📋 *{len(pieces)} captions + {len(video_ideas)} video ideas ready!*\n\n"
        for p in pieces:
            msg += f"🆔 `{p['id']}`\n🏷 {p['pillar']}\n📝 {p['caption'][:80]}...\n\n"
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

    fp = f"content/queue/{datetime.now().strftime('%Y%m%d')}.json"
    with open(fp, "w") as f:
        json.dump(pieces, f, indent=2)

    total = len(pieces) + len(video_ideas)
    print(f"📁 {fp} | 📋 {len(pieces)} captions + 🎥 {len(video_ideas)} video ideas ready")
    notify_telegram(pieces, video_ideas)


if __name__ == "__main__":
    main()
