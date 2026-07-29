import pytest
from agents.studio.approval import ApprovalManager

pytestmark = pytest.mark.unit


class FakeDB:
    def __init__(self):
        self.items = {"ELN-TEST-001": {"id": "uuid-001", "status": "RAW_RECEIVED", "custom_id": "ELN-TEST-001"}}

    @property
    def client(self):
        class Q:
            def table(self, *args, **kwargs):
                return self

            def select(self, *args, **kwargs):
                return self

            def in_(self, *args, **kwargs):
                return self

            def order(self, *args, **kwargs):
                return self

            def limit(self, *args, **kwargs):
                return self

            def execute(self):
                class R:
                    data = []
                return R()

        return Q()

    def get_content_by_custom_id(self, cid):
        return self.items.get(cid)

    def update_status(self, item_id, new_status, extra=None):
        for v in self.items.values():
            if v["id"] == item_id:
                v["status"] = new_status
                if extra:
                    v.update(extra)
        return []

    def log_event(self, *args, **kwargs):
        return []


def make(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr("agents.studio.approval.ElinaDB", lambda: db)
    mgr = ApprovalManager()
    mgr.db = db
    return mgr, db


def test_promote(monkeypatch):
    mgr, _ = make(monkeypatch)
    r = mgr.promote_to_review("ELN-TEST-001", "t")
    assert r["ok"] and r["new_status"] == "READY_FOR_REVIEW"


def test_reject(monkeypatch):
    mgr, _ = make(monkeypatch)
    r = mgr.reject_item("ELN-TEST-001", "bad", "t")
    assert r["ok"] and r["new_status"] == "REJECTED"


def test_approve_valid_slot(monkeypatch):
    mgr, _ = make(monkeypatch)
    r = mgr.approve_and_schedule("ELN-TEST-001", "prime_evening", "t")
    assert r["ok"] and r["new_status"] == "APPROVED" and "scheduled_for" in r


def test_approve_invalid_slot(monkeypatch):
    mgr, _ = make(monkeypatch)
    r = mgr.approve_and_schedule("ELN-TEST-001", "bad_slot", "t")
    assert not r["ok"]


def test_not_found(monkeypatch):
    mgr, _ = make(monkeypatch)
    r = mgr.promote_to_review("ELN-NONE", "t")
    assert not r["ok"]


def test_needs_edit(monkeypatch):
    mgr, _ = make(monkeypatch)
    r = mgr.mark_needs_edit("ELN-TEST-001", "add hook", "t")
    assert r["ok"] and r["new_status"] == "NEEDS_EDIT"
