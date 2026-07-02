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
    # use_trends=False keeps the test offline/deterministic (no network)
    pieces = cc.run(count=3, use_trends=False)

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
# ZernioPublisher
# --------------------------------------------------------------------------- #
def test_zernio_publisher_no_token(workdir, monkeypatch):
    monkeypatch.delenv("ZERNIO_API_KEY", raising=False)
    from agents.publisher_zernio import ZernioPublisher

    result = ZernioPublisher().run()
    assert result.get("error") == "no_token"


def test_zernio_platform_resolution(workdir, monkeypatch):
    monkeypatch.setenv("ZERNIO_API_KEY", "sk_fake")
    from agents.publisher_zernio import ZernioPublisher

    pub = ZernioPublisher()
    account_map = {"instagram": "acc_ig", "tiktok": "acc_tt"}
    # 'lemon8' is unsupported and should be dropped; 'x' maps to twitter (absent)
    resolved = pub._resolve_platforms(["instagram", "lemon8", "tiktok"], account_map)
    assert {"platform": "instagram", "accountId": "acc_ig"} in resolved
    assert {"platform": "tiktok", "accountId": "acc_tt"} in resolved
    assert all(p["platform"] != "lemon8" for p in resolved)


def test_zernio_publish_success(workdir, monkeypatch):
    monkeypatch.setenv("ZERNIO_API_KEY", "sk_fake")
    from agents import publisher_zernio

    piece = {
        "id": "z-1",
        "caption": "hi",
        "hashtags": "#x",
        "platforms": ["instagram"],
        "status": "approved",
    }
    fp = "content/queue/z.json"
    with open(fp, "w") as f:
        json.dump([piece], f)

    pub = publisher_zernio.ZernioPublisher()
    # Stub network: account listing + successful post
    monkeypatch.setattr(pub, "list_accounts", lambda: [{"_id": "acc_ig", "platform": "instagram"}])

    class _Resp:
        status_code = 201
        text = "ok"

    monkeypatch.setattr(pub.session, "post", lambda *a, **k: _Resp())

    result = pub.run()
    assert len(result["published"]) == 1
    with open(fp) as f:
        data = json.load(f)
    assert data[0]["status"] == "published"
    assert data[0]["published_via"] == "zernio"


def test_zernio_no_accounts(workdir, monkeypatch):
    monkeypatch.setenv("ZERNIO_API_KEY", "sk_fake")
    from agents.publisher_zernio import ZernioPublisher

    pub = ZernioPublisher()
    monkeypatch.setattr(pub, "list_accounts", lambda: [])
    result = pub.run()
    assert result.get("error") == "no_accounts"


# --------------------------------------------------------------------------- #
# TrendHunter
# --------------------------------------------------------------------------- #
def test_trend_hunter_run_always_returns_list(workdir):
    from agents.trend_hunter import TrendHunter

    th = TrendHunter()
    # Seed a fresh cache so run() returns instantly without any network calls
    th._save_cache([{"name": "seeded", "platform": "reddit", "popularity_rank": 1}])
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
# TrendHunter caching & summary
# --------------------------------------------------------------------------- #
def test_trend_hunter_cache_roundtrip(workdir):
    from agents.trend_hunter import TrendHunter

    th = TrendHunter()
    sample = [{"name": "x", "platform": "reddit", "popularity_rank": 1}]
    th._save_cache(sample)
    loaded = th._load_cache()
    assert loaded == sample


def test_trend_summary_prefers_real(workdir):
    from agents.trend_hunter import TrendHunter

    th = TrendHunter()
    th.trends = [
        {"name": "Real trend A", "platform": "reddit", "popularity_rank": 2},
        {"name": "Curated B", "platform": "ig", "curated": True},
        {"name": "Real trend C", "platform": "reddit", "popularity_rank": 1},
        {"name": "Mock D", "platform": "reddit", "mock": True},
    ]
    summary = th.trend_summary(limit=5)
    assert summary == ["Real trend C", "Real trend A"]


# --------------------------------------------------------------------------- #
# TrendVisualAnalyzer (offline: colour math only, no network)
# --------------------------------------------------------------------------- #
def test_visual_analyzer_palette_math():
    from agents.trend_visual_analyzer import TrendVisualAnalyzer, _HAS_DEPS

    if not _HAS_DEPS:
        import pytest as _pt
        _pt.skip("Pillow/numpy not installed")

    from PIL import Image

    tva = TrendVisualAnalyzer()
    # A solid beige image should yield a cream/neutral dominant tone
    img = Image.new("RGB", (64, 64), (245, 240, 232))
    palette = tva._dominant_colors(img, k=2)
    assert palette and palette[0]["name"] in ("cream/neutral", "neutral")
    assert palette[0]["hex"].startswith("#")


