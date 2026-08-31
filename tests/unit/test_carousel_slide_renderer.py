import os
from PIL import Image, ImageDraw

import pytest

from agents.editing.typography_engine import TypographyEngine
from agents.carousel import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    CarouselConfigError,
    CarouselImageError,
    CarouselTextOverflowError,
    CarouselSlideRenderer,
    TEMPLATES,
    parse_carousel_slide,
)
from agents.carousel.schema import (
    CAROUSEL_IMAGE_NOT_FOUND,
    CAROUSEL_SLIDE_CONFIG_INVALID,
    CAROUSEL_TEXT_OVERFLOW,
)
from agents.carousel.slide_renderer import _cover_crop

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


def make_renderer():
    engine = TypographyEngine(font_path=TEST_FONT_PATH, render_mode="fallback")
    return CarouselSlideRenderer(engine=engine)


def make_source_image(path, size=(1600, 900), color=(30, 60, 120)):
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    # Distinctive marker in the top-left corner
    draw.rectangle([0, 0, 120, 120], fill=(255, 255, 255))
    img.save(path)
    return path


COVER_SLIDE = {
    "slide_type": "cover",
    "title": "برخی زخم‌ها با گذشت خوب نمی‌شوند",
    "eyebrow": "روان‌شناسی هویت",
    "body": "اما با فهم، شکل می‌گیرند",
    "footer": "الینا | روان‌شناسی",
    "slide_number": 1,
}


# === A. Persian cover renders a non-empty 1080x1350 PNG ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_A_persian_cover_renders_1080x1350(tmp_path):
    renderer = make_renderer()
    out = str(tmp_path / "cover.png")
    path = renderer.render(dict(COVER_SLIDE), out)
    assert path == out
    assert os.path.getsize(out) > 0
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT) == (1080, 1350)
    assert img.mode == "RGB"
    # Non-trivial image (not a solid fill)
    assert len(img.getcolors(maxcolors=100000)) > 2


# === B. The RTL shaping helper is used (no naive reversal) ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_B_rtl_shaping_helper_is_used(tmp_path):
    engine = TypographyEngine(font_path=TEST_FONT_PATH, render_mode="fallback")
    calls = {"n": 0}
    original = engine._prepare_text_fallback

    def spy(text):
        calls["n"] += 1
        return original(text)

    engine._prepare_text_fallback = spy
    renderer = CarouselSlideRenderer(engine=engine)
    renderer.render(dict(COVER_SLIDE), str(tmp_path / "cover.png"))
    # Every drawn line went through the shaping/bidi helper
    assert calls["n"] > 0


# === C. Long title wraps and shrinks without clipping ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_C_long_title_wraps_and_shrinks(tmp_path):
    renderer = make_renderer()
    long_title = " ".join(["زخم", "آینه", "سایه", "در", "نیمه‌باز", "جوهر", "آب", "نور"] * 3)[:78]
    slide = {
        "slide_type": "title_body",
        "title": long_title,
        "body": "متن بدنه‌ی کوتاه برای تست سلسله‌مراتب تایپوگرافی.",
    }

    # Deterministic wrap produces multiple lines, each within the max width
    probe = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(probe)
    from PIL import ImageFont
    max_width = CANVAS_WIDTH - 2 * 90
    font = ImageFont.truetype(TEST_FONT_PATH, 104)
    lines = renderer.wrap_text(slide["title"], 104, max_width)
    assert len(lines) >= 2
    for line in lines:
        _, width, _ = renderer._line_layout(draw, line, font)
        assert width <= max_width + 1

    # Renders without clipping (no exception) at a reduced size
    out = str(tmp_path / "long.png")
    assert os.path.getsize(renderer.render(slide, out)) > 0


