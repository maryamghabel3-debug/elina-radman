"""ContentCreator Agent — Generates captions and scripts"""

from .base import Agent
from datetime import datetime, timedelta
import os
import json
import random

class ContentCreator(Agent):
    def __init__(self):
        super().__init__("ContentCreator", "Expert Copywriter Agent — Dynamically generates captions using LLMs")
        # In a real setup, this would connect to the LLMRouter
        # self.llm = LLMRouter()

    def load_affiliate_products(self):
        db_path = "content/affiliate_products.json"
        if os.path.exists(db_path):
            with open(db_path, "r") as f:
                return json.load(f)
        return []

    def load_diary_feeling(self):
        """Reads Elina's current emotional state from her diary"""
        diary_path = "content/elina_diary.json"
        if os.path.exists(diary_path):
            with open(diary_path, "r") as f:
                entries = json.load(f)
                if entries:
                    return entries[-1]["feeling"]
        return "Calm, focused, and ready to inspire."

    # Offline fallback captions per pillar (used when no LLM key is configured)
    FALLBACK_CAPTIONS = {
        "petite_styling": "3 style rules every petite needs 🕊️\n\n1. High-waisted everything — elongates legs\n2. Monochrome outfits — no visual break\n3. Tailor everything\n\nWhich rule do you already follow? 👇",
        "ootd": "Today's OOTD: Quiet Luxury 🕊️\n\nCropped camel blazer + high-waist trousers\nEvery piece tailored for 4'11\" ✨\n\nWhat are you wearing today? 👇",
        "capsule_wardrobe": "15 pieces = 30+ outfits 🤍\n\n3 bottoms + 4 tops + 2 blazers + 2 dresses\nAll neutral. Everything matches.\n\nComment CAPSULE for the list 📩",
        "smart_shopping": "Look expensive without the price tag 💰\n\nNatural fabrics · neutral palette · tailor everything.\n\nYour best budget style tip? 👇",
        "lifestyle": "A day in my outfits ☕\n\nSame base pieces, three different looks.\nThis is capsule wardrobe magic ✨\n\nWhat does your day look like? 👇",
    }

    def generate_dynamic_caption(self, pillar, products):
        """
        Calls the LLMRouter (e.g., Claude or Gemini) to generate a fresh,
        context-aware caption. Uses Elina's Daily Diary to color the tone.
        Falls back to a curated per-pillar caption when no API key is available,
        so the pipeline never emits placeholder text.
        """
        current_feeling = self.load_diary_feeling()

        prompt = (
            f"Write a short Instagram caption (3-4 lines) for Elina Radman, a petite "
            f"quiet-luxury fashion influencer. Content pillar: {pillar}. "
            f"Tone: warm, confident, explorer, psychologist. "
            f"Current emotional state: '{current_feeling}'. "
            f"Blend her current feelings subtly into the content. Use at most 2 emojis, "
            f"end with an engaging question, and do NOT include hashtags."
        )

        generated_caption = ""
        try:
            from .llm_router import LLMRouter
            router = LLMRouter()
            result = router.smart_generate(
                prompt,
                task_type="creative_writing",
                system_prompt="You are Elina Radman, an authentic petite fashion influencer and psychologist.",
            )
            text = (result or {}).get("response", "") or ""
            # Ignore simulation/error stubs from the router
            if text and not text.startswith("[Simulation") and not text.startswith("Error calling"):
                generated_caption = text.strip()
        except Exception as e:
            self.log(f"LLM caption generation failed, using fallback: {e}", "error")

        if not generated_caption:
            generated_caption = self.FALLBACK_CAPTIONS.get(
                pillar,
                self.FALLBACK_CAPTIONS["ootd"],
            )
        
        # Smart Monetization Injection
        if pillar in ["ootd", "petite_styling", "smart_shopping"] and products:
            prod = random.choice(products)
            affiliate_section = (
                f"\n\n✨ Found the perfect {prod['name']} from {prod['brand']} "
                f"({prod['why_it_fits']})! \n"
                f"🛒 Shop here: {prod['affiliate_link']}"
            )
            generated_caption += affiliate_section
            
        return generated_caption

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
            "psychology_of_style",
            "horticulture_and_growth"
        ]

        tags = {
            "petite_styling": "#PetiteStyle #StyleTips #ShortGirlFashion #LTKunder50",
            "ootd": "#OOTD #PetiteStyle #QuietLuxury #4ft11 #LTKit",
            "capsule_wardrobe": "#CapsuleWardrobe #MinimalistStyle #PetiteStyle",
            "smart_shopping": "#AffordableStyle #SmartShopping #QuietLuxury",
            "lifestyle": "#Explorer #LifeStyleCreator #IndependentWoman #GrowthMindset",
            "ai_tech_hacks": "#AITech #TechTips #OutfitPlanner #TechGirl",
            "psychology_of_style": "#FashionPsychology #Confidence #MentalHealth #Mindset",
            "horticulture_and_growth": "#Horticulture #PlantTherapy #NatureLover #Growth",
        }

        # Load dynamic products found by ProductHunter
        products = self.load_affiliate_products()

        pieces = []
        for i in range(count):
            p = pillars[i % len(pillars)]
            pid = f"elina-{datetime.now().strftime('%Y%m%d%H%M')}-{p[:4]}"
            
            # Use the AI Copywriter method instead of hardcoded fallbacks
            caption_text = self.generate_dynamic_caption(p, products)

            # Smart targeting for monetization platforms
            target_platforms = ["instagram", "tiktok"]
            if p == "ai_tech_hacks":
                target_platforms.extend(["youtube", "threads"])
            elif p in ["ootd", "petite_styling"]:
                target_platforms.extend(["pinterest", "lemon8"])

            piece = {
                "id": pid,
                "pillar": p,
                "caption": caption_text,
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
