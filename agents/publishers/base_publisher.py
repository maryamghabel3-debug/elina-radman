from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PublishResult:
    success: bool
    media_id: Optional[str] = None
    permalink: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False


class BasePublisher(ABC):
    """Abstract publisher adapter. All platform publishers implement this."""

    @abstractmethod
    def publish_reel(self, video_url: str, caption: str) -> PublishResult:
        ...

    @abstractmethod
    def publish_image(self, image_url: str, caption: str) -> PublishResult:
        ...

    @abstractmethod
    def publish_carousel(self, media_urls: list, caption: str) -> PublishResult:
        ...