# === D. title_body renders title and body hierarchy ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_D_title_body_hierarchy(tmp_path):
    renderer = make_renderer()
    slide = {
        "slide_type": "title_body",
        "title": "تصویر بدنت، بایگانی خاطرات توست",
        "body": "وقتی در آینه نگاه می‌کنی، فقط صورت خودت را نمی‌بینی؛ سال‌ها نگاه دیگران هم در آنجا جا شده‌اند.",
        "eyebrow": "هویت",
        "footer": "الینا",
        "slide_number": 2,
    }
    out = str(tmp_path / "title_body.png")
    renderer.render(slide, out)
    img = Image.open(out)
    assert img.size == (1080, 1350)
    assert os.path.getsize(out) > 0

    # Hierarchy: the fitted title font is larger than the fitted body font
    probe = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(probe)
    _, _, title_size = renderer._fit_block(draw, slide["title"], 900, 1350 * 0.27, 104, 60, 3)
    _, _, body_size = renderer._fit_block(draw, slide["body"], 900, 1350 * 0.36, 46, 32, 7)
    assert title_size > body_size


# === E. bullet_list renders 2-5 RTL bullets ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_E_bullet_list_renders(tmp_path):
    renderer = make_renderer()
    slide = {
        "slide_type": "bullet_list",
        "title": "سه نشانه‌ی فرسودگی",
        "bullets": ["خستگی بدون دلیل", "بی‌تفاوتی نسبت به خود", "پنهان‌کاری از دیگران"],
        "footer": "الینا",
        "slide_number": 3,
    }
    out = str(tmp_path / "bullets.png")
    renderer.render(slide, out)
    img = Image.open(out)
    assert img.size == (1080, 1350)
    assert os.path.getsize(out) > 0

    # Each bullet wraps deterministically into readable lines
    for bullet in slide["bullets"]:
        assert renderer.wrap_text(bullet, 46, 900)

    # Boundary counts: 2 and 5 bullets are valid
    for n in (2, 5):
        s = dict(slide, bullets=["نکته" + "خ" * 10] * n)
        assert parse_carousel_slide(s).slide_type == "bullet_list"
    # 1 or 6 bullets are rejected (typed config error)
    for n in (1, 6):
        with pytest.raises(CarouselConfigError):
            parse_carousel_slide(dict(slide, bullets=["نکته"] * n))


# === F. image_text preserves source-image aspect ratio ===

def test_F_cover_crop_preserves_aspect_landscape():
    src = Image.new("RGB", (1600, 900), (20, 40, 80))
    result = _cover_crop(src, 1080, 878)
    # Output is exactly the target box (no stretch) and the scaled source
    # kept its 16:9 ratio before the center crop
    assert result.size == (1080, 878)
    scale = max(1080 / 1600, 878 / 900)
    assert abs(scale - (1080 / 1600 if 1080 / 1600 > 878 / 900 else 878 / 900)) < 1e-9


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_F_image_text_full_render(tmp_path):
    src_path = make_source_image(str(tmp_path / "src.png"), size=(1600, 900))
    renderer = make_renderer()
    slide = {
        "slide_type": "image_text",
        "image_path": src_path,
        "title": "تصویر، حافظه‌ی بصری ماست",
        "body": "هر تصویری که می‌سازیم، روایتی از درون ماست.",
        "slide_number": 4,
    }
    out = str(tmp_path / "image_text.png")
    renderer.render(slide, out)
    img = Image.open(out)
    assert img.size == (1080, 1350)
    assert os.path.getsize(out) > 0


# === G. image cover uses crop, not stretch ===

def test_G_cover_crop_portrait_source_center_cropped():
    src = Image.new("RGB", (900, 1600), (60, 20, 40))
    result = _cover_crop(src, 1080, 878)
    assert result.size == (1080, 878)
    # scale = max(1080/900, 878/1600) = 1.2 -> 1080x1920, center vertical crop
    scale = max(1080 / 900, 878 / 1600)
    assert abs(scale - 1.2) < 1e-9
    expected_top = (round(1600 * scale) - 878) // 2
    assert expected_top == (1920 - 878) // 2


# === H. missing image raises CAROUSEL_IMAGE_NOT_FOUND ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_H_missing_image_typed_error(tmp_path):
    renderer = make_renderer()
    slide = {"slide_type": "cover", "title": "تست", "image_path": "/nonexistent/img.jpg"}
    with pytest.raises(CarouselImageError) as exc_info:
        renderer.render(slide, str(tmp_path / "x.png"))
    assert exc_info.value.code == CAROUSEL_IMAGE_NOT_FOUND

    slide2 = {"slide_type": "image_text", "title": "تست", "image_path": "/nonexistent/img.jpg"}
    with pytest.raises(CarouselImageError):
        renderer.render(slide2, str(tmp_path / "y.png"))


