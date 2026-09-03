import os
from PIL import Image

import pytest

from agents.editing.recipe_schema import SubtitleEntry
from agents.editing.subtitle_renderer import (
    SubtitleRenderer,
    overlay_position,
    parse_subtitle_entries,
    SUBTITLE_CONFIG_INVALID,
    SUBTITLE_FONT_NOT_FOUND,
    TOP_SAFE_MARGIN,
)
from agents.editing.typography_engine import TypographyEngine

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


def make_font_engine():
    """Fallback-mode engine with a system font (no raqm dependency in tests)."""
    return TypographyEngine(font_path=TEST_FONT_PATH, render_mode="fallback")


def make_renderer():
    return SubtitleRenderer(engine=make_font_engine())


VALID_PERSIAN_SUBTITLE = {
    "text": "بعضی لبخندها انتخاب ما نیستند.",
    "start_sec": 1.0,
    "end_sec": 4.0,
}


# === Schema / validation ===

def test_A_valid_persian_subtitle_accepted():
    """A valid Persian subtitle dict parses into a SubtitleEntry with defaults."""
    entries = parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE)])
    assert len(entries) == 1
    e = entries[0]
    assert isinstance(e, SubtitleEntry)
    assert e.text == "بعضی لبخندها انتخاب ما نیستند."
    assert e.start_sec == 1.0
    assert e.end_sec == 4.0
    assert e.position == "bottom_center"
    assert e.style == "default"
    assert e.font_size == 52
    assert e.max_width_ratio == 0.82


def test_B_empty_text_rejected():
    for bad_text in ["", "   ", None]:
        with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
            parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, text=bad_text)])


def test_C_end_sec_le_start_rejected():
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, start_sec=4.0, end_sec=4.0)])
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, start_sec=5.0, end_sec=4.0)])
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, start_sec=-0.5, end_sec=4.0)])


def test_D_invalid_position_or_style_rejected():
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, position="left_corner")])
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, style="glow")])
    # All supported positions/styles are accepted
    for position in ("bottom_center", "center", "top_center"):
        for style in ("default", "hook", "whisper", "name_reveal"):
            entries = parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, position=position, style=style)])
            assert entries[0].position == position
            assert entries[0].style == style


def test_E_excessive_fade_duration_rejected():
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([
            dict(VALID_PERSIAN_SUBTITLE, start_sec=1.0, end_sec=1.2,
                 fade_in_sec=0.5, fade_out_sec=0.5),  # 1.0s fades > 0.2s duration
        ])
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, fade_in_sec=-0.1)])
    # Boundary: fades exactly equal to the duration are accepted
    entries = parse_subtitle_entries([
        dict(VALID_PERSIAN_SUBTITLE, start_sec=1.0, end_sec=1.24,
             fade_in_sec=0.12, fade_out_sec=0.12),
    ])
    assert entries[0].fade_in_sec == 0.12


def test_range_validation_rejects_out_of_bounds():
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, font_size=150)])
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, max_width_ratio=0.2)])
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, background_opacity=1.5)])
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, font_color="white")])


def test_non_list_subtitles_rejected():
    with pytest.raises(ValueError, match=SUBTITLE_CONFIG_INVALID):
        parse_subtitle_entries(VALID_PERSIAN_SUBTITLE)
    assert parse_subtitle_entries(None) == []


# === Typography (needs a system font; skipped otherwise, like test_typography_engine) ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_F_persian_text_produces_non_empty_rgba(tmp_path):
    """Persian text renders to a non-empty RGBA PNG with a background box."""
    renderer = make_renderer()
    entry = parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE)])[0]
    out = str(tmp_path / "subtitle_000.png")

    path = renderer.render(entry, out)

    assert path == out
    assert os.path.getsize(out) > 0
    img = Image.open(out)
    assert img.mode == "RGBA"
    # Background box present: some pixels have partial/strong alpha below the text
    alpha_extrema = img.getextrema()[3]
    assert alpha_extrema[1] > 0
    # No leftover temp text layer
    assert not os.path.exists(out + ".text.png")


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_G_shaping_helper_produces_display_order_rtl_text():
    """The fallback shaping helper shapes Arabic letters (presentation forms)
    and applies bidi display ordering — not reversed source-order glyphs."""
    engine = make_font_engine()
    source = "نور"  # n-w-r: shaping must join the letters
    prepared = engine._prepare_text_fallback(source)

    # Shaped: at least one presentation-form codepoint (U+FB50..U+FEFF)
    assert any(0xFB50 <= ord(c) <= 0xFEFF for c in prepared)
    # Display order applied: the prepared string is not the logical source order
    assert prepared != source
    # Bidi display order for a pure-RTL run: first display glyph comes from
    # the LAST logical character (r -> final form), last from the first (n).
    import arabic_reshaper
    reshaped = arabic_reshaper.reshape(source)
    assert prepared == reshaped[::-1]


@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_H_multiline_wrapping_respects_max_width(tmp_path):
    """Long Persian text wraps into multiple lines, each within max width,
    and the rendered PNG is taller than a single line."""
    renderer = make_renderer()
    entry = SubtitleEntry(
        text="بعضی لبخندها انتخاب ما نیستند و بعضی‌ها پیش از ما ساخته شده‌اند و می‌مانند.",
        start_sec=0.0,
        end_sec=5.0,
        font_size=40,
        max_width_ratio=0.45,  # narrow -> forces wrapping
    )
    from PIL import ImageFont
    font = ImageFont.truetype(TEST_FONT_PATH, 40)
    max_width = entry.max_width_ratio * 1080

    lines = renderer.wrap_text(entry.text, font, max_width)
    assert len(lines) >= 2
    probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(probe)
    for line in lines:
        width, _ = renderer._line_metrics(draw, font, line)
        assert width <= max_width

    out = str(tmp_path / "wrapped.png")
    renderer.render(entry, out)
    img = Image.open(out)
    # Wrapped block must be at least ~2 lines tall (line height = font + 10px)
    assert img.size[1] >= 2 * (40 + 10)


# === Overlay positions (dimension-agnostic expressions) ===

def test_L_position_expressions():
    bottom = parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE)])[0]
    center = parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, position="center")])[0]
    top = parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, position="top_center")])[0]
    custom_margin = parse_subtitle_entries([dict(VALID_PERSIAN_SUBTITLE, margin_bottom=250)])[0]

    assert overlay_position(bottom) == ("(W-w)/2", "H-h-180")
    assert overlay_position(center) == ("(W-w)/2", "(H-h)/2")
    assert overlay_position(top) == ("(W-w)/2", str(TOP_SAFE_MARGIN))
    assert overlay_position(custom_margin) == ("(W-w)/2", "H-h-250")


# === Font failure (unit level) ===

def test_P_font_not_found_raises_typed_error(monkeypatch):
    """With no resolvable font at all, SubtitleRenderer raises SUBTITLE_FONT_NOT_FOUND.

    (The repo now bundles a Persian font, so we patch every candidate to be
    unavailable to simulate a truly fontless environment.)
    """
    import agents.editing.font_resolver as font_resolver

    monkeypatch.delenv("ELINA_FONT_PRIMARY_PATH", raising=False)
    monkeypatch.setattr(font_resolver, "BUNDLED_FONT_PATH", "/non/existent/bundled.ttf")
    monkeypatch.setattr(font_resolver, "SYSTEM_PERSIAN_FONT_CANDIDATES", [])
    with pytest.raises(RuntimeError) as exc_info:
        SubtitleRenderer()
    assert SUBTITLE_FONT_NOT_FOUND in str(exc_info.value)
