import os
import requests

class PlatformManager:
    def __init__(self, platform_name):
        self.platform_name = platform_name

    def optimize_content(self, content):
        return f"[{self.platform_name} Optimized] {content}"


class InstagramManager(PlatformManager):
    def __init__(self):
        super().__init__("Instagram")
        self.hashtags = "#ElinaRadman #AIInfluencer #Tech"


class TikTokManager(PlatformManager):
    def __init__(self):
        super().__init__("TikTok")
        self.trends = "Trending Sounds & Fast Cuts"


class YouTubeManager(PlatformManager):
    def __init__(self):
        super().__init__("YouTube")
        self.format = "Long-form / Shorts"


class PinterestManager(PlatformManager):
    def __init__(self):
        super().__init__("Pinterest")
        self.visual_style = "Aesthetic Boards"


class VisualCreatorAgent:
    def __init__(self):
        # We use Cloudflare for free B-Rolls/Backgrounds
        self.cf_account_id = os.environ.get("CF_ACCOUNT_ID", "")
        self.cf_api_token = os.environ.get("CF_API_TOKEN", "")
        
        # We MUST use Replicate/ComfyUI/InstantID for Elina's Face
        self.replicate_api_token = os.environ.get("REPLICATE_API_TOKEN", "")
        self.use_local_comfyui = os.environ.get("USE_LOCAL_COMFYUI", "false").lower() == "true"

    def generate_b_roll_cloudflare(self, prompt, output_path="broll.png"):
        """Generate Free Backgrounds/Objects using Cloudflare (No Face Required)"""
        if not self.cf_account_id or not self.cf_api_token:
            print("[VisualCreator] No CF credentials. Mocking B-Roll.")
            return f"Mock B-Roll for: {prompt}"

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.cf_account_id}/ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {"Authorization": f"Bearer {self.cf_api_token}"}
        
        try:
            print(f"[VisualCreator] Requesting Free B-Roll from Cloudflare...")
            response = requests.post(url, headers=headers, json={"prompt": prompt})
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
        except Exception as e:
            print(f"[VisualCreator] CF Error: {e}")
        return None

    def generate_consistent_character(self, prompt):
        """
        Generate visual assets maintaining Elina's EXACT face.
        Cloudflare alone is NOT enough for a consistent face. We must use LoRA or InstantID.
        """
        print(f"[VisualCreator] Generating STRICT consistent face for Elina...")
        
        character_prompt = (
            f"1girl, Elina Radman, Iranian, petite 150cm, dark brown eyes, "
            f"wavy brown hair, quiet luxury aesthetic, {prompt}"
        )
        
        if self.use_local_comfyui:
            print("[VisualCreator] Sending to Local ComfyUI (InstantID + SDXL) via API...")
            # Here you would connect to 127.0.0.1:8188 (ComfyUI)
            return "local_comfyui_output.png"
        elif self.replicate_api_token:
            print("[VisualCreator] Sending to Replicate API (LoRA / InstantID)...")
            # Here you would call Replicate API using replicate python package
            return "cloud_replicate_output.png"
        else:
            print("[VisualCreator] ⚠️ WARNING: No Consistent Face engine configured. Falling back to Cloudflare (Face will NOT match perfectly).")
            return self.generate_b_roll_cloudflare(character_prompt, "fallback_face.png")

