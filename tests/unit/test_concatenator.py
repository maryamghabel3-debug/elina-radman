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


# === New Per-Segment Transition Tests ===

def test_transition_absent_identical_behavior():
    """Absent transition_out or hard_cut with 0 duration should produce identical command to legacy behavior."""
    concat = VideoConcatenator()
    segments_legacy = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    segments_with_empty_trans = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "transition_out": None},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0, "transition_out": {"type": "hard_cut", "duration_sec": 0.0}},
    ]
    
    cmd_legacy = concat.build_trim_concat_command(segments_legacy, "/output/merged.mp4")
    cmd_trans = concat.build_trim_concat_command(segments_with_empty_trans, "/output/merged.mp4")
    assert cmd_legacy == cmd_trans


def test_transition_dissolve_builds_xfade(monkeypatch):
    """dissolve transition builds xfade with correct offset/duration."""
    import agents.editing.concatenator as concat_mod
    
    # Mock get_video_properties to return 10.0 seconds
    def fake_props(path, **kwargs):
        return {
            "codec": "h264", "width": 1080, "height": 1920, "fps": 30.0,
            "pix_fmt": "yuv420p", "sample_rate": None, "channels": None,
            "duration": 10.0, "has_audio": False,
        }
    monkeypatch.setattr(concat_mod, "get_video_properties", fake_props)

    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "transition_out": {"type": "dissolve", "duration_sec": 0.5}},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4")
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    
    # offset should be 5.0 - 0.5 = 4.5
    assert "xfade=transition=fade:duration=0.5:offset=4.5" in filter_str


def test_transition_fade_black_builds_fade_filters():
    """fade_black transition builds fade filters on both sides."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "transition_out": {"type": "fade_black", "duration_sec": 0.4}},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4")
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    
    # Segment 0: fade-out to black at 5.0 - 0.4 = 4.6
    assert "fade=t=out:st=4.6:d=0.4" in filter_str
    # Segment 1: fade-in from black at 0
    assert "fade=t=in:st=0:d=0.4" in filter_str


def test_transition_invalid_type_raises_error():
    """Invalid transition type raises TRANSITION_TYPE_INVALID before running FFmpeg."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "transition_out": {"type": "unsupported_transition", "duration_sec": 0.5}},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    
    with pytest.raises(ValueError, match="TRANSITION_TYPE_INVALID"):
        concat.build_trim_concat_command(segments, "/output/merged.mp4")


def test_transition_keep_audio_dissolve_includes_acrossfade(monkeypatch):
    """keep_audio=True + dissolve includes acrossfade filter."""
    import agents.editing.concatenator as concat_mod
    
    def fake_props(path, **kwargs):
        return {
            "codec": "h264", "width": 1080, "height": 1920, "fps": 30.0,
            "pix_fmt": "yuv420p", "sample_rate": 48000, "channels": 2,
            "duration": 10.0, "has_audio": True,
        }
    monkeypatch.setattr(concat_mod, "get_video_properties", fake_props)

    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "transition_out": {"type": "dissolve", "duration_sec": 0.5}},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4", keep_audio=True)
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    
    assert "acrossfade=d=0.5:c1=tri:c2=tri" in filter_str


# === New Freeze Frame Tail Tests ===

def test_freeze_absent_identical_behavior():
    """Absent freeze_tail_sec or 0.0 duration produces identical command to legacy behavior."""
    concat = VideoConcatenator()
    segments_legacy = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    segments_with_empty_freeze = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "freeze_tail_sec": None},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0, "freeze_tail_sec": 0.0},
    ]
    
    cmd_legacy = concat.build_trim_concat_command(segments_legacy, "/output/merged.mp4")
    cmd_freeze = concat.build_trim_concat_command(segments_with_empty_freeze, "/output/merged.mp4")
    assert cmd_legacy == cmd_freeze


def test_freeze_adds_tpad():
    """freeze_tail_sec=0.2 adds tpad filter with clone stop_duration."""
    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "freeze_tail_sec": 0.2},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4")
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    
    assert "tpad=stop_mode=clone:stop_duration=0.2" in filter_str


def test_freeze_dissolve_compose_order(monkeypatch):
    """freeze frame pads the clip first, then the transition is calculated from the padded clip."""
    import agents.editing.concatenator as concat_mod
    
    def fake_props(path, **kwargs):
        return {
            "codec": "h264", "width": 1080, "height": 1920, "fps": 30.0,
            "pix_fmt": "yuv420p", "sample_rate": None, "channels": None,
            "duration": 10.0, "has_audio": False,
        }
    monkeypatch.setattr(concat_mod, "get_video_properties", fake_props)

    concat = VideoConcatenator()
    # Segment 0 has duration 5.0, freeze 0.2s, dissolve 0.5s.
    # Total segment active duration = 5.0 + 0.2 = 5.2s.
    # xfade offset should be 5.2 - 0.5 = 4.7s.
    segments = [
        {
            "path": "/input/a.mp4",
            "start_sec": 0.0,
            "end_sec": 5.0,
            "freeze_tail_sec": 0.2,
            "transition_out": {"type": "dissolve", "duration_sec": 0.5}
        },
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4")
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    
    # 1. Trim happens first
    assert "trim=start=0.0:end=5.0,setpts=PTS-STARTPTS[v0_trim]" in filter_str
    # 2. tpad is applied to v0_trim producing v0
    assert "[v0_trim]tpad=stop_mode=clone:stop_duration=0.2[v0]" in filter_str
    # 3. xfade transition is applied to v0 and v1 with computed offset 4.7
    assert "[v0][v1]xfade=transition=fade:duration=0.5:offset=4.7" in filter_str


def test_freeze_keep_audio_adds_apad(monkeypatch):
    """keep_audio=True + freeze adds apad filter to pad audio with silence."""
    import agents.editing.concatenator as concat_mod
    
    def fake_props(path, **kwargs):
        return {
            "codec": "h264", "width": 1080, "height": 1920, "fps": 30.0,
            "pix_fmt": "yuv420p", "sample_rate": 48000, "channels": 2,
            "duration": 10.0, "has_audio": True,
        }
    monkeypatch.setattr(concat_mod, "get_video_properties", fake_props)

    concat = VideoConcatenator()
    segments = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "freeze_tail_sec": 0.3},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    
    cmd = concat.build_trim_concat_command(segments, "/output/merged.mp4", keep_audio=True)
    filter_idx = cmd.index("-filter_complex")
    filter_str = cmd[filter_idx + 1]
    
    assert "apad=pad_dur=0.3" in filter_str


def test_freeze_out_of_range_raises_error():
    """freeze_tail_sec out of range raises ValueError with FREEZE_DURATION_INVALID."""
    concat = VideoConcatenator()
    segments_low = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "freeze_tail_sec": -0.1},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    segments_high = [
        {"path": "/input/a.mp4", "start_sec": 0.0, "end_sec": 5.0, "freeze_tail_sec": 1.1},
        {"path": "/input/b.mp4", "start_sec": 0.0, "end_sec": 5.0},
    ]
    
    with pytest.raises(ValueError, match="FREEZE_DURATION_INVALID"):
        concat.build_trim_concat_command(segments_low, "/output/merged.mp4")
        
    with pytest.raises(ValueError, match="FREEZE_DURATION_INVALID"):
        concat.build_trim_concat_command(segments_high, "/output/merged.mp4")


