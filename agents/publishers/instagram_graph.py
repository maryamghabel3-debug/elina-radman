import os
import time
import logging
from typing import Optional

import httpx

from agents.publishers.base_publisher import BasePublisher, PublishResult

logger = logging.getLogger(__name__)

TRANSIENT_ERROR_CODES = {1, 2, 4, 17, 341}


class InstagramGraphPublisher(BasePublisher):
    """
    Official Instagram Graph API publisher.
    Requires:
      IG_USER_ID          - Instagram Business/Creator account ID
      IG_ACCESS_TOKEN     - long-lived access token
      META_GRAPH_API_BASE - e.g. https://graph.facebook.com
      META_GRAPH_API_VERSION - e.g. v21.0
    Media must be provided as a publicly reachable URL
    (short-lived signed URL from Supabase Storage).
    """

    def __init__(self):
        self.ig_user_id = os.environ.get("IG_USER_ID")
        self.access_token = os.environ.get("IG_ACCESS_TOKEN")
        self.api_version = os.environ.get("META_GRAPH_API_VERSION")
        self.api_base = os.environ.get("META_GRAPH_API_BASE")

        if not self.api_base:
            raise ValueError("Missing META_GRAPH_API_BASE in environment. Set META_GRAPH_API_BASE, e.g. https://graph.facebook.com")
        if not self.api_version:
            raise ValueError("Missing META_GRAPH_API_VERSION in environment. Set META_GRAPH_API_VERSION, e.g. v21.0")

        # Strip trailing slash from base
        self.api_base = self.api_base.rstrip("/")
        self.graph_base = f"{self.api_base}/{self.api_version}"

        if not self.ig_user_id or not self.access_token:
            raise ValueError("Missing IG_USER_ID or IG_ACCESS_TOKEN in environment.")

    def _post(self, path: str, data: dict) -> dict:
        data = {**data, "access_token": self.access_token}
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{self.graph_base}/{path}", data=data)
        body = resp.json()
        if resp.status_code >= 400:
            raise InstagramApiError(body)
        return body

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, "access_token": self.access_token}
        with httpx.Client(timeout=60) as client:
            resp = client.get(f"{self.graph_base}/{path}", params=params)
        body = resp.json()
        if resp.status_code >= 400:
            raise InstagramApiError(body)
        return body

    def _wait_until_ready(self, container_id: str, max_wait_seconds: int = 300) -> bool:
        waited = 0
        interval = 10
        while waited < max_wait_seconds:
            status = self._get(container_id, {"fields": "status_code"})
            code = status.get("status_code")
            if code == "FINISHED":
                return True
            if code == "ERROR":
                return False
            time.sleep(interval)
            waited += interval
        return False

    def _publish_container(self, container_id: str) -> PublishResult:
        result = self._post(f"{self.ig_user_id}/media_publish", {"creation_id": container_id})
        media_id = result.get("id")
        permalink = None
        try:
            info = self._get(media_id, {"fields": "permalink"})
            permalink = info.get("permalink")
        except Exception:
            pass
        return PublishResult(success=True, media_id=media_id, permalink=permalink)

    def publish_reel(self, video_url: str, caption: str) -> PublishResult:
        try:
            container = self._post(
                f"{self.ig_user_id}/media",
                {"media_type": "REELS", "video_url": video_url, "caption": caption},
            )
            container_id = container.get("id")
            if not container_id:
                return PublishResult(success=False, error_code="NO_CONTAINER", error_message="No container id returned")
            if not self._wait_until_ready(container_id):
                return PublishResult(success=False, error_code="CONTAINER_NOT_READY", error_message="Container processing failed or timed out", retryable=True)
            return self._publish_container(container_id)
        except InstagramApiError as e:
            return e.to_result()
        except httpx.HTTPError as e:
            return PublishResult(success=False, error_code="NETWORK", error_message=str(e), retryable=True)

    def publish_image(self, image_url: str, caption: str) -> PublishResult:
        try:
            container = self._post(
                f"{self.ig_user_id}/media",
                {"image_url": image_url, "caption": caption},
            )
            container_id = container.get("id")
            if not container_id:
                return PublishResult(success=False, error_code="NO_CONTAINER", error_message="No container id returned")
            return self._publish_container(container_id)
        except InstagramApiError as e:
            return e.to_result()
        except httpx.HTTPError as e:
            return PublishResult(success=False, error_code="NETWORK", error_message=str(e), retryable=True)

    def publish_carousel(self, media_urls: list, caption: str) -> PublishResult:
        try:
            children = []
            for url in media_urls:
                child = self._post(f"{self.ig_user_id}/media", {"image_url": url, "is_carousel_item": "true"})
                child_id = child.get("id")
                if child_id:
                    children.append(child_id)
            if len(children) < 2:
                return PublishResult(success=False, error_code="CAROUSEL_CHILDREN", error_message="Need at least 2 valid children")
            container = self._post(
                f"{self.ig_user_id}/media",
                {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption},
            )
            container_id = container.get("id")
            if not container_id:
                return PublishResult(success=False, error_code="NO_CONTAINER", error_message="No container id returned")
            return self._publish_container(container_id)
        except InstagramApiError as e:
            return e.to_result()
        except httpx.HTTPError as e:
            return PublishResult(success=False, error_code="NETWORK", error_message=str(e), retryable=True)


class InstagramApiError(Exception):
    def __init__(self, body: dict):
        self.body = body or {}
        err = self.body.get("error", {})
        self.code = err.get("code")
        self.message = err.get("message", "Unknown Instagram API error")
        super().__init__(self.message)

    def to_result(self) -> PublishResult:
        retryable = self.code in TRANSIENT_ERROR_CODES
        return PublishResult(
            success=False,
            error_code=str(self.code),
            error_message=self.message,
            retryable=retryable,
        )
