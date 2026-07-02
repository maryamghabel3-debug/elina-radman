"""ImageStudio Agent — Generates REAL, on-brand, face-consistent photos of Elina.

Design goals (fixing the earlier random-portrait problem):
  1. FACE CONSISTENCY — sends Elina's real reference photos (images/*.jpg) to
     Google's Nano Banana (gemini-2.5-flash-image), which accepts up to ~14
     reference images and keeps the SAME face across generations.
  2. GEMINI IS PRIMARY — Pollinations is only an emergency fallback, because it
     cannot honor a reference face. If Gemini has no key, we say so clearly.
  3. FULL EDITORIAL FASHION — the prompt asks for a full-body / 3-4 look styled
     shot (outfit, pose, setting, camera, lighting), not a face close-up.
  4. TREND-DRIVEN — pulls the latest reverse-engineered trend signals
     (content/trend_visuals.json) so the outfit/pose/palette match what's going
     viral, instead of a random image.

Writes a real JPEG to content/images/ and returns its path.
"""

import os
import base64
import glob
import urllib.parse
from datetime import datetime

import requests

from .base import Agent

_OUT_DIR = "content/images"
_REF_DIR = "images"

# Nano Banana (Gemini 2.5 Flash Image). Override with GEMINI_IMAGE_MODEL.
_DEFAULT_MODEL = "gemini-2.5-flash-image"

_IDENTITY = (
    "Elina Radman, a 24-year-old Iranian woman with warm wheat skin, thick dark "
    "eyebrows, soft dark brown eyes, long wavy near-black hair, full lips with "
    "subtle nude lip color, petite 150cm frame"
)


