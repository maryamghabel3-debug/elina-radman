"""
Prompt Engineering Agent for AI Image & Video
Upgraded for 2026: Implements Director's Mindset, Structural Prompting, 
and Scene-by-Scene cinematic video scripting.
"""
import random

class PromptEngineerAgent:
    def __init__(self):
        self.name = "PromptEngineer"
        self.desc = "Master Prompt Engineer for Midjourney V6/V7, Kling, and Google Flow"

    # --- PHOTO PROMPT FORMULA (Midjourney V6/Flux Style) ---
    def generate_photo_prompt(self, subject_concept: str, mood: str, camera_lens: str) -> str:
        """
        Formula: [Subject] + [Environment/Setting] + [Lighting] + [Style/Medium] + [Camera/Render specs] + [--parameters]
        """
        # Base Subject lock
        subject = (
            "A 25-year-old petite Iranian female clinical psychologist and digital artist, "
            "dark wavy hair, deep dark eyes, calm but emotionally resonant expression"
        )
        
        # Structural arrangement
        prompt = (
            f"STRICT INSTRUCTION: USE EXACT FACE FROM ATTACHED REFERENCE. "
            f"[{subject}] doing [{subject_concept}]. "
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

if __name__ == "__main__":
    agent = PromptEngineerAgent()
    print("Photo Prompt Example:")
    print(agent.generate_photo_prompt("looking out of a rainy window", "melancholic", "85mm f/1.4"))
    print("\nVideo Prompt Example:")
    print(agent.generate_video_scene_prompt("The window shatters into black butterflies", "Fast dolly out", "4-second"))
