"""
Deterministic asset pinning for re-renders (M20A SFX, M20B voice).

Re-renders of the same content must resolve the same sound files and reuse
previously generated voice files. Without pinning, every render re-queries
Freesound and re-runs TTS, so re-renders could pick a *different* sound file
or waste time re-generating identical narration, making final content
non-deterministic.

AssetPinner pins resolved assets into storage under deterministic keys:
- SFX:  assets/sfx/{content_id}/{sha256(normalized_query)[:12]}.mp3
        (normalized query = lowercase + stripped + whitespace collapsed;
        timing/gain/fades are mix decisions, not asset identity)
- Voice: voice/{content_id}/{sha256(normalized_text|voice|rate)[:12]}.mp3
        (normalized text = stripped + whitespace collapsed; the key covers
        exactly what changes the TTS output: text + voice + rate)

All storage interactions are soft: a pinning hiccup (network, 404, bucket
misconfiguration) degrades to "not pinned" / "pin skipped" and is logged —
pinning must never fail a render.
"""

import hashlib
import logging
import os
import re
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


class AssetPinner:
    """Pins resolved SFX / generated voice assets in storage for
    deterministic re-renders."""

    # assets/sfx/{content_id}/{sha256(normalized_query)[:12]}.{extension}
    SFX_KEY_TEMPLATE = "assets/sfx/{content_id}/{digest}.{extension}"
    # voice/{content_id}/{sha256(normalized_text|voice|rate)[:12]}.{extension}
    VOICE_KEY_TEMPLATE = "voice/{content_id}/{digest}.{extension}"
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
        return self.SFX_KEY_TEMPLATE.format(content_id=content_id, digest=digest, extension=ext)

    # ------------------------------------------------------------------
    # Voice pinning (M20B)
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_text(text: str) -> str:
        """Strip and collapse internal whitespace runs to one space so
        '  hello   world ' and 'hello world' hash identically. Case is
        preserved: the text is TTS content, not a search query."""
        return re.sub(r"\s+", " ", (text or "").strip())

    def build_voice_key(
        self,
        content_id: str,
        text: str,
        voice_name: str,
        rate: str,
        extension: str = "mp3",
    ) -> str:
        """
        Return the deterministic storage key for a generated voice asset.

        Hash input = normalized text + "|" + voice_name + "|" + rate —
        exactly the inputs that change TTS output.
        """
        payload = f"{self.normalize_text(text)}|{voice_name}|{rate}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[: self.HASH_LENGTH]
        ext = (extension or "mp3").lstrip(".").lower() or "mp3"
        return self.VOICE_KEY_TEMPLATE.format(
            content_id=content_id, digest=digest, extension=ext
        )

    def get_pinned_voice(
        self, content_id: str, text: str, voice_name: str, rate: str
    ) -> Optional[str]:
        """
        If a pinned voice object exists, download it to a temp local file and
        return the local path. Otherwise return None (caller falls back to
        generating the voice).

        Soft by design: any storage error is logged and treated as "not
        pinned" so a pinning hiccup never blocks a render.
        """
        key = self.build_voice_key(content_id, text, voice_name, rate)
        fd, local_path = tempfile.mkstemp(suffix=".mp3", prefix="pinned_voice_")
        os.close(fd)
        try:
            self.storage.download_file(key, local_path)
        except Exception as exc:
            logger.info(
                "No pinned voice for content %s (%r...): %s", content_id, text[:30], exc
            )
            self._quiet_unlink(local_path)
            return None
        if os.path.getsize(local_path) <= 0:
            self._quiet_unlink(local_path)
            return None
        return local_path

    def pin_voice(
        self, content_id: str, text: str, voice_name: str, rate: str, local_path: str
    ) -> str:
        """
        Upload the generated voice file to its deterministic storage key.
        Returns the storage key. Soft: upload failures are logged, never
        raised — the render keeps the local file and continues.
        """
        extension = os.path.splitext(local_path)[1] or ".mp3"
        key = self.build_voice_key(
            content_id, text, voice_name, rate, extension=extension
        )
        try:
            self.storage.upload_file(local_path, key, content_type="audio/mpeg")
            logger.info("Pinned voice for content %s (%r...) -> %s", content_id, text[:30], key)
        except Exception as exc:
            logger.warning(
                "Failed to pin voice for content %s (%r...) to %s: %s",
                content_id, text[:30], key, exc,
            )
        return key

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
