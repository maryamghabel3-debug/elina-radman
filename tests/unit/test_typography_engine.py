import pytest
import os
from PIL import Image
from agents.editing.typography_engine import TypographyEngine

pytestmark = pytest.mark.unit

POTENTIAL_TEST_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "arial.ttf"
]

def find_test_font():
    for path in POTENTIAL_TEST_FONTS:
        if os.path.exists(path):
            return path
    return None

TEST_FONT_PATH = find_test_font()

def test_missing_font_falls_back_to_bundled(monkeypatch):
    """A missing explicit path falls through to the repo-bundled font
    (no failure) instead of raising — the whole point of the resolver."""
    import agents.editing.font_resolver as font_resolver

    monkeypatch.delenv("ELINA_FONT_PRIMARY_PATH", raising=False)
    # A missing explicit path must not fail: it falls back to the bundled font.
    engine = TypographyEngine(font_path="/non/existent/nowhere.ttf")
    assert engine.font_path == str(font_resolver.BUNDLED_FONT_PATH)


def test_no_font_available_raises_typed_error(monkeypatch):
    """When no candidate font is loadable, a clear typed error is raised."""
    import agents.editing.font_resolver as font_resolver
    from agents.editing.font_resolver import FontNotFoundError

    monkeypatch.delenv("ELINA_FONT_PRIMARY_PATH", raising=False)
    # Make every candidate unavailable so resolution must fail.
    monkeypatch.setattr(font_resolver, "BUNDLED_FONT_PATH", "/non/existent/bundled.ttf")
    monkeypatch.setattr(font_resolver, "SYSTEM_PERSIAN_FONT_CANDIDATES", [])

    with pytest.raises(FontNotFoundError):
        TypographyEngine(font_path="/non/existent/explicit.ttf")

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_engine_creates_valid_png(tmp_path):
    engine = TypographyEngine(font_path=TEST_FONT_PATH, render_mode="fallback")
    output = str(tmp_path / "test.png")
    res = engine.render_text_to_png("سلام", output)
    assert os.path.exists(res)
    img = Image.open(res)
    assert img.mode == "RGBA"

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_engine_fails_empty_text(tmp_path):
    engine = TypographyEngine(font_path=TEST_FONT_PATH)
    with pytest.raises(ValueError):
        engine.render_text_to_png("   ", str(tmp_path / "t.png"))

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_engine_fails_overflow(tmp_path):
    engine = TypographyEngine(font_path=TEST_FONT_PATH)
    with pytest.raises(ValueError):
        # 10x10 canvas is too small for size 70 font
        engine.render_text_to_png("متن طولانی", str(tmp_path / "t.png"), canvas_size=(10, 10))
