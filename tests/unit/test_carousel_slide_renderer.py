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
    palette_rgb,
)
from agents.carousel.schema import (
    CAROUSEL_IMAGE_NOT_FOUND,
    CAROUSEL_SLIDE_CONFIG_INVALID,
    CAROUSEL_TEXT_OVERFLOW,
)
from agents.carousel.slide_renderer import _cover_crop, choose_auto_image_layout

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

# === N. image_overlay: full-bleed image + bottom gradient (M22) ===

def make_overlay_source(path, size=(900, 1600), color=(30, 120, 220)):
    """Portrait source: solid color plus a full-width white band at
    src y 250..400 (visible after the center crop)."""
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 250, size[0], 400], fill=(255, 255, 255))
    img.save(path)
    return path


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_N_image_overlay_full_bleed_1080x1350(tmp_path):
    """The image covers the whole canvas: the source's top band is visible
    (like the cover) AND the bottom zone shows image color, not the flat
    background panel image_text paints there."""
    src_path = make_overlay_source(str(tmp_path / "src.png"))
    renderer = make_renderer()
    slide = {
        "slide_type": "image_overlay",
        "image_path": src_path,
        "title": "تصویر، حافظه‌ی بصری ماست",
        "body": "هر تصویری که می‌سازیم، روایتی از درون ماست.",
        "slide_number": 2,
    }
    out = str(tmp_path / "image_overlay.png")
    renderer.render(slide, out)
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT) == (1080, 1350)
    assert os.path.getsize(out) > 0

    # Top: the source's white band survives the crop -> bright pixels
    r, g, b = img.getpixel((540, 100))[:3]
    assert min(r, g, b) > 100
    # Bottom zone (safe margin column, below the text block): the source's
    # blue is still visible under the gradient
    r2, g2, b2 = img.getpixel((45, 1000))[:3]
    assert b2 >= 45 and g2 >= 28


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_N_image_overlay_preserves_source_aspect(tmp_path):
    """A landscape 1600x900 source cover-cropped to 1080x1350 scales by 1.5
    and center-crops horizontally; a white marker at src (800..850, 450..500)
    must land at output (540..615, 675..750). A stretched render would put
    it at (540..574, ...) instead — the probe point discriminates."""
    src = Image.new("RGB", (1600, 900), (30, 120, 220))
    draw = ImageDraw.Draw(src)
    draw.rectangle([800, 450, 850, 500], fill=(255, 255, 255))
    src_path = str(tmp_path / "landscape.png")
    src.save(src_path)

    renderer = make_renderer()
    out = str(tmp_path / "aspect.png")
    renderer.render({
        "slide_type": "image_overlay",
        "image_path": src_path,
        "title": "تست",
    }, out)
    img = Image.open(out)
    # White marker visible at its cover-crop position (no stretch)
    r, g, b = img.getpixel((577, 712))[:3]
    assert r > 70 and g > 70
    # Just right of the marker: darkened source color, not white
    r2, g2, b2 = img.getpixel((700, 712))[:3]
    assert r2 < 60


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_N_image_overlay_title_only_and_title_body(tmp_path):
    src_path = make_overlay_source(str(tmp_path / "src.png"))
    renderer = make_renderer()
    # title-only (with eyebrow + footer + slide number)
    out1 = str(tmp_path / "io_title.png")
    renderer.render({
        "slide_type": "image_overlay",
        "image_path": src_path,
        "title": "فقط عنوان",
        "eyebrow": "هویت",
        "footer": "الینا",
        "slide_number": 2,
    }, out1)
    img1 = Image.open(out1)
    assert img1.size == (1080, 1350)
    assert os.path.getsize(out1) > 0
    # title + body
    out2 = str(tmp_path / "io_title_body.png")
    renderer.render({
        "slide_type": "image_overlay",
        "image_path": src_path,
        "title": "عنوان اسلاید",
        "body": "متن بدنه‌ای روی گرادیان پایین تصویر.",
        "slide_number": 3,
    }, out2)
    img2 = Image.open(out2)
    assert img2.size == (1080, 1350)
    assert os.path.getsize(out2) > 0


def test_N_image_overlay_text_limits_match_image_text():
    base = {"slide_type": "image_overlay", "image_path": "x.jpg"}
    # Boundaries pass: title 60, body 140 (same as image_text)
    parse_carousel_slide(dict(base, title="ع" * 60, body="ب" * 140))
    # One char over each limit is rejected
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, title="ع" * 61))
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, title="ع", body="ب" * 141))


def test_N_image_overlay_requires_image_path():
    with pytest.raises(CarouselConfigError) as exc_info:
        parse_carousel_slide({"slide_type": "image_overlay", "title": "تست"})
    assert exc_info.value.code == CAROUSEL_SLIDE_CONFIG_INVALID


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


# === O. image_text image_layout variants (M22A) ===

def make_colored_source(path, size, color):
    Image.new("RGB", size, color).save(path)
    return path


