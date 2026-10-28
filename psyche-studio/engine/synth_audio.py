"""Procedural, copyright-free audio bed and SFX (numpy only).

All sound is synthesized: no samples, no TTS, no external music.
  * warm pad: detuned sine triads on a slow minor progression, slow LFO
  * gentle pulse: soft low sine pluck, 80 BPM, deliberately unobtrusive
  * SFX: paper pop / paper whoosh / stamp / soft click / thought-bubble pop
Every generated fragment carries cosine fade in/out so it cannot click.
The music ducks under voice from a 50 ms RMS envelope; the master bus is
peak-limited and normalized to a narration-friendly -15 LUFS target.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np

SR = 44100


def _t(dur: float) -> np.ndarray:
    return np.linspace(0.0, dur, int(SR * dur), endpoint=False)


def _fade(x: np.ndarray, ms: float = 4.0) -> np.ndarray:
    n = min(int(SR * ms / 1000), len(x) // 2)
    if n < 2:
        return x
    f = 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, n))
    x[:n] *= f
    x[-n:] *= f[::-1]
    return x


def _one_pole_lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):  # warm, dull roll-off (no harsh highs)
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def _sine(freq: float, dur: float, detune: float = 0.0) -> np.ndarray:
    tt = _t(dur)
    f = freq * (1 + detune)
    return np.sin(2 * math.pi * f * tt)


def warm_pad(dur: float) -> np.ndarray:
    """Slow A-minor / F / C / G progression, soft detuned sines + LFO."""
    chords = [(110.0, 164.81, 220.0),   # Am
              (87.31, 130.81, 174.61),  # F
              (130.81, 196.0, 261.63),  # C
              (98.0, 146.83, 196.0)]    # G
    seg = dur / len(chords)
    out = np.zeros(int(SR * dur))
    for k, chord in enumerate(chords):
        tt = _t(seg + 0.4)
        layer = np.zeros_like(tt)
        for f in chord:
            layer += 0.33 * _sine(f, seg + 0.4, detune=0.0015)
            layer += 0.20 * _sine(f * 2, seg + 0.4, detune=-0.002)
        lfo = 0.75 + 0.25 * np.sin(2 * math.pi * 0.12 * tt + k)
        env = np.minimum(tt / 0.6, 1.0) * np.minimum((seg + 0.4 - tt) / 0.6, 1.0)
        layer *= lfo * np.clip(env, 0, 1)
        a = int(k * seg * SR)
        b = min(len(out), a + len(layer))
        out[a:b] += layer[: b - a] * 0.16
    return _one_pole_lowpass(out, 2600)


def gentle_pulse(dur: float) -> np.ndarray:
    """Soft low pluck every 0.75 s (80 BPM)."""
    out = np.zeros(int(SR * dur))
    step = 0.75
    k = 0
    while k * step < dur:
        t0 = int(k * step * SR)
        tt = _t(0.32)
        env = np.exp(-tt * 9)
        pluck = (np.sin(2 * math.pi * 130.81 * tt) * 0.8 +
                 np.sin(2 * math.pi * 196.0 * tt) * 0.3) * env
        n = min(len(pluck), len(out) - t0)
        out[t0:t0 + n] += pluck[:n] * 0.10
        k += 1
    return _one_pole_lowpass(out, 1200)


# ----------------------------- SFX library --------------------------------

def paper_pop() -> np.ndarray:
    tt = _t(0.07)
    noise = np.random.default_rng(7).standard_normal(len(tt))
    env = np.exp(-tt * 55)
    drop = np.sin(2 * math.pi * (420 * np.exp(-tt * 18) + 180) * tt)
    return _fade((0.6 * noise + 0.7 * drop) * env * 0.30, 2)


def paper_whoosh() -> np.ndarray:
    dur = 0.26
    tt = _t(dur)
    noise = np.random.default_rng(11).standard_normal(len(tt))
    # moving cutoff via time-varying one-pole
    out = np.zeros_like(noise)
    acc = 0.0
    for i, v in enumerate(noise):
        cutoff = 350 + 2600 * math.sin(math.pi * i / len(tt))
        a = math.exp(-2 * math.pi * cutoff / SR)
        acc = (1 - a) * v + a * acc
        out[i] = acc
    env = np.sin(math.pi * tt / dur) ** 2
    return _fade(out * env * 0.22, 3)


def stamp() -> np.ndarray:
    tt = _t(0.13)
    env = np.exp(-tt * 26)
    thump = np.sin(2 * math.pi * (95 * np.exp(-tt * 10) + 42) * tt)
    click = np.sin(2 * math.pi * 1800 * tt[: int(0.012 * SR)]) * \
        np.exp(-_t(0.012) * 400)
    x = thump * env * 0.40
    x[: len(click)] += click * 0.12
    return _fade(x, 1.5)


def soft_click() -> np.ndarray:
    tt = _t(0.035)
    env = np.exp(-tt * 120)
    return _fade(np.sin(2 * math.pi * 2100 * tt) * env * 0.12, 1)


def bubble_pop() -> np.ndarray:
    tt = _t(0.11)
    f = 380 + 420 * np.minimum(tt / 0.03, 1.0)
    env = np.exp(-tt * 22)
    return _fade(np.sin(2 * math.pi * f * tt) * env * 0.18, 2)


SFX = {"paper_pop": paper_pop, "paper_whoosh": paper_whoosh, "stamp": stamp,
       "soft_click": soft_click, "bubble_pop": bubble_pop}


def duck_under_voice(music: np.ndarray, voice: np.ndarray) -> np.ndarray:
    """Sidechain-style ducking from the voice 50 ms RMS envelope."""
    win = SR // 20
    n = min(len(music), len(voice)) // win
    vrms = np.sqrt(np.mean(voice[: n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    gate = vrms > 0.02
    gain = np.where(gate, 0.32, 1.0)  # music at 32 % under speech
    # smooth: 90 ms attack, 320 ms release
    g = np.empty_like(gain, dtype=np.float64)
    g[0] = gain[0]
    ga = math.exp(-0.05 / 0.09); gr = math.exp(-0.05 / 0.32)
    for i in range(1, len(gain)):
        c = ga if gain[i] < g[i - 1] else gr
        g[i] = c * g[i - 1] + (1 - c) * gain[i]
    full = np.repeat(g, win)
    full = np.concatenate([full, np.full(max(0, len(music) - len(full)), g[-1])])
    return music * full[: len(music)]


def place_sfx(events: list[dict], dur: float, skin: str) -> np.ndarray:
    """Lay SFX on the timeline event schedule (key moments get bigger SFX)."""
    track = np.zeros(int(SR * dur))
    for e in events:
        t = e.get("t", 0.0)
        if t >= dur:
            continue
        if e["type"] == "visual_beat":
            frag = soft_click() if skin == "glass" else bubble_pop()
            gain = 0.7
        elif e.get("is_key"):
            if e.get("role") == "negative":
                frag = stamp() if skin == "glass" else paper_pop()
            else:
                frag = paper_pop()
            gain = 1.0
        else:
            if int(t * 3) % 3 == 0:
                frag = paper_whoosh(); gain = 0.55
            else:
                continue
        i = int(t * SR)
        n = min(len(frag), len(track) - i)
        track[i: i + n] += frag[:n] * gain
    return track


def _ebur128(path: Path) -> float | None:
    ff = _ffmpeg()
    r = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(path),
                        "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        s = line.strip()
        if s.startswith("I:"):
            try:
                return float(s.split()[1])
            except (IndexError, ValueError):
                pass
    return None


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _loudness_tp(path: Path) -> tuple[float | None, float | None]:
    ff = _ffmpeg()
    r = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(path),
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i_lufs = tp = None
    for line in r.stderr.splitlines():
        s = line.strip()
        if s.startswith("I:"):
            try: i_lufs = float(s.split()[1])
            except (IndexError, ValueError): pass
        if s.startswith("Peak:") and ("dBTP" in s or "dBFS" in s):
            try: tp = float(s.split()[1])
            except (IndexError, ValueError): pass
    return i_lufs, tp


def _write_wav(path: Path, x: np.ndarray) -> None:
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def build_mix(voice: np.ndarray, events: list[dict], dur: float,
              out_wav: Path, skin: str = "glass") -> Path:
    """Music bed + pulse + SFX, ducked under voice, limited and normalized.

    Targets: integrated -15.5 LUFS (inside the -14..-16 band), true peak
    strictly below -1.5 dBTP, no clipping. Gain is computed from measured
    ebur128 values and capped by the true-peak ceiling.
    """
    music = warm_pad(dur) + gentle_pulse(dur)
    music = duck_under_voice(music, voice)
    sfx = place_sfx(events, dur, skin)
    n = min(len(music), len(voice), len(sfx))
    mix = voice[:n] * 0.92 + music[:n] + sfx[:n]
    # brick-wall-safe soft limiter
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    _write_wav(out_wav, mix)
    i_lufs, _tp = _loudness_tp(out_wav)
    if i_lufs is not None:
        # Measured gain loop toward -15.5 LUFS. alimiter runs with
        # level=false (its default auto-makeup would re-boost past the cap);
        # the 0.70 sample ceiling leaves intersample headroom so the measured
        # TRUE peak stays below -1.5 dBTP.
        tmp = out_wav.with_suffix(".pre.wav")
        out_wav.replace(tmp)
        current, gain_db, step = tmp, -15.5 - i_lufs, 0
        result = None
        for step in range(3):
            nxt = out_wav.with_suffix(f".step{step}.wav")
            subprocess.run(
                [_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                 "-i", str(current),
                 "-af", (f"volume={gain_db:.2f}dB,"
                         "alimiter=limit=0.70:level=false:attack=5:release=50"),
                 "-c:a", "pcm_s16le", str(nxt)], check=True)
            i_now, tp_now = _loudness_tp(nxt)
            result = nxt
            # stop when inside the -14..-16 LUFS band, or when no true-peak
            # headroom remains for another gain step
            if i_now is None or i_now >= -16.0 or (tp_now is not None and tp_now > -1.7):
                break
            gain_db = min(1.5, -15.5 - i_now)
            current = nxt
        if result is not None and result != out_wav:
            result.replace(out_wav)
        for stale in out_wav.parent.glob(out_wav.stem + ".step*.wav"):
            stale.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
    return out_wav
