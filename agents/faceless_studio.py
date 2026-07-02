"""
FacelessStudio Agent — Inspired by MoneyPrinterV2 & Open-AI-Design-Agent
Autonomous video production engine that turns a single keyword or fashion tip
into a complete, viral 9:16 short video (script -> TTS -> visuals -> subtitle overlay).
"""

import os
import glob
import json
import asyncio
from datetime import datetime
from .base import Agent

class FacelessStudio(Agent):
    def __init__(self):
        super().__init__("FacelessStudio", "Autonomous Faceless Shorts/Reels Video Generator (MoneyPrinterV2 style)")
        self.output_dir = "content/videos/"
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_short_script(self, topic: str) -> list:
        """Generates a 3-part viral script for a short video."""
        self.log(f"Drafting 3-part viral script for topic: '{topic}'...")
        return [
            {"scene": 1, "text": f"POV: You're 4'11 and styling {topic}.", "duration": 2.5},
            {"scene": 2, "text": "Pro secret: Focus on vertical lines and monochrome layering to elongate your frame.", "duration": 3.0},
            {"scene": 3, "text": "Save this petite fashion tip and tap link in bio for exact pieces 🤍✨", "duration": 2.5}
        ]

    def _render_tts(self, text: str, output_audio: str) -> bool:
        """Synthesizes natural voiceover using edge-tts if installed."""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
            asyncio.run(communicate.save(output_audio))
            return os.path.exists(output_audio)
        except Exception as e:
            self.log(f"edge-tts voiceover skipped ({e})", "warning")
            return False

    def create_faceless_short(self, topic: str = "Quiet Luxury Basics") -> dict:
        """
        Executes end-to-end video production: creates script, renders visual slides
        using Elina's reference photos, applies dynamic text overlay, and writes MP4.
        """
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        
        script = self.generate_short_script(topic)
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        out_mp4 = os.path.join(self.output_dir, f"faceless_{ts}.mp4")
        out_mp3 = os.path.join(self.output_dir, f"faceless_{ts}.mp3")
        
        full_text = " ".join([s["text"] for s in script])
        tts_ok = self._render_tts(full_text, out_mp3)
        
        try:
            import cv2
            import numpy as np

            refs = sorted(glob.glob("images/*.jpg"))
            if not refs:
                self.log("No reference photos found in images/ for faceless short", "error")
                return {"error": "no_reference_photos"}

            # Load and crop image to 9:16 (540x960)
            img = cv2.imread(refs[0])
            h, w = img.shape[:2]
            target_ratio = 9 / 16.0
            if w / h > target_ratio:
                new_w = int(h * target_ratio)
                offset = (w - new_w) // 2
                img = img[:, offset:offset+new_w]
            else:
                new_h = int(w / target_ratio)
                offset = (h - new_h) // 2
                img = img[offset:offset+new_h, :]
            img = cv2.resize(img, (540, 960))
            h, w = img.shape[:2]

            out = cv2.VideoWriter(out_mp4, cv2.VideoWriter_fourcc(*'mp4v'), 30, (w, h))
            
            # Render each scene
            for scene_data in script:
                duration_sec = scene_data["duration"]
                frames = int(duration_sec * 30)
                text = scene_data["text"]
                
                for f in range(frames):
                    # Slight zoom per scene
                    zoom = 1.0 + (0.08 * f / frames)
                    cw, ch = int(w / zoom), int(h / zoom)
                    x1, y1 = (w - cw) // 2, (h - ch) // 2
                    frame = cv2.resize(img[y1:y1+ch, x1:x1+cw], (w, h))
                    
                    # Dark subtitle banner at bottom
                    cv2.rectangle(frame, (0, h - 180), (w, h - 80), (0, 0, 0), -1)
                    
                    # Word wrap basic display
                    words = text.split()
                    line1 = " ".join(words[:len(words)//2 + 1])
                    line2 = " ".join(words[len(words)//2 + 1:])
                    cv2.putText(frame, line1, (30, h - 140), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                    if line2:
                        cv2.putText(frame, line2, (30, h - 105), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                        
                    cv2.putText(frame, "@elina.radman | #StyledByElina", (30, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (212, 197, 185), 1)
                    out.write(frame)
                    
            out.release()
            self.log(f"Faceless viral short produced: {out_mp4}")
            return {
                "video_path": out_mp4,
                "audio_path": out_mp3 if tts_ok else "",
                "topic": topic,
                "script": script,
                "status": "ready"
            }
        except Exception as e:
            self.log(f"FacelessStudio rendering error: {e}", "error")
            return {"error": str(e)}

    def run(self, topic: str = "Quiet Luxury Basics") -> dict:
        return self.create_faceless_short(topic)
