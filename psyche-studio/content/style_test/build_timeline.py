"""Build the V3 kinetic timeline from the actual transcript.

Times are mapped from original recordings onto the cleaned stems through the
piecewise time map emitted by engine.audio_clean_v3 (trim + pause splice +
atempo 1.12), so no re-transcription is needed.

s01 rule (from the transcription pass): the original 27-57.5 s region is
off-mic. Words there never become exact word-level impact text; phrases still
drive visual events at phrase granularity.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.audio_clean_v3 import map_time  # noqa: E402

MANIFEST = ROOT / "content/my_voice_v2/narration_manifest.json"
CLEAN = ROOT / "content/my_voice_cleaned_v3/cleanup_report_data.json"
OUT = ROOT / "content/style_test/timeline.json"
WEAK_REGION = (27.0, 57.5)  # original-time s01 off-mic span

# Display normalization for known, cross-validated ASR spelling errors.
# Raw transcript stays untouched in narration_manifest.json; this only affects
# on-screen subtitle/impact display strings.
SPELL = [
    (r"کتاح|قوطا|قطایی|کوداه|قتاح", "کوتاه"),
    (r"تفکی(?!ک)", "تفکیک"), (r"خادی|خادای", "خالی"),
    (r"لوزومن|لوزوم", "لزوماً"), (r"زهن", "ذهن"),
    (r"استوپ", "استپ"), (r"بدلکش", "بلاکش"),
    (r"دوسترین", "دوست دارین"), (r"هلون", "حالا"),
    (r"ایندوری", "این‌طوری"), (r"نارهت", "ناراحت"),
    (r"اصابان|اصابه", "عصبانی"), (r"اوست", "عوض"),
    (r"گوچی", "کوچیک"), (r"سراقه", "سراغ"),
    (r"نراحت", "ناراحت"), (r"آدت", "عادت"),
    (r"خد\s*کوتاه", "خیلی کوتاه"), (r"هله", "حالا"),
    (r"تفاقی", "اتفاقی"),
]

# key token -> (color role). First match wins; checked on normalized text.
KEY_RULES = [
    (r"باشه", "trigger"),
    (r"چی\s*شد", "structure"),
    (r"کوتاه", "trigger"),
    (r"ناراحت", "negative"),
    (r"عصبانی", "negative"),
    (r"دوستم?\s*ندار", "negative"),
    (r"بلاکش", "negative"),
    (r"استپ", "structure"),
    (r"واقعیت|حقیقت", "reality"),
    (r"تفسیر", "negative"),
    (r"ذهن", "structure"),
    (r"جای\s*خالی", "structure"),
    (r"سوال|سؤال", "reality"),
]


def display(text: str) -> str:
    out = text.strip()
    for pat, rep in SPELL:
        out = re.sub(pat, rep, out)
    return re.sub(r"\s+", " ", out)


def key_role(text: str) -> str | None:
    for pat, role in KEY_RULES:
        if re.search(pat, text):
            return role
    return None


def word_reliability(p: float, in_weak: bool) -> str:
    r = "high" if p >= 0.70 else ("medium" if p >= 0.50 else "low")
    if in_weak and r == "high":
        r = "medium"
    return r


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    clean = json.loads(CLEAN.read_text())
    maps = {f"cleaned_s{i}": s["time_map"]
            for i, s in enumerate(clean["stems"], start=1)}
    stems_out = []
    for idx, f in enumerate(manifest["files"], start=1):
        stem = f"cleaned_s{idx}"
        is_s1 = idx == 1
        events, phrase_id = [], 0
        for seg in f["segments"]:
            phrase_id += 1
            o0, o1 = seg["start"], seg["end"]
            in_weak = is_s1 and (WEAK_REGION[0] <= o0 <= WEAK_REGION[1] or
                                 WEAK_REGION[0] <= o1 <= WEAK_REGION[1])
            t0 = round(map_time(o0, maps[stem]), 3)
            t1 = round(map_time(o1, maps[stem]), 3)
            phrase_text = display(seg["text"])
            phrase_role = key_role(phrase_text)
            phrase_rel = ("low" if in_weak and seg["avg_logprob"] < -0.6
                          else ("medium" if in_weak else "high"))
            word_events = []
            for w in seg.get("words", []):
                raw = w["w"].strip()
                if not raw:
                    continue
                w_in_weak = is_s1 and WEAK_REGION[0] <= w["s"] <= WEAK_REGION[1]
                rel = word_reliability(w["p"], w_in_weak)
                wtxt = display(raw)
                role = key_role(wtxt)
                # Exact word-level impact only for reliable words; the weak
                # s01 region may never produce exact word impact stamps.
                exact = role is not None and rel == "high" and not w_in_weak
                word_events.append({
                    "t": round(map_time(w["s"], maps[stem]), 3),
                    "end": round(map_time(w["e"], maps[stem]), 3),
                    "text": wtxt, "role": role, "reliability": rel,
                    "is_key": bool(exact),
                })
            # Phrase-level key event is allowed even in the weak region
            # (visual metaphor / chip, not an exact uncertain word stamp).
            events.append({
                "phrase_id": phrase_id, "type": "phrase",
                "t": t0, "end": t1, "text": phrase_text,
                "role": phrase_role, "reliability": phrase_rel,
                "is_key": phrase_role is not None,
                "word_level_impact_allowed": not in_weak,
                "words": word_events,
            })
        # Visual beats: guarantee an event at least every 1.1 s of start time,
        # including inside long phrases (ambient motion, never subtitles).
        starts = sorted(e["t"] for e in events)
        end_t = max(e["end"] for e in events)
        beats = []
        for a, b in zip([0.0] + starts, starts + [end_t]):
            cursor = a + 1.1
            while b - cursor > 0.15:
                beats.append({"type": "visual_beat", "t": round(cursor, 3),
                              "text": None, "role": "ambient",
                              "reliability": "high", "is_key": False})
                cursor += 1.1
        all_events = sorted(events + beats, key=lambda e: e["t"])
        stems_out.append({
            "stem": stem, "source_file": f["new_filename"],
            "cleaned_duration_s": clean["stems"][idx - 1]["cleaned_duration_s"],
            "weak_region_original_s": WEAK_REGION if is_s1 else None,
            "events": all_events,
        })
    timeline = {
        "version": 3, "atempo": clean["atempo"],
        "pause_rule": f"pauses > {clean['pause_limit_s']}s -> {clean['pause_kept_s']}s",
        "color_roles": {
            "trigger": "gold/mustard - trigger word (باشه/کوتاه)",
            "negative": "coral/red - negative thought",
            "reality": "mint/green - reality/question",
            "structure": "indigo/violet - structural heading",
            "ambient": "no text - visual-only beat",
        },
        "test_window_s": 40.0,
        "stems": stems_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(timeline, ensure_ascii=False, indent=1))
    for s in stems_out:
        n_key = sum(1 for e in s["events"] if e.get("is_key"))
        n_word_key = sum(1 for e in s["events"] if e["type"] == "phrase"
                         for w in e["words"] if w["is_key"])
        print(f"{s['stem']}: {len(s['events'])} events, {n_key} key phrases, "
              f"{n_word_key} exact word impacts, duration {s['cleaned_duration_s']}s")


if __name__ == "__main__":
    main()
