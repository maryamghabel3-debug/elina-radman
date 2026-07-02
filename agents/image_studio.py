"""ImageStudio Agent — Generates REAL photos of Elina.

This replaces the old HF-only VisualCreatorAgent with a robust, multi-provider
studio that actually produces image files, with graceful fallback:

  1. Gemini image generation (Nano Banana)  — primary, uses the GEMINI_API_KEY
     you already have. Best quality + can honor a reference face for consistency.
  2. Pollinations.ai                          — free, no key required, always-on
     fallback so an image is (almost) always produced.
  3. Clear error result                       — never crashes the pipeline.

It builds the actual prompt via PromptEngineer (so outfit/pose/camera/lighting
and the trending palette are baked in), then writes a real JPEG to
content/images/ and returns its path.
"""

import os
import io
import time
import base64
import urllib.parse
from datetime import datetime

import requests

from .base import Agent

_OUT_DIR = "content/images"
_REFERENCE_FACE = "images/elina-profile-pic-03.jpg"

# Identity lock so every generated photo looks like the same person.
_IDENTITY = (
    "Elina Radman, a 24-year-old Iranian woman with warm wheat skin, soft dark "
    "brown eyes, petite 150cm frame, full lips with subtle nude lip color, long "
    "dark brown hair"
)


class ImageStudio(Agent):
    def __init__(self):
        super().__init__("ImageStudio", "Generates real photos of Elina (Gemini + Pollinations)")
        os.makedirs(_OUT_DIR, exist_ok=True)
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.gemini_image_model = os.environ.get(
            "GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation"
        )
        self.session = requests.Session()
        self.has_reference = (
            os.path.exists(_REFERENCE_FACE) and os.path.getsize(_REFERENCE_FACE) > 1024
        )

    # ------------------------------------------------------------------ #
    # Prompt building
    # ------------------------------------------------------------------ #
    def build_prompt(self, concept: str, tone: str = "Quiet Luxury") -> str:
        """Use PromptEngineer for a rich, on-brand, trend-aware photo prompt."""
        try:
            from .prompt_engineer import PromptEngineerAgent

            pe = PromptEngineerAgent()
            return pe.generate_photo_prompt(concept, tone=tone)
        except Exception as e:
            self.log(f"PromptEngineer unavailable ({e}); using basic prompt", "error")
            return (
                f"{_IDENTITY}, {concept}, editorial fashion photography, "
                f"quiet luxury aesthetic, soft natural light, photorealistic, high resolution"
            )

    # ------------------------------------------------------------------ #
    # Providers
    # ------------------------------------------------------------------ #
    def _gemini_image(self, prompt: str, out_path: str) -> bool:
        """Generate via Gemini image model. Returns True on success."""
        if not self.gemini_key:
            return False
        # Optionally attach the reference face for identity consistency
        parts = [{"text": f"Generate a photorealistic image. {prompt}"}]
        if self.has_reference:
            try:
                with open(_REFERENCE_FACE, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                parts.insert(0, {"inline_data": {"mime_type": "image/jpeg", "data": b64}})
                parts[1]["text"] = (
                    "Using the face in the reference image as the exact same person, "
                    f"generate a new photorealistic image. {prompt}"
                )
            except OSError:
                pass

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_image_model}:generateContent?key={self.gemini_key}"
        )
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }
        try:
            r = self.session.post(url, json=payload, timeout=90)
            if r.status_code != 200:
                self.log(f"Gemini image HTTP {r.status_code}: {r.text[:150]}", "error")
                return False
            data = r.json()
            for cand in data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inline_data") or part.get("inlineData")
                    if inline and inline.get("data"):
                        img_bytes = base64.b64decode(inline["data"])
                        with open(out_path, "wb") as f:
                            f.write(img_bytes)
                        return True
            self.log("Gemini returned no image part", "error")
            return False
        except (requests.RequestException, ValueError) as e:
            self.log(f"Gemini image error: {e}", "error")
            return False

    def _pollinations_image(self, prompt: str, out_path: str,
                            width: int = 768, height: int = 1024) -> bool:
        """Free, no-key fallback via Pollinations.ai. Returns True on success."""
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
    def generate(self, concept: str, tone: str = "Quiet Luxury",
                 prefer: str = "auto") -> dict:
        """Generate one photo of Elina for the given concept.

        prefer: 'auto' (Gemini then Pollinations), 'gemini', or 'pollinations'.
        Returns {path, provider, prompt} or {error, prompt}.
        """
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        prompt = self.build_prompt(concept, tone=tone)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        out_path = os.path.join(_OUT_DIR, f"elina_{ts}.jpg")

        order = {
            "gemini": ["gemini"],
            "pollinations": ["pollinations"],
        }.get(prefer, ["gemini", "pollinations"])

        for provider in order:
            ok = (
                self._gemini_image(prompt, out_path)
                if provider == "gemini"
                else self._pollinations_image(prompt, out_path)
            )
            if ok:
                self.log(f"Image generated via {provider}: {out_path}")
                return {"path": out_path, "provider": provider, "prompt": prompt}

        return {"error": "all_providers_failed", "prompt": prompt}

    def run(self, concept: str = "wearing a tailored camel blazer in a sunlit cafe",
            tone: str = "Quiet Luxury", prefer: str = "auto") -> dict:
        return self.generate(concept, tone=tone, prefer=prefer)


if __name__ == "__main__":
    import json
    studio = ImageStudio()
    print(json.dumps(studio.run(), indent=2, ensure_ascii=False))
