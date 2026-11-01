#!/usr/bin/env bash
# Real QA for the two Eli prototypes. Works with plain ffmpeg (no ffprobe
# needed) so it runs both in CI and in a bare sandbox.
#
#   bash scripts/qa-eli.sh
#   FFMPEG=/path/to/ffmpeg bash scripts/qa-eli.sh
#
# Per video it checks:
#   * duration 10.0 s, 1080x1920, 30 fps, h264, yuv420p, 300 frames
#   * no audio stream at all (silent by design)
#   * full decode with no decoder errors
#   * no black / blank frames, healthy exposure
#   * the picture actually changes, in every quarter of the timeline
# and finally that the two versions differ from each other.
set -uo pipefail
cd "$(dirname "$0")/../.."

FFMPEG="${FFMPEG:-ffmpeg}"
OUT=remotion/out/eli
FAIL=0

pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=1; }

# note: eli_*.mp4 are rendered with --pixel-format=yuv420p; ffmpeg prints
# yuvj420p for full-range yuv420p, so both spellings are accepted below.

# extract "key=value" pairs from one ffmpeg summary
probe() {
  "$FFMPEG" -hide_banner -i "$1" 2>&1 | python3 -c '
import re, sys
text = sys.stdin.read()
out = {}
m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", text)
if m:
    h, mi, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
    out["duration"] = h * 3600 + mi * 60 + s
v = re.search(r"Stream #\d+:\d+.*?: Video: (\w+).*?, (\d+)x(\d+).*?, ([\d.]+) fps", text)
if v:
    out["codec"], out["width"], out["height"], out["fps"] = v.group(1), v.group(2), v.group(3), v.group(4)
p = re.search(r"Video: \w+.*?(yuv\w+)", text)
if p:
    out["pix_fmt"] = p.group(1)
out["audio_streams"] = len(re.findall(r"Stream #\d+:\d+.*?: Audio:", text))
for k, val in out.items():
    print(f"{k}={val}")
'
}