def test_O_invalid_image_layout_rejected():
    with pytest.raises(CarouselConfigError) as exc_info:
        parse_carousel_slide({"slide_type": "image_text", "title": "تست",
                              "image_path": "x.jpg", "image_layout": "poster"})
    assert exc_info.value.code == CAROUSEL_SLIDE_CONFIG_INVALID
    # All supported values parse fine
    for layout in ("split_panel", "full_bleed_caption", "contain_caption", "auto"):
        assert parse_carousel_slide({"slide_type": "image_text", "title": "تست",
                                     "image_path": "x.jpg",
                                     "image_layout": layout}).image_layout == layout
    # Omitted -> None (legacy split_panel)
    assert parse_carousel_slide({"slide_type": "image_text", "title": "تست",
                                 "image_path": "x.jpg"}).image_layout is None


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_image_layout_none_keeps_legacy_split_panel(tmp_path):
    """image_layout=None renders exactly the legacy 65/35 layout (stored
    decks without the field are byte-for-byte unchanged)."""
    src = make_colored_source(str(tmp_path / "s.png"), (1600, 900), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "split_none.png")
    renderer.render({"slide_type": "image_text", "image_path": src, "title": "تست"}, out)
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
    # Image region (top 65%): the source blue is visible
    r, g, b = img.getpixel((540, 876))[:3]
    assert b > 100
    # Bottom 35%: opaque panel, exactly the template background
    assert img.getpixel((540, 880))[:3] == palette_rgb("ink_black")


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_split_panel_explicit_uses_65_over_35(tmp_path):
    """Explicit 'split_panel' == None (legacy), byte for byte."""
    src = make_colored_source(str(tmp_path / "s.png"), (1600, 900), (30, 120, 220))
    renderer = make_renderer()
    out_explicit = str(tmp_path / "split_explicit.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src,
        "title": "تست", "image_layout": "split_panel",
    }, out_explicit)
    img = Image.open(out_explicit)
    r, g, b = img.getpixel((540, 876))[:3]
    assert b > 100
    assert img.getpixel((540, 880))[:3] == palette_rgb("ink_black")

    out_none = str(tmp_path / "split_none.png")
    renderer.render({"slide_type": "image_text", "image_path": src, "title": "تست"}, out_none)
    assert open(out_explicit, "rb").read() == open(out_none, "rb").read()


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_full_bleed_caption_covers_full_canvas(tmp_path):
    """full_bleed_caption: the image spans the whole canvas and there is
    NO opaque background panel anywhere. (M25: caption patches are local,
    so clean margin points must show the source under the base gradient
    only.)"""
    src = make_colored_source(str(tmp_path / "s.png"), (1600, 900), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "fb.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src,
        "title": "تصویر، حافظه‌ی بصری ماست",
        "body": "هر تصویری که می‌سازیم، روایتی از درون ماست.",
        "image_layout": "full_bleed_caption",
        "slide_number": 2,
    }, out)
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
    # Clean margin points (outside any caption patch) show the source:
    # top-left, mid-left and bottom-left must be the darkened source color,
    # never the flat template background.
    for point in ((60, 60), (60, 675), (100, 1200)):
        r, g, b = img.getpixel(point)[:3]
        assert b >= 60 and g >= 30, f"{point} = {(r, g, b)}"
    # Definitely not an opaque 35% background panel
    bottom = img.getpixel((100, 1200))[:3]
    assert bottom != palette_rgb("ink_black")
    assert bottom[2] >= 30


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_full_bleed_caption_smaller_zone_without_body(tmp_path):
    """M25/M27B: the readability patch is sized to the text block. Both
    renders stack in the auto 'bottom' zone; WITH a body the stacked block
    (and its patch) is taller, so a point inside the with-body patch but
    above the title-only patch is less darkened without the body.
    """
    src = make_colored_source(str(tmp_path / "s.png"), (1600, 900), (30, 120, 220))
    renderer = make_renderer()
    base = {"slide_type": "image_text", "image_path": src, "title": "تست",
            "image_layout": "full_bleed_caption"}
    out_tb = str(tmp_path / "fb_tb.png")
    renderer.render(dict(base, body="متن بدنه‌ای برای تست."), out_tb)
    out_t = str(tmp_path / "fb_t.png")
    renderer.render(base, out_t)
    # y=1100: inside both patches, but deeper into the taller with-body one
    b_with_body = Image.open(out_tb).getpixel((540, 1100))[2]
    b_title_only = Image.open(out_t).getpixel((540, 1100))[2]
    assert b_with_body < b_title_only
    # Above both patches: identical base photo
    assert Image.open(out_tb).getpixel((540, 900)) == Image.open(out_t).getpixel((540, 900))


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_contain_caption_wide_source_no_crop_no_stretch(tmp_path):
    """A 16:9 source is contain-fitted (1080x608, centered): the marker
    lands exactly at the contain position (proves no stretch and no
    cover-crop) and both top and bottom image edges stay visible."""
    src = Image.new("RGB", (1600, 900), (30, 120, 220))
    draw = ImageDraw.Draw(src)
    draw.rectangle([800, 450, 850, 500], fill=(255, 255, 255))
    src_path = str(tmp_path / "wide.png")
    src.save(src_path)

    renderer = make_renderer()
    out = str(tmp_path / "contain_wide.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src_path,
        "title": "تست", "body": "بدنه", "image_layout": "contain_caption",
    }, out)
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)

    scale = min(CANVAS_WIDTH / 1600, CANVAS_HEIGHT / 900)  # 0.675
    fit_h = round(900 * scale)                             # 608
    top = (CANVAS_HEIGHT - fit_h) // 2                     # 371
    # Marker (src 800..850 x 450..500) at its exact contain position
    mx, my = int(825 * scale), top + int(475 * scale)      # (556, 691)
    assert img.getpixel((mx, my))[0] > 150
    # A point below the marker: source color under contain (would be white
    # under a stretched render) -> proves no stretch and no cover-crop
    assert img.getpixel((mx, top + int(560 * scale)))[0] < 100
    # Top edge of the fitted image: pure source color (no crop at the top)
    assert img.getpixel((10, top + 10))[:3] == (30, 120, 220)
    # Bottom edge of the fitted image still visible (under the gradient)
    assert img.getpixel((10, top + fit_h - 3))[2] > 100
    # Letterbox above the image: blurred+darkened source — not flat bg,
    # not the pure source either
    r2, g2, b2 = img.getpixel((540, 200))[:3]
    assert 100 < b2 < 200
    # Letterbox below the image: darkened source, not a flat panel
    r3, g3, b3 = img.getpixel((540, 1000))[:3]
    assert b3 > 40 and g3 > 30


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_contain_caption_portrait_source_side_letterboxed(tmp_path):
    """A 9:16 source is contain-fitted to a full-height centered column;
    the left/right letterbox is a blurred+darkened copy (Pillow only)."""
    src = Image.new("RGB", (900, 1600), (30, 120, 220))
    draw = ImageDraw.Draw(src)
    draw.rectangle([400, 800, 450, 850], fill=(255, 255, 255))
    src_path = str(tmp_path / "tall.png")
    src.save(src_path)

    renderer = make_renderer()
    out = str(tmp_path / "contain_tall.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src_path,
        "title": "تست", "body": "بدنه", "image_layout": "contain_caption",
    }, out)
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)

    scale = min(CANVAS_WIDTH / 900, CANVAS_HEIGHT / 1600)  # 0.84375
    fit_w = round(900 * scale)                             # 759
    x0 = (CANVAS_WIDTH - fit_w) // 2                       # 160
    # Marker at its exact contain position
    mx, my = x0 + int(425 * scale), int(825 * scale)
    assert img.getpixel((mx, my))[0] > 150
    # Fitted column: pure source color at the top (no crop at the top)
    assert img.getpixel((x0 + 40, 50))[:3] == (30, 120, 220)
    # Side letterbox: darkened source, not flat background, not pure source
    for x in (80, CANVAS_WIDTH - 80):
        r, g, b = img.getpixel((x, 300))[:3]
        assert 100 < b < 200


