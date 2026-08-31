"""
Character asset resolution for branded carousel slides (M18C-UPDATE).

Elina's carousel slides should show the character (or the story world) for
AI-planned content. `CharacterAssetProvider` is the abstraction the planner
uses; `LocalCharacterAssetProvider` is the simple default implementation
that resolves files from a local directory (e.g. content/assets/characters/).

Contract: providers must be soft — a missing asset returns None and never
raises. The planner additionally guards against provider exceptions.
"""

import os
from pathlib import Path
from typing import Optional

# Recognized character hints (ElinaOS character universe)
KNOWN_CHARACTER_HINTS = ("elina", "elli", "world")

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


class CharacterAssetProvider:
    """Abstract interface for resolving a character image asset for a slide."""

    def get_asset(
        self,
        character_hint: str,   # "elina" | "elli" | "world"
        scene_hint: str,
        slide_type: str,
        template: str,
    ) -> Optional[str]:
        """
        Return a local image path suitable for the given slide, or None.

        Implementations must never raise for missing assets.
        """
        raise NotImplementedError


class LocalCharacterAssetProvider(CharacterAssetProvider):
    """
    Resolves character assets from a local directory.

    Layout convention (flat directory, deterministic resolution):
        <directory>/elina_hero.png
        <directory>/elina_smiling.jpg
        <directory>/elli_default.png
        <directory>/world_market.png

    Resolution order for character_hint in ("elina", "elli"):
      1. a file named "<hint>_<scene>_*" (scene hint present in the name)
      2. a file named "<hint>_hero.*" (the default hero asset)
      3. the first (sorted) file starting with "<hint>_"
      4. None

    For character_hint == "world":
      1. a file matching "<scene>_*" (scene hint present in the name)
      2. the first (sorted) "world_*" file
      3. None
    """

    def __init__(self, directory: Optional[str] = None):
        if directory is None:
            # <repo root>/content/assets/characters
            root = Path(__file__).resolve().parents[2]
            directory = str(root / "content" / "assets" / "characters")
        self.directory = directory

    def _list_images(self) -> list:
        try:
            entries = sorted(os.listdir(self.directory))
        except OSError:
            return []
        return [
            os.path.join(self.directory, name)
            for name in entries
            if os.path.splitext(name)[1].lower() in _IMAGE_EXTS
        ]

    def _pick(self, candidates: list) -> Optional[str]:
        for path in candidates:
            try:
                if os.path.isfile(path) and os.path.getsize(path) > 0:
                    return path
            except OSError:
                continue
        return None

    def get_asset(
        self,
        character_hint: str,
        scene_hint: str,
        slide_type: str,
        template: str,
    ) -> Optional[str]:
        hint = (character_hint or "").strip().lower()
        scene = (scene_hint or "").strip().lower().replace(" ", "_")[:40]
        images = self._list_images()
        if not images:
            return None

        if hint == "world":
            if scene:
                match = [p for p in images if f"_{scene}_" in os.path.basename(p).lower()
                         or os.path.basename(p).lower().startswith(f"{scene}_")]
                hit = self._pick(match)
                if hit:
                    return hit
            return self._pick([p for p in images if os.path.basename(p).lower().startswith("world_")])

        if hint not in KNOWN_CHARACTER_HINTS:
            # Unknown hint: try it as a plain prefix, otherwise None.
            return self._pick([p for p in images if os.path.basename(p).lower().startswith(f"{hint}_")])

        if scene:
            match = [p for p in images
                     if os.path.basename(p).lower().startswith(f"{hint}_")
                     and f"_{scene}_" in os.path.basename(p).lower()]
            hit = self._pick(match)
            if hit:
                return hit
        hero = self._pick([p for p in images
                           if os.path.basename(p).lower().startswith(f"{hint}_hero")])
        if hero:
            return hero
        return self._pick([p for p in images
                           if os.path.basename(p).lower().startswith(f"{hint}_")])
