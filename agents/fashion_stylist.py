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
            "theme": "Parisian Autumn for Petites",
            "color_palette": ["Camel", "Navy", "Cream", "Matte Gold"],
            "aesthetic": "Quiet Luxury, Minimalist, Tailored",
            "target_brands": [
                "Reformation Petite", "Aritzia (Short Lengths)", "Petite Studio NYC",
                "Abercrombie & Fitch (Short/Extra Short)", "Madewell Petite",
                "Everlane", "ASOS Design Petite", "Mango"
            ],
            "instructions_for_hunter": [
                {
                    "category": "trousers",
                    "description": "Effortless tailored wide-leg trousers (Short Length)",
                    "target_platform": "Aritzia / Abercrombie"
                },
                {
                    "category": "outerwear",
                    "description": "Structured minimalist blazer sized for under 5'4\"",
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
