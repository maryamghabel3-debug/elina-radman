import os
import shutil
import subprocess
import logging
from typing import List

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
