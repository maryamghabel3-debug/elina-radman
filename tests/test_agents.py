"""Basic smoke/unit tests for ElinaOS agents.

Run with:  pytest -q
These tests are offline-safe: they never require API keys or network access
(network-dependent methods are exercised only for graceful-failure behaviour).
"""

import os
import sys
import json
import glob
import shutil
import tempfile

import pytest

# Make the repo root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Run each test in an isolated temp cwd so we never touch real content/."""
    monkeypatch.chdir(tmp_path)
    os.makedirs("content/queue", exist_ok=True)
    yield tmp_path


# --------------------------------------------------------------------------- #
# ContentCreator
# --------------------------------------------------------------------------- #
def test_content_creator_produces_valid_pieces(workdir, monkeypatch):
    # Ensure no LLM key so we exercise the offline fallback path
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    from agents.content_creator import ContentCreator

    cc = ContentCreator()
    pieces = cc.run(count=3)

    assert len(pieces) == 3
    required = {"id", "pillar", "caption", "hashtags", "platforms", "status"}
    for p in pieces:
        assert required.issubset(p.keys())
        assert p["status"] == "pending_approval"
        assert p["caption"].strip()
        # Must NOT emit the old placeholder text
        assert not p["caption"].startswith("[AI Generated")

    # A queue file should have been written
    assert glob.glob("content/queue/*.json")


def test_content_creator_caption_fallback_is_real(workdir, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from agents.content_creator import ContentCreator

    cc = ContentCreator()
    cap = cc.generate_dynamic_caption("ootd", [])
    assert isinstance(cap, str) and len(cap) > 10
    assert "[AI Generated" not in cap


# --------------------------------------------------------------------------- #
# Publisher
# --------------------------------------------------------------------------- #
def test_publisher_no_token_returns_error(workdir, monkeypatch):
    monkeypatch.delenv("POSTIZ_API_TOKEN", raising=False)
    from agents.publisher import Publisher

    result = Publisher().run()
    assert result.get("error") == "no_token"


def test_publisher_keeps_approved_on_network_failure(workdir, monkeypatch):
    monkeypatch.setenv("POSTIZ_API_TOKEN", "fake")
    # Point at a port with nothing listening -> connection error
    monkeypatch.setenv("POSTIZ_URL", "http://127.0.0.1:59999/api")

    piece = {
        "id": "t-1",
        "caption": "hi",
        "hashtags": "#x",
        "platforms": ["instagram"],
        "status": "approved",
    }
    fp = "content/queue/test.json"
    with open(fp, "w") as f:
        json.dump([piece], f)

    from agents.publisher import Publisher

    result = Publisher().run()
    assert result["published"] == []

    # Status must remain 'approved' (no silent content loss)
    with open(fp) as f:
        data = json.load(f)
    assert data[0]["status"] == "approved"


# --------------------------------------------------------------------------- #
# TrendHunter
# --------------------------------------------------------------------------- #
def test_trend_hunter_run_always_returns_list(workdir):
    from agents.trend_hunter import TrendHunter

    th = TrendHunter()
    trends = th.run()
    assert isinstance(trends, list)
    assert len(trends) >= 1  # evergreen formats guarantee non-empty
    # Every trend has the minimum shape
    for t in trends:
        assert "name" in t and "platform" in t


def test_trend_hunter_top_images_shape(workdir):
    from agents.trend_hunter import TrendHunter

    th = TrendHunter()
    th.trends = [
        {"name": "a", "platform": "reddit", "image": "http://x/1.jpg", "popularity_rank": 2},
        {"name": "b", "platform": "reddit", "image": None, "popularity_rank": 1},
        {"name": "c", "platform": "reddit", "image": "http://x/3.jpg", "popularity_rank": 1},
    ]
    tops = th.top_images(limit=5)
    # Only items WITH images, sorted by popularity_rank ascending
    assert [t["name"] for t in tops] == ["c", "a"]


def test_trend_hunter_upscale_enlarges_thumbnail():
    from agents.trend_hunter import TrendHunter

    small = "https://preview.redd.it/x.jpg?width=140&height=140&crop=1:1,smart&auto=webp"
    big = TrendHunter._upscale(small)
    assert "width=640" in big and "width=140" not in big


# --------------------------------------------------------------------------- #
# Base Agent
# --------------------------------------------------------------------------- #
def test_base_agent_status_and_logging():
    from agents.base import Agent

    a = Agent("Tester", "unit test agent")
    a.log("hello")
    a.log("boom", "error")
    status = a.status()
    assert status["name"] == "Tester"
    assert status["errors"] == 1
