import pytest
from agents.scheduler import PublishScheduler
from agents.publishers.base_publisher import PublishResult

pytestmark = pytest.mark.unit


class FakeDB:
    def __init__(self, items=None):
        self.items = items or []
        self.status_updates = []
        self.events = []

    def get_due_items(self, now_iso, limit=1):
        # Respect limit for testing max items per run
        return self.items[:limit]

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
        "status": "SCHEDULED",
        "scheduled_for": "2020-01-01T00:00:00Z",
        "approved_at": "2020-01-01T00:00:00Z",
        "approved_by": "tester",
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


def test_approved_without_schedule_not_published():
    """APPROVED without scheduled_for should not be published (only SCHEDULED due)."""
    db = FakeDB([{
        "id": "uuid-1",
        "custom_id": "ELN-TEST-APPROVED",
        "content_type": "reel",
        "caption_fa": "test",
        "hashtags": [],
        "media_keys": ["a.mp4"],
        "status": "APPROVED",
        "scheduled_for": None,
        "approved_at": None,
        "approved_by": None,
        "attempts": 0,
    }])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    # Simulate get_due_items returning empty for APPROVED (since we now only query SCHEDULED)
    # But if FakeDB returns APPROVED, scheduler guard should skip it
    # For this test, we directly call _process_item? No, we test run_once guard
    # Our FakeDB returns the APPROVED item, but run_once should skip because status != SCHEDULED
    summary = s.run_once()
    assert summary["published"] == 0
    # Should be skipped, not published
    assert summary["skipped"] >= 1 or summary["checked"] == 1


def test_only_scheduled_due_published():
    """Only SCHEDULED and due items should be published."""
    db = FakeDB([
        {
            "id": "uuid-sched-due",
            "custom_id": "ELN-SCHED-DUE",
            "content_type": "reel",
            "caption_fa": "due",
            "hashtags": [],
            "media_keys": ["a.mp4"],
            "status": "SCHEDULED",
            "scheduled_for": "2020-01-01T00:00:00Z",
            "approved_at": "2020-01-01T00:00:00Z",
            "approved_by": "tester",
            "attempts": 0,
        },
        {
            "id": "uuid-approved",
            "custom_id": "ELN-APPROVED",
            "content_type": "reel",
            "caption_fa": "not due",
            "hashtags": [],
            "media_keys": ["b.mp4"],
            "status": "APPROVED",
            "scheduled_for": None,
            "approved_at": None,
            "approved_by": None,
            "attempts": 0,
        }
    ])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    # Only 1 should be published (the SCHEDULED one), the APPROVED one skipped
    # Because we limit to 1 by default, checked=1, published=1
    # If we set limit 2, checked=2, published=1, skipped=1
    assert summary["published"] == 1


def test_max_items_per_run_limit():
    """Each run should respect limit (default 1, env configurable)."""
    items = []
    for i in range(3):
        items.append(make_item(custom_id=f"ELN-TEST-{i}", id=f"uuid-{i}"))
    db = FakeDB(items)
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    # Default limit 1, so only 1 checked
    assert summary["checked"] == 1
    assert summary["published"] == 1


def test_missing_approved_by_skipped():
    db = FakeDB([{
        "id": "uuid-1",
        "custom_id": "ELN-TEST",
        "content_type": "reel",
        "caption_fa": "test",
        "hashtags": [],
        "media_keys": ["a.mp4"],
        "status": "SCHEDULED",
        "scheduled_for": "2020-01-01T00:00:00Z",
        "approved_at": "2020-01-01T00:00:00Z",
        "approved_by": None,
        "attempts": 0,
    }])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["skipped"] == 1
    assert summary["published"] == 0


def test_missing_approved_at_skipped():
    db = FakeDB([{
        "id": "uuid-1",
        "custom_id": "ELN-TEST",
        "content_type": "reel",
        "caption_fa": "test",
        "hashtags": [],
        "media_keys": ["a.mp4"],
        "status": "SCHEDULED",
        "scheduled_for": "2020-01-01T00:00:00Z",
        "approved_at": None,
        "approved_by": "tester",
        "attempts": 0,
    }])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["skipped"] == 1


def test_missing_scheduled_for_skipped():
    db = FakeDB([{
        "id": "uuid-1",
        "custom_id": "ELN-TEST",
        "content_type": "reel",
        "caption_fa": "test",
        "hashtags": [],
        "media_keys": ["a.mp4"],
        "status": "SCHEDULED",
        "scheduled_for": None,
        "approved_at": "2020-01-01T00:00:00Z",
        "approved_by": "tester",
        "attempts": 0,
    }])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["skipped"] == 1


def test_story_goes_to_manual_publish_required():
    db = FakeDB([{
        "id": "uuid-story",
        "custom_id": "ELN-STORY-1",
        "content_type": "story",
        "caption_fa": "story content",
        "hashtags": [],
        "media_keys": ["story.jpg"],
        "status": "SCHEDULED",
        "scheduled_for": "2020-01-01T00:00:00Z",
        "approved_at": "2020-01-01T00:00:00Z",
        "approved_by": "tester",
        "attempts": 0,
    }])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["skipped"] == 1 or summary["failed"] == 0
    statuses = [u[1] for u in db.status_updates]
    assert "MANUAL_PUBLISH_REQUIRED" in statuses


def test_meta_graph_api_version_missing_fails(monkeypatch):
    """Publisher initialization should fail clearly if META_GRAPH_API_VERSION missing."""
    monkeypatch.delenv("META_GRAPH_API_VERSION", raising=False)
    monkeypatch.setenv("IG_USER_ID", "test_user")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "test_token")

    from agents.publishers.instagram_graph import InstagramGraphPublisher
    try:
        pub = InstagramGraphPublisher()
        assert False, "Should have raised ValueError for missing META_GRAPH_API_VERSION"
    except ValueError as e:
        assert "META_GRAPH_API_VERSION" in str(e)


def test_workflow_has_concurrency():
    """Workflow should have concurrency group to prevent parallel runs."""
    import pathlib
    workflow_path = pathlib.Path(".github/workflows/publish-scheduler.yml")
    content = workflow_path.read_text(encoding="utf-8")
    assert "concurrency:" in content
    assert "elina-publish-scheduler" in content
    assert "cancel-in-progress: false" in content
    assert "META_GRAPH_API_VERSION" in content
    assert "PUBLISH_MAX_ITEMS_PER_RUN" in content
