import json
import logging
import os
from PIL import Image

import pytest

from agents.editing.typography_engine import TypographyEngine

from agents.carousel import (
    CAROUSEL_DECK_EMPTY,
    CAROUSEL_DECK_INVALID,
    CarouselDeck,
    CarouselDeckEmptyError,
    CarouselDeckError,
    CarouselDeckRenderer,
    CarouselSlide,
    parse_carousel_deck,
    parse_carousel_slide,
    prepare_carousel_content_item,
)
from agents.carousel.slide_renderer import CarouselSlideRenderer

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


class RecordingSlideRenderer:
    """Fake slide renderer: records prepared slides and writes dummy PNGs."""

    def __init__(self):
        self.received = []

    def render(self, slide, output_path):
        self.received.append(slide)
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"PNG-FAKE-BYTES")
        return output_path


def make_slides(n=3):
    """n valid slides: cover first, cta last, quotes in between."""
    slides = [{"slide_type": "cover", "title": "کاور اسلاید"}]
    for i in range(n - 2):
        slides.append({"slide_type": "quote", "title": f"نقل قول {i + 1}"})
    slides.append({"slide_type": "cta", "title": "این اسلایدها را ذخیره کن"})
    return slides


def make_deck_dict(n=3, **overrides):
    deck = {"title": "دک تست", "template": "midnight_editorial", "slides": make_slides(n)}
    deck.update(overrides)
    return deck


def make_deck_renderer():
    rec = RecordingSlideRenderer()
    return CarouselDeckRenderer(slide_renderer=rec), rec


# === A. valid 3-slide deck renders 3 PNGs in deterministic order ===

@pytest.mark.skipif(TEST_FONT_PATH is None, reason="No system font found")
def test_A_valid_deck_renders_ordered_pngs(tmp_path):
    engine = TypographyEngine(font_path=TEST_FONT_PATH, render_mode="fallback")
    renderer = CarouselDeckRenderer(slide_renderer=CarouselSlideRenderer(engine=engine))
    out_dir = str(tmp_path / "deck")
    paths = renderer.render_deck(make_deck_dict(3), out_dir)

    assert len(paths) == 3
    assert [os.path.basename(p) for p in paths] == [
        "01_cover.png", "02_quote.png", "03_cta.png"
    ]
    for p in paths:
        assert os.path.exists(p)
        img = Image.open(p)
        assert img.size == (1080, 1350)
        assert img.mode == "RGB"


# === B. filenames are zero-padded and stable ===

def test_B_filenames_zero_padded_and_stable():
    renderer, _ = make_deck_renderer()
    cover = parse_carousel_slide({"slide_type": "cover", "title": "x"})
    cta = parse_carousel_slide({"slide_type": "cta", "title": "x"})

    assert renderer.build_slide_filename(1, cover) == "01_cover.png"
    assert renderer.build_slide_filename(2, cover) == "02_cover.png"
    assert renderer.build_slide_filename(10, cta) == "10_cta.png"
    assert renderer.build_slide_filename(1, cover, prefix="mydeck") == "mydeck_01_cover.png"
    assert renderer.build_slide_filename(1, cover, prefix="  ") == "01_cover.png"
    # Stability: same inputs -> same names
    assert renderer.build_slide_filename(3, cta) == renderer.build_slide_filename(3, cta)


# === C. deck template inheritance works ===

def test_C_deck_template_inheritance(tmp_path):
    renderer, rec = make_deck_renderer()
    renderer.render_deck(make_deck_dict(3), str(tmp_path / "deck"))
    # All slides inherited the deck template (midnight_editorial)
    assert all(s.template == "midnight_editorial" for s in rec.received)


# === D. deck footer inheritance works ===

