import pytest
import os
from PIL import Image
from agents.editing.typography_engine import TypographyEngine

pytestmark = pytest.mark.unit

# Try to find a default system font for testing purposes
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

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No default system font found for testing")
def test_typography_engine_creates_valid_png(tmp_path):
    engine = TypographyEngine(font_path=TEST_FONT_PATH)
    output_file = tmp_path / "test_output.png"

    result_path = engine.render_text_to_png(
        text="تست",
        output_path=str(output_file)
    )

    assert os.path.exists(result_path)
    img = Image.open(result_path)
    assert img.mode == "RGBA"
    assert img.width > 0

def test_typography_engine_fails_without_font():
    with pytest.raises(FileNotFoundError):
        TypographyEngine(font_path="/non/existent/font.ttf")

def test_reshape_logic_changes_text_order():
    # We can test the internal logic without needing a font file necessarily,
    # but since __init__ requires a font, we mock font_path check temporarily
    # or test static logic if refactored.
    # For simplicity here, we assume Font exists check is bypassed if TEST_FONT_PATH exists.
    if TEST_FONT_PATH:
        engine = TypographyEngine(font_path=TEST_FONT_PATH)
        original = "سلام"
        prepared = engine._prepare_text(original)
        assert original != prepared  # Bidi/reshape should change the character forms/order representation
