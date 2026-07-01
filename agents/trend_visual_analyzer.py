"""TrendVisualAnalyzer Agent — Learns the *look* of what's going viral.

Downloads the top trending fashion photos (from TrendHunter.top_images), then
extracts a dominant colour palette and simple visual signals from each one.
The aggregated palette is fed to the PromptEngineer so Elina's generated photos
visually echo whatever aesthetic is pulling the most views right now.

Only depends on Pillow + numpy (already in requirements). Every step degrades
gracefully: a failed download or decode is skipped, never fatal.
"""

import os
import io
import json
import colorsys
from collections import Counter
from datetime import datetime

import requests

from .base import Agent

try:
    from PIL import Image
    import numpy as np
    _HAS_DEPS = True
except ImportError:  # pragma: no cover - deps are in requirements
    _HAS_DEPS = False

_OUT_PATH = "content/trend_visuals.json"

# Human-readable names for broad hue buckets (for prompt wording).
_HUE_NAMES = [
    (0.04, "red"), (0.09, "orange"), (0.17, "yellow"), (0.42, "green"),
    (0.55, "teal"), (0.70, "blue"), (0.83, "purple"), (0.95, "pink"), (1.01, "red"),
]


class TrendVisualAnalyzer(Agent):
    def __init__(self):
        super().__init__("TrendVisualAnalyzer", "Analyzes trending photos for palette & style")
        self.session = requests.Session()
        # A real browser UA + Reddit referer are needed; preview.redd.it returns
        # 403 on bare hotlinks.
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Referer": "https://www.reddit.com/",
                "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
            }
        )

    # ------------------------------------------------------------------ #
    def _download_image(self, url):
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        except (requests.RequestException, OSError) as e:
            self.log(f"Image download/decode failed ({url[:60]}): {e}", "error")
            return None

    @staticmethod
    def _rgb_to_hex(rgb):
        return "#{:02x}{:02x}{:02x}".format(*(int(c) for c in rgb))

    @staticmethod
    def _hue_name(rgb):
        r, g, b = (c / 255.0 for c in rgb)
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        if s < 0.12:
            return "cream/neutral" if v > 0.6 else "charcoal/neutral"
        for edge, name in _HUE_NAMES:
            if h <= edge:
                return name
        return "neutral"

    def _dominant_colors(self, img, k=4, sample=64):
        """Return the top-k dominant colours via a simple quantised histogram."""
        img = img.resize((sample, sample))
        arr = np.asarray(img).reshape(-1, 3)
        # Quantise to a 32-step grid so near-identical colours group together
        quant = (arr // 32) * 32 + 16
        keys = [tuple(int(c) for c in px) for px in quant]
        common = Counter(keys).most_common(k)
        total = sum(c for _, c in common) or 1
        return [
            {
                "hex": self._rgb_to_hex(rgb),
                "name": self._hue_name(rgb),
                "weight": round(count / total, 3),
            }
            for rgb, count in common
        ]

    def analyze_image(self, url):
        img = self._download_image(url)
        if img is None:
            return None
        w, h = img.size
        orientation = "portrait" if h > w * 1.1 else "landscape" if w > h * 1.1 else "square"
        return {
            "url": url,
            "orientation": orientation,
            "palette": self._dominant_colors(img),
        }

    # ------------------------------------------------------------------ #
    def run(self, images=None, limit=5):
        """Analyse trending images. If `images` (list of trend dicts) is not
        given, pull them from TrendHunter.top_images()."""
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        if not _HAS_DEPS:
            self.log("Pillow/numpy not installed; skipping visual analysis", "error")
            return {"error": "missing_dependencies"}

        if images is None:
            try:
                from .trend_hunter import TrendHunter

                th = TrendHunter()
                th.run()
                images = th.top_images(limit=limit)
            except Exception as e:
                self.log(f"Could not load trending images: {e}", "error")
                images = []

        analyses = []
        for item in images[:limit]:
            url = item.get("image") if isinstance(item, dict) else item
            if not url:
                continue
            result = self.analyze_image(url)
            if result:
                result["title"] = item.get("name") if isinstance(item, dict) else None
                analyses.append(result)

        # Aggregate the most common palette colours across all trending photos
        palette_counter = Counter()
        name_counter = Counter()
        for a in analyses:
            for c in a["palette"]:
                palette_counter[c["hex"]] += c["weight"]
                name_counter[c["name"]] += c["weight"]

        aggregate = {
            "generated_at": datetime.now().isoformat(),
            "images_analyzed": len(analyses),
            "top_colors": [hex_ for hex_, _ in palette_counter.most_common(5)],
            "dominant_tones": [name for name, _ in name_counter.most_common(3)],
            "per_image": analyses,
        }

        try:
            os.makedirs(os.path.dirname(_OUT_PATH), exist_ok=True)
            with open(_OUT_PATH, "w") as f:
                json.dump(aggregate, f, indent=2)
        except OSError as e:
            self.log(f"Could not save visual report: {e}", "error")

        self.log(
            f"Analyzed {len(analyses)} trend photos; "
            f"dominant tones: {aggregate['dominant_tones']}"
        )
        return aggregate

    @staticmethod
    def load_latest_palette():
        """Helper for PromptEngineer: returns the last aggregate report or None."""
        try:
            if os.path.exists(_OUT_PATH):
                with open(_OUT_PATH) as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
        return None


if __name__ == "__main__":
    tva = TrendVisualAnalyzer()
    report = tva.run()
    print(json.dumps({k: v for k, v in report.items() if k != "per_image"}, indent=2))
