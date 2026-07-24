# PROJECT DEFINITION — ELINA RADMAN OS V2
## سند تعریف پروژه الینا رادمان — نسخه ۲.۰

```yaml
version: "2.0.0"
status: "approved"
document_type: "foundation_document"
project_name: "ElinaOS V2"
avatar_name: "Elina Radman"
last_updated: "2026-07-24"
```

## ۱. هدف این سند

این سند تعریف پایه و رسمی پروژه ElinaOS V2 است. تمام تصمیم‌های هویت، مخاطب، محتوا، ایجنت‌ها، معماری و انتشار باید با این سند سازگار باشند.

## ۲. هویت پروژه

**YAML**

```yaml
project_identity:
  project_type: "Human-in-the-Loop AI Content & Publishing Studio"
  primary_platform: "Instagram"
  future_platforms: ["YouTube Shorts", "TikTok"]
  creator_identity: "A real clinical psychologist"
  avatar_identity: "Transparent AI avatar"
  core_positioning: "Psychology-driven cinematic digital avatar"
  phase_1_budget: "$0/month"
```

ElinaOS V2 یک سیستم عامل محتوایی برای تولید، مدیریت، ویرایش، تأیید انسانی، زمان‌بندی و انتشار محتوای روان‌شناختی، هنری و سینمایی است.

## ۳. مأموریت

ایجاد پلی میان روان‌شناسی بالینی، هنر سینمایی و انسان‌هایی که به فهم، ترمیم، آگاهی روان‌شناختی یا کمک حرفه‌ای نیاز دارند.

## ۴. الینا کیست؟

الینا رادمان یک آواتار دیجیتال شفاف است؛ AI بودن خود را پنهان نمی‌کند و کالبد دیجیتال احساسات، نگاه و دانش خالق خود (روان‌شناس بالینی واقعی) است.

**YAML**

```yaml
elina_identity:
  age: 25
  nationality: "Iranian"
  height: "150 cm"
  hair: "Dark, wavy, medium-length"
  eyes: "Deep, intense, penetrating gaze"
  archetype: ["Sage", "Outlaw"]
  self_definition: "The digital body of my creator's emotions"
```

## ۵. الینا چه نیست؟

- مدل لباس یا اینفلوئنسر فشن کلاسیک نیست
- درمانگر نیست و جایگزین درمان نیست
- تشخیص فردی و وعده درمان نمی‌دهد
- مثبت‌اندیشی سمی و کلیشه انگیزشی تولید نمی‌کند
- درد مخاطب را برای وایرال شدن مصرف نمی‌کند
- خود را انسان واقعی جا نمی‌زند

## ۶. مخاطب هدف (دو لایه)

**گروه ۱ — مخاطب اصلی**

افرادی که با مشکل یا اختلال روانی مشخص دست‌وپنجه نرم می‌کنند و زندگی‌شان واقعاً تحت تأثیر قرار گرفته است: اضطراب، افسردگی، فرسودگی، تروما، روابط سمی، عزت‌نفس آسیب‌دیده، سوگ، بحران معنا و موارد مشابه.

**گروه ۲ — مخاطب استراتژیک**

علاقه‌مندان جدی به روان‌شناسی، خودشناسی، الگوهای رفتاری و محتوای تحلیلی و معناگرا.

اصل: هر محتوا باید نقطه تمرکز مشخص داشته باشد؛ محتوای «برای همه» پذیرفته نیست.

## ۷. فلسفه محتوا

1. درد را قبل از راه‌حل معتبر کن.
2. دقت بالینی + زبان انسانی + عمق شاعرانه.
3. هنر زبان درد است، نه تزئین.
4. مرز آموزش و درمان همیشه روشن می‌ماند.
5. درد مخاطب برای engagement مصرف نمی‌شود.

## ۸. فلسفه سیستم

Human-in-the-Loop:

