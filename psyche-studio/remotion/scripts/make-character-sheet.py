#!/usr/bin/env python3
"""Assemble the Eli character sheet contact sheet (labelled)."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__)) + "/../../output/eli_charactersheet"
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../assets/fonts")
FONT = ImageFont.truetype(os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf"), 34)
FONT_SM = ImageFont.truetype(os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf"), 26)
FONT_TITLE = ImageFont.truetype(os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf"), 52)

BG = (250, 244, 235)
INK = (58, 40, 60)
SUB = (140, 110, 120)
PAD = 40
GAP = 26

# row 1: the three accent bases (square)
bases = [
    ("eli_base_yellow.png", "BASE · SUNNY YELLOW"),
    ("eli_base_coral.png", "BASE · CORAL / PEACH"),
    ("eli_base_blue.png", "BASE · SKY BLUE"),
]
# row 2: expressions from the yellow base (square)
exprs = [
    ("eli_curious.png", "CURIOUS"),
    ("eli_worried.png", "WORRIED / OVERTHINKING"),
    ("eli_resolved.png", "RESOLVED / HAPPY"),
]

CELL = 420
LABEL = 56
row_w = 3 * CELL + 2 * GAP
room_w = int(CELL * 0.62)
room_h = int(room_w * 16 / 9)

title_h = 118
H = PAD + title_h + (CELL + LABEL) + 46 + (CELL + LABEL) + 46 + room_h + LABEL + PAD
W = PAD * 2 + row_w
sheet = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(sheet)

d.text((PAD, PAD), "ELI — CHARACTER SHEET", font=FONT_TITLE, fill=INK)
d.text((PAD, PAD + 62), "phase 1 · 3 accent variants + 3 expressions + room · clay/diorama style",
       font=FONT_SM, fill=SUB)


def place_row(items, y0):
    x = PAD
    for name, label in items:
        im = Image.open(os.path.join(OUT, name)).convert("RGB")
        im = im.resize((CELL, CELL), Image.LANCZOS)
        sheet.paste(im, (x, y0))
        d.rectangle([x, y0, x + CELL - 1, y0 + CELL - 1], outline=(226, 212, 200), width=2)
        d.text((x + 12, y0 + CELL + 12), label, font=FONT, fill=INK)
        x += CELL + GAP
    return y0 + CELL + LABEL


y = place_row(bases, PAD + title_h)
y = place_row(exprs, y + 46)

# room, centred, with its own label
x = PAD + (row_w - room_w) // 2
room = Image.open(os.path.join(OUT, "room_v1.png")).convert("RGB").resize((room_w, room_h), Image.LANCZOS)
sheet.paste(room, (x, y))
d.rectangle([x, y, x + room_w - 1, y + room_h - 1], outline=(226, 212, 200), width=2)
d.text((x + 12, y + room_h + 12), "ROOM · 9:16 cozy corner", font=FONT, fill=INK)

sheet.save(os.path.join(OUT, "CHARACTER_SHEET.png"), optimize=True)
print("wrote CHARACTER_SHEET.png", sheet.size)