def test_O_auto_selection_by_aspect():
    # 4:5 (the carousel ratio) -> full-bleed
    assert choose_auto_image_layout(1080, 1350) == "full_bleed_caption"
    assert choose_auto_image_layout(900, 1125) == "full_bleed_caption"
    assert choose_auto_image_layout(1200, 1500) == "full_bleed_caption"
    # Very wide / very tall / square -> contain (letterboxed)
    assert choose_auto_image_layout(1920, 1080) == "contain_caption"
    assert choose_auto_image_layout(1080, 1920) == "contain_caption"
    assert choose_auto_image_layout(1080, 1080) == "contain_caption"
    # Deterministic
    assert choose_auto_image_layout(1600, 900) == choose_auto_image_layout(1600, 900)


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_auto_e2e_4to5_full_bleed_wide_contain(tmp_path):
    renderer = make_renderer()
    # 4:5 source -> full-bleed (top of the canvas shows the source)
    src45 = make_colored_source(str(tmp_path / "r45.png"), (1080, 1350), (30, 120, 220))
    out1 = str(tmp_path / "auto_45.png")
    renderer.render({"slide_type": "image_text", "image_path": src45,
                     "title": "تست", "image_layout": "auto"}, out1)
    assert Image.open(out1).getpixel((540, 60))[2] >= 60
    # 16:9 source -> contain (letterbox band at the top)
    src169 = make_colored_source(str(tmp_path / "r169.png"), (1920, 1080), (30, 120, 220))
    out2 = str(tmp_path / "auto_169.png")
    renderer.render({"slide_type": "image_text", "image_path": src169,
                     "title": "تست", "image_layout": "auto"}, out2)
    img2 = Image.open(out2)
    assert 100 < img2.getpixel((540, 200))[2] < 200


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_cover_layout_unchanged(tmp_path):
    """image_layout only applies to image_text: cover renders identically
    with and without it (full-bleed image, centered title)."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    base = {"slide_type": "cover", "title": "کاور", "image_path": src}
    out1 = str(tmp_path / "cover1.png")
    out2 = str(tmp_path / "cover2.png")
    renderer.render(base, out1)
    renderer.render(dict(base, image_layout="auto"), out2)
    assert open(out1, "rb").read() == open(out2, "rb").read()
    # Full-bleed cover: the source is visible at the top
    assert Image.open(out1).getpixel((540, 60))[2] >= 60


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_O_missing_image_typed_error_all_layouts(tmp_path):
    renderer = make_renderer()
    for layout in (None, "split_panel", "full_bleed_caption",
                   "contain_caption", "auto"):
        slide = {"slide_type": "image_text", "title": "تست",
                 "image_path": "/nonexistent/img.jpg"}
        if layout is not None:
            slide["image_layout"] = layout
        with pytest.raises(CarouselImageError) as exc_info:
            renderer.render(slide, str(tmp_path / "x.png"))
        assert exc_info.value.code == CAROUSEL_IMAGE_NOT_FOUND


# === P. text_zone: smart placement for full-bleed slides (M23) ===

def test_H_invalid_text_zone_rejected():
    with pytest.raises(CarouselConfigError) as exc_info:
        parse_carousel_slide({"slide_type": "image_text", "title": "تست",
                              "image_path": "x.jpg", "text_zone": "sideways"})
    assert exc_info.value.code == CAROUSEL_SLIDE_CONFIG_INVALID
    # Valid values parse fine
    for zone in ("top", "middle", "bottom"):
        assert parse_carousel_slide({"slide_type": "image_text", "title": "تست",
                                     "image_path": "x.jpg",
                                     "text_zone": zone}).text_zone == zone
    # Omitted -> None (auto-detect)
    assert parse_carousel_slide({"slide_type": "image_text", "title": "تست",
                                 "image_path": "x.jpg"}).text_zone is None


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_F_text_zone_top_renders_text_in_top_region(tmp_path):
    """Explicit text_zone='top': gradient + text in the top safe area, and
    the bottom of the photo is NOT darkened by the caption gradient."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "zone_top.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src,
        "title": "تست", "body": "بدنه‌ی تست",
        "image_layout": "full_bleed_caption", "text_zone": "top",
    }, out)
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
    # Top is darkened by the mirrored gradient; bottom only has the light
    # base gradient -> bottom stays visibly brighter
    top = img.getpixel((540, 60))[:3]
    bottom = img.getpixel((540, 1200))[:3]
    assert top[1] < bottom[1] and top[2] < bottom[2]
    # Text (bright) lives in the top region, not in the bottom region
    assert img.crop((0, 100, 1080, 560)).getextrema()[0][1] > 200
    assert img.crop((0, 900, 1080, 1220)).getextrema()[0][1] < 200


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_F2_text_zone_middle_renders_centered_band(tmp_path):
    """Explicit text_zone='middle': band gradient peaks in the vertical
    center and the text is centered. (Title+body: the band grows with the
    text stack — an int height is required for the gradient.)"""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "zone_mid.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src,
        "title": "تست", "body": "بدنه‌ی تست برای مرکز تصویر",
        "image_layout": "full_bleed_caption", "text_zone": "middle",
    }, out)
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
    # Center row darker than the top row (band gradient peaks mid-way)
    assert img.getpixel((540, 675))[2] < img.getpixel((540, 60))[2]
    # Text is bright in the center, absent from the top area
    assert img.crop((0, 560, 1080, 800)).getextrema()[0][1] > 200
    assert img.crop((0, 100, 1080, 400)).getextrema()[0][1] < 200


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_G_text_zone_none_triggers_auto_detection(tmp_path, monkeypatch):
    """text_zone=None (default): the renderer auto-detects the zone from the
    source image and uses the result."""
    import agents.carousel.slide_renderer as sr
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    calls = []

    def fake_zone(image):
        calls.append(image)
        return "top"

    monkeypatch.setattr(sr, "find_best_text_zone", fake_zone)
    out = str(tmp_path / "zone_auto.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src,
        "title": "تست", "image_layout": "full_bleed_caption",
    }, out)
    # Auto-detection was called exactly once with the source image...
    assert len(calls) == 1
    assert calls[0].size == (1080, 1350)
    # ...and its result ("top") was used: text bright at the top, not bottom
    img = Image.open(out)
    assert img.crop((0, 100, 1080, 560)).getextrema()[0][1] > 200
    assert img.crop((0, 900, 1080, 1220)).getextrema()[0][1] < 200


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_default_stacked_on_flat_source(tmp_path):
    """M27B: a flat source — the auto zone resolves to 'bottom' (tie-break)
    and title+body stack TOGETHER in that single zone (no auto split):
    white title + gray body in the bottom region, nothing in the top."""
    import agents.carousel.slide_renderer as sr
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    assert sr.find_best_text_zone(Image.open(src)) == "bottom"
    renderer = make_renderer()
    out = str(tmp_path / "zone_default.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src,
        "title": "تست", "body": "بدنه", "image_layout": "full_bleed_caption",
    }, out)
    img = Image.open(out)
    # No text anywhere in the top half (previously the title auto-split there)
    assert img.crop((0, 0, 1080, 675)).getextrema()[0][1] < 150
    # Both parts in the bottom region: white title core...
    assert img.crop((0, 900, 1080, 1240)).getextrema()[0][1] > 200
    # ...and the gray body (dawn_gray ~L180) as well
    import numpy as np
    a = np.array(img.convert("L"))
    body_mask = (a[900:1240] > 150) & (a[900:1240] < 210)
    assert body_mask.sum() > 20


