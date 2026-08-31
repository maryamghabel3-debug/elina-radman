import pytest

from agents.editing.recipe_schema import EditRecipe, InputMediaConfig, SubtitleEntry
from agents.editing.subtitle_sync import (
    VOICE_SUBTITLE_SYNC_CONFIG_INVALID,
    build_auto_subtitle_entries,
    chunk_persian_text,
    parse_voice_auto_subtitle_config,
)

pytestmark = pytest.mark.unit

SAMPLE = "سلام دنیا، این یک آزمایش است. خدانگهدار"


# === Chunking ===

def test_chunking_splits_on_clause_punctuation():
    chunks = chunk_persian_text("سلام دنیا، این یک آزمایش است. خدانگهدار")
    assert [" ".join(c) for c in chunks] == [
        "سلام دنیا،",
        "این یک آزمایش است.",
        "خدانگهدار",
    ]


def test_chunking_caps_max_words_per_cue():
    text = " ".join(f"کلمه{i}" for i in range(20))  # no punctuation
    chunks = chunk_persian_text(text)
    assert all(len(c) <= 8 for c in chunks)
    assert sum(len(c) for c in chunks) == 20
    assert len(chunks) == 3  # 8 + 8 + 4


def test_chunking_merges_one_word_orphan_tail():
    # Clause fills to the cap, then a lone trailing word: merge, no orphan
    text = " ".join(f"کلمه{i}" for i in range(8)) + " کلمهآخر"
    chunks = chunk_persian_text(text)
    assert len(chunks) == 1
    assert len(chunks[0]) == 9


def test_chunking_empty_text():
    assert chunk_persian_text("") == []
    assert chunk_persian_text("   ") == []


# === Timing: word-boundary metadata ===

def _boundaries_for(words_timing):
    return [
        {"start_sec": s, "end_sec": e, "text": w}
        for w, s, e in words_timing
    ]


def test_entries_use_word_boundary_timing():
    text = "سلام دنیا، این آزمایش"  # 4 words -> cues: [0,2) and [2,4)
    boundaries = _boundaries_for([
        ("سلام", 0.0, 0.4),
        ("دنیا،", 0.4, 0.9),
        ("این", 1.3, 2.0),
        ("آزمایش", 2.0, 2.8),
    ])
    entries = build_auto_subtitle_entries(text, boundaries, audio_duration_sec=2.9)
    assert [e.text for e in entries] == ["سلام دنیا،", "این آزمایش"]
    assert (entries[0].start_sec, entries[0].end_sec) == (0.0, 0.9)
    assert (entries[1].start_sec, entries[1].end_sec) == (1.3, 2.8)


def test_entries_start_offset_applied_to_all_cues():
    text = "سلام دنیا، این آزمایش"
    boundaries = _boundaries_for([
        ("سلام", 0.0, 0.4),
        ("دنیا،", 0.4, 0.9),
        ("این", 1.3, 2.0),
        ("آزمایش", 2.0, 2.8),
    ])
    entries = build_auto_subtitle_entries(
        text, boundaries, audio_duration_sec=2.9, start_offset_sec=1.5
    )
    assert entries[0].start_sec == 1.5 and entries[0].end_sec == 2.4
    assert entries[1].start_sec == 2.8 and entries[1].end_sec == 4.3


# === Timing: proportional fallback (soft, never fatal) ===

def test_proportional_fallback_without_boundaries():
    text = "سلام دنیا، این آزمایش"  # cues cover word ranges [0,2) and [2,4)
    entries = build_auto_subtitle_entries(text, [], audio_duration_sec=4.0)
    assert len(entries) == 2
    # proportional over [0, 4.0]
    assert (entries[0].start_sec, entries[0].end_sec) == (0.0, 2.0)
    assert (entries[1].start_sec, entries[1].end_sec) == (2.0, 4.0)
    # no cue outside the audio span
    for e in entries:
        assert 0.0 <= e.start_sec < e.end_sec <= 4.0


