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


def generate(pillar, trends=None):
    api_key = os.environ.get("GEMINI_API_KEY", "")

    trend_line = ""
    if trends:
        trend_line = f"- Currently trending in fashion: {', '.join(trends[:5])}. Weave in ONE if relevant.\n"

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


def notify_telegram(pieces):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Telegram not configured")
        return
    try:
        import requests

        msg = f"📋 *{len(pieces)} new content pieces ready!*\n\n"
        for p in pieces:
            msg += f"🆔 `{p['id']}`\n🏷 {p['pillar']}\n📝 {p['caption'][:80]}...\n\n"
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

    trends = load_trends()
    if trends:
        print(f"   🔥 Grounding in {len(trends)} live trends")

    pieces = [generate(PILLARS[i % len(PILLARS)], trends=trends) for i in range(3)]
    for p in pieces:
        print(f"   ✅ {p['id']} — {p['pillar']}")

    fp = f"content/queue/{datetime.now().strftime('%Y%m%d')}.json"
    with open(fp, "w") as f:
        json.dump(pieces, f, indent=2)

    print(f"📁 {fp} | 📋 {len(pieces)} pieces ready")
    notify_telegram(pieces)


if __name__ == "__main__":
    main()
