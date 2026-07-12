"""
Prompt Engineering Agent for AI Image & Video
Upgraded for 2026: Implements Director's Mindset, Structural Prompting, 
and Scene-by-Scene cinematic video scripting.
"""
from .base import Agent
import random
import json
from datetime import datetime

class PromptEngineerAgent(Agent):
    def __init__(self):
        super().__init__("PromptEngineer", "Expert Prompt Engineer for Midjourney V6/V7, Kling, and Google Flow")
        # Base Subject lock
        self.base_subject = (
            "A 25-year-old petite Iranian female clinical psychologist and digital artist, "
            "dark wavy hair, deep dark eyes, calm but emotionally resonant expression"
        )

    # --- PHOTO PROMPT FORMULA (Midjourney V6/Flux Style) ---
    def generate_photo_prompt(self, subject_concept: str, mood: str="melancholic", camera_lens: str="85mm f/1.4") -> str:
        """
        Formula: [Subject] + [Environment/Setting] + [Lighting] + [Style/Medium] + [Camera/Render specs] + [--parameters]
        """
        prompt = (
            f"STRICT INSTRUCTION: USE EXACT FACE FROM ATTACHED REFERENCE. "
            f"[{self.base_subject}] doing [{subject_concept}]. "
            f"Environment: {mood} atmosphere. "
            f"Lighting: Chiaroscuro, dramatic cinematic lighting, deep shadows. "
            f"Style/Medium: Live-action movie still, psychological fine art photography, raw unretouched aesthetic. "
            f"Camera/Specs: Shot on Hasselblad H6D or Arri Alexa 65, {camera_lens}, flawless natural skin texture, "
            f"film grain, ultra-detailed, 8k resolution. "
            f"--cw 100 --v 6.0 --style raw"
        )
        return prompt

    # --- VIDEO PROMPT FORMULA (Kling/Google Flow/Sora Style) ---
    def generate_video_scene_prompt(self, action_desc: str, camera_movement: str, duration: str = "5-second") -> str:
        """
        Formula: The Director's Mindset (Camera Movement + Subject Action + Physics/VFX + Sound + Length)
        """
        prompt = (
            f"A {duration} high-paced cinematic shot. "
            f"CAMERA: {camera_movement}. "
            f"SUBJECT: A young Iranian woman (use attached reference face strictly) wearing an elegant dark outfit. "
            f"ACTION & VFX: {action_desc}. "
            f"LIGHTING: Moody, cinematic high-contrast lighting. "
            f"AESTHETIC: Photorealistic live-action movie still, NOT CGI, no 3D render look. "
            f"SOUND EFFECT INSTRUCTION: Match the audio to the intense visual action."
        )
        return prompt

    def generate_5_shot_carousel_prompts(self, base_concept, styling_logic="", tone="Quiet Luxury") -> list:
        # Fallback to keep compatibility with existing generate.py logic
        return [{"title_fa": "Main Shot", "prompt": self.generate_photo_prompt(base_concept)}]

    def generate_cinematic_json_script(self, base_concept, tone="dark"):
        # Fallback to keep compatibility with existing generate.py logic
        return self.generate_video_scene_prompt(base_concept, "slow push-in")

    def run(self, base_concept, format_type="photo", tone="dark"):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        if format_type == "photo":
            return self.generate_photo_prompt(base_concept)
        return self.generate_video_scene_prompt(base_concept, "cinematic pan")

if __name__ == "__main__":
    agent = PromptEngineerAgent()
    print("Photo Prompt Example:")
    print(agent.generate_photo_prompt("looking out of a rainy window"))