class ImageStudio(Agent):
    def __init__(self):
        super().__init__("ImageStudio", "Generates real, face-consistent photos of Elina")
        os.makedirs(_OUT_DIR, exist_ok=True)
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = os.environ.get("GEMINI_IMAGE_MODEL", _DEFAULT_MODEL)
        self.session = requests.Session()

    # ------------------------------------------------------------------ #
    # Reference faces
    # ------------------------------------------------------------------ #
    def reference_images(self, limit: int = 3) -> list:
        """Return paths to Elina's real reference photos (largest first = best)."""
        files = [
            f for f in glob.glob(os.path.join(_REF_DIR, "*.jpg"))
            if os.path.getsize(f) > 1024
        ]
        # Prefer the curated 'final' shots, biggest (highest quality) first
        files.sort(key=lambda f: (("final" not in f), -os.path.getsize(f)))
        return files[:limit]

    # ------------------------------------------------------------------ #
    # Prompt building (trend-aware, full editorial)
    # ------------------------------------------------------------------ #
    def build_prompt(self, concept: str, tone: str = "Quiet Luxury") -> str:
        """Rich editorial prompt via PromptEngineer (5-part formula + trending
        palette/aesthetic), forced to a full-body styled fashion shot."""
        base = ""
        try:
            from .prompt_engineer import PromptEngineerAgent

            base = PromptEngineerAgent().generate_photo_prompt(concept, tone=tone)
        except Exception as e:
            self.log(f"PromptEngineer unavailable ({e}); basic prompt", "error")
            base = f"{_IDENTITY}, {concept}, editorial fashion photography, quiet luxury"

        # Force full-body styled fashion framing (not a face close-up)
        framing = (
            "Full-body or three-quarter length editorial fashion photograph showing "
            "the complete styled outfit, shoes and accessories, natural confident "
            "model pose, realistic body proportions, Instagram fashion-influencer look"
        )
        return f"{base} {framing}."

    def trend_concept(self) -> str:
        """Derive a photo concept from the latest trend analysis so the image is
        trend-driven, not random. Falls back to a sensible default."""
        try:
            from .trend_visual_analyzer import TrendVisualAnalyzer

            rep = TrendVisualAnalyzer.load_latest_palette()
            if rep:
                bits = []
                aes = rep.get("trending_aesthetics") or []
                prod = rep.get("trending_standout_products") or []
                poses = rep.get("sample_poses") or []
                if aes:
                    bits.append(f"in a {aes[0]} aesthetic")
                if prod:
                    bits.append(f"styled around {prod[0]}")
                if poses:
                    bits.append(f"pose reference: {str(poses[0])[:60]}")
                if bits:
                    return "wearing an on-trend outfit " + ", ".join(bits)
        except Exception as e:
            self.log(f"trend_concept fallback: {e}", "error")
        return "wearing a tailored camel trench coat and wide-leg trousers, city street, golden hour"

    # ------------------------------------------------------------------ #
    # Providers
    # ------------------------------------------------------------------ #
    def _gemini_image(self, prompt: str, out_path: str) -> bool:
        """Nano Banana image-to-image using Elina's reference faces."""
        if not self.gemini_key:
            return False

        parts = []
        refs = self.reference_images(limit=3)
        for ref in refs:
            try:
                with open(ref, "rb") as f:
                    parts.append({
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64.b64encode(f.read()).decode(),
                        }
                    })
            except OSError:
                continue

        instruction = (
            "Generate a NEW photorealistic image of the SAME woman shown in the "
            "reference photo(s) — keep her exact face, bone structure, eyebrows, "
            "eyes, nose, lips and skin tone identical for perfect character "
            f"consistency. {prompt}"
            if refs
            else f"Generate a photorealistic image. {_IDENTITY}. {prompt}"
        )
        parts.append({"text": instruction})

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }
        try:
            r = self.session.post(
                url,
                headers={"x-goog-api-key": self.gemini_key, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            if r.status_code != 200:
                self.log(f"Gemini image HTTP {r.status_code}: {r.text[:200]}", "error")
                return False
            data = r.json()
            for cand in data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inline_data") or part.get("inlineData")
                    if inline and inline.get("data"):
                        with open(out_path, "wb") as f:
                            f.write(base64.b64decode(inline["data"]))
                        return True
            self.log(f"Gemini returned no image part: {str(data)[:200]}", "error")
            return False
        except (requests.RequestException, ValueError) as e:
            self.log(f"Gemini image error: {e}", "error")
            return False

    def _pollinations_image(self, prompt: str, out_path: str,
                            width: int = 832, height: int = 1216) -> bool:
        """Emergency fallback only (NO face consistency)."""
        full = f"{_IDENTITY}, {prompt}"
        url = (
            "https://image.pollinations.ai/prompt/"
            + urllib.parse.quote(full)
            + f"?width={width}&height={height}&nologo=true"
        )
        try:
            r = self.session.get(url, timeout=120)
            if r.status_code == 200 and r.content[:3] == b"\xff\xd8\xff":
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return True
            self.log(f"Pollinations HTTP {r.status_code}", "error")
            return False
        except requests.RequestException as e:
            self.log(f"Pollinations error: {e}", "error")
            return False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def generate(self, concept: str = None, tone: str = "Quiet Luxury",
                 prefer: str = "auto", allow_pollinations: bool = True) -> dict:
        """Generate one on-brand, face-consistent photo of Elina.

        concept=None -> derive from the latest trend analysis (trend-driven).
        prefer: 'auto' (Gemini then Pollinations), 'gemini', or 'pollinations'.
        """
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        if not concept:
            concept = self.trend_concept()

        prompt = self.build_prompt(concept, tone=tone)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        out_path = os.path.join(_OUT_DIR, f"elina_{ts}.jpg")

        order = {"gemini": ["gemini"], "pollinations": ["pollinations"]}.get(
            prefer, ["gemini", "pollinations"]
        )
        if not allow_pollinations:
            order = [p for p in order if p != "pollinations"]

        for provider in order:
            ok = (
                self._gemini_image(prompt, out_path)
                if provider == "gemini"
                else self._pollinations_image(prompt, out_path)
            )
            if ok:
                self.log(f"Image generated via {provider}: {out_path}")
                return {
                    "path": out_path,
                    "provider": provider,
                    "concept": concept,
                    "used_reference": provider == "gemini" and bool(self.reference_images()),
                    "prompt": prompt,
                }

        return {"error": "all_providers_failed", "concept": concept, "prompt": prompt}

    def run(self, concept: str = None, tone: str = "Quiet Luxury", prefer: str = "auto") -> dict:
        return self.generate(concept, tone=tone, prefer=prefer)


if __name__ == "__main__":
    import json
    print(json.dumps(ImageStudio().run(), indent=2, ensure_ascii=False))
