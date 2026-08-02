import os
import shutil
import subprocess
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class VideoConcatenator:
    """Concatenates multiple video clips (video stream only) into one file."""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def build_concat_command(self, input_paths: List[str], output_path: str) -> List[str]:
        if not input_paths:
            raise ValueError("No input paths provided.")
        if len(input_paths) == 1:
            return []

        # Build concat filter for video streams (v:1, a=0 because we add audio later)
        filter_complex = "".join(f"[{i}:v]" for i in range(len(input_paths)))
        filter_complex += f"concat=n={len(input_paths)}:v=1:a=0[outv]"

        cmd = [self.ffmpeg_path, "-y"]
        for p in input_paths:
            cmd.extend(["-i", p])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            output_path,
        ])
        return cmd

    def concat_videos(self, input_paths: List[str], output_path: str) -> str:
        if not input_paths:
            raise ValueError("No input paths provided.")
        if len(input_paths) == 1:
            shutil.copy2(input_paths[0], output_path)
            return output_path

        cmd = self.build_concat_command(input_paths, output_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed: {result.stderr[:300]}")
        return output_path

    def build_trim_concat_command(self, segments: List[Dict[str, Any]], output_path: str) -> List[str]:
        """
        Build FFmpeg command for trimming and concatenating video segments.

        Args:
            segments: List of dicts with keys: path, start_sec, end_sec
                - path: str - local file path
                - start_sec: float - trim start time (default 0.0)
                - end_sec: float or None - trim end time (None = no end trim)

        Returns:
            List[str] - FFmpeg command arguments
        """
        if not segments:
            raise ValueError("No segments provided.")

        # Validate segments
        for i, seg in enumerate(segments):
            if seg.get("start_sec", 0.0) < 0:
                raise ValueError(f"Segment {i}: start_sec cannot be negative.")
            end = seg.get("end_sec")
            if end is not None and end <= seg.get("start_sec", 0.0):
                raise ValueError(f"Segment {i}: end_sec must be greater than start_sec.")

        # Single segment with no trim: return empty to trigger copy
        if len(segments) == 1:
            seg = segments[0]
            start = seg.get("start_sec", 0.0)
            end = seg.get("end_sec")
            if start == 0.0 and end is None:
                return []

        # Build trim+concat filter graph
        filter_parts = []
        for i, seg in enumerate(segments):
            path = seg["path"]
            start = seg.get("start_sec", 0.0)

            # Trim filter
            if start > 0 or seg.get("end_sec") is not None:
                end = seg.get("end_sec")
                if end is not None:
                    filter_parts.append(f"[{i}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")
                else:
                    filter_parts.append(f"[{i}:v]trim=start={start},setpts=PTS-STARTPTS[v{i}]")
            else:
                filter_parts.append(f"[{i}:v][v{i}]")

        # Create concat filter
        v_labels = "".join(f"[v{i}]" for i in range(len(segments)))
        filter_complex = ";".join(filter_parts) + f";{v_labels}concat=n={len(segments)}:v=1:a=0[outv]"

        # Build command
        cmd = [self.ffmpeg_path, "-y"]
        for seg in segments:
            cmd.extend(["-i", seg["path"]])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            output_path,
        ])
        return cmd

    def concat_segments(self, segments: List[Dict[str, Any]], output_path: str) -> str:
        """
        Concatenate video segments with optional trimming.

        Args:
            segments: List of dicts with keys: path, start_sec, end_sec
            output_path: str - output file path

        Returns:
            str - output_path on success
        """
        if not segments:
            raise ValueError("No segments provided.")

        cmd = self.build_trim_concat_command(segments, output_path)

        # No trim needed, single segment - just copy
        if not cmd:
            shutil.copy2(segments[0]["path"], output_path)
            return output_path

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg trim+concat failed: {result.stderr[:300]}")
        return output_path
