#!/usr/bin/env python3
"""Assemble the labelled comparison sheet from the four QA stills per version.

Input : remotion/out/eli/EliCloudTest_{30,120,210,270}.png
        remotion/out/eli/EliLinesTest_{30,120,210,270}.png
Output: remotion/out/eli/eli_comparison_sheet.png

The sheet is a 4×2 grid: columns are the four timeline moments, rows are the
two designs. Labels are kept to neutral design names (A / B) and seconds —
no brand marks, no Latin debug strings.

Usage:
    python3 scripts/make-comparison-sheet.py
    FONT_DIR=assets/fonts python3 scripts/make-comparison-sheet.py
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "out", "eli")

FRAMES = [30, 120, 210, 270]           # ≈ 1 s, 4 s, 7 s, 9 s at 30 fps
ROW_A = "EliCloudTest"
ROW_B = "EliLinesTest"
ROW_LABELS = {ROW_A: "A · Eli as a cloud", ROW_B: "B · Eli as flowing light lines"}
COL_LABELS = ["0–2 s  room established", "2–5 s  phone reaction",
              "5–8 s  thought shapes", "8–10 s  final pose"]

CELL_W = 405                            # 1080/8*3 -> quarter of the width
CELL_H = 720                            # keeps the 9:16 cells
PAD = 18
HEADER_H = 156
ROW_LABEL_H = 52
FOOTER_H = 64
BG = (24, 20, 32)
CARD = (32, 27, 42)
INK = (245, 240, 250)
DIM = (168, 158, 186)
ACCENT = (255, 186, 145)


def font(size, bold=False):
    candidates = []
    font_dir = os.environ.get("FONT_DIR", os.path.join(ROOT, "..", "assets", "fonts"))
    if os.path.isdir(font_dir):
        candidates += [
            os.path.join(font_dir, "Vazirmatn-Bold.ttf" if bold else "Vazirmatn-Medium.ttf"),
            os.path.join(font_dir, "Vazirmatn-Bold.ttf"),
        ]
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def main() -> int:
    missing = [
        os.path.join(OUT_DIR, f"{name}_{f}.png")
        for name in (ROW_A, ROW_B)
        for f in FRAMES
        if not os.path.exists(os.path.join(OUT_DIR, f"{name}_{f}.png"))
    ]
    if missing:
        print("missing stills:\n  " + "\n  ".join(missing), file=sys.stderr)
        print("run: bash scripts/render-eli.sh --stills", file=sys.stderr)
        return 1

    cols = len(FRAMES)
    width = PAD + cols * (CELL_W + PAD)
    height = HEADER_H + 2 * (ROW_LABEL_H + CELL_H + PAD) + FOOTER_H
    sheet = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(sheet)

    # header
    draw.text((PAD + 4, 26), "Eli — two 3D prototypes", font=font(46, bold=True), fill=INK)
    draw.text(
        (PAD + 4, 80),
        "same room · same camera · same lighting · same 10-second timeline · 1080×1920 · 30 fps",
        font=font(21),
        fill=DIM,
    )

    # column labels sit above the first row, so they never collide with the
    # row labels
    for col, label in enumerate(COL_LABELS):
        draw.text(
            (PAD + col * (CELL_W + PAD) + 4, HEADER_H - 34),
            label,
            font=font(21, bold=True),
            fill=DIM,
        )

    for row, name in enumerate((ROW_A, ROW_B)):
        y = HEADER_H + row * (ROW_LABEL_H + CELL_H + PAD)
        draw.text((PAD + 4, y + 8), ROW_LABELS[name], font=font(30, bold=True), fill=ACCENT)
        for col, frame in enumerate(FRAMES):
            x = PAD + col * (CELL_W + PAD)
            cell_y = y + ROW_LABEL_H
            img = Image.open(os.path.join(OUT_DIR, f"{name}_{frame}.png")).convert("RGB")
            img = img.resize((CELL_W, CELL_H), Image.LANCZOS)
            draw.rounded_rectangle(
                [x - 2, cell_y - 2, x + CELL_W + 2, cell_y + CELL_H + 2],
                radius=10,
                fill=CARD,
            )
            sheet.paste(img, (x, cell_y))
            # frame number, small, neutral
            draw.text(
                (x + 8, cell_y + CELL_H - 26),
                f"frame {frame}",
                font=font(16),
                fill=(255, 255, 255),
            )

    draw.text(
        (PAD + 4, height - FOOTER_H + 16),
        "silent prototype · no narration, no music · rendered deterministically from the frame number",
        font=font(19),
        fill=DIM,
    )

    out_path = os.path.join(OUT_DIR, "eli_comparison_sheet.png")
    sheet.save(out_path, optimize=True)
    print(f"wrote {out_path} ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