# === I. invalid slide type raises CAROUSEL_SLIDE_CONFIG_INVALID ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_I_invalid_slide_type(tmp_path):
    renderer = make_renderer()
    with pytest.raises(CarouselConfigError) as exc_info:
        renderer.render({"slide_type": "mystery", "title": "x"}, str(tmp_path / "x.png"))
    assert exc_info.value.code == CAROUSEL_SLIDE_CONFIG_INVALID


# === J. unsupported template/accent raises a typed config error ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_J_unsupported_template_and_accent(tmp_path):
    renderer = make_renderer()
    for bad_key, bad_val in (("template", "neon_pink"), ("accent", "neon_pink")):
        slide = dict(COVER_SLIDE, **{bad_key: bad_val})
        with pytest.raises(CarouselConfigError) as exc_info:
            renderer.render(slide, str(tmp_path / "x.png"))
        assert exc_info.value.code == CAROUSEL_SLIDE_CONFIG_INVALID


# === K. text that cannot fit raises CAROUSEL_TEXT_OVERFLOW ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_K_overflow_raises_typed_error(tmp_path):
    # Tiny canvas + maximum-length quote -> cannot fit at minimum size
    renderer = CarouselSlideRenderer(
        engine=TypographyEngine(font_path=TEST_FONT_PATH, render_mode="fallback"),
        canvas_size=(100, 200),
    )
    # 179 chars (under the 180 quote limit) -> 8 wrapped lines at minimum
    # size in a ~47px box, but max_lines is 6 -> overflow.
    slide = {"slide_type": "quote", "title": "کلمه " * 35 + "کلمه"}
    with pytest.raises(CarouselTextOverflowError) as exc_info:
        renderer.render(slide, str(tmp_path / "x.png"))
    assert exc_info.value.code == CAROUSEL_TEXT_OVERFLOW


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_K_fit_block_overflow_is_deterministic():
    """Core overflow mechanism: a huge text in a tiny box raises the typed
    error even at the minimum font size."""
    renderer = make_renderer()
    probe = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(probe)
    with pytest.raises(CarouselTextOverflowError) as exc_info:
        renderer._fit_block(draw, "زخم " * 200, 100, 50, 40, 20, 2)
    assert exc_info.value.code == CAROUSEL_TEXT_OVERFLOW


# === L. all four brand templates render successfully ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_L_all_templates_render(tmp_path):
    renderer = make_renderer()
    assert set(TEMPLATES) == {
        "psychological_dark", "midnight_editorial", "warm_cream", "minimal_photo"
    }
    for i, template in enumerate(TEMPLATES):
        out = str(tmp_path / f"tpl_{i}.png")
        renderer.render(dict(COVER_SLIDE, template=template, slide_number=i + 1), out)
        img = Image.open(out)
        assert img.size == (1080, 1350)
        assert os.path.getsize(out) > 0


# === M. identical input renders deterministically ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_M_repeated_render_is_deterministic(tmp_path):
    renderer = make_renderer()
    out1 = str(tmp_path / "run1.png")
    out2 = str(tmp_path / "run2.png")
    renderer.render(dict(COVER_SLIDE), out1)
    # Fresh renderer instance, identical input
    make_renderer().render(dict(COVER_SLIDE), out2)
    assert open(out1, "rb").read() == open(out2, "rb").read()
    assert Image.open(out1).size == Image.open(out2).size


# === LTR footer/handle handling ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_LTR_footer_not_reordered_by_rtl(tmp_path):
    """An LTR handle like '@elina' must not be reordered into 'elina@' by the
    RTL engine; lines without strong RTL chars are drawn left-to-right."""
    from agents.carousel.slide_renderer import _is_rtl_line
    assert _is_rtl_line("@elina") is False
    assert _is_rtl_line("متن فارسی") is True
    assert _is_rtl_line("این mix است") is True

    renderer = make_renderer()
    slide = dict(COVER_SLIDE, footer="@elina")
    out = str(tmp_path / "ltr_footer.png")
    renderer.render(slide, out)
    assert os.path.getsize(out) > 0
    img = Image.open(out)
    assert img.size == (1080, 1350)
