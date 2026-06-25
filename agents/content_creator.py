"""ContentCreator Agent — Generates captions and scripts"""

from .base import Agent
from datetime import datetime, timedelta
import os
import json


class ContentCreator(Agent):
    def __init__(self):
        super().__init__("ContentCreator", "Generates content pieces")

    def run(self, pillars=None, count=3):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        pillars = pillars or [
            "petite_styling",
            "ootd",
            "capsule_wardrobe",
            "smart_shopping",
            "lifestyle",
        ]

        fallback = {
            "petite_styling": "3 style rules every petite needs 🕊️\n\n1. High-waisted everything\n2. Monochrome = taller\n3. Tailor everything\n\nSave this 📌 What's your #1 style rule? 👇",
            "ootd": "Today's OOTD: Quiet Luxury 🕊️\n\nCropped camel blazer + high-waist trousers\nEvery piece tailored for 4'11\" ✨\n\nWhat are you wearing today? 👇",
            "capsule_wardrobe": "15 pieces. 30+ outfits. My petite capsule 🤍\n\n3 bottoms + 4 tops + 2 blazers + 2 dresses\nAll neutral. Everything matches.\n\nComment CAPSULE for the list 📩",
            "smart_shopping": "Look expensive on a budget 💰\n\n1. Natural fabrics 2. Neutral colors\n3. Tailor everything 4. Less is more\n\nYour best budget style hack? 👇",
            "lifestyle": "A day in my outfits ☕\n\nMorning coffee → stroll → dinner\nSame base, three different looks\n\nCapsule wardrobe magic ✨",
        }
        tags = {
            "petite_styling": "#PetiteStyle #StyleTips #ShortGirlFashion #FashionHacks",
            "ootd": "#OOTD #PetiteStyle #QuietLuxury #4ft11",
            "capsule_wardrobe": "#CapsuleWardrobe #MinimalistStyle #PetiteStyle",
            "smart_shopping": "#AffordableStyle #SmartShopping #QuietLuxury",
            "lifestyle": "#DayInMyLife #PetiteStyle #LifeStyleCreator",
        }

        pieces = []
        for i in range(count):
            p = pillars[i % len(pillars)]
            pid = f"elina-{datetime.now().strftime('%Y%m%d%H%M')}-{p[:4]}"
            piece = {
                "id": pid,
                "pillar": p,
                "caption": fallback.get(p, fallback["ootd"]),
                "hashtags": f"{tags.get(p,'')} #StyledByElina #PetiteFashion",
                "platforms": ["instagram", "tiktok", "pinterest"],
                "status": "pending_approval",
                "created_at": datetime.now().isoformat(),
                "scheduled_for": (datetime.now() + timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )
                + "T10:00:00",
            }
            pieces.append(piece)

        os.makedirs("content/queue", exist_ok=True)
        fp = f"content/queue/{datetime.now().strftime('%Y%m%d%H%M')}.json"
        with open(fp, "w") as f:
            json.dump(pieces, f, indent=2)

        self.log(f"Created {len(pieces)} pieces → {fp}")
        return pieces
