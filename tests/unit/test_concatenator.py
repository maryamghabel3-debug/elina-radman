import pytest
import os
import tempfile
from agents.editing.concatenator import VideoConcatenator

pytestmark = pytest.mark.unit


def test_single_file_returns_empty_command():
    """Single input file should return empty list (no concat needed)."""
    concat = VideoConcatenator()
    cmd = concat.build_concat_command(["/path/to/video.mp4"], "/path/to/output.mp4")
    assert cmd == []


def test_two_files_builds_correct_concat_filter():
    """Two input files should produce correct concat filter with n=2."""
    concat = VideoConcatenator()
    cmd = concat.build_concat_command(
        ["/input/a.mp4", "/input/b.mp4"],
        "/output/merged.mp4"
    )
    assert cmd[0] == "ffmpeg"
    assert "-filter_complex" in cmd
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    assert "concat=n=2:v=1:a=0[outv]" in filter_str
    assert "-i" in cmd
    assert "/input/a.mp4" in cmd
    assert "/input/b.mp4" in cmd


def test_five_files_correct_n_parameter():
    """Five input files should produce concat filter with n=5."""
    concat = VideoConcatenator()
    cmd = concat.build_concat_command(
        [f"/input/v{i}.mp4" for i in range(5)],
        "/output/merged.mp4"
    )
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    assert "concat=n=5:v=1:a=0[outv]" in filter_str


def test_empty_list_raises_value_error():
    """Empty input list should raise ValueError."""
    concat = VideoConcatenator()
    with pytest.raises(ValueError, match="No input paths"):
        concat.build_concat_command([], "/output.mp4")


# === Trim + Concat Tests ===

def test_build_trim_concat_command_includes_trim_filter():
    """Trim command should include trim=start=X filter."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 1.5, "end_sec": 10.0},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4")
    assert cmd[0] == "ffmpeg"
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    assert "trim=start=1.5:end=10.0" in filter_str
    assert "trim=start=0.0:end=5.0" in filter_str


def test_build_trim_concat_end_omitted_if_none():
    """When end_sec is None, the trim filter should omit the end parameter."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 5.0, "end_sec": None},
    ]
    cmd = concat.build_trim_concat_command(segments, "/output/trimmed.mp4")
    assert cmd[0] == "ffmpeg"
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    # Should have trim with start but no end
    assert "trim=start=5.0" in filter_str
    assert "trim=start=5.0:end=" not in filter_str


def test_two_segments_produces_concat_n2():
    """Two segments should produce concat filter with n=2."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0},
        {"path": "/input/b.mp4", "start_sec": 2.0, "end_sec": 8.0},
    ]
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4")
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    assert "concat=n=2:v=1:a=0[outv]" in filter_str


def test_single_untrimmed_segment_returns_empty():
    """Single segment with no trim (start=0, end=None) should return empty list."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": None},
    ]
    cmd = concat.build_trim_concat_command(segments, "/output/copy.mp4")
    assert cmd == []


def test_negative_start_raises_value_error():
    """Segment with negative start_sec should raise ValueError."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": -1.0, "end_sec": 5.0},
    ]
    with pytest.raises(ValueError, match="cannot be negative"):
        concat.build_trim_concat_command(segments, "/output.mp4")


def test_end_leq_start_raises_value_error():
    """Segment with end_sec <= start_sec should raise ValueError."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 5.0, "end_sec": 3.0},
    ]
    with pytest.raises(ValueError, match="end_sec must be greater than start_sec"):
        concat.build_trim_concat_command(segments, "/output.mp4")


def test_empty_segments_raises_value_error():
    """Empty segments list should raise ValueError."""
    concat = VideoConcatenator()
    with pytest.raises(ValueError, match="No segments provided"):
        concat.build_trim_concat_command([], "/output.mp4")


def test_five_segments_produces_concat_n5():
    """Five segments should produce concat filter with n=5."""
    concat = VideoConcatenator()
    segments = [
        {"path": f"/input/v{i}.mp4", "start_sec": 0.0, "end_sec": 10.0}
        for i in range(5)
    ]
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4")
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    assert "concat=n=5:v=1:a=0[outv]" in filter_str


# === Keep Original Audio Tests ===

def test_build_trim_concat_command_keep_audio():
    """keep_audio=True must concat audio too (v=1:a=1, [outa]) with atrim filters."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 1.5, "end_sec": 10.0},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4", keep_audio=True)
    assert cmd[0] == "ffmpeg"
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    assert "atrim=start=1.5:end=10.0,asetpts=PTS-STARTPTS" in filter_str
    assert "atrim=start=0.0:end=5.0,asetpts=PTS-STARTPTS" in filter_str
    # concat expects interleaved per-segment stream order: [v0][a0][v1][a1]
    assert "concat=n=2:v=1:a=1[outv][outa]" in filter_str
    assert "[v0][a0][v1][a1]concat=n=2:v=1:a=1" in filter_str
    # Audio stream mapped and re-encoded to a uniform profile
    assert ["-map", "[outv]", "-map", "[outa]"] in [cmd[i:i+4] for i in range(len(cmd) - 3)]
    assert "-c:a" in cmd and "aac" in cmd


def test_build_trim_concat_command_default_drops_audio():
    """Default keep_audio=False must keep v=1:a=0 behavior (no [outa])."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4")
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    assert "concat=n=1:v=1:a=0[outv]" in filter_str
    assert "[outa]" not in cmd


def test_concat_segments_keep_audio_falls_back_without_audio_streams(monkeypatch):
    """keep_audio=True must fall back to video-only when no segment has audio."""
    import agents.editing.concatenator as concat_mod
    from unittest.mock import MagicMock, patch

    def fake_props(path):
        return {
            "codec": "h264", "width": 1080, "height": 1920, "fps": 30.0,
            "pix_fmt": "yuv420p", "sample_rate": None, "channels": None,
            "has_audio": False,
        }

    monkeypatch.setattr(concat_mod, "get_video_properties", fake_props)

    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stderr = ""

    with patch("subprocess.run", return_value=mock_run) as mock_subprocess:
        concat = VideoConcatenator()
        concat.concat_segments(
            [
                {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 2.0},
                {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 2.0},
            ],
            "/output/merged.mp4",
            keep_audio=True,
        )
        cmd = mock_subprocess.call_args[0][0]
        filter_str = cmd[cmd.index("-filter_complex") + 1]
        assert "v=1:a=0[outv]" in filter_str
        assert "outa" not in filter_str
