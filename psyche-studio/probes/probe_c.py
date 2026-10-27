"""Probe C — video encode via the imageio-ffmpeg bundled binary.

Builds 60 RGB frames (1080x1920, 30 fps -> 2 s) with a moving rectangle and
pipes raw video into ffmpeg: libx264, yuv420p, CRF 18.
Reports the ffmpeg binary path, output size, and ffprobe availability.
"""
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe_c.mp4"

W, H, FPS, N = 1080, 1920, 30, 60
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

cmd = [
    ffmpeg_exe, "-y",
    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
    "-i", "-",
    "-an",
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
    str(OUT),
]

proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

rng = np.random.default_rng(7)
for i in range(N):
    # subtle animated background so the encoder has real motion to compress
    base = np.zeros((H, W, 3), dtype=np.uint8)
    base[..., 0] = 30 + int(20 * np.sin(i / 10))
    base[..., 2] = 60 + int(25 * np.cos(i / 8))
    img = Image.fromarray(base, "RGB")
    draw = ImageDraw.Draw(img)
    x = 120 + i * 12  # rectangle slides down the frame
    y = 200 + i * 20
    draw.rectangle([x, y, x + 360, y + 240], fill=(196, 168, 130))
    draw.ellipse([W - 300, 300 + i * 15, W - 120, 480 + i * 15],
                 fill=(212, 197, 185))
    proc.stdin.write(img.tobytes())

proc.stdin.close()
stderr = proc.stderr.read().decode("utf-8", "replace")
rc = proc.wait()
if rc != 0:
    print(stderr[-3000:])
    raise SystemExit(f"ffmpeg failed with {rc}")

size = OUT.stat().st_size
print("ffmpeg binary :", ffmpeg_exe)
print("ffprobe on PATH:", shutil.which("ffprobe") or "NOT FOUND")
print("ffprobe next to binary:",
      (Path(ffmpeg_exe).parent / "ffprobe").exists())
print("output        :", OUT)
print("size bytes    :", size, f"({size/1024:.1f} KiB)")
print("frames/fps/dur:", N, FPS, f"{N/FPS:.2f}s")
# Pull the encoder's own summary line as proof of h264/yuv420p
for line in stderr.splitlines():
    if "Video:" in line or "frame=" in line and "libx264" in line:
        print("ffmpeg:", line.strip())
