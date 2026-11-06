#!/usr/bin/env python3
"""کاوش استایل یک ویدیو موشن — همان اندازه‌گیری‌هایی که سند را ساخت.

هر عددی که در docs/MOTION-REVERSE-ENGINEERING.md آمده، از این اسکریپت می‌آید.
برای ویدیوی خودتان اجرا کنید تا ببینید چقدر با نمونه فاصله دارد.

  python scripts/probe_motion_style.py example.mp4
  python scripts/probe_motion_style.py my-motion.mp4 --out /tmp/probe
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg پیدا نشد: apt install ffmpeg  یا  pip install imageio-ffmpeg")


def probe_meta(src: Path, ff: str) -> dict:
    out = subprocess.run([ff, "-hide_banner", "-i", str(src)],
                         capture_output=True, text=True).stderr
    meta = {"raw": []}
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("Duration:"):
            meta["duration"] = s.split(",")[0].replace("Duration:", "").strip()
        if "Video:" in s or "Audio:" in s:
            meta["raw"].append(s)
        if "encoder" in s:
            meta["encoder"] = s.strip()
    return meta


def extract_frames(src: Path, ff: str, fps: int, scale: int, work: Path) -> list[Path]:
    d = work / "frames"
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-i", str(src),
                    "-vf", f"fps={fps},scale={scale}:-1", str(d / "%05d.png")], check=True)
    return sorted(d.glob("*.png"))


def analyse(frames: list[Path]) -> dict:
    arrs = [np.asarray(Image.open(f).convert("L"), dtype=np.uint8) for f in frames]
    if not arrs:
        return {}
    h, w = arrs[0].shape
    stack = np.stack(arrs)

    res: dict = {"frames": len(arrs), "size": f"{w}x{h}"}

    # --- سیاهی ---
    res["black_ratio_percent"] = round(float((stack < 13).mean() * 100), 2)

    # --- تست «رندر تمیز»: پیکسل دقیقاً صفر ---
    res["exact_zero_percent"] = round(float((stack == 0).mean() * 100), 2)

    # --- رنگ ---
    rgb = np.asarray(Image.open(frames[len(frames) // 2]).convert("RGB"), dtype=np.int16)
    lit = rgb.max(2) > 40
    if lit.any():
        px = rgb[lit]
        spread = (px.max(1) - px.min(1))
        res["channel_spread_mean"] = round(float(spread.mean()), 3)
        res["tinted_percent"] = round(float((spread > 15).mean() * 100), 2)

    # --- ضخامت خط ---
    runs = []
    for a in arrs[:: max(1, len(arrs) // 12)]:
        l = a > 60
        for y in range(0, h, 5):
            c = 0
            for v in l[y]:
                if v:
                    c += 1
                elif c:
                    runs.append(c)
                    c = 0
            if c:
                runs.append(c)
    runs = np.array([r for r in runs if 0 < r < 40])
    if len(runs):
        res["stroke_px"] = {"median": int(np.median(runs)),
                            "p10": int(np.percentile(runs, 10)),
                            "p90": int(np.percentile(runs, 90))}

    # --- پرش بین فریم‌ها (پایداری رندر) ---
    diffs = [float(np.abs(arrs[i + 1].astype(np.int16) - arrs[i].astype(np.int16)).mean())
             for i in range(min(len(arrs) - 1, 120))]
    if diffs:
        res["frame_diff_mean"] = round(float(np.mean(diffs)), 4)

    # --- نوارهای ثابت (هدر / زیرنویس) ---
    top = stack[:, : int(h * 0.10), :].mean(axis=(1, 2))
    bot = stack[:, int(h * 0.82):, :].mean(axis=(1, 2))
    res["top_band_present_percent"] = round(float((top > 1).mean() * 100), 1)
    res["bottom_band_present_percent"] = round(float((bot > 1).mean() * 100), 1)

    return res


def scene_cuts(src: Path, ff: str, thr: float = 0.25) -> int:
    p = subprocess.run([ff, "-hide_banner", "-i", str(src), "-filter:v",
                        f"select='gt(scene,{thr})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    return p.stderr.count("pts_time:")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--fps", type=int, default=5)
    ap.add_argument("--scale", type=int, default=360)
    ap.add_argument("--json", action="store_true", help="خروجی JSON خام")
    args = ap.parse_args()

    if not args.video.exists():
        sys.exit(f"فایل پیدا نشد: {args.video}")

    ff = ffmpeg_bin()
    work = Path(tempfile.mkdtemp(prefix="motionprobe-"))
    try:
        meta = probe_meta(args.video, ff)
        frames = extract_frames(args.video, ff, args.fps, args.scale, work)
        stats = analyse(frames)
        stats["cuts_at_0.25"] = scene_cuts(args.video, ff)
        stats["meta"] = meta

        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            return 0

        print(f"\n=== {args.video.name} ===")
        print(f"  مدت: {meta.get('duration', '?')}")
        for line in meta.get("raw", []):
            print(f"  {line}")
        print(f"\n  سیاهی فریم:          {stats.get('black_ratio_percent')}%")
        print(f"  پیکسل دقیقاً صفر:    {stats.get('exact_zero_percent')}%  "
              f"{'← رندر تمیز' if (stats.get('exact_zero_percent') or 0) > 60 else ''}")
        print(f"  نشتی رنگ:            {stats.get('tinted_percent', 0)}%")
        print(f"  ضخامت خط:            {stats.get('stroke_px')}")
        print(f"  پرش فریم:            {stats.get('frame_diff_mean')}")
        print(f"  نوار هدر:            {stats.get('top_band_present_percent')}% فریم‌ها")
        print(f"  نوار زیرنویس:        {stats.get('bottom_band_present_percent')}% فریم‌ها")
        print(f"  کات (آستانه ۰٫۲۵):   {stats.get('cuts_at_0.25')}")
        print()
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
