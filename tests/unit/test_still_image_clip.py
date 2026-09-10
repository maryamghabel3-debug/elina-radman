"""M30 — tests for agents/editing/still_image_clip.py.

The command-construction and validation tests always run. The real-ffmpeg
tests produce actual MP4s and are skipped when ffmpeg/ffprobe are not
installed (e.g. minimal CI images).
"""
import json
import math
import os
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.unit

from agents.editing.still_image_clip import (
    StillImageClipBuilder,
    StillImageClipError,
)

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg/ffprobe not installed")


# ---------------------------------------------------------------------------
# Validation (no ffmpeg needed)
# ---------------------------------------------------------------------------

def test_invalid_duration_rejected():
    b = StillImageClipBuilder()
    for bad in ("abc", None, 0, -1, math.nan, math.inf, 0.1, 3000):
        with pytest.raises(StillImageClipError):
            b.normalize_duration(bad)


def test_valid_duration_accepted():
    b = StillImageClipBuilder()
    assert b.normalize_duration("3") == 3.0
    assert b.normalize_duration(2.5) == 2.5


def test_invalid_motion_rejected():
    b = StillImageClipBuilder()
    for bad in ("pan", "slide", "", None, 5):
        with pytest.raises(StillImageClipError):
            b.normalize_motion(bad)
    # case-insensitive
    assert b.normalize_motion("ZOOM_IN") == "zoom_in"


def test_invalid_fit_rejected():
    b = StillImageClipBuilder()
    for bad in ("stretch", "fill", "", None):
        with pytest.raises(StillImageClipError):
            b.normalize_fit(bad)
    assert b.normalize_fit("COVER") == "cover"


def test_invalid_zoom_scale_rejected():
    b = StillImageClipBuilder()
    for bad in (0.5, 0.0, -1, 10, "abc", None, math.nan):
        with pytest.raises(StillImageClipError):
            b.normalize_scale("start_scale", bad)


def test_build_missing_image_raises():
    b = StillImageClipBuilder()
    with pytest.raises(StillImageClipError):
        b.build("/nonexistent/image.png", "/tmp/whatever.mp4")


def test_is_image_media_key():
    assert StillImageClipBuilder.is_image_media_key("intake/20260910/ELN.jpg")
    assert StillImageClipBuilder.is_image_media_key("intake/20260910/ELN.PNG")
    assert not StillImageClipBuilder.is_image_media_key("raw/shot1.mp4")
    assert not StillImageClipBuilder.is_image_media_key("")


# ---------------------------------------------------------------------------
# Filtergraph construction (no ffmpeg needed)
# ---------------------------------------------------------------------------

def test_filtergraph_contain_keeps_whole_image_with_blurred_fill():
    graph = StillImageClipBuilder().build_filtergraph(fit="contain")
    # whole image (aspect ratio preserved, never stretched)
    assert "force_original_aspect_ratio=decrease" in graph
    # blurred + darkened copy fills the canvas
    assert "split=2" in graph
    assert "boxblur" in graph
    assert "eq=brightness=" in graph
    assert "overlay=(W-w)/2:(H-h)/2" in graph
    # never a raw stretch onto the canvas
    assert "scale=1080:1920,setsar" not in graph


def test_filtergraph_cover_crops_without_stretch():
    graph = StillImageClipBuilder().build_filtergraph(fit="cover")
    assert "force_original_aspect_ratio=increase" in graph
    assert "crop=1080:1920" in graph
    assert "overlay" not in graph


def test_filtergraph_zoom_in_ramp_start_to_end():
    graph = StillImageClipBuilder().build_filtergraph(
        motion="zoom_in", start_scale=1.0, end_scale=1.05, duration_sec=3.0
    )
    assert "zoompan" in graph
    assert "1.000000" in graph
    assert "1.050000" in graph
    # linear ramp over 89 steps (90 frames at 30fps for 3s)
    assert "*on/89" in graph
    assert "d=90" in graph


def test_filtergraph_zoom_out_reversed():
    graph = StillImageClipBuilder().build_filtergraph(
        motion="zoom_out", start_scale=1.0, end_scale=1.2, duration_sec=1.0
    )
    # starts zoomed-in (1.2), eases back to 1.0
    assert "(1.200000+(1.000000-1.200000)*on/29" in graph
    assert "d=30" in graph


def test_filtergraph_none_is_static():
    graph = StillImageClipBuilder().build_filtergraph(motion="none", start_scale=1.0)
    assert "zoompan=z='1.000000'" in graph


def test_build_command_has_full_reel_spec():
    cmd = StillImageClipBuilder().build_command(
        "/in/pic.jpg", "/out/clip.mp4", duration_sec=3.0
    )
    joined = " ".join(cmd)
    assert cmd[0] == "ffmpeg"
    assert "/in/pic.jpg" in cmd
    assert "/out/clip.mp4" in cmd
    assert "libx264" in cmd
    assert "yuv420p" in cmd
    assert "-r" in cmd and "30" in cmd
    assert "-vsync" in cmd and "cfr" in cmd
    # silent AAC stereo 48 kHz
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    assert "-ar" in cmd and "48000" in cmd
    assert "-ac" in cmd and "2" in cmd
    assert "-movflags" in cmd and "+faststart" in cmd
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "1080x1920" in graph or "s=1080x1920" in graph
    assert "setsar=1" in graph


