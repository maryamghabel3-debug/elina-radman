"""Frame rendering and h264/yuv420p encoding via the bundled ffmpeg binary.

Pipeline:
  scene callables -> RGB PIL frames -> rawvideo pipe -> silent mp4
  -> optional audio mux (-c:v copy -c:a aac -shortest).
No ffprobe is available; durations come from engine.audio_sync.

Memory model: frames are STREAMED into the ffmpeg pipe one at a time.
Long videos (thousands of frames) must never be buffered as a Python list —
each raw 1080x1920 RGB frame is ~6.2 MB, so a full video would exhaust RAM.
The list-based helpers remain for short clips/tests.
"""
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Tuple

import imageio_ffmpeg
from PIL import Image

from . import config, audio_sync
from .text import draw_subtitle

SceneCall = Callable[[float, float], Image.Image]
SceneSpec = Tuple[SceneCall, float]


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_scene_iter(scene_func: SceneCall, duration_seconds: float,
                      fps: int = config.FPS) -> Iterator[Image.Image]:
    """Generator version of :func:`render_scene`; yields one frame at a time."""
    n = max(1, int(round(duration_seconds * fps)))
    for i in range(n):
        yield scene_func(i / fps, duration_seconds)


def render_scene(scene_func: SceneCall, duration_seconds: float,
                 fps: int = config.FPS) -> List[Image.Image]:
    """Sample one scene into ``round(duration*fps)`` RGB frames (in memory)."""
    return list(render_scene_iter(scene_func, duration_seconds, fps))


def add_subtitles_to_frames(frames: List[Image.Image],
                            subtitles: List[dict],
                            fps: int = config.FPS) -> List[Image.Image]:
    """Burn the SRT cue active at each frame's timestamp onto that frame."""
    out: List[Image.Image] = []
    for i, frame in enumerate(frames):
        cue = audio_sync.get_active_subtitles(subtitles, i / fps)
        if cue:
            draw_subtitle(frame, cue)
        out.append(frame)
    return out


def _ffmpeg_base_cmd(out_path: Path, fps: int) -> List[str]:
    return [
        _ffmpeg(), "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{config.WIDTH}x{config.HEIGHT}",
        "-r", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", str(config.ENCODE_CRF), "-preset", config.ENCODE_PRESET,
        "-movflags", "+faststart",
        str(out_path),
    ]


def _encode_silent_iter(frame_iter: Iterator[Image.Image], out_path: Path,
                        fps: int) -> int:
    """Stream frames into ffmpeg; return the number of frames written."""
    cmd = _ffmpeg_base_cmd(out_path, fps)
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    count = 0
    try:
        for frame in frame_iter:
            if frame.size != (config.WIDTH, config.HEIGHT):
                raise ValueError(
                    f"Frame size {frame.size} != "
                    f"{(config.WIDTH, config.HEIGHT)}"
                )
            proc.stdin.write(frame.tobytes())
            count += 1
    finally:
        proc.stdin.close()
    stderr = proc.stderr.read().decode("utf-8", "replace")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg encode failed ({rc}): {stderr[-2000:]}")
    if count == 0:
        raise RuntimeError("frame stream produced zero frames")
    return count


def _encode_silent(frames: List[Image.Image], out_path: Path,
                   fps: int) -> None:
    _encode_silent_iter(iter(frames), out_path, fps)


def _full_frame_stream(scene_list: List[SceneSpec],
                       subtitles: Optional[List[dict]],
                       fps: int) -> Iterator[Image.Image]:
    """Yield every frame of every scene, burning subtitles on the fly."""
    frame_index = 0
    for scene_func, duration in scene_list:
        for frame in render_scene_iter(scene_func, duration, fps):
            if subtitles:
                cue = audio_sync.get_active_subtitles(
                    subtitles, frame_index / fps
                )
                if cue:
                    draw_subtitle(frame, cue)
            frame_index += 1
            yield frame


def render_video(scene_list: List[SceneSpec], output_path,
                 audio_path: Optional[str] = None,
                 subtitles: Optional[List[dict]] = None,
                 fps: int = config.FPS) -> None:
    """Render scenes in order, optionally burn subtitles and mux audio.

    Frames are streamed (never fully buffered), so the renderer works within
    a few hundred MB of RAM even for multi-thousand-frame videos. When
    ``audio_path`` is given its duration drives the final mux via
    ``-shortest`` so the deliverable never runs past the narration.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not scene_list:
        raise ValueError("scene_list produced zero scenes")

    silent_path = output_path.with_name(output_path.stem + ".silent.mp4")
    frame_count = _encode_silent_iter(
        _full_frame_stream(scene_list, subtitles, fps), silent_path, fps
    )
    video_seconds = frame_count / fps

    if audio_path:
        audio_seconds = audio_sync.get_audio_duration(audio_path)
        cmd = [
            _ffmpeg(), "-y",
            "-i", str(silent_path), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-shortest", str(output_path),
        ]
        proc = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg audio mux failed: {proc.stderr[-2000:]}"
            )
        silent_path.unlink(missing_ok=True)
        print(f"[render_video] frames={frame_count} video={video_seconds:.2f}s "
              f"audio={audio_seconds:.2f}s -> {output_path}")
    else:
        shutil.move(str(silent_path), str(output_path))
        print(f"[render_video] frames={frame_count} video={video_seconds:.2f}s "
              f"-> {output_path}")
