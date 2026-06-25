"""
FashionStylist Agent
Acts as Elina's personal Art Director and Fashion Stylist.
Creates weekly mood boards, color palettes, and instructs the ProductHunter
on exactly what items to look for or design for her Private Label.
"""

import json
import os
from datetime import datetime
from .base import Agent

class FashionStylist(Agent):
    def __init__(self):
        super().__init__("FashionStylist", "Directs Elina's style and instructs ProductHunter")
        self.moodboard_path = "content/weekly_moodboard.json"

    def create_weekly_vision(self):
        """Creates the aesthetic vision for the week"""
        self.log("Creating new weekly fashion moodboard for Elina...")
        
        vision = {
            "week": datetime.now().strftime("%Y-W%W"),
            "theme": "Nature-Inspired Minimalism & Enclothed Cognition",
            "color_palette": ["Olive Green", "Camel", "Cream", "Matte Gold"],
            "aesthetic": "Quiet Luxury, Eco-friendly, Tailored",
            "target_brands": [
                "Reformation Petite (Priority)", "Aritzia (Short Lengths)", "Petite Studio NYC",
                "Abercrombie & Fitch", "Everlane", "ASOS Design Petite",
                "*Open to any sustainable/eco-friendly petite brands*"
            ],
            "instructions_for_hunter": [
                {
                    "category": "trousers",
                    "description": "Linen or organic cotton wide-leg trousers (Short Length)",
                    "target_platform": "Aritzia / Abercrombie / Global Search"
                },
                {
                    "category": "outerwear",
                    "description": "Earth-toned structured blazer, confidence-boosting fit",
                    "target_platform": "Petite Studio NYC / Reformation"
                },
                {
                    "category": "jewelry",
                    "description": "18k gold plated minimalist croissant hoops (Dropshipping/ShineOn)",
                    "target_platform": "ShineOn"
                },
                {
                    "category": "bag",
                    "description": "Structured leather crossbody bag neutral color (Private Label)",
                    "target_platform": "Pietra Studio"
                },
                {
                    "category": "shoes",
                    "description": "Pointed-toe slingback heels nude (Affiliate)",
                    "target_platform": "ShareASale / ShopStyle"
                }
            ]
        }
        
        os.makedirs(os.path.dirname(self.moodboard_path), exist_ok=True)
        with open(self.moodboard_path, "w") as f:
            json.dump(vision, f, indent=2)
            
        return vision

    def run(self):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        
        vision = self.create_weekly_vision()
        self.log(f"Vision set: {vision['theme']}. 4 items requested.")
        return vision