# === Q. M25 text composition: split zones, side width, blend, scale ===

def test_Q_split_zones_two_separate_patches(tmp_path):
    """title_zone + body_zone: two separate local patches; the middle of
    the canvas stays undarkened."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "split.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src,
        "title": "عنوان تست", "body": "بدنه‌ی جدا در گوشه‌ی دیگر",
        "image_layout": "full_bleed_caption",
        "title_zone": "top_right", "body_zone": "bottom_left",
    }, out)
    img = Image.open(out)
    # Title bright in the top-right block, body present in the bottom-left
    assert img.crop((500, 100, 995, 400)).getextrema()[0][1] > 200
    assert img.crop((85, 1000, 570, 1240)).getextrema()[0][1] > 150
    # Middle stays undarkened: brighter than both patch areas
    mid = img.getpixel((540, 675))[2]
    top_patch = img.getpixel((750, 150))[2]
    bot_patch = img.getpixel((300, 1100))[2]
    assert mid > top_patch
    assert mid > bot_patch


def test_Q_side_zone_block_limited_to_45_width(tmp_path):
    """Side zones limit the block to 45% width anchored to that side."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "side.png")
    renderer.render({
        "slide_type": "image_text", "image_path": src,
        "title": "عنوان", "image_layout": "full_bleed_caption",
        "text_zone": "right",
    }, out)
    img = Image.open(out)
    # Text bright only in the right 45% block
    assert img.crop((550, 400, 995, 900)).getextrema()[0][1] > 200
    # Left region: no text and NOT darkened by a patch either
    assert img.crop((90, 400, 450, 900)).getextrema()[0][1] < 200


