"""Project 001 V3 narration cleanup.

Non-destructive pipeline (sources are never modified):

  1. decode each source ONCE to mono 44.1 kHz PCM (numpy)
  2. click/transient attenuation at the head and tail (short cosine fades)
  3. short-time RMS voice activity -> trim lead/trail room tone (120 ms pad)
  4. pause compression: internal non-speech runs > 0.75 s become 0.25 s,
     spliced with 8 ms cosine crossfades (no hard cuts, no dead silence)
  5. ffmpeg: atempo 1.12 -> highpass 95 Hz -> 250 Hz -4 dB (boominess)
     -> 3 kHz +2 dB presence -> mild compressor -> conservative afftdn
     -> two-pass-free single loudnorm (I=-16, TP=-2.0)
  6. encode each stem once to WAV (PCM) and once to MP3 128 kbps

A piecewise time map (original time -> cleaned time) is emitted so the
kinetic timeline can align recognizer timestamps without re-transcription.
"""
from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 44100
WIN_MS = 20
WIN = SR * WIN_MS // 1000
PAD_S = 0.12
PAUSE_LIMIT_S = 0.75
PAUSE_KEEP_S = 0.25
XFADE_S = 0.008
ATEMPO = 1.12


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode_pcm(src: Path) -> np.ndarray:
    """Single decode to float64 mono PCM at SR."""
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", "-f", "wav", "pipe:1"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    import wave
    import io
    with wave.open(io.BytesIO(raw)) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.astype(np.float64) / 32768.0


def rms_envelope(x: np.ndarray) -> np.ndarray:
    n = len(x) // WIN
    return np.sqrt(np.mean(x[:n * WIN].reshape(n, WIN) ** 2, axis=1) + 1e-12)


def detect_clicks(x: np.ndarray) -> list[dict]:
    """Broadband impulse candidates: single-sample jumps > 0.45 FS, plus
    head/tail transients (the shared encoder blip lives on the first samples,
    so an absolute-level scan of the edge regions is also required)."""
    out = []
    d = np.abs(np.diff(x))
    for i in np.where(d > 0.45)[0]:
        out.append({"sample": int(i), "time_s": round(i / SR, 4),
                    "jump_fs": round(float(d[i]), 3),
                    "location": "head" if i < SR * 0.05 else
                                ("tail" if i > len(x) - SR * 0.05 else "internal")})
    # Edge transients: high level inside the first/last 10 ms followed by a
    # sharp drop (the shared encoder blip sits on samples 0..3 then silence).
    for loc, seg, base in (("head", x[: int(0.01 * SR)], 0),
                           ("tail", x[-int(0.01 * SR):], len(x) - int(0.01 * SR))):
        for k in range(len(seg) - 1):
            if abs(seg[k]) > 0.45 and abs(seg[k]) - abs(seg[k + 1]) > 0.3:
                out.append({"sample": base + k, "time_s": round((base + k) / SR, 4),
                            "level_fs": round(float(abs(seg[k])), 3),
                            "location": loc})
                break
    return out


def fade_edges(x: np.ndarray, head_s: float = 0.006, tail_s: float = 0.008) -> None:
    h = int(head_s * SR); t = int(tail_s * SR)
    x[:h] *= 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, h))
    x[-t:] *= 0.5 + 0.5 * np.cos(np.linspace(0, math.pi, t))


def speech_windows(env: np.ndarray) -> np.ndarray:
    """Adaptive gate: max(-40 dBFS, noise floor + 10 dB), floor from 10% quietest."""
    db = 20 * np.log10(np.maximum(env, 1e-9))
    noise = np.percentile(db, 10)
    gate = max(-40.0, noise + 10.0)
    return db > gate, gate, float(noise)


def splice(x: np.ndarray, keep_ranges: list[tuple[int, int]],
           kept_silence: list[tuple[int, int]]) -> np.ndarray:
    """Concatenate kept ranges, inserting 0.25 s of original room tone per
    removed pause, with 8 ms cosine crossfades at every junction."""
    pieces = []
    xk = int(XFADE_S * SR)
    for k, (a, b) in enumerate(keep_ranges):
        pieces.append(x[a:b].copy())
        if k < len(kept_silence):
            sa, sb = kept_silence[k]
            pieces.append(x[sa:sb].copy())
    if not pieces:
        return x
    out = pieces[0]
    for p in pieces[1:]:
        m = min(xk, len(out) // 2, len(p) // 2)
        if m < 2:
            out = np.concatenate([out, p]); continue
        fade = 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, 2 * m))
        head, tail = out[:-m], out[-m:].copy()
        ph, pt = p[:m].copy(), p[m:]
        tail *= 1 - fade[:m]; ph *= fade[:m]
        out = np.concatenate([head, tail + ph, pt])
    return out


