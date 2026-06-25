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
        self.workflow = "Cloudflare Workers AI (SDXL)"
        self.cf_account_id = os.environ.get("CF_ACCOUNT_ID", "")
        self.cf_api_token = os.environ.get("CF_API_TOKEN", "")

    def generate_image_cloudflare(self, prompt, output_path="output.png"):
        """Generate Free Images using Cloudflare Workers AI (100k free requests/day)"""
        if not self.cf_account_id or not self.cf_api_token:
            print("[VisualCreator] No Cloudflare credentials. Mocking output.")
            return f"Mock Generated Asset for: {prompt}"

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.cf_account_id}/ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {"Authorization": f"Bearer {self.cf_api_token}"}
        payload = {"prompt": prompt}

        try:
            print(f"[VisualCreator] Requesting Free AI Image from Cloudflare...")
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
        except Exception as e:
            print(f"[VisualCreator] Error: {e}")
        
        return "Error generating image"

    def generate_consistent_character(self, prompt):
        """Generate visual assets maintaining Elina's face consistency"""
        enhanced_prompt = f"{prompt}, highly detailed, portrait of Elina, photorealistic, 8k"
        return self.generate_image_cloudflare(enhanced_prompt)

