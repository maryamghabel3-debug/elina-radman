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

def test_missing_font_raises_error():
    with pytest.raises(FileNotFoundError):
        TypographyEngine(font_path="/non/existent.ttf")

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
