# CI workflow for BasheV3 rendering

This document contains the **correct** GitHub Actions workflow YAML for rendering the
`BasheV3` Remotion composition. It is provided as a markdown file (not committed as
`.github/workflows/*.yml`) because the GitHub App used in this sandbox cannot create or
update workflow files.

To enable CI, paste the YAML below into `.github/workflows/render-bashe-v3.yml` via the
GitHub web UI (Actions → "set up a workflow yourself"), then trigger it manually from the
Actions tab (`workflow_dispatch`).

## Workflow YAML

```yaml
name: Render BasheV3 (V3 style comparison)

on:
  workflow_dispatch:

concurrency:
  group: render-bashe-v3
  cancel-in-progress: true

jobs:
  render:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"
          cache-dependency-path: psyche-studio/remotion/package-lock.json

      - name: Install dependencies
        working-directory: psyche-studio/remotion
        run: npm ci

      - name: Ensure Chromium for Remotion render
        working-directory: psyche-studio/remotion
        run: npx remotion browser ensure

      - name: Render BasheV3 composition
        working-directory: psyche-studio/remotion
        run: >
          npx remotion render BasheV3 out/bashe_v3.mp4
          --codec=h264
          --crf=20
          --width=1080
          --height=1920
          --fps=30
          --entry-point=./src/index.tsx

      - name: Upload render artifact
        uses: actions/upload-artifact@v4
        with:
          name: bashe_v3
          path: psyche-studio/remotion/out/bashe_v3.mp4
          retention-days: 14
```

## Notes

- **Audio is inside the composition.** `BasheV3` includes
  `<Audio src={staticFile("full_voice_cleaned.mp3")} />` with the MP3 committed to
  `psyche-studio/remotion/public/full_voice_cleaned.mp3`. There is **no** `--audio` CLI
  flag (Remotion does not have one); narration is muxed via the `<Audio>` component.
- Composition: id `BasheV3`, entry point `src/index.tsx`, 1080×1920, 30 fps,
  `durationInFrames = 1200` (40 s).
- Narration audio is the real cleaned voice
  (`psyche-studio/content/my_voice_cleaned_v3/full_voice_cleaned.mp3`, copied into the
  package's `public/` folder); no TTS, no regenerated audio.
- Trigger: `workflow_dispatch` only — no auto-render on push.
- Artifact: `bashe_v3.mp4`, retained 14 days.
