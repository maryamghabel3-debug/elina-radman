# Carousel Studio — MVP (M18A + M18B + M18C)

Deterministic static carousel studio for ElinaOS. Takes an optional image
plus structured Persian text and produces branded 1080x1350 PNG slides
(Instagram 4:5) using **Pillow only** — no browser, no SVG engine, no new
dependencies.

- **M18A**: single slide renderer (brand themes, slide types, overflow
  protection)
- **M18B**: ordered multi-slide decks, deck-level validation, deterministic
  file naming, optional storage upload, content-item preparation
- **M18C**: AI planner — topic (+ optional image) → complete validated
  Persian deck JSON (written by Elina's voice rules, via LLMRouter)

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

## Usage (single slide, M18A)

```python
from agents.carousel import CarouselSlideRenderer

renderer = CarouselSlideRenderer()  # font via ELINA_FONT_PRIMARY_PATH
renderer.render(slide_dict_or_dataclass, "/tmp/slide_01.png")
```

## Deck schema (M18B)

```python
@dataclass
class CarouselDeck:
    title: str = ""
    template: str = "psychological_dark"   # inherited by slides without one
    slides: list[CarouselSlide] = []       # 2-10 slides, rendered in order
    deck_footer: str = ""                  # inherited by slides without a footer
    output_prefix: str | None = None       # optional filename prefix
    visual_consistency: bool = True
```

### Deck sample JSON

```json
{
  "title": "آینه‌ی هویت",
  "template": "psychological_dark",
  "deck_footer": "الینا | روان‌شناسی",
  "output_prefix": "mirror",
  "slides": [
    {"slide_type": "cover", "title": "آینه‌ای که ما می‌سازیم، خودِ ماست", "eyebrow": "هویت و تصویر"},
    {"slide_type": "title_body", "title": "تصویر بدنت، بایگانی نگاه‌های دیگران است", "body": "هر آینه‌ای که در آن ایستادی، یک روایت را به تو داده است."},
    {"slide_type": "quote", "title": "ما آینه‌ی هم را می‌سازیم، گاهی با نواختن و گاهی با شکستن."},
    {"slide_type": "bullet_list", "title": "سه نشانه‌ی تکرار زخم",
     "bullets": ["خستگی بدون دلیل", "پنهان‌کاری از خود", "توجیه مداوم دیگران"]},
    {"slide_type": "cta", "title": "این اسلایدها را ذخیره کن"}
  ]
}
```

### Deck rules (M18B)

- **2-10 slides** (0 -> `CAROUSEL_DECK_EMPTY`, 1 or 11+ -> `CAROUSEL_DECK_INVALID`)
- every slide must pass the M18A slide validation (child errors bubble as
  deck errors)
- **template inheritance**: a slide without `template` uses `deck.template`
  (standalone slides fall back to `psychological_dark`)
- **footer inheritance**: a slide without `footer` uses `deck.deck_footer`
- **slide numbers** are assigned deterministically (1-based) when missing;
  explicit numbers are kept
- **soft conventions** (log warnings, never fail): cover first, cta last

## Deterministic file naming (M18B)

`render_deck(deck, output_dir)` writes, in deck order:

```
01_cover.png
02_title_body.png
03_quote.png
04_bullet_list.png
05_cta.png
```

With `output_prefix`: `mirror_01_cover.png`, ... Zero-padded two-digit
index + slide type. Repeated renders of identical input produce identical
names and ordering.

## Storage upload helper (M18B)

```python
keys = renderer.upload_deck_to_storage(paths, custom_id, storage)
# -> ["carousel/<custom_id>/01_cover.png", ..., "carousel/<custom_id>/05_cta.png"]
```

- dependency-injected: `storage` must implement
  `upload_file(local, dest, content_type)` (the Supabase client qualifies)
- ordered keys, `image/png` content type
- no signed URLs, no publishing

## Content-item preparation helper (M18B)

```python
prepare_carousel_content_item(db, custom_id, media_keys, title=..., template=...)
```

Inserts a `content_type="carousel"` content item with the **ordered**
`media_keys` (the scheduler already publishes carousel items from ordered
media_keys) and deck metadata in `editor_notes`. Not wired to any bot in
M18B; no scheduling or publishing happens here.

## Typed errors (deck, M18B)

- `CAROUSEL_DECK_INVALID` — wrong slide count, bad deck template, invalid child slide
- `CAROUSEL_DECK_EMPTY` — no slides
- `CAROUSEL_DECK_RENDER_FAILED` — a slide failed during deck rendering
  (wraps the underlying typed slide error with the slide index)

Slide-level errors from M18A remain: `CAROUSEL_SLIDE_CONFIG_INVALID`,
`CAROUSEL_IMAGE_NOT_FOUND`, `CAROUSEL_FONT_NOT_FOUND`,
`CAROUSEL_TEXT_OVERFLOW`, `CAROUSEL_RENDER_FAILED`.

Generated slides are written to caller-provided paths (tests use temp
directories; nothing is written inside the repository).

## AI planner (M18C)

`CarouselPlanner` writes the Persian carousel content for a topic (and an
optional image) and returns a fully validated deck:

```python
from agents.carousel import CarouselPlanner

result = CarouselPlanner().plan(
    topic="چرا بعضی آدم‌ها وقتی به آن‌ها نزدیک می‌شوی عقب می‌کشند؟",
    slide_count=6,
    template="psychological_dark",
    image_path="/path/to/source.jpg",     # optional
    image_description="...",              # optional, skips vision call
    goal="save_and_share",                # save_and_share | follow | reflect
    language="fa",                        # Persian-only
)
# result: CarouselPlanResult(deck, caption, hashtags, image_description, provider_used)
```

### Planner JSON contract

```json
{
  "deck_title": "...",
  "slides": [
    {"slide_type": "cover", "title": "...", "eyebrow": "..."},
    {"slide_type": "title_body", "title": "...", "body": "..."},
    {"slide_type": "bullet_list", "title": "...", "bullets": ["..."]},
    {"slide_type": "quote", "title": "..."},
    {"slide_type": "cta", "title": "..."}
  ],
  "caption": "2-4 short Persian paragraphs + gentle CTA",
  "hashtags": ["#فارسی", "#english", "..."]
}
```

### Editorial rules encoded in the prompt (Brand Book / Voice & Tone /
Content Safety V2)

