"""TrendVideoAnalyzer Agent — Reverse-engineers WHY trending videos go viral.

For each trending fashion video it:
  1. Pulls rich metadata from the YouTube Data API (title, description, tags,
     view/like/comment counts, duration) plus the TOP comments (how people
     actually react).
  2. Feeds all of that to Gemini for a full teardown: topic, hook, structure,
     filming/editing style, how the caption/script is written, engagement
     drivers, and the concrete reasons it earned so many views — then a
     ready-to-shoot blueprint for recreating it as Elina.

Graceful degradation:
  * no YOUTUBE_API_KEY -> can still analyse a title/description you pass in.
  * no GEMINI_API_KEY  -> returns the raw metadata + a heuristic summary.
"""

import os
import json
from datetime import datetime

import requests

from .base import Agent
from . import vision

_OUT_PATH = "content/trend_videos.json"


class TrendVideoAnalyzer(Agent):
    def __init__(self):
        super().__init__("TrendVideoAnalyzer", "Reverse-engineers viral fashion videos")
        self.session = requests.Session()
        self.youtube_api_key = os.environ.get("YOUTUBE_API_KEY", "")

    # ------------------------------------------------------------------ #
    # Metadata + comments
    # ------------------------------------------------------------------ #
    def fetch_video_details(self, video_id: str) -> dict:
        """Full snippet + statistics + contentDetails for one video."""
        if not self.youtube_api_key:
            return {}
        try:
            r = self.session.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics,contentDetails",
                    "id": video_id,
                    "key": self.youtube_api_key,
                },
                timeout=10,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            if not items:
                return {}
            it = items[0]
            sn, stats = it.get("snippet", {}), it.get("statistics", {})
            return {
                "video_id": video_id,
                "title": sn.get("title"),
                "description": (sn.get("description") or "")[:1500],
                "tags": sn.get("tags", [])[:20],
                "channel": sn.get("channelTitle"),
                "published_at": sn.get("publishedAt"),
                "duration": it.get("contentDetails", {}).get("duration"),
                "views": int(stats["viewCount"]) if stats.get("viewCount") else None,
                "likes": int(stats["likeCount"]) if stats.get("likeCount") else None,
                "comments": int(stats["commentCount"]) if stats.get("commentCount") else None,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        except (requests.RequestException, ValueError, KeyError) as e:
            self.log(f"YouTube details error for {video_id}: {e}", "error")
            return {}

    def fetch_top_comments(self, video_id: str, limit: int = 15) -> list:
        """The most-liked comments — how the audience actually reacts."""
        if not self.youtube_api_key:
            return []
        try:
            r = self.session.get(
                "https://www.googleapis.com/youtube/v3/commentThreads",
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "order": "relevance",
                    "maxResults": limit,
                    "textFormat": "plainText",
                    "key": self.youtube_api_key,
                },
                timeout=10,
            )
            r.raise_for_status()
            out = []
            for it in r.json().get("items", []):
                c = it["snippet"]["topLevelComment"]["snippet"]
                out.append({"text": c.get("textDisplay", "")[:300], "likes": c.get("likeCount", 0)})
            return out
        except (requests.RequestException, ValueError, KeyError) as e:
            # Comments are often disabled; not fatal
            self.log(f"YouTube comments unavailable for {video_id}: {e}", "info")
            return []

    # ------------------------------------------------------------------ #
    # Reverse-engineering teardown
    # ------------------------------------------------------------------ #
    def reverse_engineer(self, meta: dict, comments: list) -> dict:
        """Full Gemini teardown of a single video. Falls back to a heuristic
        summary when Gemini is unavailable."""
        engagement_rate = None
        if meta.get("views"):
            inter = (meta.get("likes") or 0) + (meta.get("comments") or 0)
            engagement_rate = round(inter / max(meta["views"], 1) * 100, 3)

        if not vision.gemini_available():
            return {
                "engine": "heuristic",
                "engagement_rate_pct": engagement_rate,
                "note": "Set GEMINI_API_KEY for a full AI teardown.",
                "top_comment_samples": [c["text"] for c in comments[:5]],
            }

        comment_block = "\n".join(f"- ({c['likes']}👍) {c['text']}" for c in comments[:12]) or "N/A"
        prompt = (
            "You are a viral short-form video strategist and cinematographer. "
            "Reverse-engineer this trending fashion video from its metadata and top "
            "comments. Deduce filming/editing even though you only see metadata. "
            "Respond ONLY with JSON using EXACTLY these keys:\n"
            "{\n"
            '  "topic": "what the video is about in one line",\n'
            '  "hook": "the likely first-3-seconds hook and why it stops the scroll",\n'
            '  "structure": ["ordered beats of the video, e.g. hook -> reveal -> tips -> CTA"],\n'
            '  "filming_style": "shot types, camera movement, transitions, pace, setting",\n'
            '  "editing": "cuts, captions/text-on-screen, music/sound, effects",\n'
            '  "script_copywriting": "how the caption/spoken script is written (tone, structure, CTA)",\n'
            '  "audience_reaction": "what the comments reveal about why people engage",\n'
            '  "why_it_went_viral": ["concrete ranked reasons for the high view count"],\n'
            '  "elina_recreation": {"concept": "how Elina should adapt this", '
            '"hook": "her opening line", "shot_list": ["3-6 concrete shots"], '
            '"caption": "a ready caption in her voice"}\n'
            "}\n\n"
            f"TITLE: {meta.get('title')}\n"
            f"CHANNEL: {meta.get('channel')}\n"
            f"VIEWS: {meta.get('views')} | LIKES: {meta.get('likes')} | COMMENTS: {meta.get('comments')} "
            f"| ENGAGEMENT: {engagement_rate}%\n"
            f"DURATION: {meta.get('duration')}\n"
            f"TAGS: {', '.join(meta.get('tags', []))}\n"
            f"DESCRIPTION: {meta.get('description')}\n"
            f"TOP COMMENTS:\n{comment_block}"
        )
        result = vision.analyze_text(prompt)
        if result.get("available"):
            result.pop("available", None)
            result["engine"] = "gemini"
            result["engagement_rate_pct"] = engagement_rate
            return result
        if result.get("error"):
            self.log(f"Video teardown error: {result['error']}", "error")
        return {"engine": "error", "engagement_rate_pct": engagement_rate}

    # ------------------------------------------------------------------ #
    def analyze_video(self, video_id: str = None, meta: dict = None) -> dict:
        """Analyse one video by id (fetches everything) or by a supplied meta dict."""
        if meta is None:
            if not video_id:
                return {"error": "need video_id or meta"}
            meta = self.fetch_video_details(video_id)
        vid = meta.get("video_id") or video_id
        comments = self.fetch_top_comments(vid) if vid else []
        teardown = self.reverse_engineer(meta, comments)
        return {"meta": meta, "top_comments": comments[:8], "teardown": teardown}

    def run(self, videos=None, limit=3):
        """Analyse trending videos. If `videos` is None, pull YouTube trends
        from TrendHunter. `videos` items may be trend dicts (with 'url'/id) or
        raw video-id strings."""
        self.runs += 1
        self.last_run = datetime.now().isoformat()

        if videos is None:
            try:
                from .trend_hunter import TrendHunter

                th = TrendHunter()
                th.run()
                videos = [t for t in th.trends if t.get("source") == "youtube"][:limit]
            except Exception as e:
                self.log(f"Could not load trending videos: {e}", "error")
                videos = []

        results = []
        for v in videos[:limit]:
            if isinstance(v, str):
                vid = v
            else:
                url = v.get("url", "")
                vid = url.split("v=")[-1] if "v=" in url else v.get("video_id")
            if not vid:
                continue
            results.append(self.analyze_video(video_id=vid))

        report = {
            "generated_at": datetime.now().isoformat(),
            "videos_analyzed": len(results),
            "analyses": results,
        }
        try:
            os.makedirs(os.path.dirname(_OUT_PATH), exist_ok=True)
            with open(_OUT_PATH, "w") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except OSError as e:
            self.log(f"Could not save video report: {e}", "error")

        self.log(f"Reverse-engineered {len(results)} trending videos")
        return report

    @staticmethod
    def load_latest():
        try:
            if os.path.exists(_OUT_PATH):
                with open(_OUT_PATH) as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
        return None


if __name__ == "__main__":
    tva = TrendVideoAnalyzer()
    rep = tva.run()
    print(json.dumps(rep, indent=2, ensure_ascii=False)[:2000])
