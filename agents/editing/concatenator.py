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
    """Concatenates multiple video clips (video stream only) into one file with transitions, freezes, and transforms."""

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
        Build FFmpeg command for trimming, transforming, freezing, and concatenating video segments with transitions.

        When keep_audio is True, the original audio streams are trimmed and
        concatenated together with the video (v=1:a=1). Otherwise the output
        is video-only (v=1:a=0), which is the default behavior.
        """
        if not segments:
            raise ValueError("No segments provided.")

        # Validate segments, transitions, freezes, and transforms first
        for i, seg in enumerate(segments):
            if seg.get("start_sec", 0.0) < 0:
                raise ValueError(f"Segment {i}: start_sec cannot be negative.")
            end = seg.get("end_sec")
            if end is not None and end <= seg.get("start_sec", 0.0):
                raise ValueError(f"Segment {i}: end_sec must be greater than start_sec.")

            trans = seg.get("transition_out")
            if trans is not None:
                if not isinstance(trans, dict):
                    raise ValueError("TRANSITION_TYPE_INVALID: transition_out must be a dictionary")
                t_type = trans.get("type", "hard_cut")
                if t_type not in ("hard_cut", "dissolve", "fade_black"):
                    raise ValueError(f"TRANSITION_TYPE_INVALID: invalid transition type '{t_type}'")

            freeze_sec = seg.get("freeze_tail_sec")
            if freeze_sec is not None:
                try:
                    f_val = float(freeze_sec)
                    if f_val < 0.0 or f_val > 1.0:
                        raise ValueError("FREEZE_DURATION_INVALID: freeze_tail_sec must be between 0.0 and 1.0")
                except ValueError as ve:
                    if "FREEZE_DURATION_INVALID" in str(ve):
                        raise
                    raise ValueError("FREEZE_DURATION_INVALID: freeze_tail_sec must be a float")

            transform = seg.get("transform")
            if transform is not None:
                if not isinstance(transform, dict):
                    raise ValueError("TRANSFORM_INVALID: transform must be a dictionary")
                if len(transform) > 0:
                    scale = transform.get("scale")
                    x = transform.get("x")
                    y = transform.get("y")
                    if scale is None or x is None or y is None:
                        raise ValueError("TRANSFORM_INVALID: transform must contain scale, x, and y")
                    try:
                        s_val = float(scale)
                        if s_val < 0.8 or s_val > 1.5:
                            raise ValueError("TRANSFORM_INVALID: scale must be between 0.8 and 1.5")
                    except ValueError as ve:
                        if "TRANSFORM_INVALID" in str(ve):
                            raise
                        raise ValueError("TRANSFORM_INVALID: scale must be a float")
                    try:
                        int(x)
                        int(y)
                    except ValueError:
                        raise ValueError("TRANSFORM_INVALID: x and y offsets must be integers")

        # Single segment with no trim, no transition, no freeze, and no transform: return empty to trigger copy
        if len(segments) == 1:
            seg = segments[0]
            start = seg.get("start_sec", 0.0)
            end = seg.get("end_sec")
            freeze_sec = seg.get("freeze_tail_sec")
            has_freeze = freeze_sec is not None and float(freeze_sec) > 0.0
            transform = seg.get("transform")
            has_transform = transform is not None and isinstance(transform, dict) and len(transform) > 0
            if start == 0.0 and end is None and not has_freeze and not has_transform:
                return []

        # Check if there are any non-trivial transitions, freezes, or transforms
        has_complex_operations = False
        for i in range(len(segments)):
            if i < len(segments) - 1:
                trans = segments[i].get("transition_out")
                if trans and isinstance(trans, dict):
                    t_type = trans.get("type", "hard_cut")
                    duration_sec = trans.get("duration_sec", 0.0)
                    if t_type in ("dissolve", "fade_black") and duration_sec > 0:
                        has_complex_operations = True
            
            freeze_sec = segments[i].get("freeze_tail_sec")
            if freeze_sec is not None and float(freeze_sec) > 0.0:
                has_complex_operations = True

            transform = segments[i].get("transform")
            if transform is not None and isinstance(transform, dict) and len(transform) > 0:
                has_complex_operations = True

        if not has_complex_operations:
            # === LEGACY PATH (Guarantees identical behavior for absent transitions, freezes, and transforms) ===
            filter_parts = []
            for i, seg in enumerate(segments):
                path = seg["path"]
                start = seg.get("start_sec", 0.0)
                end = seg.get("end_sec")

                # Video trim filter (forces SAR to 1:1 before trim)
                if start > 0 or end is not None:
                    if end is not None:
                        filter_parts.append(f"[{i}:v]setsar=1,trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")
                    else:
                        filter_parts.append(f"[{i}:v]setsar=1,trim=start={start},setpts=PTS-STARTPTS[v{i}]")
                else:
                    filter_parts.append(f"[{i}:v]setsar=1,null[v{i}]")

                # Audio trim filter (only when keeping original audio)
                if keep_audio:
                    if start > 0 or end is not None:
                        if end is not None:
                            filter_parts.append(f"[{i}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]")
                        else:
                            filter_parts.append(f"[{i}:a]atrim=start={start},asetpts=PTS-STARTPTS[a{i}]")
                    else:
                        filter_parts.append(f"[{i}:a]anull[a{i}]")

            if keep_audio:
                interleaved_labels = "".join(f"[v{i}][a{i}]" for i in range(len(segments)))
                filter_complex = (
                    ";".join(filter_parts)
                    + f";{interleaved_labels}concat=n={len(segments)}:v=1:a=1[outv][outa]"
                )
            else:
                v_labels = "".join(f"[v{i}]" for i in range(len(segments)))
                filter_complex = ";".join(filter_parts) + f";{v_labels}concat=n={len(segments)}:v=1:a=0[outv]"

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

        # === TRANSITION, FREEZE, & TRANSFORM PATH ===
        # 1. Compute duration of each trimmed segment
        segment_durations = []
        for i, seg in enumerate(segments):
            start = seg.get("start_sec", 0.0)
            end = seg.get("end_sec")
            if end is not None:
                dur = end - start
            else:
                props = get_video_properties(seg["path"], ffprobe_binary="ffprobe")
                source_dur = props.get("duration", 0.0)
                dur = source_dur - start
            dur = max(0.0, dur)

            # Account for freeze frame duration padding
            freeze_sec = seg.get("freeze_tail_sec")
            if freeze_sec is not None:
                freeze_sec = float(freeze_sec)
                dur += freeze_sec

            segment_durations.append(dur)

        filter_parts = []
        # Trim clips to [v0_trim], [v1_trim]... and [a0_trim], [a1_trim]...
        for i, seg in enumerate(segments):
            start = seg.get("start_sec", 0.0)
            end = seg.get("end_sec")

            # Video trim filter (forces SAR to 1:1 before trim)
            if start > 0 or end is not None:
                if end is not None:
                    filter_parts.append(f"[{i}:v]setsar=1,trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}_trim]")
                else:
                    filter_parts.append(f"[{i}:v]setsar=1,trim=start={start},setpts=PTS-STARTPTS[v{i}_trim]")
            else:
                filter_parts.append(f"[{i}:v]setsar=1,null[v{i}_trim]")

            if keep_audio:
                if start > 0 or end is not None:
                    if end is not None:
                        filter_parts.append(f"[{i}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}_trim]")
                    else:
                        filter_parts.append(f"[{i}:a]atrim=start={start},asetpts=PTS-STARTPTS[a{i}_trim]")
                else:
                    filter_parts.append(f"[{i}:a]anull[a{i}_trim]")

        # Apply transform if requested (composes first)
        for i, seg in enumerate(segments):
            transform = seg.get("transform")
            if transform is not None and isinstance(transform, dict) and len(transform) > 0:
                scale = float(transform.get("scale", 1.0))
                x = int(transform.get("x", 0))
                y = int(transform.get("y", 0))

                scaled_w = int(round(1080 * scale))
                scaled_h = int(round(1920 * scale))

                if scale >= 1.0:
                    crop_x = f"(in_w-1080)/2-({x})"
                    crop_y = f"(in_h-1920)/2-({y})"
                    transform_vf = f"scale={scaled_w}:{scaled_h},crop=1080:1920:{crop_x}:{crop_y}"
                else:
                    pad_x = f"(1080-in_w)/2+({x})"
                    pad_y = f"(1920-in_h)/2+({y})"
                    transform_vf = f"scale={scaled_w}:{scaled_h},pad=1080:1920:{pad_x}:{pad_y}:black"

                filter_parts.append(f"[v{i}_trim]{transform_vf}[v{i}_trans]")
            else:
                filter_parts.append(f"[v{i}_trim]null[v{i}_trans]")

        # Apply freeze frame tail padding if requested (composes after transform, before transitions)
        for i, seg in enumerate(segments):
            freeze_sec = seg.get("freeze_tail_sec")
            if freeze_sec is not None:
                freeze_sec = float(freeze_sec)
            else:
                freeze_sec = 0.0

            if freeze_sec > 0.0:
                # Video tpad clones the last frame of the transformed video stream
                filter_parts.append(f"[v{i}_trans]tpad=stop_mode=clone:stop_duration={freeze_sec}[v{i}]")
                if keep_audio:
                    # Audio silence padding using apad to keep A/V aligned
                    filter_parts.append(f"[a{i}_trim]apad=pad_dur={freeze_sec}[a{i}]")
            else:
                filter_parts.append(f"[v{i}_trans]null[v{i}]")
                if keep_audio:
                    filter_parts.append(f"[a{i}_trim]anull[a{i}]")

        current_v = "v0"
        current_v_dur = segment_durations[0]
        current_a = "a0" if keep_audio else None

        for i in range(len(segments) - 1):
            next_v = f"v{i+1}"
            next_v_dur = segment_durations[i+1]
            next_a = f"a{i+1}" if keep_audio else None

            trans = segments[i].get("transition_out") or {}
            t_type = trans.get("type", "hard_cut")
            duration_sec = float(trans.get("duration_sec", 0.0))

            if t_type in ("dissolve", "fade_black"):
                duration_sec = max(0.05, min(1.0, duration_sec))

            out_v = f"v_step_{i}"
            out_a = f"a_step_{i}" if keep_audio else None

            if t_type == "dissolve" and duration_sec > 0:
                # dissolve: use FFmpeg xfade filter (transition=fade)
                # honoring duration_sec (clamp 0.05-1.0s)
                # Duration accounting: xfade overlaps clips; total duration will shrink by the transition duration.
                offset = current_v_dur - duration_sec
                if offset < 0:
                    offset = 0.0

                filter_parts.append(f"[{current_v}][{next_v}]xfade=transition=fade:duration={duration_sec}:offset={offset}[{out_v}]")

                if keep_audio:
                    filter_parts.append(f"[{current_a}][{next_a}]acrossfade=d={duration_sec}:c1=tri:c2=tri[{out_a}]")

                current_v_dur = current_v_dur + next_v_dur - duration_sec

            elif t_type == "fade_black" and duration_sec > 0:
                # fade_black: fade-out to black at end of segment N and fade-in from black on segment N+1
                # Duration accounting: fade_black does not overlap clips; total duration is preserved.
                v_fade_out = f"v_fade_out_{i}"
                v_fade_in = f"v_fade_in_{i}"

                st_out = current_v_dur - duration_sec
                if st_out < 0:
                    st_out = 0.0

                filter_parts.append(f"[{current_v}]fade=t=out:st={st_out}:d={duration_sec}[{v_fade_out}]")
                filter_parts.append(f"[{next_v}]fade=t=in:st=0:d={duration_sec}[{v_fade_in}]")
                filter_parts.append(f"[{v_fade_out}][{v_fade_in}]concat=n=2:v=1:a=0[{out_v}]")

                if keep_audio:
                    a_fade_out = f"a_fade_out_{i}"
                    a_fade_in = f"a_fade_in_{i}"

                    filter_parts.append(f"[{current_a}]afade=t=out:st={st_out}:d={duration_sec}[{a_fade_out}]")
                    filter_parts.append(f"[{next_a}]afade=t=in:st=0:d={duration_sec}[{a_fade_in}]")
                    filter_parts.append(f"[{a_fade_out}][{a_fade_in}]concat=n=2:v=0:a=1[{out_a}]")

                current_v_dur = current_v_dur + next_v_dur

            else:
                # hard_cut: current concat behavior (no change)
                # Duration accounting: hard_cut does not overlap clips; total duration is preserved.
                filter_parts.append(f"[{current_v}][{next_v}]concat=n=2:v=1:a=0[{out_v}]")

                if keep_audio:
                    filter_parts.append(f"[{current_a}][{next_a}]concat=n=2:v=0:a=1[{out_a}]")

                current_v_dur = current_v_dur + next_v_dur

            current_v = out_v
            if keep_audio:
                current_a = out_a

        filter_complex = ";".join(filter_parts)

        cmd = [self.ffmpeg_path, "-y"]
        for seg in segments:
            cmd.extend(["-i", seg["path"]])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", f"[{current_v}]",
        ])
        if keep_audio:
            cmd.extend(["-map", f"[{current_a}]", "-c:a", "aac", "-ar", "48000", "-ac", "2"])
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            output_path,
        ])
        return cmd

    def concat_segments(self, segments: List[Dict[str, Any]], output_path: str, keep_audio: bool = False) -> str:
        """
        Concatenate video segments with optional trimming, freezing, transforming, and normalization.

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

        # Check if there are any non-trivial transitions, freezes, or transforms
        has_complex_operations = False
        for i in range(len(segments)):
            if i < len(segments) - 1:
                trans = segments[i].get("transition_out")
                if trans and isinstance(trans, dict):
                    t_type = trans.get("type", "hard_cut")
                    duration_sec = trans.get("duration_sec", 0.0)
                    if t_type in ("dissolve", "fade_black") and duration_sec > 0:
                        has_complex_operations = True
            
            freeze_sec = segments[i].get("freeze_tail_sec")
            if freeze_sec is not None and float(freeze_sec) > 0.0:
                has_complex_operations = True

            transform = segments[i].get("transform")
            if transform is not None and isinstance(transform, dict) and len(transform) > 0:
                has_complex_operations = True

        force_norm = False
        if has_complex_operations and os.environ.get("ELINA_TEST_ALLOW_MOCKS") != "true":
            force_norm = True

        # Check and normalize if heterogeneous or if non-trivial transitions/transforms require uniform formats
        if should_normalize_segments(segment_props) or force_norm:
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