def test_proportional_fallback_on_boundary_count_mismatch():
    text = "سلام دنیا، این آزمایش"  # 4 words
    mismatched = _boundaries_for([("x", 0.0, 0.5)])  # 1 boundary != 4 words
    entries = build_auto_subtitle_entries(text, mismatched, audio_duration_sec=4.0)
    assert len(entries) == 2
    assert (entries[0].start_sec, entries[0].end_sec) == (0.0, 2.0)
    assert (entries[1].start_sec, entries[1].end_sec) == (2.0, 4.0)


def test_no_boundaries_no_duration_uses_estimate():
    text = "سلام دنیا، این آزمایش"
    entries = build_auto_subtitle_entries(text, None, audio_duration_sec=None)
    assert len(entries) == 2
    # estimate = 4 words * 0.45 = 1.8s; proportional over it
    assert entries[0].start_sec == 0.0
    assert entries[1].end_sec == pytest.approx(1.8, abs=1e-6)


# === M16 validation constraints always satisfied ===

def test_generated_entries_pass_m16_validation():
    text = "بعضی لبخندها انتخاب ما نیستند و بعضی‌ها پیش از ما ساخته شده‌اند. خدانگهدار"
    boundaries = _boundaries_for(
        [(w, i * 0.4, i * 0.4 + 0.35) for i, w in enumerate(text.split())]
    )
    entries = build_auto_subtitle_entries(
        text, boundaries, audio_duration_sec=12.0,
        start_offset_sec=2.0, style="whisper", position="center",
    )
    assert entries
    for e in entries:
        assert isinstance(e, SubtitleEntry)
        assert e.start_sec >= 0
        assert e.end_sec > e.start_sec
        assert e.fade_in_sec >= 0 and e.fade_out_sec >= 0
        assert e.fade_in_sec + e.fade_out_sec <= e.end_sec - e.start_sec
        assert e.position == "center"
        assert e.style == "whisper"

    # Full M16 recipe validation passes
    recipe = EditRecipe(
        content_id="x",
        input_media=InputMediaConfig(video_keys=["v.mp4"]),
        subtitles=entries,
    )
    assert recipe.validate() == []


def test_generated_entries_short_cue_min_duration_and_fades():
    # Very short audio: cues can become tiny -> fades must shrink to fit
    text = "الف ب"  # 2 words, 1 clause-ish
    entries = build_auto_subtitle_entries(text, None, audio_duration_sec=0.3)
    for e in entries:
        dur = e.end_sec - e.start_sec
        assert dur >= 0.2
        assert e.fade_in_sec + e.fade_out_sec <= dur


# === Config validation (typed, terminal) ===

def test_parse_auto_subtitle_config_defaults():
    cfg = parse_voice_auto_subtitle_config({"text": "x"})
    assert cfg == {"enabled": False, "style": "default", "position": "bottom_center"}


def test_parse_auto_subtitle_config_valid_values():
    cfg = parse_voice_auto_subtitle_config({
        "text": "x",
        "auto_subtitles": True,
        "subtitle_style": "whisper",
        "subtitle_position": "top_center",
    })
    assert cfg == {"enabled": True, "style": "whisper", "position": "top_center"}


def test_parse_auto_subtitle_config_invalid_values():
    bad_configs = [
        {"auto_subtitles": "yes"},
        {"auto_subtitles": 1},
        {"subtitle_style": "glow"},
        {"subtitle_position": "nowhere"},
        "not-a-dict",
    ]
    for bad in bad_configs:
        with pytest.raises(ValueError, match=VOICE_SUBTITLE_SYNC_CONFIG_INVALID):
            parse_voice_auto_subtitle_config(bad)


def test_style_position_propagate_to_entries():
    text = "سلام دنیا"
    entries = build_auto_subtitle_entries(
        text, None, audio_duration_sec=2.0, style="name_reveal", position="top_center"
    )
    assert all(e.style == "name_reveal" for e in entries)
    assert all(e.position == "top_center" for e in entries)