def test_Q_blend_has_no_gradient_darkening(tmp_path):
    """Blend style: no gradient patch — a point inside the gradient's
    patch area (away from glyphs) stays undarkened."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    slide = {"slide_type": "image_text", "image_path": src, "title": "تست",
             "image_layout": "full_bleed_caption", "text_zone": "bottom"}
    out_g = str(tmp_path / "b_grad.png")
    out_b = str(tmp_path / "b_blend.png")
    renderer.render(dict(slide, text_style="gradient"), out_g)
    renderer.render(dict(slide, text_style="blend"), out_b)
    g = Image.open(out_g).getpixel((200, 1150))[2]
    b = Image.open(out_b).getpixel((200, 1150))[2]
    assert b > g


def test_Q_blend_text_color_from_zone_luminance(tmp_path):
    """Blend style samples the zone luminance: dark zone -> bone_white,
    bright zone -> ink_black."""
    renderer = make_renderer()
    dark = make_colored_source(str(tmp_path / "dark.png"), (1080, 1350), (30, 120, 220))
    out1 = str(tmp_path / "b_dark.png")
    renderer.render({"slide_type": "image_text", "image_path": dark, "title": "تست",
                     "image_layout": "full_bleed_caption", "text_zone": "bottom",
                     "text_style": "blend"}, out1)
    img1 = Image.open(out1)
    # white glyphs in the title area
    assert img1.crop((300, 1050, 780, 1200)).getextrema()[0][1] > 200
    light = make_colored_source(str(tmp_path / "light.png"), (1080, 1350), (220, 220, 220))
    out2 = str(tmp_path / "b_light.png")
    renderer.render({"slide_type": "image_text", "image_path": light, "title": "تست",
                     "image_layout": "full_bleed_caption", "text_zone": "bottom",
                     "text_style": "blend"}, out2)
    img2 = Image.open(out2)
    # black glyphs in the title area
    assert img2.crop((300, 1050, 780, 1200)).getextrema()[0][0] < 80


def test_Q_text_scale_changes_title_height(tmp_path):
    """text_scale: a larger scale yields a taller title block (its top
    edge sits higher in the bottom zone)."""
    import numpy as np
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()

    def first_bright_row(img):
        a = np.array(img.convert("L"))
        rows = np.where((a > 200).sum(axis=1) > 2)[0]
        assert len(rows) > 0
        return int(rows.min())

    def render_scale(scale):
        out = str(tmp_path / f"scale_{scale}.png")
        renderer.render({"slide_type": "image_text", "image_path": src,
                         "title": "تست", "image_layout": "full_bleed_caption",
                         "text_zone": "bottom", "text_scale": scale}, out)
        return Image.open(out)

    assert first_bright_row(render_scale(1.3)) < first_bright_row(render_scale(0.7))


def test_Q_cover_auto_calls_detector(tmp_path, monkeypatch):
    """Cover parity: text_zone='auto' on a cover runs the detector and
    places the text in the detected zone."""
    import agents.carousel.slide_renderer as sr
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    calls = []
    monkeypatch.setattr(sr, "find_best_text_zone",
                        lambda image, *a, **k: calls.append(image) or "top")
    renderer = make_renderer()
    out = str(tmp_path / "cover_auto.png")
    renderer.render({"slide_type": "cover", "title": "کاور", "image_path": src,
                     "text_zone": "auto"}, out)
    assert len(calls) >= 1
    img = Image.open(out)
    # Title landed in the top region
    assert img.crop((100, 50, 980, 450)).getextrema()[0][1] > 200


def test_Q_cover_none_stays_legacy_byte_identical(tmp_path):
    """Cover parity: text_zone=None (all defaults) is byte-identical to a
    cover rendered without any composition fields."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    base = {"slide_type": "cover", "title": "کاور", "image_path": src,
            "body": "بدنه‌ی کاور"}
    out1 = str(tmp_path / "c1.png")
    out2 = str(tmp_path / "c2.png")
    renderer.render(base, out1)
    renderer.render(dict(base, text_zone=None), out2)
    assert open(out1, "rb").read() == open(out2, "rb").read()