def test_D_deck_footer_inheritance(tmp_path):
    renderer, rec = make_deck_renderer()
    deck = make_deck_dict(3, deck_footer="پاورقی مشترک دک")
    deck["slides"][1]["footer"] = "پاورقی اختصاصی"
    renderer.render_deck(deck, str(tmp_path / "deck"))
    assert rec.received[0].footer == "پاورقی مشترک دک"      # inherited
    assert rec.received[1].footer == "پاورقی اختصاصی"         # explicit kept
    assert rec.received[2].footer == "پاورقی مشترک دک"      # inherited


# === E. explicit per-slide template override works ===

def test_E_per_slide_template_override(tmp_path):
    renderer, rec = make_deck_renderer()
    deck = make_deck_dict(3)
    deck["slides"][1]["template"] = "warm_cream"
    renderer.render_deck(deck, str(tmp_path / "deck"))
    assert rec.received[0].template == "midnight_editorial"
    assert rec.received[1].template == "warm_cream"
    assert rec.received[2].template == "midnight_editorial"


# === F. slide_number auto-assignment works ===

def test_F_slide_number_auto_assignment(tmp_path):
    renderer, rec = make_deck_renderer()
    deck = make_deck_dict(3)
    deck["slides"][0]["slide_number"] = 7  # explicit kept
    renderer.render_deck(deck, str(tmp_path / "deck"))
    assert rec.received[0].slide_number == 7
    assert rec.received[1].slide_number == 2
    assert rec.received[2].slide_number == 3


# === G. empty deck raises CAROUSEL_DECK_EMPTY ===

def test_G_empty_deck_raises():
    with pytest.raises(CarouselDeckEmptyError) as exc_info:
        parse_carousel_deck({"title": "خالی", "slides": []})
    assert exc_info.value.code == CAROUSEL_DECK_EMPTY

    with pytest.raises(CarouselDeckEmptyError):
        parse_carousel_deck({"title": "no slides key"})


# === H. >10 slides raises CAROUSEL_DECK_INVALID ===

def test_H_too_many_slides_raises():
    with pytest.raises(CarouselDeckError) as exc_info:
        parse_carousel_deck(make_deck_dict(11))
    assert exc_info.value.code == CAROUSEL_DECK_INVALID

    # 1 slide is below the minimum as well
    with pytest.raises(CarouselDeckError) as exc_info:
        parse_carousel_deck({"title": "t", "slides": [{"slide_type": "cover", "title": "x"}]})
    assert exc_info.value.code == CAROUSEL_DECK_INVALID

    # 10 is the allowed maximum
    assert len(parse_carousel_deck(make_deck_dict(10)).slides) == 10


# === I. invalid child slide bubbles as deck validation error ===

def test_I_invalid_child_slide_bubbles():
    deck = make_deck_dict(3)
    deck["slides"][1] = {"slide_type": "bogus_type", "title": "x"}
    with pytest.raises(CarouselDeckError) as exc_info:
        parse_carousel_deck(deck)
    assert exc_info.value.code == CAROUSEL_DECK_INVALID
    assert "slide 2" in str(exc_info.value)

    # A deck template that is not supported is also invalid
    with pytest.raises(CarouselDeckError) as exc_info:
        parse_carousel_deck(make_deck_dict(3, template="neon_pink"))
    assert exc_info.value.code == CAROUSEL_DECK_INVALID


# === J. upload helper returns ordered storage keys ===

