# 💰 ZERO COST AUTOMATION — Elina Radman
## کاملاً رایگان — $0/ماه
## June 2026

---

## 🎯 استک رایگان

| نیاز | سرویس رایگان | محدودیت | وضعیت |
|------|-------------|---------|--------|
| 📤 پست خودکار | **Postiz (متن‌باز)** | نامحدود، self-host | ✅ Instagram + TikTok + Pinterest |
| ▶️ یوتیوب | **YouTube Data API** | ۱۰,۰۰۰ درخواست/روز | ✅ |
| 🖼️ تولید عکس | **Leonardo AI** | ۱۵۰ عکس/روز | ✅ ۷ عکس روزانه |
| 🧠 تولید اسکریپت | **Google Gemini API** | ۱۵۰۰ درخواست/روز | ✅ |
| ⏰ زمان‌بندی | **GitHub Actions** | ۲۰۰۰ دقیقه/ماه | ✅ |
| 📱 تأیید محتوا | **Telegram Bot** | کاملاً رایگان | ✅ |
| 💻 سرور | **نیاز نیست** | GitHub Actions = سرور | ✅ |

---

## 🔄 چطور کار می‌کنه

```
GitHub Actions (سرور رایگان)
│
├── هر روز ساعت ۲:۳۰ بامداد
│   ├── Google Gemini → اسکریپت + کپشن + هشتگ می‌سازه
│   └── ذخیره‌سازی تو گیت‌هاب
│
├── ساعت ۸ صبح
│   └── Telegram → الینا:
│       "📋 ۳ محتوای جدید آماده‌ست"
│       [✅ تایید] [❌ رد]
│
├── الینا تأیید می‌کنه
│   └── Postiz API → پست تو:
│       📷 Instagram 🎵 TikTok 📌 Pinterest
│
└── YouTube → YouTube Data API جداگانه
```

---

## 📋 ۵ قدم راه‌اندازی (۱ ساعت)

### قدم ۱: Postiz (۱۵ دقیقه)
- برو به: https://buffer.com
- Sign up رایگان با elinaradman24@gmail.com
- پلن Free ($۰)
- وصل کن: Instagram + TikTok + Pinterest
- Settings → API Access → API Token بگیر

### قدم ۲: Google Gemini API (۱۰ دقیقه)
- برو به: https://aistudio.google.com
- با gmail لاگین کن
- Get API Key — رایگان
- محدودیت: ۱۵۰۰ درخواست/روز

### قدم ۳: Leonardo AI (۱۰ دقیقه)
- برو به: https://leonardo.ai
- Sign up رایگان
- API Settings → API Key بگیر
- محدودیت: ۱۵۰ عکس/روز

### قدم ۴: گیت‌هاب (۲۰ دقیقه)
- برو به: https://github.com
- Sign up با elinaradman24@gmail.com
- Repository جدید: "elina-os"
- **Public** (unlimited free minutes)
- Settings → Secrets → API key ها رو بذار

### قدم ۵: تلگرام بات (۵ دقیقه)
- @BotFather → /newbot
- اسم: Elina OS
- Token رو کپی کن

---

## 💻 فایل‌های گیت‌هاب

```
elina-os/
├── .github/workflows/
│   ├── daily-content.yml  ← هر روز ۲:۳۰ اجرا
│   └── post-content.yml   ← بعد از تأیید الینا
├── scripts/
│   ├── generate.py         ← تولید محتوا
│   ├── publish.py          ← پست کردن
│   └── telegram_bot.py     ← ربات تأیید
├── content/
│   ├── queue/              ← آماده تأیید
│   └── published/          ← پست شده
└── config.py
```

---

## ⚡ چقدر طول می‌کشه

| کار | زمان |
|-----|------|
| ثبت‌نام/راه‌اندازی Postiz | ۱۵ دقیقه |
| Google Gemini API | ۱۰ دقیقه |
| Leonardo AI | ۱۰ دقیقه |
| ساخت گیت‌هاب | ۲۰ دقیقه |
| تلگرام بات | ۵ دقیقه |
| **جمع** | **۱ ساعت** |

---

## 🎯 نتیجه نهایی — $۰/ماه

- ✅ هر روز محتوا خودکار ساخته می‌شه
- ✅ ساعت ۸ صبح تلگرام میاد
- ✅ یه دکمه → پست تو ۴ پلتفرم
- ✅ **هزینه: صفر — برای همیشه**
- ✅ ۲۰۰۰ دقیقه گیت‌هاب = ۳۳ ساعت/ماه
- ✅ مصرف ما: ۳۰ ساعت/ماه ← جا داره

---

## 📊 چرا رایگانه

| سرویس | Free Tier |
|-------|-----------|
| **Postiz** | نامحدود + API رایگان (متن‌باز) |
| **GitHub Actions** | Public repo = unlimited |
| **Google Gemini** | ۱۵۰۰ req/day رایگان |
| **Leonardo AI** | ۱۵۰ image/day رایگان |
| **Telegram** | همیشه رایگان |

---

🚀 بگو «بریم» — از Postiz شروع می‌کنیم
