# Eli — two 3D prototypes (cloud vs. flowing light lines)

A visual A/B of **Eli**, the character that represents Elina's mind, built as
two 10-second 3D prototypes that share one room, one camera, one lighting rig
and one event timeline.

This is a **prototype only**: no narration, no music, no psychology script, no
final Elina model. The audio drive and the old BasheV3 / ContactSheet
compositions are untouched.

| | Composition | Output |
|---|---|---|
| A | `EliCloudTest` | `out/eli/eli_cloud_test.mp4` |
| B | `EliLinesTest` | `out/eli/eli_lines_test.mp4` |

Both: **10 s · 1080×1920 · 30 fps · H.264 / yuv420p · silent**.

---

## What is shared and what changes

```
src/eli/
  palette.ts     one art-direction palette (lavender / peach / sky / cream / yellow)
  timeline.ts    the single 10-second event clock + easing helpers
  eliPose.ts     one pure pose function: entrance, turn, blink, reach, joy, thoughts
  Room.tsx       the shared room: walls, floor, rug, armchair, side table + phone,
                 plant, shelf, window, pendant lamp, lights, camera
  CloudEli.tsx   VERSION A — cloud character + cloud-style thought shapes
  LinesEli.tsx   VERSION B — luminous line character + line-style thought shapes
  EliTest.tsx    both compositions; identical Room, camera and state
  index.tsx      entry point for just these two compositions
```

Everything that decides *when* something happens lives in `timeline.ts` and
`eliPose.ts`. Everything that decides *what it looks like* lives in the two
character files. That is what makes the comparison fair: swapping the
character cannot move a beat.

### Timeline (identical for A and B)

| Time | Beat |
|---|---|
| 0.0–2.0 s | room lights up, camera settles, Eli floats in from upper left |
| 2.3 s | phone screen lights with a notification, warm spill into the room |
| 2.55–3.6 s | Eli turns toward the phone, eyes lead the turn |
| 3.5–4.7 s | curious peak, lean and reach toward the table, surprise pop |
| 5.0–6.1 s | three thought shapes emerge beside the head |
| 5.9–7.6 s | shapes orbit Eli; brows/eyes and body follow them |
| 7.7–8.7 s | shapes settle into a tidy arrange, reach comes back down |
| 8.3–9.2 s | final expressive pose: happy squint, smile, arms out |
| 9.2–10.0 s | gentle hold with continuing idle float |

Animation is **deterministic**: every value is a pure function of the Remotion
frame number. No `useFrame`, no `Date.now`, no `Math.random`, no time-based
loop. Re-rendering the same frame twice produces the same pixels.

---

## Art direction

Cheerful, cosy, stylised room: lavender walls, cream surfaces, peach/coral
accents, sky-blue furniture and a single restrained yellow highlight. Soft key
light from upper left, cool lavender fill from the window side, a warm rim to
separate the character from the wall, and a warm pool of light from the phone
once the notification lands.

### Version A — Eli as a cloud
Two-lobe silhouette (a taller head-cloud above a wider body-cloud), a three-puff
yellow crown curl, two cloud "hand" puffs and two drifting feet tufts. Pastel
scheme in three coordinated families: lavender crown, peach crown accents,
sky-blue body, cream highlight. Expressive face: warm-iris eyes with
catchlights, cheeks and a smile arc that widens in the final beat.

### Version B — Eli as flowing luminous lines
A signature-like set of neon ribbons: one closed oval head loop carrying the
face, a lavender crown arch, a coral torso loop, two yellow arms that end in
glowing hands, and sky-blue tails that keep flowing. Same colour families as
version A, so the comparison is about form rather than hue. Glow is deliberately
controlled (emissive ≈ 0.4, `toneMapped: false`) so the lines stay readable and
do not blow out on the lavender wall.

---

## Package versions

Installed with npm, all `@remotion/*` aligned to one exact version:

| Package | Version | Why |
|---|---|---|
| `remotion` / `@remotion/cli` / `@remotion/three` | `4.0.539` | current stable; `@remotion/three@4.0.539` declares a peer on `remotion@4.0.539` exactly |
| `react` / `react-dom` | `18.3.1` | already used by the Repo; R3F 8.x requires React 18 |
| `three` | `0.171.0` | the version Remotion's React 19 upgrade note pins; ≥ the `>=0.137` peer of `@remotion/three` |
| `@react-three/fiber` | `8.18.0` | newest 8.x; peers `react >=18 <19`, so it matches React 18.3.1. **9.x requires React 19 and was deliberately not used.** |
| `@types/three` | `0.171.0` | matches three |

No stable/alpha mixing: only `latest` tags, no `alpha`/`canary` channel.

Three.js does not render with the default GL backend in headless Chromium, so
the render passes `--gl=swangle` (`--use-gl=angle --use-angle=swiftshader`),
as recommended in https://www.remotion.dev/docs/three.

---

## How the render was actually verified (sandbox)

This sandbox has **no Chromium, no ffmpeg and no root**, and cannot reach
`remotion.media`, so `npx remotion browser ensure` cannot work here. A real
frame was still rendered locally:

```bash
cd psyche-studio/remotion
eval "$(node scripts/ensure-browser.mjs)"    # resolves Chromium + ffmpeg for this sandbox
bash scripts/render-eli.sh                   # videos + QA stills
bash scripts/qa-eli.sh                       # full QA, exits non-zero on failure
```

`scripts/ensure-browser.mjs` finds, in order: Remotion's own Chrome Headless
Shell cache, `@sparticuz/chromium` (installed as a devDependency) plus its
bundled NSS libraries, or a system Chrome. It shims ffmpeg so Remotion can call
it by name. It prints shell exports; it does not download anything from
blocked hosts.

`scripts/qa-eli.sh` checks, per file: duration 10.0 s, 1080×1920, 30 fps,
h264, yuv420p, 300 frames, **no audio stream**, full decode without errors,
no black frames, healthy mean luma, and — using direct frame-to-frame
difference rather than ffmpeg's scene-cut score — that the picture really
changes in every quarter of the timeline.

`scripts/make-comparison-sheet.py` assembles the labelled 4×2 sheet
(`out/eli/eli_comparison_sheet.png`) from frames 30 / 120 / 210 / 270.

---

## Rendering in CI

The existing workflows (`render-bashe-v3.yml`, `bashe-preview.yml`) are hard-coded
to the BasheV3 and ContactSheet compositions; they cannot render these
compositions, and the prototypes were deliberately **not** renamed to those IDs.
See `ELI_CI.md` for the smallest workflow that renders both videos and the sheet.

```bash
# what CI needs to run, from psyche-studio/remotion
npm ci
npx remotion browser ensure
bash scripts/render-eli.sh
bash scripts/qa-eli.sh
python3 scripts/make-comparison-sheet.py   # needs Pillow
```
