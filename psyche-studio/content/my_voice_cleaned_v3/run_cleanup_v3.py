"""Driver: clean the four active V3 narration stems (non-destructive)."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine import audio_clean_v3 as ac

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "content/my_voice_v2"
OUT = ROOT / "content/my_voice_cleaned_v3"
WORK = Path("/tmp/v3_clean_work")
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

FF = ac.ffmpeg()
report = {"atempo": ac.ATEMPO, "pause_limit_s": ac.PAUSE_LIMIT_S,
          "pause_kept_s": ac.PAUSE_KEEP_S, "pad_s": ac.PAD_S, "stems": []}
wavs = []
for i in range(1, 5):
    src = SRC / f"s0{i}.mp3"
    i_before, _ = ac.ebur128(src)
    res, wav = ac.clean_piece(f"cleaned_s{i}", src, WORK)
    i_after, tp_after = ac.ebur128(wav)
    res.loudness_before_lufs, res.loudness_after_lufs, res.true_peak_after_dbtp = \
        round(i_before, 2), round(i_after, 2), round(tp_after, 2)
    import shutil
    out_wav = OUT / f"cleaned_s{i}.wav"
    shutil.copyfile(wav, out_wav)
    ac.encode_mp3(wav, OUT / f"cleaned_s{i}.mp3")
    wavs.append(out_wav)
    d = res.__dict__.copy()
    d["time_saved_s"] = round(res.original_duration_s - res.cleaned_duration_s, 3)
    report["stems"].append(d)
    print(f"s{i}: {res.original_duration_s}s -> {res.cleaned_duration_s}s "
          f"(saved {d['time_saved_s']}s) I {i_before} -> {i_after} LUFS TP {tp_after} "
          f"pauses={len(res.pauses_compressed)} clicks={len(res.clicks)} "
          f"risky={len(res.risky_cuts)}", flush=True)

# Full voice: filter concat with 0.30 s anullsrc gaps between stems.
gap = 0.30
inputs = []
for w in wavs:
    inputs += ["-i", str(w)]
fc = []
n = len(wavs)
for k in range(n):
    fc.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=mono[a{k}]")
chain = "".join(f"[a{k}]" for k in range(n))
# interleave gaps
parts = []
for k in range(n):
    parts.append(f"[a{k}]")
    if k < n - 1:
        parts.append(f"anullsrc=r=44100:cl=mono:d={gap}[g{k}]")
fc = []
for k in range(n):
    fc.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=mono[a{k}]")
for k in range(n - 1):
    fc.append(f"anullsrc=r=44100:cl=mono:d={gap}[g{k}]")
seq = "".join((f"[a{k}][g{k}]" if k < n - 1 else f"[a{k}]") for k in range(n))
fc.append(f"{seq}concat=n={2*n-1}:v=0:a=1[mix]")
cmd = [FF, "-y", "-hide_banner", "-loglevel", "error", *inputs,
       "-filter_complex", ";".join(fc), "-map", "[mix]",
       "-c:a", "libmp3lame", "-b:a", "128k", str(OUT / "full_voice_cleaned.mp3")]
subprocess.run(cmd, check=True)
full_i, full_tp = ac.ebur128(OUT / "full_voice_cleaned.mp3")
report["full_voice"] = {"gap_s": gap, "integrated_lufs": round(full_i, 2),
                        "true_peak_dbtp": round(full_tp, 2)}
(OUT / "cleanup_report_data.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print("full voice:", report["full_voice"])
print("DONE")
