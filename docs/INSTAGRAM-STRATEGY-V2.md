# INSTAGRAM STRATEGY V2 — الینا رادمان و مریم
# استراتژی اینستاگرام — نسخه ۲.۰ (بر اساس واقعیت‌های ۲۰۲۶)

```yaml
document:
  version: "2.0.0"
  status: "APPROVED"
  type: "Platform Strategy"
  last_updated: "2026-07-26"
  primary_platform: "Instagram"
  secondary_platform: "YouTube Shorts (adapter-ready)"
  related_docs:
    - "docs/BRAND-BOOK-V2.md"
    - "docs/VOICE-AND-TONE-V2.md"
    - "docs/CONTENT-SAFETY-GUIDELINES-V2.md"
    - "docs/AUDIENCE-STRATEGY-V2.md"
accounts:
  elina: "کشف، احساس، استعاره، کاراکترهای همراه"
  maryam: "توضیح، اعتبار، اعتماد، مسیر کمک و سایت"
```

---

## ۱. واقعیت‌های الگوریتم ۲۰۲۶ (مبنای این سند)

1. ریچ ارگانیک پایین است (حدود ۲ تا ۳ درصد)؛ برنده کسی است که
   سیگنال‌های کیفیت تولید کند، نه حجم.
2. سه سیگنال اصلی رتبه‌بندی ریلز:
   - Watch time (تماشا و تکمیل)
   - Sends per reach (ارسال به دایرکت — قوی‌ترین سیگنال)
   - Likes per reach (سیگنال سوم و ضعیف‌تر)
3. ارسال در دایرکت چند برابر لایک ارزش دارد. محتوای الینا باید
   «قابل فرستادن برای یک نفر خاص» طراحی شود.
4. کاروسل بیشترین engagement و save را دارد و شانس نمایش مجدد
   اسلایدهای بعدی وجود دارد.
5. Trial Reels ابزار رسمی تست روی غیرفالوورهاست: ریلز آزمایشی به
   فالوورها و گرید نمایش داده نمی‌شود و حدود ۲۴ ساعت بعد متریک اولیه می‌دهد.
6. اصالت (Originality) پاداش می‌گیرد؛ محتوای کپی و واترمارک‌دار تنزل می‌گیرد.
7. سریال‌سازی (Recurring Series) ترند کلیدی ۲۰۲۶ است: مخاطب باید
   حس کند وسط یک داستان ادامه‌دار است.
8. صیقل بیش از حد دیگر مزیت نیست؛ حس انسانی و «نقص عمدی» ترند است.

---

## ۲. تصمیم‌های قفل‌شده فاز اول

```yaml
locked:
  primary_format: "Reels"
  weekly_output_total: "3-4 قطعه در هفته برای پیج الینا"
  weekly_mix:
    reels: 3
    carousel: 1   # آموزشی/ذخیره‌محور، از هفته دوم
  reel_length_default: "30-60s"
  reel_length_range: "15-90s"
  trial_reels: "فعال برای همه ریلزهای جدید الینا"
  captions: "فارسی، معنادار، چندخطی (کپشن کوتاه تزئینی ممنوع)"
  watermark_cross_post: "ممنوع — master file تمیز برای هر پلتفرم"
  youtube_shorts: "از روز اول با همان master file — بدون واترمارک اینستاگرام"
  maryam_account: "2 محتوا در هفته (۱ توضیحی + ۱ متصل به محتوای الینا)"
  collab_tag: "استفاده از Instagram Collab برای محتوای مشترک الینا×مریم"
```

قانون فرکانس: بیش از ۵ پست در هفته ممنوع؛ افت engagement هر پست
به‌ازای حجم بیشتر، مستند است. کیفیت و سریال‌بودن مقدم است.

---

## ۳. سبد فرمت‌های محتوا (پینگ‌پنگ فقط یکی از ابزارهاست)

