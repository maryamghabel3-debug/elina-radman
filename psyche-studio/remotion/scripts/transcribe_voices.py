#!/usr/bin/env python3
"""Stage-1 Persian speech transcription and independent-model cross-check.

The workflow resolves each Hugging Face model's main ref to its immutable
commit SHA once, then passes that SHA to faster-whisper and records it.
Generated outputs are intended for the workflow artifact, not source control.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import math
import re
import statistics
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PSYCHE = ROOT / "psyche-studio"
OUTPUT = PSYCHE / "output" / "eli_elina_full_draft_v3" / "transcripts"
VOICE_DIR = PSYCHE / "content" / "voice_review_v2"
SCENARIO_DIR = PSYCHE / "content" / "scenario"
PRIMARY_MODEL = "Systran/faster-whisper-large-v3"
CROSS_MODEL = "Systran/faster-whisper-medium"
MIN_WORD_CONFIDENCE = 0.80
MAX_CORPUS_CER = 0.15
MAX_UTTERANCE_CER = 0.20
MIN_UTTERANCES_WITHIN_CER = 0.80

AUDIO_INPUTS = {
    "elina_new": ("elina", VOICE_DIR / "elina_new.mp3", True),
    "eli": ("eli", VOICE_DIR / "eli_presetB.mp3", True),
    "elina_old": ("elina", VOICE_DIR / "elina_draft.mp3", False),
}
SOURCE_TEXTS = {
    "eli": SCENARIO_DIR / "source_text_eli.txt",
    "elina": SCENARIO_DIR / "source_text_elina.txt",
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\u064a", "\u06cc").replace("\u0649", "\u06cc").replace("\u0643", "\u06a9")
    out = []
    for ch in text:
        if ch in "\u200c\u200d\ufeff" or unicodedata.category(ch) in {"Mn", "Me", "Cf"}:
            continue
        if ch.isalpha() or ch.isdigit():
            out.append(ch)
    return "".join(out)


def tokens(text: str) -> list[str]:
    norm = unicodedata.normalize("NFKC", text).replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
    return re.findall(r"[\w]+", norm, flags=re.UNICODE)


def edit_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize_text(reference), normalize_text(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes:02d}:{seconds - minutes * 60:04.1f}"


def mean_median(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return statistics.mean(values), statistics.median(values)


def resolve_model_revisions() -> dict[str, dict[str, str]]:
    from huggingface_hub import HfApi

    api = HfApi()
    resolved: dict[str, dict[str, str]] = {}
    for label, repo_id in (("primary", PRIMARY_MODEL), ("cross_check", CROSS_MODEL)):
        sha = api.model_info(repo_id, revision="main").sha
        if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
            raise RuntimeError(f"Could not resolve an immutable 40-character revision for {repo_id}: {sha!r}")
        resolved[label] = {"repo_id": repo_id, "resolved_revision": sha, "resolved_from": "main"}
    return resolved


def transcribe_file(model: Any, path: Path, speaker: str, utterance_prefix: str) -> dict[str, Any]:
    segments, info = model.transcribe(
        str(path),
        language="fa",
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=True,
    )
    utterances: list[dict[str, Any]] = []
    for idx, segment in enumerate(segments, 1):
        word_items = []
        for word in (segment.words or []):
            probability = getattr(word, "probability", None)
            word_items.append({
                "word": str(word.word),
                "start": round(float(word.start), 3),
                "end": round(float(word.end), 3),
                "confidence": round(float(probability), 6) if probability is not None else None,
                "low_confidence": probability is not None and float(probability) < MIN_WORD_CONFIDENCE,
                "cross_check_disagreement": False,
            })
        utterances.append({
            "id": f"{utterance_prefix}_{idx:03d}",
            "speaker": speaker,
            "text": str(segment.text).strip(),
            "words": word_items,
            "start": round(float(segment.start), 3),
            "end": round(float(segment.end), 3),
        })
    return {
        "file": str(path.relative_to(ROOT)),
        "speaker": speaker,
        "language": getattr(info, "language", "fa"),
        "language_probability": getattr(info, "language_probability", None),
        "utterances": utterances,
    }


def sequence_match(primary: list[dict[str, Any]], cross: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Monotonic utterance alignment by text CER plus a modest timing penalty."""
    n, m = len(primary), len(cross)
    gap = 0.78
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i * gap
        back[i][0] = "delete"
    for j in range(1, m + 1):
        dp[0][j] = j * gap
        back[0][j] = "insert"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            p, c = primary[i - 1], cross[j - 1]
            text_cost = min(1.0, cer(p["text"], c["text"]))
            time_cost = min(1.0, abs((p["start"] + p["end"]) / 2 - (c["start"] + c["end"]) / 2) / 12)
            sub = 0.78 * text_cost + 0.22 * time_cost
            options = [(dp[i - 1][j - 1] + sub, "match"), (dp[i - 1][j] + gap, "delete"), (dp[i][j - 1] + gap, "insert")]
            dp[i][j], back[i][j] = min(options, key=lambda item: item[0])
    pairs: list[tuple[int, int]] = []
    i, j = n, m
    while i or j:
        action = back[i][j]
        if action == "match":
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif action == "delete":
            i -= 1
        elif action == "insert":
            j -= 1
        else:
            break
    return list(reversed(pairs))


