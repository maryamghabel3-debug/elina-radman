"""
Performance & Analytics Agent (The Strategist)
Monitors post-upload metrics (views, retention, CTR, sentiment of comments).
Uses this data to pivot strategies, suggest new hooks, or tweak the editing style.

Real data sources (used automatically when the relevant token is set):
  * YouTube Data API v3  -> real view/like/comment counts for Elina's channel
    (needs YOUTUBE_API_KEY + YOUTUBE_CHANNEL_ID)
  * Instagram Graph API  -> reach/impressions for the connected IG business
    account (needs IG_ACCESS_TOKEN + IG_USER_ID)

If no tokens are configured it falls back to clearly-labelled simulated data so
the pipeline still produces a strategy and never crashes.
"""
import random
import os
import json
from datetime import datetime

import requests

from .base import Agent


class PerformanceAnalyzer(Agent):
    def __init__(self):
        super().__init__("PerformanceAnalyzer", "Analyzes real post metrics to pivot strategy")
        self.metrics_db = "content/performance_metrics.json"
        self.session = requests.Session()

    # ------------------------------------------------------------------ #
    # Real data sources
    # ------------------------------------------------------------------ #
    def fetch_youtube_metrics(self):
        """Aggregate stats for the channel's most recent uploads via YouTube API."""
        key = os.environ.get("YOUTUBE_API_KEY", "")
        channel = os.environ.get("YOUTUBE_CHANNEL_ID", "")
        if not key or not channel:
            return None
        try:
            # 1) Recent videos on the channel
            s = self.session.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "id",
                    "channelId": channel,
                    "order": "date",
                    "maxResults": 10,
                    "type": "video",
                    "key": key,
                },
                timeout=10,
            )
            s.raise_for_status()
            ids = [it["id"]["videoId"] for it in s.json().get("items", []) if it.get("id", {}).get("videoId")]
            if not ids:
                return None
            # 2) Their statistics
            v = self.session.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": ",".join(ids), "key": key},
                timeout=10,
            )
            v.raise_for_status()
            items = v.json().get("items", [])
            views = [int(i["statistics"].get("viewCount", 0)) for i in items]
            likes = [int(i["statistics"].get("likeCount", 0)) for i in items]
            comments = [int(i["statistics"].get("commentCount", 0)) for i in items]
            n = len(views) or 1
            total_views = sum(views)
            return {
                "source": "youtube_api",
                "videos_analyzed": len(items),
                "recent_views": total_views,
                "avg_views": total_views // n,
                "avg_likes": sum(likes) // n,
                "avg_comments": sum(comments) // n,
                # engagement rate = (likes+comments)/views
                "engagement_rate": round(
                    (sum(likes) + sum(comments)) / max(total_views, 1) * 100, 2
                ),
            }
        except (requests.RequestException, ValueError, KeyError) as e:
            self.log(f"YouTube metrics error: {e}", "error")
            return None

    def fetch_instagram_metrics(self):
        """Reach/impressions for the connected IG business account."""
        token = os.environ.get("IG_ACCESS_TOKEN", "")
        user_id = os.environ.get("IG_USER_ID", "")
        if not token or not user_id:
            return None
        try:
            r = self.session.get(
                f"https://graph.facebook.com/v19.0/{user_id}/insights",
                params={
                    "metric": "reach,impressions,profile_views",
                    "period": "week",
                    "access_token": token,
                },
                timeout=10,
            )
            r.raise_for_status()
            data = {d["name"]: d["values"][0]["value"] for d in r.json().get("data", [])}
            return {"source": "instagram_graph", **data}
        except (requests.RequestException, ValueError, KeyError) as e:
            self.log(f"Instagram metrics error: {e}", "error")
            return None

    def simulated_metrics(self):
        """Clearly-labelled fallback when no analytics tokens are configured."""
        return {
            "source": "simulated",
            "recent_views": random.randint(10000, 500000),
            "ctr": round(random.uniform(3.5, 12.0), 1),
            "retention_dropoff": "Seconds 3 to 5",
            "audience_retention": "72%",
            "top_comment_keywords": ["outfit link", "love this", "where to buy", "so aesthetic"],
            "sentiment": "85% Positive, 15% Inquiring",
        }

    # ------------------------------------------------------------------ #
    # Strategy
    # ------------------------------------------------------------------ #
    def build_strategy(self, metrics):
        """Turn whatever metrics we have (real or simulated) into action items."""
        fixes = []
        src = metrics.get("source", "unknown")

        if src == "youtube_api":
            er = metrics.get("engagement_rate", 0)
            if er < 3:
                fixes.append(
                    f"HOOK_FIX: Engagement rate is low ({er}%). Strengthen the first 3 "
                    "seconds and add a clearer value hook in the title/thumbnail."
                )
            else:
                fixes.append(f"KEEP: Engagement healthy ({er}%). Double down on top formats.")
            if metrics.get("avg_views", 0) < metrics.get("recent_views", 0) / max(metrics.get("videos_analyzed", 1), 1) * 0.5:
                fixes.append("CONSISTENCY_FIX: View counts are uneven — post on a steadier schedule.")

        elif src == "instagram_graph":
            reach = metrics.get("reach", 0)
            pv = metrics.get("profile_views", 0)
            if reach and pv / max(reach, 1) < 0.02:
                fixes.append("BIO_FIX: Reach is high but profile visits are low — sharpen bio CTA.")
            fixes.append("KEEP: Track reach weekly; scale the pillars driving the most reach.")

        else:  # simulated
            if metrics.get("ctr", 0) < 5.0:
                fixes.append("THUMBNAIL_FIX: CTR dropping. Larger face in frame 1, higher contrast.")
            else:
                fixes.append("THUMBNAIL_KEEP: Aesthetic working. Keep current hook styles.")
            if "Seconds 3 to 5" in metrics.get("retention_dropoff", ""):
                fixes.append("HOOK_FIX: Drop at second 4. Add a camera-angle/BGM shift before it.")
            kws = metrics.get("top_comment_keywords", [])
            if "where to buy" in kws or "outfit link" in kws:
                fixes.append("SALES_FIX: High purchase intent! Push LTK/Amazon links in next 3 posts.")

        return fixes

    def analyze_past_performance(self):
        print(f"📊 [{self.name}] Analyzing Elina's recent content performance...")

        # Prefer real data; combine sources when multiple are configured.
        metrics = self.fetch_youtube_metrics() or self.fetch_instagram_metrics()
        if metrics is None:
            self.log("No analytics tokens set; using simulated metrics", "info")
            metrics = self.simulated_metrics()
        else:
            self.log(f"Pulled real metrics from {metrics['source']}")

        strategy = self.build_strategy(metrics)
        print(f"   📈 Source: {metrics['source']} | Strategy items: {len(strategy)}")

        os.makedirs(os.path.dirname(self.metrics_db), exist_ok=True)
        with open(self.metrics_db, "w") as f:
            json.dump(
                {"date": datetime.now().isoformat(), "metrics": metrics, "strategy": strategy},
                f,
                indent=2,
            )
        return strategy

    def run(self):
        self.runs += 1
        self.last_run = datetime.now().isoformat()
        return self.analyze_past_performance()


if __name__ == "__main__":
    pa = PerformanceAnalyzer()
    print(json.dumps(pa.run(), indent=2, ensure_ascii=False))
