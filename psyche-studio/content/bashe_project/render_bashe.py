"""Project 001 (باشه) — full end-to-end render orchestration.

Pipeline:
  1. concatenate the seven extracted scene MP3s with GAP seconds of silence
     between them into full_voice.mp3 (ffmpeg concat demuxer, stream copy);
  2. measure each scene's duration and compute global scene start times;
  3. build engine scene callables (lambdas with the (t, duration) signature;
     functools.partial breaks that signature);
  4. build globally shifted subtitles from subtitles_gen and burn them via
     engine.video.add_subtitles_to_frames (called inside render_video);
  5. encode 1080x1920 h264/yuv420p at CRF 20 and mux the narration AAC.

Run from psyche-studio/:  .venv/bin/python content/bashe_project/render_bashe.py
"""
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg

# Make psyche-studio/ importable.
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO))

from engine import audio_sync, config, scenes, video  # noqa: E402
from content.bashe_project.scenes_config import GAP, IMAGE_DIR, SCENES  # noqa: E402
from content.bashe_project.subtitles_gen import build_subtitles  # noqa: E404

VOICE_DIR = STUDIO / "content" / "my_voice"
WORK_DIR = STUDIO / "content" / "bashe_project"
OUTPUT = WORK_DIR / "bashe_v1.mp4"
FULL_VOICE = WORK_DIR / "full_voice.mp3"

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-1500:]}")


def step1_concat_audio(durations):
    """Build full_voice.mp3: voice, 0.35s silence, voice, ..., voice.

    Uses the concat *filter* with a single PCM anullsrc segment (exact
    duration, unlike an MP3 gap whose encoder padding adds ~40ms each).
    Re-encoded once, uniformly, to mono 44.1kHz 128k MP3.
    """
    cmd = [FFMPEG, "-y"]
    for i in range(1, 8):
        cmd += ["-i", str(VOICE_DIR / f"scene_{i:02d}.mp3")]
    # Input 7: exact PCM silence, reused for all six inter-scene gaps.
    cmd += ["-f", "lavfi", "-t", str(GAP),
            "-i", "anullsrc=channel_layout=mono:sample_rate=44100"]
    chain = "".join(
        f"[{i - 1}:a][7:a]" if i < 7 else f"[{i - 1}:a]" for i in range(1, 8)
    )
    cmd += [
        "-filter_complex", f"{chain}concat=n=13:v=0:a=1[out]",
        "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "128k",
        str(FULL_VOICE),
    ]
    run(cmd)


def build_scene_callable(cfg):
    bg = str(IMAGE_DIR / cfg["bg"])
    kind = cfg["type"]
    if kind == "hook":
        return lambda t, duration: scenes.scene_hook(
            bg, cfg["headline"], t, duration)
    if kind == "bubbles":
        return lambda t, duration: scenes.scene_bubbles(
            bg, cfg["center_text"], cfg["bubbles"], t, duration)
    if kind == "split":
        return lambda t, duration: scenes.scene_split(
            bg, cfg["left_label"], cfg["left_text"],
            cfg["right_label"], cfg["right_text"], t, duration)
    if kind == "cards":
        return lambda t, duration: scenes.scene_cards(
            bg, cfg["cards"], t, duration)
    if kind == "outro":
        return lambda t, duration: scenes.scene_outro(
            bg, cfg["closing_text"], t, duration)
    raise ValueError(f"unknown scene type: {kind}")


def main():
    t0 = time.perf_counter()

    # --- Step 0: measured narration durations ------------------------------
    durations = {
        cfg["scene"]: audio_sync.get_audio_duration(
            VOICE_DIR / f"scene_{cfg['scene']:02d}.mp3")
        for cfg in SCENES
    }
    print("Scene audio durations:")
    for i, d in durations.items():
        print(f"  scene_{i:02d}: {d:.3f}s")

    # --- Step 1: concatenated narration -------------------------------------
    step1_concat_audio(durations)
    total_audio = audio_sync.get_audio_duration(FULL_VOICE)
    expected = sum(durations.values()) + GAP * 6
    print(f"full_voice.mp3: {total_audio:.3f}s "
          f"(expected {expected:.3f}s = audio + 6 gaps)")

    # --- Steps 2-3: scene list; gap after scenes 1..6, none after the last -
    scene_list = []
    global_start = 0.0
    prior_seconds = 0.0
    n_scenes = len(SCENES)
    for cfg in SCENES:
        i = cfg["scene"]
        is_last = i == n_scenes
        scene_seconds = durations[i] + (0.0 if is_last else GAP)
        if is_last:
            # Safety: hold the outro long enough that the video stream always
            # covers the full narration, regardless of encoder padding.
            scene_seconds = max(
                scene_seconds,
                total_audio - prior_seconds + 1.0 / config.FPS,
            )
        scene_list.append((build_scene_callable(cfg), scene_seconds))
        print(f"  scene_{i:02d} [{cfg['type']:<8}] "
              f"start={global_start:7.3f}s  render={scene_seconds:6.3f}s  "
              f"frames={round(scene_seconds * config.FPS)}")
        global_start += scene_seconds
        prior_seconds += scene_seconds

    # --- Step 5: globally shifted subtitles ---------------------------------
    subtitles = build_subtitles(durations, GAP)
    print(f"subtitle cues: {len(subtitles)}")

    # --- Steps 4/7: render + burn subtitles + mux, CRF 20 -------------------
    config.ENCODE_CRF = 20  # runtime override; engine code untouched
    video.render_video(scene_list, OUTPUT,
                       audio_path=str(FULL_VOICE), subtitles=subtitles)

    elapsed = time.perf_counter() - t0
    final_duration = audio_sync.get_audio_duration(OUTPUT)
    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"\nDONE in {elapsed:.1f}s")
    print(f"output: {OUTPUT}")
    print(f"duration: {final_duration:.3f}s | size: {size_mb:.2f} MiB")


if __name__ == "__main__":
    main()
