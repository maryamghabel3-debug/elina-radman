"""Shared Configuration for ElinaOS (Psychology & AI Art Focus)"""

# -----------------------------------------------------------------------------
# CORE IDENTITY
# -----------------------------------------------------------------------------
BRAND = "Elina Radman"
NICHE = "Psychology, Mental Well-being, and AI Digital Art"
TONE = "Empathetic, analytical, calm, deeply reflective, and artistic."
AUDIENCE = "Young adults (18-35) interested in mental health, self-discovery, and AI technology/art."

# -----------------------------------------------------------------------------
# CONTENT PILLARS
# -----------------------------------------------------------------------------
PILLARS = [
    "psychology_insights",      # Deep dives into human behavior, emotions, and therapy concepts
    "ai_art_therapy",           # Expressing complex emotions (anxiety, peace, overthinking) through AI-generated surreal art
    "mindful_lifestyle",        # Candid, moody everyday moments with reflective thoughts
    "ai_creator_behind_scenes"  # Sharing prompts and AI tools used to create the art
]

# -----------------------------------------------------------------------------
# HASHTAGS
# -----------------------------------------------------------------------------
BASE_TAGS = "#ElinaRadman #روانشناسی #هوش_مصنوعی #آرامش_درون"

TAGS = {
    "psychology_insights": "#توسعه_فردی #روانکاوی #تحلیل_رفتار #سلامت_روان #خودشناسی",
    "ai_art_therapy": "#هنر_دیجیتال #تصویرسازی_ذهنی #هنر_درمانی #AIArt #MidjourneyArt",
    "mindful_lifestyle": "#لایف_استایل #زندگی_آگاهانه #مایندفولنس #روزمرگی",
    "ai_creator_behind_scenes": "#پرامپت_نویسی #تولید_محتوا #آموزش_هوش_مصنوعی #AICommunity",
}

def tags_for(pillar: str) -> str:
    return TAGS.get(pillar, "")

# -----------------------------------------------------------------------------
# FALLBACK CAPTIONS (If LLM fails)
# -----------------------------------------------------------------------------
FALLBACK_CAPTIONS = {
    "psychology_insights": "گاهی سکوت ما، پرصداترین فریادِ درونمون برای شنیده شدنه. امروز بیاین درباره‌ی خستگی‌های عاطفی که پنهان می‌کنیم حرف بزنیم... شما کِی بیشتر از همیشه احساس کردید که نیاز به درک شدن دارید؟ 🤍✨",
    "ai_art_therapy": "من این تصویر رو با هوش مصنوعی ساختم تا حسِ 'گیر افتادن در افکار (Overthinking)' رو نشون بدم. هنر همیشه بهترین راه برای ترجمه کردنِ دردهای روانیه. نظر شما در مورد این تصویر چیه؟ 🎨🧠",
    "mindful_lifestyle": "یه گوشه‌ی دنج، یه لیوان قهوه و مرورِ افکارِ امروز. سرعت زندگی اونقدر بالاست که گاهی یادمون میره فقط 'حضور' داشته باشیم. امروز چند دقیقه برای خودتون وقت گذاشتید؟ ☕️🕊️",
    "ai_creator_behind_scenes": "خیلی‌ها می‌پرسن این تصاویرِ مفهومی رو چطور می‌سازم؟ پشت هر کدوم از این عکس‌ها، یک پرامپتِ مهندسی‌شده و یک تحلیلِ روانی نهفته است. تو پست‌های بعدی بیشتر از ترفندهای هوش مصنوعی براتون می‌گم! 💻✨"
}

def fallback_for(pillar: str) -> str:
    return FALLBACK_CAPTIONS.get(pillar, FALLBACK_CAPTIONS["mindful_lifestyle"])
