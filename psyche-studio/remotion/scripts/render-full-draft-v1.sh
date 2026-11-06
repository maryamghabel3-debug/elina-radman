#!/usr/bin/env bash
# Render and mux the 35-turn full Eli–Elina voiced draft.
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(cd .. && pwd)"
OUT="$ROOT/output/eli_elina_full_draft_v1"
PUB="public/eli_elina_full_draft_v1"
CUES="$OUT/full_cues.json"
MIX="$ROOT/.draft_tools/full_dialogue_mix.wav"
RAW="$ROOT/.draft_tools/full_draft_remotion_raw.mp4"
FINAL="$OUT/eli_elina_full_draft_v1.mp4"
mkdir -p "$OUT" "$PUB" "$ROOT/.draft_tools"
[[ -f "$CUES" ]] || { echo "Missing $CUES; run build-full-draft-audio.py" >&2; exit 1; }
[[ -f "$MIX" ]] || { echo "Missing $MIX; run build-full-draft-audio.py" >&2; exit 1; }
cp "$CUES" "$PUB/full_cues.json"
cp "$MIX" "$PUB/full_dialogue_mix.wav"
cleanup() {
  rm -f "$PUB/full_cues.json" "$PUB/full_dialogue_mix.wav"
  rmdir "$PUB" 2>/dev/null || true
}
trap cleanup EXIT

eval "$(PYTHONPATH="$ROOT/.draft_tools${PYTHONPATH:+:$PYTHONPATH}" node scripts/ensure-browser.mjs)"
BROWSER_ARGS=()
if [[ -n "${REMOTION_BROWSER_EXECUTABLE:-}" ]]; then
  BROWSER_ARGS+=(--browser-executable="$REMOTION_BROWSER_EXECUTABLE")
  BROWSER_ARGS+=(--gl="${REMOTION_GL:-swangle}")
fi

npx remotion render src/eli/full-draft-index.tsx EliElinaFullDraft \
  "$RAW" \
  --codec=h264 --pixel-format=yuv420p --crf=18 \
  --width=1080 --height=1920 --fps=30 --concurrency=2 --log=error \
  "${BROWSER_ARGS[@]}"

FFMPEG="$(command -v ffmpeg)"
"$FFMPEG" -hide_banner -loglevel error -y -i "$RAW" -map 0:v:0 -map 0:a:0 \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -color_range tv \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$FINAL"
rm -f "$RAW"
printf '\nRendered %s\n' "$FINAL"
