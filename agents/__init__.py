"""ElinaOS Agent System — Extensible agent framework

Psychology-first build. Fashion / affiliate agents were removed in the
cleanup/remove-fashion-content pass.
"""

from .base import Agent
from .memory_engine import MemoryEngine
from .faceless_studio import FacelessStudio
from .image_studio import ImageStudio
from .video_generator import DirectorAgent
from .lip_sync_studio import LipSyncStudio
from .trend_hunter import TrendHunter
from .content_creator import ContentCreator

__all__ = [
    "Agent",
    "MemoryEngine",
    "FacelessStudio",
    "ImageStudio",
    "DirectorAgent",
    "LipSyncStudio",
    "TrendHunter",
    "ContentCreator",
]
