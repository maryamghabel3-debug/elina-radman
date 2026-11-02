#!/usr/bin/env bash
# Real QA for Eli Cloud V2 (both palettes).
#
#   bash scripts/qa-eli-v2.sh
#   FFMPEG=/path/to/ffmpeg bash scripts/qa-eli-v2.sh
#
# Per video: 10.0 s / 300 frames, 1080x1920, 30 fps, h264, yuv420p, no audio
# stream, clean full decode, no black frames, healthy exposure, and real
# frame-to-frame motion in every quarter of the timeline.
#
# Then, per still: Eli fully inside the 9:16 safe area (y 250-1500), never
# touching a frame edge, and brighter than the background.
set -uo pipefail
cd "$(dirname "$0")/../.."
FFMPEG="${FFMPEG:-ffmpeg}"
OUT=remotion/out/v2
FAIL=0
pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=1; }

probe() {
  "$FFMPEG" -hide_banner -i "$1" 2>&1 | python3 -c '
import re, sys
text = sys.stdin.read()
out = {}
m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", text)
if m:
    out["duration"] = float(m.group(1))*3600 + float(m.group(2))*60 + float(m.group(3))
v = re.search(r"Stream #\d+:\d+.*?: Video: (\w+).*?, (\d+)x(\d+).*?, ([\d.]+) fps", text)
if v:
    out["codec"], out["width"], out["height"], out["fps"] = v.group(1), v.group(2), v.group(3), v.group(4)
p = re.search(r"Video: \w+.*?(yuv\w+)", text)
if p: out["pix_fmt"] = p.group(1)
out["audio_streams"] = len(re.findall(r"Stream #\d+:\d+.*?: Audio:", text))
for k, val in out.items(): print(f"{k}={val}")
'
}

check_video() {
  local file="$1" name="$2"
  echo "=== ${name}: ${file}"
  local kv duration width height fps codec pixfmt audio frames
  kv=$(probe "$file")
  duration=$(sed -n 's/^duration=//p' <<<"$kv" | xargs printf '%.3f')
  width=$(sed -n 's/^width=//p' <<<"$kv"); height=$(sed -n 's/^height=//p' <<<"$kv")
  fps=$(sed -n 's/^fps=//p' <<<"$kv"); codec=$(sed -n 's/^codec=//p' <<<"$kv")
  pixfmt=$(sed -n 's/^pix_fmt=//p' <<<"$kv"); audio=$(sed -n 's/^audio_streams=//p' <<<"$kv")
  echo "    ${duration}s  ${width}x${height}  ${fps} fps  ${codec}/${pixfmt}"

  [[ "$codec" == "h264" ]] && pass "codec h264" || fail "codec ${codec}"
  [[ "$width" == "1080" && "$height" == "1920" ]] && pass "resolution 1080x1920" || fail "resolution ${width}x${height}"
  python3 -c "import sys; sys.exit(0 if abs(float('${fps}')-30)<0.01 else 1)" && pass "30 fps" || fail "fps ${fps}"
  [[ "$pixfmt" == "yuv420p" || "$pixfmt" == "yuvj420p" ]] && pass "pixel format yuv420p (${pixfmt})" || fail "pixel format ${pixfmt}"
  [[ "$audio" == "0" ]] && pass "no audio stream (silent by design)" || fail "unexpected audio: ${audio}"
  python3 -c "import sys; sys.exit(0 if abs(float('${duration}')-10.0)<0.1 else 1)" && pass "duration 10.0 s" || fail "duration ${duration} s"

  local decode_out
  decode_out=$("$FFMPEG" -hide_banner -v error -xerror -i "$file" -map 0:v -f null - 2>&1)
  [[ -z "$decode_out" ]] && pass "full decode, no errors" || fail "decode errors: ${decode_out:0:200}"

  local black
  black=$("$FFMPEG" -hide_banner -i "$file" -vf "blackdetect=d=0.04:pic_th=0.97" -an -f null - 2>&1 | grep -c "black_start")
  [[ "$black" == "0" ]] && pass "no black frames" || fail "${black} black-frame events"

  local luma
  luma=$("$FFMPEG" -hide_banner -i "$file" -vf "signalstats,metadata=print:key=lavfi.signalstats.YAVG" -an -f null - 2>&1 | grep -o "YAVG=[0-9.]*" | cut -d= -f2)
  python3 -c "
import sys
v=[float(x) for x in '''$luma'''.split()]
print(f'    mean luma: min {min(v):.1f} max {max(v):.1f} avg {sum(v)/len(v):.1f}')
sys.exit(0 if 40 < sum(v)/len(v) < 200 else 1)" && pass "exposure healthy" || fail "mean luma out of range"

  local diffs
  diffs=$("$FFMPEG" -hide_banner -i "$file" -vf "scale=270:-1,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG" -an -f null - 2>&1 | grep -o "YAVG=[0-9.]*" | cut -d= -f2)
  python3 - "$fps" "$duration" <<PY
import sys
fps=float(sys.argv[1]); dur=float(sys.argv[2])
vals=[float(x) for x in """$diffs""".split()]
moving=sum(1 for v in vals if v>0.12)
print(f"    frame-to-frame change: {moving}/{len(vals)} frames moving ({100*moving/max(1,len(vals)):.0f}%)")
bad=[]
for a,b,label in [(0,2,"calm"),(2,5,"curious"),(5,8,"worried"),(8,10,"resolved")]:
    seg=vals[max(0,int(a*fps)-1):int(b*fps)-1]
    if not seg: bad.append(label); continue
    pct=100*sum(1 for v in seg if v>0.12)/len(seg)
    print(f"    {a}-{b}s ({label}): {pct:.0f}% frames move, mean delta {sum(seg)/len(seg):.2f}")
    if pct < 50: bad.append(label)
sys.exit(1 if bad else 0)
PY
  [[ $? -eq 0 ]] && pass "motion in all four beats" || fail "static beat detected"
  echo
}

