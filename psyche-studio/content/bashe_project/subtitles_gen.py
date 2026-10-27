"""Generate global subtitles for project 001 (باشه) from narration texts.

No .srt files exist for the recordings, so cues are built from the known
narration scripts:
  * each scene's text is split into short cues of at most MAX_WORDS words,
    preferring clause boundaries (، . ؟ ! ؛) and splitting long clauses on
    word boundaries;
  * cue duration inside a scene is allocated proportionally to word count,
    using the scene's measured audio duration;
  * cues are then shifted by the scene's global start time (cumulative
    durations + inter-scene gaps).

Output of build_subtitles() is the same [{start, end, text}, ...] shape
consumed by engine.audio_sync / engine.video.
"""
import re
from typing import Dict, List

MAX_WORDS = 6

# Narration text per scene, identical to the recorded voice-over.
NARRATION: Dict[int, str] = {
    1: "تا حالا شده یکی فقط بنویسه باشه، و کل روزت به هم بریزه؟",
    2: "پیام کوتاهه؛ ولی ذهن تو شروع می‌کنه به ساختن داستان. شاید ناراحت شده. "
       "شاید سرد شده. شاید حرف بدی زدم. شاید دیگه دوستم نداره. "
       "این پیام چند ثانیه پیش فقط دو حرف بود؛ الان یه داستان کامل شده.",
    3: "چرا این اتفاق میفته؟ وقتی طرف مقابل جلوی تو نیست، سه تا چیز از دستت رفته: "
       "لحن صداش، حالت چهره‌ش، و زبان بدنش. پس فقط چند تا کلمه مونده. "
       "و ذهن از جای خالی خوشش نمیاد؛ پس خودش پرش می‌کنه.",
    4: "بدتر اینکه ذهن ما برای دیدن خطر ساخته شده. برای همین بین ده تا احتمال، "
       "معمولاً بدترینش رو انتخاب می‌کنه. در حالی که شاید اون طرف فقط سرش شلوغ بوده، "
       "یا خسته بوده، یا عجله داشته.",
    5: "اینجا یه تفاوت مهم هست. او نوشته باشه؛ این یه واقعیته. "
       "ولی حتماً ازم ناراحته؟ این فقط یه تفسیره؛ حدس تو، نه حقیقت. "
       "به این می‌گن ذهن‌خوانی: مطمئن شدن درباره ذهن طرف، بدون شواهد کافی.",
    6: "پس دفعه بعد که یه پیام کوتاه ذهنت رو درگیر کرد، سه تا جمله بنویس. "
       "اول، واقعیت چیه؟ فقط چیزی که واقعاً اتفاق افتاده. "
       "دوم، داستان ذهنم چیه؟ حدس‌هایی که دارم می‌سازم. "
       "سوم، اقدام سالم چیه؟ مثلاً به جای حدس زدن، آرام بپرسم: همه چیز اوکیه؟",
    7: "یادت باشه؛ هر فکری که از ذهنت می‌گذره، حقیقت نیست. "
       "اگه این ویدیو به کارت اومد، بفرستش برای اونی که همیشه دنبال معنی پیام‌ها می‌گرده.",
}

_CLAUSE_SPLIT = re.compile(r"[.؟!؛,،]")


def split_into_cues(text: str, max_words: int = MAX_WORDS) -> List[str]:
    """Split narration into short subtitle cues of at most max_words words."""
    cues: List[str] = []
    for clause in _CLAUSE_SPLIT.split(text):
        words = clause.split()
        if not words:
            continue
        for i in range(0, len(words), max_words):
            chunk = " ".join(words[i:i + max_words]).strip()
            if chunk:
                cues.append(chunk)
    return cues


def build_subtitles(scene_durations: Dict[int, float], gap: float) -> List[Dict]:
    """Return globally timed subtitle cues for all seven scenes.

    scene_durations: {scene_number: audio duration in seconds}
    gap: silence inserted between scenes (seconds).
    """
    subtitles: List[Dict] = []
    global_start = 0.0
    for scene in sorted(NARRATION):
        duration = float(scene_durations[scene])
        cues = split_into_cues(NARRATION[scene])
        word_counts = [len(cue.split()) for cue in cues]
        total_words = sum(word_counts) or 1

        cursor = global_start
        for cue, words in zip(cues, word_counts):
            cue_duration = duration * words / total_words
            subtitles.append({
                "start": round(cursor, 3),
                "end": round(cursor + cue_duration, 3),
                "text": cue,
            })
            cursor += cue_duration
        # Next scene begins after this scene's audio plus the inter-scene gap.
        global_start += duration + gap
    return subtitles


if __name__ == "__main__":
    # Manual smoke check with placeholder durations.
    demo = {i: 10.0 for i in range(1, 8)}
    subs = build_subtitles(demo, gap=0.35)
    print(f"{len(subs)} cues")
    for cue in subs[:8]:
        print(cue)
