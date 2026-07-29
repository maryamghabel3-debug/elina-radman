# EDITOR SUITE SPEC V2 — ElinaOS
# مشخصات معماری ادیتور هوشمند الینا

---
version: "2.1.0"
status: "APPROVED"
document_type: "Architecture Specification"
project: "ElinaOS V2"
module: "Elina Smart Editor Suite"
last_updated: "2026-07-28"
---

## ۱. هدف

Elina Smart Editor Suite یک ادیتور ساده FFmpeg نیست.

این سیستم یک موتور هوشمند recipe-based برای آماده‌سازی محتوای فارسی، روان‌شناختی و سینمایی الینا است.

هدف:
- دریافت ویدیو، تصویر، ویس، موسیقی و متن
- ساخت خروجی آماده انتشار برای Instagram Reels، Story، Carousel Video و محتوای مریم
- حفظ کیفیت تایپوگرافی فارسی
- حفظ وضوح نریشن
- پردازش سینمایی صدا
- تولید موسیقی اختصاصی
- آماده‌سازی کاور و زیرنویس
- کنترل کیفیت خروجی
- آماده‌سازی محتوا قبل از ورود به مرحله تأیید و زمان‌بندی

## ۲. اصل معماری

ادیتور الینا از دو بخش جدا تشکیل می‌شود:

1. Edit Intelligence
2. Render Engine

Edit Intelligence تصمیم می‌گیرد چه ادیتی لازم است.
Render Engine همان تصمیم‌ها را اجرا می‌کند.

هیچکدام از این دو مرحله نباید مستقیماً محتوا را منتشر کنند.

## ۳. جریان کلی ادیت

CONTENT RAW
↓
EDIT REQUEST
↓
RECIPE GENERATION
↓
TYPOGRAPHY RENDERING
↓
SUBTITLE RENDERING
↓
AUDIO PROCESSING (Noise + Cinematic)
↓
AUDIO MIXING (Voice + Music + Ducking)
↓
FFMPEG FINAL RENDER
↓
QUALITY CHECK
↓
EDIT_DONE
↓
READY_FOR_REVIEW

## ۴. نقش انسان در ادیت

ادیتور باید هم ادیت خودکار و هم ادیت انسانی را پشتیبانی کند.

در فاز اول:
- CapCut
- Canva
- Photoshop
- Figma
- Descript
- Runway
- Suno / ElevenLabs
- ابزارهای بیرونی

می‌توانند برای ادیت دستی استفاده شوند.

ElinaOS باید وضعیت ادیت را مدیریت کند، نه اینکه از روز اول جای همه ابزارهای حرفه‌ای را بگیرد.

## ۵. موتور Recipe

هر ادیت با یک recipe تعریف می‌شود.

Recipe یک فایل JSON یا رکورد دیتابیس است که می‌گوید:

- ویدیوی ورودی کدام است
- ویس کدام است
- موسیقی کدام است
- متن هوک چیست
- زیرنویس لازم است یا نه
- موسیقی باید چقدر کم شود
- کاور باید ساخته شود یا نه
- خروجی چه اندازه و فرمتی داشته باشد

## ۶. نمونه Recipe

{
  "project_type": "reel",
  "preset": "elina_cinematic_reel",
  "input_media": {
    "video_key": "raw/reel_001.mp4",
    "voice_key": "voice/reel_001.wav",
    "music_key": "music/ambient_01.mp3"
  },
  "hook": {
    "enabled": true,
    "text": "تو تنبل نیستی",
    "style": "hook_bold_center",
    "start": 0.0,
    "end": 2.8
  },
  "subtitles": {
    "enabled": true,
    "source": "narration_text",
    "style": "farsi_cinematic_bottom",
    "highlight_keywords": true
  },
  "audio": {
    "voice_processing": {
      "enabled": true,
      "preset": "elina_cinematic",
      "noise_removal": true,
      "normalize": true
    },
    "music": {
      "source": "library",
      "key": "music/ambient_deep_01.mp3",
      "gain_db": -12,
      "loop": true,
      "fade_in": 1.0,
      "fade_out": 2.0
    },
    "ducking": {
      "enabled": true,
      "target_reduction_db": 6,
      "attack": 0.2,
      "release": 0.6
    }
  },
  "cover": {
    "enabled": true,
    "text": "تو تنبل نیستی",
    "style": "cover_dark_gold"
  },
  "export": {
    "format": "mp4",
    "resolution": "1080x1920",
    "fps": 30,
    "max_size_mb": 18
  }
}

