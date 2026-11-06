#!/usr/bin/env python3
"""Assemble CHARACTER_SHEET_V2 contact sheet: 6 poses + room + hero keyframe."""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "../../output/eli_charactersheet_v2"))
FONT_DIR = os.path.normpath(os.path.join(HERE, "../../assets/fonts"))
FONT = ImageFont.truetype(os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf"), 30)
FONT_SM = ImageFont.truetype(os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf"), 24)
FONT_TITLE = ImageFont.truetype(os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf"), 54)

BG = (247, 241, 232)
INK = (46, 36, 58)
SUB = (132, 108, 116)
PAD, GAP = 44, 28
CELL, LABEL = 400, 74

poses = [
    ("eli_base_v2.png", "BASE", "friendly · mischievous"),
    ("eli_curious_v2.png", "CURIOUS", "leaning in, eyes wide"),
    ("eli_suspicious_v2.png", "SUSPICIOUS", "raised brow · pointing"),
    ("eli_detective_v2.png", "DETECTIVE", "tiny magnifying glass"),
    ("eli_worried_v2.png", "WORRIED", "storm tint · bolts + scribbles"),
    ("eli_sheepish_v2.png", "SHEEPISH", "blushing · looking sideways"),
]

row_w = 3 * CELL + 2 * GAP
scene_w = int(CELL * 0.78)
scene_h = int(scene_w * 16 / 9)

title_h = 130
H = PAD + title_h + 2 * (CELL + LABEL) + 40 + 40 + scene_h + 80 + PAD
W = PAD * 2 + row_w
sheet = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(sheet)

d.text((PAD, PAD), "ELI — CHARACTER SHEET V2", font=FONT_TITLE, fill=INK)
d.text((PAD, PAD + 66),
       "sunny-yellow accent · lavender-periwinkle body · 6 acting poses + room + hero keyframe",
       font=FONT_SM, fill=SUB)


def cell_box(x, y, w, h):
    d.rectangle([x, y, x + w - 1, y + h - 1], outline=(224, 210, 198), width=2)


def place_row(items, y0):
    x = PAD
    for name, label, sub in items:
        im = Image.open(os.path.join(OUT, name)).convert("RGB").resize((CELL, CELL), Image.LANCZOS)
        sheet.paste(im, (x, y0))
        cell_box(x, y0, CELL, CELL)
        d.text((x + 12, y0 + CELL + 12), label, font=FONT, fill=INK)
        d.text((x + 12, y0 + CELL + 46), sub, font=FONT_SM, fill=SUB)
        x += CELL + GAP
    return y0 + CELL + LABEL


y = place_row(poses[:3], PAD + title_h)
y = place_row(poses[3:], y + 40)

# scenes centred
total = 2 * scene_w + GAP
startx = PAD + (row_w - total) // 2
for i, (name, l1, l2) in enumerate([("room_v2.png", "ROOM V2", "9:16 · teal / coral / mustard"),
                                   ("hero_keyframe.png", "HERO KEYFRAME", "Eli + phone + «؟» marks")]):
    x = startx + i * (scene_w + GAP)
    im = Image.open(os.path.join(OUT, name)).convert("RGB").resize((scene_w, scene_h), Image.LANCZOS)
    sheet.paste(im, (x, y))
    cell_box(x, y, scene_w, scene_h)
    cx = x + (scene_w - d.textlength(l1, font=FONT)) // 2
    d.text((cx, y + scene_h + 10), l1, font=FONT, fill=INK)
    if d.textlength(l2, font=FONT_SM) <= scene_w:
        cx2 = x + (scene_w - d.textlength(l2, font=FONT_SM)) // 2
        d.text((cx2, y + scene_h + 44), l2, font=FONT_SM, fill=SUB)
    else:
        d.text((x, y + scene_h + 44), l2.split(" · ")[0], font=FONT_SM, fill=SUB)

sheet.save(os.path.join(OUT, "CHARACTER_SHEET_V2.png"), optimize=True)
print("wrote CHARACTER_SHEET_V2.png", sheet.size)
