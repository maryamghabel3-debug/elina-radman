"""Shared configuration for ElinaOS — Psychology build.

Brand owner: Maryam (clinical psychologist)
Voice surface: Maryam (human, credited) + Elina/Ellie (illustrated narrative layer)
Core audience: Persian-speaking adults 25-45, core 30-40, Iran + diaspora.

Rules encoded here:
  * Every piece of content serves ONE pain. "Content for everyone" is not allowed.
  * No toxic positivity. No diagnosis. No client stories.
  * Scientifically grounded, plain language.
"""

# -----------------------------------------------------------------------------
# CORE IDENTITY
# -----------------------------------------------------------------------------
BRAND = "Maryam Ghabbel | روانشناس بالینی"
AVATAR = "Elina & Ellie (illustrated narrative layer, transparently AI)"
NICHE = "Evidence-based psychology for adults who look fine and feel empty"
TONE = "Precise, calm, unflinching but never judgmental. Poetic in image, clinical in sentence."
AUDIENCE = (
    "Persian-speaking adults aged 25-45 (core 30-40), in Iran and across the diaspora, "
    "who are functional on the outside and depleted inside."
)

# -----------------------------------------------------------------------------
# CONTENT PILLARS  (one pain per piece)
# -----------------------------------------------------------------------------
PILLARS = [
    "pain_naming",        # Giving the invisible experience a name. "This is not laziness."
    "mechanism",          # What the brain and body are actually doing. Why it makes sense.
    "first_step",         # One small, realistic action. Never a magic cure.
    "myth_demolition",    # Dismantling pop-psychology and toxic positivity.
    "therapy_literacy",   # How therapy works; when support is genuinely indicated.
]

PILLAR_WEIGHTS = {
    "pain_naming": 0.35,
    "mechanism": 0.25,
    "first_step": 0.20,
    "myth_demolition": 0.10,
    "therapy_literacy": 0.10,
}

# -----------------------------------------------------------------------------
# RECURRING SERIES
# -----------------------------------------------------------------------------
SERIES = [
    "اسمش تنبلی نیست",        # burnout / shutdown / paralysis
    "بدنِ تو قبل از تو می‌داند",  # somatic signs
    "تله",                    # repeating relational patterns
    "سی‌سالگی، بدون جشن",      # meaning + achievement crisis
    "سوگِ بی‌جنازه",           # migration grief, ambiguous loss
    "چیزی که به کسی نگفتی",    # shame, secrecy, silencing
    "درمان دروغ نمی‌گوید",      # therapy literacy
    "اتاق مریم",              # behind the scenes, human, Q&A
]

# -----------------------------------------------------------------------------
# HASHTAGS — Farsi-first, search-intent oriented. No fashion/mood-board tags.
# -----------------------------------------------------------------------------
BASE_TAGS = "#روانشناسی #سلامت_روان #روانشناسی_بالینی #خودشناسی #مریم_قابل"

TAGS = {
    "pain_naming": "#فرسودگی #افسردگی_پنهان #خستگی_روانی #درد_روان #احساس_پوچی",
    "mechanism": "#نوروساینس #مغز #سیستم_عصبی #پاسخ_به_استرس #علم_روانشناسی",
    "first_step": "#تمرین_روانی #قدم_کوچک #مهارت_زندگی #خودمراقبتی_واقعی",
    "myth_demolition": "#باور_غلط #روانشناسی_زرد #مثبت_اندیشی_سمی #افسانه_روانشناسی",
    "therapy_literacy": "#روان_درمانی #چه_زمانی_درمان #درمان_چیست #سلامت_روان_بزرگسال",
}


def tags_for(pillar: str) -> str:
    return TAGS.get(pillar, "")


# -----------------------------------------------------------------------------
# FALLBACK CAPTIONS — used only if every LLM provider fails.
# Written to be safe (no diagnosis, no promise), so a failed run never ships harm.
# -----------------------------------------------------------------------------
FALLBACK_CAPTIONS = {
    "pain_naming": (
        "بعضی روزها فقط «خسته» نیستی. چیزی در تو خاموش است، و اسمش تنبلی نیست. "
        "اگر این جمله را با خودت گفته‌ای، شاید وقتش باشد که دقیق‌تر نگاهش کنیم."
    ),
    "mechanism": (
        "وقتی استرس طولانی می‌شود، مغز سیستم پاداش را کم‌فعال می‌کند. "
        "یعنی چیزی که قبلاً انگیزه می‌داد، دیگر سیگنال نمی‌دهد. "
        "این ضعف اراده نیست؛ یک پاسخ فیزیولوژیک است."
    ),
    "first_step": (
        "قدم صفر: امروز به‌جای «باید شروع کنم»، فقط بنویس چه چیزی بیشتر از همه انرژی‌ات را می‌برد. "
        "اسم‌گذاری، اولین قدم است — نه آخرین."
    ),
    "myth_demolition": (
        "«خودت را دوست داشته باش» توصیه نیست؛ یک جمله‌ی قشنگ است. "
        "روان‌شناسی واقعی، تمرین و تکرار و سازوکار دارد، نه شعار."
    ),
    "therapy_literacy": (
        "این محتوا آموزشی است و تشخیص نیست. "
        "اگر حال بد بیش از چند هفته با تو مانده و کار و خوابت را گرفته، ارزش دارد که با یک متخصص صحبت کنی."
    ),
}

DISCLAIMER_FA = "این محتوا آموزشی است و جای درمان فردی را نمی‌گیرد."


def fallback_for(pillar: str) -> str:
    return FALLBACK_CAPTIONS.get(pillar, FALLBACK_CAPTIONS["pain_naming"])
