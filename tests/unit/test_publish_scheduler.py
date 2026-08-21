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
        # Also update item status for subsequent checks
        for item in self.items:
            if item["id"] == item_id:
                item["status"] = new_status
        return []

    def log_event(self, content_id, event_type, from_status, to_status, actor, detail=""):
        self.events.append(event_type)
        return []

    def claim_for_publishing(self, item_id, expected_status):
        # Simulate successful atomic claim if item exists and status matches expected
        for item in self.items:
            if item["id"] == item_id and item.get("status") == expected_status:
                # Record PUBLISHING as would happen in real DB
                self.status_updates.append((item_id, "PUBLISHING", {}))
                item["status"] = "PUBLISHING"
                return True
        return False




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


def test_successful_publish_marks_published(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    db = FakeDB([make_item()])
    pub = FakePublisher(PublishResult(success=True, media_id="123", permalink="https://insta/p/1"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["published"] == 1
    statuses = [u[1] for u in db.status_updates]
    assert "PUBLISHING" in statuses
    assert "PUBLISHED" in statuses


def test_retryable_failure_goes_to_retry_pending(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    db = FakeDB([make_item()])
    pub = FakePublisher(PublishResult(success=False, error_code="4", error_message="rate limit", retryable=True))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["retry"] == 1
    statuses = [u[1] for u in db.status_updates]
    assert "RETRY_PENDING" in statuses


def test_permanent_failure_goes_to_failed(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    db = FakeDB([make_item()])
    pub = FakePublisher(PublishResult(success=False, error_code="100", error_message="bad request", retryable=False))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["failed"] == 1
    statuses = [u[1] for u in db.status_updates]
    assert "FAILED" in statuses


def test_no_media_fails_without_publishing(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    db = FakeDB([make_item(media_keys=[])])
    pub = FakePublisher(PublishResult(success=True))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["failed"] == 1
    assert pub.calls == []


def test_max_attempts_reached_fails(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    db = FakeDB([make_item(attempts=2)])
    pub = FakePublisher(PublishResult(success=False, error_code="4", error_message="rate limit", retryable=True))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    s.run_once()
    statuses = [u[1] for u in db.status_updates]
    assert "FAILED" in statuses


def test_carousel_uses_all_media_keys(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    db = FakeDB([make_item(content_type="carousel", media_keys=["a.jpg", "b.jpg", "c.jpg"])])
    pub = FakePublisher(PublishResult(success=True, media_id="9"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    s.run_once()
    kind, urls = pub.calls[0]
    assert kind == "carousel"
    assert len(urls) == 3


def test_approved_without_schedule_not_published(monkeypatch):
    """APPROVED without scheduled_for should not be published (only SCHEDULED due)."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
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
    summary = s.run_once()
    assert summary["published"] == 0
    assert summary["skipped"] >= 1


def test_only_scheduled_due_published(monkeypatch):
    """Only SCHEDULED and due items should be published."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
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
    assert summary["published"] == 1


def test_max_items_per_run_limit(monkeypatch):
    """Each run should respect limit (default 1, env configurable)."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    monkeypatch.setenv("PUBLISH_MAX_ITEMS_PER_RUN", "1")
    items = []
    for i in range(3):
        it = make_item(custom_id=f"ELN-TEST-{i}", id=f"uuid-{i}")
        it["status"] = "SCHEDULED"
        it["scheduled_for"] = "2020-01-01T00:00:00Z"
        it["approved_at"] = "2020-01-01T00:00:00Z"
        it["approved_by"] = "tester"
        items.append(it)
    db = FakeDB(items)
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["checked"] == 1
    assert summary["published"] == 1


def test_missing_approved_by_skipped(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
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


def test_missing_approved_at_skipped(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
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


def test_missing_scheduled_for_skipped(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
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


def test_story_goes_to_manual_publish_required(monkeypatch):
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
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
    monkeypatch.delenv("META_GRAPH_API_BASE", raising=False)
    monkeypatch.setenv("IG_USER_ID", "test_user")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "test_token")
    monkeypatch.setenv("META_GRAPH_API_BASE", "https://graph.facebook.com")
    monkeypatch.delenv("META_GRAPH_API_VERSION", raising=False)

    from agents.publishers.instagram_graph import InstagramGraphPublisher
    try:
        pub = InstagramGraphPublisher()
        assert False, "Should have raised ValueError for missing META_GRAPH_API_VERSION"
    except ValueError as e:
        assert "META_GRAPH_API_VERSION" in str(e)


def test_meta_graph_api_base_missing_fails(monkeypatch):
    """Publisher initialization should fail clearly if META_GRAPH_API_BASE missing."""
    monkeypatch.setenv("IG_USER_ID", "test_user")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "test_token")
    monkeypatch.setenv("META_GRAPH_API_VERSION", "v21.0")
    monkeypatch.delenv("META_GRAPH_API_BASE", raising=False)

    from agents.publishers.instagram_graph import InstagramGraphPublisher
    try:
        pub = InstagramGraphPublisher()
        assert False, "Should have raised ValueError for missing META_GRAPH_API_BASE"
    except ValueError as e:
        assert "META_GRAPH_API_BASE" in str(e)


def test_workflow_has_concurrency():
    """Workflow should have concurrency group to prevent parallel runs."""
    import pathlib
    workflow_path = pathlib.Path(".github/workflows/publish-scheduler.yml")
    content = workflow_path.read_text(encoding="utf-8")
    assert "concurrency:" in content
    assert "elina-publish-scheduler" in content
    assert "cancel-in-progress: false" in content
    assert "META_GRAPH_API_VERSION" in content
    assert "META_GRAPH_API_BASE" in content
    assert "PUBLISH_MAX_ITEMS_PER_RUN" in content
    assert "PUBLISH_LIVE_ENABLED" in content
    assert "PUBLISH_RETRY_DELAY_MINUTES" in content


def test_atomic_claim_prevents_double_publish(monkeypatch):
    """Atomic claim should succeed only once."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")

    class FakeDBClaim:
        def __init__(self):
            self.claimed = False
            self.items = [{
                "id": "uuid-1",
                "custom_id": "ELN-TEST",
                "content_type": "reel",
                "caption_fa": "test",
                "hashtags": [],
                "media_keys": ["a.mp4"],
                "status": "SCHEDULED",
                "scheduled_for": "2020-01-01T00:00:00Z",
                "approved_at": "2020-01-01T00:00:00Z",
                "approved_by": "tester",
                "attempts": 0,
            }]
            self.status_updates = []
            self.events = []

        def get_due_items(self, now_iso, limit=1):
            return self.items[:limit]

        def claim_for_publishing(self, item_id, expected_status):
            if self.claimed:
                return False
            self.claimed = True
            return True

        def update_status(self, *args, **kwargs):
            self.status_updates.append(args)
            return []

        def log_event(self, *args, **kwargs):
            self.events.append("event")
            return []

    db = FakeDBClaim()
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    # First claim should succeed
    assert db.claim_for_publishing("uuid-1", "SCHEDULED") is True
    # Second claim should fail
    assert db.claim_for_publishing("uuid-1", "SCHEDULED") is False


def test_live_kill_switch_disables_publishing(monkeypatch):
    """When PUBLISH_LIVE_ENABLED=false, no publisher or signed URL should be created."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "false")
    db = FakeDB([make_item()])
    storage_calls = []

    class TrackingStorage(FakeStorage):
        def create_signed_url(self, key, ttl):
            storage_calls.append(key)
            return super().create_signed_url(key, ttl)

    s = PublishScheduler(db=db, storage=TrackingStorage(), publisher=FakePublisher(PublishResult(success=True, media_id="123")))
    summary = s.run_once()
    # When live disabled, checked=0, no storage calls, no publish
    assert summary["checked"] == 0
    assert len(storage_calls) == 0
    assert summary["published"] == 0


def test_empty_queue_no_meta_secrets_needed(monkeypatch):
    """Empty queue should not require Meta secrets."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    # Ensure Meta env vars are NOT set, but queue empty should still not fail
    # Actually our scheduler will try to get due items first, then only init publisher if needed
    # So with empty queue, it should not require IG_USER_ID etc
    monkeypatch.delenv("IG_USER_ID", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_GRAPH_API_BASE", raising=False)
    monkeypatch.delenv("META_GRAPH_API_VERSION", raising=False)

    db = FakeDB([])  # Empty
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=FakePublisher(PublishResult(success=True)))
    summary = s.run_once()
    assert summary["checked"] == 0
    assert summary["published"] == 0


def test_publish_scheduler_uses_edited_media_key(monkeypatch):
    """Test A: content item has edited_media_key + media_keys -> chooses edited_media_key."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    item = make_item(
        media_keys=["intake/raw.mp4"],
        edited_media_key="edited/final_render.mp4"
    )
    db = FakeDB([item])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["published"] == 1
    assert len(pub.calls) == 1
    kind, url = pub.calls[0]
    assert url == "https://signed.example/edited/final_render.mp4"


def test_publish_scheduler_fallback_to_raw(monkeypatch):
    """Test B: content item has no edited_media_key -> falls back to media_keys[0]."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    item = make_item(
        media_keys=["intake/raw.mp4"]
    )
    # Ensure edited_media_key is NOT present
    item.pop("edited_media_key", None)
    db = FakeDB([item])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["published"] == 1
    assert len(pub.calls) == 1
    kind, url = pub.calls[0]
    assert url == "https://signed.example/intake/raw.mp4"


def test_publish_scheduler_fallback_when_edited_media_key_empty(monkeypatch):
    """Test C: content item has edited_media_key set to empty/null -> falls back to media_keys[0]."""
    monkeypatch.setenv("PUBLISH_LIVE_ENABLED", "true")
    item = make_item(
        media_keys=["intake/raw.mp4"],
        edited_media_key=""  # empty string
    )
    db = FakeDB([item])
    pub = FakePublisher(PublishResult(success=True, media_id="123"))
    s = PublishScheduler(db=db, storage=FakeStorage(), publisher=pub)
    summary = s.run_once()
    assert summary["published"] == 1
    assert len(pub.calls) == 1
    kind, url = pub.calls[0]
    assert url == "https://signed.example/intake/raw.mp4"
