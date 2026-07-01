"""ContentCreator Agent — Generates captions and scripts"""

from .base import Agent
from . import content_config as cfg
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

    # Offline fallback captions live in the shared content_config module so the
    # bot/dashboard path and the GitHub Actions path stay in sync.
    FALLBACK_CAPTIONS = cfg.FALLBACK_CAPTIONS

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
        # Pillars/tags come from the shared content_config (single source of truth)
        pillars = pillars or cfg.PILLARS

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
                "hashtags": f"{cfg.tags_for(p)} #ElinaRadman #AIInfluencer",
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