@dataclass
class CleanResult:
    name: str
    src: str
    original_duration_s: float
    cleaned_duration_s: float = 0.0
    lead_removed_s: float = 0.0
    trail_removed_s: float = 0.0
    pauses_compressed: list[dict] = field(default_factory=list)
    clicks: list[dict] = field(default_factory=list)
    risky_cuts: list[str] = field(default_factory=list)
    gate_dbfs: float = 0.0
    noise_floor_dbfs: float = 0.0
    time_map: list[list[float]] = field(default_factory=list)  # [orig_t, clean_t]
    loudness_before_lufs: float | None = None
    loudness_after_lufs: float | None = None
    true_peak_after_dbtp: float | None = None


def clean_piece(name: str, src: Path, work: Path) -> CleanResult:
    x = decode_pcm(src)
    res = CleanResult(name=name, src=str(src), original_duration_s=round(len(x) / SR, 3))
    res.clicks = detect_clicks(x)
    # The transcription-pass inventory found a shared 4-sample encoder blip at
    # t=0. In the piped WAV decode ffmpeg pads encoder delay as leading silence
    # (no impulse survives: verify max sample jump), and the VAD head trim
    # (>=0.72 s on every stem) plus a 6/8 ms cosine edge fade remove it
    # regardless. Record the handling explicitly for the report.
    max_jump = float(np.max(np.abs(np.diff(x)))) if len(x) > 1 else 0.0
    res.edge_artifact_handling = {
        "known_t0_blip": "4-sample encoder transient documented in TRANSCRIPT_REPORT.md",
        "max_sample_jump_fs": round(max_jump, 4),
        "impulses_surviving_decode": len(res.clicks),
        "mitigation": "6 ms cosine head fade + 8 ms tail fade + VAD head trim",
    }
    fade_edges(x)  # attenuates the shared t=0 encoder blip and any tail impulse

    env = rms_envelope(x)
    voiced, gate, noise = speech_windows(env)
    res.gate_dbfs, res.noise_floor_dbfs = round(gate, 2), round(noise, 2)
    vi = np.where(voiced)[0]
    if len(vi) < 2:
        raise RuntimeError(f"{name}: no speech detected above {gate} dBFS")

    first = max(0, int((vi[0] * WIN_MS / 1000 - PAD_S) * SR))
    last = min(len(x), int(((vi[-1] + 1) * WIN_MS / 1000 + PAD_S) * SR))
    res.lead_removed_s = round(first / SR, 3)
    res.trail_removed_s = round((len(x) - last) / SR, 3)
    body = x[first:last]

    # Internal non-speech runs (window indices relative to body).
    bn = len(body) // WIN
    bv = voiced[:bn]
    runs, start = [], None
    for j, v in enumerate(bv):
        if not v and start is None:
            start = j
        if v and start is not None:
            runs.append((start, j)); start = None
    if start is not None:
        runs.append((start, bn))

    keep_ranges, kept_silence = [], []
    cursor = 0
    for (ws, we) in runs:
        run_s = (we - ws) * WIN_MS / 1000
        if run_s <= PAUSE_LIMIT_S:
            continue
        a, b = ws * WIN, we * WIN
        # borderline pauses sit within 0.10 s of the 0.75 s threshold:
        # the splice keeps 0.25 s, so speech is never cut, but timing margin
        # against VAD misclassification is small -> flag for the report.
        if run_s < PAUSE_LIMIT_S + 0.10:
            res.risky_cuts.append(
                f"borderline pause {run_s:.2f}s at orig "
                f"~{res.lead_removed_s + ws * WIN_MS / 1000:.2f}s "
                f"(within 0.10s of the {PAUSE_LIMIT_S}s threshold)")
        keep_ranges.append((cursor, a))
        tone_a = a + max(0, (b - a) // 2 - int(PAUSE_KEEP_S * SR) // 2)
        kept_silence.append((tone_a, tone_a + int(PAUSE_KEEP_S * SR)))
        cursor = b
        res.pauses_compressed.append(
            {"orig_start_s": round(first / SR + ws * WIN_MS / 1000, 3),
             "orig_length_s": round(run_s, 3), "kept_s": PAUSE_KEEP_S,
             "removed_s": round(run_s - PAUSE_KEEP_S, 3)})
    keep_ranges.append((cursor, len(body)))
    if kept_silence:
        body = splice(body, keep_ranges, kept_silence)

    edited_wav = work / f"{name}_edited.wav"
    _write_wav(edited_wav, body)

    # Time map anchors (pre-atempo), then atempo divides elapsed time.
    anchors = [(0.0, 0.0)]
    removed = 0.0
    for p in res.pauses_compressed:
        removed += p["removed_s"]
        orig_t = res.lead_removed_s + p["orig_start_s"] + p["orig_length_s"]
        clean_pre = (orig_t - res.lead_removed_s - removed)
        anchors.append([round(orig_t, 3), round(clean_pre / ATEMPO, 3)])

    # ffmpeg: atempo -> EQ -> compressor -> conservative denoise -> loudnorm.
    # Two-pass loudnorm for an accurate -16 LUFS / -2 dBTP target.
    base_af = (f"atempo={ATEMPO},"
               f"highpass=f=95,"
               f"equalizer=f=250:t=q:w=1.5:g=-4,"
               f"equalizer=f=3000:t=q:w=2:g=2,"
               f"acompressor=threshold=-20dB:ratio=2.5:attack=12:release=180:makeup=2,"
               f"afftdn=nr=8:nf=-40")
    measure = subprocess.run(
        [ffmpeg(), "-hide_banner", "-nostats", "-i", str(edited_wav),
         "-af", base_af + ",loudnorm=I=-16:TP=-2.0:LRA=11:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True, check=True)
    j = json.loads(measure.stderr[measure.stderr.rindex("{"):measure.stderr.rindex("}") + 1])
    af2 = (base_af +
           f",loudnorm=I=-16:TP=-2.0:LRA=11:linear=true:"
           f"measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
           f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:"
           f"offset={j['target_offset']}")
    out_wav = work / f"{name}_clean.wav"
    subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(edited_wav), "-af", af2, "-ar", str(SR),
                    "-c:a", "pcm_s16le", str(out_wav)], check=True)
    # final anchors: extend map to full duration
    dur = _wav_duration(out_wav)
    res.cleaned_duration_s = round(dur, 3)
    total_removed = res.lead_removed_s + res.trail_removed_s + \
        sum(p["removed_s"] for p in res.pauses_compressed)
    anchors.append([round(res.original_duration_s, 3),
                    round((res.original_duration_s - total_removed) / ATEMPO, 3)])
    res.time_map = anchors
    return res, out_wav


def _write_wav(path: Path, x: np.ndarray) -> None:
    import wave
    x16 = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x16 * 32767).astype(np.int16).tobytes())


def _wav_duration(path: Path) -> float:
    import wave
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def ebur128(path: Path) -> tuple[float | None, float | None]:
    r = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(path),
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = tp = None
    for line in r.stderr.splitlines():
        s = line.strip()
        if s.startswith("I:"):
            try: i = float(s.split()[1])
            except (IndexError, ValueError): pass
        if s.startswith("Peak:") and ("dBTP" in s or "dBFS" in s):
            try: tp = float(s.split()[1])
            except (IndexError, ValueError): pass
    return i, tp


def encode_mp3(wav: Path, mp3: Path) -> None:
    subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "128k",
                    str(mp3)], check=True)


def map_time(t: float, anchors: list[list[float]]) -> float:
    """Map an original-timestamp to cleaned-timestamp through piecewise anchors."""
    if t <= anchors[0][0]:
        return max(0.0, t / ATEMPO)
    for (o0, c0), (o1, c1) in zip(anchors, anchors[1:]):
        if o0 <= t <= o1:
            if o1 == o0:
                return c0
            return c0 + (t - o0) * (c1 - c0) / (o1 - o0)
    return anchors[-1][1]
