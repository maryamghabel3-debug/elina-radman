# CI for the two Eli 3D prototypes

The repository already has two render workflows, and **neither can render these
compositions** — this is the exact blocker:

| Workflow | Why it cannot render Eli |
|---|---|
| `.github/workflows/render-bashe-v3.yml` | hard-codes `npx remotion render BasheV3 … --audio=…` and uploads `out/bashe_v3.mp4`. No `EliCloudTest` / `EliLinesTest` path, and it forces an audio track, which these prototypes must not have. |
| `.github/workflows/bashe-preview.yml` | hard-codes `npx remotion still ContactSheet out/sheet.png` and `BasheV3`. Same problem. |
| `.github/workflows/render-worker.yml` | runs the Python `scripts/render_worker.py` queue; unrelated to Remotion compositions. |

Rather than rename the prototypes to `BasheV3` to get a green run, this file
holds the **smallest addition** that renders them. Per the task rules no file
under `.github/workflows/` was created or modified.

## Smallest ready-to-paste workflow

Save as `.github/workflows/render-eli-prototypes.yml` (via the GitHub web UI:
Actions → *New workflow* → *set up a workflow yourself*).

It is additive: a new file in its own concurrency group, touching no existing
workflow, no secrets and no production paths.

```yaml
name: Render Eli 3D prototypes

on:
  workflow_dispatch:
  push:
    branches: [arena/34e914e6-elina-radman]
    paths:
      - "psyche-studio/remotion/src/eli/**"
      - "psyche-studio/remotion/scripts/**"

concurrency:
  group: render-eli-prototypes
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  render:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"
          cache-dependency-path: psyche-studio/remotion/package-lock.json

      - name: Install dependencies
        working-directory: psyche-studio/remotion
        run: npm ci

      - name: Ensure browser
        working-directory: psyche-studio/remotion
        run: npx remotion browser ensure

      - name: Typecheck
        working-directory: psyche-studio/remotion
        run: npm run typecheck

      # Renders both 10 s videos and the four QA stills per version.
      # three.js needs ANGLE/SwiftShader in headless Chromium:
      # https://www.remotion.dev/docs/three
      - name: Render prototypes
        working-directory: psyche-studio/remotion
        env:
          REMOTION_GL: swangle
          REMOTION_CONCURRENCY: "2"
        run: bash scripts/render-eli.sh

      - name: QA (duration, resolution, fps, codec, silence, black frames, motion)
        working-directory: psyche-studio/remotion
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg
          cd ..
          bash remotion/scripts/qa-eli.sh

      - name: Comparison sheet
        working-directory: psyche-studio/remotion
        run: |
          python3 -m pip install --quiet pillow
          python3 scripts/make-comparison-sheet.py

      - name: Upload Eli Cloud video
        uses: actions/upload-artifact@v4
        with:
          name: eli_cloud_test
          path: psyche-studio/remotion/out/eli/eli_cloud_test.mp4
          retention-days: 30

      - name: Upload Eli Lines video
        uses: actions/upload-artifact@v4
        with:
          name: eli_lines_test
          path: psyche-studio/remotion/out/eli/eli_lines_test.mp4
          retention-days: 30

      - name: Upload comparison sheet + stills
        uses: actions/upload-artifact@v4
        with:
          name: eli_comparison_sheet
          path: |
            psyche-studio/remotion/out/eli/eli_comparison_sheet.png
            psyche-studio/remotion/out/eli/EliCloudTest_*.png
            psyche-studio/remotion/out/eli/EliLinesTest_*.png
          retention-days: 30
```

Artifact names produced by this workflow:

- `eli_cloud_test` → `eli_cloud_test.mp4`
- `eli_lines_test` → `eli_lines_test.mp4`
- `eli_comparison_sheet` → `eli_comparison_sheet.png` plus the eight QA stills

## Notes

- The workflow triggers on pushes to `arena/34e914e6-elina-radman`. If the work
  lands on a different branch, change that one line (or delete the `push` block
  and run it by hand with *Run workflow*).
- `bash scripts/render-eli.sh` picks the software-GL renderer automatically in
  CI; no extra configuration is required. `scripts/ensure-browser.mjs` is only
  needed in sandboxes that have no Chrome and cannot reach `remotion.media`.
- The QA step re-derives every fact from the encoded file (duration, size, fps,
  pixel format, absence of an audio stream, black frames, per-window motion) and
  fails the job if any check does not hold.
