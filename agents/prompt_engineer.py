"""
Prompt Engineering Agent for AI Image & Video
Generates highly structured, professional, and cinematic prompts based on the 
"Aduni 5-Part Formula" for Photos and the "Seedance JSON Script" format for Videos.
"""
from .base import Agent
import random
import json
from datetime import datetime

class PromptEngineerAgent(Agent):
    def __init__(self):
        super().__init__("PromptEngineer", "Expert Prompt Engineer for Cinematic AI Media")
        # Base identity locks (Never change)
        self.base_subject = "A 24-year-old Iranian woman with warm wheat skin, soft dark brown eyes, petite frame, and full lips with subtle nude lip color"

    def determine_dynamic_styling(self, base_concept):
        """Intelligently changes Elina's hair and style based on the prompt context"""
        concept_lower = base_concept.lower()
        if "nature" in concept_lower or "garden" in concept_lower or "plant" in concept_lower:
            return "hair tied in a loose messy braid with a few strands escaping, no-makeup makeup look, wearing a cozy oversized earth-toned linen shirt"
        elif "cafe" in concept_lower or "city" in concept_lower or "coffee" in concept_lower:
            return "long dark brown hair tucked effortlessly behind her ears, subtle gold hoop earrings, wearing a tailored petite camel trench coat"
        elif "sad" in concept_lower or "vulnerable" in concept_lower or "therapist" in concept_lower:
            return "hair casually gathered in a low soft ponytail, bare-faced and raw, wearing a comforting oversized knit sweater"
        elif "luxury" in concept_lower or "event" in concept_lower or "evening" in concept_lower:
            return "dark brown hair styled in a sleek low bun, sharp minimal eyeliner, wearing a perfectly fitted black blazer"
        else:
            return "long wavy dark brown hair flowing naturally, minimal soft aesthetic, wearing effortless neutral-toned basics"

    def trending_palette_phrase(self):
        """Turn the latest TrendVisualAnalyzer report into a rich prompt phrase.

        Uses not just the colour palette but the reverse-engineered creative
        direction (aesthetic, camera angle, hero product) when available.
        Returns an empty string when no analysis exists, so the prompt is
        unchanged in that case.
        """
        try:
            from .trend_visual_analyzer import TrendVisualAnalyzer

            report = TrendVisualAnalyzer.load_latest_palette()
            if not report:
                return ""

            parts = []
            tones = report.get("dominant_tones", [])[:3]
            hexes = report.get("top_colors", [])[:3]
            if tones:
                p = f"color-graded toward trending tones ({', '.join(tones)}"
                if hexes:
                    p += f"; palette {', '.join(hexes)}"
                p += ")"
                parts.append(p)

            # Deep reverse-engineered signals (outfit/pose/camera)
            aesthetics = report.get("trending_aesthetics", [])
            if aesthetics:
                parts.append(f"styled in the currently-trending {', '.join(aesthetics[:2])} aesthetic")
            products = report.get("trending_standout_products", [])
            if products:
                parts.append(f"featuring on-trend pieces like {products[0]}")
            angles = report.get("trending_camera_angles", [])
            if angles:
                parts.append(f"shot from a {angles[0]} angle popular in trending posts")
            poses = report.get("sample_poses", [])
            if poses:
                # keep it short - poses can be long sentences
                parts.append(f"pose inspired by trends: {str(poses[0])[:80]}")

            return ", ".join(parts)
        except Exception as e:
            self.log(f"Could not load trending analysis: {e}", "error")
            return ""

    def generate_photo_prompt(self, base_concept, tone="Quiet Luxury", use_trending_palette=True):
        """Aduni's 5-Part Formula for stunning AI photos"""
        self.log(f"Engineering 5-Part photo prompt for: {base_concept}")
        
        dynamic_styling = self.determine_dynamic_styling(base_concept)
        subject_with_style = f"{self.base_subject}, {dynamic_styling}"
        
        # Style logic
        style_desc = "editorial fashion photography style with magazine-cover composition"
        if tone == "Quiet Luxury":
            style_desc = "minimalist quiet luxury aesthetic with a soft neutral palette of cream, beige, and warm white"
        elif tone == "Dark Cinematic":
            style_desc = "dark cinematic aesthetic with chiaroscuro lighting, film-still quality"
        else:
            style_desc = "documentary realism, raw and grounded"
            
        camera_lens = random.choice([
            "shot on a medium format camera with 85mm lens at f/2.8, shallow depth of field, creamy bokeh",
            "shot on an anamorphic lens at f/2.0, cinematic aspect ratio",
            "shot on 35mm lens, lifestyle documentary feel"
        ])
        
        lighting = random.choice([
            "soft diffused natural window light, calm and refined mood",
            "soft natural light from the left with warm golden hour tones",
            "single dramatic spotlight from above cutting through shadow, deep cinematic shadows"
        ])

        # Inject the palette learned from what's currently going viral
        palette_phrase = self.trending_palette_phrase() if use_trending_palette else ""
        palette_part = f", {palette_phrase}" if palette_phrase else ""

        # 4-Layer Monetization-Ready Prompt Architecture (2026 Standard)
        layer_0_identity = f"{self.base_subject}, {dynamic_styling}, maintaining exact facial features and natural proportions"
        layer_1_scene = f"Wide-angle full-body candid fashion shot from head to toe: {base_concept}. Framed from a distance so her complete outfit, trousers length, and shoes are 100% visible without cropping. Authentic environment with realistic background depth."
        layer_2_style = f"High-fashion styling: {style_desc}{palette_part}. Impeccable tailoring creating an elongated, elegant silhouette."
        layer_3_camera = (
            f"{camera_lens}, {lighting}. Real-world photography characteristics: natural detailed skin texture, "
            f"visible micro-pores, soft organic facial highlights, Kodak Portra 400 film grain, shallow depth of field. "
            f"Unfiltered UGC influencer aesthetic with zero CGI, 3D render, or artificial beauty airbrushing."
        )

        return f"{layer_0_identity}. {layer_1_scene} {layer_2_style} {layer_3_camera}"

    def generate_cinematic_json_script(self, base_concept, tone="dark"):
        """
        Applies Aduni's advanced JSON-style directed workflow (like the Food Film example).
        Outputs a precise JSON structure that controls environment, camera, and speed ramping.
        """
        self.log(f"Engineering JSON-style directed video prompt for: {base_concept}")
        
        script_payload = {
            "scene_duration": "15 seconds",
            "style": {
                "environment": f"High-end minimalist setting, {tone} aesthetic, dramatic negative space",
                "lighting": "High-contrast chiaroscuro: cold silver-white key light cutting across the subject, hard shadows",
                "effects": "dust particles floating in the air, slow-motion fabric movement catching the light"
            },
            "references": {
                "character_identity": f"@[Image 1] ({self.base_subject}, {self.determine_dynamic_styling(base_concept)})"
            },
            "camera_language": {
                "general": "cinematic pacing — whip-pans, snap cuts, bullet-time freezes, aggressive push-ins, low-angle hero shots",
                "lenses": "24mm for wide action, 100mm macro for fabric/skin texture"
            },
            "sequence": [
                {
                    "time": "0-5s",
                    "hook": f"COLD OPEN: Extreme close-up on Elina. Dead silence implied. Then she executes a deliberate action ({base_concept}) in ultra-slow-motion, catching the cold silver light.",
                    "camera": "extreme macro -> ultra-slow-motion wide shot -> fast whip-pan to face",
                    "speed_ramp": "1x (pause) -> 0.1x (action) -> 2x (whip-pan)"
                },
                {
                    "time": "5-10s",
                    "hook": "THE REVEAL: Elina looks directly at the lens. Cold composed energy. Every gesture intentional.",
                    "camera": "low dutch-angle tracking shot -> snap cut to extreme macro -> fast push-in",
                    "speed_ramp": "1.5x -> 0.2x (reveal to camera) -> 1.5x"
                },
                {
                    "time": "10-15s",
                    "hook": "THE FINALE: Final freeze frame, epic lighting holding the tension. Pulls wide and fast.",
                    "camera": "cut from black -> fast push-in -> extreme low-angle ground hero shot -> hard freeze frame hold",
                    "speed_ramp": "2x -> 0.1x -> freeze"
                }
            ]
        }
        
        return json.dumps(script_payload, indent=2)

    def run(self, base_concept, format_type="photo", tone="dark"):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        
        if format_type == "photo":
            return self.generate_photo_prompt(base_concept, tone)
        else:
            return self.generate_cinematic_json_script(base_concept, tone)
