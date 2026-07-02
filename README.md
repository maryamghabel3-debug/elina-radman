# 🕊️ Elina Radman — AI Influencer OS

> **"Style has no size."** — سیستم خودکار مدیریت محتوا و شبکه‌های اجتماعی با هوش مصنوعی — **هزینه: $۰/ماه**

---

## 📖 پروژه چیه؟

**ElinaOS** یه سیستم کامل مبتنی بر [GitHub Actions](https://github.com/features/actions) و [Google Gemini API](https://aistudio.google.com) است که به صورت **کاملاً رایگان** محتوای اینفلوئنسر فشن رو می‌سازه، زمان‌بندی می‌کنه، تأیید می‌گیره، و پست می‌کنه.

---

## 👤 الینا رادمان کیه؟

| مشخصات | |
|--------|-----|
| **نام برند** | Elina Radman |
| **نیچ** | Petite Quiet Luxury Fashion |
| **قد** | 150cm / 4'11" |
| **وزن** | 43kg |
| **پلتفرم‌ها** | Instagram @elina.radman · TikTok · YouTube · Pinterest |
| **زبان** | 🇬🇧 English + 🇮🇷 فارسی |
| **شعار** | "Style has no size." |
| **هشتگ** | #StyledByElina |

---

## 🤖 معماری سیستم

```
GitHub Actions (سرور رایگان)
│
├── 🔥 TrendHunter — ترندهای واقعی فشن (Reddit + Google + YouTube) با عکس
├── 🖼️ TrendVisualAnalyzer — پالت رنگ عکس‌های ترند رو تحلیل می‌کنه
├── 🎨 ContentCreator — کپشن + هشتگ بر اساس ترندهای زنده می‌سازه
├── ✍️ PromptEngineer — prompt عکس/ویدیوی سینمایی می‌سازه
├── 🛍️ ProductHunter — محصولات افیلیت پیدا می‌کنه
├── 👗 FashionStylist — moodboard هفتگی می‌سازه
├── 📊 PerformanceAnalyzer — آمار واقعی رو تحلیل و استراتژی می‌ده
├── 📤 Publisher — تو Instagram + TikTok + Pinterest پست می‌کنه
├── 🎬 DirectorAgent (video_generator) — مدیر پروژه ویدیو
├── 🧭 LLMRouter — بین مدل‌های مختلف LLM مسیریابی می‌کنه
└── 🐙 GitHubManager — کدهای گیت‌هاب رو مدیریت می‌کنه
│
├── ⏰ daily-content.yml — هر شب ۲:۳۰ صبح اجرا می‌شه
├── 📱 bot-runner.yml — هر ۵ دقیقه ربات تلگرام رو بیدار می‌کنه
└── 📤 post-content.yml — روزی ۳ بار پست تأییدشده منتشر می‌کنه
```

---

## 📱 ربات تلگرام — @ElinaRA_bot

الینا از طریق تلگرام کل سیستم رو کنترل می‌کنه:

| دستور | توضیح |
|-------|--------|
| `/status` | وضعیت سیستم |
| `/content` | ساخت ۳ پست جدید با Gemini |
| `/list` | دیدن صف محتوا |
| `/approve شناسه` | تأیید و انتشار محتوا |
| `/reject شناسه` | رد محتوا |
| `/trends` | ترندهای فشن روز |
| `/agents` | لیست ایجنت‌ها |
| `/github` | وضعیت گیت‌هاب |
| `/ghedit مسیر \| کد` | ویرایش کد از طریق تلگرام |
| `/help` | راهنمای کامل |

💬 *هر پیامی که دستور نباشه → با Gemini چت می‌کنه*

---

## 🏗️ ساختار فایل‌ها

```
elina-radman/
├── .github/workflows/
│   ├── daily-content.yml      ← تولید محتوای روزانه (۲:۳۰ صبح)
│   ├── bot-runner.yml          ← ربات تلگرام (هر ۵ دقیقه)
│   └── post-content.yml        ← انتشار (۳ بار در روز)
├── agents/
│   ├── base.py                 ← کلاس پایه ایجنت
│   ├── trend_hunter.py         ← پیدا کردن ترندها
│   ├── content_creator.py      ← ساخت اسکریپت و کپشن
│   ├── publisher.py            ← انتشار در پلتفرم‌ها
│   └── github_manager.py       ← مدیریت گیت‌هاب
├── scripts/
│   ├── elina_bot.py            ← ربات تلگرام (۱۸ فرمان)
│   ├── generate.py             ← تولید محتوا با Gemini
│   └── publish.py              ← انتشار با Postiz API
├── docs/                       ← مستندات استراتژی و دایرکتوری‌های جامع (۱۷ فایل)
│   ├── FREE-AI-CHARACTER-TOOLS-2026.md  ← ۲۵ وب‌سایت و ابزار حفظ هویت چهره
│   ├── TOP-USABLE-AI-AGENTS-GITHUB-2026.md ← ۲۰ ایجنت متن‌باز و آماده اجرا
│   └── AFFILIATE-AND-IMAGE-GUIDE.md     ← راهنمای افیلیت و سکرت‌ها
├── images/                     ← عکس‌های برند (۱۱ فایل)
├── content/queue/              ← صف محتوا
├── dashboard.html              ← داشبورد مدیریت
├── SETUP.md                    ← راهنمای نصب
└── README.md                   ← همین فایل
```

---

## 💰 هزینه: $۰/ماه

| سرویس | قیمت | کاربرد |
|-------|------|--------|
| GitHub Actions | **$۰** — public repo = unlimited | سرور + زمان‌بندی |
| Google Gemini API | **$۰** — ۱۵۰۰ درخواست/روز | ساخت اسکریپت + چت |
| Postiz | **$۰** — متن‌باز و self-host | انتشار در IG + TT + Pinterest + ... |
| Telegram Bot API | **$۰** — همیشه رایگان | رابط کاربری |
| YouTube Data API | **$۰** — ۱۰,۰۰۰ درخواست/روز | انتشار در یوتیوب |
| Leonardo AI | **$۰** — ۱۵۰ عکس/روز | ساخت تصویر (آینده) |

---

## 🚀 چطور نصب کنم؟

۱. این ریپو رو Fork کن
۲. Settings → Secrets → Actions ← ۷ تا Secret اضافه کن (طبق `SETUP.md`)
۳. Settings → Actions → General ← Read/write + Allow all
۴. Actions → Generate Daily Content → Run workflow ▸
۵. برو تلگرام `@ElinaRA_bot` ← بزن `/status`

---

## 🎨 برند

| رنگ | کد |
|------|-----|
| Cream | `#F5F0E8` |
| Beige | `#D4C5B9` |
| Camel | `#C4A882` |
| Charcoal | `#3A3A3A` |

---

## ⚠️ امنیت

- **همه API key ها در GitHub Secrets ذخیره می‌شن** — نه در کد
- Push Protection فعاله
- هر ۳۰ روز یکبار کلیدها رو Regenerate کن

---

*Built with ❤️ — 2026 — $0/month by default · MIT License*
