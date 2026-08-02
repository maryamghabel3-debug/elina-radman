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
