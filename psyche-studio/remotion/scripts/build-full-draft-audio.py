#!/usr/bin/env python3
"""Assemble the known 35-turn Eli/Elina draft without ASR.

The user-confirmed Elina stem is deliberately one stable path. To replace it,
put the replacement at content/voice_review_v2/elina_draft.mp3 and rerun this
script; the video and cue schema do not need a source-path edit.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

PSYCHE = Path(__file__).resolve().parents[2]
VOICE_DIR = PSYCHE / "content" / "voice_review_v2"
OUTPUT_DIR = PSYCHE / "output" / "eli_elina_full_draft_v1"
WORK_DIR = PSYCHE / ".draft_tools"
ELINA_STEM = VOICE_DIR / "elina_draft.mp3"  # swap this one stable file later
ELI_STEM = VOICE_DIR / "eli_presetB.mp3"
FULL_CUES = OUTPUT_DIR / "full_cues.json"
DURATION_SOURCE = PSYCHE / "remotion" / "src" / "eli" / "full-draft-duration.json"
MIX_WAV = WORK_DIR / "full_dialogue_mix.wav"
SR = 24000
FPS = 30
WINDOW_S = 0.010
MIN_GAP_S = 0.180
PAD_S = 0.080
TARGET_INTERTURN_SILENCE_S = 0.200
# Segments retain 80 ms of source room tone on each side, so the inserted
# timeline gap is reduced to keep the audible speech-to-speech gap near 200 ms.
TURN_GAP_S = max(0.0, TARGET_INTERTURN_SILENCE_S - 2 * PAD_S)

ELINA_LINES = [
    "آره، دیدم. جواب داده.",
    "فقط نوشته باشه.",
    "نه. فقط همین.",
    "ناراحت؟ برای چی؟",
    "من که حرف بدی نزدم.",
    "راست می‌گی. شاید.",
    "صبر کن الی. استپ.",
    "بیا برگردیم عقب. واقعاً چی شد؟",
    "دقیقاً. فقط نوشت باشه. بقیه‌ش رو کی ساخت؟",
    "آره، تو. پیام متنی لحن صدا نداره، قیافه نداره. یه جای خالی می‌مونه، و تو اون جای خالی رو با بدترین حدس‌ها پر می‌کنی.",
    "می‌دونم. ولی اسم این کار ذهن خوانیه. یعنی مطمئن بودن از فکرِ یه نفر دیگه، بدون هیچ مدرکی.",
    "جدا می‌کنیم. واقعیت چیه؟ یه جواب کوتاه: باشه.",
    "همه‌ی اون داستان‌هایی که ساختی. ناراحته، عصبانیه، دوستم نداره.",
    "برای همین به جای حدس زدن، می‌پرسم. می‌نویسم: حالت خوبه؟ سرت شلوغه؟",
    "نوشته: آره خوبم، فقط سرِ کار بودم.",
    "یادت باشه الی: هر فکری که تو سرمون میاد، واقعیت نیست.",
    "الی!",
]
ELI_LINES = [
    "الینا! الینا! گوشیت لرزید!",
    "خب؟ چی نوشته؟ زود باش بخون!",
    "همین؟ فقط باشه؟ نه سلامی، نه استیکری، نه هیچی؟",
    "وای وای وای. این خیلی بده. یعنی ناراحت شده!",
    "معلومه دیگه! حتماً یه چیزی گفتی که بهش برخورده. یادته دیروز چی نوشتی؟",
    "شاید عصبانیه. شاید دیگه براش مهم نیستی. شاید اصلاً دیگه دوستت نداره!",
    "آره! پس تو هم دیگه جوابش رو نده. اصلاً بلاکش کن!",
    "چی؟ چرا؟",
    "خب. اون نوشت باشه.",
    "من؟",
    "خب کار من اینه که مراقب باشم! اول بدترین رو چک می‌کنم که غافلگیر نشی.",
    "پس حالا چیکار کنیم؟",
    "و فکرهای من چیه؟",
    "باشه. ولی بازم نمی‌دونیم منظورش چی بوده!",
    "جواب داد؟ جواب داد؟ چی گفت؟",
    "آهان. خب. پس شاید یه کوچولو زیادی فکر کردم.",
    "باشه.",
    "این یکی واقعاً یعنی باشه!",
]

# Per-turn visual cues are metadata consumed by the Remotion composition.
CAMERA = {
    1:"shared",2:"elina",3:"eli",4:"phone",5:"eli",6:"elina",7:"eli",8:"elina",9:"eli",10:"elina",
    11:"eli",12:"elina",13:"eli",14:"shared",15:"eli",16:"phone",17:"shared",18:"elina",19:"eli",20:"shared",
    21:"eli",22:"elina",23:"eli",24:"shared",25:"eli",26:"shared",27:"eli",28:"phone",29:"eli",30:"phone",
    31:"eli",32:"elina",33:"eli",34:"elina",35:"eli",
}
ELI_POSE = {1:"excited",3:"curious",5:"suspicious",7:"suspicious",9:"suspicious",11:"suspicious",13:"suspicious",15:"curious",17:"curious",19:"curious",21:"suspicious",23:"curious",25:"curious",27:"suspicious",29:"excited",31:"curious",33:"curious",35:"excited"}
ELINA_POSE = {2:"neutral",4:"neutral",6:"concerned",8:"concerned",10:"concerned",12:"concerned",14:"concerned",16:"concerned",18:"neutral",20:"neutral",22:"neutral",24:"neutral",26:"concerned",28:"neutral",30:"neutral",32:"neutral",34:"concerned"}
BEAT = {
    1:"phone_intro",7:"thought_storm",8:"thought_storm",9:"thought_storm",10:"thought_storm",11:"thought_storm",12:"thought_storm",13:"block_stamp",
    14:"stop_freeze",16:"rewind",20:"missing_tone_labels",22:"mind_reading_impact",24:"split_card",25:"split_card",26:"split_card",
    28:"chat_question",29:"chat_reaction",30:"chat_reply",31:"warm_outro",32:"warm_outro",33:"warm_outro",34:"warm_outro",35:"final_gag",
}


def ffmpeg_bin() -> str:
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("FFmpeg is required (PATH or imageio-ffmpeg).") from exc


def decode_mono_24k(path: Path) -> np.ndarray:
    cmd = [ffmpeg_bin(), "-hide_banner", "-v", "error", "-i", str(path), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1"]
    raw = subprocess.run(cmd, check=True, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, dtype="<f4").copy()


def rms_db(x: np.ndarray) -> tuple[np.ndarray, float, float]:
    n = int(round(SR * WINDOW_S))
    count = len(x) // n
    windows = x[:count*n].reshape(count, n)
    rms = np.sqrt(np.mean(windows.astype(np.float64) ** 2, axis=1) + 1e-24)
    db = 20 * np.log10(rms + 1e-12)
    floor = float(np.percentile(db, 20))
    return db, floor, floor + 6.0


def silence_candidates(db: np.ndarray, threshold: float) -> list[dict[str, float]]:
    below = db <= threshold
    gaps: list[dict[str, float]] = []
    begin: int | None = None
    for i, is_below in enumerate(below):
        if is_below and begin is None:
            begin = i
        elif not is_below and begin is not None:
            end = i
            duration = (end - begin) * WINDOW_S
            if duration >= MIN_GAP_S and begin > 0 and end < len(db):
                gaps.append({"start": begin * WINDOW_S, "end": end * WINDOW_S, "duration": duration})
            begin = None
    return gaps


def line_chars(text: str) -> int:
    return sum(not ch.isspace() for ch in text)


def correlation(a: list[int], b: list[float]) -> float:
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(np.asarray(a, dtype=float), np.asarray(b, dtype=float))[0, 1])


def chunk_bounds(x: np.ndarray, db: np.ndarray, threshold: float, gaps: list[dict[str, float]], count: int, texts: list[str]):
    active_frames = np.flatnonzero(db > threshold)
    duration = len(x) / SR
    live_start = max(0.0, active_frames[0] * WINDOW_S - PAD_S)
    live_end = min(duration, (active_frames[-1] + 1) * WINDOW_S + PAD_S)
    chars = [line_chars(t) for t in texts]
    total_scale = (live_end - live_start) / sum(chars)
    expected = [c * total_scale for c in chars]

    # First pass: exactly N-1 longest eligible silence intervals.
    longest = sorted(gaps, key=lambda g: g["duration"], reverse=True)[:count - 1]
    longest.sort(key=lambda g: g["start"])
    starts = [live_start] + [g["end"] - PAD_S for g in longest]
    ends = [g["start"] + PAD_S for g in longest] + [live_end]
    initial_durations = [ends[i] - starts[i] for i in range(count)]
    initial_r = correlation(chars, initial_durations)

    # Refinement: after character-duration outliers in pass one, reselect pauses
    # inside the candidate pool by a constrained ordered dynamic program.
    # Relative duration fit is soft; a small bonus favors longer quiet windows.
    m = len(gaps)
    if m < count - 1:
        raise RuntimeError(f"Only {m} eligible gaps for {count-1} boundaries")
    dp: list[np.ndarray] = []
    back: list[np.ndarray] = []
    gap_bonus = 0.10
    first = np.full(m, np.inf)
    first_back = np.full(m, -1, dtype=int)
    for k, g in enumerate(gaps):
        d = g["start"] + PAD_S - live_start
        if d > 0:
            first[k] = (math.log(d / expected[0]) / 0.65) ** 2 - gap_bonus * math.log(g["duration"] / MIN_GAP_S)
    dp.append(first)
    back.append(first_back)
    for line_i in range(1, count - 1):
        cur = np.full(m, np.inf)
        parent = np.full(m, -1, dtype=int)
        for k, g in enumerate(gaps):
            end = g["start"] + PAD_S
            for j in range(k):
                start = gaps[j]["end"] - PAD_S
                d = end - start
                if d <= 0 or not math.isfinite(dp[-1][j]):
                    continue
                cost = dp[-1][j] + (math.log(d / expected[line_i]) / 0.65) ** 2 - gap_bonus * math.log(g["duration"] / MIN_GAP_S)
                if cost < cur[k]:
                    cur[k] = cost
                    parent[k] = j
        dp.append(cur)
        back.append(parent)
    best_cost, last = math.inf, -1
    for j, g in enumerate(gaps):
        d = live_end - (g["end"] - PAD_S)
        if d <= 0 or not math.isfinite(dp[-1][j]):
            continue
        cost = dp[-1][j] + (math.log(d / expected[-1]) / 0.65) ** 2
        if cost < best_cost:
            best_cost, last = cost, j
    if last < 0:
        raise RuntimeError("Could not find an ordered silence segmentation")
    selected_idx = [last]
    for layer in range(count - 2, 0, -1):
        last = int(back[layer][last])
        selected_idx.append(last)
    selected_idx.reverse()
    selected = [gaps[i] for i in selected_idx]
    starts = [live_start] + [g["end"] - PAD_S for g in selected]
    ends = [g["start"] + PAD_S for g in selected] + [live_end]
    durations = [ends[i] - starts[i] for i in range(count)]
    ratios = [durations[i] / expected[i] for i in range(count)]
    final_r = correlation(chars, durations)
    return {
        "live_start": live_start, "live_end": live_end, "characters": chars, "expected": expected,
        "initial_gaps": longest, "initial_durations": initial_durations, "initial_r": initial_r,
        "selected_gaps": selected, "starts": starts, "ends": ends, "durations": durations,
        "ratios": ratios, "final_r": final_r, "threshold": threshold,
    }


def visual(turn: int) -> dict:
    speaker = "eli" if turn % 2 else "elina"
    return {
        "camera": CAMERA[turn], "beat": BEAT.get(turn, "dialogue"),
        "eliPose": ELI_POSE.get(turn, "curious"), "elinaPose": ELINA_POSE.get(turn, "neutral"),
    }


def rms_envelope(mix: np.ndarray, start_s: float, end_s: float) -> tuple[int, list[float]]:
    start_frame = max(0, math.floor(start_s * FPS))
    end_frame = max(start_frame + 1, math.ceil(end_s * FPS))
    win = int(round(SR / FPS))
    values = []
    for frame in range(start_frame, end_frame):
        center = int(round((frame + 0.5) * SR / FPS))
        a = max(0, center - win // 2)
        b = min(len(mix), a + win)
        segment = mix[a:b]
        level = math.sqrt(float(np.mean(segment.astype(np.float64) ** 2)) + 1e-24) if len(segment) else 0.0
        values.append(round(20 * math.log10(level + 1e-12), 1))
    return start_frame, values


def write_pcm_wav_from_f32(mix: np.ndarray, out: Path) -> None:
    # The WAV is a transient lossless 48 kHz stereo mux source; no MP3 re-encode.
    raw = mix.astype("<f4", copy=False).tobytes()
    cmd = [ffmpeg_bin(), "-hide_banner", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)]
    subprocess.run(cmd, input=raw, check=True)


def main() -> None:
    for path in (ELINA_STEM, ELI_STEM):
        if not path.is_file():
            raise FileNotFoundError(path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    stem_data = {}
    analysis = {}
    for speaker, path, texts in (("elina", ELINA_STEM, ELINA_LINES), ("eli", ELI_STEM, ELI_LINES)):
        x = decode_mono_24k(path)
        db, floor, threshold = rms_db(x)
        gaps = silence_candidates(db, threshold)
        seg = chunk_bounds(x, db, threshold, gaps, len(texts), texts)
        stem_data[speaker] = {"samples": x, "db": db, "path": path, "texts": texts, "gaps": gaps, **seg}
        analysis[speaker] = {
            "source": str(path.relative_to(PSYCHE)), "durationSeconds": len(x) / SR,
            "rmsWindowMs": 10, "rmsFloorDbfsP20": floor, "silenceThresholdDbfs": threshold,
            "minimumSilenceSeconds": MIN_GAP_S, "eligibleSilenceCount": len(gaps),
            "initialLongestOnlyPearsonR": seg["initial_r"], "refinedDurationCharacterPearsonR": seg["final_r"],
            "selectedBoundarySilencesSeconds": [round(g["duration"], 3) for g in seg["selected_gaps"]],
            "chunkDurationsSeconds": [round(d, 3) for d in seg["durations"]],
            "characterCountsNonWhitespace": seg["characters"],
            "durationToExpectedCharacterRateRatios": [round(r, 3) for r in seg["ratios"]],
        }

    turn_specs = []
    for turn in range(1, 36):
        speaker = "eli" if turn % 2 else "elina"
        line_index = (turn - 1) // 2 if speaker == "eli" else (turn // 2) - 1
        turn_specs.append((turn, speaker, line_index))

    audio_pieces: list[np.ndarray] = []
    cue_stubs: list[dict] = []
    cursor = 0
    pad_gap = np.zeros(int(round(TURN_GAP_S * SR)), dtype=np.float32)
    for idx, (turn, speaker, line_index) in enumerate(turn_specs):
        data = stem_data[speaker]
        x = data["samples"]
        db = data["db"]
        start_s, end_s = data["starts"][line_index], data["ends"][line_index]
        a = max(0, int(round(start_s * SR)))
        b = min(len(x), int(round(end_s * SR)))
        if b <= a:
            raise RuntimeError(f"Empty audio chunk at turn {turn}")
        piece = x[a:b].copy()
        # Identify audible onset/offset within the padded source segment.
        f0 = max(0, int(math.floor(start_s / WINDOW_S)))
        f1 = min(len(db), int(math.ceil(end_s / WINDOW_S)))
        active = np.flatnonzero(db[f0:f1] > data["threshold"])
        if len(active):
            onset_s = (f0 + int(active[0])) * WINDOW_S
            offset_s = min(end_s, (f0 + int(active[-1]) + 1) * WINDOW_S)
        else:
            onset_s, offset_s = start_s, end_s
        mix_start = cursor
        speech_start = mix_start + max(0, int(round((onset_s - start_s) * SR)))
        speech_end = min(mix_start + len(piece), mix_start + max(1, int(round((offset_s - start_s) * SR))))
        v = visual(turn)
        chars = data["characters"][line_index]
        ratio = data["ratios"][line_index]
        left_gap = data["selected_gaps"][line_index - 1]["duration"] if line_index > 0 else 0.0
        right_gap = data["selected_gaps"][line_index]["duration"] if line_index < len(data["selected_gaps"]) else 0.0
        if ratio < 0.55 or ratio > 1.8 or (left_gap and left_gap < 0.22) or (right_gap and right_gap < 0.22):
            confidence = "low"
        elif ratio < 0.75 or ratio > 1.35 or (left_gap and left_gap < 0.30) or (right_gap and right_gap < 0.30):
            confidence = "medium"
        else:
            confidence = "high"
        cue = {
            "turn": turn, "speaker": speaker, "text": data["texts"][line_index],
            "start": round(speech_start / SR, 6), "end": round(speech_end / SR, 6),
            "segmentStart": round(mix_start / SR, 6), "segmentEnd": round((mix_start + len(piece)) / SR, 6),
            "sourceFile": str(data["path"].relative_to(PSYCHE)),
            "sourceIn": round(start_s, 6), "sourceOut": round(end_s, 6),
            "sourceLineIndex": line_index + 1, "characterCountNonWhitespace": chars,
            "durationCharacterRatio": round(ratio, 3), "confidence": confidence,
            "boundarySilenceBeforeSeconds": round(left_gap, 3) if line_index > 0 else None,
            "boundarySilenceAfterSeconds": round(right_gap, 3) if line_index < len(data["selected_gaps"]) else None,
            **v,
        }
        cue_stubs.append(cue)
        audio_pieces.append(piece)
        cursor += len(piece)
        if turn < 35:
            audio_pieces.append(pad_gap)
            cursor += len(pad_gap)

    mix = np.concatenate(audio_pieces).astype(np.float32, copy=False)
    samples_per_video_frame = SR // FPS
    duration_frames = math.ceil(len(mix) / samples_per_video_frame)
    target_samples = duration_frames * samples_per_video_frame
    if target_samples > len(mix):
        mix = np.pad(mix, (0, target_samples - len(mix)))
    duration_seconds = duration_frames / FPS
    for cue in cue_stubs:
        frame_start, env = rms_envelope(mix, cue["start"], cue["end"])
        cue["rmsEnvelopeFrameStart"] = frame_start
        cue["rmsEnvelopeDb"] = env
        cue["startFrame"] = round(cue["start"] * FPS)
        cue["endFrame"] = math.ceil(cue["end"] * FPS)

    active_gaps = [cue_stubs[i + 1]["start"] - cue_stubs[i]["end"] for i in range(len(cue_stubs) - 1)]
    cues = {
        "version": 1, "fps": FPS, "sampleRateHz": SR, "durationSeconds": round(duration_seconds, 6),
        "durationInFrames": duration_frames, "turnGapSeconds": TURN_GAP_S,
        "targetInterTurnSpeechGapSeconds": TARGET_INTERTURN_SILENCE_S,
        "measuredInterTurnSpeechGapSeconds": {
            "min": round(min(active_gaps), 3), "max": round(max(active_gaps), 3),
            "mean": round(sum(active_gaps) / len(active_gaps), 3),
        },
        "speakerAssignmentSource": "explicit user confirmation",
        "segmentationMethod": "RMS silence candidate pool + character-duration refinement; no ASR",
        "segmentation": analysis,
        "lines": cue_stubs,
    }
    FULL_CUES.write_text(json.dumps(cues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DURATION_SOURCE.write_text(json.dumps({"fps": FPS, "durationInFrames": duration_frames}, indent=2) + "\n", encoding="utf-8")
    write_pcm_wav_from_f32(mix, MIX_WAV)
    print(json.dumps({"cues": str(FULL_CUES), "mix": str(MIX_WAV), "durationSeconds": duration_seconds,
                      "durationInFrames": duration_frames,
                      "correlation": {s: a["refinedDurationCharacterPearsonR"] for s, a in analysis.items()},
                      "lowConfidenceTurns": [c["turn"] for c in cue_stubs if c["confidence"] == "low"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