def test_build_command_rejects_bad_motion():
    with pytest.raises(StillImageClipError):
        StillImageClipBuilder().build_command(
            "/in/pic.jpg", "/out/clip.mp4", motion="fly"
        )


def test_build_with_mocked_ffmpeg_success(tmp_path):
    from unittest.mock import patch, MagicMock

    img = tmp_path / "pic.png"
    img.write_bytes(b"fake")
    out = tmp_path / "out.mp4"

    mock_run = MagicMock(returncode=0, stderr="")
    # simulate ffmpeg writing the output file
    def side_effect(cmd, **kw):
        out_path = cmd[-1]
        with open(out_path, "wb") as f:
            f.write(b"fake mp4")
        return mock_run

    with patch("subprocess.run", side_effect=side_effect) as mock_subprocess:
        result = StillImageClipBuilder().build(str(img), str(out), duration_sec=2.0)

    assert result == str(out)
    cmd = mock_subprocess.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert str(out) in cmd


def test_build_with_mocked_ffmpeg_failure_raises(tmp_path):
    from unittest.mock import patch, MagicMock

    img = tmp_path / "pic.png"
    img.write_bytes(b"fake")
    out = tmp_path / "out.mp4"

    mock_run = MagicMock(returncode=1, stderr="boom: encoder error")
    with patch("subprocess.run", return_value=mock_run):
        with pytest.raises(StillImageClipError) as exc:
            StillImageClipBuilder().build(str(img), str(out))
    assert "encoder error" in str(exc.value)


# ---------------------------------------------------------------------------
# Real ffmpeg tests (skipped when ffmpeg is not installed)
# ---------------------------------------------------------------------------

def _make_source_image(path, size=(1600, 900)):
    """16:9 landscape source: red band (left), blue band (right), white
    middle, 200x200 black square in the exact center."""
    from PIL import Image

    w, h = size
    img = Image.new("RGB", (w, h), (255, 255, 255))
    px = img.load()
    band = w // 8
    sq = w // 8
    cx0, cx1 = w // 2 - sq // 2, w // 2 + sq // 2
    cy0, cy1 = h // 2 - sq // 2, h // 2 + sq // 2
    for x in range(band):
        for y in range(h):
            px[x, y] = (255, 0, 0)
    for x in range(w - band, w):
        for y in range(h):
            px[x, y] = (0, 0, 255)
    for x in range(cx0, cx1):
        for y in range(cy0, cy1):
            px[x, y] = (0, 0, 0)
    img.save(str(path))
    return str(path)


