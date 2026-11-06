#!/usr/bin/env python3
"""V2 comparison sheet: 4 timeline moments x 2 palette variants, labelled.

Input : remotion/out/v2/EliCloudV2Warm_{30,120,210,270}.png
        remotion/out/v2/EliCloudV2Cool_{30,120,210,270}.png
Output: remotion/out/v2/eli_v2_comparison_sheet.png

Labels are design names only, RTL-correct where Arabic script is used, and no
brand marks or Latin debug strings in the images themselves.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "out", "v2")

FRAMES = [30, 120, 210, 270]  # ≈ 1 s, 4 s, 7 s, 9 s
ROWS = [
    ("EliCloudV2Warm", "V2-warm  ·  گزینه گرم  (peach / coral room, violet Eli)"),
    ("EliCloudV2Cool", "V2-cool  ·  گزینه سرد  (teal / mint room, violet Eli)"),
]
COL_LABELS = [
    "1 s  ·  calm",
    "4 s  ·  curious (phone)",
    "7 s  ·  worried (thoughts)",
    "9 s  ·  resolved",
]

CELL_W = 405
CELL_H = 720
PAD = 18
HEADER_H = 168
ROW_LABEL_H = 54
FOOTER_H = 74
BG = (22, 18, 28)
CARD = (34, 28, 44)
INK = (246, 241, 250)
DIM = (170, 160, 188)
ACCENT = (255, 201, 60)


def font(size, bold=False, rtl=False):
    font_dir = os.environ.get("FONT_DIR", os.path.join(ROOT, "..", "assets", "fonts"))
    candidates = []
    if rtl and os.path.isdir(font_dir):
        candidates.append(os.path.join(font_dir, "Vazirmatn-Bold.ttf"))
    if os.path.isdir(font_dir):
        candidates += [
            os.path.join(font_dir, "Vazirmatn-Bold.ttf" if bold else "Vazirmatn-Medium.ttf"),
            os.path.join(font_dir, "Vazirmatn-Bold.ttf"),
        ]
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
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
        for name, _ in ROWS
        for f in FRAMES
        if not os.path.exists(os.path.join(OUT_DIR, f"{name}_{f}.png"))
    ]
    if missing:
        print("missing stills:\n  " + "\n  ".join(missing), file=sys.stderr)
        print("run: bash scripts/render-eli-v2.sh --stills", file=sys.stderr)
        return 1

    cols = len(FRAMES)
    width = PAD + cols * (CELL_W + PAD)
    height = HEADER_H + len(ROWS) * (ROW_LABEL_H + CELL_H + PAD) + FOOTER_H
    sheet = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(sheet)

    draw.text((PAD + 4, 26), "Eli Cloud V2 — two palettes", font=font(46, bold=True), fill=INK)
    draw.text(
        (PAD + 4, 82),
        "same room · same camera · same lighting · same 10 s timeline · 1080×1920 · 30 fps · silent",
        font=font(21),
        fill=DIM,
    )

    for col, label in enumerate(COL_LABELS):
        draw.text(
            (PAD + col * (CELL_W + PAD) + 4, HEADER_H - 34),
            label,
            font=font(21, bold=True),
            fill=DIM,
        )

    for row, (name, row_label) in enumerate(ROWS):
        y = HEADER_H + row * (ROW_LABEL_H + CELL_H + PAD)
        draw.text((PAD + 4, y + 10), row_label, font=font(28, bold=True, rtl=True), fill=ACCENT)
        for col, frame in enumerate(FRAMES):
            x = PAD + col * (CELL_W + PAD)
            cell_y = y + ROW_LABEL_H
            img = Image.open(os.path.join(OUT_DIR, f"{name}_{frame}.png")).convert("RGB")
            img = img.resize((CELL_W, CELL_H), Image.LANCZOS)
            draw.rounded_rectangle(
                [x - 2, cell_y - 2, x + CELL_W + 2, cell_y + CELL_H + 2], radius=10, fill=CARD
            )
            sheet.paste(img, (x, cell_y))

    draw.text(
        (PAD + 4, height - FOOTER_H + 18),
        "silent prototype · no narration, no music · every motion is a pure function of the frame number",
        font=font(19),
        fill=DIM,
    )

    out_path = os.path.join(OUT_DIR, "eli_v2_comparison_sheet.png")
    sheet.save(out_path, optimize=True)
    print(f"wrote {out_path} ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
