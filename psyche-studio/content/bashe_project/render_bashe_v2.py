"""Project 001 V2 render orchestration.

Builds the motion-graphics cut from the CLEANED narration:
  * ffmpeg concat-filter joins the seven cleaned MP3s with exact 0.35 s PCM
    silence gaps (sample-accurate, no per-gap encoder padding);
  * each scene is produced by an engine.scenes_v2 component from its
    per-scene SRT cue timings;
  * 250-400 ms PIL transitions join scenes, chrome (progress line, chapter
    tab, dot pagination) and clean subtitles are burned globally;
  * frames are streamed through the ffmpeg pipe (memory-safe), h264 CRF 20.

Run from psyche-studio/:  .venv/bin/python content/bashe_project/render_bashe_v2.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import imageio_ffmpeg

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO))

from engine import audio_sync, beats, chrome, config, kinetic, transitions, video  # noqa
from engine import scenes_v2 as sv2  # noqa

GAP = 0.35
FPS = config.FPS
CLEAN_DIR = STUDIO / "content" / "my_voice_cleaned"
WORK_DIR = STUDIO / "content" / "bashe_project"
OUTPUT = WORK_DIR / "bashe_v2.mp4"
FULL_VOICE = WORK_DIR / "full_voice_v2.mp3"
MANIFEST = WORK_DIR / "v2_manifest.json"

CHAPTER_TITLES = [
    "شروع", "طوفان ذهن", "پیام و حضور", "شاید",
    "واقعیت و تفسیر", "سه قدم", "جمع‌بندی",
]
SCENE_TRANSITIONS = [None, "swipe", "whip_pan", "scale_cut",
                     "swipe", "mask_reveal", "scale_cut"]
NEGATIVE_THOUGHTS = ["ناراحت شده؟", "سرد شده؟", "حرف بدی زدم؟",
                     "دیگه دوستم نداره؟"]
ALTERNATIVES = ["سرش شلوغ بود", "خسته بود", "عجله داشت", "متوجه لحن نشد"]


def ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: List[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-1500:]}")


def build_full_voice() -> Dict[int, float]:
    durations = {
        i: audio_sync.get_audio_duration(CLEAN_DIR / f"scene_{i:02d}.mp3")
        for i in range(1, 8)
    }
    cmd = [ffmpeg(), "-y"]
    for i in range(1, 8):
        cmd += ["-i", str(CLEAN_DIR / f"scene_{i:02d}.mp3")]
    cmd += ["-f", "lavfi", "-t", str(GAP),
            "-i", "anullsrc=channel_layout=mono:sample_rate=44100"]
    chain = "".join(f"[{i - 1}:a][7:a]" if i < 7 else f"[{i - 1}:a]"
                    for i in range(1, 8))
    cmd += ["-filter_complex",
            f"{chain}concat=n=13:v=0:a=1[out]", "-map", "[out]",
            "-c:a", "libmp3lame", "-b:a", "128k", str(FULL_VOICE)]
    run(cmd)
    return durations


def build_scene_factory(scene: int, cues: List[dict], duration: float):
    if scene == 1:
        return sv2.make_hook(cues, duration)
    if scene == 2:
        return sv2.make_storm(cues, duration, "باشه.", NEGATIVE_THOUGHTS,
                              config.COLORS["danger"], "img_storm.png",
                              NEGATIVE_THOUGHTS, seed=61, badge=True)
    if scene == 3:
        return sv2.make_compare(cues, duration)
    if scene == 4:
        return sv2.make_storm(cues, duration, "شاید...", ALTERNATIVES,
                              config.COLORS["violet"], "img_storm.png",
                              ["شاید..."] + ALTERNATIVES, seed=71,
                              badge=False)
    if scene == 5:
        return sv2.make_head_transform(cues, duration)
    if scene == 6:
        return sv2.make_steps(cues, duration)
    return sv2.make_outro(cues, duration)


def main() -> int:
    t0 = time.perf_counter()
    durations = build_full_voice()
    total_audio = audio_sync.get_audio_duration(FULL_VOICE)
    print(f"full cleaned voice: {total_audio:.3f}s")

    scene_specs = []
    global_cues: List[dict] = []
    manifest = {"scenes": [], "gap": GAP}
    global_start = 0.0
    prior = 0.0
    for scene in range(1, 8):
        cues = audio_sync.parse_srt(CLEAN_DIR / f"scene_{scene:02d}.srt")
        render_seconds = durations[scene] + (GAP if scene < 7 else 0.0)
        if scene == 7:
            render_seconds = max(render_seconds,
                                 total_audio - prior + 1.0 / FPS)
        callable_, meta = build_scene_factory(scene, cues, render_seconds)
        plan = beats.build_scene_beats(
            scene, render_seconds, [c["start"] for c in cues],
            impact_texts=meta["impact_texts"],
            ambient_layers=meta["ambient"],
            active_layers=meta["active_layers"],
            extra_events=[beats.Beat(t=0.2, kind="entrance",
                                     note="scene entrance")])
        manifest["scenes"].append({
            "scene": scene, "chapter": CHAPTER_TITLES[scene - 1],
            "global_start": round(global_start, 3),
            "duration": round(render_seconds, 3),
            **beats.validate_plan(plan),
        })
        scene_specs.append((scene, callable_, render_seconds, global_start))
        for cue in cues:
            global_cues.append({
                "start": round(cue["start"] + global_start, 3),
                "end": round(cue["end"] + global_start, 3),
                "text": cue["text"],
            })
        print(f"scene_{scene:02d}: start={global_start:7.3f} "
              f"render={render_seconds:6.3f}s frames={round(render_seconds * FPS)} "
              f"beats={len(plan.beats)} max_static={plan.max_static:.2f}s")
        global_start += render_seconds
        prior += render_seconds

    total_render = global_start
    manifest["total_render_seconds"] = round(total_render, 3)
    manifest["total_audio_seconds"] = round(total_audio, 3)
    manifest["subtitle_cues"] = len(global_cues)

    # --- Frame stream with transitions + chrome + subtitles ---------------
    transition_frames = int(0.32 * FPS)
    prev_tail = None
    frame_index = 0

    def frame_stream():
        nonlocal prev_tail, frame_index
        for s_idx, (scene, func, seconds, g_start) in enumerate(scene_specs):
            n = max(1, round(seconds * FPS))
            kind = SCENE_TRANSITIONS[s_idx]
            local_tail = None
            for i in range(n):
                t = i / FPS
                frame = func(t, seconds)
                local_tail = frame.copy()
                if kind is not None and prev_tail is not None \
                        and i < transition_frames:
                    p = (i + 1) / transition_frames
                    frame = transitions.apply(kind, prev_tail, frame, p,
                                              direction=1)
                frame = frame.convert("RGBA")
                g_t = g_start + t
                chrome.draw_chrome(frame, g_t, total_render, s_idx, 7,
                                   CHAPTER_TITLES[s_idx])
                active = audio_sync.get_active_subtitles(global_cues, g_t)
                if active:
                    kinetic.draw_subtitle_clean(frame, active)
                frame_index += 1
                yield frame.convert("RGB")
            prev_tail = local_tail

    config.ENCODE_CRF = 20
    silent = WORK_DIR / "bashe_v2.silent.mp4"
    count = video._encode_silent_iter(frame_stream(), silent, FPS)
    print(f"encoded {count} frames ({count / FPS:.2f}s)")

    # --- Mux cleaned narration ---------------------------------------------
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(silent), "-i", str(FULL_VOICE),
           "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
           "-shortest", str(OUTPUT)]
    run(cmd)
    silent.unlink(missing_ok=True)

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    final_dur = audio_sync.get_audio_duration(OUTPUT)
    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"\nDONE in {time.perf_counter() - t0:.1f}s")
    print(f"output: {OUTPUT}")
    print(f"duration: {final_dur:.3f}s | size: {size_mb:.2f} MiB | "
          f"frames: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
