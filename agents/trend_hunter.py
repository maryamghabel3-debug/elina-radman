"""TrendHunter Agent — Finds REAL, currently-trending fashion content.

Data sources (all free, no API key required):
  * Reddit "top of week/month" fashion feeds  -> real posts ranked by upvotes
    (a strong proxy for views/engagement) INCLUDING the post image URL, so Elina
    can see exactly which photos are pulling the most views right now.
  * Google Trends RSS                          -> trending search queries.

The old Pinterest RSS endpoint was removed by Pinterest (returns 404), so it is
no longer used. Every network call degrades gracefully: on failure or rate-limit
the agent returns clearly-labelled mock data instead of crashing.
"""

import re
import time
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

from .base import Agent

# Reddit XML namespaces
_ATOM = "http://www.w3.org/2005/Atom"
_MRSS = "http://search.yahoo.com/mrss/"

# A descriptive User-Agent is required by Reddit; generic ones get 429/403.
_UA = "ElinaOS/1.0 (fashion trend hunter; +https://github.com/maryamghabel3-debug/elina-radman)"

# Subreddits that best match Elina's niche (petite / quiet luxury / women's fashion)
_FASHION_SUBS = [
    "femalefashionadvice",
    "petitefashionadvice",
    "womensstreetwear",
    "streetwear",
]


