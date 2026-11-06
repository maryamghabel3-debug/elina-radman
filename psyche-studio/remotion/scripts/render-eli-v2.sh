#!/usr/bin/env bash
# Eli Cloud V2 — two palette variants, 10 s, 1080x1920, 30 fps, h264/yuv420p,
# silent by design (no --audio flag anywhere).
#
#   bash scripts/render-eli-v2.sh            # stills + both videos
#   bash scripts/render-eli-v2.sh --stills   # stills only (fast)
#
# In a sandbox without a browser/ffmpeg: eval "$(node scripts/ensure-browser.mjs)"
set -euo pipefail
cd "$(dirname "$0")/.."

BROWSER_ARGS=()
if [[ -n "${REMOTION_BROWSER_EXECUTABLE:-}" ]]; then
  BROWSER_ARGS+=(--browser-executable="${REMOTION_BROWSER_EXECUTABLE}")
  BROWSER_ARGS+=(--gl="${REMOTION_GL:-swangle}")
fi

OUT=out/v2
mkdir -p "$OUT"

STILLS=0
if [[ "${1:-}" == "--stills" ]]; then STILLS=1; fi

# QA stills at 1 s, 4 s, 7 s, 9 s (frames 30, 120, 210, 270)
for comp in EliCloudV2Warm EliCloudV2Cool; do
  for f in 30 120 210 270; do
    echo "== still ${comp} @ frame ${f}"
    npx remotion still src/eli/v2/index.tsx "$comp" "$OUT/${comp}_${f}.png" \
      --frame="$f" --log=error "${BROWSER_ARGS[@]}"
  done
done

if [[ "$STILLS" == "1" ]]; then echo "stills -> $OUT"; exit 0; fi

for pair in "EliCloudV2Warm:eli_cloud_v2_warm" "EliCloudV2Cool:eli_cloud_v2_cool"; do
  comp="${pair%%:*}"; name="${pair##*:}"
  echo "== render ${comp} -> ${name}.mp4"
  npx remotion render src/eli/v2/index.tsx "$comp" "$OUT/${name}.mp4" \
    --codec=h264 --pixel-format=yuv420p --crf=17 \
    --width=1080 --height=1920 --fps=30 \
    --concurrency="${REMOTION_CONCURRENCY:-2}" \
    --log=error "${BROWSER_ARGS[@]}"
done
ls -la "$OUT"