def mark_word_disagreements(primary_words: list[dict[str, Any]], cross_words: list[dict[str, Any]]) -> None:
    p_tokens = [normalize_text(w["word"]) for w in primary_words]
    c_tokens = [normalize_text(w["word"]) for w in cross_words]
    matcher = difflib.SequenceMatcher(a=p_tokens, b=c_tokens, autojunk=False)
    matched: set[int] = set()
    for a, b, size in matcher.get_matching_blocks():
        matched.update(range(a, a + size))
    for index, word in enumerate(primary_words):
        word["cross_check_disagreement"] = index not in matched


def build_cross_check(primary: dict[str, Any], cross: dict[str, Any], primary_revision: str, cross_revision: str) -> dict[str, Any]:
    p_utterances, c_utterances = primary["utterances"], cross["utterances"]
    pairs = sequence_match(p_utterances, c_utterances)
    aligned_primary: set[int] = set()
    rows = []
    for pi, ci in pairs:
        p, c = p_utterances[pi], c_utterances[ci]
        aligned_primary.add(pi)
        value = cer(p["text"], c["text"])
        mark_word_disagreements(p["words"], c["words"])
        rows.append({
            "primary_utterance_id": p["id"],
            "cross_utterance_id": c["id"],
            "primary_text": p["text"],
            "cross_text": c["text"],
            "cer": round(value, 6),
            "agreement": "agree" if value <= MAX_UTTERANCE_CER else "disagree",
        })
    aligned_cross = {ci for _, ci in pairs}
    for i, p in enumerate(p_utterances):
        if i not in aligned_primary:
            for word in p["words"]:
                word["cross_check_disagreement"] = True
            rows.append({"primary_utterance_id": p["id"], "cross_utterance_id": None, "primary_text": p["text"], "cross_text": None, "cer": None, "agreement": "unmatched"})
    for j, c in enumerate(c_utterances):
        if j not in aligned_cross:
            rows.append({"primary_utterance_id": None, "cross_utterance_id": c["id"], "primary_text": None, "cross_text": c["text"], "cer": None, "agreement": "unmatched_cross"})
    p_text = " ".join(u["text"] for u in p_utterances)
    c_text = " ".join(u["text"] for u in c_utterances)
    confidence = [w["confidence"] for u in p_utterances for w in u["words"] if w["confidence"] is not None]
    cross_confidence = [w["confidence"] for u in c_utterances for w in u["words"] if w["confidence"] is not None]
    mean, median = mean_median(confidence)
    cross_mean, cross_median = mean_median(cross_confidence)
    scored = [row["cer"] for row in rows if row["cer"] is not None]
    within = sum(value <= MAX_UTTERANCE_CER for value in scored) / len(scored) if scored else 0.0
    return {
        "speaker": primary["speaker"],
        "primary_model": {"repo_id": PRIMARY_MODEL, "revision": primary_revision},
        "cross_model": {"repo_id": CROSS_MODEL, "revision": cross_revision},
        "corpus_cer": round(cer(p_text, c_text), 6),
        "utterance_agreement_fraction": round(within, 6),
        "primary_word_confidence": {"mean": round(mean, 6) if mean is not None else None, "median": round(median, 6) if median is not None else None, "count": len(confidence)},
        "cross_word_confidence": {"mean": round(cross_mean, 6) if cross_mean is not None else None, "median": round(cross_median, 6) if cross_median is not None else None, "count": len(cross_confidence)},
        "per_utterance": sorted(rows, key=lambda row: (row["primary_utterance_id"] is None, row["primary_utterance_id"] or row["cross_utterance_id"] or "")),
    }