```yaml
formats:

  serial_character_story:
    priority: 1
    desc: "سری چندقسمتی با یک کاراکتر همراه (مثل کوچولو)"
    why: "ترند سریال‌سازی ۲۰۲۶ + retention + follow"
    cadence: "هر کاراکتر: ۳-۵ قسمت، هفته‌ای ۱-۲ قسمت"

  pov_to_collective:
    priority: 2
    desc: "شروع از تجربه فردی (تو) → گسترش به تجربه جمعی (ما)"
    why: "قلاب احساسی + shareability بالا"

  send_to_someone:
    priority: 2
    desc: "محتوایی که صریحاً برای فرستادن ساخته شده"
    cta_example: "این را برای کسی بفرست که همیشه خودش را تنبل صدا می‌زند."
    why: "sends per reach = قوی‌ترین سیگنال ۲۰۲۶"

  educational_carousel:
    priority: 3
    desc: "کاروسل آموزشی: نام‌گذاری الگو، تفاوت دو مفهوم، قدم امن"
    why: "save بالا + نمایش مجدد اسلایدها"

  myth_demolition:
    priority: 3
    desc: "تخریب یک باور غلط روان‌شناسی زرد"
    why: "share ضدکلیشه + تمایز برند"

  imperfect_raw:
    priority: 4
    desc: "لحظه خام و کم‌پرداخت (مکث، سکوت، قاب ساده)"
    why: "ترند ضدصیقل ۲۰۲۶ + انسانی‌تر شدن الینا"

  elina_maryam_bridge:
    priority: 4
    desc: "الینا احساس را باز می‌کند، مریم توضیح بالینی می‌دهد (پینگ‌پنگ/Collab)"
    why: "انتقال اعتماد + قیف اخلاقی به سایت"
    cadence: "هفته‌ای حداکثر ۱"
```

---

## ۴. آناتومی ریلز الینا

```text
0-3s   هوک فارسی (متن روی تصویر + نریشن)
        - جمله «تو»یی یا نام‌گذاری درد
        - قانون: بدون مقدمه، بدون لوگو
3-15s  بدنه: استعاره بصری / تعامل با کاراکتر / روایت
15-40s عمق: نام‌گذاری الگو (لحن غیرشخصی طبق VOICE-AND-TONE)
پایان   جمع‌بندی انسانی + CTA نرم
        - CTA اولویت‌دار: ارسال («بفرست برای...») سپس ذخیره
subtitle: فارسی، خوانا، همیشه روشن
loop:   ترجیحاً پایان به شروع وصل شود (replay = watch time)
```

قوانین:
- هر ریلز فقط یک درد/یک پیام.
- محتوای «برای همه» ممنوع (طبق AUDIENCE-STRATEGY).
- هشدار محتوا طبق CONTENT-SAFETY-GUIDELINES.

---

## ۵. پروتکل Trial Reels

```yaml
trial_protocol:
  scope: "همه ریلزهای الینا در فاز تست"
  wait_window: "24-72h"
  evaluate:
    - non_follower_reach
    - watch_time / completion
    - sends
    - saves
    - profile_visits
  decision:
    strong: "انتشار عمومی + برنامه‌ریزی قسمت بعدی سری"
    medium: "بازنویسی هوک/کاور و تست مجدد نسخه دوم"
    weak: "آرشیو + ثبت درس‌آموخته در گزارش هفتگی"
  rule: "هر موضوع حداکثر ۲ بار تست می‌شود؛ بعد کنار گذاشته می‌شود"
```

---

## ۶. KPIها (طبق مأموریت، نه vanity)

