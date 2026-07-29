import pytest
from agents.scheduler import PublishScheduler
from agents.publishers.base_publisher import PublishResult

pytestmark = pytest.mark.unit


class FakeDB:
    def __init__(self, items=None):
        self.items = items or []
        self.status_updates = []
        self.events = []

    def get_due_items(self, now_iso):
        return self.items

    def update_status(self, item_id, new_status, extra=None):
        self.status_updates.append((item_id, new_status, extra or {}))
        return []

    def log_event(self, content_id, event_type, from_status, to_status, actor, detail=""):
        self.events.append(event_type)
        return []


class FakeStorage:
    def create_signed_url(self, key, ttl):
        return f"https://signed.example/{key}"


class FakePublisher:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def publish_reel(self, video_url, caption):
        self.calls.append(("reel", video_url))
        return self.result

    def publish_image(self, image_url, caption):
        self.calls.append(("image", image_url))
        return self.result

    def publish_carousel(self, media_urls, caption):
        self.calls.append(("carousel", media_urls))
        return self.result


def make_item(**overrides):
    item = {
        "id": "uuid-1",
        "custom_id": "ELN-TEST-1",
        "content_type": "reel",
        "caption_fa": "کپشن تست",
        "hashtags": ["#تست"],
        "media_keys": ["intake/video.mp4"],
        "status": "APPROVED",
        "attempts": 0,
    }
    item.update(overrides)
    return item


def test_successful_publish_marks_published():
    db = FakeDB([make_item()])
    pub = FakePublisher(PublishResult(success=True, media_id="123", permalink="https://insta/p/1"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["published"] == 1
    statuses = [u[1] for u in db.status_updates]
    assert "PUBLISHING" in statuses
    assert "PUBLISHED" in statuses


def test_retryable_failure_goes_to_retry_pending():
    db = FakeDB([make_item()])
    pub = FakePublisher(PublishResult(success=False, error_code="4", error_message="rate limit", retryable=True))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["retry"] == 1
    statuses = [u[1] for u in db.status_updates]
    assert "RETRY_PENDING" in statuses


def test_permanent_failure_goes_to_failed():
    db = FakeDB([make_item()])
    pub = FakePublisher(PublishResult(success=False, error_code="100", error_message="bad request", retryable=False))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["failed"] == 1
    statuses = [u[1] for u in db.status_updates]
    assert "FAILED" in statuses


def test_no_media_fails_without_publishing():
    db = FakeDB([make_item(media_keys=[])])
    pub = FakePublisher(PublishResult(success=True))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["failed"] == 1
    assert pub.calls == []


def test_max_attempts_reached_fails():
    db = FakeDB([make_item(attempts=2)])
    pub = FakePublisher(PublishResult(success=False, error_code="4", error_message="rate limit", retryable=True))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    s.run_once()
    statuses = [u[1] for u in db.status_updates]
    assert "FAILED" in statuses


def test_carousel_uses_all_media_keys():
    db = FakeDB([make_item(content_type="carousel", media_keys=["a.jpg", "b.jpg", "c.jpg"])])
    pub = FakePublisher(PublishResult(success=True, media_id="9"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    s.run_once()
    kind, urls = pub.calls[0]
    assert kind == "carousel"
    assert len(urls) == 3