## ۷. مشکل تایپوگرافی فارسی

FFmpeg به‌تنهایی برای رندر متن فارسی مناسب نیست.

مشکلات رایج:
- جدا شدن حروف فارسی
- جهت اشتباه متن راست به چپ
- کرنینگ ضعیف
- عدم پشتیبانی مناسب از فونت‌های فارسی
- شکست line break در متن‌های چندخطی

بنابراین FFmpeg نباید مستقیماً متن فارسی را با drawtext رندر کند.

## ۸. راه‌حل تایپوگرافی فارسی

برای رندر متن فارسی، ElinaOS از این مسیر استفاده می‌کند:

Persian text
↓
arabic_reshaper
↓
python-bidi
↓
Pillow canvas
↓
transparent PNG
↓
FFmpeg overlay

این یعنی:
- متن اول به شکل درست فارسی بازآرایی می‌شود
- جهت راست به چپ اصلاح می‌شود
- با فونت فارسی روی PNG شفاف رندر می‌شود
- سپس FFmpeg فقط آن PNG را روی ویدیو overlay می‌کند

## ۹. موتور Typography

Typography Engine مسئول موارد زیر است:

- ساخت Hook Overlay
- ساخت Subtitle Card
- ساخت Cover Text
- ساخت CTA Card
- حفظ safe area
- کنترل فونت
- کنترل line height
- کنترل سایه، stroke و contrast
- ساخت خروجی PNG شفاف

## ۱۰. کتابخانه‌های Typography

کتابخانه‌های پیشنهادی:

- Pillow
- arabic_reshaper
- python-bidi

فونت‌ها نباید داخل ریپوی عمومی ذخیره شوند اگر license نامشخص دارند.
مسیر فونت باید configurable باشد.

نمونه متغیرهای تنظیمی:

- ELINA_FONT_PRIMARY_PATH
- ELINA_FONT_SECONDARY_PATH

اگر فونت موجود نبود، سیستم باید fail کند و پیام واضح بدهد، نه اینکه متن خراب تولید کند.

## ۱۱. Audio Ducking

در ویدیوهای روان‌شناختی، موسیقی Ambient مهم است اما نباید نریشن را خفه کند.

ElinaOS باید Auto-Ducking را پشتیبانی کند.

یعنی:
- وقتی voice/narration فعال است، صدای موسیقی پس‌زمینه کاهش پیدا کند
- وقتی voice سکوت دارد، موسیقی به سطح طبیعی برگردد

## ۱۲. تنظیمات Ducking

Recipe باید این فیلدها را داشته باشد:

{
  "ducking": {
    "enabled": true,
    "target_reduction_db": 6,
    "attack": 0.2,
    "release": 0.6
  }
}

در FFmpeg، این می‌تواند با sidechaincompress یا تکنیک‌های معادل انجام شود.

هدف:
- وضوح نریشن
- حفظ حس موسیقی
- جلوگیری از clipping
- خروجی حرفه‌ای

## ۱۳. لایه‌های ادیتور

### ۱۳.۱. Hook Editor

مسئول:
- متن ۳ ثانیه اول
- typography overlay
- جایگاه در تصویر
- نسخه A/B در آینده

### ۱۳.۲. Subtitle Editor

مسئول:
- زیرنویس فارسی خوانا
- burn-in
- highlight کلمات کلیدی
- تقسیم متن به قطعات کوتاه
- رعایت safe area

### ۱۳.۳. Voice Editor

