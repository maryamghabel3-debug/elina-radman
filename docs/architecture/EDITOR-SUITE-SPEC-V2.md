# EDITOR SUITE SPEC V2 — ElinaOS
# مشخصات معماری ادیتور هوشمند الینا

---
version: "2.0.0"
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
AUDIO MIXING
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
    "voice_gain_db": 0,
    "music_gain_db": -12,
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
- تنظیم gain
- sync ساده
- حذف سکوت در فاز بعد

### ۱۳.۴. Music Editor

مسئول:
- اضافه کردن موسیقی ambient
- loop
- fade in/out
- ducking

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

کتابخانه‌های اختیاری فاز بعد:

- moviepy
- faster-whisper
- auto-editor
- pydub

ابزارهای بیرونی:

- CapCut
- Descript
- Runway
- Submagic
- OpusClip

ابزارهای بیرونی می‌توانند در workflow انسانی استفاده شوند، اما هسته سیستم باید قابل اجرا بدون آن‌ها بماند.

## ۲۰. کارهایی که فعلاً انجام نمی‌دهیم

در فاز اول انجام نمی‌شود:

- ساخت UI کامل شبیه Submagic
- تدوین کاملاً خودکار چندصحنه‌ای
- تشخیص هوشمند beat موسیقی
- انتخاب خودکار بهترین hook
- تولید خودکار character animation
- انتشار مستقیم از ادیتور

این‌ها بعد از MVP قابل اضافه شدن هستند.

## ۲۱. اولویت کدنویسی

ترتیب پیاده‌سازی:

1. recipe schema
2. typography renderer
3. FFmpeg overlay renderer
4. audio mixer with ducking
5. cover generator
6. QC checker
7. integration with Supabase Storage
8. Studio Bot edit commands
9. tests

## ۲۲. اصل نهایی

ادیتور الینا باید خروجی حرفه‌ای و قابل انتشار بسازد، اما نباید از روز اول تلاش کند جای همه ابزارهای تدوین را بگیرد.

هدف MVP:
- فارسی درست
- صدای واضح
- خروجی تمیز
- کنترل‌پذیری
- حفظ حریم خصوصی
- اتصال به مسیر تأیید و انتشار
