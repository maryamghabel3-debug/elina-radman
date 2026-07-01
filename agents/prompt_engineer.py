"""
Prompt Engineering Agent for AI Video
Generates highly structured, professional, and cinematic prompts based on the 
"Card Sovereign Workflow" style to maximize consistency and pressure in AI Videos.
"""
from .base import Agent
from datetime import datetime

class PromptEngineerAgent(Agent):
    def __init__(self):
        super().__init__("PromptEngineer", "Expert Prompt Engineer for Cinematic AI Video")

    def generate_cinematic_prompt(self, base_concept, tone="dark"):
        self.log(f"Engineering high-pressure cinematic prompt for: {base_concept}")
        
        # We apply the structured prompting technique (like CCAIPS or Card Sovereign)
        structured_prompt = (
            f"Using [Elina's Reference Image] as live-action character reference, generate a cinematic video. "
            f"Full live-action throughout. No anime, no animation, no text or symbols. "
            f"Style: {tone} cinematic atmosphere, overwhelming tension, visually explosive.\n\n"
            f"CAMERA LANGUAGE: Multi-angle fast cuts with handheld breathing feel. "
            f"Extreme low-angle upshots or dynamic tracking shots. "
            f"Heavy depth of field throughout. Every move feels intentional and weighted.\n\n"
            f"SCENE DIRECTION: {base_concept}\n\n"
            f"PERFORMANCE: Slow deliberate movement. Cold composed energy. Every gesture intentional."
        )
        
        # If the model allows sound design notes (e.g. for OpenMontage to pick up)
        sound_design = (
            "SOUND DESIGN: Deep resonant ambient hum. Slow-motion low-frequency audio stretch. "
            "Sharp whoosh sounds for sudden movements. Epic electronic or orchestral score rising beneath."
        )
        
        return {
            "visual_prompt": structured_prompt,
            "sound_design": sound_design,
            "rhythm_notes": "Alternate between full speed and extreme slow motion to create cinematic tension."
        }

    def run(self, base_concept, tone="dark"):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        return self.generate_cinematic_prompt(base_concept, tone)
