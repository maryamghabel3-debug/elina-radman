import os
import logging
from typing import List
import requests

from agents.audio.base_provider import BaseSoundProvider, SoundResult, DownloadedSound

logger = logging.getLogger(__name__)

FREESOUND_API_BASE = "https://freesound.org/apiv2"
ALLOWED_LICENSES = ["Creative Commons 0", "Attribution", "Attribution Noncommercial"]


class FreesoundProvider(BaseSoundProvider):
    """
    Freesound API provider.
    Requires FREESOUND_API_KEY in environment.
    Only fetches sounds with permissive licenses.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("FREESOUND_API_KEY")
        if not self.api_key:
            raise ValueError("Missing FREESOUND_API_KEY environment variable.")

    def search(self, query: str, max_duration_sec: float = 15.0, limit: int = 5) -> List[SoundResult]:
        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        params = {
            "query": query,
            "filter": f"duration:[0 TO {max_duration_sec}] license:(\"Creative Commons 0\" OR \"Attribution\")",
            "sort": "score",
            "page_size": limit,
            "fields": "id,name,license,username,duration,previews,download,tags",
            "token": self.api_key,
        }

        response = requests.get(f"{FREESOUND_API_BASE}/search/text/", params=params, timeout=15)
        if response.status_code != 200:
            logger.error(f"Freesound search failed: {response.status_code} - {response.text[:200]}")
            return []

        data = response.json()
        results = []
        for item in data.get("results", []):
            license_name = item.get("license", "")
            if not any(allowed in license_name for allowed in ALLOWED_LICENSES):
                continue

            attribution = None
            if "Attribution" in license_name and "Creative Commons 0" not in license_name:
                attribution = f"{item.get('name')} by {item.get('username')} — {license_name}"

            preview_url = None
            previews = item.get("previews", {})
            if previews:
                preview_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")

            results.append(SoundResult(
                provider="freesound",
                external_id=str(item.get("id")),
                name=item.get("name", ""),
                license=license_name,
                attribution=attribution,
                duration_sec=float(item.get("duration", 0)),
                download_url=item.get("download", ""),
                preview_url=preview_url,
                tags=item.get("tags", []),
            ))

        return results

    def download(self, sound: SoundResult, output_path: str) -> DownloadedSound:
        """
        Download the preview MP3 (safer for automated use).
        Full download requires OAuth2 which is more complex.
        """
        if not sound.preview_url:
            raise RuntimeError(f"No preview URL for sound {sound.external_id}")

        response = requests.get(sound.preview_url, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download sound: {response.status_code}")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        return DownloadedSound(local_path=output_path, metadata=sound)
