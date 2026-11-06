#!/usr/bin/env python3
"""Extract labelled storyboard and mouth-state comparisons from bubbles v1."""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "output/eli_elina_bubbles_v1/eli_elina_bubbles_v1.mp4"
OUT = VIDEO.parent
# The established visual beats plus both chunks of Eli's longer reaction.
STORY = [
    (12, "0.4s — shared opening"),
    (39, "1.3s — Eli close / cue 1"),
    (78, "2.6s — Elina reply"),
    (117, "3.9s — Eli question / mouth test"),
    (156, "5.2s — phone + «باشه»"),
    (210, "7.0s — Eli reaction / chunk 1"),
    (267, "8.9s — Eli reaction / chunk 2"),
    (315, "10.5s — Elina final reply"),
    (348, "11.6s — shared finish"),
]


def h32(text: str) -> int:
    h = 2166136261
    for c in text:
        h = ((h ^ ord(c)) * 16777619) & 0xFFFFFFFF
    return h


def state_for(line_id: str, start: int, frame: int, pause_ranges=()) -> str:
    rel = frame - start
    if any(a <= rel < b for a, b in pause_ranges):
        return "closed"
    elapsed = max(0, frame - start - 4)
    cycle = consumed = 0
    period = 10
    while consumed <= elapsed:
        period = 10 + h32(f"{line_id}-{cycle}") % 5
        if elapsed < consumed + period:
            break
        consumed += period
        cycle += 1
    phase = elapsed - consumed
    if phase < round(period * .58):
        return "closed"
    if phase < round(period * .86):
        return "small"
    return "open"


def first_triplet(line_id: str, start: int, end: int, pauses=(), search_from=None):
    found = {}
    for f in range(start if search_from is None else search_from, end):
        st = state_for(line_id, start, f, pauses)
        found.setdefault(st, f)
    missing = {"closed", "small", "open"} - set(found)
    if missing:
        raise RuntimeError(f"no sampled {missing} state in cue {line_id}")
    return [found[s] for s in ("closed", "small", "open")]


def extract_frames(frames: list[int], directory: Path) -> dict[int, Image.Image]:
    # One ffmpeg decode pass; output frames are ordered exactly as requested.
    filt = "select=" + "+".join(f"eq(n\\,{n})" for n in frames)
    pattern = directory / "frame-%02d.png"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(VIDEO),
        "-vf", filt, "-fps_mode", "passthrough", "-frames:v", str(len(frames)), str(pattern),
    ], check=True)
    paths = sorted(directory.glob("frame-*.png"))
    if len(paths) != len(frames):
        raise RuntimeError(f"expected {len(frames)} extracted frames, got {len(paths)}")
    return {n: Image.open(p).convert("RGB") for n, p in zip(frames, paths)}


def label_font(size: int):
    choices = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in choices:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_story(frames: dict[int, Image.Image]):
    cols, rows, cell_w, cell_h = 3, 3, 340, 604
    margin, head = 18, 42
    sheet = Image.new("RGB", (margin + cols * (cell_w + margin), margin + rows * (cell_h + head + margin)), "#f2eee7")
    draw = ImageDraw.Draw(sheet)
    fnt = label_font(18)
    for i, (frame, title) in enumerate(STORY):
        col, row = i % cols, i // cols
        x, y = margin + col * (cell_w + margin), margin + row * (cell_h + head + margin)
        draw.text((x, y + 7), title, fill="#362d2b", font=fnt)
        im = frames[frame].resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        sheet.paste(im, (x, y + head))
    sheet.save(OUT / "CONTACT_SHEET.png", optimize=True)


def make_mouth_sheet(frames: dict[int, Image.Image], eli_frames: list[int], elina_frames: list[int]):
    crop_specs = [
        ("Eli — curious pose", eli_frames, (456, 746, 706, 906)),
        ("Elina — neutral pose", elina_frames, (429, 821, 679, 981)),
    ]
    cell_w, cell_h, top_h, left_w, gap = 470, 320, 46, 260, 18
    width = left_w + 3 * cell_w + 4 * gap
    height = 2 * (top_h + cell_h) + 3 * gap
    sheet = Image.new("RGB", (width, height), "#f2eee7")
    d = ImageDraw.Draw(sheet)
    heading = label_font(22)
    small = label_font(20)
    state_names = ["CLOSED", "SMALL OPEN", "OPEN"]
    for row, (title, frame_list, crop_box) in enumerate(crop_specs):
        y = gap + row * (top_h + cell_h + gap)
        d.text((gap, y + 12), title, fill="#362d2b", font=heading)
        for col, f in enumerate(frame_list):
            x = left_w + gap + col * (cell_w + gap)
            d.text((x, y + 12), f"{state_names[col]} — frame {f}", fill="#362d2b", font=small)
            close = frames[f].crop(crop_box).resize((cell_w, cell_h), Image.Resampling.LANCZOS)
            sheet.paste(close, (x, y + top_h))
    sheet.save(OUT / "MOUTH_COMPARISONS.png", optimize=True)


def main():
    if not VIDEO.exists():
        raise FileNotFoundError(VIDEO)
    eli = first_triplet("p1_l3", 105, 133, ((15, 20),), search_from=109)
    elina = first_triplet("p1_l2", 65, 105, ((17, 24),))
    needed = sorted({f for f, _ in STORY} | set(eli) | set(elina))
    with tempfile.TemporaryDirectory(prefix="bubbles-frames-") as tmp:
        frames = extract_frames(needed, Path(tmp))
        make_story(frames)
        make_mouth_sheet(frames, eli, elina)
    print(f"wrote {OUT / 'CONTACT_SHEET.png'}")
    print(f"wrote {OUT / 'MOUTH_COMPARISONS.png'}")
    print(f"Eli state frames: {eli}; Elina state frames: {elina}")


if __name__ == "__main__":
    main()