def load_old_lines() -> tuple[list[str], list[str]]:
    path = PSYCHE / "remotion" / "scripts" / "build-full-draft-audio.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"ELI_LINES", "ELINA_LINES"}:
                    found[target.id] = ast.literal_eval(node.value)
    return found.get("ELI_LINES", []), found.get("ELINA_LINES", [])


def old_script_anchor(utterances: list[dict[str, Any]], lines: list[str]) -> list[tuple[int, float]]:
    anchors: list[tuple[int, float]] = []
    cursor = 0
    for utterance in utterances:
        best_idx, best_score = cursor, 0.0
        for idx in range(cursor, min(len(lines), cursor + 5)):
            score = difflib.SequenceMatcher(None, normalize_text(utterance["text"]), normalize_text(lines[idx]), autojunk=False).ratio()
            if score > best_score:
                best_idx, best_score = idx, score
        if best_score >= 0.20:
            cursor = min(len(lines), best_idx + 1)
        anchors.append((best_idx, best_score))
    return anchors


def write_transcript_files(stem_key: str, transcript: dict[str, Any], model: dict[str, str]) -> None:
    transcript["model"] = model
    transcript["word_confidence_threshold"] = MIN_WORD_CONFIDENCE
    output_key = "elina" if stem_key == "elina_new" else stem_key
    json_path = OUTPUT / f"{output_key}_spoken.json"
    txt_path = OUTPUT / f"{output_key}_spoken.txt"
    json_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = []
    for i, utterance in enumerate(transcript["utterances"], 1):
        words = []
        for word in utterance["words"]:
            value = word["word"]
            if word["low_confidence"] or word["cross_check_disagreement"]:
                value = f"**{value.strip()}?**"
            words.append(value)
        text = "".join(words).strip() or utterance["text"]
        lines.append(f"{i}. {format_time(utterance['start'])}–{format_time(utterance['end'])}: {text}")
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def confidence_summary(transcript: dict[str, Any]) -> dict[str, Any]:
    values = [w["confidence"] for u in transcript["utterances"] for w in u["words"] if w["confidence"] is not None]
    mean, median = mean_median(values)
    return {"word_count": len(values), "mean": mean, "median": median, "below_0_80": sum(v < MIN_WORD_CONFIDENCE for v in values), "missing": sum(w["confidence"] is None for u in transcript["utterances"] for w in u["words"])}


def write_old_new_diff(old: dict[str, Any], new: dict[str, Any]) -> None:
    old_lines = [u["text"] for u in old["utterances"]]
    new_lines = [u["text"] for u in new["utterances"]]
    output = [
        "مقایسهٔ transcript صدای قدیمی و جدید الینا؛ هر دو فقط ASR مدل primary هستند.",
        f"مدل قدیمی: {old['model']['repo_id']} @ {old['model']['revision']}",
        f"مدل جدید: {new['model']['repo_id']} @ {new['model']['revision']}",
        f"CER متن کامل (قدیمی به‌عنوان reference): {cer(' '.join(old_lines), ' '.join(new_lines)):.4f}",
        "",
    ]
    output.extend(difflib.unified_diff(old_lines, new_lines, fromfile="elina_draft", tofile="elina_new", lineterm=""))
    (OUTPUT / "elina_old_vs_new_diff.txt").write_text("\n".join(output) + "\n", encoding="utf-8")


