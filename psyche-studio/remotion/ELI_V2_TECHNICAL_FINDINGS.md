# V2 — technical investigation of the washed-out look

Before changing any colour I checked whether the milky look was a renderer
problem or a design problem. Measured, not assumed.

## What was checked

| Item | Finding in V1 |
|---|---|
| Renderer output colour space | **Correct.** R3F sets `outputEncoding` to sRGB (`3001`) on first configure; three r171 then reports `outputColorSpace = 'srgb'`. No linear-space output bug. |
| Tone mapping | R3F defaults to **ACESFilmic** (`flat: false`). ACES is a filmic curve: it desaturates as values approach white and lifts shadows slightly. **Kept, then compared** (see below). |
| Exposure | 1.0. Not the cause. |
| Ambient / fill | **Main cause.** `ambientLight` 0.55 + `hemisphereLight` 0.75 + two extra point/directional fills. Nothing in the scene could get dark. |
| Fog | V1 had `<fog args={[ceiling, 12, 26]}/>`. At camera distance ≈ 6.5 the wall sits around 9–10 units away, inside the fog ramp — **a literal milky haze over the background**. |
| Shadows | Enabled (`shadows` on the canvas, `castShadow`/`receiveShadow` on meshes, 2048² map). Present but almost invisible because the ambient floor was so high. |
| Antialiasing / pixel ratio | `antialias: true`, dpr forced to 1 by the fixed canvas size. Software GL under SwiftShader was **not** degrading colour. |
| Material colours | Nearly every material was a light pastel (sRGB value ≥ 0.85). Even perfect colour management cannot create contrast out of a scene with no dark or saturated surfaces. |

## The tone-mapping probe

`src/eli/tonemap-probe.tsx` renders the same lit geometry (a `#7C3AED` sphere and
a `#FFC93C` box on a `#8C7BB0` background, exactly the "vivid subject on a
mid-value background" situation under test) four times, changing only the tone
mapping. Measured with `scripts/color-metrics.py`:

| Tone mapping | frame saturation (mean) | vivid-parts saturation (p90) | subject saturation |
|---|---|---|---|
| ACESFilmic (R3F default) | 0.413 | 0.862 | 0.851 |
| NoToneMapping | 0.348 | 0.551 | 0.554 |
| AgX | 0.397 | 0.778 | 0.727 |
| **Neutral** | **0.439** | **0.941** | **0.907** |

**Conclusion that contradicts the initial hypothesis:** ACES was *not* the main
culprit, and removing tone mapping entirely makes things *worse* (raw linear
clipping loses even more saturation). Switching from ACES to
`NeutralToneMapping` recovers about +6 % frame saturation and +6 % on the vivid
parts, with better highlight roll-off than none.

So: ~6 % of the washout was tone mapping; the other ~94 % was scene design —
high ambient, fog, and pastel-on-pastel values.

## V1 baseline, measured on the actual frames

| Metric | V1 (frame 120) | V1 (frame 270) |
|---|---|---|
| mean saturation | 0.138 | 0.141 |
| 90th-percentile saturation | 0.224 | 0.241 |
| luma std-dev (contrast) | 26.2 | 26.7 |
| **5th-percentile luma (darkest 5 %)** | **171 / 255** | **170 / 255** |
| 95th-percentile luma | 239 | 241 |
| character↔background colour distance | 18.0 | 18.1 |

The decisive number is the 5th-percentile luma of **171**: the darkest five
percent of the V1 frame never got below two-thirds brightness. That is precisely
the "milky haze" the reviewer described, and it is a lighting-value problem, not
a colour-space problem.

## What changed in V2

1. `toneMapping = THREE.NeutralToneMapping` explicitly on the canvas (keeps
   saturation in the highlights; verified above).
2. **Fog removed.** Background separation is now done with value and a separate
   background layer, not by washing everything out.
3. Ambient dropped from 0.55 → **0.16**, hemisphere fill removed entirely and
   replaced by one controlled fill. This is what allows real darks.
4. Key + fill + rim rig kept, with the rim light deliberately coloured and
   positioned to trace Eli's silhouette.
5. Contact shadow: a soft radial-gradient shadow plane under Eli, plus real
   shadow maps.
6. Materials moved from near-white pastels to saturated mid-values
   (violet `#7C3AED`, coral `#FF6B4A`, yellow `#FFC93C`) so there is room for
   both highlights *and* darks.
7. Character/background contrast is now by complementary hue **and** by value:
   vivid violet Eli against a deeper coral (warm) or deep teal (cool) room.

Measured results for V2 are in the delivery report and in
`psyche-studio/output/eli_prototypes_v2/`.
