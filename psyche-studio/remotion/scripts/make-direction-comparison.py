#!/usr/bin/env python3
"""Build Eli direction A/B comparison graphics.

Outputs into psyche-studio/output/eli_direction_test/:
  eli_AB_side_by_side.png   equal-size portraits, labelled
  eli_AB_thumbnail_test.png both at Instagram-feed scale (~180 px tall)
  eli_AB_silhouette_test.png solid dark silhouettes of both

Silhouettes come from a border flood-fill of the bright studio backdrop,
so interior highlights stay part of the character and the outline is exact
(no hand-tuned thresholds on the face).
"""
import os
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
from PIL import ImageFont as _F  # noqa: E402


def font_dir():
    d = os.path.normpath(os.path.join(HERE, "../../assets/fonts"))
    return d


OUT = os.path.normpath(os.path.join(HERE, "../../output/eli_direction_test"))
FONT_DIR = font_dir()
FT = os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf")

INK = (44, 34, 56)
SUB = (128, 104, 112)
CARD = (252, 246, 237)


def character_mask(path, tol=50):
    """Character mask via flood fill of the backdrop, modelled per row.

    The studio backdrop is a smooth vertical gradient, so a single reference
    colour fails at one end of the frame. Instead each row's reference colour
    is measured from the frame's own left/right border columns (pure backdrop
    in these portraits), smoothed along y, and the fill is seeded from the
    border. The result is then reduced to the largest component that does not
    touch the frame, and interior holes (eye highlights) are filled.
    """
    im = Image.open(path).convert("RGB")
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)
    h, w, _ = a.shape

    strip = np.concatenate([a[:, :20, :], a[:, -20:, :]], axis=1).mean(1)  # (h,3)
    k = 41
    pad = np.pad(strip, ((k // 2, k // 2), (0, 0)), mode="edge")
    ref = np.stack([np.convolve(pad[:, c], np.ones(k) / k, mode="valid") for c in range(3)], 1)

    diff = np.abs(a - ref[:, None, :]).sum(2)
    bg = np.zeros((h, w), bool)
    seen = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        q.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        q.extend(((0, y), (w - 1, y)))
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or seen[y, x]:
            continue
        seen[y, x] = True
        if diff[y, x] > tol:
            continue
        bg[y, x] = True
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    cand0 = ~bg
    m_img = Image.fromarray((cand0 * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5))
    cand0 = np.asarray(m_img) > 127

    def blobs(cand):
        seen2 = np.zeros((h, w), bool)
        out = []
        for sy in range(0, h, 2):
            for sx in range(0, w, 2):
                if not cand[sy, sx] or seen2[sy, sx]:
                    continue
                qq = deque([(sx, sy)])
                seen2[sy, sx] = True
                pix, touches = [], False
                while qq:
                    x, y = qq.popleft()
                    pix.append((x, y))
                    if x <= 1 or y <= 1 or x >= w - 2 or y >= h - 2:
                        touches = True
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= nx < w and 0 <= ny < h and cand[ny, nx] and not seen2[ny, nx]:
                            seen2[ny, nx] = True
                            qq.append((nx, ny))
                if not touches:
                    out.append(pix)
        return out

    # the character is centred horizontally and lives above the contact shadow;
    # score blobs by area, closeness to centre-x and distance above the bottom
    best, best_score = None, -1
    for pix in blobs(cand0):
        area = len(pix) / float(w * h)
        if area < 0.02:
            continue
        xs = [p[0] for p in pix]
        ys = [p[1] for p in pix]
        cxn = (sum(xs) / len(xs)) / w
        cyn = (sum(ys) / len(ys)) / h
        score = area - 2.0 * abs(cxn - 0.5) - 1.2 * max(0.0, cyn - 0.72)
        if score > best_score:
            best_score, best = score, pix

    mask = np.zeros((h, w), bool)
    if best:
        xs = [p[0] for p in best]
        ys = [p[1] for p in best]
        mask[ys, xs] = True

    if mask.any():
        # close small gaps where the character is nearly backdrop-coloured
        mr = Image.fromarray((mask * 255).astype(np.uint8))
        mr = mr.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.MinFilter(17)).filter(ImageFilter.MedianFilter(9))
        mask = np.asarray(mr) > 127
        inv = Image.eval(mr, lambda v: 255 - v)
        for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            ImageDraw.floodfill(inv, seed, 128)
        mask = mask | (np.asarray(inv) != 128)
    return mask


def bbox(mask):
    ys, xs = np.where(mask)
    return xs.min(), ys.min(), xs.max(), ys.max()


def normalise(path, out_h_frac=0.68, canvas=(900, 1600)):
    """Equalise character height by CROPPING (never pasting).

    Each frame is cropped around its own character so that the character
    height becomes out_h_frac of the crop, then the crop is resized to the
    panel size. Both panels keep their native backdrop, there is no
    compositing seam and no resampling blur on the character.
    """
    im = Image.open(path).convert("RGB")
    m = character_mask(path)
    x0, y0, x1, y1 = bbox(m)
    ch = y1 - y0 + 1
    cw, chh = canvas
    ar = cw / chh

    crop_h = min(im.height, ch / out_h_frac)
    crop_w = crop_h * ar
    if crop_w > im.width:
        crop_w = im.width
        crop_h = crop_w / ar

    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left = cx - crop_w / 2
    top = cy - crop_h / 2
    left = max(0, min(left, im.width - crop_w))
    top = max(0, min(top, im.height - crop_h))
    box = (int(round(left)), int(round(top)),
           int(round(left + crop_w)), int(round(top + crop_h)))
    crop = im.crop(box).resize(canvas, Image.LANCZOS)
    return crop, m, (x0, y0, x1, y1), crop_h / ch


def silhouette(path, colour=(38, 28, 48)):
    im = Image.open(path).convert("RGB")
    m = character_mask(path)
    alpha = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    sil = Image.new("RGBA", im.size, colour + (0,))
    sil.putalpha(alpha)
    base = Image.new("RGB", im.size, (247, 242, 233))
    base.paste(sil, (0, 0), sil)
    return base


def label(d, xy, text, font, fill=INK):
    d.text(xy, text, font=font, fill=fill)


def two_up(imgs, labels, subs, out, footer=None, pad=54, gap=40,
           title="ELI — DIRECTION COMPARISON", subtitle=None, bg=CARD,
           min_content_w=0):
    w_i, h_i = imgs[0].size
    title_h = 150 if subtitle else 110
    foot_h = 92 if footer else 0
    F_T = ImageFont.truetype(FT, 56)
    F_S = ImageFont.truetype(FT, 26)
    F_L = ImageFont.truetype(FT, 40)
    F_U = ImageFont.truetype(FT, 24)
    # width must fit the images, the titles/subtitles and the footer
    need = [w_i * 2 + gap, min_content_w]
    for txt, f in [(title, F_T), (subtitle or "", F_S), (footer or "", F_U)]:
        need.append(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(txt, font=f))
    for lab, sub in zip(labels, subs):
        need.append(max(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(lab, font=F_L),
                        ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(sub or "", font=F_U)))
    W = pad * 2 + int(max(need)) + 8
    H = pad + title_h + h_i + 96 + foot_h
    sheet = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(sheet)
    d.text((pad, pad - 8), title, font=ImageFont.truetype(FT, 56), fill=INK)
    if subtitle:
        d.text((pad, pad + 58), subtitle, font=ImageFont.truetype(FT, 26), fill=SUB)
    row_w = w_i * 2 + gap
    x_off = pad + max(0, (W - pad * 2 - row_w) // 2)
    for i, (im, lab, sub) in enumerate(zip(imgs, labels, subs)):
        x = x_off + i * (w_i + gap)
        y = pad + title_h
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + w_i - 1, y + h_i - 1], outline=(222, 206, 194), width=2)
        # shrink the label until it fits inside its own panel, then centre it
        lf = 40
        while lf > 16 and d.textlength(lab, font=ImageFont.truetype(FT, lf)) > w_i - 8:
            lf -= 1
        f_lab = ImageFont.truetype(FT, lf)
        d.text((x + (w_i - d.textlength(lab, font=f_lab)) / 2, y + h_i + 14), lab, font=f_lab, fill=INK)
        if sub:
            sf = 24
            while sf > 14 and d.textlength(sub, font=ImageFont.truetype(FT, sf)) > w_i - 8:
                sf -= 1
            f_sub = ImageFont.truetype(FT, sf)
            d.text((x + (w_i - d.textlength(sub, font=f_sub)) / 2, y + h_i + 14 + lf + 12),
                   sub, font=f_sub, fill=SUB)
    if footer:
        d.text((pad, H - foot_h + 8), footer, font=ImageFont.truetype(FT, 24), fill=SUB)
    sheet.save(out, optimize=True)
    print("wrote", os.path.basename(out), sheet.size)


def main():
    A = os.path.join(OUT, "eli_A_portrait.png")
    B = os.path.join(OUT, "eli_B_portrait.png")

    # 1. equal-size side by side (normalised to the same character height)
    a_can, _, abox, asc = normalise(A)
    b_can, _, bbox_, bsc = normalise(B)
    two_up([a_can, b_can],
           ["A — Cloud Eli", "B — Purple Eli"],
           ["white cloud · yellow core · 30 % yellow",
            "purple creature · yellow crown · 25 % yellow"],
           os.path.join(OUT, "eli_AB_side_by_side.png"),
           subtitle="same backdrop · same pose · same camera · characters normalised to equal height",
           footer="Neutral friendly-mischievous pose. Both scaled so the character occupies 62 % of the frame height.")

    # 2. thumbnail test at Instagram feed scale (~180 px tall character)
    # characters sit at 68 % of panel height; make that 180 px exactly
    th_h = int(round(180 / 0.68))
    th_w = int(round(th_h * a_can.width / a_can.height))
    a_th = a_can.resize((th_w, th_h), Image.LANCZOS)
    b_th = b_can.resize((th_w, th_h), Image.LANCZOS)
    print("thumbnail panel %dx%d -> character ~180 px tall" % (th_w, th_h))
    two_up([a_th, b_th],
           ["A — Cloud Eli", "B — Purple Eli"],
           ["", ""],
           os.path.join(OUT, "eli_AB_thumbnail_test.png"),
           subtitle="character shown at true size — ~180 px tall, as it appears in an Instagram feed",
           footer="Both panels are shown at true size — the character is ~180 px tall, as it would appear in an Instagram feed.",
           pad=48, gap=34, title="ELI — THUMBNAIL TEST", min_content_w=980)

    # 3. silhouettes
    a_sil = silhouette(A).resize(a_can.size, Image.LANCZOS)
    b_sil = silhouette(B).resize(b_can.size, Image.LANCZOS)
    two_up([a_sil, b_sil],
           ["A — Cloud Eli", "B — Purple Eli"],
           ["cloud silhouette", "creature with curly crown + tail"],
           os.path.join(OUT, "eli_AB_silhouette_test.png"),
           subtitle="silhouette test — flat dark shape only, no colour or detail",
           footer="Which outline is more distinctive and still readable as a small cloud character?",
           title="ELI — SILHOUETTE TEST")


if __name__ == "__main__":
    main()
