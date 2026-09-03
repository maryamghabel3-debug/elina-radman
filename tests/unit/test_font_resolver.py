import os
import shutil

import pytest
from PIL import ImageFont

from agents.editing import font_resolver
from agents.editing.font_resolver import (
    BUNDLED_FONT_PATH,
    FontNotFoundError,
    resolve_persian_font,
)

pytestmark = pytest.mark.unit


def _temp_font_copy(tmp_path):
    """A second valid font file (a copy of the bundled font) at a distinct path."""
    dst = tmp_path / "CopyOfVazirmatn.ttf"
    shutil.copyfile(str(BUNDLED_FONT_PATH), str(dst))
    return str(dst)


def test_bundled_font_is_loadable_by_pillow():
    """The repo-bundled Vazirmatn is a real, loadable Persian font."""
    assert os.path.exists(BUNDLED_FONT_PATH)
    font = ImageFont.truetype(str(BUNDLED_FONT_PATH), 40)
    # Persian text must produce a non-empty bounding box (real Persian glyphs).
    bbox = font.getbbox("سلام دنیا")
    assert bbox[2] > bbox[0]


def test_valid_explicit_path_wins(monkeypatch, tmp_path):
    """An explicit valid path wins over the env var and the bundled font."""
    env_font = _temp_font_copy(tmp_path)
    monkeypatch.setenv("ELINA_FONT_PRIMARY_PATH", env_font)
    assert resolve_persian_font(str(BUNDLED_FONT_PATH)) == str(BUNDLED_FONT_PATH)


def test_env_path_used_when_no_explicit(monkeypatch, tmp_path):
    """A valid env path wins over the bundled font when no explicit path is set."""
    env_font = _temp_font_copy(tmp_path)
    monkeypatch.setenv("ELINA_FONT_PRIMARY_PATH", env_font)
    assert resolve_persian_font() == env_font


def test_invalid_env_falls_back_to_bundled(monkeypatch):
    """A configured-but-missing env path falls back to the repo font (no failure)."""
    monkeypatch.setenv("ELINA_FONT_PRIMARY_PATH", "/non/existent/nowhere.ttf")
    assert resolve_persian_font() == str(BUNDLED_FONT_PATH)


def test_no_font_available_raises_typed_error(monkeypatch):
    """When no candidate font is loadable, a clear typed error is raised."""
    monkeypatch.delenv("ELINA_FONT_PRIMARY_PATH", raising=False)
    monkeypatch.setattr(font_resolver, "BUNDLED_FONT_PATH", "/non/existent/bundled.ttf")
    monkeypatch.setattr(font_resolver, "SYSTEM_PERSIAN_FONT_CANDIDATES", [])
    with pytest.raises(FontNotFoundError):
        resolve_persian_font("/non/existent/explicit.ttf")


def test_run_server_sets_env_for_child_processes(monkeypatch):
    """check_persian_font resolves a font and sets ELINA_FONT_PRIMARY_PATH so
    child bots inherit a working path."""
    from scripts.run_server import check_persian_font

    monkeypatch.delenv("ELINA_FONT_PRIMARY_PATH", raising=False)
    assert check_persian_font() is True
    assert os.environ.get("ELINA_FONT_PRIMARY_PATH")
    # The resolved path must be a real, loadable font.
    ImageFont.truetype(os.environ["ELINA_FONT_PRIMARY_PATH"], 40)


def test_carousel_renderer_works_without_env(monkeypatch):
    """CarouselSlideRenderer resolves the bundled font even when the env var
    is absent — no manual font setup required."""
    from agents.carousel.slide_renderer import CarouselSlideRenderer

    monkeypatch.delenv("ELINA_FONT_PRIMARY_PATH", raising=False)
    renderer = CarouselSlideRenderer()
    assert renderer.engine.font_path == str(BUNDLED_FONT_PATH)