def test_visual_analyzer_hue_names():
    from agents.trend_visual_analyzer import TrendVisualAnalyzer

    assert "neutral" in TrendVisualAnalyzer._hue_name((250, 248, 245))
    assert TrendVisualAnalyzer._hue_name((20, 20, 20)) == "charcoal/neutral"


# --------------------------------------------------------------------------- #
# PerformanceAnalyzer
# --------------------------------------------------------------------------- #
def test_performance_analyzer_simulated(workdir, monkeypatch):
    for k in ("YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_ID", "IG_ACCESS_TOKEN", "IG_USER_ID"):
        monkeypatch.delenv(k, raising=False)
    from agents.performance_analyzer import PerformanceAnalyzer

    pa = PerformanceAnalyzer()
    strategy = pa.run()
    assert isinstance(strategy, list) and strategy
    # Report file should be written
    assert os.path.exists("content/performance_metrics.json")


# --------------------------------------------------------------------------- #
# PromptEngineer trending palette injection
# --------------------------------------------------------------------------- #
def test_prompt_engineer_uses_palette(workdir):
    import json as _json

    os.makedirs("content", exist_ok=True)
    with open("content/trend_visuals.json", "w") as f:
        _json.dump(
            {"dominant_tones": ["cream/neutral", "camel"], "top_colors": ["#f5f0e8"]},
            f,
        )

    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    prompt = pe.generate_photo_prompt("in a cafe")
    assert "trending tones" in prompt
    assert "cream/neutral" in prompt

    # And it should be omittable
    plain = pe.generate_photo_prompt("in a cafe", use_trending_palette=False)
    assert "trending tones" not in plain


def test_prompt_engineer_uses_deep_signals(workdir):
    import json as _json

    os.makedirs("content", exist_ok=True)
    with open("content/trend_visuals.json", "w") as f:
        _json.dump(
            {
                "dominant_tones": ["cream/neutral"],
                "top_colors": ["#f5f0e8"],
                "trending_aesthetics": ["quiet luxury", "old money"],
                "trending_standout_products": ["camel wool trench coat"],
                "trending_camera_angles": ["low angle"],
                "sample_poses": ["walking away, glancing over shoulder"],
            },
            f,
        )

    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    prompt = pe.generate_photo_prompt("street style walk")
    # Deep reverse-engineered signals should surface in the prompt
    assert "quiet luxury" in prompt
    assert "camel wool trench coat" in prompt
    assert "low angle" in prompt


# --------------------------------------------------------------------------- #
# vision helper (offline: JSON extraction + no-key guard)
# --------------------------------------------------------------------------- #
def test_vision_json_extraction():
    from agents import vision

    assert vision._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert vision._extract_json('noise {"b": 2, "c": [1,2]} tail') == {"b": 2, "c": [1, 2]}
    assert vision._extract_json("not json at all") is None


def test_vision_no_key_guard(monkeypatch):
    from agents import vision

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert vision.gemini_available() is False
    assert vision.analyze_image("http://x", "p")["available"] is False
    assert vision.analyze_text("p")["available"] is False