def source_text_notes() -> list[str]:
    notes = []
    for speaker, path in SOURCE_TEXTS.items():
        if not path.exists():
            notes.append(f"- متن مرجع {speaker}: پیدا نشد (`{path.relative_to(ROOT)}`)؛ forced alignment متنی اجرا نشده است.")
            continue
        source = path.read_text(encoding="utf-8").strip()
        notes.append(f"- متن مرجع {speaker}: موجود ({len(source)} نویسه). اختلاف transcript با متن منبع در این اجرا باید بررسی شود.")
    return notes


def write_review(transcripts: dict[str, dict[str, Any]], cross_checks: dict[str, dict[str, Any]], revisions: dict[str, dict[str, str]], error: str | None = None) -> None:
    lines = [
        "# بازبینی transcript گفتار Eli و Elina — Stage 1",
        "",
        f"زمان تولید: {datetime.now(timezone.utc).isoformat(timespec='seconds')} (UTC)",
        "",
        "## وضعیت اجرا",
        "",
        ("**اجرا ناموفق/ناقص است.** هیچ نتیجهٔ transcript تأییدشده‌ای برای بخش ناقص ادعا نمی‌شود. خطا: " + error) if error else "**ASR اجرا شد؛ متن‌ها خروجی خام مدل‌اند و نیازمند تأیید مالک هستند.**",
        "",
        f"- مدل primary: `{PRIMARY_MODEL}`؛ revision: `{revisions.get('primary', {}).get('resolved_revision', 'نامشخص')}`.",
        f"- مدل مستقل cross-check: `{CROSS_MODEL}`؛ revision: `{revisions.get('cross_check', {}).get('resolved_revision', 'نامشخص')}`.",
        "- هر دو پاس با `language=fa`, `word_timestamps=True`, `vad_filter=True` اجرا می‌شوند. زمان‌ها relative به فایل صوتی خودشان هستند.",
        "",
        "## منابع متنی اختیاری",
        "",
        *source_text_notes(),
        "",
        "## متن کامل هر stem (primary ASR)",
        "",
    ]
    for stem_key, speaker in (("elina_new", "elina"), ("eli", "eli"), ("elina_old", "elina")):
        transcript = transcripts.get(stem_key)
        lines += [f"### {stem_key} — {speaker}", ""]
        if not transcript:
            lines += ["Transcript در دسترس نیست.", ""]
            continue
        for i, utterance in enumerate(transcript["utterances"], 1):
            rendered = []
            for word in utterance["words"]:
                text = word["word"].strip()
                if word["low_confidence"] or word["cross_check_disagreement"]:
                    text = f"**{text}?**"
                rendered.append(text)
            text = " ".join(rendered).strip() or utterance["text"]
            lines.append(f"{i}. {format_time(utterance['start'])}–{format_time(utterance['end'])}: {text}")
        lines.append("")
    lines += ["## Cross-check و confidence", "", "### معیار gate (تعریف عملیاتی این اجرا)", "", f"- میانگین و میانهٔ confidence واژه‌های primary برای هر دو stem جدید: هرکدام حداقل {MIN_WORD_CONFIDENCE:.2f}.", f"- corpus CER میان دو مدل برای هر stem جدید: حداکثر {MAX_CORPUS_CER:.2f}; دست‌کم {MIN_UTTERANCES_WITHIN_CER:.0%} از utteranceهای هم‌تراز CER حداکثر {MAX_UTTERANCE_CER:.2f} داشته باشند.", "- utterance بدون match یا confidence ناموجود جداگانه گزارش می‌شود؛ confidence مدل، احتمال کالیبره‌شدهٔ صحت نیست.", ""]
    all_pass = bool(cross_checks)
    for key in ("elina_new", "eli"):
        check = cross_checks.get(key)
        primary = transcripts.get(key)
        lines.append(f"### {key}")
        if not check or not primary:
            lines += ["اندازه‌گیری انجام نشده؛ gate: **PENDING/FAIL**.", ""]
            all_pass = False
            continue
        summary = confidence_summary(primary)
        lines.append(f"- primary word confidence: mean={summary['mean']}, median={summary['median']}, words={summary['word_count']}, <0.80={summary['below_0_80']}, missing={summary['missing']}.")
        lines.append(f"- cross-check corpus CER={check['corpus_cer']}; utterance agreement fraction={check['utterance_agreement_fraction']}.")
        for row in check["per_utterance"]:
            cer_text = "unmatched" if row["cer"] is None else f"CER={row['cer']:.3f}"
            lines.append(f"  - {row['primary_utterance_id']} ↔ {row['cross_utterance_id'] or 'no match'}: {cer_text} — {row['agreement']}")
        stem_pass = (
            summary["mean"] is not None and summary["median"] is not None
            and summary["mean"] >= MIN_WORD_CONFIDENCE and summary["median"] >= MIN_WORD_CONFIDENCE
            and summary["missing"] == 0
            and check["corpus_cer"] <= MAX_CORPUS_CER
            and check["utterance_agreement_fraction"] >= MIN_UTTERANCES_WITHIN_CER
            and all(row["agreement"] not in {"unmatched", "unmatched_cross"} for row in check["per_utterance"])
        )
        all_pass = all_pass and stem_pass
        lines.append(f"- gate برای {key}: **{'PASS' if stem_pass else 'FAIL'}**.")
        lines.append("")
    lines += [f"### نتیجهٔ کلی", "", f"**{'PASS' if all_pass else 'FAIL/PENDING'}** — نتیجه بر مبنای gate بالا؛ بررسی انسانی همچنان لازم است.", "", "## گفت‌وگوی پیشنهادی (موقت)", ""]
    eli_lines, elina_lines = load_old_lines()
    new_eli = transcripts.get("eli", {}).get("utterances", [])
    new_elina = transcripts.get("elina_new", {}).get("utterances", [])
    eli_anchors = old_script_anchor(new_eli, eli_lines)
    elina_anchors = old_script_anchor(new_elina, elina_lines)
    proposed = []
    for speaker, utterances, anchors, offset in (("eli", new_eli, eli_anchors, 0), ("elina", new_elina, elina_anchors, 1)):
        for idx, utterance in enumerate(utterances):
            old_index, similarity = anchors[idx]
            rank = old_index * 2 + offset
            uncertain = similarity < 0.35
            proposed.append((rank, utterance["start"], speaker, utterance, similarity, uncertain, old_index + 1))
    proposed.sort(key=lambda item: (item[0], item[1]))
    lines.append("این ترتیب فقط پیشنهاد است: utteranceهای مستقل با ترتیب نوبت‌های آرایه‌های قدیمی `ELI_LINES`/`ELINA_LINES` تراز شده‌اند؛ سپس از توالی سؤال/پاسخ و مضمون همان متن‌ها برای نوبت‌دهی استفاده شده است. زمان‌ها هرکدام relative به stem خود هستند و sync مشترک محسوب نمی‌شوند. موارد با تطبیق ضعیف با آرایهٔ قدیمی علامت «موقعیت نامطمئن» دارند.")
    lines.append("")
    if not proposed:
        lines.append("ترتیب مکالمه تا دریافت transcript قابل پیشنهاد نیست.")
    else:
        for i, (_, _, speaker, utterance, similarity, uncertain, old_idx) in enumerate(proposed, 1):
            text = utterance["text"]
            marker = " — **موقعیت نامطمئن**" if uncertain else ""
            lines.append(f"{i}. {speaker} ({format_time(utterance['start'])}–{format_time(utterance['end'])} در فایل خودش): {text}{marker} [تطبیق با نوبت قدیمی {old_idx}: {similarity:.2f}]")
    lines += ["", "## پرسش‌های لازم برای تأیید مالک", "", "1. آیا ترتیب پیشنهادیِ مبتنی بر نوبت‌های اسکریپت قبلی را به‌عنوان ترتیب پایه قبول دارید؟", "2. موارد **پررنگ با ?** یا utteranceهای با CER بالا را از نظر گفتار واقعی تأیید/اصلاح می‌کنید؟", "3. اگر متن مرجع مالک بعداً اضافه شود، کدام اختلاف معنایی را باید نگه داشت و کدام را اصلاح کرد؟", "4. آیا معیار عددی gate بالا برای تأیید transcript قابل قبول است؟", ""]
    (OUTPUT / "TRANSCRIPT_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")


