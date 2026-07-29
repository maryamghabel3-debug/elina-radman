# EDITOR SUITE SPEC V2 — ElinaOS
# مشخصات معماری ادیتور هوشمند الینا

---
version: "2.2.0"
status: "APPROVED_FOR_MVP_IMPLEMENTATION"
document_type: "Architecture Specification"
project: "ElinaOS V2"
module: "Elina Smart Editor Suite"
last_updated: "2026-07-29"
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
      "normalize": true,
      "target_lufs": "CONFIGURED_TARGET_LUFS",
      "max_true_peak_db": "CONFIGURED_MAX_TRUE_PEAK_DB",
      "loudness_mode": "two_pass",
      "preserve_original": true
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

مسیر ترجیحی:

Persian text
↓
Pillow with libraqm
↓
direction = rtl
↓
OpenType shaping and kerning
↓
transparent PNG
↓
FFmpeg overlay

مسیر fallback در محیطی که libraqm در دسترس نیست:

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

قواعد:

- وجود libraqm هنگام startup بررسی شود.
- متن ترکیبی فارسی، انگلیسی، اعداد، ایموجی و علامت‌گذاری جداگانه تست شود.
- renderer نباید بدون هشدار بین مسیر اصلی و fallback جابه‌جا شود.
- line wrapping باید براساس اندازه واقعی rendered text انجام شود.
- تصاویر Hook، Subtitle و Cover باید نسخه‌گذاری و از یکدیگر جدا باشند.
- متن‌های طولانی نباید خارج از safe area رندر شوند.

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


- Loudness normalization برای فایل نهایی باید ترجیحاً با FFmpeg loudnorm در حالت two-pass انجام شود.
- مقدار نهایی LUFS و True Peak پس از تست شنیداری و تأیید مالک در preset ثبت می‌شود.
- هیچ مقدار loudness نباید بدون QC به‌عنوان استاندارد قطعی همه صداها استفاده شود.
- فایل نهایی ویدیویی با Audio Sample Rate برابر 48 kHz تولید می‌شود.
- صدای voice می‌تواند mono باقی بماند، اما final mix می‌تواند stereo باشد.
- Stereo widening روی نریشن پیش‌فرض نیست و فقط با preset تأییدشده مجاز است.

## ۱۱. Audio Ducking

در ویدیوهای روان‌شناختی، موسیقی Ambient مهم است اما نباید نریشن را خفه کند.

ElinaOS باید Auto-Ducking را پشتیبانی کند.

یعنی:
- وقتی voice/narration فعال است، صدای موسیقی پس‌زمینه کاهش پیدا کند
- وقتی voice سکوت دارد، موسیقی به سطح طبیعی برگردد

- موتور ترجیحی MVP برابر FFmpeg sidechaincompress است.
- نریشن ورودی sidechain و موسیقی ورودی اصلی تحت compression است.
- Ducking فقط در بازه حضور واقعی نریشن اعمال می‌شود.
- attack، release، threshold، ratio و makeup gain باید در Recipe قابل تنظیم باشند.
- میکس نهایی باید بررسی کند موسیقی در مکث‌ها ناگهان جهش نکند.
- اگر voice وجود ندارد، ducking باید غیرفعال شود.
- Ducking نباید جایگزین تنظیم دستی gain موسیقی شود.

## ۱۲. تنظیمات Ducking

Recipe باید این فیلدها را داشته باشد:

