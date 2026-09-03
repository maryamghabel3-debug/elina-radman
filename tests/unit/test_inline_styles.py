"""
Unit tests for the M26 inline styling markup parser.
"""

import pytest

from agents.carousel.inline_styles import (
    TextSegment,
    has_inline_styles,
    parse_inline_styles,
    split_pipes_outside_brackets,
)

pytestmark = pytest.mark.unit


# --- plain text ---

def test_plain_text_single_segment():
    segs = parse_inline_styles("وقتی خوب‌بودن راهِ زنده‌ماندنت بود")
    assert segs == [TextSegment("وقتی خوب‌بودن راهِ زنده‌ماندنت بود")]


def test_empty_text_single_segment():
    assert parse_inline_styles("") == [TextSegment("")]
    assert parse_inline_styles(None) == [TextSegment("")]


# --- single styled word ---

def test_single_styled_word_color_only():
    segs = parse_inline_styles("وقتی [خوب‌بودن|color=#B89B65] راه")
    assert segs == [
        TextSegment("وقتی "),
        TextSegment("خوب‌بودن", color="#B89B65", size_multiplier=1.0),
        TextSegment(" راه"),
    ]


def test_single_styled_word_size_only():
    segs = parse_inline_styles("این [کلمه|size=1.3] است")
    assert segs == [
        TextSegment("این "),
        TextSegment("کلمه", color=None, size_multiplier=1.3),
        TextSegment(" است"),
    ]


def test_single_styled_word_color_and_size():
    segs = parse_inline_styles("[خودِ کاذب|color=#B89B65,size=1.3]")
    assert segs == [TextSegment("خودِ کاذب", color="#B89B65", size_multiplier=1.3)]


# --- multiple styled segments in one line ---

def test_multiple_styled_segments():
    text = "[اول|color=#B89B65] وسط [دوم|size=1.2] آخر"
    segs = parse_inline_styles(text)
    assert segs == [
        TextSegment("اول", color="#B89B65", size_multiplier=1.0),
        TextSegment(" وسط "),
        TextSegment("دوم", color=None, size_multiplier=1.2),
        TextSegment(" آخر"),
    ]


def test_adjacent_plain_segments_merged():
    segs = parse_inline_styles("a [x|color=#FF0000] b")
    assert len(segs) == 3
    assert segs[0] == TextSegment("a ")
    assert segs[2] == TextSegment(" b")


# --- multiple words inside one bracket ---

def test_multi_word_phrase_in_brackets():
    segs = parse_inline_styles("بخشی از [بخش زنده‌ترِ تو|color=#B89B65,size=1.2] محافظت")
    assert segs[1] == TextSegment("بخش زنده‌ترِ تو", color="#B89B65", size_multiplier=1.2)


# --- attribute order and case ---

def test_attribute_order_reversed_and_hex_lower():
    segs = parse_inline_styles("[x|size=1.1,color=#b89b65]")
    assert segs == [TextSegment("x", color="#B89B65", size_multiplier=1.1)]


# --- malformed markup -> whole text plain ---

def test_malformed_missing_pipe_plain():
    segs = parse_inline_styles("متن [بدون ویرگول] ادامه")
    assert segs == [TextSegment("متن [بدون ویرگول] ادامه")]


def test_malformed_missing_bracket_plain():
    segs = parse_inline_styles("متن [بدون بستن|color=#B89B65 ادامه")
    assert segs == [TextSegment("متن [بدون بستن|color=#B89B65 ادامه")]


def test_empty_brackets_plain():
    segs = parse_inline_styles("متن [] ادامه")
    assert segs == [TextSegment("متن [] ادامه")]


def test_bad_color_value_plain():
    segs = parse_inline_styles("[x|color=red]")
    assert segs == [TextSegment("[x|color=red]")]


def test_bad_size_value_plain():
    segs = parse_inline_styles("[x|size=abc]")
    assert segs == [TextSegment("[x|size=abc]")]


def test_size_out_of_range_plain():
    segs = parse_inline_styles("[x|size=99]")
    assert segs == [TextSegment("[x|size=99]")]


def test_unknown_attribute_plain():
    segs = parse_inline_styles("[x|weight=bold]")
    assert segs == [TextSegment("[x|weight=bold]")]


# --- Persian RTL mixed content ---

