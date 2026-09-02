"""
Deterministic SFX asset pinning (M20A).

Re-renders of the same content must resolve the same sound files. Without
pinning, every render re-queries Freesound and may get a different file for
the same query, making final content non-deterministic.

AssetPinner pins the resolved SFX file into storage under a deterministic
key derived ONLY from (content_id, normalized query). Timing/gain/fades are
mix decisions, not asset identity, and are deliberately NOT part of the key.

All storage interactions are soft: a pinning hiccup (network, 404, bucket
misconfiguration) degrades to "not pinned" / "pin skipped" and is logged —
pinning must never fail a render.

SFX ONLY: voice/music pinning is out of scope (M20B).
"""

import hashlib
import logging
import os
import re
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


class AssetPinner:
    """Pins resolved SFX assets in storage for deterministic re-renders."""

    # assets/sfx/{content_id}/{sha256(normalized_query)[:12]}.{extension}
    KEY_TEMPLATE = "assets/sfx/{content_id}/{digest}.{extension}"
    HASH_LENGTH = 12

    def __init__(self, storage):
        """`storage` must implement upload_file(local, dest, content_type)
        and download_file(storage_path, local_path) (ElinaStorage qualifies)."""
        self.storage = storage

    # ------------------------------------------------------------------
    # Key construction
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_query(query: str) -> str:
        """Lowercase, strip, and collapse internal whitespace runs to one
        space so '  Click ', 'click', and 'CLICK' hash identically."""
        return re.sub(r"\s+", " ", (query or "").strip().lower())

    def build_sfx_key(self, content_id: str, query: str, extension: str = "mp3") -> str:
        """Return the deterministic storage key for a content_id + query."""
        digest = hashlib.sha256(
            self.normalize_query(query).encode("utf-8")
        ).hexdigest()[: self.HASH_LENGTH]
        ext = (extension or "mp3").lstrip(".").lower() or "mp3"
        return self.KEY_TEMPLATE.format(content_id=content_id, digest=digest, extension=ext)

    # ------------------------------------------------------------------
    # Pin / reuse
    # ------------------------------------------------------------------

    def get_pinned_sfx(self, content_id: str, query: str) -> Optional[str]:
        """
        If a pinned storage object exists, download it to a temp local file
        and return the local path. Otherwise return None (caller falls back
        to the provider search).

        Soft by design: any storage error is logged and treated as "not
        pinned" so a pinning hiccup never blocks a render.
        """
        key = self.build_sfx_key(content_id, query)
        fd, local_path = tempfile.mkstemp(suffix=".mp3", prefix="pinned_sfx_")
        os.close(fd)
        try:
            self.storage.download_file(key, local_path)
        except Exception as exc:
            logger.info(
                "No pinned SFX for query %r (content %s): %s", query, content_id, exc
            )
            self._quiet_unlink(local_path)
            return None
        if os.path.getsize(local_path) <= 0:
            self._quiet_unlink(local_path)
            return None
        return local_path

    def pin_sfx(self, content_id: str, query: str, local_path: str) -> str:
        """
        Upload the local SFX file to its deterministic storage key.
        Returns the storage key. Soft: upload failures are logged, never
        raised — the render keeps the local file and continues.
        """
        extension = os.path.splitext(local_path)[1] or ".mp3"
        key = self.build_sfx_key(content_id, query, extension=extension)
        try:
            self.storage.upload_file(local_path, key, content_type="audio/mpeg")
            logger.info("Pinned SFX %r (content %s) -> %s", query, content_id, key)
        except Exception as exc:
            logger.warning(
                "Failed to pin SFX %r (content %s) to %s: %s",
                query, content_id, key, exc,
            )
        return key

    @staticmethod
    def _quiet_unlink(path: str) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass
