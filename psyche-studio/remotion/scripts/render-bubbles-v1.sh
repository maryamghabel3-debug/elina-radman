#!/usr/bin/env bash
# Render the 12 s silent Eli–Elina bubble/mouth test without touching approved outputs.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="../output/eli_elina_bubbles_v1"
mkdir -p "$OUT"
# The sandbox browser/ffmpeg route is the repository's existing helper. The
# transient Python wheel is kept under ignored node_modules/.python-tools.
eval "$(PYTHONPATH="$PWD/node_modules/.python-tools${PYTHONPATH:+:$PYTHONPATH}" node scripts/ensure-browser.mjs)"
BROWSER_ARGS=()
if [[ -n "${REMOTION_BROWSER_EXECUTABLE:-}" ]]; then
  BROWSER_ARGS+=(--browser-executable="${REMOTION_BROWSER_EXECUTABLE}")
  BROWSER_ARGS+=(--gl="${REMOTION_GL:-swangle}")
fi

RAW="$OUT/eli_elina_bubbles_v1.render.mp4"
TMP="$OUT/eli_elina_bubbles_v1.tmp.mp4"
npx remotion render src/eli/bubbles-v1-index.tsx EliElinaBubblesV1 \
  "$RAW" \
  --codec=h264 --pixel-format=yuv420p --crf=18 \
  --width=1080 --height=1920 --fps=30 --concurrency=2 --log=error "${BROWSER_ARGS[@]}"
# The sandbox FFmpeg labels its full-range output yuvj420p; normalize the final
# delivery explicitly to limited-range yuv420p while keeping it silent.
ffmpeg -hide_banner -loglevel error -y -i "$RAW" -map 0:v:0 -an \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -color_range tv \
  -movflags +faststart "$TMP"
mv "$TMP" "$OUT/eli_elina_bubbles_v1.mp4"
rm -f "$RAW"
printf '\nRendered %s\n' "$OUT/eli_elina_bubbles_v1.mp4"
