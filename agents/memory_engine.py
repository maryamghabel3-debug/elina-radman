"""
MemoryEngine Agent — Inspired by Letta / MemGPT
Provides persistent, long-term memory and emotional continuity for Elina Radman.
Stores past diary entries, successful content hooks, affiliate items shared,
and persona milestones so daily content never feels generic or disconnected.
"""

import os
import json
from datetime import datetime
from .base import Agent

_MEMORY_PATH = "content/memory_store.json"

_DEFAULT_MEMORY = {
    "persona_core": {
        "name": "Elina Radman",
        "niche": "Petite Quiet Luxury Fashion",
        "philosophy": "Style has no size.",
        "height": "150cm / 4'11\"",
        "location": "Paris / Nuremberg / Global Citizen",
        "current_focus": "Enclothed cognition and effortless tailored silhouettes for petite frames."
    },
    "diary_entries": [
        {
            "date": "2026-07-01",
            "mood": "Inspired & Focused",
            "reflection": "Realized that finding trousers with the exact right rise changes posture immediately. Confidence starts before leaving the mirror."
        }
    ],
    "successful_hooks": [
        "POV: You're 4'11 and styling wide-leg trousers without drowning in fabric 🤍✨",
        "3 petite styling mistakes making you look shorter (and how to fix them today) 🕊️"
    ],
    "shared_affiliate_items": []
}

class MemoryEngine(Agent):
    def __init__(self):
        super().__init__("MemoryEngine", "Long-term persistent memory & emotional continuity agent (MemGPT style)")
        self.memory_path = _MEMORY_PATH
        self._ensure_store()

    def _ensure_store(self):
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        if not os.path.exists(self.memory_path):
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(_DEFAULT_MEMORY, f, indent=2, ensure_ascii=False)

    def load_memory(self) -> dict:
        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.log(f"Error loading memory: {e}; returning default", "warning")
            return _DEFAULT_MEMORY

    def save_memory(self, data: dict):
        try:
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"Error saving memory: {e}", "error")

    def store_event(self, reflection: str, mood: str = "Confident & Serene", category: str = "diary"):
        """Records a new life reflection or content event into Elina's permanent memory."""
        data = self.load_memory()
        today = datetime.now().strftime("%Y-%m-%d")
        
        if category == "diary":
            data.setdefault("diary_entries", []).append({
                "date": today,
                "mood": mood,
                "reflection": reflection
            })
            # Keep only last 50 diary entries
            data["diary_entries"] = data["diary_entries"][-50:]
        elif category == "hook":
            data.setdefault("successful_hooks", []).append(reflection)
            data["successful_hooks"] = data["successful_hooks"][-30:]
        elif category == "affiliate":
            data.setdefault("shared_affiliate_items", []).append({
                "date": today,
                "item": reflection
            })
            
        self.save_memory(data)
        self.log(f"Stored permanent memory event in '{category}'")

    def retrieve_context(self, topic: str = "") -> str:
        """
        Retrieves a rich, formatted context briefing containing Elina's latest diary entries,
        philosophy, and recent hooks to condition the ContentCreator LLM prompt.
        """
        data = self.load_memory()
        core = data.get("persona_core", {})
        recent_diaries = data.get("diary_entries", [])[-2:]
        recent_hooks = data.get("successful_hooks", [])[-2:]
        
        diary_str = " | ".join([f"[{d.get('date')}] ({d.get('mood')}): {d.get('reflection')}" for d in recent_diaries])
        hooks_str = "; ".join(recent_hooks)
        
        briefing = (
            f"[LONG-TERM MEMORY CONTEXT]\n"
            f"Philosophy: {core.get('philosophy')} Focus: {core.get('current_focus')}\n"
            f"Recent Diary/Life Reflections: {diary_str}\n"
            f"Proven Viral Hooks to Channel: {hooks_str}"
        )
        return briefing

    def run(self, action: str = "retrieve", **kwargs):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        if action == "retrieve":
            return self.retrieve_context(kwargs.get("topic", ""))
        elif action == "store":
            self.store_event(
                reflection=kwargs.get("reflection", ""),
                mood=kwargs.get("mood", "Confident"),
                category=kwargs.get("category", "diary")
            )
            return {"status": "stored"}
        return self.load_memory()
