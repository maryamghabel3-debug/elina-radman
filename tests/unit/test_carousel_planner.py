import json
import os

import pytest

from agents.carousel import (
    CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE,
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


# === M18C-UPDATE: three operational modes + character assets ===

class FakeCharacterProvider:
    """CharacterAssetProvider stand-in: returns canned assets in order."""

    def __init__(self, assets):
        self.assets = list(assets)
        self.calls = []

    def get_asset(self, character_hint, scene_hint, slide_type, template):
        self.calls.append({
            "hint": character_hint,
            "scene": scene_hint,
            "type": slide_type,
            "template": template,
        })
        if not self.assets:
            return None
        return self.assets.pop(0)


def make_image_files(tmp_path, n):
    paths = []
    for i in range(n):
        p = tmp_path / f"img_{i}.jpg"
        p.write_bytes(b"JPEGDATA" + str(i).encode())
        paths.append(str(p))
    return paths


def text_overlay_texts(n, with_body=True):
    texts = [{"title": "عنوان اسلاید یک", "eyebrow": "هویت"}]
    for i in range(1, n):
        t = {"title": f"عنوان اسلاید {i + 1}"}
        if with_body:
            t["body"] = f"بدنه‌ی اسلاید {i + 1}"
        texts.append(t)
    return texts


# --- text_overlay (no LLM) ---

def test_mode_text_overlay_builds_deck_without_llm(tmp_path):
    images = make_image_files(tmp_path, 3)
    texts = text_overlay_texts(3)
    router = FakeRouter([])  # must never be called
    result = make_planner(router).plan(
        mode="text_overlay", image_paths=images, slide_texts=texts
    )
    # No LLM call at all
    assert router.calls == []
    assert result.provider_used is None
    # First image -> cover, zipped in exact order
    assert result.deck.slides[0].slide_type == "cover"
    assert result.deck.slides[0].image_path == images[0]
    assert [s.image_path for s in result.deck.slides] == images
    # Non-cover with body -> image_text with the photo-preserving
    # "auto" layout (M22A)
    assert result.deck.slides[1].slide_type == "image_text"
    assert result.deck.slides[1].image_layout == "auto"
    # Deck validates end-to-end
    parse_carousel_deck({
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


def test_mode_text_overlay_no_body_uses_image_text_auto(tmp_path):
    """A title-only slide still uses image_text + auto (the M18A title_body
    type requires a body and would drop the user's image)."""
    images = make_image_files(tmp_path, 3)
    texts = text_overlay_texts(3, with_body=False)
    result = make_planner(FakeRouter([])).plan(
        mode="text_overlay", image_paths=images, slide_texts=texts
    )
    assert result.deck.slides[1].slide_type == "image_text"
    assert result.deck.slides[1].image_layout == "auto"
    assert result.deck.slides[1].body == ""
    assert [s.image_path for s in result.deck.slides] == images


def test_mode_text_overlay_all_content_slides_are_image_text_auto(tmp_path):
    """M22A: slides 2..N map to image_text with image_layout='auto'
    (photo-preserving), each keeping its paired image."""
    images = make_image_files(tmp_path, 4)
    texts = text_overlay_texts(4)
    result = make_planner(FakeRouter([])).plan(
        mode="text_overlay", image_paths=images, slide_texts=texts
    )
    assert result.deck.slides[0].slide_type == "cover"
    for slide in result.deck.slides[1:]:
        assert slide.slide_type == "image_text"
        assert slide.image_layout == "auto"
        assert slide.image_path
    assert [s.image_path for s in result.deck.slides] == images


def test_mode_text_overlay_mismatched_lengths_raises(tmp_path):
    images = make_image_files(tmp_path, 3)
    texts = text_overlay_texts(2)  # 2 texts for 3 images
    with pytest.raises(CarouselPlanConfigError) as exc_info:
        make_planner(FakeRouter([])).plan(
            mode="text_overlay", image_paths=images, slide_texts=texts
        )
    assert exc_info.value.code == CAROUSEL_PLAN_CONFIG_INVALID


def test_mode_text_overlay_requires_both_inputs(tmp_path):
    images = make_image_files(tmp_path, 2)
    texts = text_overlay_texts(2)
    # missing image_paths
    with pytest.raises(CarouselPlanConfigError):
        make_planner(FakeRouter([])).plan(mode="text_overlay", slide_texts=texts)
    # missing slide_texts
    with pytest.raises(CarouselPlanConfigError):
        make_planner(FakeRouter([])).plan(mode="text_overlay", image_paths=images)
    # empty image_paths
    with pytest.raises(CarouselPlanConfigError):
        make_planner(FakeRouter([])).plan(
            mode="text_overlay", image_paths=[], slide_texts=[]
        )


def test_mode_invalid_raises_config_invalid():
    with pytest.raises(CarouselPlanConfigError) as exc_info:
        make_planner(FakeRouter([valid_deck_json(3)])).plan("موضوع", mode="dance")
    assert exc_info.value.code == CAROUSEL_PLAN_CONFIG_INVALID


# --- image_deck (LLM fills text, images zipped in order) ---

def test_mode_image_deck_forces_slide_count_to_match_images(tmp_path):
    images = make_image_files(tmp_path, 4)
    router = FakeRouter([valid_deck_json(4)])
    result = make_planner(router).plan(
        mode="image_deck", topic="موضوع", image_paths=images
    )
    # LLM told to write exactly 4 slides
    assert "تعداد دقیق اسلایدها: 4" in router.calls[0]["prompt"]
    assert len(result.deck.slides) == 4
    # Images zipped onto the generated slides, in order
    assert [s.image_path for s in result.deck.slides] == images
    # Deck still validated
    parse_carousel_deck({
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


def test_mode_image_deck_image_text_becomes_image_overlay(tmp_path):
    """M22: image-bearing text slides use the full-bleed image_overlay
    layout; legacy image_text model output is still accepted and converted."""
    images = make_image_files(tmp_path, 4)
    deck = {
        "deck_title": "دک تصاویر",
        "slides": [
            {"slide_type": "cover", "title": "کاور"},
            {"slide_type": "image_text", "title": "متن روی تصویر",
             "body": "بدنه‌ی روی تصویر", "image_path": "pending"},
            {"slide_type": "quote", "title": "نقل قول"},
            {"slide_type": "cta", "title": "ذخیره کن"},
        ],
        "caption": "کپشن تست",
        "hashtags": ["#تست"],
    }
    router = FakeRouter([json.dumps(deck, ensure_ascii=False)])
    result = make_planner(router).plan(
        mode="image_deck", topic="موضوع", image_paths=images
    )
    # The prompt now asks for the full-bleed type
    assert "image_overlay" in router.calls[0]["prompt"]
    # Image-bearing text slide converted and zipped with its image
    assert result.deck.slides[1].slide_type == "image_overlay"
    assert result.deck.slides[1].image_path == images[1]
    # Other slide types untouched
    assert result.deck.slides[0].slide_type == "cover"
    assert result.deck.slides[2].slide_type == "quote"
    assert result.deck.slides[3].slide_type == "cta"


def test_mode_image_deck_explicit_image_layout_is_preserved(tmp_path):
    """M22A: when the model explicitly sets image_layout on an image_text
    slide, image_deck keeps the slide as image_text with that layout
    (no silent conversion to image_overlay)."""
    images = make_image_files(tmp_path, 4)
    deck = {
        "deck_title": "دک تصاویر",
        "slides": [
            {"slide_type": "cover", "title": "کاور"},
            {"slide_type": "image_text", "title": "متن روی تصویر",
             "body": "بدنه‌ی روی تصویر", "image_path": "pending",
             "image_layout": "contain_caption"},
            {"slide_type": "quote", "title": "نقل قول"},
            {"slide_type": "cta", "title": "ذخیره کن"},
        ],
        "caption": "کپشن تست",
        "hashtags": ["#تست"],
    }
    router = FakeRouter([json.dumps(deck, ensure_ascii=False)])
    result = make_planner(router).plan(
        mode="image_deck", topic="موضوع", image_paths=images
    )
    assert result.deck.slides[1].slide_type == "image_text"
    assert result.deck.slides[1].image_layout == "contain_caption"
    assert result.deck.slides[1].image_path == images[1]


def test_mode_image_deck_requires_topic_and_images(tmp_path):
    images = make_image_files(tmp_path, 3)
    with pytest.raises(CarouselPlanConfigError):
        make_planner(FakeRouter([])).plan(mode="image_deck", topic="   ", image_paths=images)
    with pytest.raises(CarouselPlanConfigError):
        make_planner(FakeRouter([])).plan(mode="image_deck", topic="موضوع")


# --- ai_planned with character presence ---

def test_mode_ai_planned_character_provider_assigns_images(tmp_path):
    router = FakeRouter([valid_deck_json(3)])  # cover, quote, cta
    provider = FakeCharacterProvider(["/assets/elina_hero.png"])
    result = make_planner(router).plan(
        "موضوع", slide_count=3, character_asset_provider=provider
    )
    # Every content slide (cover, quote) got a character visual; cta did not
    assert result.deck.slides[0].image_path == "/assets/elina_hero.png"
    # quote reuses the last successful image (only one asset available)
    assert result.deck.slides[1].image_path == "/assets/elina_hero.png"
    assert result.deck.slides[2].image_path is None  # cta
    # Provider was queried with the elina hint
    assert all(c["hint"] == "elina" for c in provider.calls)
    # cta was never queried
    assert all(c["type"] != "cta" for c in provider.calls)


def test_mode_ai_planned_distinct_assets_per_slide():
    router = FakeRouter([valid_deck_json(3)])  # cover, quote, cta
    provider = FakeCharacterProvider(["/assets/elina_a.png", "/assets/elina_b.png"])
    result = make_planner(router).plan(
        "موضوع", slide_count=3, character_asset_provider=provider
    )
    assert result.deck.slides[0].image_path == "/assets/elina_a.png"
    assert result.deck.slides[1].image_path == "/assets/elina_b.png"
    assert result.deck.slides[2].image_path is None


def test_mode_ai_planned_falls_back_to_previous_image():
    router = FakeRouter([valid_deck_json(3)])  # cover, quote, cta
    # First slide gets a real asset; the next returns None -> reuse previous
    provider = FakeCharacterProvider(["/assets/elina_hero.png"])
    result = make_planner(router).plan(
        "موضوع", slide_count=3, character_asset_provider=provider
    )
    assert result.deck.slides[0].image_path == "/assets/elina_hero.png"
    assert result.deck.slides[1].image_path == "/assets/elina_hero.png"  # fallback


def test_mode_ai_planned_all_assets_missing_raises():
    from agents.carousel import CarouselCharacterAssetsError
    router = FakeRouter([valid_deck_json(3)])
    provider = FakeCharacterProvider([])  # nothing available
    with pytest.raises(CarouselCharacterAssetsError) as exc_info:
        make_planner(router).plan(
            "موضوع", slide_count=3, character_asset_provider=provider
        )
    assert exc_info.value.code == CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE


def test_mode_ai_planned_no_provider_keeps_legacy_behavior():
    """Without a provider, ai_planned does not enforce character presence."""
    router = FakeRouter([valid_deck_json(3)])
    result = make_planner(router).plan("موضوع", slide_count=3)
    # No image_path was provided -> slides have no image (legacy behavior)
    assert result.deck.slides[0].image_path is None


# --- LocalCharacterAssetProvider ---

def test_local_character_asset_provider(tmp_path):
    from agents.carousel import LocalCharacterAssetProvider
    (tmp_path / "elina_hero.png").write_bytes(b"PNG")
    (tmp_path / "elina_smiling.png").write_bytes(b"PNG")
    (tmp_path / "elli_default.png").write_bytes(b"PNG")
    (tmp_path / "world_market.png").write_bytes(b"PNG")
    (tmp_path / "notes.txt").write_bytes(b"not-an-image")

    provider = LocalCharacterAssetProvider(directory=str(tmp_path))
    # elina hero (default asset)
    hit = provider.get_asset("elina", "", "cover", "psychological_dark")
    assert hit and hit.endswith("elina_hero.png")
    # elina with scene hint matching a filename
    hit = provider.get_asset("elli", "default", "cover", "psychological_dark")
    assert hit and hit.endswith("elli_default.png")
    # world hint resolves a world_ file
    hit = provider.get_asset("world", "", "cover", "psychological_dark")
    assert hit and hit.endswith("world_market.png")
    # never raises for a missing asset -> None
    assert provider.get_asset("nobody", "", "cover", "x") is None


def test_local_character_asset_provider_missing_dir_never_raises():
    from agents.carousel import LocalCharacterAssetProvider
    provider = LocalCharacterAssetProvider(directory="/nonexistent/dir/xyz")
    assert provider.get_asset("elina", "", "cover", "x") is None


# --- M27B: text_overlay default text_scale 0.85 ---

def test_mode_text_overlay_default_text_scale_085(tmp_path):
    images = make_image_files(tmp_path, 3)
    texts = text_overlay_texts(3)
    result = make_planner(FakeRouter([])).plan(
        mode="text_overlay", image_paths=images, slide_texts=texts
    )
    # All slides (cover included) default to the smaller text scale
    assert all(s.text_scale == 0.85 for s in result.deck.slides)
    # Other M25 defaults untouched
    assert result.deck.slides[0].text_zone == "auto"
    assert result.deck.slides[1].text_zone == "auto"
    assert result.deck.slides[1].image_layout == "auto"


def test_mode_image_deck_keeps_default_text_scale(tmp_path):
    """image_deck (and ai_planned) must keep text_scale=None (M27B only
    changes text_overlay)."""
    images = make_image_files(tmp_path, 3)
    result = make_planner(FakeRouter([valid_deck_json(3)])).plan(
        mode="image_deck", topic="موضوع", image_paths=images
    )
    assert all(s.text_scale is None for s in result.deck.slides)
