#!/usr/bin/env python3
"""تحلیل دسته‌ای ویدیوها — موتور مهندسی معکوس.

روی یک پوشه پر از ویدیو اجرا می‌شود و برای هر کدام می‌گوید:
  · با هوش مصنوعی ساخته شده یا رندر کد؟ (تست پیکسل دقیقاً صفر)
  · چند شات دارد و هر شات چقدر طول می‌کشد
  · پالت رنگ، ضخامت خط، سبک زیرنویس
  · آیا صدا دارد و ریتم گفتارش چطور است
  · برای هر شات یک فریم کلیدی ذخیره می‌کند

  python scripts/analyze_lessons.py media/
  python scripts/analyze_lessons.py media/ --out analysis/lesson-04

خروجی: analysis/report.json + analysis/report.md + analysis/keyframes/
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

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg پیدا نشد: apt install ffmpeg  یا  pip install imageio-ffmpeg")


def probe(src: Path, ff: str) -> dict:
    txt = subprocess.run([ff, "-hide_banner", "-i", str(src)],
                         capture_output=True, text=True).stderr
    info: dict = {"streams": []}
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("Duration:"):
            hms = s.split("Duration:")[1].split(",")[0].strip()
            h, m, sec = hms.split(":")
            info["durationSec"] = round(int(h) * 3600 + int(m) * 60 + float(sec), 2)
        if "Video:" in s:
            info["streams"].append(s)
            import re
            m = re.search(r"(\d{2,5})x(\d{2,5})", s)
            if m:
                info["width"], info["height"] = int(m.group(1)), int(m.group(2))
            m = re.search(r"([\d.]+) fps", s)
            if m:
                info["fps"] = float(m.group(1))
            m = re.search(r"(\d+) kb/s", s)
            if m:
                info["videoKbps"] = int(m.group(1))
            for codec in ("h264", "hevc", "av1", "vp9", "prores"):
                if codec in s.lower():
                    info["codec"] = codec
                    break
            if "yuv420p" in s:
                info["pixfmt"] = "yuv420p"
        if "Audio:" in s:
            info["streams"].append(s)
            info["hasAudio"] = True
            import re
            m = re.search(r"(\d+) Hz", s)
            if m:
                info["audioHz"] = int(m.group(1))
            for c in ("aac", "mp3", "opus", "pcm"):
                if c in s.lower():
                    info["audioCodec"] = c
    info.setdefault("hasAudio", False)
    if "encoder" in txt:
        for line in txt.splitlines():
            if "encoder" in line:
                info["encoder"] = line.strip()
                break
    return info


def cut_points(src: Path, ff: str, thr: float = 0.08) -> list[float]:
    p = subprocess.run(
        [ff, "-hide_banner", "-i", str(src),
         "-filter:v", f"select='gt(scene,{thr})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    import re
    return sorted({round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", p.stderr)})


def frame_at(src: Path, ff: str, t: float, scale: int = 640) -> Image.Image:
    tmp = Path(tempfile.mkdtemp()) / "f.png"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-ss", f"{t}",
                    "-i", str(src), "-frames:v", "1", "-vf", f"scale={scale}:-1",
                    str(tmp), "-y"], check=True)
    img = Image.open(tmp).convert("RGB")
    shutil.rmtree(tmp.parent, ignore_errors=True)
    return img


def analyse_visual(img: Image.Image, ff: str, src: Path, samples: list[Image.Image]) -> dict:
    a = np.asarray(img.convert("L"), dtype=np.uint8)
    rgb = np.asarray(img, dtype=np.int16)
    h, w = a.shape
    lit = a > 40
    out: dict = {"frameSize": f"{w}x{h}"}

    out["blackRatio"] = round(float((a < 13).mean() * 100), 2)
    if lit.any():
        px = rgb[lit]
        out["accentSpread"] = round(float((px.max(1) - px.min(1)).mean()), 2)
        out["isGreyscale"] = out["accentSpread"] < 3
        # رنگ تاکیدی: پرتکرارترین رنگ غیرخاکستری
        tinted = px[(px.max(1) - px.min(1)) > 25]
        if len(tinted) > 50:
            vals, counts = np.unique(tinted.reshape(-1, 3), axis=0, return_counts=True)
            top = vals[counts.argmax()]
            out["accentColour"] = "#%02X%02X%02X" % tuple(int(c) for c in top)

    # تست رندر کد
    out["exactZeroPercent"] = round(float((a == 0).mean() * 100), 2)
    out["likelyCodeRender"] = out["exactZeroPercent"] > 55 and out.get("isGreyscale", False)

    # ضخامت خط
    runs = []
    for y in range(0, h, 6):
        c = 0
        for v in lit[y]:
            if v:
                c += 1
            elif c:
                runs.append(c)
                c = 0
    runs = np.array([r for r in runs if 0 < r < 40])
    if len(runs):
        out["strokePx"] = int(np.median(runs))

    # نوارهای ثابت
    out["topBandInk"] = int(lit[: int(h * 0.10)].sum())
    out["bottomBandInk"] = int(lit[int(h * 0.82):].sum())
    out["captionLikely"] = out["bottomBandInk"] > 200
    return out


def analyse_audio(src: Path, ff: str, work: Path) -> dict:
    wav = work / "a.wav"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-i", str(src),
                    "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(wav), "-y"])
    if not wav.exists() or wav.stat().st_size < 1000:
        return {"hasAudio": False}
    import wave
    w = wave.open(str(wav))
    n, sr = w.getnframes(), w.getframerate()
    a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    out = {"hasAudio": True, "peak": round(float(np.abs(a).max()), 3),
           "rms": round(float(np.sqrt((a ** 2).mean())), 4)}

    win = int(sr * 0.05)
    env = np.array([np.sqrt((a[i:i + win] ** 2).mean())
                    for i in range(0, len(a) - win, win)])
    if len(env):
        thr = env.max() * 0.06
        speech = env > thr
        runs, c = [], 0
        for s in speech:
            if s:
                c += 1
            elif c:
                runs.append(c * 0.05); c = 0
        if c:
            runs.append(c * 0.05)
        if runs:
            out["speechBursts"] = len(runs)
            out["meanBurstSec"] = round(float(np.mean(runs)), 2)
            out["medianBurstSec"] = round(float(np.median(runs)), 2)
            dur = n / sr
            out["burstsPerMinute"] = round(len(runs) / dur * 60, 1)
    return out


def describe(a: Image.Image) -> str:
    """توضیح متنی کوتاه از یک فریم — برای بازبینی انسانی، نه تشخیص خودکار."""
    g = np.asarray(a.convert("L"))
    lit = g > 40
    h, w = g.shape
    parts = []
    if lit.mean() < 0.005:
        return "فریم تقریباً خالی"
    ys, xs = np.nonzero(lit)
    parts.append(f"محتوا در x {xs.min()}-{xs.max()}, y {ys.min()}-{ys.max()}")
    # چگالی خط در مرکز
    cy0, cy1 = int(h * 0.35), int(h * 0.65)
    cx0, cx1 = int(w * 0.35), int(w * 0.65)
    centre = lit[cy0:cy1, cx0:cx1].mean()
    parts.append("مرکز شلوغ" if centre > 0.03 else "مرکز خالی")
    return " · ".join(parts)


def process(src: Path, ff: str, outdir: Path) -> dict:
    info = probe(src, ff)
    dur = info.get("durationSec") or 0
    cuts = cut_points(src, ff)
    bounds = [0.0] + cuts + [dur]
    shots = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    shots = [s for s in shots if s[1] - s[0] > 0.3]

    kf_dir = outdir / "keyframes" / src.stem
    kf_dir.mkdir(parents=True, exist_ok=True)

    shot_info = []
    for i, (a0, a1) in enumerate(shots):
        mid = a0 + (a1 - a0) * 0.55
        img = frame_at(src, ff, mid)
        img.save(kf_dir / f"{i:03d}_{mid:07.2f}s.png")
        vis = analyse_visual(img, ff, src, [img])
        shot_info.append({
            "index": i, "start": round(a0, 2), "end": round(a1, 2),
            "durationSec": round(a1 - a0, 2),
            "keyframe": str((kf_dir / f"{i:03d}_{mid:07.2f}s.png").relative_to(outdir)),
            "description": describe(img),
            **vis,
        })

    work = Path(tempfile.mkdtemp())
    audio = analyse_audio(src, ff, work)
    shutil.rmtree(work, ignore_errors=True)

    # نمای کلی
    allvis = [s for s in shot_info]
    code_share = round(100 * sum(1 for s in allvis if s.get("likelyCodeRender")) / max(len(allvis), 1), 1)
    grey_share = round(100 * sum(1 for s in allvis if s.get("isGreyscale")) / max(len(allvis), 1), 1)

    return {
        "file": src.name,
        "container": info,
        "shots": shot_info,
        "shotCount": len(shot_info),
        "meanShotSec": round(sum(s["durationSec"] for s in shot_info) / max(len(shot_info), 1), 2),
        "medianShotSec": round(float(np.median([s["durationSec"] for s in shot_info])) if shot_info else 0, 2),
        "codeRenderShotPercent": code_share,
        "greyscaleShotPercent": grey_share,
        "audio": audio,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="فایل ویدیو یا پوشه")
    ap.add_argument("--out", type=Path, default=Path("analysis"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"پیدا نشد: {args.input}")

    files = ([args.input] if args.input.is_file()
             else sorted(p for p in args.input.rglob("*") if p.suffix.lower() in VIDEO_EXT))
    if args.limit:
        files = files[: args.limit]
    if not files:
        sys.exit("هیچ فایل ویدیویی پیدا نشد")

    ff = ffmpeg_bin()
    args.out.mkdir(parents=True, exist_ok=True)

    results = []
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {f.name} ...", flush=True)
        try:
            results.append(process(f, ff, args.out))
        except Exception as e:  # noqa: BLE001
            print(f"   ✗ خطا: {e}")
            results.append({"file": f.name, "error": str(e)})

    (args.out / "report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# گزارش تحلیل ویدیوها", ""]
    L.append(f"تعداد فایل: **{len(results)}**")
    L.append("")
    L.append("| فایل | مدت | رزولوشن | شات | میانه شات | رندر کد؟ | خاکستری؟ | صدا |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in results:
        if "error" in r:
            L.append(f"| {r['file']} | — | — | — | — | — | — | خطا |")
            continue
        c = r["container"]
        L.append(
            f"| {r['file']} | {c.get('durationSec', '?')}s | "
            f"{c.get('width','?')}×{c.get('height','?')} | {r['shotCount']} | "
            f"{r['medianShotSec']}s | {r['codeRenderShotPercent']}% | "
            f"{r['greyscaleShotPercent']}% | "
            f"{'دارد' if r['audio'].get('hasAudio') else 'ندارد'} |")
    L.append("")

    for r in results:
        if "error" in r:
            continue
        L.append(f"## {r['file']}")
        L.append("")
        c = r["container"]
        L.append(f"- مدت: {c.get('durationSec')}s · {c.get('width')}×{c.get('height')} · "
                 f"{c.get('fps')}fps · {c.get('videoKbps')} kb/s · {c.get('codec')}")
        if "encoder" in c:
            L.append(f"- encoder: `{c['encoder']}`")
        a = r["audio"]
        if a.get("hasAudio"):
            L.append(f"- صدا: burst={a.get('speechBursts')} · "
                     f"میانگین {a.get('meanBurstSec')}s · "
                     f"{a.get('burstsPerMinute')}/دقیقه · RMS={a.get('rms')}")
        L.append(f"- شات: {r['shotCount']} · میانه {r['medianShotSec']}s · "
                 f"میانگین {r['meanShotSec']}s")
        L.append("")
        L.append("| # | شروع | مدت | توضیح | رندر کد |")
        L.append("|---|---|---|---|---|")
        for s in r["shots"][:40]:
            L.append(f"| {s['index']} | {s['start']}s | {s['durationSec']}s | "
                     f"{s['description']} | {'✓' if s.get('likelyCodeRender') else '—'} |")
        if len(r["shots"]) > 40:
            L.append(f"| … | | | {len(r['shots'])-40} شات دیگر | |")
        L.append("")

    (args.out / "report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n✓ {args.out/'report.md'}")
    print(f"✓ {args.out/'report.json'}")
    print(f"✓ {args.out/'keyframes'}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
