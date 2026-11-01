#!/usr/bin/env bash
# Render the two Eli 3D prototypes (10 s, 1080x1920, 30 fps, h264/yuv420p, silent).
#
#   bash scripts/render-eli.sh              # videos + QA stills
#   bash scripts/render-eli.sh --stills     # QA stills only (fast)
#
# On GitHub Actions the browser is provided by `npx remotion browser ensure`.
# In a sandbox without a browser or ffmpeg, first run:
#   eval "$(node scripts/ensure-browser.mjs)"
set -euo pipefail
cd "$(dirname "$0")/.."

BROWSER_ARGS=()
if [[ -n "${REMOTION_BROWSER_EXECUTABLE:-}" ]]; then
  BROWSER_ARGS+=(--browser-executable="${REMOTION_BROWSER_EXECUTABLE}")
  # software WebGL is the only option on a GPU-less sandbox
  BROWSER_ARGS+=(--gl="${REMOTION_GL:-swangle}")
fi

OUT=out/eli
mkdir -p "$OUT"

STILLS=0
if [[ "${1:-}" == "--stills" ]]; then STILLS=1; fi

# --- QA stills: ~1 s, 4 s, 7 s, 9 s (frames 30, 120, 210, 270) ---
for comp in EliCloudTest EliLinesTest; do
  for f in 30 120 210 270; do
    echo "== still ${comp} frame ${f}"
    npx remotion still src/eli/index.tsx "$comp" "$OUT/${comp}_${f}.png" \
      --frame="$f" --log=error "${BROWSER_ARGS[@]}"
  done
done

if [[ "$STILLS" == "1" ]]; then
  echo "stills written to $OUT"
  exit 0
fi

# --- videos ---
# No --audio flag anywhere: both files are silent by design.
for pair in "EliCloudTest:eli_cloud_test" "EliLinesTest:eli_lines_test"; do
  comp="${pair%%:*}"
  name="${pair##*:}"
  echo "== render ${comp} -> ${name}.mp4"
  npx remotion render src/eli/index.tsx "$comp" "$OUT/${name}.mp4" \
    --codec=h264 --pixel-format=yuv420p --crf=18 \
    --width=1080 --height=1920 --fps=30 \
    --concurrency="${REMOTION_CONCURRENCY:-2}" \
    --log=error "${BROWSER_ARGS[@]}"
done

ls -la "$OUT"
