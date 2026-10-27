"""End-to-end smoke test for the psyche-studio motion engine.

Builds (locally, no AI assets):
  1. 6 s of silence as test_audio.mp3 (ffmpeg lavfi anullsrc)
  2. a 3-cue Persian SRT covering the 6 seconds
  3. a dark navy->indigo gradient background (Pillow/numpy)
then renders scene_hook (3 s) + scene_split (3 s) with burned subtitles and
muxed audio into motion_test.mp4 (1080x1920, 30 fps, h264/yuv420p, AAC).

Run:  psyche-studio/.venv/bin/python psyche-studio/probes/test_motion.py
"""
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

# Make the psyche-studio package root importable.
STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO))

import imageio_ffmpeg  # noqa: E402

from engine import audio_sync, config, scenes, video  # noqa: E402

PROBES = STUDIO / "probes"
AUDIO = PROBES / "test_audio.mp3"
SRT = PROBES / "test_subs.srt"
BG = PROBES / "test_bg.jpg"
OUT = PROBES / "motion_test.mp4"

results = []


def report(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# --- 1. Six seconds of silence ---------------------------------------------
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
silence_cmd = [
    ffmpeg, "-y",
    "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
    "-t", "6", "-c:a", "libmp3lame", "-q:a", "4", str(AUDIO),
]
proc = subprocess.run(silence_cmd, stdout=subprocess.DEVNULL,
                      stderr=subprocess.PIPE, text=True)
report("silence audio created", proc.returncode == 0 and AUDIO.exists(),
       f"{AUDIO.name} {AUDIO.stat().st_size} bytes" if AUDIO.exists()
       else proc.stderr[-300:])

# --- 2. Persian SRT with three cues ----------------------------------------
srt_text = """1
00:00:00,500 --> 00:00:02,000
ذهن شما کارهای نیمه‌تمام را فراموش نمی‌کند.

2
00:00:02,000 --> 00:00:04,000
این یعنی مغز همچنان منتظر پایان است.

3
00:00:04,000 --> 00:00:05,800
راه‌حل: برنامه مشخص، در زمان مشخص.
"""
SRT.write_text(srt_text, encoding="utf-8")
subtitles = audio_sync.parse_srt(SRT)
report("SRT parsed", len(subtitles) == 3,
       f"{len(subtitles)} cues, first starts at {subtitles[0]['start']}s")
report("subtitle lookup",
       audio_sync.get_active_subtitles(subtitles, 3.0) is not None
       and audio_sync.get_active_subtitles(subtitles, 5.9) is None,
       "cue active at t=3.0, none at t=5.9")

# --- 3. Gradient background (no AI image) ----------------------------------
top = np.array(config.COLORS["background"], dtype=np.float32)
bottom = np.array(config.COLORS["background_alt"], dtype=np.float32)
gradient = np.zeros((config.HEIGHT, config.WIDTH, 3), dtype=np.uint8)
for y in range(config.HEIGHT):
    k = y / (config.HEIGHT - 1)
    # ease the gradient slightly for a richer backdrop
    k = k * k * (3 - 2 * k)
    gradient[y, :, :] = (top * (1 - k) + bottom * k).astype(np.uint8)
Image.fromarray(gradient, "RGB").save(BG, quality=92)
report("gradient background", BG.exists() and BG.stat().st_size > 0,
       f"{BG.name} {BG.stat().st_size // 1024} KiB, "
       f"{config.WIDTH}x{config.HEIGHT}")

# --- 4. Render two scenes with audio + subtitles ---------------------------
t0 = time.perf_counter()
hook = lambda t, duration: scenes.scene_hook(
    BG, "چرا یک پیام کوتاه، تمام ذهنت را درگیر می‌کند؟", t, duration
)
split = lambda t, duration: scenes.scene_split(
    BG,
    "واقعیت", "او فقط کلمه «باشه» را نوشت؛ هیچ اطلاعات دیگری نیست.",
    "تفسیر", "ذهنت آن را نشانه ناراحتی یا قهر فرض می‌کند.",
    t, duration,
)
video.render_video(
    [(hook, 3.0), (split, 3.0)],
    OUT,
    audio_path=str(AUDIO),
    subtitles=subtitles,
)
render_seconds = time.perf_counter() - t0

# --- 5/6. Verification ------------------------------------------------------
exists = OUT.exists() and OUT.stat().st_size > 0
report("output file", exists,
       f"{OUT.name} {OUT.stat().st_size // 1024} KiB" if exists else "missing")

duration = audio_sync.get_audio_duration(OUT)
report("duration ~6s", abs(duration - 6.0) < 0.5,
       f"measured {duration:.2f} s")

banner = subprocess.run(
    [ffmpeg, "-hide_banner", "-i", str(OUT)],
    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
).stderr
report("resolution 1080x1920", "1080x1920" in banner,
       "1080x1920 found in ffmpeg banner" if "1080x1920" in banner
       else "resolution missing")
report("h264 + yuv420p", "h264" in banner and "yuv420p" in banner,
       "h264/yuv420p present" if ("h264" in banner and "yuv420p" in banner)
       else "codec/pixfmt missing")
report("AAC audio track", "aac" in banner.lower(),
       "aac present" if "aac" in banner.lower() else "audio missing")
report("render wall time", render_seconds < 120,
       f"{render_seconds:.1f}s for 180 frames "
       f"({render_seconds / 180 * 1000:.0f} ms/frame incl. encode)")

print("\n--- Files created ---")
for p in (AUDIO, SRT, BG, OUT):
    print(f"{p}  ({p.stat().st_size} bytes)")

failed = [name for name, ok, _ in results if not ok]
print(f"\nSUMMARY: {len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED:", ", ".join(failed))
    sys.exit(1)
