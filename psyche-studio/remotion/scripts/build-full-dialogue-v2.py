#!/usr/bin/env python3
"""Process the confirmed voice stems, align known script turns, and assemble v2.

No ASR and no silence-only line assignment are used. Pause candidates are a
secondary hint; script character weights, explicit short-turn anchors, and the
known longest lines constrain a deterministic k-best boundary search.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

PSYCHE = Path(__file__).resolve().parents[2]
ROOT = PSYCHE.parent
VOICE = PSYCHE / "content" / "voice_review_v1"
SCRIPT_DIR = PSYCHE / "content" / "voice_review_v2"
OUT = PSYCHE / "output" / "eli_elina_full_v2"
WORK = Path(os.environ.get("ELI_V2_WORKDIR", "/tmp/eli-elina-full-v2"))
SR = 24000
FPS = 30
RMS_WINDOW_S = 0.010
MIN_PAUSE_S = 0.180
EDGE_KEEP_S = 0.020
DEFAULT_GAP_S = 0.190
LONG_GAP_AFTER = {13, 22, 28}
MIN_TURN_S = 0.300
TOP_K = 3

SPEAKERS = {
    "elina": {
        "candidate": "candidate_01",
        "source": VOICE / "candidate_01_reference.mp3",
        "script": SCRIPT_DIR / "script_elina.txt",
        "speed": 1.18,
        "pitch_semitones": 0.0,
        "longest_line_one_based": 10,
        "short_anchors_one_based": [17],
        "filter_prefix": "highpass=f=102,equalizer=f=230:t=q:w=1:g=-4,treble=f=3500:g=2.5",
    },
    "eli": {
        "candidate": "candidate_02",
        "source": VOICE / "candidate_02_reference.mp3",
        "script": SCRIPT_DIR / "script_eli.txt",
        "speed": 1.24,
        "pitch_semitones": 2.0,
        # The user's longest-Eli reference is global dialogue turn 9, which is
        # the 5th Eli-only line in script_eli.txt (turns 1,3,5,7,9 are Eli).
        "longest_line_one_based": 5,
        "short_anchors_one_based": [8, 10, 17],
        "filter_prefix": "highpass=f=130,equalizer=f=250:t=q:w=1:g=-5,treble=f=4000:g=3.5",
    },
}


def ffmpeg_bin() -> str:
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("imageio-ffmpeg is required; install scripts/requirements-full-draft.txt") from exc


def run_ffmpeg(cmd: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def loudnorm_json(stderr: str) -> dict[str, str]:
    matches = re.findall(r"\{\s*\"input_i\".*?\n\}", stderr, flags=re.S)
    if not matches:
        raise RuntimeError("Could not parse FFmpeg loudnorm statistics")
    return json.loads(matches[-1])


def measure_loudness(path: Path) -> dict[str, Any]:
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return loudnorm_json(result.stderr.decode("utf-8", "replace"))


def processing_filter(speaker: str) -> str:
    cfg = SPEAKERS[speaker]
    prefix = cfg["filter_prefix"]
    filters = [prefix, "acompressor=threshold=-20dB:ratio=2:attack=12:release=140:makeup=1"]
    semitones = float(cfg["pitch_semitones"])
    speed = float(cfg["speed"])
    if semitones:
        ratio = 2 ** (semitones / 12.0)
        compensated_tempo = speed / ratio
        filters.extend([
            f"asetrate={SR}*{ratio:.9f}",
            f"aresample={SR}",
            f"atempo={compensated_tempo:.9f}",
        ])
    else:
        filters.append(f"atempo={speed:.9f}")
    filters.append("loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json")
    return ",".join(filters)


def process_to_pcm(speaker: str) -> tuple[np.ndarray, dict[str, Any]]:
    cfg = SPEAKERS[speaker]
    source: Path = cfg["source"]
    if not source.is_file():
        raise FileNotFoundError(source)
    stats_in = measure_loudness(source)
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-nostats", "-threads", "1", "-i", str(source),
        "-map", "0:a:0", "-vn", "-af", processing_filter(speaker),
        "-ar", str(SR), "-ac", "1", "-f", "f32le", "pipe:1",
    ]
    result = run_ffmpeg(cmd)
    samples = np.frombuffer(result.stdout, dtype="<f4").astype(np.float32, copy=True)
    if not len(samples):
        raise RuntimeError(f"Processing produced no PCM samples for {speaker}")
    stats = loudnorm_json(result.stderr.decode("utf-8", "replace"))
    return samples, {
        "candidate_id": cfg["candidate"],
        "source_file": str(source.relative_to(PSYCHE)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "processing": processing_filter(speaker),
        "tempo_factor": cfg["speed"],
        "pitch_shift_semitones": cfg["pitch_semitones"],
        "input_duration_seconds": round(float(len(samples) / SR * cfg["speed"]), 3),
        "processed_duration_seconds": round(len(samples) / SR, 3),
        "input_loudness": stats_in,
        "processed_loudness": stats,
        "sample_rate_hz": SR,
        "channels": 1,
        "pcm_format": "float32le",
    }


def read_script(path: Path, expected_count: int) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != expected_count:
        raise ValueError(f"{path.name}: expected {expected_count} non-empty turns, found {len(lines)}")
    return lines


def text_weight(text: str) -> float:
    # Character length is the principal duration prior; word count gently
    # compensates for short Persian words and explicit punctuation pauses.
    chars = sum(ch.isalpha() or ch.isdigit() for ch in text)
    words = len(re.findall(r"\S+", text))
    punct = len(re.findall(r"[.!؟?؛]", text))
    return max(1.0, chars + 1.5 * words + 1.4 * punct)


def rms_envelope(samples: np.ndarray) -> tuple[np.ndarray, float]:
    win = int(round(SR * RMS_WINDOW_S))
    count = int(math.ceil(len(samples) / win))
    padded = np.pad(samples, (0, count * win - len(samples)))
    blocks = padded.reshape(count, win).astype(np.float64)
    rms = np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-24)
    db = 20 * np.log10(rms + 1e-12)
    floor = float(np.percentile(db, 20))
    threshold = max(floor + 6.0, -45.0)
    return db, threshold


def detect_pauses(samples: np.ndarray) -> tuple[list[dict[str, float]], dict[str, float]]:
    db, threshold = rms_envelope(samples)
    active = np.flatnonzero(db > threshold)
    if not len(active):
        raise RuntimeError("No active audio detected above the RMS threshold")
    duration = len(samples) / SR
    speech_start = max(0.0, float(active[0] * RMS_WINDOW_S - 0.060))
    speech_end = min(duration, float((active[-1] + 1) * RMS_WINDOW_S + 0.060))
    below = db <= threshold
    pauses: list[dict[str, float]] = []
    begin = None
    for i, is_below in enumerate(below):
        if is_below and begin is None:
            begin = i
        elif not is_below and begin is not None:
            end = i
            start_s, end_s = begin * RMS_WINDOW_S, end * RMS_WINDOW_S
            length = end_s - start_s
            if length >= MIN_PAUSE_S and start_s > speech_start + 0.05 and end_s < speech_end - 0.05:
                pauses.append({"start": start_s, "end": end_s, "center": (start_s + end_s) / 2, "duration": length})
            begin = None
    if begin is not None:
        end_s = len(db) * RMS_WINDOW_S
        start_s = begin * RMS_WINDOW_S
        length = end_s - start_s
        if length >= MIN_PAUSE_S and start_s > speech_start + 0.05 and end_s < speech_end - 0.05:
            pauses.append({"start": start_s, "end": end_s, "center": (start_s + end_s) / 2, "duration": length})
    return pauses, {"speech_start": speech_start, "speech_end": speech_end, "duration": duration, "threshold_dbfs": threshold, "floor_p20_dbfs": float(np.percentile(db, 20)), "pause_count": len(pauses)}


def segment_duration_cost(duration: float, expected: float, *, line_index: int, long_index: int) -> float:
    if duration < MIN_TURN_S or expected <= 0:
        return float("inf")
    cost = (math.log(duration / expected) / 0.62) ** 2
    if line_index != long_index and duration > 0:
        # A ≥500 ms internal pause is a warning unless the line is the
        # deliberately long reference line; it is not silently split.
        pass
    return cost


def k_best_segmentations(pauses: list[dict[str, float]], timing: dict[str, float], lines: list[str], long_line_one_based: int, short_anchors_one_based: list[int], k: int = TOP_K) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    n = len(lines)
    need = n - 1
    if len(pauses) < need:
        return [], {"reason": f"Only {len(pauses)} candidate pauses for {need} required boundaries", "required_boundaries": need, "available_pauses": len(pauses)}
    start, end = timing["speech_start"], timing["speech_end"]
    weights = [text_weight(line) for line in lines]
    nominal_pause = min(0.32, max(0.18, statistics.median(p["duration"] for p in pauses)))
    body = max(n * MIN_TURN_S, end - start - need * nominal_pause)
    expected = [w * body / sum(weights) for w in weights]
    cumulative_targets = []
    running = 0.0
    for i, value in enumerate(expected[:-1]):
        running += value
        cumulative_targets.append(start + running + (i + 1) * nominal_pause)

    # Each state retains several best monotonic paths ending at one candidate pause.
    states: dict[int, list[tuple[float, tuple[int, ...]]]] = {}
    for slot in range(need):
        new_states: dict[int, list[tuple[float, tuple[int, ...]]]] = {}
        for current in range(len(pauses)):
            if current < slot or len(pauses) - current - 1 < need - slot - 1:
                continue
            gap = pauses[current]
            position_sigma = max(0.75, expected[slot] * 0.42)
            position_cost = 0.18 * ((gap["center"] - cumulative_targets[slot]) / position_sigma) ** 2
            gap_reward = -0.08 * math.log(max(gap["duration"], MIN_PAUSE_S) / MIN_PAUSE_S)
            candidates: list[tuple[float, tuple[int, ...]]] = []
            if slot == 0:
                duration = gap["start"] - start
                local = segment_duration_cost(duration, expected[0], line_index=0, long_index=long_line_one_based - 1)
                if math.isfinite(local):
                    candidates.append((local + position_cost + gap_reward, (current,)))
            else:
                for previous, paths in states.items():
                    if previous >= current:
                        continue
                    duration = gap["start"] - pauses[previous]["end"]
                    local = segment_duration_cost(duration, expected[slot], line_index=slot, long_index=long_line_one_based - 1)
                    if not math.isfinite(local):
                        continue
                    for prior_score, prior_path in paths:
                        candidates.append((prior_score + local + position_cost + gap_reward, prior_path + (current,)))
            if candidates:
                candidates.sort(key=lambda item: (item[0], item[1]))
                new_states[current] = candidates[:max(k * 4, 12)]
        states = new_states
        if not states:
            return [], {"reason": f"No feasible ordered segmentation at boundary slot {slot + 1}", "required_boundaries": need, "available_pauses": len(pauses)}

    complete: list[dict[str, Any]] = []
    for previous, paths in states.items():
        last_duration = end - pauses[previous]["end"]
        last_cost = segment_duration_cost(last_duration, expected[-1], line_index=n - 1, long_index=long_line_one_based - 1)
        if not math.isfinite(last_cost):
            continue
        for path_score, path in paths:
            bounds = [start] + [pauses[i]["end"] for i in path]
            ends = [pauses[i]["start"] for i in path] + [end]
            durations = [b - a for a, b in zip(bounds, ends)]
            score = path_score + last_cost
            long_idx = long_line_one_based - 1
            longest_other = max(d for j, d in enumerate(durations) if j != long_idx)
            long_ratio = durations[long_idx] / max(longest_other, 1e-9)
            if long_ratio < 1.0:
                score += 8.0
            elif long_ratio < 1.15:
                score += 3.0
            # Very short distinctive anchors should remain short by construction.
            for one_based in short_anchors_one_based:
                d = durations[one_based - 1]
                if d > 1.8:
                    score += 2.0 * (d - 1.8) ** 2
            internal_long_pauses = []
            for line_i, (seg_start, seg_end) in enumerate(zip(bounds, ends)):
                inside = [p for p in pauses if p["start"] >= seg_start + 0.04 and p["end"] <= seg_end - 0.04 and p["duration"] >= 0.5]
                for p in inside:
                    internal_long_pauses.append({"line": line_i + 1, **p})
                    if line_i != long_idx:
                        score += 1.4
            complete.append({"score": score, "pause_indices": list(path), "durations": durations, "starts": bounds, "ends": ends, "expected_durations": expected, "longest_line_ratio": long_ratio, "internal_pauses_ge_500ms": internal_long_pauses})
    complete.sort(key=lambda item: (item["score"], item["pause_indices"]))
    # Keep unique segmentations only.
    unique = []
    seen = set()
    for item in complete:
        key = tuple(item["pause_indices"])
        if key not in seen:
            seen.add(key); unique.append(item)
        if len(unique) >= k:
            break
    return unique, {"required_boundaries": need, "available_pauses": len(pauses), "nominal_pause_seconds": nominal_pause, "text_weights": weights, "expected_durations": expected, "speech_start": start, "speech_end": end}


def boundary_confidences(solutions: list[dict[str, Any]], pauses: list[dict[str, float]]) -> list[dict[str, Any]]:
    if not solutions:
        return []
    result = []
    count = len(solutions[0]["pause_indices"])
    for boundary_index in range(count):
        selected_idx = solutions[0]["pause_indices"][boundary_index]
        selected = pauses[selected_idx]
        times = [pauses[s["pause_indices"][boundary_index]]["center"] for s in solutions]
        spread = max(times) - min(times) if times else 0.0
        if spread <= 0.15 and selected["duration"] >= 0.28:
            confidence = "high"
        elif spread <= 0.35:
            confidence = "medium"
        else:
            confidence = "low"
        result.append({
            "after_turn": boundary_index + 1,
            "before_turn": boundary_index + 2,
            "time_processed_seconds": round(selected["center"], 3),
            "pause_start_seconds": round(selected["start"], 3),
            "pause_end_seconds": round(selected["end"], 3),
            "pause_duration_seconds": round(selected["duration"], 3),
            "confidence": confidence,
            "top3_position_spread_seconds": round(spread, 3),
            "estimated": True,
        })
    return result


def is_high_confidence(solutions: list[dict[str, Any]], boundaries: list[dict[str, Any]], speaker: str, lines: list[str]) -> tuple[bool, list[str]]:
    issues = []
    if not solutions or len(solutions[0]["pause_indices"]) != len(lines) - 1:
        return False, ["Exact boundary count was not reached"]
    best = solutions[0]
    cfg = SPEAKERS[speaker]
    long_idx = cfg["longest_line_one_based"] - 1
    if max(range(len(best["durations"])), key=best["durations"].__getitem__) != long_idx:
        issues.append(f"Expected longest line {long_idx + 1} is not the duration outlier")
    if any(d <= MIN_TURN_S for d in best["durations"]):
        issues.append("At least one turn is not longer than 0.3 s")
    stable = sum(b["confidence"] != "low" for b in boundaries)
    if boundaries and stable / len(boundaries) < 0.80:
        issues.append("Fewer than 80% of boundary positions are stable across the top-3 candidates")
    for anchor in cfg["short_anchors_one_based"]:
        d = best["durations"][anchor - 1]
        if d > 1.8:
            issues.append(f"Short anchor line {anchor} is not short (estimated {d:.2f}s)")
        for boundary_idx in (anchor - 2, anchor - 1):
            if 0 <= boundary_idx < len(boundaries) and boundaries[boundary_idx]["confidence"] == "low":
                issues.append(f"Boundary adjacent to short anchor line {anchor} is low confidence")
    unexpected = [p for p in best["internal_pauses_ge_500ms"] if p["line"] != cfg["longest_line_one_based"]]
    if unexpected:
        issues.append("At least one non-long turn contains an unselected pause >= 500 ms")
    if len(solutions) >= 2:
        margin = solutions[1]["score"] - solutions[0]["score"]
        if margin < 0.02:
            issues.append("Best and second-best segmentation scores are effectively tied")
    return not issues, issues


def write_segmentation_ambiguity(speaker_results: dict[str, Any], error: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SEGMENTATION_DIAGNOSTIC.json").write_text(json.dumps({"status": "STOPPED_BEFORE_ASSEMBLY", "error": error, "speakers": speaker_results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# ابهام در مرزبندی گفتار — اجرای ویدئو متوقف شد", "", f"**دلیل توقف:** {error}", "", "مرزهای زیر تخمین‌اند؛ در این گزارش هیچ‌کدام exact ادعا نشده‌اند.", ""]
    for speaker, result in speaker_results.items():
        lines += [
            f"## {speaker}", "",
            f"نوبت موردانتظار: {result.get('required_turns', '?')}؛ مرز لازم: {result.get('required_boundaries', '?')}؛ مکث‌های کاندیدا: {result.get('pause_count', '?')}؛ وضعیت: **{result.get('status', 'unknown')}**.",
            f"مسائل gate: {'؛ '.join(result.get('issues', [])) or 'ندارد'}.", "",
            "مرزهای منتخب (زمان در PCM پردازش‌شده، همه تخمینی):",
        ]
        for boundary in result.get("selected_boundaries", []):
            lines.append(f"- پس از نوبت {boundary['after_turn']}: {boundary['time_processed_seconds']:.3f}s؛ مکث {boundary['pause_duration_seconds']:.3f}s؛ اطمینان {boundary['confidence']}؛ گسترهٔ top-3={boundary['top3_position_spread_seconds']:.3f}s.")
        lines.append("")
        for rank, solution in enumerate(result.get("top3", []), 1):
            lines.append(f"### نامزد {rank} (امتیاز {solution['score']:.3f}؛ نسبت بلندترین نوبت به بقیه {solution['longest_line_ratio']:.3f})")
            lines.append("مرزهای تخمینی پس از نوبت‌ها: " + ", ".join(f"{i+1}→{time:.3f}s" for i, time in enumerate(solution.get("boundary_times_processed", []))))
            lines.append("مدت نوبت‌ها (ثانیه): " + ", ".join(f"{duration:.3f}" for duration in solution["durations"]))
            lines.append("")
    lines += ["به‌دلیل gate اطمینان، `full_dialogue_v2.mp3`، cues و ویدئو ساخته نشدند.", ""]
    (OUT / "SEGMENTATION_DIAGNOSTIC.md").write_text("\n".join(lines), encoding="utf-8")


def fade_quiet_edges(chunk: np.ndarray, fade_ms: float = 5.0) -> np.ndarray:
    out = chunk.copy()
    n = min(int(round(SR * fade_ms / 1000)), len(out) // 4)
    if n < 2:
        return out
    ramp = np.sin(np.linspace(0.0, math.pi / 2, n, endpoint=True, dtype=np.float32)) ** 2
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def extract_turn_chunks(samples: np.ndarray, solution: dict[str, Any]) -> list[np.ndarray]:
    cuts = solution["pause_indices"]
    chunks = []
    start_s = solution["starts"][0]
    for boundary_idx, pause_idx in enumerate(cuts):
        pause = solution["_pauses"][pause_idx]
        end_s = pause["start"] + EDGE_KEEP_S
        start_i = max(0, int(round(start_s * SR)))
        end_i = min(len(samples), int(round(end_s * SR)))
        chunks.append(fade_quiet_edges(samples[start_i:end_i]))
        start_s = max(0.0, pause["end"] - EDGE_KEEP_S)
    start_i = max(0, int(round(start_s * SR)))
    end_i = min(len(samples), int(round(solution["ends"][-1] * SR)))
    chunks.append(fade_quiet_edges(samples[start_i:end_i]))
    return chunks


def frame_rms_db(samples: np.ndarray) -> list[float]:
    window = SR // FPS
    count = int(math.ceil(len(samples) / window))
    padded = np.pad(samples, (0, count * window - len(samples)))
    blocks = padded.reshape(count, window).astype(np.float64)
    rms = np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-24)
    return [round(float(20 * math.log10(value + 1e-12)), 1) for value in rms]


def encode_mp3(mix: np.ndarray, path: Path) -> None:
    cmd = [ffmpeg_bin(), "-hide_banner", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", "192k", "-ar", str(SR), "-ac", "1", "-write_xing", "1", str(path)]
    run_ffmpeg(cmd, input_bytes=mix.astype("<f4", copy=False).tobytes())


def measure_pcm_loudness(samples: np.ndarray) -> dict[str, Any]:
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostats", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]
    result = run_ffmpeg(cmd, input_bytes=samples.astype("<f4", copy=False).tobytes())
    return loudnorm_json(result.stderr.decode("utf-8", "replace"))


def assemble(speaker_data: dict[str, Any], scripts: dict[str, list[str]], solutions: dict[str, dict[str, Any]], boundaries: dict[str, list[dict[str, Any]]]) -> tuple[np.ndarray, dict[str, Any]]:
    chunk_map = {}
    for speaker in ("elina", "eli"):
        solutions[speaker]["_pauses"] = speaker_data[speaker]["pauses"]
        chunk_map[speaker] = extract_turn_chunks(speaker_data[speaker]["samples"], solutions[speaker])
    parts: list[np.ndarray] = []
    cues: list[dict[str, Any]] = []
    cursor = 0
    splice_checks = []
    for turn in range(1, 36):
        speaker = "eli" if turn % 2 else "elina"
        line_index = (turn - 1) // 2 if speaker == "eli" else turn // 2 - 1
        chunk = chunk_map[speaker][line_index]
        if len(chunk) / SR <= MIN_TURN_S:
            raise RuntimeError(f"Turn {turn} is too short after extraction: {len(chunk)/SR:.3f}s")
        start_sample = cursor
        parts.append(chunk)
        cursor += len(chunk)
        gap_after = None
        if turn < 35:
            target_gap = 0.30 if turn in LONG_GAP_AFTER else DEFAULT_GAP_S
            # Keep 20 ms quiet context from each adjacent source turn.
            insert_s = max(0.0, target_gap - 2 * EDGE_KEEP_S)
            gap = np.zeros(int(round(insert_s * SR)), dtype=np.float32)
            parts.append(gap)
            cursor += len(gap)
            gap_after = target_gap
            left = float(chunk[-1]) if len(chunk) else 0.0
            right = 0.0
            splice_checks.append({"after_turn": turn, "target_speech_gap_seconds": target_gap, "inserted_silence_seconds": len(gap) / SR, "edge_sample_abs": abs(left), "edge_step_abs": abs(left - right)})
        cfg = SPEAKERS[speaker]
        speed = float(cfg["speed"])
        speaker_turn_index = line_index
        speaker_boundary = boundaries[speaker]
        before = None if line_index == 0 else speaker_boundary[line_index - 1]
        after = None if line_index >= len(speaker_boundary) else speaker_boundary[line_index]
        source_start_processed = solutions[speaker]["starts"][line_index]
        source_end_processed = solutions[speaker]["ends"][line_index]
        start_frame = int(round(start_sample / SR * FPS))
        end_frame = int(math.ceil((start_sample + len(chunk)) / SR * FPS))
        env_samples = np.pad(chunk, (0, max(0, (end_frame - start_frame) * (SR // FPS) - len(chunk))))
        rms_values = frame_rms_db(env_samples)[:end_frame - start_frame]
        durations = solutions[speaker]["durations"]
        expected = solutions[speaker]["expected_durations"]
        cues.append({
            "turn": turn,
            "speaker": speaker,
            "text": scripts[speaker][line_index],
            "sourceFile": str(cfg["source"].relative_to(PSYCHE)),
            "sourceIn": round(source_start_processed * speed, 3),
            "sourceOut": round(source_end_processed * speed, 3),
            "processedSourceIn": round(source_start_processed, 3),
            "processedSourceOut": round(source_end_processed, 3),
            "start": round(start_sample / SR, 6),
            "end": round((start_sample + len(chunk)) / SR, 6),
            "segmentStart": round(start_sample / SR, 6),
            "segmentEnd": round((start_sample + len(chunk)) / SR, 6),
            "startFrame": start_frame,
            "endFrame": end_frame,
            "rmsEnvelopeFrameStart": start_frame,
            "rmsEnvelopeDb": rms_values,
            "sourceTimeMapping": "estimated processed-time × tempo factor; filter/codec latency not removed from estimate",
            "boundaryBefore": before,
            "boundaryAfter": after,
            "durationSeconds": round(len(chunk) / SR, 3),
            "expectedTextDurationSeconds": round(expected[line_index], 3),
            "durationToTextRatio": round(durations[line_index] / expected[line_index], 3),
            "confidence": min((b["confidence"] for b in (before, after) if b is not None), default="high"),
            "gapAfterSeconds": gap_after,
        })
    mix = np.concatenate(parts).astype(np.float32, copy=False)
    return mix, {"lines": cues, "splice_checks": splice_checks}


def write_cues(mix: np.ndarray, cue_data: dict[str, Any], processing: dict[str, Any], segmentation: dict[str, Any]) -> dict[str, Any]:
    duration = len(mix) / SR
    frames = math.ceil(duration * FPS) + FPS
    padded = np.pad(mix, (0, max(0, math.ceil(frames * SR / FPS) - len(mix))))
    env = frame_rms_db(padded)
    cue_data["durationSeconds"] = round(duration, 6)
    cue_data["durationInFrames"] = frames
    cue_data["fps"] = FPS
    cue_data["sampleRateHz"] = SR
    cue_data["version"] = 2
    cue_data["speakerAssignmentSource"] = "owner-confirmed: candidate_01=Elina, candidate_02=Eli"
    cue_data["segmentationMethod"] = "known-script-constrained top-3 pause-boundary dynamic program; pause detector is secondary"
    cue_data["processing"] = processing
    cue_data["segmentation"] = segmentation
    cue_data["lines"] = cue_data.pop("lines")
    (OUT / "full_cues_v2.json").write_text(json.dumps(cue_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"duration_seconds": duration, "duration_in_frames": frames, "full_rms_frames": len(env)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    scripts = {
        "elina": read_script(SPEAKERS["elina"]["script"], 17),
        "eli": read_script(SPEAKERS["eli"]["script"], 18),
    }
    # Elina line 10 is stem-local line 10. Eli's cited line 9 is global turn 9,
    # i.e. stem-local Eli line 5 in the alternating 35-turn dialogue.
    expected_long = {"elina": 10, "eli": 5}
    for speaker in scripts:
        weights = [text_weight(line) for line in scripts[speaker]]
        target_weight = weights[expected_long[speaker] - 1]
        if target_weight < 0.90 * max(weights):
            raise RuntimeError(f"The specified long-line anchor {expected_long[speaker]} is not among the longest text turns for {speaker}")
    speaker_data: dict[str, Any] = {}
    top_solutions: dict[str, Any] = {}
    boundary_info: dict[str, list[dict[str, Any]]] = {}
    speaker_results: dict[str, Any] = {}
    all_ok = True
    for speaker in ("elina", "eli"):
        samples, processing = process_to_pcm(speaker)
        pauses, timing = detect_pauses(samples)
        cfg = SPEAKERS[speaker]
        solutions, solver_meta = k_best_segmentations(pauses, timing, scripts[speaker], cfg["longest_line_one_based"], cfg["short_anchors_one_based"])
        for solution in solutions:
            solution["_pauses"] = pauses
        boundaries = boundary_confidences(solutions, pauses)
        okay, issues = is_high_confidence(solutions, boundaries, speaker, scripts[speaker])
        speaker_data[speaker] = {"samples": samples, "pauses": pauses, "timing": timing, "processing": processing}
        top_solutions[speaker] = solutions
        boundary_info[speaker] = boundaries
        speaker_results[speaker] = {
            **timing,
            "status": "PASS" if okay else "LOW_CONFIDENCE_STOP",
            "issues": issues,
            "required_turns": len(scripts[speaker]),
            "required_boundaries": len(scripts[speaker]) - 1,
            "top3": [{"score": s["score"], "pause_indices": s["pause_indices"], "durations": [round(d, 3) for d in s["durations"]], "boundary_times_processed": [round(pauses[i]["center"], 3) for i in s["pause_indices"]], "longest_line_ratio": round(s["longest_line_ratio"], 3)} for s in solutions],
            "selected_boundaries": boundaries,
            "selected_duration_seconds": [round(d, 3) for d in solutions[0]["durations"]] if solutions else [],
            "text_weight_model": solver_meta,
            "processing": processing,
            "pause_count": len(pauses),
        }
        all_ok = all_ok and okay
    if not all_ok:
        write_segmentation_ambiguity(speaker_results, "At least one stem did not meet the explicit boundary-confidence gate")
        return 2

    mix, cue_data = assemble(speaker_data, scripts, top_solutions, boundary_info)
    # The target gaps are built from source pause context plus deterministic
    # inserted silence; speech itself is not time-stretched after segmentation.
    cue_data["segmentation"] = speaker_results
    cue_data["processing"] = {speaker: speaker_data[speaker]["processing"] for speaker in ("elina", "eli")}
    metadata = write_cues(mix, cue_data, cue_data["processing"], speaker_results)
    audio_path = OUT / "full_dialogue_v2.mp3"
    encode_mp3(mix, audio_path)
    final_loudness = measure_loudness(audio_path)
    with (OUT / "full_cues_v2.json").open("r+", encoding="utf-8") as f:
        cues = json.load(f)
        cues["finalAudio"] = {"path": str(audio_path.relative_to(PSYCHE)), "codec": "MP3", "bitrate_bps": 192000, "integrated_loudness": final_loudness}
        f.seek(0); json.dump(cues, f, ensure_ascii=False, indent=2); f.write("\n"); f.truncate()
    summary = {
        "status": "PASS",
        "audio": str(audio_path.relative_to(PSYCHE)),
        "cues": str((OUT / "full_cues_v2.json").relative_to(PSYCHE)),
        "duration_seconds": round(len(mix) / SR, 3),
        "duration_in_frames_with_tail": metadata["duration_in_frames"],
        "turn_count": len(cue_data["lines"]),
        "final_loudness": final_loudness,
        "speakers": speaker_results,
        "splice_checks": cue_data["splice_checks"],
    }
    (OUT / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "BUILD_ERROR.md").write_text(f"# خطای ساخت صدای v2\n\n`{type(exc).__name__}: {exc}`\n", encoding="utf-8")
        raise