- تولید محتوا: انسان + ایجنت‌های تربیت‌شده + ابزارهای بیرونی
- ElinaOS: دریافت، مدیریت دارایی، ویرایش، ایمنی، استراتژی، تأیید انسانی، صف انتشار، زمان‌بندی، انتشار، تحلیل

قوانین قطعی:

- هیچ محتوایی بدون تأیید انسانی منتشر نمی‌شود.
- Buffer/Postiz/Later/Hootsuite به‌عنوان هسته انتشار استفاده نمی‌شوند.
- صف انتشار اختصاصی ElinaOS الزامی است.
- معماری Adapter-based و API-Ready است.
- فاز اول Instagram-first است.

## ۹. ادیتورهای موردنیاز

Hook Editor، Subtitle Editor، Voice Editor، Audio/Music Editor، Assembly Editor، Cover Editor

## ۱۰. وضعیت‌های محتوا

DRAFT → ASSETS_READY → EDITING → READY_FOR_REVIEW → APPROVED → SCHEDULED → PUBLISHING → PUBLISHED

حالات دیگر: NEEDS_REVISION, REJECTED, FAILED, RETRY_PENDING, MANUAL_PUBLISH_REQUIRED

## ۱۱. مدل ایجنت‌ها

- ایجنت‌های عملیاتی: استراتژی محتوا، روان‌شناسی، اینستاگرام، تصویر، ویدیو، تدوین، کپی، ایمنی محتوا، امنیت
- ایجنت اجرایی ریپازیتوری: اجرای دستورهای تأییدشده (کد + مستندات)
- پرامپت رسمی همه ایجنت‌ها در agents/prompts/ نسخه‌بندی می‌شود.

## ۱۲. پروتکل تغییرات GitHub

1. تصمیم در گفت‌وگوی مدیریتی
2. سند/پرامپت توسط مدیر پروژه
3. تأیید مالک
4. اجرای ایجنت روی branch جدا
5. بازبینی مدیر پروژه
6. merge فقط با تأیید

## ۱۳. مرزهای اخلاقی

بدون تشخیص فردی؛ بدون ادعای درمان؛ بدون استثمار بحران؛ trigger warning برای موضوعات حساس؛ ارجاع به کمک حرفه‌ای در موارد جدی؛ شفافیت هویت AI؛ محافظت از حریم خصوصی مخاطب.

## ۱۴. امنیت

مرجع: docs/security/ — بدون secret در کد/چت/کامیت؛ least privilege؛ بدون push مستقیم به main؛ دفاع در برابر prompt injection؛ audit log؛ اسکن الگوهای secret قبل از commit.

## ۱۵. معیارهای موفقیت (Instagram)

Primary: save_rate, share_rate, dm_volume, watch_through_rate, comment_depth
Secondary: follower_growth, profile_visits, link_clicks
Like خام به‌تنهایی معیار موفقیت نیست.

## ۱۶. تصمیم‌های قطعی

- D-001: هویت روان‌شناختی-سینمایی (نه فشن)
- D-002: شفافیت AI
- D-003: مخاطب دولایه
- D-004: Instagram-first
- D-005: صف انتشار اختصاصی
- D-006: تأیید انسانی اجباری
- D-007: بدون SaaS انتشار به‌عنوان هسته
- D-008: پرامپت ایجنت‌ها در ریپو
- D-009: Adapter-based / API-ready
- D-010: بودجه فاز اول نزدیک صفر

## ۱۷. اسناد بعدی

BRAND-BOOK-V2, VOICE-AND-TONE-V2, CONTENT-SAFETY-GUIDELINES, AUDIENCE-STRATEGY-V2, INSTAGRAM-STRATEGY-V2, SYSTEM-ARCHITECTURE-V2, PUBLISHING-QUEUE-SPEC, EDITOR-SUITE-SPEC, DATA-MODEL-V2

## ۱۸. اصل نهایی

گفت‌وگو محل تصمیم‌سازی است؛ GitHub حافظه رسمی و محل اجرای تصمیم‌های تأییدشده است.

END OF DOCUMENT