def test_Q_invalid_composition_values_rejected():
    base = {"slide_type": "image_text", "title": "تست", "image_path": "x.jpg"}
    # middle_center is detector-internal, not user-settable
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, text_zone="middle_center"))
    with pytest.raises(CarouselConfigError) as exc_info:
        parse_carousel_slide(dict(base, text_zone="sideways"))
    assert exc_info.value.code == CAROUSEL_SLIDE_CONFIG_INVALID
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, title_zone="nowhere"))
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, body_zone="nope"))
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, text_style="glow"))
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, text_scale=2.0))
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, text_scale=0.5))
    with pytest.raises(CarouselConfigError):
        parse_carousel_slide(dict(base, text_scale="x"))
    # Valid: all 10 addressable zones + auto, scale bounds, styles
    for z in ("auto", "top", "middle", "bottom", "left", "right",
              "top_left", "top_right", "bottom_left", "bottom_right",
              "middle_left", "middle_right"):
        assert parse_carousel_slide(dict(base, text_zone=z)).text_zone == z
    assert parse_carousel_slide(dict(base, text_scale=0.7)).text_scale == 0.7
    assert parse_carousel_slide(dict(base, text_scale=1.3)).text_scale == 1.3
    assert parse_carousel_slide(dict(base, text_scale=1)).text_scale == 1.0
    assert parse_carousel_slide(dict(base, text_style="blend")).text_style == "blend"


# === R. M26: reduced font defaults + inline styling ===

def test_R_new_title_default_smaller_than_old():
    from agents.carousel.slide_renderer import _COMP_TITLE_FACTOR
    from agents.carousel.brand_theme import get_template
    theme = get_template("psychological_dark")
    old_title = int(theme.title_size * 0.78)      # M25 default (81)
    new_title = int(theme.title_size * _COMP_TITLE_FACTOR)
    assert new_title < old_title
    # "about 25% smaller"
    assert old_title - new_title >= old_title * 0.20


def test_R_new_body_default_60_65_percent_of_title():
    from agents.carousel.slide_renderer import _COMP_TITLE_FACTOR, _COMP_BODY_RATIO
    from agents.carousel.brand_theme import get_template
    theme = get_template("psychological_dark")
    old_body = int(theme.body_size * 1.18)        # M25 default (54)
    new_title = int(theme.title_size * _COMP_TITLE_FACTOR)
    new_body = int(round(new_title * _COMP_BODY_RATIO))
    assert new_body < old_body
    assert 0.60 <= new_body / new_title <= 0.65


def test_R_cover_defaults_reduced():
    from agents.carousel.slide_renderer import _COVER_TITLE_FACTOR, _COVER_BODY_FACTOR
    from agents.carousel.brand_theme import get_template
    theme = get_template("psychological_dark")
    assert int(round(theme.title_size * _COVER_TITLE_FACTOR)) < theme.title_size
    assert int(round(theme.body_size * _COVER_BODY_FACTOR)) < theme.body_size


def test_R_text_scale_still_applies_on_new_defaults(tmp_path):
    """text_scale multiplies the NEW starting defaults (behavior
    unchanged), measured by the rendered title's top edge in a bottom
    zone."""
    import numpy as np
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()

    def first_bright_row(img):
        a = np.array(img.convert("L"))
        rows = np.where((a > 200).sum(axis=1) > 2)[0]
        assert len(rows) > 0
        return int(rows.min())

    def render_scale(scale):
        out = str(tmp_path / f"r_scale_{scale}.png")
        renderer.render({"slide_type": "image_text", "image_path": src,
                         "title": "تست", "image_layout": "full_bleed_caption",
                         "text_zone": "bottom", "text_scale": scale}, out)
        return Image.open(out)

    assert first_bright_row(render_scale(1.3)) < first_bright_row(render_scale(0.7))


def test_R_overflow_protection_still_works(tmp_path):
    """Tiny canvas + maximum-length text still raises the typed overflow
    error (minimums untouched)."""
    renderer = CarouselSlideRenderer(
        engine=TypographyEngine(font_path=TEST_FONT_PATH, render_mode="fallback"),
        canvas_size=(100, 200),
    )
    with pytest.raises(CarouselTextOverflowError) as exc_info:
        renderer.render({"slide_type": "quote", "title": "کلمه " * 35 + "کلمه"},
                        str(tmp_path / "x.png"))
    assert exc_info.value.code == CAROUSEL_TEXT_OVERFLOW


def test_R_unmarked_text_takes_plain_path(tmp_path):
    """No markup -> plain TextFit (byte-identical legacy path)."""
    renderer = make_renderer()
    probe = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(probe)
    fit = renderer._fit_text(draw, "متن ساده بدون markup", 900, 300, 80, 40, 3)
    assert fit.plain is True
    assert fit.rich_lines is None
    # plain render matches _fit_block + _draw_block exactly
    font, lines, size = renderer._fit_block(draw, "متن ساده بدون markup", 900, 300, 80, 40, 3)
    assert fit.lines == lines
    assert fit.size == size
    assert fit.font.size == font.size


# --- inline styling rendering ---