def write_pending_files(error: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "TRANSCRIPT_REVIEW.md").write_text(
        "# بازبینی transcript — اجرا در انتظار/ناموفق\n\n"
        "هیچ transcript یا metric ساختگی درج نشده است. اجرای ASR کامل نشده؛ لطفاً log اجرای workflow را ببینید.\n\n"
        f"خطا: `{error}`\n\n"
        f"مدل‌های مورد نظر: `{PRIMARY_MODEL}` و `{CROSS_MODEL}`. زمان‌بندی، گفت‌وگوی پیشنهادی و quality gate پس از اجرای واقعی اضافه می‌شوند.\n",
        encoding="utf-8",
    )
    (OUTPUT / "run_error.txt").write_text(error + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    revisions: dict[str, dict[str, str]] = {}
    transcripts: dict[str, dict[str, Any]] = {}
    cross_raw: dict[str, dict[str, Any]] = {}
    from faster_whisper import WhisperModel

    revisions = resolve_model_revisions()
    (OUTPUT / "model_revisions.json").write_text(json.dumps(revisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    common = {"device": args.device, "compute_type": args.compute_type, "cpu_threads": args.threads, "num_workers": 1}
    primary_model = WhisperModel(revisions["primary"]["repo_id"], revision=revisions["primary"]["resolved_revision"], **common)
    for stem_key in ("elina_new", "eli", "elina_old"):
        speaker, path, needs_cross = AUDIO_INPUTS[stem_key]
        if not path.is_file():
            raise FileNotFoundError(f"Required audio is missing: {path}")
        transcripts[stem_key] = transcribe_file(primary_model, path, speaker, stem_key)
    del primary_model

    cross_model = WhisperModel(revisions["cross_check"]["repo_id"], revision=revisions["cross_check"]["resolved_revision"], **common)
    for stem_key in ("elina_new", "eli"):
        speaker, path, _ = AUDIO_INPUTS[stem_key]
        cross_raw[stem_key] = transcribe_file(cross_model, path, speaker, stem_key + "_cross")
    del cross_model

    checks = {}
    for stem_key in ("elina_new", "eli"):
        checks[stem_key] = build_cross_check(transcripts[stem_key], cross_raw[stem_key], revisions["primary"]["resolved_revision"], revisions["cross_check"]["resolved_revision"])
    for stem_key, speaker, _ in (("elina_new", "elina", True), ("eli", "eli", True), ("elina_old", "elina", False)):
        transcripts[stem_key]["speaker"] = speaker
        write_transcript_files(stem_key, transcripts[stem_key], revisions["primary"])
    write_old_new_diff(transcripts["elina_old"], transcripts["elina_new"])
    (OUTPUT / "cross_check.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "cross_check.txt").write_text("\n".join(
        f"{key}: CER={value['corpus_cer']:.4f}; mean confidence={value['primary_word_confidence']['mean']}; median confidence={value['primary_word_confidence']['median']}"
        for key, value in checks.items()
    ) + "\n", encoding="utf-8")
    write_review(transcripts, checks, revisions)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    try:
        run(args)
        return 0
    except Exception as exc:  # Preserve a truthful artifact on model/network failure.
        OUTPUT.mkdir(parents=True, exist_ok=True)
        write_pending_files(f"{type(exc).__name__}: {exc}")
        print(f"ASR failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
