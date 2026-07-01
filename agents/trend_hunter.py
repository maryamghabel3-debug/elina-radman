"""TrendHunter Agent — Finds viral content formats"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from .base import Agent


class TrendHunter(Agent):
    def __init__(self):
        super().__init__("TrendHunter", "Scans for viral fashion trends across platforms")
        self.trends = []

    def get_pinterest_trends(self, limit=5):
        """Fetches and parses the Pinterest fashion RSS feed for free trend hunting.

        Falls back to a clearly-labelled mock entry if the feed is unreachable
        or cannot be parsed, so downstream code always gets usable data.
        """
        url = "https://www.pinterest.com/ideas/womens-fashion/feed/"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ElinaOS/1.0; +trend-hunter)"}
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            trends = []
            # RSS 2.0: channel/item/title ; Atom: entry/title
            items = root.findall(".//item") or root.findall(
                ".//{http://www.w3.org/2005/Atom}entry"
            )
            for item in items[:limit]:
                title_el = item.find("title")
                if title_el is None:
                    title_el = item.find("{http://www.w3.org/2005/Atom}title")
                title = (title_el.text or "").strip() if title_el is not None else ""
                if title:
                    trends.append(
                        {
                            "name": title,
                            "platform": "pinterest",
                            "format": "image/carousel",
                            "effort": "low",
                        }
                    )
            if trends:
                return trends
            self.log("Pinterest feed returned no parseable items; using mock", "info")
        except (requests.RequestException, ET.ParseError) as e:
            self.log(f"Pinterest scrape error: {e}", "error")

        # Explicit mock fallback (clearly labelled so it isn't mistaken for live data)
        return [
            {
                "name": "Trending Fashion Pin (mock)",
                "platform": "pinterest",
                "format": "image/carousel",
                "effort": "low",
                "mock": True,
            }
        ]

    def get_youtube_trends(self):
        """Fetches YouTube Shorts trends (Can be expanded with YouTube Data API)"""
        return [
            {
                "name": "Day in the Life Vlogs",
                "platform": "youtube",
                "format": "long-form",
                "effort": "high",
            },
            {
                "name": "AI Tech Reviews",
                "platform": "youtube",
                "format": "shorts",
                "effort": "medium",
            }
        ]

    def get_tiktok_trends(self):
        """Simulates TikTokApi / Instagram scraping"""
        return [
            {
                "name": "Transitions / Outfit changes",
                "platform": "tiktok",
                "format": "short-video",
                "effort": "medium",
            },
            {
                "name": "GRWM Storytime",
                "platform": "tiktok+ig",
                "format": "video",
                "effort": "medium",
            }
        ]

    def run(self):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        
        self.trends = (
            self.get_pinterest_trends() + 
            self.get_youtube_trends() + 
            self.get_tiktok_trends()
        )
        
        self.log(f"Found {len(self.trends)} trends")
        return self.trends

