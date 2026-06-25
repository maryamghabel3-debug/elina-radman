"""
ELINA OS — Daily Content Generator
Uses Google Gemini API (FREE) to create scripts + captions
Runs on GitHub Actions — $0/month
"""

import os
import json
from datetime import datetime, timedelta

PILLARS = ["petite_styling", "ootd", "capsule_wardrobe", "smart_shopping", "lifestyle"]

BRAND = "Elina Radman | Petite Quiet Luxury | 4'11\" (150cm) | 43kg"
TONE = "warm, sophisticated, relatable, like a stylish best friend"
AUDIENCE = "petite women 18-35 who want to look expensive on a budget"

TAGS = {
    "petite_styling": "#PetiteStyle #StyleTips #ShortGirlFashion #FashionHacks #LookTaller",
    "ootd": "#OOTD #OutfitOfTheDay #PetiteStyle #QuietLuxury #4ft11",
    "capsule_wardrobe": "#CapsuleWardrobe #MinimalistStyle #PetiteStyle #WardrobeEssentials",
    "smart_shopping": "#AffordableStyle #SmartShopping #PetiteHaul #QuietLuxury",
    "lifestyle": "#DayInMyLife #PetiteStyle #QuietLuxury #LifeStyleCreator",
}
BASE_TAGS = "#StyledByElina #PetiteFashion"


def generate(pillar):
    api_key = os.environ.get("GEMINI_API_KEY", "")

    prompt = f"""You are {BRAND}. Tone: {TONE}. Audience: {AUDIENCE}.
Create an Instagram/TikTok caption (3-4 short lines) for content pillar: {pillar}.

Rules:
- Warm, helpful, relatable voice
- Include outfit or tip details
- End with an engaging question
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
        fallbacks = {
            "petite_styling": "3 style rules every petite needs 🕊️\n\n1. High-waisted everything — elongates legs\n2. Monochrome outfits — no visual break\n3. Tailor everything — $15 = looks like $500\n\nWhich rule do you already follow? 👇",
            "ootd": "Today's OOTD: Quiet Luxury 🕊️\n\nCropped camel blazer + high-waist trousers\nEvery piece tailored for 4'11\" ✨\n\nWhat are you wearing today? 👇",
            "capsule_wardrobe": "15 pieces = 30+ outfits 🤍\n\nMy petite capsule wardrobe system:\n3 bottoms + 4 tops + 2 blazers + 2 dresses\nAll neutral. Everything matches.\n\nComment CAPSULE for the list 📩",
            "smart_shopping": "Look expensive without the price tag 💰\n\n1. Natural fabrics only\n2. Neutral color palette\n3. Tailor everything\n4. Less is more\n\nYour best budget style tip? 👇",
            "lifestyle": "A day in my outfits ☕\n\nMorning coffee → afternoon stroll → evening dinner\nSame base pieces, three different looks\n\nThis is capsule wardrobe magic ✨",
        }
        caption = fallbacks.get(pillar, fallbacks["ootd"])

    pid = f"elina-{datetime.now().strftime('%Y%m%d')}-{pillar[:4]}"
    return {
        "id": pid,
        "pillar": pillar,
        "caption": caption,
        "hashtags": f"{TAGS.get(pillar, '')} {BASE_TAGS}",
        "platforms": ["instagram", "tiktok", "pinterest"],
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

    pieces = [generate(PILLARS[i % len(PILLARS)]) for i in range(3)]
    for p in pieces:
        print(f"   ✅ {p['id']} — {p['pillar']}")

    fp = f"content/queue/{datetime.now().strftime('%Y%m%d')}.json"
    with open(fp, "w") as f:
        json.dump(pieces, f, indent=2)

    print(f"📁 {fp} | 📋 {len(pieces)} pieces ready")
    notify_telegram(pieces)


if __name__ == "__main__":
    main()