مسئول:
- اضافه کردن ویس
- نویزگیری
- پردازش سینمایی صدا
- تنظیم gain
- normalize
- sync ساده
- حذف سکوت در فاز بعد

### ۱۳.۴. Music Editor

مسئول:
- اضافه کردن موسیقی ambient
- loop
- fade in/out
- ducking
- تولید موسیقی اختصاصی از طریق ابزارهای AI

### ۱۳.۵. Cover Editor

مسئول:
- ساخت کاور
- متن فارسی درست
- سبک برند
- خروجی 1080x1920 یا 1080x1350

### ۱۳.۶. Assembly Editor

مسئول:
- ترکیب همه لایه‌ها
- خروجی نهایی
- کنترل کیفیت

## ۱۴. Presets

Presetها باید قابل تنظیم باشند.

Presetهای اولیه:

- elina_cinematic_reel
- maryam_face_to_camera
- story_quick_update
- carousel_video_slide
- crisis_silent_frame
- ellie_character_scene

هر preset باید مشخص کند:
- resolution
- font style
- text position
- color palette
- subtitle style
- audio settings
- export settings

## ۱۵. Quality Control

پس از رندر، QC Engine باید بررسی کند:

- فایل خروجی وجود دارد
- فرمت خروجی mp4 یا jpg است
- نسبت تصویر درست است
- فایل از max_size_mb بزرگ‌تر نیست
- صدا وجود دارد اگر voice_required=true
- سطح loudness در محدوده مجاز است
- clipping صوتی وجود ندارد
- متن hook داخل safe area است
- خروجی صفر بایت نیست
- مدت ویدیو در محدوده مجاز است
- هیچ فایل موقت حساس باقی نمانده

## ۱۶. مسیرهای فایل

با توجه به Fileless Architecture، فایل‌های ورودی و خروجی عملیاتی نباید در GitHub ذخیره شوند.

ادیتور باید:
- فایل‌ها را از Supabase Storage دانلود کند
- در temp directory پردازش کند
- خروجی را دوباره در Supabase Storage آپلود کند
- فایل‌های موقت را پاک کند

مسیرهای GitHub فقط کد و تست هستند.

## ۱۷. وضعیت‌های ادیت

وضعیت‌های پیشنهادی:

- edit_not_needed
- edit_requested
- edit_recipe_ready
- edit_rendering
- edit_done
- edit_failed
- manual_edit_required

## ۱۸. فرمان‌های Studio Bot مربوط به ادیت

فرمان‌های آینده:

- /edit ID typography
- /edit ID subtitle
- /edit ID cover
- /edit ID audio
- /edit ID assembly
- /editdone ID
- /editfail ID reason

این فرمان‌ها فقط status و metadata را تغییر می‌دهند.
خود انتشار را اجرا نمی‌کنند.

## ۱۹. کتابخانه‌های فنی

کتابخانه‌های فاز اول:

- ffmpeg
- ffprobe
- Pillow
- arabic_reshaper
- python-bidi
- pedalboard

کتابخانه‌های اختیاری فاز بعد:

- moviepy
- faster-whisper
- auto-editor
- pydub
- librosa
- noisereduce
- pysndfx

ابزارهای بیرونی:

- CapCut
- Descript
- Runway
- Submagic
- OpusClip
- Suno
- ElevenLabs Music
- MusicAPI

ابزارهای بیرونی می‌توانند در workflow انسانی استفاده شوند، اما هسته سیستم باید قابل اجرا بدون آن‌ها بماند.

## ۲۰. کارهایی که فعلاً انجام نمی‌دهیم

در فاز اول انجام نمی‌شود:

- ساخت UI کامل شبیه Submagic
- تدوین کاملاً خودکار چندصحنه‌ای
- تشخیص هوشمند beat موسیقی
- انتخاب خودکار بهترین hook
- تولید خودکار character animation
- انتشار مستقیم از ادیتور
- تولید کاملاً خودکار موسیقی داخل pipeline

