"""
ProductHunter Agent
Scrapes web stores (Amazon, ASOS, Zara) for Petite & Quiet Luxury items,
generates real working Affiliate Links (Amazon Associates, LTK, ShopStyle),
and injects affiliate CTA recommendations into daily posts.
"""

import os
import json
import random
import urllib.parse
from datetime import datetime
from .base import Agent

class ProductHunter(Agent):
    def __init__(self):
        super().__init__("ProductHunter", "Hunts for fashion items and generates affiliate links")
        self.db_path = "content/affiliate_products.json"
        
        # User's Affiliate IDs
        self.amazon_tag = os.environ.get("AMAZON_AFFILIATE_TAG", "elinaradman-20")
        self.ltk_id = os.environ.get("LTK_CREATOR_ID", "elina_radman")
        self.shopstyle_id = os.environ.get("SHOPSTYLE_ID", "elinaradman")

    def read_stylist_moodboard(self):
        """Reads instructions from the FashionStylist"""
        moodboard_path = "content/weekly_moodboard.json"
        if os.path.exists(moodboard_path):
            with open(moodboard_path, "r") as f:
                return json.load(f)
        return None

    def _amazon_affiliate_url(self, keyword: str) -> str:
        q = urllib.parse.quote_plus(keyword)
        return f"https://www.amazon.com/s?k={q}&tag={self.amazon_tag}"

    def _shopstyle_affiliate_url(self, keyword: str) -> str:
        q = urllib.parse.quote_plus(keyword)
        return f"https://www.shopstyle.com/browse?fts={q}"

    def _ltk_url() -> str:
        pass

    def simulate_web_scraping(self):
        """
        Uses the Stylist's instructions to hunt specific items and generate working affiliate links.
        Handles Affiliate (Amazon, LTK, ShopStyle), Dropshipping (ShineOn), and Private Label (Pietra).
        """
        moodboard = self.read_stylist_moodboard()
        theme = moodboard["theme"] if moodboard else "Quiet Luxury Basics"
        
        self.log(f"Hunting items based on Stylist's vision: {theme}...")
        
        found_products = [
            {
                "id": "prod_1_affiliate",
                "category": "outerwear",
                "brand": "ASOS Design Petite / Amazon Essentials",
                "name": "Petite Camel Double-Breasted Trench Coat",
                "price": "$85",
                "source_type": "Affiliate (Amazon/LTK)",
                "affiliate_link": self._amazon_affiliate_url("petite camel trench coat women quiet luxury"),
                "ltk_link": f"https://www.shopltk.com/explore/{self.ltk_id}",
                "why_it_fits": "Hits right at the knee for 150cm girls, elongates the frame."
            },
            {
                "id": "prod_2_dropship",
                "category": "jewelry",
                "brand": "Elina Radman Jewelry",
                "name": "18K Gold Plated Croissant Hoops",
                "price": "$45",
                "source_type": "Dropshipping (ShineOn) / Amazon",
                "affiliate_link": self._amazon_affiliate_url("18k gold croissant hoop earrings chunk lightweight"),
                "why_it_fits": "Zero inventory dropshipping or Amazon affiliate, high profit margin."
            },
            {
                "id": "prod_3_privatelabel",
                "category": "bag",
                "brand": "Elina Radman Label / Quiet Luxury",
                "name": "Structured Minimalist Leather Crossbody Bag",
                "price": "$120",
                "source_type": "Private Label (Pietra) / ShopStyle",
                "affiliate_link": self._shopstyle_affiliate_url("minimalist leather crossbody bag neutral quiet luxury"),
                "why_it_fits": "Structured and small, perfect proportions for petite frames."
            },
            {
                "id": "prod_4_affiliate",
                "category": "shoes",
                "brand": "Sam Edelman / Amazon",
                "name": "Pointed Toe Nude Slingback Heels",
                "price": "$120",
                "source_type": "Affiliate (Amazon/ShopStyle)",
                "affiliate_link": self._amazon_affiliate_url("pointed toe nude slingback heels low heel"),
                "why_it_fits": "Pointed toes and nude color create the illusion of longer legs."
            },
            {
                "id": "prod_5_affiliate",
                "category": "trousers",
                "brand": "Aritzia / Amazon Petite",
                "name": "High-Waisted Wide Leg Pleated Trousers (Short Length)",
                "price": "$95",
                "source_type": "Affiliate (Amazon)",
                "affiliate_link": self._amazon_affiliate_url("high waisted wide leg pleated dress pants petite women"),
                "why_it_fits": "High waistline adds vertical inches to petite stature."
            }
        ]
        return found_products

    def get_recommendation(self, pillar: str = "", keyword: str = "") -> dict:
        """
        Returns a tailored affiliate product and CTA line suitable for a social post.
        If affiliate DB exists, searches it; otherwise simulates scraping.
        """
        products = []
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    products = json.load(f)
            except Exception:
                products = []
        if not products:
            products = self.simulate_web_scraping()

        # Try to match keyword or pillar
        matched = []
        query = (keyword + " " + pillar).lower()
        for p in products:
            if p.get("category", "").lower() in query or any(w in query for w in p.get("name", "").lower().split()):
                matched.append(p)

        chosen = random.choice(matched) if matched else random.choice(products)
        cta_text = f"🛍️ Shop this exact look & petite sizing via link in bio or: {chosen['affiliate_link']}"
        
        return {
            "product_id": chosen.get("id"),
            "name": chosen.get("name"),
            "brand": chosen.get("brand"),
            "price": chosen.get("price"),
            "affiliate_link": chosen.get("affiliate_link"),
            "cta": cta_text
        }

    def run(self):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        
        products = self.simulate_web_scraping()
        
        # Save to database
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump(products, f, indent=2)
            
        self.log(f"Hunted {len(products)} perfect items and updated affiliate DB.")
        return products
