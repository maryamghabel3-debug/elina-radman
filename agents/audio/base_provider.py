from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SoundResult:
    provider: str
    external_id: str
    name: str
    license: str
    attribution: Optional[str]
    duration_sec: float
    download_url: str
    preview_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class DownloadedSound:
    local_path: str
    metadata: SoundResult


class BaseSoundProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_duration_sec: float = 15.0, limit: int = 5) -> List[SoundResult]:
        pass

    @abstractmethod
    def download(self, sound: SoundResult, output_path: str) -> DownloadedSound:
        pass
