"""ContentCreator Agent — Generates captions and scripts"""

from .base import Agent
from datetime import datetime, timedelta
import os
import json
import random

class ContentCreator(Agent):
    def __init__(self):
        super().__init__("ContentCreator", "Generates content pieces and injects Affiliate Links")

    def load_affiliate_products(self):
        db_path = "content/affiliate_products.json"
        if os.path.exists(db_path):
            with open(db_path, "r") as f:
                return json.load(f)
        return []

    def run(self, pillars=None, count=3):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        pillars = pillars or [
            "petite_styling",
            "ootd",
            "capsule_wardrobe",
            "smart_shopping",
            "lifestyle",
            "ai_tech_hacks",
            "psychology_of_style"
        ]

        # Integrated Affiliate / Monetization Hooks
        fallback = {
            "petite_styling": "3 style rules every petite needs 🕊️\n\n1. High-waisted everything\n2. Monochrome = taller\n3. Tailor everything\n\nSave this 📌 Link in bio for my favorite high-waisted trousers! 👇",
            "ootd": "Today's OOTD: Quiet Luxury 🕊️\n\nCropped camel blazer + high-waist trousers\nEvery piece tailored for 4'11\" ✨\n\nShop my exact look via the LTK link in my bio 🤍",
            "capsule_wardrobe": "15 pieces. 30+ outfits. My petite capsule 🤍\n\nAll neutral. Everything matches.\n\nComment CAPSULE and I'll DM you my free guide on how to build one! 📩",
            "smart_shopping": "Look expensive on a budget 💰\n\n1. Natural fabrics 2. Neutral colors\n3. Tailor everything 4. Less is more\n\nGrab my Lightroom presets (Link in Bio) to make your photos look expensive too! ✨",
            "lifestyle": "Recharging in nature today 🌿\n\nEarthy tones and fresh air are my ultimate therapy.\nWhat's your favorite way to unplug? ☕",
            "ai_tech_hacks": "How I plan my outfits using AI 🤖✨\n\nI use ChatGPT to build a smart wardrobe schedule.\nWant the prompt I use? Check the link in my bio! 🔗",
            "psychology_of_style": "Enclothed Cognition: Why your outfit changes your mood 🧠✨\n\nAs a psychologist, I know that wearing structured clothes actually makes you feel more confident and focused. \n\nDress for the mindset you want today. 🤍",
        }
        tags = {
            "petite_styling": "#PetiteStyle #StyleTips #ShortGirlFashion #LTKunder50",
            "ootd": "#OOTD #PetiteStyle #QuietLuxury #4ft11 #LTKit",
            "capsule_wardrobe": "#CapsuleWardrobe #MinimalistStyle #PetiteStyle",
            "smart_shopping": "#AffordableStyle #SmartShopping #QuietLuxury",
            "lifestyle": "#NatureLover #Mindfulness #PetiteStyle #LifeStyleCreator",
            "ai_tech_hacks": "#AITech #TechTips #OutfitPlanner #TechGirl",
            "psychology_of_style": "#FashionPsychology #Confidence #MentalHealth #Mindset",
        }

        # Load dynamic products found by ProductHunter
        products = self.load_affiliate_products()

        pieces = []
        for i in range(count):
            p = pillars[i % len(pillars)]
            pid = f"elina-{datetime.now().strftime('%Y%m%d%H%M')}-{p[:4]}"
            
            # Dynamic Affiliate Link Injection
            caption_text = fallback.get(p, fallback["ootd"])
            if p in ["ootd", "petite_styling", "smart_shopping"] and products:
                # Pick a random product matching the aesthetic
                prod = random.choice(products)
                affiliate_section = (
                    f"\n\n✨ Found the perfect {prod['name']} from {prod['brand']} "
                    f"({prod['why_it_fits']})! \n"
                    f"🛒 Shop here: {prod['affiliate_link']}"
                )
                caption_text += affiliate_section

            # Smart targeting for monetization platforms
            target_platforms = ["instagram", "tiktok"]
            if p == "ai_tech_hacks":
                target_platforms.extend(["youtube", "threads"])
            elif p in ["ootd", "petite_styling"]:
                target_platforms.extend(["pinterest", "lemon8"])

            piece = {
                "id": pid,
                "pillar": p,
                "caption": fallback.get(p, fallback["ootd"]),
                "hashtags": f"{tags.get(p,'')} #ElinaRadman #AIInfluencer",
                "platforms": target_platforms,
                "status": "pending_approval",
                "created_at": datetime.now().isoformat(),
                "scheduled_for": (datetime.now() + timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )
                + "T10:00:00",
            }
            pieces.append(piece)

        os.makedirs("content/queue", exist_ok=True)
        fp = f"content/queue/{datetime.now().strftime('%Y%m%d%H%M')}.json"
        with open(fp, "w") as f:
            json.dump(pieces, f, indent=2)

        self.log(f"Created {len(pieces)} pieces → {fp}")
        return pieces
