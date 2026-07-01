# 🚀 راهنمای قدم‌به‌قدم راه‌اندازی ElinaOS (همراه با هزینه‌ها)

این سند دقیقاً می‌گه که **تو** باید چه کارهایی انجام بدی تا سیستم زنده بشه، و **هر کدوم رایگانه یا نه**.

> 💡 خبر خوب: بدون هیچ‌کدوم از این‌ها هم کد **کرش نمی‌کنه** (همه fallback دارن). ولی برای اینکه واقعاً پست بذاره و داده واقعی بگیره، این مراحل لازمه.

---

## 📊 جدول خلاصه هزینه‌ها

| سرویس | برای چی؟ | رایگان؟ | ضروری؟ |
|-------|----------|---------|--------|
| **GitHub** | میزبانی کد + اجرای خودکار (Actions) | ✅ کاملاً رایگان (repo عمومی) | بله |
| **Google Gemini API** | نوشتن کپشن‌ها با AI | ✅ رایگان (۱۵۰۰ درخواست/روز) | بله |
| **Telegram Bot** | کنترل سیستم از تلگرام | ✅ همیشه رایگان | بله |
| **YouTube Data API** | ترند ویدیویی واقعی + آمار | ✅ رایگان (۱۰٬۰۰۰ درخواست/روز) | اختیاری |
| **Instagram Graph API** | آمار واقعی اینستاگرام | ✅ رایگان | اختیاری |
| **Postiz** | انتشار خودکار در شبکه‌ها | ✅ رایگان اگر self-host / 🟡 پولی اگر cloud | برای انتشار خودکار |
| **Reddit / Google Trends** | ترند فشن + عکس | ✅ رایگان (بدون کلید) | خودکار فعاله |

**جمع‌بندی: می‌تونی کل سیستم رو با ۰ تومان راه بندازی.** تنها جایی که ممکنه پول لازم بشه، انتشار خودکار cloud هست (که جایگزین رایگان self-host داره).

---

## مرحله ۱ — کلیدهای ضروری (رایگان، ~۲۰ دقیقه)

### ۱.۱ — Gemini API Key (رایگان)
1. برو به https://aistudio.google.com
2. با اکانت گوگل وارد شو
3. روی **"Get API Key"** → **"Create API Key"** کلیک کن
4. کلید رو کپی کن (شکلش مثل `AIza...`)

### ۱.۲ — ساخت ربات تلگرام (رایگان)
1. توی تلگرام، **@BotFather** رو باز کن
2. بزن `/newbot` → یک اسم و username برای ربات انتخاب کن
3. BotFather یک **توکن** می‌ده (مثل `123456:ABC-DEF...`) → کپی کن = `TELEGRAM_BOT_TOKEN`

### ۱.۳ — گرفتن Chat ID (رایگان)
1. توی تلگرام **@userinfobot** رو باز کن → بزن `/start`
2. عددی که می‌ده = `TELEGRAM_CHAT_ID`

### ۱.۴ — ساخت GitHub PAT (رایگان)
1. GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. **Generate new token (classic)**
3. دسترسی‌ها: تیک `repo` و `workflow` رو بزن
4. انقضا: مثلاً ۹۰ روز
5. توکن رو کپی کن = `GH_PAT`

---

## مرحله ۲ — وارد کردن کلیدها در GitHub (~۵ دقیقه)

1. برو به repo: `github.com/maryamghabel3-debug/elina-radman`
2. **Settings → Secrets and variables → Actions → New repository secret**
3. این‌ها رو یکی‌یکی اضافه کن:

| Name | Value |
|------|-------|
| `GEMINI_API_KEY` | کلید مرحله ۱.۱ |
| `TELEGRAM_BOT_TOKEN` | توکن مرحله ۱.۲ |
| `TELEGRAM_CHAT_ID` | عدد مرحله ۱.۳ |
| `GH_PAT` | توکن مرحله ۱.۴ |
| `REPO_OWNER` | `maryamghabel3-debug` |
| `REPO_NAME` | `elina-radman` |

4. بعد: **Settings → Actions → General** →
   - ✅ Allow all actions
   - ✅ Read and write permissions → **Save**

---

## مرحله ۳ — تست اولیه (~۲ دقیقه)

1. توی repo برو به تب **Actions**
2. از لیست چپ **"Generate Daily Content"** رو انتخاب کن → **Run workflow ▸**
3. چند ثانیه صبر کن تا سبز بشه
4. برو تلگرام، به ربات خودت پیام بده: `/status`
   - اگر جواب داد → 🎉 سیستم زنده‌ست!

---

## مرحله ۴ — ترند و آمار واقعی (اختیاری، رایگان)

### ۴.۱ — YouTube Data API (رایگان)
1. برو به https://console.cloud.google.com
2. یک پروژه جدید بساز
3. **APIs & Services → Library** → جستجو کن **"YouTube Data API v3"** → **Enable**
4. **APIs & Services → Credentials → Create Credentials → API Key**
5. کلید رو کپی کن → در GitHub Secrets اضافه کن با نام `YOUTUBE_API_KEY`
6. (اختیاری) `YOUTUBE_CHANNEL_ID` = آیدی کانال یوتیوب الینا برای آمار واقعی

> بدون این کلید هم ترند از Reddit + Google Trends میاد (رایگان و خودکار).

### ۴.۲ — Instagram آمار (اختیاری، رایگان ولی کمی فنی)
نیاز به اکانت **Business/Creator** اینستاگرام + اتصال به یک صفحه فیسبوک داره:
1. برو به https://developers.facebook.com → یک App بساز
2. محصول **Instagram Graph API** رو اضافه کن
3. `IG_ACCESS_TOKEN` و `IG_USER_ID` رو بگیر → در Secrets اضافه کن

---

## مرحله ۵ — انتشار خودکار (اختیاری)

برای اینکه الینا واقعاً پست بذاره، به **Postiz** نیاز داری:

### گزینه A — Postiz Cloud (سریع، 🟡 پولی)
1. برو به https://postiz.com → ثبت‌نام
2. شبکه‌های اجتماعی الینا رو وصل کن
3. از **Settings → API** توکن بگیر
4. در Secrets: `POSTIZ_API_TOKEN` و `POSTIZ_URL` (مثل `https://api.postiz.com`)

> پلن cloud معمولاً ماهانه هزینه داره (بسته به تعداد کانال).

### گزینه B — Postiz Self-Host (✅ کاملاً رایگان، فنی‌تر)
1. Postiz متن‌بازه: https://github.com/gitroomhq/postiz-app
2. با Docker روی یک سرور رایگان (مثل Oracle Cloud Free Tier) نصبش کن
3. همون `POSTIZ_API_TOKEN` و `POSTIZ_URL` خودت رو بساز

> این گزینه ۰ تومانه ولی به دانش فنی نیاز داره.

---

## ⚠️ نکته امنیتی خیلی مهم

توکن GitHub‌ای که قبلاً توی چت به اشتراک گذاشتی رو **حتماً باطل کن**:
`GitHub → Settings → Developer settings → Personal access tokens → (توکن) → Delete/Revoke`

بعد یک توکن جدید بساز و **فقط** توی GitHub Secrets بذار — هیچ‌وقت جای دیگه.

---

## ❓ اگر گیر کردی
هر مرحله‌ای مشکل داشت، بگو کدوم قدم و چه خطایی — قدم‌به‌قدم راهنماییت می‌کنم.