check_video "$OUT/eli_cloud_v2_warm.mp4" "V2-warm"
check_video "$OUT/eli_cloud_v2_cool.mp4" "V2-cool"

echo "=== framing + contrast on the eight stills"
python3 remotion/scripts/frame-check.py "$OUT"/EliCloudV2Warm_30.png "$OUT"/EliCloudV2Warm_120.png "$OUT"/EliCloudV2Warm_210.png "$OUT"/EliCloudV2Warm_270.png "$OUT"/EliCloudV2Cool_30.png "$OUT"/EliCloudV2Cool_120.png "$OUT"/EliCloudV2Cool_210.png "$OUT"/EliCloudV2Cool_270.png > /tmp/framing.json
python3 - <<'PY'
import json
rows = json.load(open('/tmp/framing.json'))
fail = False
for r in rows:
    name = r['file'].split('/')[-1]
    ok_safe = r['inside_safe_area_250_1500']
    ok_crop = r['not_cropped_by_edges']
    ok_bright = r['char_contrast_ratio'] >= 1.15
    print(f"  {'PASS' if ok_safe else 'FAIL'} {name}: inside safe area (top {r['bbox']['top']}, bottom {r['bbox']['bottom']})")
    print(f"  {'PASS' if ok_crop else 'FAIL'} {name}: not cropped (L {r['bbox']['left']}, R {r['bbox']['right']})")
    print(f"  {'PASS' if ok_bright else 'FAIL'} {name}: Eli brighter than room (ratio {r['char_contrast_ratio']})")
    fail = fail or not (ok_safe and ok_crop and ok_bright)
raise SystemExit(1 if fail else 0)
PY
[[ $? -eq 0 ]] || FAIL=1

echo
if [[ "$FAIL" == "0" ]]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit "$FAIL"