def _probe(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries",
        "stream=codec_name,codec_type,width,height,pix_fmt,r_frame_rate,"
        "sample_aspect_ratio,display_aspect_ratio,sample_rate,channels:"
        "format=duration,nb_streams",
        "-of", "json", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _video_packets(path):
    cmd = [
        "ffprobe", "-v", "error", "-count_packets",
        "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_packets",
        "-of", "csv=p=0", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip())


def _extract_frame(path, frame_index, out_png):
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", path,
        "-vf", f"select=eq(n\\,{frame_index})",
        "-frames:v", "1", out_png,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return out_png


def _black_square_box(frame_png):
    """(height, width) bounding box of the dark square in a frame."""
    import numpy as np
    from PIL import Image

    arr = np.array(Image.open(frame_png).convert("RGB"))
    mask = arr.sum(axis=2) < 60
    assert mask.any(), "dark square not found in frame"
    rows = mask.any(axis=1)
    cols = mask.any(axis=0)
    r0 = int(np.argmax(rows))
    r1 = len(rows) - int(np.argmax(rows[::-1])) - 1
    c0 = int(np.argmax(cols))
    c1 = len(cols) - int(np.argmax(cols[::-1])) - 1
    return (r1 - r0 + 1, c1 - c0 + 1)


@needs_ffmpeg
class TestStillImageClipRealFfmpeg:
    def setup_method(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory(prefix="m30_clip_")
        self.tmp = self._tmp.name
        self.source = _make_source_image(os.path.join(self.tmp, "src.png"))

    def teardown_method(self):
        self._tmp.cleanup()

    def _build(self, **kwargs):
        out = os.path.join(self.tmp, f"clip_{kwargs.get('motion', 'zoom_in')}_{kwargs.get('fit', 'contain')}.mp4")
        return StillImageClipBuilder().build(self.source, out, **kwargs)

    def test_zoom_in_produces_playable_vertical_mp4(self):
        out = self._build(duration_sec=3.0, motion="zoom_in", fit="contain")
        assert os.path.isfile(out)

        info = _probe(out)
        streams = info["streams"]
        video = [s for s in streams if s["codec_type"] == "video"][0]
        audio = [s for s in streams if s["codec_type"] == "audio"][0]

        assert video["codec_name"] == "h264"
        assert video["width"] == 1080
        assert video["height"] == 1920
        assert video["pix_fmt"] == "yuv420p"
        assert video["r_frame_rate"] == "30/1"
        assert video["sample_aspect_ratio"] == "1:1"
        assert video["display_aspect_ratio"] == "9:16"

        assert audio["codec_name"] == "aac"
        assert audio["sample_rate"] == "48000"
        assert audio["channels"] == 2

        duration = float(info["format"]["duration"])
        assert abs(duration - 3.0) < 0.15
        # exactly 90 frames at 30 fps => constant frame rate
        assert _video_packets(out) == 90

    def test_contain_preserves_whole_image(self):
        out = self._build(duration_sec=2.0, motion="none", fit="contain")
        import numpy as np
        from PIL import Image

        frame = _extract_frame(out, 0, os.path.join(self.tmp, "c.png"))
        arr = np.array(Image.open(frame).convert("RGB"))
        h, w, _ = arr.shape
        assert (w, h) == (1080, 1920)

        # both source edges are visible in the frame -> whole image kept
        left = arr[h // 2, :10, :].mean(axis=0)
        right = arr[h // 2, w - 10:, :].mean(axis=0)
        assert left[0] > 150 and left[1] < 120 and left[2] < 120  # red
        assert right[2] > 150 and right[0] < 120 and right[1] < 120  # blue

        # top strip is the blurred+darkened fill, not the raw image
        top_fill = arr[:60, :, :].mean(axis=(0, 1)).mean()
        assert top_fill < 200

    def test_cover_does_not_stretch(self):
        out = self._build(duration_sec=2.0, motion="none", fit="cover")
        import numpy as np
        from PIL import Image

        frame = _extract_frame(out, 0, os.path.join(self.tmp, "cv.png"))
        arr = np.array(Image.open(frame).convert("RGB"))
        h, w, _ = arr.shape
        assert (w, h) == (1080, 1920)

        # A 16:9 landscape source covered onto 9:16 must be center-cropped:
        # the red/blue side bands are cropped away, NOT stretched into view.
        left = arr[h // 2, :10, :].mean(axis=0)
        right = arr[h // 2, w - 10:, :].mean(axis=0)
        assert left.min() > 150  # white (source center), not red
        assert right.min() > 150  # white (source center), not blue

        # the square stays a square (uniform scale => no stretch)
        sh, sw = _black_square_box(frame)
        assert 0.9 <= sw / sh <= 1.1

    def test_contain_square_not_stretched_either(self):
        out = self._build(duration_sec=2.0, motion="none", fit="contain")
        frame = _extract_frame(out, 0, os.path.join(self.tmp, "cn.png"))
        sh, sw = _black_square_box(frame)
        assert 0.9 <= sw / sh <= 1.1

    def test_clip_has_silent_audio(self):
        out = self._build(duration_sec=2.0, motion="zoom_in", fit="cover")
        import numpy as np

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", out, "-vn", "-ac", "1", "-f", "f32le", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr
        samples = np.frombuffer(result.stdout, dtype=np.float32)
        assert len(samples) > 0
        assert float(np.abs(samples).max()) < 1e-3

    def test_zoom_in_grows_frame_content(self):
        out = self._build(
            duration_sec=2.0, motion="zoom_in", fit="contain",
            start_scale=1.0, end_scale=1.2,
        )
        first = _extract_frame(out, 0, os.path.join(self.tmp, "z0.png"))
        last = _extract_frame(out, 59, os.path.join(self.tmp, "z59.png"))
        fh0, fw0 = _black_square_box(first)
        fh1, fw1 = _black_square_box(last)
        assert fw1 > fw0 * 1.05  # visibly zoomed in by ~20% at the end

    def test_zoom_out_shrinks_frame_content(self):
        out = self._build(
            duration_sec=2.0, motion="zoom_out", fit="contain",
            start_scale=1.0, end_scale=1.2,
        )
        first = _extract_frame(out, 0, os.path.join(self.tmp, "o0.png"))
        last = _extract_frame(out, 59, os.path.join(self.tmp, "o59.png"))
        fh0, fw0 = _black_square_box(first)
        fh1, fw1 = _black_square_box(last)
        assert fw0 > fw1 * 1.05  # starts zoomed in, eases back out

    def test_none_motion_is_static(self):
        out = self._build(duration_sec=2.0, motion="none", fit="cover")
        first = _extract_frame(out, 0, os.path.join(self.tmp, "n0.png"))
        last = _extract_frame(out, 59, os.path.join(self.tmp, "n59.png"))
        _, fw0 = _black_square_box(first)
        _, fw1 = _black_square_box(last)
        assert abs(fw0 - fw1) <= 2  # no visible motion
