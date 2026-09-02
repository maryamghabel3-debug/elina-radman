import os
from unittest.mock import MagicMock

import pytest
from PIL import Image

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


def write_source_image(tmp_path, size=(1600, 2000), color=(40, 50, 80)):
    img = Image.new("RGB", size, color)
    img.save(tmp_path / "src.jpg", quality=90)
    return str(tmp_path / "src.jpg")


# 1. Reel cover renders at exactly 1080x1920

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_reel_cover_renders_1080x1920(tmp_path):
    from agents.carousel import ReelCoverRenderer

    renderer = ReelCoverRenderer(font_path=TEST_FONT_PATH)
    out = str(tmp_path / "cover.png")
    path = renderer.render_cover("بعضی زخم‌ها با گذشت خوب نمی‌شوند", out)
    assert path == out
    img = Image.open(out)
    assert img.size == (1080, 1920)
    assert img.mode == "RGB"
    assert os.path.getsize(out) > 0
    # Not a solid fill: real text + layout were drawn
    assert len(img.getcolors(maxcolors=100000)) > 3


# 2. EXPLICIT REGRESSION: carousel slide renderer still defaults to 1080x1350

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_carousel_renderer_default_unchanged_1080x1350(tmp_path):
    from agents.carousel import CarouselSlide
    from agents.carousel.slide_renderer import CANVAS_HEIGHT, CANVAS_WIDTH, CarouselSlideRenderer

    # Module constants unchanged
    assert (CANVAS_WIDTH, CANVAS_HEIGHT) == (1080, 1350)

    renderer = CarouselSlideRenderer(font_path=TEST_FONT_PATH)  # no canvas_size
    slide = CarouselSlide(slide_type="cover", title="کاور کاروسل")
    out = str(tmp_path / "carousel_slide.png")
    renderer.render(slide, out)
    assert Image.open(out).size == (1080, 1350)


# 3. Short title renders without overflow

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_short_title_renders_without_overflow(tmp_path):
    from agents.carousel import ReelCoverRenderer

    renderer = ReelCoverRenderer(font_path=TEST_FONT_PATH)
    out = str(tmp_path / "short.png")
    path = renderer.render_cover("تو کافی هستی", out, eyebrow="هویت")
    assert os.path.getsize(path) > 0
    assert Image.open(path).size == (1080, 1920)


# 4. Overflow protection inherited (typed error, never clipped)

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_long_title_overflow_protection(tmp_path):
    from agents.carousel import ReelCoverRenderer
    from agents.carousel.schema import CarouselTextOverflowError

    # Tiny canvas: a 59-char / 12-word title cannot fit even at the minimum
    # font size within the 4-line max -> typed overflow error.
    renderer = ReelCoverRenderer(font_path=TEST_FONT_PATH, canvas_size=(70, 100))
    long_title = ("کلمه " * 11) + "کلمه"  # 12 words, 59 chars (<= 60 cap)
    assert len(long_title) <= 60
    with pytest.raises(CarouselTextOverflowError):
        renderer.render_cover(long_title, str(tmp_path / "x.png"))


# 5. Works with and without a background image

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_cover_with_and_without_background_image(tmp_path):
    from agents.carousel import ReelCoverRenderer

    renderer = ReelCoverRenderer(font_path=TEST_FONT_PATH)
    src = write_source_image(tmp_path)

    out_img = str(tmp_path / "with_img.png")
    renderer.render_cover("عنوان با تصویر", out_img, image_path=src)
    assert Image.open(out_img).size == (1080, 1920)

    out_plain = str(tmp_path / "plain.png")
    renderer.render_cover("عنوان بدون تصویر", out_plain)
    assert Image.open(out_plain).size == (1080, 1920)


# 6. Input validation (typed errors before rendering)

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_cover_input_validation(tmp_path):
    from agents.carousel import ReelCoverRenderer
    from agents.carousel.schema import CarouselConfigError, CarouselImageError

    renderer = ReelCoverRenderer(font_path=TEST_FONT_PATH)

    with pytest.raises(CarouselConfigError):
        renderer.render_cover("   ", str(tmp_path / "x.png"))
    with pytest.raises(CarouselConfigError):
        renderer.render_cover("ع" * 61, str(tmp_path / "x.png"))
    with pytest.raises(CarouselConfigError):
        renderer.render_cover("عنوان", str(tmp_path / "x.png"), template="neon_pink")
    with pytest.raises(CarouselConfigError):
        renderer.render_cover("عنوان", str(tmp_path / "x.png"), accent="hotpink")
    with pytest.raises(CarouselConfigError):
        renderer.render_cover("عنوان", str(tmp_path / "x.png"), eyebrow="ب" * 41)
    with pytest.raises(CarouselConfigError):
        renderer.render_cover("عنوان", str(tmp_path / "x.png"), image_path=123)
    with pytest.raises(CarouselConfigError):
        renderer.render_cover("عنوان", str(tmp_path / "x.jpg"))  # must be PNG output

    # Missing image file -> typed image error
    with pytest.raises(CarouselImageError):
        renderer.render_cover("عنوان", str(tmp_path / "y.png"),
                              image_path="/nonexistent/img.jpg")
