# Carousel Studio — MVP (M18A)

Deterministic static carousel slide renderer for ElinaOS. Takes an optional
image plus structured Persian text and produces branded 1080x1350 PNG slides
(Instagram 4:5) using **Pillow only** — no browser, no SVG engine, no new
dependencies.

## Capabilities (M18A)

- **Persian RTL typography**: shaping/bidi via the existing
  `TypographyEngine` (libraqm when available, `arabic-reshaper` +
  `python-bidi` fallback). Font resolution reuses `ELINA_FONT_PRIMARY_PATH`.
  Naive text reversal is never used.
- **Text hierarchy**: eyebrow → title → body/bullets → footer/slide number,
  with deterministic word wrapping and automatic font-size reduction within
  configured minimums.
- **Images**: cover crop into the canvas (aspect preserved, never stretched),
  dark gradient overlay behind text, typed error for missing/invalid images.
- **Brand Book V2** palette and four templates (see below).
- **Overflow protection**: if text still cannot fit at minimum size,
  `CAROUSEL_TEXT_OVERFLOW` is raised (clear failure, never clipped text).
- **Deterministic output**: identical input produces identical PNG bytes.

## Slide schema

```python
@dataclass
class CarouselSlide:
    slide_type: str                  # cover | title_body | quote | bullet_list | image_text | cta
    title: str = ""
    body: str = ""
    bullets: list[str] = []          # bullet_list only, 2-5 items
    image_path: str | None = None    # optional (required for image_text)
    eyebrow: str = ""
    footer: str = ""
    template: str = "psychological_dark"
    accent: str = "antique_gold"     # any Brand Book V2 palette color
    slide_number: int | None = None
```

### Sample JSON

```json
{
  "slide_type": "title_body",
  "template": "psychological_dark",
  "accent": "antique_gold",
  "eyebrow": "روان‌شناسی هویت",
  "title": "تصویر بدنت، بایگانی خاطرات توست",
  "body": "وقتی در آینه نگاه می‌کنی، فقط صورت خودت را نمی‌بینی؛ سال‌ها نگاه دیگران هم در آنجا جا شده‌اند.",
  "footer": "الینا | روان‌شناسی",
  "slide_number": 2
}
```

## Supported slide types

| Type         | Behavior |
|--------------|----------|
| `cover`      | Optional full-bleed image + gradient overlay, strong title, optional eyebrow/subtitle, minimal elements |
| `title_body` | Clear title + readable body (RTL right-aligned), short accent line |
| `quote`      | Large quote text, restrained vertical accent line, optional author footer |
| `bullet_list`| Title + 2-5 concise bullets, marker at the RTL edge |
| `image_text` | Deterministic split: image region top 65%, text panel bottom 35% |
| `cta`        | One clear action, centered, optional supporting line (never competing CTAs) |

## Supported templates

| Template             | Ground | Text | Accent |
|----------------------|--------|------|--------|
| `psychological_dark` | ink_black | bone_white | antique_gold |
| `midnight_editorial` | midnight_blue | bone_white | oxidized_teal |
| `warm_cream`         | warm_cream | ink_black | muted_saffron |
| `minimal_photo`      | deep_charcoal | bone_white | dawn_gray |

## Palette (Brand Book V2, exact hex)

```yaml
primary:
  ink_black: "#101014"
  deep_charcoal: "#1A1A22"
  midnight_blue: "#161C2D"
  bone_white: "#E9E3DA"
accent:
  antique_gold: "#B89B65"
  dried_blood: "#762F35"      # reserved: danger/wound/climax only
  muted_saffron: "#B9853B"
  oxidized_teal: "#355E61"
hope:
  warm_cream: "#F1E9DC"
  dawn_gray: "#B8B4B0"
```

Brand rules encoded: dark grounds by default, bone_white typography on dark,
dried_blood never a template default accent, antique gold kept restrained
(thin short rules only), no generic pastel wellness styling, no ornamental
motifs without narrative meaning.

## Text limits (enforced at parse time)

| Type        | title | body | bullets |
|-------------|-------|------|---------|
| cover       | 60    | 80   | —       |
| title_body  | 80    | 240  | —       |
| quote       | 180   | —    | —       |
| bullet_list | 80    | —    | 2-5, each ≤ 64 |
| image_text  | 60    | 140  | —       |
| cta         | 60    | 80   | —       |

`eyebrow` ≤ 40 chars, `footer` ≤ 60 chars.

## Typed errors

- `CAROUSEL_SLIDE_CONFIG_INVALID` — bad slide template/accent/type/limits
- `CAROUSEL_IMAGE_NOT_FOUND` — missing or unreadable source image
- `CAROUSEL_FONT_NOT_FOUND` — no Persian-capable font resolvable
- `CAROUSEL_TEXT_OVERFLOW` — text cannot fit at minimum size
- `CAROUSEL_RENDER_FAILED` — unexpected render failure

## Usage

```python
from agents.carousel import CarouselSlideRenderer

renderer = CarouselSlideRenderer()  # font via ELINA_FONT_PRIMARY_PATH
renderer.render(slide_dict_or_dataclass, "/tmp/slide_01.png")
```

Generated slides are written to caller-provided paths (tests use temp
directories; nothing is written inside the repository).

## Intentionally deferred (post-M18A)

- multi-slide deck generation (ordering, pagination strategy)
- AI carousel text planning
- Supabase storage upload
- Telegram commands
- carousel publishing automation
- Reel cover generation
