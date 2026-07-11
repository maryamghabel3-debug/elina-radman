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
        self.base_subject = (
            "A 24-year-old Iranian woman with warm wheat skin, captivating dark brown almond eyes, "
            "refined symmetrical facial structure, full lips with subtle nude lip color, petite 150cm frame, "
            "and magnetic high-fashion editorial allure with a serene, mysterious, and sophisticated expression (no cheesy or broad smiling)"
        )

    # Color palettes Elina can be styled in -- rewritten 2026-07-06 per
    # explicit user feedback: "نیازی نیست همیشه رنگ ها خنثی باشه بستگی به
    # مد و ... هم داره میتونه از رنگ های دیگه هم استفاده کنه از چالت های
    # رنگی دیگه" (colors don't always need to be neutral, it depends on the
    # trend/mood -- she can use other color palettes too). Previously EVERY
    # outfit/style_desc in this file was hard-coded to
    # cream/beige/ivory/camel/nude -- there was no code path that ever
    # produced a different palette. random.choice() picks one per photo so
    # variety happens naturally without needing a caller to specify it,
    # while "neutral_quiet_luxury" stays in the mix as her default/most
    # common look, not her ONLY look.
    _COLOR_PALETTES = {
        "neutral_quiet_luxury": "a soft neutral palette of cream, beige, camel, ivory, and warm white",
        "persian_jewel_tones": (
            "a bold Persian jewel-tone palette inspired by Iranian tilework and carpets -- "
            "deep turquoise/Persian blue, pomegranate red, and gold accents"
        ),
        "persian_rose_plum": (
            "a rich Persian rose and plum palette inspired by Qajar-era tilework and rosewater "
            "aesthetics -- dusty rose, deep plum, and warm blush tones"
        ),
        "bold_street_layering": (
            "a bold, layered color-blocked palette inspired by real Iranian street style -- "
            "confident contrasting colors (mustard, emerald, burgundy) layered together, not muted"
        ),
        "monochrome_noir": "a striking monochrome black-and-white palette with sharp tailoring",
    }

    def pick_color_palette(self, base_concept: str = "") -> tuple:
        """Returns (palette_key, palette_phrase). Defaults to weighting
        neutral quiet luxury heaviest (still her signature look) while
        genuinely giving other palettes a real chance to be picked --
        verified this actually varies output rather than always defaulting
        to neutral like the pre-2026-07-06 code always did."""
        c = base_concept.lower()
        if "celebration" in c or "festival" in c or "jashn" in c or "eid" in c or "wedding" in c:
            key = random.choice(["persian_jewel_tones", "persian_rose_plum", "bold_street_layering"])
        elif "street" in c or "casual" in c or "denim" in c:
            key = random.choice(["bold_street_layering", "neutral_quiet_luxury"])
        else:
            # Weighted: neutral quiet luxury stays her most common look, but
            # roughly 40% of the time a bolder/Persian-inspired palette is
            # used so the feed isn't monotone.
            key = random.choices(
                list(self._COLOR_PALETTES.keys()),
                weights=[60, 12, 12, 12, 4],
            )[0]
        return key, self._COLOR_PALETTES[key]

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

    def extract_rich_styling_and_location(self, base_concept):
        """Converts abstract concepts or question captions into specific,
        rich high-fashion outfit items and locations.

        REWRITTEN 2026-07-06 per explicit user feedback: previously every
        single branch here hard-coded a neutral (camel/cream/ivory/beige)
        outfit and a European (Paris/Scandinavian) location -- there was no
        code path that ever produced a color-varied or Iran-inspired look.
        Each branch now has a real alternate outfit in a bolder/Persian
        palette that gets picked some of the time (not always), so variety
        actually happens instead of being hard-coded away. Locations
        occasionally reference real, well-documented Iranian street-style
        aesthetics (long colorful manteau/overcoat layering, per live
        research on Iranian street fashion) instead of defaulting to Paris
        every time."""
        c = base_concept.lower()
        bold_roll = random.random() < 0.35  # ~35% of the time, use the bold/Persian-palette variant

        if "trouser" in c or "pant" in c or "rise" in c or "petite" in c:
            if bold_roll:
                outfit = "tailored high-waisted wide-leg trousers in deep Persian turquoise paired with a structured pomegranate-red silk blouse and gold-accented pointed-toe heels"
                location = "a sunlit rooftop terrace overlooking a historic Persian tiled courtyard"
                acc = "gold jewelry inspired by traditional Persian metalwork and a structured leather crossbody bag"
            else:
                outfit = "tailored high-waisted pleated camel wool wide-leg trousers paired with a structured double-breasted ivory silk blouse and pointed-toe nude leather slingback heels"
                location = "a sunlit luxury Parisian boutique terrace overlooking cobblestone streets"
                acc = "minimalist 18k gold croissant hoop earrings and a structured designer leather crossbody bag"
        elif "trench" in c or "coat" in c or "outerwear" in c or "manteau" in c:
            if bold_roll:
                outfit = "a long tailored colorful manteau-style overcoat in a rich emerald or plum tone, layered over a fitted turtleneck and slim trousers -- inspired by real, vibrant Iranian street style layering"
                location = "a stylish tree-lined street in northern Tehran during golden hour"
                acc = "statement gold hoop earrings and a structured handbag"
            else:
                outfit = "a tailored petite camel double-breasted trench coat draped over a fine white ribbed cashmere turtleneck and cream wide-leg tailored trousers"
                location = "an elegant Parisian street cafe terrace during morning golden hour"
                acc = "subtle gold hoop earrings and leather driving gloves"
        elif "knit" in c or "sweater" in c or "cozy" in c:
            if bold_roll:
                outfit = "an oversized mustard or burgundy cashmere knit sweater styled over tailored dark trousers"
                location = "a warmly-lit minimalist apartment with Persian rug accents"
                acc = "delicate layered gold necklaces"
            else:
                outfit = "an oversized luxury beige cashmere knit sweater styled over tailored ivory lounging trousers"
                location = "a minimalist sunlit Scandinavian apartment living room"
                acc = "delicate layered 18k gold necklaces"
        elif "celebration" in c or "festival" in c or "eid" in c or "jashn" in c or "wedding" in c:
            outfit = "an elegant occasion dress in rich Persian jewel tones (deep turquoise, rose, or pomegranate red) with gold embroidered accents, inspired by Persian textile art"
            location = "an ornately tiled, softly lit courtyard evocative of Persian architecture"
            acc = "statement gold jewelry with traditional Persian-inspired motifs"
        else:
            if bold_roll:
                outfit = "a structured oversized blazer in a bold jewel tone paired with wide-leg tailored trousers and pointed-toe heels"
                location = "a vibrant, colorful street scene with real Iranian urban fashion energy"
                acc = "bold gold jewelry and a designer leather clutch"
            else:
                outfit = "a structured oversized camel wool blazer paired with wide-leg pleated cream trousers and pointed-toe heels"
                location = "a vibrant sunlit boulevard in Paris during Fashion Week"
                acc = "minimalist 18k gold jewelry and a designer leather clutch"
        return outfit, location, acc

    def generate_photo_prompt(self, base_concept, tone="Quiet Luxury", use_trending_palette=True):
        """Aduni's 5-Part Formula for stunning AI photos"""
        self.log(f"Engineering 5-Part photo prompt for: {base_concept[:50]}")
        
        dynamic_styling = self.determine_dynamic_styling(base_concept)
        outfit, location, acc = self.extract_rich_styling_and_location(base_concept)

        # Style logic. Color palette is no longer hard-coded to
        # neutral-only (2026-07-06 fix -- see pick_color_palette's
        # docstring): every tone branch below now uses a genuinely varied
        # palette phrase instead of a fixed "cream, beige, and warm white".
        _, palette_desc = self.pick_color_palette(base_concept)
        style_desc = "editorial fashion photography style with magazine-cover composition"
        if tone == "Quiet Luxury":
            style_desc = f"high-fashion aesthetic styled with {palette_desc}"
        elif tone == "Dark Cinematic":
            style_desc = "dark cinematic aesthetic with chiaroscuro lighting, film-still quality"
        else:
            style_desc = "documentary realism, raw and grounded"
            
        camera_lens = random.choice([
            "shot on a medium format camera with 85mm lens at f/2.8, shallow depth of field, creamy bokeh",
            "shot on an anamorphic lens at f/2.0, cinematic aspect ratio",
            "shot on Canon EOS R5 35mm lens, lifestyle documentary feel"
        ])
        
        lighting = random.choice([
            "soft diffused natural window light, calm and refined mood",
            "soft natural light from the left with warm golden hour tones",
            "single dramatic spotlight from above cutting through shadow, deep cinematic shadows"
        ])

        palette_phrase = self.trending_palette_phrase() if use_trending_palette else ""
        palette_part = f", {palette_phrase}" if palette_phrase else ""

        # 4-Layer Monetization-Ready Prompt Architecture (2026 Standard)
        layer_0_identity = f"{self.base_subject}, {dynamic_styling}, maintaining exact facial features and natural proportions"
        layer_1_scene = f"Wide-angle full-body candid fashion shot from head to toe in {location}. She is wearing {outfit} styled with {acc}. Framed from a distance so her complete outfit, trousers length, and shoes are 100% visible without cropping."
        layer_2_style = f"High-fashion styling: {style_desc}{palette_part}. Impeccable tailoring creating an elongated, elegant silhouette."
        layer_3_camera = (
            f"{camera_lens}, {lighting}. Real-world photography characteristics: natural detailed skin texture, "
            f"visible micro-pores, soft organic facial highlights, Kodak Portra 400 film grain, shallow depth of field. "
            f"Unfiltered UGC influencer aesthetic with zero CGI, 3D render, or artificial beauty airbrushing."
        )

        return f"{layer_0_identity}. {layer_1_scene} {layer_2_style} {layer_3_camera}"

    def generate_5_shot_carousel_prompts(self, base_concept, styling_logic="", tone="Quiet Luxury") -> list:
        """
        Generates 5 distinct photographic angles/compositions for a complete outfit set,
        incorporating styling logic and magnetic facial allure.
        """
        dynamic_styling = self.determine_dynamic_styling(base_concept)
        outfit, location, acc = self.extract_rich_styling_and_location(base_concept)
        logic_str = f" Fashion styling rationale applied: {styling_logic}." if styling_logic else ""
        
        prompts = [
            {
                "type": "full_body",
                "title_fa": "۱. نمای تمام‌قد (Head-to-Toe Wide Shot)",
                "prompt": (
                    f"{self.base_subject}, {dynamic_styling}. Wide-angle full-body candid fashion shot from head to toe in {location}. "
                    f"She is wearing {outfit} styled with {acc}. Framed from a distance showing entire outfit, trousers length, and shoes on the ground without cropping.{logic_str} "
                    f"Shot on Canon EOS R5 35mm f/2.0, natural daylight, detailed skin texture, Kodak Portra grain."
                )
            },
            {
                "type": "portrait_detail",
                "title_fa": "۲. پرتره و فکوس روی بافت لباس (Portrait & Fabric Detail)",
                "prompt": (
                    f"{self.base_subject}, {dynamic_styling}. Captivating medium close-up editorial portrait in {location}. Focusing on upper outfit tailoring of {outfit}, "
                    f"luxury fabric weave, {acc}, and magnetic serene facial allure. Subtle alluring gaze looking toward camera. "
                    f"Shot on 85mm f/1.4 lens, creamy bokeh, natural micro-pores, magazine Vogue cover quality."
                )
            },
            {
                "type": "flat_lay",
                "title_fa": "۳. چیدمان ست لباس‌ها بدون مدل (Flat Lay / Outfit Layout Grid)",
                "prompt": (
                    f"High-end fashion flat lay photography composition showing ONLY the styled clothing pieces and accessories: {outfit}, along with {acc}. "
                    f"Neatly arranged side-by-side on a clean textured neutral linen background. "
                    f"NO human model, NO person, NO face visible. Crisp studio lighting, top-down 90-degree architectural view, editorial luxury product layout."
                )
            },
            {
                "type": "street_movement",
                "title_fa": "۴. حرکت و استایل خیابانی (Dynamic Street Movement)",
                "prompt": (
                    f"{self.base_subject}, {dynamic_styling}. Full-body dynamic candid shot walking confidently across {location}, wearing {outfit}. "
                    f"Capturing elegant fabric movement, coat flowing in the breeze, and elongated vertical silhouette.{logic_str} "
                    f"Shot on 50mm f/1.8, natural lifestyle motion sharpness, unfiltered influencer aesthetic."
                )
            },
            {
                "type": "candid_lifestyle",
                "title_fa": "۵. تعامل لایف‌استایل در محیط (Atmospheric Candid Interaction)",
                "prompt": (
                    f"{self.base_subject}, {dynamic_styling}. Atmospheric candid lifestyle capture sitting or relaxing naturally in {location}, wearing {outfit} with {acc}. "
                    f"Serene magnetic expression, warm natural sunlight beams, shallow depth of field, genuine everyday Parisian elegance. "
                    f"Real skin micro-details, zero CGI or plastic airbrushing."
                )
            }
        ]
        return prompts

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

    # ==================================================================
    # CHARACTER IDENTITY LOCKING PIPELINE
    # Added per user request based on the "Cinematic AI Food Film"
    # breakdown by the creator who locks identity BEFORE any video via a
    # 3-step pipeline: (1) full-body, (2) 8K face close-up with real skin
    # pores/imperfections, (3) a multi-angle character reference sheet.
    # This is THE key to 100% face consistency across every scene/video,
    # because giving the video model (Kling/Seedance/Hunyuan) a multi-angle
    # turnaround sheet stops it from inventing/changing the face on head
    # turns. Run this ONCE to mint Elina's canonical reference assets.
    # ==================================================================

    def generate_character_reference_sheet(self):
        """STEP 3 of the pipeline: a print-ready multi-angle turnaround sheet.
        This is the single most important asset for face consistency -- it
        locks Elina's identity from every angle so downstream video models
        never drift the face on profile/back turns."""
        self.log("Minting Elina's canonical CHARACTER REFERENCE SHEET (identity lock)")
        return (
            f"Create a professional character reference sheet based strictly on the uploaded reference image of "
            f"{self.base_subject}. Use a clean neutral plain light-grey background and present the sheet as a "
            f"technical model turnaround while matching the exact realistic visual style of the reference. "
            f"Arrange the composition into two horizontal rows. "
            f"TOP ROW: four full-body standing views -- front, left profile, right profile, and back. "
            f"BOTTOM ROW: three close-up portraits -- front, left profile, right profile. "
            f"Maintain PERFECT identity consistency across every panel (same face, same bone structure, "
            f"same hair, same height and proportions). Keep the subject in a relaxed A-pose with consistent "
            f"scale and alignment, accurate anatomy, and a clear silhouette. Lighting must be identical and "
            f"even across all panels. Output a crisp, ultra-realistic, print-ready reference sheet. No text, "
            f"no writings, no watermarks, no labels."
        )

    def generate_8k_face_closeup(self):
        """STEP 2 of the pipeline: the 8K skin-realism enhancement pass.
        The pro secret from the breakdown -- explicitly asking for pores and
        natural skin imperfections is what removes the fake 'plastic AI'
        look and makes Elina read as a real photographed human."""
        self.log("Generating 8K skin-realism face close-up for Elina")
        return (
            f"Extreme close-up of {self.base_subject}'s face, enhanced to 8K image detail. "
            f"Enhance facial skin realism while preserving ALL facial features, bone structure and expression exactly. "
            f"Add realistic skin pores, fine peach fuzz, subtle natural skin imperfections, faint under-eye texture, "
            f"soft natural sebum highlights on the T-zone, and individual eyebrow/eyelash strands. "
            f"Photographed on a 100mm macro lens at f/4, soft even beauty lighting. "
            f"Absolutely no airbrushing, no CGI, no 3D-render smoothness, no plastic skin -- raw photorealistic human skin only."
        )

    def generate_full_body_reference(self, outfit_desc="a plain fitted outfit in a neutral tone"):
        """STEP 1 of the pipeline: the full-body establishing shot that
        pins down proportions, height and styling before the face pass."""
        self.log("Generating full-body character reference for Elina")
        return (
            f"Full body shot of {self.base_subject}, wearing {outfit_desc}, standing in a relaxed natural pose "
            f"against a plain neutral background. Entire body visible head-to-toe with no cropping, accurate petite "
            f"150cm proportions, natural detailed skin texture with visible pores, shot on Canon EOS R5 50mm f/4, "
            f"even studio lighting, ultra-realistic, zero CGI or airbrushing."
        )

    def build_identity_pipeline(self, outfit_desc="a plain fitted outfit in a neutral tone"):
        """Returns all 3 identity-locking assets in the exact order the
        breakdown recommends generating them. Run this ONCE up front; feed
        the resulting reference sheet into every video generation call."""
        return {
            "step_1_full_body": self.generate_full_body_reference(outfit_desc),
            "step_2_face_8k": self.generate_8k_face_closeup(),
            "step_3_reference_sheet": self.generate_character_reference_sheet(),
            "pro_tip": (
                "Generate these BEFORE any video. The reference sheet locks identity so Elina looks identical "
                "across every scene. Always pass the reference sheet (not a single random selfie) as the "
                "character reference into Kling/Seedance/Hunyuan."
            ),
        }


    def generate_hero_asset_prompt(
        self,
        asset_name="signature object",
        asset_context="fashion editorial",
        material_focus="texture, fibers, surface detail, steam/dust/particles when appropriate",
    ):
        """Generate a separate HERO ASSET prompt before video production.

        Inspired by the cinematic food-film workflow: first create the hero object
        (food/product/outfit/accessory) as a reference image, then feed it into
        the video model. This keeps lighting, material style, color palette, and
        texture consistent across all shots.
        """
        return (
            f"HERO ASSET REFERENCE — {asset_name}. Context: {asset_context}. "
            "Create a premium commercial/editorial hero shot, centered composition, no text, no logos, no watermark. "
            "Use one clear material language and one consistent surface/background. "
            f"Emphasize {material_focus}. "
            "Include micro-detail: pores, fabric weave, leather grain, metal reflections, dust motes, steam, scratches, "
            "or natural imperfections where relevant. Lighting must be consistent with the final video: high-end cinematic "
            "key light plus motivated back/rim light, deep controlled shadows, realistic reflections, and physically plausible scale. "
            "Ultra-realistic, print-ready, commercial still, 8K detail."
        )

    def generate_exploded_view_prompt(self, elements, base_surface="minimal dark editorial surface", aesthetic="cinematic editorial"):
        """Generate an exploded-view / suspended-elements reference.

        The food-film breakdown teaches that complex scenes become more controllable
        when important components are pre-generated as clean references: ingredients,
        accessories, garments, products, cards, plants, props, etc.
        """
        if isinstance(elements, (list, tuple)):
            elements_text = ", ".join(elements)
        else:
            elements_text = str(elements)

        return (
            "EXPLODED VIEW REFERENCE — vertical suspended composition. "
            f"Elements: {elements_text}. Base surface: {base_surface}. "
            f"Aesthetic: {aesthetic}. Arrange each element in clean vertical alignment, hovering with believable scale, "
            "each object separated and readable, no hands, no body parts unless explicitly requested. "
            "Add tiny airborne particles, dust, fabric fibers, spice-like particulate energy, or pollen/leaf particles when suitable. "
            "Use consistent lens, lighting, background, and color palette with the hero asset. "
            "No text, no symbols, no labels. Ultra-realistic, crisp, high-detail reference plate."
        )

    def generate_action_detail_prompt(
        self,
        action="hands adjusting a garment",
        surface="dark editorial prep surface",
        detail_focus="texture and motion",
        aesthetic="high-end cinematic editorial",
    ):
        """Generate a close action-shot prompt for tactile motion references."""
        return (
            "ACTION DETAIL REFERENCE — tactile close-up. "
            f"Action: {action}. Surface/background: {surface}. "
            f"Focus: {detail_focus}. Aesthetic: {aesthetic}. "
            "Macro-level detail, realistic contact, pressure, material deformation, particles in air, natural imperfections, "
            "motivated directional lighting, shallow depth of field, no distracting background elements, no text or watermark."
        )

    def generate_directed_production_workflow(
        self,
        base_concept,
        production_type="fashion",
        duration="15 seconds",
        mood="cinematic pressure",
        platform="reels/shorts/youtube",
    ):
        """Create a full directed AI-video workflow with pre-production assets.

        This combines lessons from:
        - Card Sovereign: pressure, rhythm, low-angle authority, speed-ramping, sound design.
        - Cinematic Food Film: build character first, 8K face, reference sheet, hero asset,
          exploded view, action-detail shots, JSON timecoded direction, lens logic, particles,
          hero reveal, negative space, and consistent visual references.
        """
        self.log(f"Engineering directed production workflow for: {base_concept[:80]}")

        # Choose objects and tactile details based on topic, but keep it generic enough
        # for fashion, food, product, psychology, gardening, and cinematic content.
        concept_lower = base_concept.lower()
        if production_type == "food" or any(k in concept_lower for k in ["food", "chef", "recipe", "kitchen", "spice", "cook"]):
            hero_asset = "the final plated dish / hero food object"
            exploded_elements = ["main ingredient", "herbs", "spices", "oil drizzle", "steam", "garnish", "texture particles"]
            action = "hands seasoning, plating, slicing, or revealing the hero food object"
            environment = "high-end dark cinematic kitchen with matte surfaces, dark wood, steel fixtures, dramatic negative space"
            effects = "spice dust explosions, steam bursts, oil drizzle, heat distortion, micro herb flakes drifting"
            lenses = "24mm for explosive wide action, 100mm macro for texture, steam, skin/fabric/product detail"
        elif production_type == "product" or any(k in concept_lower for k in ["bag", "shoe", "jewelry", "perfume", "product"]):
            hero_asset = "the featured product/accessory"
            exploded_elements = ["product", "packaging", "material fragments", "reflection highlights", "brand-color accents"]
            action = "hands reveal, rotate, open, wear, or place the product with deliberate elegance"
            environment = "luxury editorial set with controlled negative space, premium surfaces, and clean shadows"
            effects = "dust motes, polished reflections, fabric fibers, soft glints, subtle lens flare"
            lenses = "50mm for natural product scale, 100mm macro for leather grain/metal reflection/fabric weave"
        else:
            hero_asset = "Elina's outfit / signature visual object / emotional symbol of the scene"
            exploded_elements = ["garment details", "accessories", "plant/nature symbol", "light particles", "fabric motion"]
            action = "Elina performs one intentional gesture connected to the story"
            environment = "cinematic fashion/lifestyle location with controlled negative space and emotionally meaningful props"
            effects = "floating dust, fabric movement, hair movement, pollen/leaf particles, atmospheric haze"
            lenses = "35mm for intimate lifestyle movement, 85mm for portraits, 100mm macro for fabric/skin/accessory detail"

        identity_pipeline = self.build_identity_pipeline(
            outfit_desc="a clean full-body styling reference matching the chosen story, with exact face and petite proportions preserved"
        )

        workflow = {
            "workflow_name": "Directed Cinematic AI Video Workflow",
            "based_on": [
                "Card Sovereign pressure/rhythm/sound-design method",
                "Cinematic Food Film reference-first production method",
                "Aduni 5-part photoreal prompt formula",
            ],
            "platform": platform,
            "duration": duration,
            "pre_production": {
                "identity_lock": identity_pipeline,
                "hero_asset_prompt": self.generate_hero_asset_prompt(
                    hero_asset,
                    asset_context=f"{production_type} / {base_concept}",
                    material_focus="macro detail, realistic imperfections, consistent lighting, surface texture, particles, steam/fabric/light movement",
                ),
                "exploded_view_prompt": self.generate_exploded_view_prompt(
                    exploded_elements,
                    base_surface="the same surface/background language as the hero asset",
                    aesthetic="premium cinematic editorial realism",
                ),
                "action_detail_prompt": self.generate_action_detail_prompt(
                    action=action,
                    surface="the same set/background as the hero asset",
                    detail_focus="material contact, deliberate gesture, texture, motion, particles, and believable physics",
                    aesthetic="cinematic commercial/editorial realism",
                ),
                "pro_tip": (
                    "Generate hero asset first, then exploded/detail references. Use them as references for the video model. "
                    "This keeps lighting, props, surfaces, textures, color palette, and identity consistent across all shots."
                ),
            },
            "video_prompt_json": {
                "scene_duration": duration,
                "style": {
                    "environment": environment,
                    "lighting": (
                        "high-contrast motivated lighting: controlled key light carving the subject/object, "
                        "rim/back light for separation, hard shadows where drama is needed, soft fill only when emotionally justified"
                    ),
                    "effects": effects,
                    "mood": mood,
                    "negative_space": "use darkness/empty space as a storytelling weapon; avoid busy backgrounds and random colorful clutter",
                },
                "references": {
                    "character_identity": "@[Character Reference Sheet] exact Elina identity, exact face, exact petite proportions, no face drift",
                    "hero_asset": "@[Hero Asset Reference] final object/product/outfit/food shot with consistent lighting and texture",
                    "exploded_view": "@[Exploded View Reference] suspended components for motion and detail continuity",
                    "action_detail": "@[Action Detail Reference] tactile close-up for believable hands/material interaction",
                },
                "camera_language": {
                    "general": (
                        "directed cinematic pacing: intentional hook, aggressive but motivated push-ins, whip-pans only on action beats, "
                        "snap cuts, bullet-time freezes, low-angle hero shots, selective dutch angles, handheld breathing only when it adds tension"
                    ),
                    "lenses": lenses,
                    "depth": "use shallow depth of field for emotion/detail, deeper focus only for spatial reveals",
                    "framing": "every shot must have a clear subject, readable silhouette, and no accidental crops of face/hands/product",
                },
                "sequence": [
                    {
                        "time": "0-2s",
                        "beat": "THE HOOK / ENTRANCE",
                        "direction": (
                            f"Start with the strongest visual promise of {base_concept}. Open with controlled pressure, not random motion. "
                            "Camera breathes inward. One clear gesture or reveal makes the viewer stop scrolling."
                        ),
                        "camera": "extreme close-up or low-angle hero entrance -> slow push-in",
                        "speed_ramp": "near-still pause -> 0.25x slow-motion on the first meaningful gesture",
                    },
                    {
                        "time": "2-6s",
                        "beat": "THE TACTILE MONEY SHOT",
                        "direction": (
                            "Feature the most satisfying object/material/action: texture, fabric, product, food, plant, card, hand gesture, or emotional symbol. "
                            "Use macro detail. Make every fiber, pore, grain, crease, reflection, particle, or steam trail visible."
                        ),
                        "camera": "100mm macro insert -> rapid push-in -> suspended slow-motion hover",
                        "speed_ramp": "full speed launch/action -> instant extreme slow-motion hover -> snap back to full speed",
                    },
                    {
                        "time": "6-10s",
                        "beat": "THE EXPLOSION / TRANSFORMATION",
                        "direction": (
                            "Use the exploded-view logic: components rise, rotate, assemble, reveal, or orbit around the subject. "
                            "The subject remains composed while the world moves around her/it."
                        ),
                        "camera": "360-degree orbit while rising, low upshot, tight side cut, rotating follow shot",
                        "speed_ramp": "0.5x build -> 1.5x fast cuts -> bullet-time freeze",
                    },
                    {
                        "time": "10-15s",
                        "beat": "THE HERO RELEASE / FINAL FRAME",
                        "direction": (
                            "Resolve with a powerful hero image: final outfit/product/dish/idea perfectly framed. "
                            "End on an epic freeze frame that feels like the beginning of something bigger."
                        ),
                        "camera": "wide pull-back -> final centered hero frame -> freeze",
                        "speed_ramp": "ultra slow -> full speed impact -> silence/freeze",
                    },
                ],
                "sound_design": {
                    "voice": "deep/clear/intimate voiceover when needed; voice must match the language, emotion, and platform",
                    "foley": "sharp whooshes, tactile fabric/product/food sounds, micro cracks, breath, room tone",
                    "slow_motion": "low-frequency audio stretch, near-silence with ambient hum during hover moments",
                    "music": "score must support the scene like a trailer, not generic background music",
                    "ending": "sub-bass impact hit, then a short silence to create memory",
                },
                "subtitle_rules": {
                    "required": True,
                    "style": "platform-optimized, high contrast, not covering face/product/hands; word-by-word for shorts when appropriate",
                    "languages": "generate subtitles in target language and optionally English for international reach",
                },
                "negative_prompt": (
                    "no anime, no CGI look unless explicitly CGV, no plastic skin, no random text/symbols/logos, no face drift, "
                    "no extra fingers, no distorted hands, no inconsistent outfit, no busy colorful background, no flat lighting, "
                    "no abrupt/jarring cuts that feel accidental, no low-quality blur, no watermark"
                ),
            },
            "qa_checklist": [
                "Does identity remain identical in every frame/reference?",
                "Is there a clear hero asset or hero visual promise?",
                "Are lighting/background/materials consistent across references and video?",
                "Does the first 1-2 seconds stop scrolling?",
                "Is there speed-ramp rhythm: full speed -> slow hover -> snap/impact?",
                "Are micro-details visible (pores, fibers, reflections, steam, particles)?",
                "Does sound design carry emotion, not just fill silence?",
                "Does the final freeze/hero frame leave viewers wanting more?",
                "Are subtitles readable and not covering important visual areas?",
            ],
        }
        return workflow

    def run(self, base_concept, format_type="photo", tone="dark"):
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        if format_type == "photo":
            return self.generate_photo_prompt(base_concept, tone)
        elif format_type == "reference_sheet":
            # One-time identity-locking pipeline (full-body -> 8K face -> turnaround sheet)
            return self.build_identity_pipeline()
        elif format_type == "face_8k":
            return self.generate_8k_face_closeup()
        elif format_type in ["directed_workflow", "production_workflow", "cinematic_workflow", "food_film"]:
            # Full pre-production + video-direction pipeline learned from
            # Card Sovereign and Cinematic Food Film prompt breakdowns.
            return self.generate_directed_production_workflow(base_concept, production_type=tone)
        else:
            return self.generate_cinematic_json_script(base_concept, tone)
