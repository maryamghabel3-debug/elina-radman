import os
import shutil
import subprocess
import logging
import json
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_video_properties(path: str, ffprobe_binary: str = "ffprobe") -> dict:
    """
    Probe video properties using ffprobe.
    """
    properties = {
        "codec": None,
        "width": None,
        "height": None,
        "fps": 30.0,
        "pix_fmt": None,
        "sample_rate": None,
        "channels": None,
        "duration": 0.0,
        "has_audio": False
    }
    if not path or not os.path.exists(path):
        return properties

    try:
        cmd = [
            ffprobe_binary,
            "-v", "error",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels,codec_type,duration:format=duration",
            "-of", "json",
            path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            info = json.loads(result.stdout)
            streams = info.get("streams", [])
            for stream in streams:
                if stream.get("codec_type") == "video":
                    properties["codec"] = stream.get("codec_name")
                    properties["width"] = stream.get("width")
                    properties["height"] = stream.get("height")
                    properties["pix_fmt"] = stream.get("pix_fmt")
                    if stream.get("duration"):
                        try:
                            properties["duration"] = float(stream["duration"])
                        except ValueError:
                            pass
                    r_frame_rate = stream.get("r_frame_rate", "30/1")
                    if "/" in r_frame_rate:
                        try:
                            num, den = map(float, r_frame_rate.split("/"))
                            properties["fps"] = num / den if den != 0 else 30.0
                        except ValueError:
                            properties["fps"] = 30.0
                    else:
                        try:
                            properties["fps"] = float(r_frame_rate)
                        except ValueError:
                            properties["fps"] = 30.0
                elif stream.get("codec_type") == "audio":
                    properties["has_audio"] = True
                    if stream.get("sample_rate"):
                        try:
                            properties["sample_rate"] = int(stream["sample_rate"])
                        except ValueError:
                            pass
                    if stream.get("channels"):
                        try:
                            properties["channels"] = int(stream["channels"])
                        except ValueError:
                            pass

            fmt = info.get("format", {})
            if fmt.get("duration"):
                try:
                    properties["duration"] = float(fmt["duration"])
                except ValueError:
                    pass

    except Exception as e:
        logger.warning(f"Failed to probe video properties for {path}: {e}")

    return properties


def should_normalize_segments(segment_props: List[dict]) -> bool:
    """
    Check if segments have heterogeneous formats or properties.
    """
    if os.environ.get("ELINA_TEST_ALLOW_MOCKS") == "true":
        return False

    if not segment_props:
        return False

    first = segment_props[0]
    for p in segment_props:
        if p["width"] != first["width"] or p["height"] != first["height"]:
            logger.info("Heterogeneous inputs: differing resolution.")
            return True
        if abs(p["fps"] - first["fps"]) > 0.1:
            logger.info("Heterogeneous inputs: differing frame rate.")
            return True
        if p["pix_fmt"] != first["pix_fmt"]:
            logger.info("Heterogeneous inputs: differing pixel format.")
            return True
        if p["codec"] != first["codec"]:
            logger.info("Heterogeneous inputs: differing video codec.")
            return True
        if p["has_audio"] != first["has_audio"]:
            logger.info("Heterogeneous inputs: some have audio, some do not.")
            return True
        if p["has_audio"]:
            if p["sample_rate"] != first["sample_rate"] or p["channels"] != first["channels"]:
                logger.info("Heterogeneous inputs: differing audio sample rate or channels.")
                return True

    for p in segment_props:
        if p["width"] != 1080 or p["height"] != 1920:
            logger.info("Non-canonical resolution detected. Will normalize.")
            return True

    return False


def normalize_segment(input_path: str, output_path: str, props: dict, ffmpeg_path: str = "ffmpeg") -> None:
    """
    Normalize video segment to canonical 1080x1920, h264, 30fps profile, adding silent audio if needed.
    """
    cmd = [ffmpeg_path, "-y"]

    cmd.extend(["-i", input_path])

    if not props.get("has_audio"):
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])

    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"

    cmd.extend([
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
    ])

    if props.get("has_audio"):
        cmd.extend([
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
        ])
    else:
        cmd.extend([
            "-c:a", "aac",
            "-shortest"
        ])

    cmd.append(output_path)

    logger.info(f"Executing normalization command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        err_tail = result.stderr[-2000:] if result.stderr else ""
        raise RuntimeError(f"FFmpeg segment normalization failed: {err_tail}")


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
        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            err_tail = result.stderr[-2000:] if result.stderr else ""
            raise RuntimeError(f"FFmpeg concat failed: {err_tail}")
        return output_path

    def build_trim_concat_command(self, segments: List[Dict[str, Any]], output_path: str, keep_audio: bool = False) -> List[str]:
        """
        Build FFmpeg command for trimming and concatenating video segments.

        When keep_audio is True, the original audio streams are trimmed and
        concatenated together with the video (v=1:a=1). Otherwise the output
        is video-only (v=1:a=0), which is the default behavior.
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
            end = seg.get("end_sec")

            # Video trim filter
            if start > 0 or end is not None:
                if end is not None:
                    filter_parts.append(f"[{i}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")
                else:
                    filter_parts.append(f"[{i}:v]trim=start={start},setpts=PTS-STARTPTS[v{i}]")
            else:
                filter_parts.append(f"[{i}:v]null[v{i}]")

            # Audio trim filter (only when keeping original audio)
            if keep_audio:
                if start > 0 or end is not None:
                    if end is not None:
                        filter_parts.append(f"[{i}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]")
                    else:
                        filter_parts.append(f"[{i}:a]atrim=start={start},asetpts=PTS-STARTPTS[a{i}]")
                else:
                    filter_parts.append(f"[{i}:a]anull[a{i}]")

        # Create concat filter. With keep_audio, concat expects the segment
        # streams interleaved per segment: [v0][a0][v1][a1]... (verified against
        # ffmpeg 7; grouped [v0][v1][a0][a1] fails with a media-type mismatch).
        if keep_audio:
            interleaved_labels = "".join(f"[v{i}][a{i}]" for i in range(len(segments)))
            filter_complex = (
                ";".join(filter_parts)
                + f";{interleaved_labels}concat=n={len(segments)}:v=1:a=1[outv][outa]"
            )
        else:
            v_labels = "".join(f"[v{i}]" for i in range(len(segments)))
            filter_complex = ";".join(filter_parts) + f";{v_labels}concat=n={len(segments)}:v=1:a=0[outv]"

        # Build command
        cmd = [self.ffmpeg_path, "-y"]
        for seg in segments:
            cmd.extend(["-i", seg["path"]])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
        ])
        if keep_audio:
            cmd.extend(["-map", "[outa]", "-c:a", "aac", "-ar", "48000", "-ac", "2"])
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            output_path,
        ])
        return cmd

    def concat_segments(self, segments: List[Dict[str, Any]], output_path: str, keep_audio: bool = False) -> str:
        """
        Concatenate video segments with optional trimming and normalization.

        keep_audio keeps the original audio streams in the concatenated output
        (used when the user's plan says to keep the original shot audio). Falls
        back to video-only when no segment actually carries an audio stream.
        """
        if not segments:
            raise ValueError("No segments provided.")

        # Probe all segments and log their properties
        segment_props = []
        normalized = False
        for i, seg in enumerate(segments):
            props = get_video_properties(seg["path"])
            logger.info(f"Segment {i} properties: {props}")
            segment_props.append(props)

        # Check and normalize if heterogeneous
        if should_normalize_segments(segment_props):
            logger.info("Normalizing segments to canonical profile before concatenation...")
            normalized = True
            normalized_segments = []
            for i, seg in enumerate(segments):
                dir_name = os.path.dirname(seg["path"])
                norm_path = os.path.join(dir_name, f"normalized_clip_{i}.mp4")
                normalize_segment(seg["path"], norm_path, segment_props[i], ffmpeg_path=self.ffmpeg_path)

                new_seg = dict(seg)
                new_seg["path"] = norm_path
                normalized_segments.append(new_seg)
            segments = normalized_segments

        # keep_audio requires an audio stream on every segment. Normalization
        # always injects one (silent track when missing); otherwise verify here.
        if keep_audio and not normalized:
            if not all(p.get("has_audio", False) for p in segment_props):
                logger.info("keep_audio requested but not every segment has audio; falling back to video-only concat")
                keep_audio = False

        cmd = self.build_trim_concat_command(segments, output_path, keep_audio=keep_audio)

        # No trim needed, single segment - just copy
        if not cmd:
            shutil.copy2(segments[0]["path"], output_path)
            return output_path

        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            err_tail = result.stderr[-2000:] if result.stderr else ""
            raise RuntimeError(f"FFmpeg trim+concat failed: {err_tail}")
        return output_path