def test_J_upload_helper_ordered_keys(tmp_path):
    # Create the rendered files the helper expects to exist
    paths = []
    for i, st in enumerate(("cover", "quote", "cta"), start=1):
        p = tmp_path / f"{i:02d}_{st}.png"
        p.write_bytes(b"PNG-FAKE")
        paths.append(str(p))

    uploads = []

    class FakeStorage:
        def upload_file(self, local_file_path, destination_path, content_type=None):
            uploads.append((local_file_path, destination_path, content_type))
            return True

    renderer, _ = make_deck_renderer()
    keys = renderer.upload_deck_to_storage(paths, "ELN-TEST-123", FakeStorage())

    assert keys == [
        "carousel/ELN-TEST-123/01_cover.png",
        "carousel/ELN-TEST-123/02_quote.png",
        "carousel/ELN-TEST-123/03_cta.png",
    ]
    assert len(uploads) == 3
    for local, dest, ct in uploads:
        assert ct == "image/png"
        assert os.path.basename(local) == os.path.basename(dest)

    # Missing file -> typed render error
    with pytest.raises(CarouselDeckError):
        renderer.upload_deck_to_storage([str(tmp_path / "missing.png")], "ELN-X", FakeStorage())
    # Empty list / bad custom_id -> typed errors
    with pytest.raises(CarouselDeckError):
        renderer.upload_deck_to_storage([], "ELN-X", FakeStorage())
    with pytest.raises(CarouselDeckError):
        renderer.upload_deck_to_storage(paths, "", FakeStorage())


# === K. repeated render_deck preserves ordering and filenames ===

def test_K_repeated_render_stable_order_and_names(tmp_path):
    renderer, _ = make_deck_renderer()
    deck = make_deck_dict(3, output_prefix="run")
    out1 = str(tmp_path / "r1")
    out2 = str(tmp_path / "r2")
    paths1 = renderer.render_deck(deck, out1)
    paths2 = renderer.render_deck(deck, out2)
    assert [os.path.basename(p) for p in paths1] == [
        "run_01_cover.png", "run_02_quote.png", "run_03_cta.png"
    ]
    assert [os.path.basename(p) for p in paths1] == [os.path.basename(p) for p in paths2]
    assert all(os.path.exists(p) for p in paths1 + paths2)


# === L. cta-last convention is a soft warning, not a failure ===

def test_L_cta_not_last_is_soft_warning(caplog):
    deck_dict = make_deck_dict(3)
    # cta in the middle, quote last
    deck_dict["slides"][1], deck_dict["slides"][2] = deck_dict["slides"][2], deck_dict["slides"][1]
    with caplog.at_level(logging.WARNING, logger="agents.carousel.deck_renderer"):
        deck = parse_carousel_deck(deck_dict)
    assert deck.slides[1].slide_type == "cta"
    assert deck.slides[2].slide_type == "quote"
    assert any("cta" in msg and "not the last" in msg for msg in caplog.messages)
    assert any("last slide is normally 'cta'" in msg for msg in caplog.messages)

    # cover-first convention warning too
    deck2_dict = make_deck_dict(3)
    deck2_dict["slides"][0], deck2_dict["slides"][1] = deck2_dict["slides"][1], deck2_dict["slides"][0]
    with caplog.at_level(logging.WARNING, logger="agents.carousel.deck_renderer"):
        parse_carousel_deck(deck2_dict)
    assert any("first slide is normally 'cover'" in msg for msg in caplog.messages)


# === Content-item preparation helper ===

def test_M_prepare_carousel_content_item():
    inserted = []

    class FakeDB:
        def insert_content(self, data):
            inserted.append(data)
            return [data]

    keys = ["carousel/ELN-C/01_cover.png", "carousel/ELN-C/02_quote.png",
            "carousel/ELN-C/03_cta.png"]
    payload = prepare_carousel_content_item(
        FakeDB(), "ELN-C", keys, title="دک آزمایش", template="psychological_dark",
        caption_fa="کپشن فارسی",
    )

    assert len(inserted) == 1
    row = inserted[0]
    assert row == payload
    assert row["content_type"] == "carousel"
    assert row["custom_id"] == "ELN-C"
    assert row["media_keys"] == keys  # ordered
    notes = json.loads(row["editor_notes"])
    assert notes["deck_title"] == "دک آزمایش"
    assert notes["deck_template"] == "psychological_dark"
    assert notes["slide_count"] == 3

    # Validation
    with pytest.raises(CarouselDeckError):
        prepare_carousel_content_item(FakeDB(), "", keys)
    with pytest.raises(CarouselDeckEmptyError):
        prepare_carousel_content_item(FakeDB(), "ELN-C", [])
