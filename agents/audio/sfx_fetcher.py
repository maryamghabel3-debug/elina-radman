import logging
from typing import Optional
from agents.audio.base_provider import BaseSoundProvider, DownloadedSound
from agents.audio.freesound_provider import FreesoundProvider

logger = logging.getLogger(__name__)


class SFXFetcher:
    """
    High-level SFX fetcher. Uses Freesound by default.
    Can be extended to multi-provider fallback later.
    """

    def __init__(self, provider: Optional[BaseSoundProvider] = None):
        self.provider = provider or FreesoundProvider()

    def fetch_best_match(self, query: str, output_path: str, max_duration_sec: float = 15.0) -> Optional[DownloadedSound]:
        results = self.provider.search(query, max_duration_sec=max_duration_sec, limit=5)
        if not results:
            logger.warning(f"No results for query: {query}")
            return None

        # For now: pick the first (highest score) match with a preview URL
        for result in results:
            if result.preview_url:
                return self.provider.download(result, output_path)

        logger.warning(f"No downloadable result for query: {query}")
        return None
