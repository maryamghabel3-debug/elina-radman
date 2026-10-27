"""Frame rendering and h264/yuv420p encoding via the bundled ffmpeg binary.

Pipeline:
  scene callables -> RGB PIL frames -> rawvideo pipe -> silent mp4
  -> optional audio mux (-c:v copy -c:a aac -shortest).
No ffprobe is available; durations come from engine.audio_sync.
"""
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import imageio_ffmpeg
from PIL import Image

from . import config, audio_sync
from .text import draw_subtitle

SceneCall = Callable[[float, float], Image.Image]
SceneSpec = Tuple[SceneCall, float]


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_scene(scene_func: SceneCall, duration_seconds: float,
                 fps: int = config.FPS) -> List[Image.Image]:
    """Sample one scene into ``round(duration*fps)`` RGB frames."""
    n = max(1, int(round(duration_seconds * fps)))
    return [scene_func(i / fps, duration_seconds) for i in range(n)]


def add_subtitles_to_frames(frames: List[Image.Image],
                            subtitles: List[dict],
                            fps: int = config.FPS) -> List[Image.Image]:
    """Burn the SRT cue active at each frame's timestamp onto that frame."""
    out: List[Image.Image] = []
    for i, frame in enumerate(frames):
        t = i / fps
        cue = audio_sync.get_active_subtitles(subtitles, t)
        if cue:
            draw_subtitle(frame, cue)
        out.append(frame)
    return out


def _encode_silent(frames: List[Image.Image], out_path: Path,
                   fps: int) -> None:
    cmd = [
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
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        for frame in frames:
            if frame.size != (config.WIDTH, config.HEIGHT):
                raise ValueError(
                    f"Frame size {frame.size} != "
                    f"{(config.WIDTH, config.HEIGHT)}"
                )
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    stderr = proc.stderr.read().decode("utf-8", "replace")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg encode failed ({rc}): {stderr[-2000:]}")


def render_video(scene_list: List[SceneSpec], output_path,
                 audio_path: Optional[str] = None,
                 subtitles: Optional[List[dict]] = None,
                 fps: int = config.FPS) -> None:
    """Render scenes in order, optionally burn subtitles and mux audio.

    When ``audio_path`` is given its duration is logged and the final mux
    uses ``-shortest`` so the deliverable never runs past the narration.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frames: List[Image.Image] = []
    for scene_func, duration in scene_list:
        frames.extend(render_scene(scene_func, duration, fps))
    if not frames:
        raise ValueError("scene_list produced zero frames")

    if subtitles:
        frames = add_subtitles_to_frames(frames, subtitles, fps)

    silent_path = output_path.with_name(output_path.stem + ".silent.mp4")
    _encode_silent(frames, silent_path, fps)

    video_seconds = len(frames) / fps
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
        print(f"[render_video] frames={len(frames)} video={video_seconds:.2f}s "
              f"audio={audio_seconds:.2f}s -> {output_path}")
    else:
        shutil.move(str(silent_path), str(output_path))
        print(f"[render_video] frames={len(frames)} video={video_seconds:.2f}s "
              f"-> {output_path}")