def _render_styled(tmp_path, title, extra=None, body=""):
    src = make_colored_source(str(tmp_path / "src.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "styled.png")
    slide = {"slide_type": "image_text", "image_path": src, "title": title,
             "image_layout": "full_bleed_caption", "text_zone": "bottom"}
    if body:
        slide["body"] = body
    slide.update(extra or {})
    renderer.render(slide, out)
    return Image.open(out)


def _pixels_near(img, box, target, tol=45):
    """Count pixels in `box` within `tol` (per channel) of `target`."""
    r, g, b = target
    n = 0
    for px in img.crop(box).getdata():
        if abs(px[0] - r) <= tol and abs(px[1] - g) <= tol and abs(px[2] - b) <= tol:
            n += 1
    return n


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_R_styled_segment_renders_with_color(tmp_path):
    """A [word|color=#B89B65] segment renders in that color; the rest of
    the title keeps the default (bone_white) color."""
    img = _render_styled(tmp_path, "وقتی [خوب‌بودن|color=#B89B65] راه")
    # Title zone (bottom): scan the whole lower band for both colors
    box = (60, 950, 1020, 1240)
    # bone_white (233, 227, 218) for the unstyled parts...
    assert _pixels_near(img, box, (233, 227, 218), tol=40) > 15
    # ...and the antique_gold accent (184, 155, 101) for the styled word
    assert _pixels_near(img, box, (184, 155, 101), tol=40) > 15


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_R_styled_segment_renders_with_size(tmp_path):
    """A [word|size=1.6] segment uses the scaled font size (measured via
    the rich layout's effective sizes)."""
    from agents.carousel.inline_styles import parse_inline_styles
    renderer = make_renderer()
    probe = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(probe)
    fit = renderer._fit_text(draw, "تست [تست|size=1.6] تست", 900, 400, 80, 40, 3)
    assert fit.plain is False
    eff_sizes = {u[2] for line in fit.rich_lines for u in line}
    assert fit.size in eff_sizes
    assert round(fit.size * 1.6) in eff_sizes
    # ...and it renders without error
    out = str(tmp_path / "styled_size.png")
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer.render({"slide_type": "image_text", "image_path": src,
                     "title": "تست [تست|size=1.6] تست",
                     "image_layout": "full_bleed_caption",
                     "text_zone": "bottom"}, out)
    assert Image.open(out).size == (1080, 1350)


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_R_styled_body_segment_renders(tmp_path):
    """Markup in the BODY works too (color override on a body phrase)."""
    img = _render_styled(tmp_path, "عنوان ساده",
                         body="بخشی که از [بخش زنده‌ترِ تو|color=#B89B65] محافظت می‌کند")
    box = (60, 900, 1020, 1240)
    assert _pixels_near(img, box, (184, 155, 101), tol=40) > 15


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_R_malformed_markup_renders_plain(tmp_path):
    """Malformed markup: the whole text renders as plain (no crash, no
    partial styling)."""
    img = _render_styled(tmp_path, "متن [بدون بستن|color=#B89B65 ادامه")
    box = (60, 950, 1020, 1240)
    # Plain title color only — no accent-colored pixels
    assert _pixels_near(img, box, (233, 227, 218), tol=40) > 15
    assert _pixels_near(img, box, (184, 155, 101), tol=40) < 5


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_R_rtl_styled_flow_right_to_left(tmp_path):
    """Styled segments flow right-to-left: in a centered line, the FIRST
    styled segment sits to the RIGHT of the second one."""
    renderer = make_renderer()
    probe = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(probe)
    fit = renderer._fit_text(
        draw, "الف [ب|color=#FF0000] ج [د|color=#00FF00] ه", 900, 400, 80, 40, 3)
    assert fit.plain is False
    line = fit.rich_lines[0]
    # Logical order preserved in the unit list (flow is drawn RTL)
    texts = [u[0] for u in line]
    assert texts.index("ب") < texts.index("د")
    # Drawn right-to-left: the first styled unit ends at the right edge
    x_cursor = 900  # right edge used by the draw call below
    positions = {}
    for text, color, eff, w in line:
        x_cursor -= w
        positions[text] = x_cursor
    # RTL: later logical units are further LEFT (smaller x)
    assert positions["ب"] > positions["د"]


# === S. M27B: stacked default composition + edge anchoring ===

def _np(img):
    import numpy as np
    return np.array(img.convert("L")), np.array(img.convert("RGB")).astype(int)


def test_S_default_stacked_title_above_body_in_top_zone(tmp_path):
    """M27B default: title and body render as ONE stacked block in the
    same zone — title above body, separated by the accent rule (pinned
    to the top zone for determinism)."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "stacked_top.png")
    renderer.render({"slide_type": "image_text", "image_path": src,
                     "title": "تست", "body": "بدنه",
                     "image_layout": "full_bleed_caption",
                     "text_zone": "top"}, out)
    img = Image.open(out)
    L, rgb = _np(img)
    title_mask = L > 215                                   # bone_white core
    rule_mask = (rgb[:, :, 0] > 120) & (rgb[:, :, 0] - rgb[:, :, 2] > 60) \
        & (rgb[:, :, 1] > 120) & (rgb[:, :, 1] < 200)      # antique_gold rule
    body_mask = (L > 150) & (L < 210)                      # dawn_gray body
    ty = np_y(title_mask)
    ry = np_y(rule_mask)
    by = np_y(body_mask)
    assert len(ty) > 0 and len(ry) > 0 and len(by) > 0
    # Vertical order: title above the rule, body below it
    assert ty.max() < ry.min() + 3
    assert ry.max() < by.max() - 30
    # All stacked in the top zone (y < 0.35H)
    assert by.max() < 0.35 * 1350


def np_y(mask):
    import numpy as np
    return np.argwhere(mask)[:, 0]


def test_S_stacked_title_body_do_not_overlap(tmp_path):
    """Stacked mode never overlaps title and body: the gap between the
    title core and the rule holds no interleaved glyphs, and nothing
    title-colored sits below the body."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "stacked_no_overlap.png")
    renderer.render({"slide_type": "image_text", "image_path": src,
                     "title": "تست", "body": "بدنه",
                     "image_layout": "full_bleed_caption",
                     "text_zone": "top"}, out)
    img = Image.open(out)
    L, rgb = _np(img)
    title_mask = L > 215
    rule_mask = (rgb[:, :, 0] > 120) & (rgb[:, :, 0] - rgb[:, :, 2] > 60) \
        & (rgb[:, :, 1] > 120) & (rgb[:, :, 1] < 200)
    body_mask = (L > 150) & (L < 210)
    ty = np_y(title_mask)
    ry = np_y(rule_mask)
    by = np_y(body_mask)
    # Gap window between title core and rule: only anti-aliasing fringes
    gap = L[ty.max() + 3: max(ty.max() + 4, ry.min() - 3), :]
    assert (gap > 150).sum() < 20
    # Nothing title-colored below the body
    below = L[by.max() + 10: min(by.max() + 110, 600), :]
    assert (below > 210).sum() == 0


def test_S_explicit_split_zones_still_split(tmp_path):
    """M25 split behavior is preserved when the operator sets explicit
    per-part zones: title top_right, body bottom_left, separate patches."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "split_explicit.png")
    renderer.render({"slide_type": "image_text", "image_path": src,
                     "title": "تست", "body": "بدنه",
                     "image_layout": "full_bleed_caption",
                     "title_zone": "top_right", "body_zone": "bottom_left"}, out)
    img = Image.open(out)
    L, _ = _np(img)
    # Title core in the top-right quadrant
    tr = L[0:450, 500:1080]
    assert (tr > 215).sum() > 20
    # Body (gray) in the bottom-left quadrant
    bl = L[900:1240, 0:600]
    assert ((bl > 150) & (bl < 210)).sum() > 20
    # No title-colored pixels in the bottom half, no text in the top-left
    assert (L[900:1350, :] > 215).sum() == 0
    assert (L[0:450, 0:450] > 150).sum() == 0


def test_S_left_zone_anchored_near_left_margin(tmp_path):
    import numpy as np
    """Side-zone anchoring: a left-zone block hugs the left safe margin —
    the right-aligned text's right edge sits at margin + 45%W, clearly in
    the left half of the canvas (not floating in the middle)."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "left_zone.png")
    renderer.render({"slide_type": "image_text", "image_path": src,
                     "title": "تست", "image_layout": "full_bleed_caption",
                     "text_zone": "middle_left"}, out)
    L, _ = _np(Image.open(out))
    xs = np.argwhere(L > 215)[:, 1]
    assert len(xs) > 0
    block_right = 90 + int(1080 * 0.45)  # left margin + 45% width
    assert xs.max() <= block_right + 5
    assert xs.max() < 0.55 * 1080        # stays in the left half
    assert xs.min() > 90 - 5             # never left of the safe margin


def test_S_right_zone_anchored_near_right_margin(tmp_path):
    import numpy as np
    """Side-zone anchoring: a right-zone block hugs the right safe margin."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "right_zone.png")
    renderer.render({"slide_type": "image_text", "image_path": src,
                     "title": "تست", "image_layout": "full_bleed_caption",
                     "text_zone": "middle_right"}, out)
    L, _ = _np(Image.open(out))
    xs = np.argwhere(L > 215)[:, 1]
    assert len(xs) > 0
    assert xs.max() >= 1080 - 90 - 5     # right edge at the right safe margin
    assert xs.max() <= 1080 - 90 + 2
    assert xs.min() > 0.45 * 1080        # stays in the right half


def test_S_center_zone_horizontally_centered(tmp_path):
    import numpy as np
    """Center zones center the block horizontally."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    renderer = make_renderer()
    out = str(tmp_path / "center_zone.png")
    renderer.render({"slide_type": "image_text", "image_path": src,
                     "title": "تست", "image_layout": "full_bleed_caption",
                     "text_zone": "middle"}, out)
    L, _ = _np(Image.open(out))
    xs = np.argwhere(L > 215)[:, 1]
    assert len(xs) > 0
    assert abs((xs.min() + xs.max()) / 2 - 540) <= 10


def test_S_legacy_slide_without_new_fields_renders(tmp_path):
    """A legacy slide dict (no M25/M26/M27 fields) parses and renders fine
    under the new defaults: stacked auto zone (flat source -> bottom)."""
    src = make_colored_source(str(tmp_path / "s.png"), (1080, 1350), (30, 120, 220))
    slide = parse_carousel_slide({"slide_type": "image_text", "title": "تست",
                                  "body": "بدنه", "image_path": src})
    assert slide.text_zone is None
    assert slide.title_zone is None and slide.body_zone is None
    assert slide.text_scale is None
    renderer = make_renderer()
    out = str(tmp_path / "legacy.png")
    renderer.render(slide, out)
    img = Image.open(out)
    assert img.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
    # Stacked in the quietest zone (bottom for a flat source)
    assert img.crop((0, 900, 1080, 1240)).getextrema()[0][1] > 150
    assert img.crop((0, 0, 1080, 675)).getextrema()[0][1] < 150