- all public text Persian; hybrid voice: «تو» for emotion, impersonal for
  analysis; intimate, calm, psychologically deep — not preachy, not
  clickbait, not generic-motivational
- cover first, exactly one cta last (enforced structurally, not just
  prompted); quote text in «...»; no emoji in titles
- per-type text limits from the M18A schema; bullets 2-5 short items
- forbidden phrases list enforced; clinical terms only with precise
  context; no medical/clinical claims, no diagnosis language
- caption 2-4 short paragraphs + gentle CTA; 5-10 relevant hashtags
  (Persian + English mix)

### Planner modes (M18C-UPDATE)

`plan(mode=...)` supports three operational modes:

| Mode | LLM? | Required inputs | Behavior |
|------|------|-----------------|----------|
| `ai_planned` (default) | yes | `topic` | M18C: the LLM writes everything |
| `text_overlay` | **no** | `image_paths` + `slide_texts` (same length, > 0) | User images + user texts zipped in exact order; first image -> cover; other slides -> image_text (keeps the user's image visible) |
| `image_deck` | yes | `image_paths` + `topic` | The LLM writes exactly `len(image_paths)` slides; generated text is zipped with the images in order |

Per-slide `slide_texts` entries: `{"title": "...", "body": "..." (optional),
"eyebrow": "..." (optional)}`. `text_overlay` returns empty caption/hashtags
(no LLM copy) and `provider_used=None`.

### Character presence (ai_planned, M18C-UPDATE)

Pass a `character_asset_provider` to `plan(...)` to enforce that every
content slide (except cta) shows a character visual:

```python
from agents.carousel import CarouselPlanner, LocalCharacterAssetProvider

provider = LocalCharacterAssetProvider(directory="content/assets/characters")
result = CarouselPlanner().plan(topic="...", mode="ai_planned",
                                character_asset_provider=provider)
```

- `CharacterAssetProvider.get_asset(character_hint, scene_hint, slide_type,
  template) -> path | None` is the abstraction (must be soft: missing asset
  -> None, never raises)
- `LocalCharacterAssetProvider` resolves from a local directory:
  `<hint>_<scene>_*` -> `<hint>_hero.*` -> first `<hint>_*` -> None
  (`world` hint -> `world_*` files)
- Fallback chain per slide: user image -> provider asset -> last successful
  image; `CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE` is raised only when no
  content slide can get any image at all
- Without a provider, `ai_planned` behaves exactly as M18C

### Planner behavior

- uses the existing `LLMRouter` (`smart_generate`, task
  `creative_writing`, `language="fa"` — CJK-contamination rejection
  included); no new dependencies
- image understanding is **soft**: `image_description` used directly when
  given; otherwise a best-effort Gemini description when `GEMINI_API_KEY`
  is set; ANY failure logs and continues without image context
- JSON parsing strips markdown fences; if parsing or deck validation fails,
  ONE repair retry quotes the exact error; then
  `CAROUSEL_PLAN_GENERATION_FAILED`
- the assembled deck passes the same validation the deck renderer uses — a
  partially valid deck is never returned silently
- the cover (and any image_text slide) receives the source `image_path`

### Planner error codes

- `CAROUSEL_PLAN_CONFIG_INVALID` — bad inputs (topic, slide_count 3-10,
  template, goal, language, missing image, invalid mode, mismatched
  image_paths/slide_texts lengths)
- `CAROUSEL_PLAN_GENERATION_FAILED` — LLM output unparseable/invalid after
  one repair retry, or no provider available
- `CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE` — ai_planned with a provider: no
  content slide could get a character visual

## Intentionally deferred (post-M18C)

- Telegram commands for carousel generation (M18D)
- Reel cover generation (M18E)
- carousel publishing automation (scheduler already supports it once an
  item exists)

## Telegram Studio flow (M18D)

Owner-only conversational carousel studio in `scripts/elina_studio_bot.py`.
All state-machine logic lives in `agents/studio/carousel_session.py` (the bot
is a thin transport layer). Session state is stored in
`context.chat_data["carousel_session"]` — separate from the `/plan` flow keys,
so the two flows never collide. Sessions expire after 30 minutes.

### States

```
/carousel
   └─ MODE_SELECT
        ├─ "1" (عکس و متن)      → COLLECT_IMAGES → /done → COLLECT_TEXTS → /done → BUILDING → PREVIEW
        ├─ "2" (عکس + موضوع)    → COLLECT_IMAGES → /done → COLLECT_TOPIC → (topic)  → BUILDING → PREVIEW
        └─ "3" (فقط موضوع)      → COLLECT_TOPIC → (topic)                        → BUILDING → PREVIEW
PREVIEW: /carousel_ok | /carousel_edit | /carousel_theme | /carousel_cancel
```

### Example conversation (Persian)

```
/carousel
→ ۱) عکس و متن می‌دهم   ۲) عکس می‌دهم + موضوع   ۳) فقط موضوع، الینا خودش بسازد
1
→ حالا عکس‌ها را یکی‌یکی بفرست (حداقل 2، حداکثر 10). وقتی تمام شد /done بزن.
[عکس ۱]
→ ✅ عکس 1 ثبت شد.
[عکس ۲]
→ ✅ عکس 2 ثبت شد.
/done
→ حالا 2 متن اسلاید را به ترتیب بفرست. برای بدنه: عنوان | بدنه
بعضی لبخندها انتخاب ما نیستند | اما با فهم، شکل می‌گیرند
→ ✅ متن 1 ثبت شد.
بعضی‌ها پیش از ما ساخته شده‌اند
→ ✅ متن 2 ثبت شد.
/done
→ ⏳ در حال ساخت کاروسل...
→ 🎨 پیش‌نمایش کاروسل: ... + [آلبوم تصاویر به‌ترتیب]
/carousel_ok
→ ✅ کاروسل تأیید و ذخیره شد. شناسه: ELN-CAR-YYYYMMDD-xxxxxxxx ...
```

### Command reference

| Command | Behavior |
|---------|----------|
| `/carousel` | Start session (active session → cancel first; expired → auto-reset with notice) |
| `/done` | Finish the current collection step (images / texts) |
| `/carousel_ok` | Upload ordered PNGs to `carousel/<custom_id>/`, create content item (`content_type="carousel"`, ordered `media_keys`, status `READY_FOR_REVIEW` — the same awaiting-schedule state `/promote` produces), clear session |
| `/carousel_edit <n> \| <text>` | Replace slide n title (and body after `\|`), re-render **that slide only** (documented choice: per-slide layout is independent), re-send the slide |
| `/carousel_theme <template>` | Validate + re-render the whole deck, re-send preview |
| `/carousel_cancel` | Clear session + temp files |

### Error messages (Persian, mapped from typed errors)

- `CAROUSEL_PLAN_CONFIG_INVALID` → «ورودی کاروسل ناقص است» + recovery hint
- `CAROUSEL_PLAN_GENERATION_FAILED` → «تولید متن… خطای موقتی» + retry hint
- `CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE` → «تصویر شخصیت پیدا نشد» + asset dir hint
- `CAROUSEL_TEXT_OVERFLOW` → «متن اسلاید N جا نمی‌شود» + retry hint
- After any build failure the session recovers to the mode's collection state
  (images preserved) so the user can fix and rebuild.

### Regression guarantees

- Photos/texts with **no** active carousel session follow the pre-M18D intake
  and `/plan` paths unchanged (covered by dedicated regression tests).
- Session state is dict-only and defensive: non-dict/corrupted state is
  treated as "no session", never a crash.

### Deferred

- publish automation (existing scheduler publishes carousels from
  `media_keys` once an item is approved)
- reel cover generation (M18E)
