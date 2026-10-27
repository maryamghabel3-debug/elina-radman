"""Project 001 — «باشه» video: ordered scene configuration.

Each entry matches one narration file in content/my_voice/scene_XX.mp3.
Background image names resolve under assets/images/bashe/. The engine's
scene builders (engine.scenes) consume the type-specific keys.
"""
from pathlib import Path

GAP = 0.35  # seconds of silence between scenes

IMAGE_DIR = Path(__file__).resolve().parents[2] / "assets" / "images" / "bashe"

SCENES = [
    {
        "scene": 1,
        "type": "hook",
        "bg": "img_hook.png",
        "headline": "چرا یه «باشه» ساده کل روزت رو به‌هم می‌ریزه؟",
    },
    {
        "scene": 2,
        "type": "bubbles",
        "bg": "img_storm.png",
        "center_text": "باشه.",
        "bubbles": ["ناراحت شده؟", "سرد شده؟", "حرف بدی زدم؟", "دیگه دوستم نداره؟"],
    },
    {
        "scene": 3,
        "type": "split",
        "bg": "img_min_a.png",
        "left_label": "مکالمه‌ی حضوری",
        "left_text": "لحن صدا • حالت چهره • زبان بدن",
        "right_label": "پیام متنی",
        "right_text": "فقط چند کلمه",
    },
    {
        "scene": 4,
        "type": "bubbles",
        "bg": "img_storm.png",
        "center_text": "شاید...",
        "bubbles": ["سرش شلوغ بود", "خسته بود", "عجله داشت", "متوجه لحن نشد"],
    },
    {
        "scene": 5,
        "type": "split",
        "bg": "img_min_b.png",
        "left_label": "واقعیت",
        "left_text": "او نوشت: باشه",
        "right_label": "تفسیر",
        "right_text": "حتماً از من ناراحته",
    },
    {
        "scene": 6,
        "type": "cards",
        "bg": "img_min_b.png",
        "cards": [
            {"number": "۱", "title": "واقعیت چیه؟",
             "body": "فقط چیزی که واقعاً اتفاق افتاده"},
            {"number": "۲", "title": "داستان ذهنم چیه؟",
             "body": "حدس‌هایی که ذهنم می‌سازه"},
            {"number": "۳", "title": "اقدام سالم چیه؟",
             "body": "به جای حدس، سؤال بپرس"},
        ],
    },
    {
        "scene": 7,
        "type": "outro",
        "bg": "img_outro.png",
        "closing_text": "هر فکری که از ذهنت می‌گذره، حقیقت نیست.",
    },
]