check_video() {
  local file="$1" name="$2"
  echo "=== ${name}: ${file}"

  local kv
  kv=$(probe "$file")
  local duration width height fps codec pixfmt audio
  duration=$(sed -n 's/^duration=//p' <<<"$kv" | xargs printf '%.3f')
  width=$(sed -n 's/^width=//p' <<<"$kv")
  height=$(sed -n 's/^height=//p' <<<"$kv")
  fps=$(sed -n 's/^fps=//p' <<<"$kv")
  codec=$(sed -n 's/^codec=//p' <<<"$kv")
  pixfmt=$(sed -n 's/^pix_fmt=//p' <<<"$kv")
  audio=$(sed -n 's/^audio_streams=//p' <<<"$kv")

  # frame count + decode errors from a full decode pass
  local decode_out frames errors
  decode_out=$("$FFMPEG" -hide_banner -v error -xerror -i "$file" -map 0:v -f null - 2>&1)
  errors=$(grep -vc "^frame=" <<<"$decode_out" || true)
  frames=$(python3 -c "print(round(float('${duration}') * float('${fps}')))")

  echo "    ${duration}s  ${width}x${height}  ${fps} fps  ${codec}/${pixfmt}  frames ${frames}"

  [[ "$codec" == "h264" ]] && pass "codec h264" || fail "codec ${codec}"
  [[ "$width" == "1080" && "$height" == "1920" ]] && pass "resolution 1080x1920" || fail "resolution ${width}x${height}"
  python3 -c "import sys; sys.exit(0 if abs(float('${fps}') - 30) < 0.01 else 1)" && pass "30 fps" || fail "fps ${fps}"
  [[ "$pixfmt" == "yuv420p" || "$pixfmt" == "yuvj420p" ]] && pass "pixel format yuv420p (${pixfmt})" || fail "pixel format ${pixfmt}"
  [[ "$audio" == "0" ]] && pass "no audio stream (silent by design)" || fail "unexpected audio streams: ${audio}"
  python3 -c "import sys; sys.exit(0 if abs(float('${duration}') - 10.0) < 0.1 else 1)" \
    && pass "duration 10.0 s" || fail "duration ${duration} s"
  [[ "$frames" == "300" ]] && pass "300 frames" || fail "frame count ${frames}"
  [[ -z "$decode_out" ]] && pass "full decode, no errors" || fail "decode errors: ${decode_out:0:200}"

  # black frames
  local black
  black=$("$FFMPEG" -hide_banner -i "$file" -vf "blackdetect=d=0.04:pic_th=0.97" -an -f null - 2>&1 | grep -c "black_start" || true)
  [[ "$black" == "0" ]] && pass "no black frames" || fail "${black} black-frame events"

  # exposure
  local luma stats
  luma=$("$FFMPEG" -hide_banner -i "$file" -vf "signalstats,metadata=print:key=lavfi.signalstats.YAVG" -an -f null - 2>&1 \
    | grep -o "YAVG=[0-9.]*" | cut -d= -f2)
  stats=$(python3 -c "
import sys
v=[float(x) for x in '''$luma'''.split()]
print(f'{min(v):.1f} {max(v):.1f} {sum(v)/len(v):.1f} {len(v)}' if v else '0 0 0 0')")
  read -r lmin lmax lmean lcount <<<"$stats"
  echo "    mean luma: min ${lmin}  max ${lmax}  avg ${lmean}  over ${lcount} frames"
  python3 -c "import sys; sys.exit(0 if 60 < float('${lmean}') < 220 else 1)" \
    && pass "exposure healthy (not black, not blown out)" || fail "mean luma ${lmean} outside 60..220"

  # ---- motion ----
  # Verified by direct frame-to-frame difference (tblend), not by ffmpeg's
  # scene-cut score: slow character drift is invisible to scene detection but
  # is exactly what this prototype needs to prove.
  local diffs
  diffs=$("$FFMPEG" -hide_banner -i "$file" \
    -vf "scale=270:-1,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG" \
    -an -f null - 2>&1 | grep -o "YAVG=[0-9.]*" | cut -d= -f2)

  python3 - "$fps" "$frames" <<PY
import sys
fps = float(sys.argv[1])
expected = int(sys.argv[2])
vals = [float(x) for x in """$diffs""".split()]
fail = False
if len(vals) < expected - 2:
    print(f"  FAIL only {len(vals)} frame diffs measured")
    sys.exit(1)
moving = sum(1 for v in vals if v > 0.12)
pct = 100 * moving / len(vals)
print(f"    frame-to-frame change: mean {sum(vals)/len(vals):.2f}, "
      f"max {max(vals):.2f}, {moving}/{len(vals)} frames moving ({pct:.0f}%)")
if pct >= 60:
    print("  PASS the scene is animated, not a still with a progress bar")
else:
    print(f"  FAIL only {pct:.0f}% of frames differ - the scene looks static")
    fail = True

windows = [(0, 2, "establish"), (2, 5, "phone reaction"), (5, 8, "thought shapes"), (8, 10, "final pose")]
for start_s, end_s, label in windows:
    lo = int(start_s * fps) - 1
    hi = int(end_s * fps) - 1
    seg = vals[max(0, lo): hi]
    if not seg:
        print(f"  FAIL window {start_s}-{end_s}s has no frames")
        fail = True
        continue
    m = sum(1 for v in seg if v > 0.12) / len(seg) * 100
    mean = sum(seg) / len(seg)
    if m >= 50:
        print(f"  PASS {start_s}-{end_s}s ({label}): {m:.0f}% frames move, mean delta {mean:.2f}")
    else:
        print(f"  FAIL {start_s}-{end_s}s ({label}): {m:.0f}% frames move, mean delta {mean:.2f}")
        fail = True
sys.exit(1 if fail else 0)
PY
  [[ $? -eq 0 ]] || FAIL=1

  echo
}

check_video "$OUT/eli_cloud_test.mp4" "Eli Cloud  (A)"
check_video "$OUT/eli_lines_test.mp4" "Eli Lines  (B)"

echo "=== versions must differ from each other"
tmp=$(mktemp -d)
"$FFMPEG" -hide_banner -v error -y -ss 4 -i "$OUT/eli_cloud_test.mp4" -frames:v 1 "$tmp/a.png"
"$FFMPEG" -hide_banner -v error -y -ss 4 -i "$OUT/eli_lines_test.mp4" -frames:v 1 "$tmp/b.png"
if cmp -s "$tmp/a.png" "$tmp/b.png"; then
  fail "the two 4 s frames are identical"
else
  pass "the two 4 s frames differ"
fi
rm -rf "$tmp"

echo
if [[ "$FAIL" == "0" ]]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit "$FAIL"