# --------------------------------------------------------------------------- #
# TrendVideoAnalyzer (offline: heuristic teardown + engagement math)
# --------------------------------------------------------------------------- #
def test_video_analyzer_heuristic_fallback(workdir, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from agents.trend_video_analyzer import TrendVideoAnalyzer

    tva = TrendVideoAnalyzer()
    meta = {"title": "t", "views": 1_000_000, "likes": 50_000, "comments": 5_000, "video_id": "x"}
    comments = [{"text": "where to buy", "likes": 100}]
    res = tva.reverse_engineer(meta, comments)
    assert res["engine"] == "heuristic"
    # engagement = (50000+5000)/1000000 * 100 = 5.5
    assert res["engagement_rate_pct"] == 5.5


def test_content_creator_video_ideas_from_blueprints(workdir):
    import json as _json

    os.makedirs("content", exist_ok=True)
    with open("content/trend_videos.json", "w") as f:
        _json.dump(
            {
                "analyses": [
                    {
                        "meta": {"title": "viral GRWM"},
                        "teardown": {
                            "why_it_went_viral": ["relatable hook"],
                            "elina_recreation": {
                                "concept": "petite GRWM",
                                "hook": "POV: you're 4'11 and...",
                                "shot_list": ["mirror shot", "close up"],
                                "caption": "getting ready with me 🤍",
                            },
                        },
                    }
                ]
            },
            f,
        )

    from agents.content_creator import ContentCreator

    cc = ContentCreator()
    pieces = cc.create_video_ideas(limit=3)
    assert len(pieces) == 1
    p = pieces[0]
    assert p["format"] == "video"
    assert p["hook"].startswith("POV")
    assert p["inspired_by"] == "viral GRWM"
    assert p["shot_list"] == ["mirror shot", "close up"]


# --------------------------------------------------------------------------- #
# Daily pipeline wiring (generate.py) with deep analysis skipped
# --------------------------------------------------------------------------- #
def test_daily_pipeline_runs_with_deep_skip(workdir, monkeypatch):
    """The full daily entrypoint should produce a queue file and never crash,
    even offline, when deep analysis is skipped."""
    import importlib

    monkeypatch.setenv("SKIP_DEEP_ANALYSIS", "1")
    monkeypatch.setenv("IMAGES_OFF", "1")  # keep the test fully offline (no image API)
    for k in ("GEMINI_API_KEY", "YOUTUBE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(k, raising=False)

    # Seed the trend cache so load_trends() stays fully offline
    from agents.trend_hunter import TrendHunter
    TrendHunter()._save_cache([{"name": "seeded", "platform": "reddit", "popularity_rank": 1}])

    import scripts.generate as gen
    importlib.reload(gen)

    # run_deep_analysis honours the skip flag and returns no video ideas
    assert gen.run_deep_analysis() == []

    gen.main()
    files = glob.glob("content/queue/*.json")
    assert files
    with open(files[0]) as f:
        data = json.load(f)
    assert len(data) == 3
    assert all(d["status"] == "pending_approval" for d in data)


def test_load_visual_signals_reads_report(workdir):
    import importlib, scripts.generate as gen
    importlib.reload(gen)

    os.makedirs("content", exist_ok=True)
    with open("content/trend_visuals.json", "w") as f:
        json.dump(
            {
                "trending_aesthetics": ["quiet luxury"],
                "trending_standout_products": ["camel trench"],
            },
            f,
        )
    sig = gen.load_visual_signals()
    assert "quiet luxury" in sig and "camel trench" in sig


# --------------------------------------------------------------------------- #
# Base Agent
# --------------------------------------------------------------------------- #
def test_image_studio_prompt_and_fallback(workdir, monkeypatch):
    """ImageStudio builds a rich prompt and falls back cleanly when providers
    fail — all offline (both providers stubbed to fail)."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from agents.image_studio import ImageStudio

    studio = ImageStudio()
    prompt = studio.build_prompt("wearing a camel blazer in a cafe")
    assert "Iranian woman" in prompt  # identity lock baked in

    # Stub both providers to fail -> graceful error, no crash
    monkeypatch.setattr(studio, "_gemini_image", lambda p, o: False)
    monkeypatch.setattr(studio, "_pollinations_image", lambda p, o: False)
    result = studio.generate("test concept")
    assert result.get("error") == "all_providers_failed"


def test_image_studio_writes_file(workdir, monkeypatch):
    """When a provider 'succeeds', the returned dict points at the written file."""
    from agents.image_studio import ImageStudio

    studio = ImageStudio()

    def fake_poll(prompt, out_path, **kw):
        with open(out_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0fakejpeg")
        return True

    monkeypatch.setattr(studio, "_gemini_image", lambda p, o: False)
    monkeypatch.setattr(studio, "_pollinations_image", fake_poll)
    result = studio.generate("test concept")
    assert result.get("provider") == "pollinations"
    assert os.path.exists(result["path"])


def test_image_studio_uses_references_and_fullbody(workdir, monkeypatch):
    """The prompt is full-body editorial and reference photos are discovered."""
    from agents.image_studio import ImageStudio

    # Create fake reference photos in images/
    os.makedirs("images", exist_ok=True)
    for i in range(2):
        with open(f"images/elina-final-0{i}.jpg", "wb") as f:
            f.write(b"x" * 5000)  # >1024 so it counts as valid

    studio = ImageStudio()
    refs = studio.reference_images()
    assert len(refs) == 2  # both discovered

    prompt = studio.build_prompt("in a cafe")
    assert "Full-body" in prompt or "three-quarter" in prompt


def test_image_studio_trend_driven_concept(workdir, monkeypatch):
    """When no concept is given, it is derived from the trend analysis file."""
    import json as _json
    os.makedirs("content", exist_ok=True)
    with open("content/trend_visuals.json", "w") as f:
        _json.dump({
            "trending_aesthetics": ["old money"],
            "trending_standout_products": ["camel wool coat"],
        }, f)

    from agents.image_studio import ImageStudio
    concept = ImageStudio().trend_concept()
    assert "old money" in concept and "camel wool coat" in concept


def test_base_agent_status_and_logging():
    from agents.base import Agent

    a = Agent("Tester", "unit test agent")
    a.log("hello")
    a.log("boom", "error")
    status = a.status()
    assert status["name"] == "Tester"
    assert status["errors"] == 1
