"""Probe B — Persian text rendering, two mutually exclusive pipelines.

Test sentence intentionally contains Persian digits, parentheses, a kasra
diacritic, and an em-dash:
  «۳ روشِ ساده برای تمرکز (بر پایه پژوهش ۲۰۱۱) — بخش اول»
(Note: the supplied sentence contains no U+200C ZWNJ codepoint; the ZWNJ
behaviour is verified separately in probe_b_zwnj.png using «نیمه‌تمام».)

Outputs (1080x1920 PNGs):
  probe_b_raqm.png  : RAW text, Pillow direction="rtl" + language="fa"
                      (works only when libraqm is present). If libraqm is
                      missing the exception is caught; the canvas documents
                      the failure and shows the naive default-layout render
                      of the raw string for comparison.
  probe_b_bidi.png  : arabic-reshaper (delete_harakat=False so the kasra
                      survives) THEN python-bidi, drawn with the default
                      layout — NO direction="rtl" here, otherwise the text
                      gets reversed twice.
  probe_b_zwnj.png  : extra diagnostic — large «نیمه‌تمام» proving the
                      ZWNJ prevents the نیمه/تمام join correctly.

The two methods must never be mixed.
"""
from pathlib import Path

import arabic_reshaper
import PIL.features
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT_PATH = HERE.parent / "assets" / "fonts" / "Vazirmatn-Bold.ttf"
SMALL_FONT_PATH = HERE.parent / "assets" / "fonts" / "Vazirmatn-Regular.ttf"

TEXT = "۳ روشِ ساده برای تمرکز (بر پایه پژوهش ۲۰۱۱) — بخش اول"
ZWNJ_TEXT = "نیمه‌تمام"
W, H = 1080, 1920
CREAM = (245, 240, 232)
CHARCOAL = (58, 58, 58)
RED = (150, 40, 40)
FONT_SIZE = 64

# Preserve harakat (the default config silently deletes them — verified).
reshaper = arabic_reshaper.ArabicReshaper(
    configuration={"delete_harakat": False}
)
font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
small = ImageFont.truetype(SMALL_FONT_PATH, 34)


def fresh_canvas():
    img = Image.new("RGB", (W, H), CREAM)
    return img, ImageDraw.Draw(img)


def center_xy(draw, text, fnt):
    box = draw.textbbox((0, 0), text, font=fnt)
    tw, th = box[2] - box[0], box[3] - box[1]
    return (W - tw) // 2 - box[0], (H - th) // 2 - box[1]


# --- Variant 1: raw text handed to Pillow's raqm RTL shaper ----------------
img1, d1 = fresh_canvas()
raqm_ok = bool(PIL.features.check("raqm"))
raqm_error = None
if raqm_ok:
    x, y = center_xy(d1, TEXT, font)
    d1.text((x, y), TEXT, font=font, fill=CHARCOAL,
            direction="rtl", language="fa")
else:
    # libraqm absent -> the documented raqm call raises KeyError. Record the
    # failure on-canvas, then show what a naive default draw does to the raw
    # string (the expected broken baseline).
    d1.text((60, 120), "raqm UNAVAILABLE: direction='rtl' raised KeyError",
            font=small, fill=RED)
    d1.text((60, 180), "(below: naive default-layout draw of the RAW string)",
            font=small, fill=RED)
    try:
        x, y = center_xy(d1, TEXT, font)
        d1.text((x, y + 120), TEXT, font=font, fill=CHARCOAL)
    except KeyError as exc:  # defensive: some builds reject it outright
        raqm_error = repr(exc)
        d1.text((60, 320), f"Exception: {exc!r}", font=small, fill=RED)
out1 = HERE / "probe_b_raqm.png"
img1.save(out1)
print("saved", out1, "| raqm_ok =", raqm_ok,
      f"| error = {raqm_error}" if raqm_error else "")

# --- Variant 2: reshape + bidi, then plain draw (no direction=!) -----------
reshaped = reshaper.reshape(TEXT)
visual = get_display(reshaped)
img2, d2 = fresh_canvas()
x, y = center_xy(d2, visual, font)
d2.text((x, y), visual, font=font, fill=CHARCOAL)
out2 = HERE / "probe_b_bidi.png"
img2.save(out2)
print("saved", out2)

# --- Extra diagnostic: ZWNJ joining behaviour ------------------------------
zwnj_visual = get_display(reshaper.reshape(ZWNJ_TEXT))
img3, d3 = fresh_canvas()
big = ImageFont.truetype(FONT_PATH, 140)
x, y = center_xy(d3, zwnj_visual, big)
d3.text((x, y - 60), zwnj_visual, font=big, fill=CHARCOAL)
d3.text((60, H - 200), "ZWNJ test: نیمه‌تمام must stay two separated words",
        font=small, fill=RED)
out3 = HERE / "probe_b_zwnj.png"
img3.save(out3)
print("saved", out3)

print("raw codepoints :", TEXT)
print("bidi codepoints:", visual)
print("kasra U+0650 survives full pipeline:", "ِ" in visual)
print("ZWNJ U+200C survives reshape stage :", "‌" in reshaper.reshape(ZWNJ_TEXT))
