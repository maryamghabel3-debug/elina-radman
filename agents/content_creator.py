"""ContentCreator Agent — Generates captions and scripts."""

from typing import List, Optional
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

    def load_affiliate_products(self) -> list:
        db_path = "content/affiliate_products.json"
        if os.path.exists(db_path):
            with open(db_path, "r") as f:
                return json.load(f)
        return []

    def load_diary_feeling(self) -> str:
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

    def load_current_trends(self, limit: int = 6) -> List[str]:
        """Fetch the top current fashion trend topics from TrendHunter.

        Cached inside TrendHunter (6h), so this is cheap to call. Returns an
        empty list on any failure so caption generation never breaks.
        """
        try:
            from .trend_hunter import TrendHunter

            th = TrendHunter()
            th.run()  # uses cache when fresh
            return th.trend_summary(limit=limit)
        except Exception as e:
            self.log(f"Could not load trends: {e}", "error")
            return []

    def load_video_blueprints(self, limit: int = 3) -> List[dict]:
        """Load reverse-engineered recreation blueprints from TrendVideoAnalyzer.

        Returns a list of {source_title, concept, hook, shot_list, caption}
        derived from the viral videos we tore down. Empty list on any failure.
        """
        try:
            from .trend_video_analyzer import TrendVideoAnalyzer

            report = TrendVideoAnalyzer.load_latest()
            if not report:
                return []
            blueprints = []
            for a in report.get("analyses", [])[:limit]:
                td = a.get("teardown", {})
                rec = td.get("elina_recreation") or {}
                if rec:
                    blueprints.append(
                        {
                            "source_title": a.get("meta", {}).get("title"),
                            "why_viral": td.get("why_it_went_viral"),
                            "concept": rec.get("concept"),
                            "hook": rec.get("hook"),
                            "shot_list": rec.get("shot_list"),
                            "caption": rec.get("caption"),
                        }
                    )
            return blueprints
        except Exception as e:
            self.log(f"Could not load video blueprints: {e}", "error")
            return []

    def create_video_ideas(self, limit: int = 3) -> List[dict]:
        """Turn the latest viral-video teardowns into ready-to-shoot video content
        pieces for Elina (concept + hook + shot list + caption), queued for approval."""
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        blueprints = self.load_video_blueprints(limit=limit)
        pieces = []
        for i, bp in enumerate(blueprints):
            pid = f"elina-{datetime.now().strftime('%Y%m%d%H%M')}-vid{i}"
            pieces.append(
                {
                    "id": pid,
                    "pillar": "video_recreation",
                    "format": "video",
                    "caption": bp.get("caption") or "",
                    "hook": bp.get("hook"),
                    "shot_list": bp.get("shot_list"),
                    "inspired_by": bp.get("source_title"),
                    "why_source_went_viral": bp.get("why_viral"),
                    "hashtags": f"{cfg.BASE_TAGS} #ElinaRadman #AIInfluencer",
                    "platforms": ["tiktok", "instagram", "youtube"],
                    "status": "pending_approval",
                    "created_at": datetime.now().isoformat(),
                }
            )
        if pieces:
            os.makedirs("content/queue", exist_ok=True)
            fp = f"content/queue/video-{datetime.now().strftime('%Y%m%d%H%M')}.json"
            with open(fp, "w") as f:
                json.dump(pieces, f, indent=2, ensure_ascii=False)
            self.log(f"Created {len(pieces)} video ideas from viral teardowns → {fp}")
        return pieces

    def generate_dynamic_caption(self, pillar: str, products: list, trends: Optional[List[str]] = None) -> str:
        """
        Calls the LLMRouter (e.g., Claude or Gemini) to generate a fresh,
        context-aware caption. Uses Elina's Daily Diary to color the tone and
        the current fashion trends to keep content timely.
        Falls back to a curated per-pillar caption when no API key is available,
        so the pipeline never emits placeholder text.
        """
        current_feeling = self.load_diary_feeling()

        trend_line = ""
        if trends:
            trend_line = (
                f"Currently trending in fashion right now: {', '.join(trends[:5])}. "
                f"Naturally weave ONE relevant trend into the caption if it fits the pillar. "
            )

        prompt = (
            f"Write a short Instagram caption (3-4 lines) for Elina Radman, a petite "
            f"quiet-luxury fashion influencer. Content pillar: {pillar}. "
            f"Tone: warm, confident, explorer, psychologist. "
            f"Current emotional state: '{current_feeling}'. "
            f"{trend_line}"
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

    def run(self, pillars: Optional[List[str]] = None, count: int = 3, use_trends: bool = True) -> List[dict]:
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        # Pillars/tags come from the shared content_config (single source of truth)
        pillars = pillars or cfg.PILLARS

        # Load dynamic products found by ProductHunter
        products = self.load_affiliate_products()

        # Fetch trending topics once and feed them into every caption
        trends = self.load_current_trends() if use_trends else []
        if trends:
            self.log(f"Grounding content in {len(trends)} live trends")

        pieces = []
        for i in range(count):
            p = pillars[i % len(pillars)]
            pid = f"elina-{datetime.now().strftime('%Y%m%d%H%M')}-{p[:4]}"
            
            # Use the AI Copywriter method instead of hardcoded fallbacks
            caption_text = self.generate_dynamic_caption(p, products, trends=trends)

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
                "trends_used": trends[:5],
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