{
  "ducking": {
    "enabled": true,
    "engine": "ffmpeg_sidechaincompress",
    "target_reduction_db": 6,
    "threshold": "CONFIGURED_DUCKING_THRESHOLD",
    "ratio": "CONFIGURED_DUCKING_RATIO",
    "attack": 0.2,
    "release": 0.6,
    "makeup_gain_db": 0
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
- سنجش loudness و true peak
- تشخیص clipping
- تشخیص silent audio
- تشخیص black frame ابتدا و انتها
- تشخیص frozen frame طولانی
- بررسی audio/video duration mismatch
- بررسی subtitle overflow
- بررسی subtitle reading speed
- بررسی mixed Persian/English rendering
- بررسی safe area برای Hook و Caption
- بررسی وجود Cover در presetهایی که Cover الزامی است
- بررسی hash و اندازه فایل
- بررسی پاک‌شدن فایل‌های temp
- بررسی نبود metadata حساس در خروجی
- سطح loudness در محدوده مجاز است
- clipping صوتی وجود ندارد
- متن hook داخل safe area است
- خروجی صفر بایت نیست
- مدت ویدیو در محدوده مجاز است
- هیچ فایل موقت حساس باقی نمانده

اگر هر بررسی بحرانی fail شد:

- status = edit_failed یا manual_edit_required
- محتوا نباید READY_FOR_REVIEW شود.

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

Phase A — Deterministic MVP:
1. Recipe schema and validation
2. Persian Typography Renderer
3. FFmpeg overlay renderer
4. Basic audio decode/resample
5. Denoise with FFmpeg afftdn
6. Voice processing with Pedalboard
7. Sidechain ducking
8. Loudness normalization
9. Cover generator
10. QC checker
11. Supabase Storage integration
12. Unit and integration tests

Phase B — Assisted Intelligence:
1. faster-whisper transcription
2. Subtitle segmentation
3. Keyword highlight suggestions
4. Edit Intelligence recipe generation
5. Studio Bot recipe review
6. Preview rendering

Phase C — External Providers:
1. AI music adapter
2. Runway/Descript/Submagic adapters
3. Advanced denoise adapter
4. Smart clipping and scene analysis
5. Optional web-based Studio UI

## ۲۸. Transcription and Caption Intelligence

برای ایجاد تجربه‌ای نزدیک به ادیتورهای هوشمند، سیستم باید بتواند نریشن را به زیرنویس زمان‌بندی‌شده تبدیل کند.

قابلیت‌ها:

- speech-to-text فارسی
- word-level یا segment-level timestamps
- تقسیم هوشمند جمله‌ها
- گروه‌بندی کلمات کوتاه و خوانا
- تشخیص مکث
- پیشنهاد highlight برای کلمات کلیدی
- پشتیبانی از اصلاح دستی متن و timestamp
- ساخت Subtitle Overlayهای فارسی
- تولید SRT، VTT و Recipe Segment
- جلوگیری از نمایش بیش از حد کلمه در هر قاب

موتور پیشنهادی:

- faster-whisper به‌عنوان موتور محلی اختیاری
- transcript آماده‌شده توسط ایجنت خارجی
- Adapter برای سرویس‌های خارجی در آینده

قواعد:

- Transcript باید قبل از انتشار قابل ویرایش باشد.
- متن فارسی باید از نظر غلط تایپی و معنایی بازبینی شود.
- هیچ Transcript حساسی در log ذخیره نشود.
- تایمینگ و متن اصلاح‌شده باید version داشته باشند.
- سیستم باید Original Transcript و Corrected Transcript را از هم جدا نگه دارد.
- کلمات کلیدی فقط پیشنهاد می‌شوند و تصمیم نهایی با انسان است.

Recipe زیرنویس باید بتواند این فیلدها را داشته باشد:

{
  "subtitles": {
    "enabled": true,
    "transcription_source": "provided_text | faster_whisper | external_adapter",
    "timing_mode": "word | segment",
    "language": "fa",
    "max_words_per_segment": "CONFIGURED_MAX_SUBTITLE_WORDS",
    "max_chars_per_line": "CONFIGURED_MAX_SUBTITLE_CHARS",
    "highlight_keywords": true,
    "manual_review_required": true,
    "style": "farsi_cinematic_bottom"
  }
}

---

## ۲۹. Edit Intelligence

Edit Intelligence موتور تصمیم‌گیری است و باید خروجی Recipe تولید کند، نه فایل ویدیویی.

ورودی‌ها:

- نوع محتوا
- فایل‌های مدیا
- نریشن
- کپشن
- هوک
- پرسونای هدف
- preset برند
- نیازهای ادیت ثبت‌شده در Studio Bot

پیشنهادهای قابل تولید:

- محل Hook
- طول Hook
- Subtitle segmentation
- Highlight keywords
- Trim points
- مکث‌های مهم
- شدت Music
- نوع Voice Preset
- نیاز به Cover
- نیاز به Human Edit
- ریسک safe-area
- ریسک خوانایی

قواعد:

- پیشنهادها خودکار اجرا نمی‌شوند مگر Recipe تأیید شده باشد.
- محتوای L3 و L4 نیازمند بررسی انسانی Recipe است.
- Edit Intelligence حق تغییر معنای نریشن را ندارد.
- Edit Intelligence نباید ادیت احساسی دستکاری‌گر پیشنهاد دهد.
- خروجی آن باید deterministic schema داشته باشد.
- در صورت ابهام باید manual_edit_required پیشنهاد دهد.

---

## ۳۰. External Editor and AI Provider Adapters

ابزارهای بیرونی باید از طریق Adapterهای مستقل متصل شوند.

Adapterهای احتمالی:

- Runway Adapter
- Descript Adapter
- Submagic Adapter
- OpusClip Adapter
- Eleven Music Adapter
- Suno Manual Import Adapter

قواعد:

- هسته سیستم نباید به یک Provider خاص وابسته باشد.
- نبود API Key نباید کل ادیتور محلی را متوقف کند.
- ارسال فایل حساس به سرویس خارجی فقط با تأیید انسانی مجاز است.
- Provider نباید Signed URL بلندمدت دریافت کند.
- URL باید کوتاه‌عمر و محدود باشد.
- API Key فقط از environment variable خوانده می‌شود.
- Responseهای Provider نباید شامل Secret در log باشند.
- تمام Providerها باید timeout، retry محدود و error classification داشته باشند.
- قابلیت هر Provider باید با وضعیت ENABLED، DISABLED یا MANUAL_ONLY ثبت شود.

---

## ۳۱. AI Music Provenance and Licensing

هر موسیقی تولیدشده یا واردشده باید یک License Manifest داشته باشد.

فیلدهای لازم:

- provider
- model
- generation_mode
- prompt
- generated_at
- provider_track_id
- subscription_tier
- license_type
- terms_version_or_review_date
- commercial_use_verified
- attribution_required
- approved_by
- source_file_hash
- storage_key

قواعد:

- استفاده از نام خواننده، گروه، آهنگ یا درخواست تقلید مستقیم از هنرمند ممنوع است.
- Track بدون وضعیت commercial_use_verified نباید وارد محتوای قابل انتشار شود.
- وضعیت لایسنس باید پیش از انتشار دوباره بررسی شود.
- تغییر Provider یا پلن ممکن است شرایط لایسنس را تغییر دهد.
- فایل موسیقی تولیدشده نباید به‌عنوان دارایی انحصاری فرض شود مگر شرایط Provider آن را تأیید کند.
- خروجی موسیقی و Manifest باید به‌صورت خصوصی نگهداری شوند.
- استفاده تجاری فقط در محدوده مجوز پلن و Provider مجاز است.

---

## ۳۲. Render Jobs, Versioning and Idempotency

هر عملیات رندر باید یک Render Job مستقل باشد.

وضعیت‌ها:

- queued
- validating
- downloading_assets
- preparing_typography
- processing_audio
- rendering
- quality_check
- completed
- failed
- cancelled
- manual_edit_required

هر Job باید شامل این فیلدها باشد:

- job_id
- content_id
- recipe_version
- input_asset_versions
- output_asset_key
- status
- attempts
- error_code
- error_detail_sanitized
- created_at
- started_at
- completed_at
- approved_by

قواعد:

- فایل ورودی overwrite نشود.
- هر خروجی نسخه جدید بگیرد.
- اجرای دوباره همان recipe نباید چند خروجی نامشخص تولید کند.
- Recipe hash برای idempotency استفاده شود.
- Retry محدود و قابل تنظیم باشد.
- خروجی failed نباید READY_FOR_REVIEW شود.
- Cancel باید قابل audit باشد.
- فایل‌های temp بعد از success یا failure پاک شوند.

---

## ۲۲. اصل نهایی

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

### ۲۳.۱. نویزگیری و پاک‌سازی صدای خام

NoiseGate یک موتور کامل Noise Reduction نیست.

NoiseGate فقط می‌تواند صدای کم‌حجم بین جمله‌ها را کاهش دهد و نباید به‌عنوان راه‌حل حذف نویز هنگام صحبت معرفی شود.

مسیر پیشنهادی MVP:

1. بررسی ورودی با FFprobe
2. High-pass filter برای حذف rumble بسیار پایین
3. حذف hum در صورت تشخیص
4. Denoise با FFmpeg afftdn
5. NoiseGate ملایم فقط برای فاصله بین جمله‌ها
6. بررسی مصنوعی‌شدن یا افت وضوح صدا
7. ارسال به مرحله EQ و Compression

مسیرهای پیشرفته و اختیاری:

- FFmpeg arnndn در صورت وجود model تأییدشده
- DeepFilterNet یا RNNoise از طریق Adapter جدا
- noisereduce برای پردازش کنترل‌شده و آزمایشی
- ابزارهای بیرونی مانند Adobe Podcast یا Descript فقط با تأیید انسانی

قواعد:

- Denoise نباید به‌صورت غیرقابل‌بازگشت روی فایل اصلی اعمال شود.
- فایل خام باید immutable باقی بماند.
- خروجی denoise در یک asset جدید ذخیره شود.
- اگر پردازش باعث صدای رباتی، metallic artifact یا افت حروف فارسی شد، وضعیت باید manual_edit_required شود.
- مقدار denoise باید توسط preset تعیین شود، نه hardcode در کد.
- ویس واقعی مریم نباید بدون تأیید انسانی به سرویس خارجی ارسال شود.


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
      "target_lufs": "CONFIGURED_TARGET_LUFS",
      "max_true_peak_db": "CONFIGURED_MAX_TRUE_PEAK_DB",
      "loudness_mode": "two_pass",
      "preserve_original": true,
      "target_lufs_example": -16
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
      "sample_rate": 48000,
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
