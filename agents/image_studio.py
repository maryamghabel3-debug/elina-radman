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
        self.last_error = ""       # last Gemini failure reason (for debugging)
        self.working_model = ""    # model id that actually produced an image

    # ------------------------------------------------------------------ #
    # Reference faces
    # ------------------------------------------------------------------ #
    def reference_images(self, limit: int = 3) -> list:
        """Return paths to Elina's real reference photos (newest / largest first = best)."""
        files = []
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            files.extend(glob.glob(os.path.join(_REF_DIR, ext)))
        files = [f for f in files if os.path.getsize(f) > 1024]
        # Sort by newest modification time and largest file size so uploaded photos take priority
        files.sort(key=lambda f: (-os.path.getmtime(f), -os.path.getsize(f)))
        return files[:limit]

    # ------------------------------------------------------------------ #
    # Prompt building (trend-aware, full editorial)
    # ------------------------------------------------------------------ #
    def build_prompt(self, concept: str, tone: str = "Quiet Luxury") -> str:
        """Rich editorial prompt via PromptEngineer with live trend signals,
        forced to ultra-photorealistic candid lifestyle photography."""
        base = ""
        try:
            from .prompt_engineer import PromptEngineerAgent
            base = PromptEngineerAgent().generate_photo_prompt(concept, tone=tone)
        except Exception as e:
            self.log(f"PromptEngineer unavailable ({e}); basic prompt", "error")
            base = f"{_IDENTITY}, {concept}, editorial fashion photography, quiet luxury"

        # Force wide head-to-toe full-body framing showing shoes and trousers completely
        framing = (
            "Wide-angle Full-body candid fashion photograph shot from head to toe, showing the complete styled outfit "
            "including trousers length and shoes on the ground without cropping. Realistic location atmosphere, natural sunlight, "
            "Kodak Portra 400 film grain, ultra realistic detailed skin texture, Vogue editorial quality."
        )
        return f"{base} {framing}"

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

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }

        # Try the configured model first, then known image-capable fallbacks.
        # Different keys/regions expose different model ids, so we probe a few.
        models_to_try = []
        for m in [
            self.model,
            "gemini-3-pro-image-preview",
            "gemini-2.5-flash-image",
            "gemini-2.5-flash-image-preview",
            "gemini-2.0-flash-preview-image-generation",
        ]:
            if m and m not in models_to_try:
                models_to_try.append(m)

        for model_id in models_to_try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_id}:generateContent"
            )
            try:
                r = self.session.post(
                    url,
                    headers={"x-goog-api-key": self.gemini_key, "Content-Type": "application/json"},
                    json=payload,
                    timeout=120,
                )
            except (requests.RequestException, ValueError) as e:
                self.last_error = f"{model_id}: {e}"
                self.log(f"Gemini image error ({model_id}): {e}", "error")
                continue

            if r.status_code != 200:
                self.last_error = f"{model_id}: HTTP {r.status_code} {r.text[:200]}"
                self.log(f"Gemini image HTTP {r.status_code} ({model_id}): {r.text[:200]}", "error")
                # 404 = model not found for this key -> try next model
                continue

            try:
                data = r.json()
            except ValueError as e:
                self.last_error = f"{model_id}: bad json {e}"
                continue

            for cand in data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inline_data") or part.get("inlineData")
                    if inline and inline.get("data"):
                        with open(out_path, "wb") as f:
                            f.write(base64.b64decode(inline["data"]))
                        self.working_model = model_id
                        return True

            self.last_error = f"{model_id}: no image part ({str(data)[:150]})"
            self.log(f"Gemini no image part ({model_id}): {str(data)[:150]}", "error")

        return False

    def _hf_instantid_image(self, prompt: str, out_path: str) -> bool:
        """Free cloud GPU generation via HuggingFace InstantID using Elina's
        reference photo for strict face consistency."""
        hf_token = os.environ.get("HF_TOKEN", "")
        if not hf_token:
            return False

        refs = self.reference_images(limit=1)
        if not refs:
            return False

        ref_img = refs[0]
        try:
            from gradio_client import Client, handle_file
        except ImportError:
            self.log("gradio_client not installed for HF InstantID", "error")
            return False

        try:
            client = Client("InstantX/InstantID", token=hf_token)
            res = client.predict(
                handle_file(ref_img),
                None,
                f"candid 35mm photograph of Elina Radman, 24yo Iranian woman, {prompt}",
                "anime, cartoon, deformed, bad anatomy, bad face, extra limbs, plastic skin, CGI, 3d render",
                "(No style)",
                30,
                0.8,
                0.75,
                0.0,
                0.0,
                [],
                5.0,
                42,
                "EulerDiscreteScheduler",
                False,
                True,
                api_name="/generate_image"
            )
            img_path = res[0] if isinstance(res, (list, tuple)) else str(res)
            if isinstance(img_path, str) and os.path.exists(img_path):
                import shutil
                shutil.copy(img_path, out_path)
                self.working_model = "InstantX/InstantID"
                return True
        except Exception as e:
            self.log(f"HF InstantID error: {e}", "error")
        return False

    def _hf_pulid_flux_image(self, prompt: str, out_path: str) -> bool:
        """Free cloud GPU generation via yanze/PuLID-FLUX using Elina's
        reference photo for exact face consistency."""
        hf_token = os.environ.get("HF_TOKEN", "")
        if not hf_token:
            return False
        refs = self.reference_images(limit=1)
        if not refs:
            return False
        try:
            from gradio_client import Client, handle_file
            client = Client("yanze/PuLID-FLUX", token=hf_token)
            res = client.predict(
                f"candid 35mm editorial fashion photo of Elina Radman, 24yo woman, {prompt}",
                handle_file(refs[0]),
                0, 4.0, "-1", 1.0, 896, 1152, 28, 1.0,
                "bad quality, worst quality, extra limbs, CGI, 3d render, illustration, plastic skin, different face", 1, 512,
                api_name="/generate_image"
            )
            img_path = res[0] if isinstance(res, (list, tuple)) else str(res)
            if isinstance(img_path, str) and os.path.exists(img_path):
                import shutil
                shutil.copy(img_path, out_path)
                self.working_model = "yanze/PuLID-FLUX"
                return True
        except Exception as e:
            self.log(f"HF PuLID-FLUX error: {e}", "error")
        return False

    def _hf_pulid_sdxl_image(self, prompt: str, out_path: str) -> bool:
        """Free cloud GPU generation via yanze/PuLID (SDXL) using Elina's
        reference photo for exact face consistency."""
        hf_token = os.environ.get("HF_TOKEN", "")
        if not hf_token:
            return False
        refs = self.reference_images(limit=1)
        if not refs:
            return False
        try:
            from gradio_client import Client, handle_file
            client = Client("yanze/PuLID", token=hf_token)
            res = client.predict(
                handle_file(refs[0]), handle_file(refs[0]), handle_file(refs[0]), handle_file(refs[0]),
                f"Elina Radman, 24yo woman, {prompt}",
                "lowres, bad anatomy, bad quality",
                1.2, 4.0, 42, 4.0, 1024, 768, 0.8, "fidelity", False,
                api_name="/run"
            )
            img_path = res[0] if isinstance(res, (list, tuple)) else str(res)
            if isinstance(img_path, str) and os.path.exists(img_path):
                import shutil
                shutil.copy(img_path, out_path)
                self.working_model = "yanze/PuLID"
                return True
        except Exception as e:
            self.log(f"HF PuLID SDXL error: {e}", "error")
        return False

    def _nvidia_nim_image(self, prompt: str, out_path: str) -> bool:
        """Free high-quality image generation via NVIDIA NIM (build.nvidia.com)."""
        api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY", "")
        if not api_key:
            return False

        url = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": f"Elina Radman, 24yo Iranian woman, petite frame, warm wheat skin, {prompt}",
            "negative_prompt": "deformed, bad anatomy, anime, cartoon, blurry, low resolution, different face",
            "samples": 1,
            "steps": 30,
        }
        try:
            r = self.session.post(url, headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                data = r.json()
                b64_str = data.get("artifacts", [{}])[0].get("base64") or data.get("b64_json") or ""
                if b64_str:
                    with open(out_path, "wb") as f:
                        f.write(base64.b64decode(b64_str))
                    self.working_model = "NVIDIA-NIM/SDXL"
                    return True
            else:
                self.log(f"NVIDIA NIM error HTTP {r.status_code}: {r.text[:150]}")
        except Exception as e:
            self.log(f"NVIDIA NIM exception: {e}", "error")
        return False

    def _fal_ai_image(self, prompt: str, out_path: str) -> bool:
        """Fast & low-cost FLUX PuLID image generation via Fal.ai API."""
        fal_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY", "")
        if not fal_key:
            return False

        refs = self.reference_images(limit=1)
        if not refs:
            return False

        try:
            with open(refs[0], "rb") as f:
                b64_img = base64.b64encode(f.read()).decode()
            data_uri = f"data:image/jpeg;base64,{b64_img}"

            url = "https://fal.run/fal-ai/flux-pulid"
            headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
            payload = {
                "prompt": f"candid 35mm editorial fashion photo of Elina Radman, 24yo woman, {prompt}",
                "reference_image_url": data_uri,
                "id_scale": 1.0,
                "num_inference_steps": 28,
            }
            r = self.session.post(url, headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                img_url = r.json().get("images", [{}])[0].get("url")
                if img_url:
                    img_data = self.session.get(img_url, timeout=30).content
                    with open(out_path, "wb") as f:
                        f.write(img_data)
                    self.working_model = "fal-ai/flux-pulid"
                    return True
        except Exception as e:
            self.log(f"Fal.ai image error: {e}", "error")
        return False

    def _together_ai_image(self, prompt: str, out_path: str) -> bool:
        """Fast & low-cost FLUX.1-dev image generation via Together AI."""
        api_key = os.environ.get("TOGETHER_API_KEY") or os.environ.get("TOGETHER_KEY", "")
        if not api_key:
            return False

        url = "https://api.together.xyz/v1/images/generations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "black-forest-labs/FLUX.1-dev",
            "prompt": f"candid 35mm editorial fashion photo of Elina Radman, 24yo woman, {prompt}",
            "width": 896,
            "height": 1152,
            "steps": 28,
            "n": 1,
            "response_format": "b64_json"
        }
        try:
            r = self.session.post(url, headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                b64_str = r.json().get("data", [{}])[0].get("b64_json", "")
                if b64_str:
                    with open(out_path, "wb") as f:
                        f.write(base64.b64decode(b64_str))
                    self.working_model = "TogetherAI/FLUX.1-dev"
                    return True
        except Exception as e:
            self.log(f"Together AI image error: {e}", "error")
        return False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def generate(self, concept: str = None, tone: str = "Quiet Luxury",
                 prefer: str = "auto", **kwargs) -> dict:
        """Generate one on-brand, face-consistent photo of Elina.

        concept=None -> derive from the latest trend analysis (trend-driven).
        prefer: 'auto' (Gemini -> NVIDIA NIM -> Fal.ai -> Together AI -> HF PuLID-FLUX).
        """
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        if not concept:
            concept = self.trend_concept()

        prompt = self.build_prompt(concept, tone=tone)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        out_path = os.path.join(_OUT_DIR, f"elina_{ts}.jpg")

        order = {
            "gemini": ["gemini"],
            "nvidia": ["nvidia_nim"],
            "fal": ["fal_ai"],
            "together": ["together_ai"],
            "flux": ["nvidia_nim", "fal_ai", "together_ai", "hf_pulid_flux"],
            "hf": ["hf_pulid_flux", "hf_pulid_sdxl", "hf_instantid"],
        }.get(prefer, ["gemini", "nvidia_nim", "fal_ai", "together_ai", "hf_pulid_flux", "hf_pulid_sdxl"])

        for provider in order:
            if provider == "gemini":
                ok = self._gemini_image(prompt, out_path)
            elif provider == "nvidia_nim":
                ok = self._nvidia_nim_image(prompt, out_path)
            elif provider == "fal_ai":
                ok = self._fal_ai_image(prompt, out_path)
            elif provider == "together_ai":
                ok = self._together_ai_image(prompt, out_path)
            elif provider == "hf_instantid":
                ok = self._hf_instantid_image(prompt, out_path)
            elif provider == "hf_pulid_flux":
                ok = self._hf_pulid_flux_image(prompt, out_path)
            elif provider == "hf_pulid_sdxl":
                ok = self._hf_pulid_sdxl_image(prompt, out_path)
            else:
                ok = False

            if ok:
                self.log(f"Image generated via {provider}: {out_path}")
                used_ref = provider != "nvidia_nim" and bool(self.reference_images())
                return {
                    "path": out_path,
                    "provider": provider,
                    "concept": concept,
                    "used_reference": used_ref,
                    "working_model": self.working_model or provider,
                    "gemini_error": self.last_error if provider != "gemini" else "",
                    "warning": "" if used_ref else "⚠️ توجه: این عکس با NVIDIA NIM (بدون مرجع چهره مستقیم) ساخته شده است.",
                    "prompt": prompt,
                }

        return {
            "error": "all_providers_failed",
            "concept": concept,
            "gemini_error": self.last_error,
            "prompt": prompt,
        }

    def run(self, concept: str = None, tone: str = "Quiet Luxury", prefer: str = "auto") -> dict:
        return self.generate(concept, tone=tone, prefer=prefer)


if __name__ == "__main__":
    import json
    print(json.dumps(ImageStudio().run(), indent=2, ensure_ascii=False))
