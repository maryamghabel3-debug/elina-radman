import os
import requests
import shutil
try:
    from gradio_client import Client, handle_file
except ImportError:
    pass

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
        # Hugging Face Token for Free Cloud GPU access
        self.hf_token = os.environ.get("HF_TOKEN", "")
        self.output_dir = "content/images/"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Ensure a reference image exists for Face consistency
        self.reference_face = "docs/elina_reference.jpg"
        if not os.path.exists("docs"):
            os.makedirs("docs", exist_ok=True)
        if not os.path.exists(self.reference_face):
            # Create a blank dummy file so code doesn't crash before user uploads real face
            with open(self.reference_face, "wb") as f:
                f.write(b"dummy")

    def generate_consistent_character(self, prompt):
        """
        Uses FREE Hugging Face Spaces (InstantID / PuLID) via gradio_client.
        Takes Elina's reference face and applies it perfectly to the new prompt.
        """
        print(f"🎨 [VisualCreator] Generating STRICT consistent face using Free Cloud GPUs...")
        if not self.hf_token:
            print("⚠️ HF_TOKEN not found! Please add it to your secrets for free cloud generation.")
            return "mock_face.jpg"
            
        character_prompt = (
            f"Elina Radman, 24yo Iranian woman, petite, highly detailed, photorealistic, 8k, {prompt}"
        )
        
        output_path = os.path.join(self.output_dir, f"elina_{os.urandom(4).hex()}.jpg")
        
        try:
            # We connect to a free public Space for Face Consistency (e.g., InstantID)
            # The client handles the API queue and returns the image!
            client = Client("InstantX/InstantID", hf_token=self.hf_token)
            
            # This simulates passing the reference image and prompt to the cloud UI
            print(f"🚀 [VisualCreator] Sending face reference and prompt to HuggingFace ZeroGPU...")
            result = client.predict(
                face_image=handle_file(self.reference_face),
                prompt=character_prompt,
                negative_prompt="anime, cartoon, deformed, bad anatomy",
                api_name="/generate_image"
            )
            
            # Copy result to our output directory
            if isinstance(result, str) and os.path.exists(result):
                shutil.copy(result, output_path)
                print(f"✅ [VisualCreator] Image saved: {output_path}")
                return output_path
                
        except Exception as e:
            print(f"❌ [VisualCreator] Cloud API Error: {e}")
            return "error_face.jpg"

