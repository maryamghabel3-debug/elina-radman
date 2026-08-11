import os
import pytest
import subprocess
from unittest.mock import MagicMock, patch, ANY

from agents.editing.concatenator import (
    get_video_properties,
    should_normalize_segments,
    normalize_segment,
    VideoConcatenator
)
from scripts.supabase_queue_hygiene import main as run_queue_hygiene

pytestmark = pytest.mark.unit


# 1. stderr tail capture
def test_stderr_tail_capture():
    # Long mock stderr with version banner at top and actual error at the very end
    long_stderr = "ffmpeg version 6.1.1 Copyright... " + "noise " * 500 + " [ERROR] Cannot open output file path/out.mp4"

    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stderr = long_stderr

    with patch("subprocess.run", return_value=mock_res):
        concat = VideoConcatenator()
        with pytest.raises(RuntimeError) as exc_info:
            concat.concat_videos(["clip1.mp4", "clip2.mp4"], "out.mp4")

        err_msg = str(exc_info.value)
        assert "[ERROR] Cannot open output" in err_msg
        assert "ffmpeg version" not in err_msg


# 2. heterogeneous-input normalization decision
def test_heterogeneous_input_normalization_decision():
    with patch.dict(os.environ, {"ELINA_TEST_ALLOW_MOCKS": "false"}):
        # Test identical canonical properties -> no normalization needed
        props_canonical = [
            {"codec": "h264", "width": 1080, "height": 1920, "fps": 30.0, "pix_fmt": "yuv420p", "sample_rate": 48000, "channels": 2, "has_audio": True},
            {"codec": "h264", "width": 1080, "height": 1920, "fps": 30.0, "pix_fmt": "yuv420p", "sample_rate": 48000, "channels": 2, "has_audio": True}
        ]
        assert should_normalize_segments(props_canonical) is False

        # Differing resolutions -> should normalize
        props_diff_res = [
            {"codec": "h264", "width": 1080, "height": 1920, "fps": 30.0, "pix_fmt": "yuv420p", "sample_rate": 48000, "channels": 2, "has_audio": True},
            {"codec": "h264", "width": 720, "height": 1280, "fps": 30.0, "pix_fmt": "yuv420p", "sample_rate": 48000, "channels": 2, "has_audio": True}
        ]
        assert should_normalize_segments(props_diff_res) is True

        # Differing fps -> should normalize
        props_diff_fps = [
            {"codec": "h264", "width": 1080, "height": 1920, "fps": 30.0, "pix_fmt": "yuv420p", "sample_rate": 48000, "channels": 2, "has_audio": True},
            {"codec": "h264", "width": 1080, "height": 1920, "fps": 25.0, "pix_fmt": "yuv420p", "sample_rate": 48000, "channels": 2, "has_audio": True}
        ]
        assert should_normalize_segments(props_diff_fps) is True


# 3. silent-audio injection
def test_silent_audio_injection():
    # Segment with NO audio stream (has_audio = False)
    props_no_audio = {"codec": "h264", "width": 1080, "height": 1920, "fps": 30.0, "pix_fmt": "yuv420p", "has_audio": False}

    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stderr = ""

    with patch("subprocess.run", return_value=mock_run) as mock_subprocess_run:
        normalize_segment("in.mp4", "out.mp4", props_no_audio)

        # Verify anullsrc and -shortest exist in the executed command line!
        mock_subprocess_run.assert_called_once()
        cmd = mock_subprocess_run.call_args[0][0]
        assert "anullsrc=channel_layout=stereo:sample_rate=48000" in cmd
        assert "-shortest" in cmd


# 4. orphaned-job detection
def test_orphaned_job_detection():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.in_.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query

    # 1. Mock active render jobs (stale/ghost jobs)
    mock_jobs_result = MagicMock()
    mock_jobs_result.data = [
        {"id": "job-orphan-1", "content_id": "ELN-BUNDLE-ORPHAN"},
        {"id": "job-terminal-2", "content_id": "ELN-BUNDLE-TERMINAL"}
    ]
    mock_query.execute.return_value = mock_jobs_result

    # 2. Mock content item lookups:
    # ELN-BUNDLE-ORPHAN lookup returns None (missing content!)
    # ELN-BUNDLE-TERMINAL lookup returns a completed/published item (terminal status!)
    def get_content_side_effect(cid):
        if cid == "ELN-BUNDLE-TERMINAL":
            return {"id": "item-terminal", "custom_id": "ELN-BUNDLE-TERMINAL", "status": "READY_FOR_REVIEW"}
        return None
    mock_db.get_content_by_custom_id.side_effect = get_content_side_effect

    with patch("scripts.supabase_queue_hygiene.ElinaDB", lambda: mock_db):
        run_queue_hygiene()

        # Check that both jobs are marked as FAILED with ORPHANED_JOB_CONTENT_NOT_ACTIVE
        mock_query.update.assert_any_call({
            "status": "FAILED",
            "error_message": "ORPHANED_JOB_CONTENT_NOT_ACTIVE"
        })
        mock_query.eq.assert_any_call("id", "job-orphan-1")
        mock_query.eq.assert_any_call("id", "job-terminal-2")
