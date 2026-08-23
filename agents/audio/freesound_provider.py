import os
import logging
from typing import List, Optional
import requests

from agents.audio.base_provider import BaseSoundProvider, SoundResult, DownloadedSound

logger = logging.getLogger(__name__)

FREESOUND_API_BASE = "https://freesound.org/apiv2"

ALIAS_MAP = {
    "rain ambience distant": ["rain ambience", "rain", "light rain"],
    "rain ambience distant soft": ["rain ambience", "rain", "light rain"],
    "pencil scratch glass": ["pencil scratch", "writing pencil", "scratch"],
    "pencil scratch glass surface": ["pencil scratch", "writing pencil", "scratch"],
    "pencil writing glass": ["pencil writing", "writing", "pencil"],
    "pencil drawing writing": ["pencil drawing", "writing", "pencil"],
    "key lock turning": ["key in lock", "turning key", "keys"],
    "key lock turning metal": ["key in lock", "turning key", "keys"],
    "door close soft": ["door close", "closing door"],
    "door close quiet soft": ["door close", "closing door"],
    "phone vibration muffled": ["phone vibration", "vibration", "phone buzz"],
    "phone vibration muffled buzz": ["phone vibration", "vibration", "phone buzz"]
}


def find_aliases(query: str) -> List[str]:
    q_norm = query.lower().strip()
    return ALIAS_MAP.get(q_norm, [])


def normalize_license(raw_license: str) -> Optional[str]:
    if not raw_license:
        return None

    raw_lower = raw_license.lower().strip()

    # Explicitly reject non-commercial or invalid licenses first
    if (
        "noncommercial" in raw_lower
        or "non-commercial" in raw_lower
        or "by-nc" in raw_lower
        or "sampling+" in raw_lower
    ):
        return None

    # Recognize CC0
    if (
        "creative commons 0" in raw_lower
        or "publicdomain/zero" in raw_lower
        or "cc0" in raw_lower
    ):
        return "cc0"

    # Recognize Attribution
    if (
        raw_lower == "attribution"
        or "attribution" in raw_lower
        or "cc-by" in raw_lower
        or raw_lower == "by"
        or "/licenses/by/" in raw_lower
    ):
        return "attribution"

    return None


class FreesoundProvider(BaseSoundProvider):
    """
    Freesound API provider.
    Requires FREESOUND_API_KEY (or compatibility fallbacks) in environment.
    Only fetches sounds with permissive commercial-safe licenses.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("FREESOUND_API_KEY") or os.environ.get("FREESOUND_CLIENT_SECRET")
        if not self.api_key:
            raise ValueError("SFX_PROVIDER_NOT_CONFIGURED: Missing Freesound API key.")

    def search(self, query: str, max_duration_sec: float = 15.0, limit: int = 5) -> List[SoundResult]:
        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        # Construct list of query candidates: [exact_query] + aliases
        candidates = [query]
        aliases = find_aliases(query)
        for alias in aliases:
            if alias not in candidates:
                candidates.append(alias)

        results = []
        # Try each candidate with initial duration limit
        for cand in candidates:
            results = self._search_strategy(cand, max_duration_sec=max_duration_sec, limit=limit)
            if results:
                logger.info(f"Freesound query '{cand}' succeeded with {len(results)} results.")
                return results

        # If strict duration limit produced zero results, allow one controlled fallback to 30.0s for the exact query
        if max_duration_sec <= 15.0:
            logger.info(f"Strict duration limit ({max_duration_sec}s) returned zero results. Retrying exact query '{query}' with 30s limit.")
            results = self._search_strategy(query, max_duration_sec=30.0, limit=limit)
            if results:
                return results

        return []

    def _search_strategy(self, query: str, max_duration_sec: float, limit: int) -> List[SoundResult]:
        # Step 1: Search CC0 separately
        cc0_results = self._search_request(query, max_duration_sec, filter_license='license:"Creative Commons 0"', limit=limit)

        # Step 2: Search Attribution separately
        by_results = self._search_request(query, max_duration_sec, filter_license='license:Attribution', limit=limit)

        # Step 3: Merge and deduplicate
        merged = {}
        for r in cc0_results + by_results:
            merged[r.external_id] = r

        final_results = []
        for r in merged.values():
            if normalize_license(r.license) is not None:
                final_results.append(r)

        if len(final_results) > 0:
            return final_results[:limit]

        # Fallback: if server-filtered searches are empty, perform one controlled duration-only request with larger page size
        logger.info("Server-filtered searches returned 0. Retrying with controlled duration-only query with larger page size...")
        raw_results = self._search_request(query, max_duration_sec, filter_license=None, limit=limit * 4)

        fallback_results = []
        seen = set()
        for r in raw_results:
            if r.external_id not in seen:
                seen.add(r.external_id)
                if normalize_license(r.license) is not None:
                    fallback_results.append(r)

        return fallback_results[:limit]

    def _search_request(self, query: str, max_duration_sec: float, filter_license: Optional[str], limit: int) -> List[SoundResult]:
        # Build filter parameter
        filter_str = f"duration:[0 TO {max_duration_sec}]"
        if filter_license:
            filter_str += f" {filter_license}"

        params = {
            "query": query,
            "filter": filter_str,
            "sort": "score",
            "page_size": limit,
            "fields": "id,name,license,username,duration,previews,tags,score",
        }
        headers = {
            "Authorization": f"Token {self.api_key}"
        }

        try:
            response = requests.get(
                f"{FREESOUND_API_BASE}/search/",
                params=params,
                headers=headers,
                timeout=15
            )
        except requests.Timeout as exc:
            logger.error(f"Freesound provider timeout: {exc}")
            raise RuntimeError("SFX_PROVIDER_TIMEOUT") from exc
        except requests.RequestException as exc:
            logger.error(f"Freesound provider network error: {exc}")
            raise RuntimeError("SFX_PROVIDER_UNAVAILABLE") from exc

        if response.status_code != 200:
            status = response.status_code
            detail = response.text[:200]
            logger.error(f"Freesound search failed: {status} - {detail} (Query: {query})")
            
            if status == 401:
                raise RuntimeError(f"SFX_AUTH_FAILED: {detail}")
            elif status == 400:
                raise RuntimeError(f"SFX_SEARCH_REQUEST_INVALID: {detail}")
            elif status == 403:
                raise RuntimeError(f"SFX_ACCESS_FORBIDDEN: {detail}")
            elif status == 429:
                raise RuntimeError(f"SFX_RATE_LIMITED: {detail}")
            elif status >= 500:
                raise RuntimeError(f"SFX_PROVIDER_UNAVAILABLE: status {status}")
            else:
                raise RuntimeError(f"SFX_PROVIDER_UNAVAILABLE: status {status}")

        data = response.json()
        results = []
        for item in data.get("results", []):
            license_name = item.get("license", "")

            attribution = None
            norm_lic = normalize_license(license_name)
            if norm_lic == "attribution":
                username = item.get('username') or 'unknown'
                name = item.get('name') or 'sound'
                attribution = f"{name} by {username} — {license_name}"

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