class TrendHunter(Agent):
    def __init__(self):
        super().__init__("TrendHunter", "Scans for viral fashion trends across platforms")
        self.trends = []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _UA})

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get(self, url, timeout=10, retries=2, backoff=3):
        """GET with simple retry/backoff for Reddit's rate limiting (HTTP 429)."""
        for attempt in range(retries + 1):
            try:
                r = self.session.get(url, timeout=timeout)
                if r.status_code == 429:
                    self.log(f"Rate limited (429) on {url}; backing off", "info")
                    if attempt < retries:
                        time.sleep(backoff * (attempt + 1))
                        continue
                    return None
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                self.log(f"Request error on {url}: {e}", "error")
                if attempt < retries:
                    time.sleep(backoff)
                    continue
                return None
        return None

    @staticmethod
    def _extract_image(entry):
        """Pull the best image URL out of a Reddit Atom entry."""
        # 1) media:thumbnail (present on image/link posts)
        thumb = entry.find(f"{{{_MRSS}}}thumbnail")
        if thumb is not None and thumb.get("url"):
            return TrendHunter._upscale(thumb.get("url"))
        # 2) Parse the HTML <content> for a preview.redd.it image
        content = entry.find(f"{{{_ATOM}}}content")
        if content is not None and content.text:
            text = html.unescape(content.text)
            m = re.search(r'src="(https://(?:preview|i)\.redd\.it/[^"]+)"', text)
            if m:
                return TrendHunter._upscale(m.group(1))
        return None

    @staticmethod
    def _upscale(url):
        """Reddit thumbnails come cropped to 140px; request a larger preview."""
        if not url:
            return url
        # Bump the tiny 140px crop to a usable 640px preview when present
        url = re.sub(r"width=\d+", "width=640", url)
        url = re.sub(r"height=\d+", "height=640", url)
        url = re.sub(r"crop=1:1,smart", "", url)
        return url

    # ------------------------------------------------------------------ #
    # Sources
    # ------------------------------------------------------------------ #
    def get_reddit_trends(self, subs=None, period="week", per_sub=4):
        """Real trending fashion posts ranked by upvotes, with image URLs.

        Reddit's Atom feed returns posts already sorted by score (top), so the
        first items are the highest-engagement / most-viewed posts of the period.
        """
        subs = subs or _FASHION_SUBS
        trends = []
        for sub in subs:
            url = f"https://www.reddit.com/r/{sub}/top/.rss?t={period}&limit={per_sub}"
            r = self._get(url)
            if r is None:
                continue
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as e:
                self.log(f"Reddit parse error for r/{sub}: {e}", "error")
                continue

            entries = root.findall(f"{{{_ATOM}}}entry")
            # rank within the sub -> higher rank = more upvotes/views
            for rank, entry in enumerate(entries[:per_sub]):
                title_el = entry.find(f"{{{_ATOM}}}title")
                link_el = entry.find(f"{{{_ATOM}}}link")
                title = (title_el.text or "").strip() if title_el is not None else ""
                if not title:
                    continue
                trends.append(
                    {
                        "name": title,
                        "platform": f"reddit/r/{sub}",
                        "format": "image/discussion",
                        "effort": "low",
                        "image": self._extract_image(entry),
                        "url": link_el.get("href") if link_el is not None else None,
                        # rank 0 == top post of the week for this sub
                        "popularity_rank": rank + 1,
                        "source": "reddit",
                    }
                )
            # be polite to Reddit between subs to avoid 429
            time.sleep(1.5)

        return trends

    def get_google_trends(self, geo="US", limit=8, fashion_only=True):
        """Trending Google search queries (optionally filtered to fashion terms)."""
        url = f"https://trends.google.com/trending/rss?geo={geo}"
        r = self._get(url, retries=1)
        if r is None:
            return []
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError as e:
            self.log(f"Google Trends parse error: {e}", "error")
            return []

        keywords = (
            "fashion", "style", "outfit", "dress", "wear", "trend", "clothes",
            "shoe", "bag", "jean", "denim", "skirt", "coat", "aesthetic", "petite",
        )
        trends = []
        ns = {"ht": "https://trends.google.com/trending/rss"}
        for item in root.findall(".//item"):
            title_el = item.find("title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            if not title:
                continue
            if fashion_only and not any(k in title.lower() for k in keywords):
                continue
            traffic_el = item.find("ht:approx_traffic", ns)
            pic_el = item.find("ht:picture", ns)
            trends.append(
                {
                    "name": title,
                    "platform": "google_trends",
                    "format": "search_query",
                    "effort": "low",
                    "image": pic_el.text if pic_el is not None else None,
                    "approx_traffic": traffic_el.text if traffic_el is not None else None,
                    "source": "google_trends",
                }
            )
        return trends[:limit]

    def get_evergreen_formats(self):
        """Curated, always-relevant short-form formats for Elina's niche.

        These are intentionally static best-practice formats (not live data) and
        are clearly labelled so they are never mistaken for scraped trends.
        """
        return [
            {"name": "GRWM Storytime", "platform": "tiktok+ig", "format": "video", "effort": "medium", "curated": True},
            {"name": "Outfit transition / 3 ways to style", "platform": "tiktok+ig", "format": "short-video", "effort": "medium", "curated": True},
            {"name": "Photo carousel: 'looks expensive on a budget'", "platform": "instagram", "format": "carousel", "effort": "low", "curated": True},
            {"name": "Day-in-the-life petite vlog", "platform": "youtube", "format": "long-form", "effort": "high", "curated": True},
        ]

    # ------------------------------------------------------------------ #
    # Orchestration
    # ------------------------------------------------------------------ #
    def top_images(self, limit=5):
        """Convenience: the highest-engagement posts that HAVE an image.

        Directly answers 'which photos are getting the most views' — returns
        real trending posts (sorted by their popularity rank) that carry an image.
        """
        with_images = [t for t in self.trends if t.get("image")]
        with_images.sort(key=lambda t: t.get("popularity_rank", 999))
        return with_images[:limit]

    def run(self):
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        reddit = self.get_reddit_trends()
        google = self.get_google_trends()

        # If both live sources failed (offline / rate-limited), fall back to a
        # clearly-labelled mock so downstream code always has usable data.
        if not reddit and not google:
            self.log("All live trend sources unavailable; using mock data", "info")
            live = [
                {
                    "name": "Quiet luxury capsule wardrobe (mock)",
                    "platform": "reddit",
                    "format": "image/discussion",
                    "effort": "low",
                    "image": None,
                    "mock": True,
                    "source": "mock",
                }
            ]
        else:
            live = reddit + google

        self.trends = live + self.get_evergreen_formats()
        self.log(
            f"Found {len(reddit)} Reddit + {len(google)} Google trends "
            f"({len(self.top_images())} with images)"
        )
        return self.trends


if __name__ == "__main__":
    th = TrendHunter()
    all_trends = th.run()
    print("\n=== TOP TRENDING IMAGES (most views) ===")
    for t in th.top_images():
        print(f"  #{t.get('popularity_rank')} [{t['platform']}] {t['name'][:55]}")
        print(f"     🖼  {t.get('image')}")