def test_persian_mixed_styled_unstyled():
    text = "وقتی [خوب‌بودن|color=#B89B65] راهِ زنده‌ماندنت بود"
    segs = parse_inline_styles(text)
    assert [s.text for s in segs] == ["وقتی ", "خوب‌بودن", " راهِ زنده‌ماندنت بود"]
    # Concatenation preserves the visible text (markup syntax removed)
    assert "".join(s.text for s in segs) == "وقتی خوب‌بودن راهِ زنده‌ماندنت بود"


# --- has_inline_styles quick check ---

def test_has_inline_styles():
    assert has_inline_styles("بدون markup") is False
    assert has_inline_styles("[x|color=#FF0000]") is True
    assert has_inline_styles("[x|size=1.1]") is True
    # Malformed markup is NOT an inline style (falls back to plain)
    assert has_inline_styles("[x|bad=1]") is False


# --- M27A: split_pipes_outside_brackets (title|body separator vs markup) ---
#
# The carousel text input uses '|' to separate title from body, while M26
# inline markup uses '|' INSIDE [...] brackets. The helper splits only on
# pipes OUTSIDE brackets. Parts keep their surrounding whitespace (the
# caller strips / rejoins), so assertions compare .strip() where noted.

def test_split_pipes_plain_unchanged():
    # "عنوان | بدنه" -> two parts (regression: plain behavior unchanged)
    parts = split_pipes_outside_brackets("عنوان | بدنه")
    assert [p.strip() for p in parts] == ["عنوان", "بدنه"]


def test_split_pipes_no_pipe_single_part():
    assert split_pipes_outside_brackets("عنوان ساده") == ["عنوان ساده"]


def test_split_pipes_multiple_pipes():
    parts = split_pipes_outside_brackets("ع | ب | دو")
    assert [p.strip() for p in parts] == ["ع", "ب", "دو"]


def test_split_pipes_title_with_markup_and_body():
    parts = split_pipes_outside_brackets("وقتی [خوب‌بودن|color=#B89B65] بود | بدنه")
    assert len(parts) == 2
    # The pipe inside the brackets is NOT a split point
    assert parts[0].strip() == "وقتی [خوب‌بودن|color=#B89B65] بود"
    assert parts[1].strip() == "بدنه"


def test_split_pipes_body_with_markup():
    parts = split_pipes_outside_brackets("عنوان | بدنه [زنده|size=1.2] است")
    assert len(parts) == 2
    assert parts[0].strip() == "عنوان"
    assert parts[1].strip() == "بدنه [زنده|size=1.2] است"


def test_split_pipes_both_with_markup():
    parts = split_pipes_outside_brackets("عنوان [a|c1] و [b|c2] | بدنه [c|c3]")
    assert len(parts) == 2
    assert parts[0].strip() == "عنوان [a|c1] و [b|c2]"
    assert parts[1].strip() == "بدنه [c|c3]"


def test_split_pipes_multiple_outside_pipes():
    # Only the pipes OUTSIDE brackets split; body keeps its own pipes
    parts = split_pipes_outside_brackets("عنوان [a|c1] | بدنه | بیشتر")
    assert len(parts) == 3
    assert parts[0].strip() == "عنوان [a|c1]"
    assert parts[1].strip() == "بدنه"
    assert parts[2].strip() == "بیشتر"


def test_split_pipes_nested_brackets():
    parts = split_pipes_outside_brackets("[a [b|c] d|e | f] | آخر")
    assert len(parts) == 2
    assert parts[0].strip() == "[a [b|c] d|e | f]"
    assert parts[1].strip() == "آخر"


def test_split_pipes_malformed_no_crash():
    # Unclosed '[' -> fall back to a plain split on every '|' (no crash)
    parts = split_pipes_outside_brackets("عنوان [بدون بستن | بدنه")
    assert [p.strip() for p in parts] == ["عنوان [بدون بستن", "بدنه"]
    # Stray ']' -> fall back to a plain split (no crash)
    parts2 = split_pipes_outside_brackets("عنوان ] بدن | ب")
    assert [p.strip() for p in parts2] == ["عنوان ] بدن", "ب"]


def test_split_pipes_empty_and_none():
    assert split_pipes_outside_brackets("") == [""]
    assert split_pipes_outside_brackets(None) == [""]