```yaml
primary_kpis:
  sends_per_reach: "قوی‌ترین سیگنال — هدف‌گذاری بعد از ۳۰ روز داده"
  watch_time_completion: "بالاتر از میانه حساب"
  saves_per_reach: "شاخص ارزش عمیق"
  profile_visits_to_follow: "کیفیت جذب"
secondary_kpis:
  qualified_dms: "سؤال مشخص، غیربحرانی"
  elina_to_maryam_crossover: "بازدید از پیج مریم بعد از محتوای الینا"
  bio_link_clicks: "ورود به قیف سایت (فاز بعد)"
ignored:
  - raw_likes
  - follower_count_alone
rule_30_days: "هیچ benchmark عددی ثابت در ۳۰ روز اول؛ فقط مقایسه با میانه خود حساب"
```

---

## ۷. نقش دو حساب و پل به سایت

```text
الینا (Reels سریالی/احساسی)
   │  Collab هفتگی + تگ + استوری متقابل
   ▼
مریم (توضیح بالینی، face-to-camera، اعتماد)
   │  CTA شفاف و غیرفروشی در بیو و کپشن
   ▼
سایت (خدمات روان‌شناختی — فاز درآمد طبق AUDIENCE-STRATEGY)
```

قوانین:
- فروش مستقیم از پیج الینا ممنوع.
- محتوای بحران فقط با تأیید مریم (Crisis Mode طبق Brand Book).
- Collab post برای محتوای مشترک تا هر دو حساب از یک محتوا رشد کنند.

---

## ۸. YouTube Shorts (Adapter از روز اول)

```yaml
youtube_shorts:
  source: "همان master file بدون واترمارک"
  title: "فارسی + کلیدواژه درد (سرچ‌محور)"
  description: "خلاصه کپشن + بدون لینک‌های کلیک‌ناپذیر اضافی"
  goal_phase_one: "حضور و تست، نه رشد فعال"
  metric: "فقط ثبت؛ بهینه‌سازی از فاز ۲"
```

---

## ۹. ریتم هفتگی پیشنهادی (فاز تست ۳۰ روزه)

```yaml
weekly_rhythm:
  monday:    "Reel سریالی (کاراکتر/موضوع ادامه‌دار)"
  wednesday: "Reel مستقل (pov_to_collective یا send_to_someone)"
  friday:    "Reel سوم یا Carousel آموزشی (تناوب هفتگی)"
  weekend:   "Story سبک: نظرسنجی/سؤال کم‌ریسک (بدون افشای تروما)"
  maryam:
    - "۱ ویدیوی توضیحی مستقل"
    - "۱ محتوای متصل (Collab یا واکنش به ریلز الینا)"
review:
  weekly: "گزارش KPI + تصمیم سری بعدی"
  monthly: "بازنگری پرسونا و فرمت‌ها طبق پروتکل ۳۰ روزه AUDIENCE-STRATEGY"
```

---

## ۱۰. ایجنت‌های وابسته به این سند

| ID | نام | خوراک از این سند |
|----|-----|------------------|
| ELN-TREND-01 | Trend Hunter | فرمت‌ها، ترندهای مجاز، فیلتر هویت |
| ELN-STRAT-01 | Content Strategist | سبد فرمت، ریتم هفتگی، سری‌ها |
| ELN-HOOK-01 | Hook & Scenario Writer | آناتومی ریلز، قواعد هوک |
| ELN-ANALYTICS-01 | Performance Analytics | KPIها، پروتکل Trial، گزارش هفتگی |
| ELN-GROWTH-INTEL-01 | Growth Intelligence | رصد تغییرات الگوریتم/قابلیت‌ها و پیشنهاد مستند |
| ELN-SAFE-01 | Safety Guardian | گیت ایمنی قبل از صف انتشار |

هر ایجنت با Agent Package کامل (mission, inputs, outputs, prompts,
checklists) جداگانه ثبت و به مالک تحویل می‌شود.

---

## ۱۱. اصل نهایی

> در اینستاگرام ۲۰۲۶، برنده کسی نیست که بیشتر منتشر می‌کند؛
> کسی است که محتوایش «فرستاده می‌شود».
> الینا باید چیزی بسازد که یک انسان، آن را برای انسان دیگری بفرستد
> و بگوید: «این تویی.»
