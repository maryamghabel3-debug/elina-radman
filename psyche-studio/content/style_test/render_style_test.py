"""Render the V3 style comparison test (first 40 s of cleaned_s1).

Two procedural skins over the same narration + timeline:
  style_test_papercut.mp4  (engine.skins.papercut.PaperCut)
  style_test_glass.mp4     (engine.skins.glass.GlassKinetic)

Frames are streamed frame-by-frame into ffmpeg (no full-frame buffering),
encoded H.264 CRF 20 and muxed with the procedurally synthesized audio bed.
No AI images, no TTS: every pixel and every sound is generated in code.
"""
from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine import config, synth_audio, video  # noqa: E402
from engine.skins.base import TimelineDriver, FPS, W, H  # noqa: E402
from engine.skins.papercut import PaperCut  # noqa: E402
from engine.skins.glass import GlassKinetic  # noqa: E402

STYLE_DIR = ROOT / "content/style_test"
CLEAN_DIR = ROOT / "content/my_voice_cleaned_v3"
WINDOW_S = 40.0
config.ENCODE_CRF = 20
config.ENCODE_PRESET = "medium"


def load_voice_window() -> np.ndarray:
    with wave.open(str(CLEAN_DIR / "cleaned_s1.wav")) as w:
        sr = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    x = pcm.astype(np.float64) / 32768.0
    n = int(WINDOW_S * sr)
    return x[:n], sr


def render(skin_name: str, skin, events, voice, sr, frame_log) -> Path:
    driver = TimelineDriver(events, WINDOW_S)
    # audio: procedural bed + SFX, ducked under the real narration
    mix_wav = STYLE_DIR / f"_work_mix_{skin_name}.wav"
    synth_audio.build_mix(voice, events, WINDOW_S, mix_wav, skin=skin_name)

    silent = STYLE_DIR / f"_work_silent_{skin_name}.mp4"

    def frames():
        n_frames = int(WINDOW_S * FPS)
        for n in range(n_frames):
            t = n / FPS
            yield skin.draw(driver.state(t))

    count = video._encode_silent_iter(frames(), silent, FPS)
    frame_log[skin_name] = count

    out = STYLE_DIR / f"style_test_{skin_name}.mp4"
    ff = video._ffmpeg()
    subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(silent), "-i", str(mix_wav),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", "-shortest", str(out)], check=True)
    silent.unlink()
    mix_wav.unlink()
    return out


def main() -> None:
    timeline = json.loads((STYLE_DIR / "timeline.json").read_text())
    stem = next(s for s in timeline["stems"] if s["stem"] == "cleaned_s1")
    events = [e for e in stem["events"] if e["t"] < WINDOW_S]
    voice, sr = load_voice_window()
    assert sr == synth_audio.SR

    # sync log: event -> nearest frame, for the QA sync check
    sync = [{"t": e["t"], "frame": round(e["t"] * FPS),
             "type": e["type"], "role": e.get("role"),
             "is_key": e.get("is_key", False),
             "reliability": e.get("reliability")}
            for e in events if e["type"] != "visual_beat"]
    (STYLE_DIR / "event_sync_log.json").write_text(
        json.dumps(sync, ensure_ascii=False, indent=1))

    frame_log = {}
    for name, ctor in (("papercut", PaperCut), ("glass", GlassKinetic)):
        out = render(name, ctor(WINDOW_S), events, voice, sr, frame_log)
        print(f"{name}: {frame_log[name]} frames -> {out.name} "
              f"({out.stat().st_size / 1e6:.2f} MiB)", flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