این‌ها بعد از MVP قابل اضافه شدن هستند.

## ۲۱. اولویت کدنویسی

ترتیب پیاده‌سازی:

1. recipe schema
2. typography renderer
3. FFmpeg overlay renderer
4. voice noise removal
5. voice cinematic processing chain
6. music import and normalize
7. audio mixer with ducking
8. cover generator
9. QC checker
10. integration with Supabase Storage
11. Studio Bot edit commands
12. tests

## ۲۲. اصل نهایی معماری

ادیتور الینا باید خروجی حرفه‌ای و قابل انتشار بسازد، اما نباید از روز اول تلاش کند جای همه ابزارهای تدوین را بگیرد.

هدف MVP:
- فارسی درست
- صدای واضح و سینمایی
- موسیقی اختصاصی
- خروجی تمیز
- کنترل‌پذیری
- حفظ حریم خصوصی
- اتصال به مسیر تأیید و انتشار

## ۲۳. موتور صوتی

سیستم صوتی الینا از چهار مرحله تشکیل می‌شود:

### ۲۳.۱. نویزگیری

صدای خام ویس یا نریشن قبل از هر پردازش باید تمیز شود.

ابزار پیشنهادی فاز اول:
- pedalboard (Spotify) با NoiseGate و optional plugins

ابزار پشتیبان:
- noisereduce
- pysndfx

ابزار دستی بیرونی:
- Adobe Podcast Enhance Speech

هدف:
- حذف نویز پس‌زمینه
- حذف هوم و هیس
- حذف صداهای محیطی
- بدون آسیب به وضوح صدای اصلی

### ۲۳.۲. پردازش سینمایی صدا

صدای الینا باید حس سینمایی، عمیق و صمیمی داشته باشد.

زنجیره پردازش پیشنهادی:

1. Noise Gate برای حذف صداهای ضعیف بین جملات
2. EQ برای تقویت فرکانس‌های گرم
3. Compressor برای یکنواخت کردن بلندی
4. Reverb برای حس فضای بزرگ
5. Limiter برای جلوگیری از کلیپ

ابزار فاز اول:
- pedalboard

ابزار فاز بعد:
- VST3 plugins از طریق pedalboard

### ۲۳.۳. Presetهای صوتی

Presetهای صوتی پیشنهادی:

elina_cinematic_voice:
- noise_gate_threshold_db: -40
- eq_low_shelf_gain_db: 3
- eq_presence_boost_db: 2
- compressor_threshold_db: -18
- compressor_ratio: 3
- reverb_room_size: 0.4
- reverb_wet_level: 0.15
- limiter_threshold_db: -1

maryam_natural_voice:
- noise_gate_threshold_db: -35
- eq_low_shelf_gain_db: 1
- compressor_threshold_db: -15
- compressor_ratio: 2
- reverb_room_size: 0.2
- reverb_wet_level: 0.08
- limiter_threshold_db: -1

crisis_gentle_voice:
- noise_gate_threshold_db: -45
- reverb_wet_level: 0.0
- compressor_threshold_db: -14
- compressor_ratio: 2
- limiter_threshold_db: -1
- توضیح: بدون reverb، بسیار نزدیک و امن

### ۲۳.۴. تولید موسیقی اختصاصی

الینا باید موسیقی ambient مخصوص خودش را داشته باشد که با هیچ برند دیگری اشتراک نداشته باشد.

دو مسیر مجاز:

مسیر ۱: تولید دستی با Suno
- مریم در suno.com با پرامپت فارسی/انگلیسی آهنگ می‌سازد
- فایل MP3 دانلود می‌شود
- در Supabase Storage در پوشه music/ ذخیره می‌شود
- کلید فایل در recipe به عنوان music_key استفاده می‌شود

مسیر ۲: تولید خودکار با API
- MusicAPI یا ElevenLabs Music API یا معادل
- پرامپت mood از recipe خوانده می‌شود
- فایل تولید و در Supabase Storage ذخیره می‌شود
- نیاز به اکانت پولی دارد
- در فاز MVP اختیاری است

