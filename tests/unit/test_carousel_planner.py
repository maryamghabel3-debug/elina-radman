import json
import os

import pytest

from agents.carousel import (
    CAROUSEL_PLAN_CONFIG_INVALID,
    CAROUSEL_PLAN_GENERATION_FAILED,
    CarouselPlanConfigError,
    CarouselPlanGenerationError,
    CarouselPlanner,
    parse_carousel_deck,
)

pytestmark = pytest.mark.unit

POTENTIAL_TEST_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "arial.ttf",
]


def find_test_font():
    for path in POTENTIAL_TEST_FONTS:
        if os.path.exists(path):
            return path
    return None


TEST_FONT_PATH = find_test_font()


class FakeRouter:
    """LLMRouter stand-in: returns canned responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def smart_generate(self, prompt, task_type="general", system_prompt="", language=""):
        self.calls.append({
            "prompt": prompt,
            "task_type": task_type,
            "system_prompt": system_prompt,
            "language": language,
        })
        if not self.responses:
            return {"provider": "", "model": "", "response": "", "attempts": []}
        return {
            "provider": "groq",
            "model": "Llama 3.3 70B (Groq)",
            "response": self.responses.pop(0),
            "attempts": [],
        }


def valid_deck_json(slide_count=3, deck_title="دک آزمایش",
                    caption="پاراگراف یک.\n\nپاراگراف دو.",
                    hashtags=("#روان_شناسی", "#هویت", "#selfcare")):
    slides = [{"slide_type": "cover", "title": "کاور قوی", "eyebrow": "هویت"}]
    for i in range(slide_count - 2):
        slides.append({"slide_type": "quote", "title": f"نقل قول شماره {i + 1}"})
    slides.append({"slide_type": "cta", "title": "این اسلایدها را ذخیره کن"})
    return json.dumps({
        "deck_title": deck_title,
        "slides": slides,
        "caption": caption,
        "hashtags": list(hashtags),
    }, ensure_ascii=False)


def make_planner(router):
    return CarouselPlanner(router=router)


# === A. valid mocked LLM JSON -> CarouselPlanResult with validated deck ===

def test_A_valid_json_produces_validated_deck():
    router = FakeRouter([valid_deck_json(3)])
    result = make_planner(router).plan("موضوع تست", slide_count=3)
    assert result.deck.title == "دک آزمایش"
    assert len(result.deck.slides) == 3
    assert [s.slide_type for s in result.deck.slides] == ["cover", "quote", "cta"]
    # Deck passes the full deck validation
    assert parse_carousel_deck({
        "title": result.deck.title,
        "template": result.deck.template,
        "slides": [
            {"slide_type": s.slide_type, "title": s.title, "body": s.body,
             "bullets": s.bullets, "image_path": s.image_path, "eyebrow": s.eyebrow,
             "footer": s.footer, "template": s.template, "accent": s.accent,
             "slide_number": s.slide_number}
            for s in result.deck.slides
        ],
    })
    # Router called with creative_writing + fa
    assert router.calls[0]["task_type"] == "creative_writing"
    assert router.calls[0]["language"] == "fa"
    assert result.provider_used == "groq"


# === B. cover forced first, cta forced last (reorder) ===

def test_B_cover_first_cta_last_enforced():
    slides = [
        {"slide_type": "quote", "title": "نقل اول"},
        {"slide_type": "cover", "title": "کاور"},
        {"slide_type": "cta", "title": "ذخیره کن"},
        {"slide_type": "quote", "title": "نقل دوم"},
    ]
    payload = json.dumps({"deck_title": "t", "slides": slides,
                          "caption": "c", "hashtags": ["#x"]}, ensure_ascii=False)
    router = FakeRouter([payload])
    result = make_planner(router).plan("موضوع", slide_count=4)
    assert [s.slide_type for s in result.deck.slides] == ["cover", "quote", "quote", "cta"]

    # Two ctas -> repair loop fails -> generation error
    slides2 = [dict(s) for s in slides]
    slides2.append({"slide_type": "cta", "title": "cta دوم"})
    payload2 = json.dumps({"deck_title": "t", "slides": slides2,
                           "caption": "c", "hashtags": ["#x"]}, ensure_ascii=False)
    router2 = FakeRouter([payload2, payload2])
    with pytest.raises(CarouselPlanGenerationError):
        make_planner(router2).plan("موضوع", slide_count=5)


# === C. markdown-fenced JSON is cleaned and parsed ===

def test_C_markdown_fenced_json_cleaned():
    fenced = "```json\n" + valid_deck_json(3) + "\n```"
    router = FakeRouter([fenced])
    result = make_planner(router).plan("موضوع", slide_count=3)
    assert len(result.deck.slides) == 3


# === D. broken first + valid second -> repair loop succeeds ===

def test_D_repair_loop_recovers():
    router = FakeRouter(["{این json شکسته است", valid_deck_json(3)])
    result = make_planner(router).plan("موضوع", slide_count=3)
    assert len(result.deck.slides) == 3
    assert len(router.calls) == 2
    # Second prompt quotes the error and asks for corrected JSON only
    assert "خطا" in router.calls[1]["prompt"]
    assert "JSON" in router.calls[1]["prompt"]


# === E. broken twice -> CAROUSEL_PLAN_GENERATION_FAILED ===

def test_E_broken_twice_raises_generation_failed():
    router = FakeRouter(["not json at all", "still not json"])
    with pytest.raises(CarouselPlanGenerationError) as exc_info:
        make_planner(router).plan("موضوع")
    assert exc_info.value.code == CAROUSEL_PLAN_GENERATION_FAILED
    assert len(router.calls) == 2


# === F. empty topic -> CAROUSEL_PLAN_CONFIG_INVALID ===

def test_F_empty_topic_config_invalid():
    router = FakeRouter([valid_deck_json(3)])
    with pytest.raises(CarouselPlanConfigError) as exc_info:
        make_planner(router).plan("   ")
    assert exc_info.value.code == CAROUSEL_PLAN_CONFIG_INVALID
    assert router.calls == []  # no LLM call for bad config

    with pytest.raises(CarouselPlanConfigError):
        make_planner(FakeRouter([])).plan("م" * 301)  # topic too long
    with pytest.raises(CarouselPlanConfigError):
        make_planner(FakeRouter([])).plan("موضوع", goal="dance")  # bad goal
    with pytest.raises(CarouselPlanConfigError):
        make_planner(FakeRouter([])).plan("موضوع", language="en")  # Persian-only


# === G. slide_count out of range -> config invalid ===

def test_G_slide_count_range():
    for bad in (2, 11, 0, "six", True):
        with pytest.raises(CarouselPlanConfigError):
            make_planner(FakeRouter([])).plan("موضوع", slide_count=bad)


# === H. unsupported template -> config invalid ===

def test_H_unsupported_template():
    with pytest.raises(CarouselPlanConfigError) as exc_info:
        make_planner(FakeRouter([])).plan("موضوع", template="neon_pink")
    assert exc_info.value.code == CAROUSEL_PLAN_CONFIG_INVALID


# === I. image_path present -> cover receives image_path ===

def test_I_image_injected_into_cover(tmp_path):
    img = tmp_path / "source.jpg"
    img.write_bytes(b"JPEGDATA")
    router = FakeRouter([valid_deck_json(3)])
    result = make_planner(router).plan("موضوع", slide_count=3, image_path=str(img))
    assert result.deck.slides[0].image_path == str(img)
    # No GEMINI_API_KEY in tests -> description None, but the model was told
    # a cover image exists (general visual context)
    assert result.image_description is None
    assert "تصویر منبع برای اسلاید کاور موجود است" in router.calls[0]["prompt"]


# === J. vision description soft-fallback ===

def test_J_vision_failure_soft_fallback(tmp_path, monkeypatch):
    """Any vision failure (no key, provider down) degrades to None and the
    plan proceeds without image context."""
    import sys
    import types

    img = tmp_path / "source.jpg"
    img.write_bytes(b"JPEGDATA")
    planner = make_planner(FakeRouter([valid_deck_json(3)]))

    # Case 1: no GEMINI_API_KEY -> soft None, no network
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert planner._describe_image(str(img)) is None

    # Case 2: key set but the provider explodes -> still soft None
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    fake_genai = types.ModuleType("google.genai")

    class _Models:
        def generate_content(self, model=None, contents=None):
            raise RuntimeError("vision provider down")

    class FakeClient:
        def __init__(self, api_key):
            self.models = _Models()

    fake_genai.Client = FakeClient
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    assert planner._describe_image(str(img)) is None

    # The plan itself succeeds end-to-end without image context
    result = planner.plan("موضوع", slide_count=3, image_path=str(img))
    assert result.image_description is None
    assert result.deck.slides[0].image_path == str(img)


def test_J2_image_description_used_directly():
    router = FakeRouter([valid_deck_json(3)])
    result = make_planner(router).plan(
        "موضوع", slide_count=3, image_description="تصویر تیره با آینه و نور کم"
    )
    assert result.image_description == "تصویر تیره با آینه و نور کم"
    assert "تصویر تیره با آینه و نور کم" in router.calls[0]["prompt"]


# === K. deck passes deck_renderer validation end-to-end ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_K_deck_renders_end_to_end(tmp_path):
    from agents.editing.typography_engine import TypographyEngine
    from agents.carousel import CarouselDeckRenderer, CarouselSlideRenderer

    router = FakeRouter([valid_deck_json(3)])
    result = make_planner(router).plan("موضوع", slide_count=3)
    engine = TypographyEngine(font_path=TEST_FONT_PATH, render_mode="fallback")
    renderer = CarouselDeckRenderer(slide_renderer=CarouselSlideRenderer(engine=engine))
    paths = renderer.render_deck(result.deck, str(tmp_path / "deck"))
    assert len(paths) == 3
    assert all(os.path.exists(p) for p in paths)


# === L. caption and hashtags extracted correctly ===

def test_L_caption_and_hashtags_extracted():
    caption = "پاراگراف اول.\n\nپاراگراف دوم با دعوت آرام."
    tags = ["#روان_شناسی", "#هویت", "#selfcare", "#psychology"]
    router = FakeRouter([valid_deck_json(3, caption=caption, hashtags=tags)])
    result = make_planner(router).plan("موضوع", slide_count=3)
    assert result.caption == caption
    assert result.hashtags == tags

    # Non-string hashtags are filtered out
    raw = json.loads(valid_deck_json(3))
    raw["hashtags"] = ["#ok", 42, "", "  ", "#two"]
    router2 = FakeRouter([json.dumps(raw, ensure_ascii=False)])
    result2 = make_planner(router2).plan("موضوع", slide_count=3)
    assert result2.hashtags == ["#ok", "#two"]