قانون لایسنس:
- تنها موسیقی‌ای مجاز است که licence آن اجازه استفاده تجاری در Instagram را بدهد
- موسیقی رایگان از منابع نامعتبر ممنوع است

### ۲۳.۵. Presetهای موسیقی

Presetهای mood پیشنهادی برای پرامپت‌های AI music:

elina_deep_ambient:
- slow tempo
- minimal piano
- soft strings
- dark cinematic
- persian influence subtle

elina_hopeful_ambient:
- warm pads
- gentle acoustic
- soft rhythm
- healing tone

maryam_calm_educational:
- soft background
- neutral tone
- non-distracting
- warm mid frequencies

crisis_silent:
- ambient only
- almost silent
- optional low drone
- no melody

### ۲۳.۶. Recipe صوتی نمونه

{
  "audio": {
    "voice_processing": {
      "enabled": true,
      "preset": "elina_cinematic_voice",
      "noise_removal": true,
      "normalize": true,
      "target_lufs": -16
    },
    "music": {
      "source": "library",
      "key": "music/elina_deep_ambient_01.mp3",
      "gain_db": -12,
      "loop": true,
      "fade_in": 1.0,
      "fade_out": 2.0
    },
    "ducking": {
      "enabled": true,
      "target_reduction_db": 6,
      "attack": 0.2,
      "release": 0.6
    },
    "export": {
      "format": "aac",
      "sample_rate": 44100,
      "channels": 2
    }
  }
}

### ۲۳.۷. QC مخصوص صدا

پس از رندر صوتی، QC باید بررسی کند:

- سطح loudness در محدوده مجاز است
- clipping صوتی وجود ندارد
- صدای voice در میکس واضح است
- موسیقی voice را خفه نمی‌کند
- طول صدا مطابق ویدیو است
- فایل خروجی خالی نیست

### ۲۳.۸. مسیرهای فایل صوتی

- voice خام: raw/voices/
- voice پردازش‌شده: processed/voices/
- موسیقی: music/
- میکس نهایی: final/audio/

هیچ فایل صوتی در GitHub ذخیره نمی‌شود.

## ۲۴. حریم خصوصی صدا

- ویس مریم داده حساس است
- ویس واقعی نباید در تست‌ها یا logها ذخیره شود
- در تست‌ها فقط صدای مصنوعی مصرف شود
- فایل‌های صوتی حساس در Supabase Storage خصوصی نگه داشته شوند
- Signed URL موقت فقط برای زمان انتشار ساخته شود

## ۲۵. اخلاق تولید صدا

- Voice cloning بدون اجازه ممنوع است
- استفاده از صدای دیگران بدون رضایت ممنوع است
- در فاز اول فقط صدای مریم یا صداهای شفاف AI مجاز است
- موسیقی باید licence روشن داشته باشد
- Track بی‌محتوا از منابع غیرقابل‌اعتماد ممنوع است

## ۲۶. ابزارهای پیشنهادی نهایی صوتی

فاز اول:
- pedalboard
- ffmpeg
- ffprobe
- pillow
- arabic_reshaper
- python-bidi

فاز بعد:
- noisereduce
- pysndfx
- pydub
- librosa
- faster-whisper
- auto-editor

تولید موسیقی:
- Suno (دستی)
- ElevenLabs Music (API)
- MusicAPI (چند مدل)

ادیت دستی صدا:
- Adobe Podcast Enhance Speech
- Descript
- Audacity

## ۲۷. اصل نهایی صدا

ادیتور الینا نباید فقط صدا را «پخش» کند.
باید صدا را «کارگردانی» کند.

هدف:
- صدا در خدمت روایت
- سکوت در جایی که لازم است
- موسیقی که درد را همراهی می‌کند نه فرار می‌دهد
- نریشن که دیده شدن ایجاد می‌کند نه سرگرم می‌کند
- خروجی نهایی که مثل یک صحنه سینمایی حس شود
