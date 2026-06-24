# 🔌 اتصال سیستم به اکانت‌ها — راهنمای قدم‌به‌قدم
## Elina Radman — از دستی به خودکار

---

## 🎯 وضعیت الان

| کار | وضعیت |
|-----|--------|
| گمیل | ✅ `elinaradman24@gmail.com` |
| اینستاگرام | ✅ `elina.radman` — بیو + عکس |
| تیک‌تاک | ✅ `elina.radman` — بیو + عکس |
| یوتیوب | ✅ `@elina.radman` — بیو + عکس |
| پینترست | ✅ `elina.radman` — بیو + عکس |
| عکس پروفایل | ✅ `elina-profile-pic-03.jpg` روی همه |
| **اتصال خودکار** | ❌ هنوز وصل نیست |

---

## 🔴 صادقانه: من نمی‌تونم مستقیم وارد اکانت‌هات بشم

دلیل: هر اکانت نیاز به **رمز عبور + احراز هویت دو مرحله‌ای (2FA)** داره. من نه رمزتو دارم (و نباید داشته باشم)، نه می‌تونم کد ۲ مرحله‌ای رو وارد کنم. این یه لایه امنیتیه که خود پلتفرم‌ها گذاشتن.

---

## ✅ راه‌حل: سیستم از طریق API وصل می‌شه، نه رمز عبور

```
❌ روش غلط: من با رمزت لاگین کنم به اینستاگرام
✅ روش درست: تو API key می‌سازی → می‌دی به سیستم → سیستم با API پست می‌کنه
```

---

## 📋 ۴ قدم تا خودکارسازی کامل

---

### قدم ۱: ثبت‌نام در PostEverywhere (۳۰ دقیقه)

**PostEverywhere چیه؟** یه سرویس که همه پلتفرم‌ها رو با **یه API key** کنترل می‌کنه.

```
１. برو به: https://posteverywhere.ai
２. Sign up با elinaradman24@gmail.com
３. پلن Growth ($39/ماه) رو انتخاب کن
     (این پلن API access داره — بدون API نمی‌تونیم خودکار کنیم)
４. توی Dashboard برو به Settings → API Keys
５. یه API Key بساز — اسمش رو بذار "ElinaOS"
６. کپی کن — این رو بعداً لازم داریم
```

---

### قدم ۲: وصل کردن اکانت‌ها به PostEverywhere (۱۵ دقیقه)

```
１. توی Dashboard برو به Accounts / Connections
２. روی Instagram کلیک کن ← با اکانت elina.radman لاگین کن
     (PostEverywhere از OAuth استفاده می‌کنه — امنه)
３. روی TikTok کلیک کن ← وصل کن
４. روی YouTube کلیک کن ← وصل کن
۵. روی Pinterest کلیک کن ← وصل کن
۶. حالا هر اکانت یه Account ID داره
     (این رو هم کپی کن — توی فایل .env می‌ذاریم)
```

**بعد از این قدم:** PostEverywhere می‌تونه از طرف تو تو همه ۴ پلتفرم پست کنه. بدون اینکه رمزت رو به کسی بدی.

---

### قدم ۳: API Key های هوش مصنوعی (۱۵ دقیقه)

```
１. OpenAI:
     برو به: https://platform.openai.com/api-keys
     Sign up ← یه API Key بساز
     حداقل $10 شارژ کن

２. HeyGen (برای ساخت ویدیو با چهره تو):
     برو به: https://app.heygen.com
     Sign up ← پلن Creator ($24/ماه)
     Settings → API → API Key بساز
```

---

### قدم ۴: راه‌اندازی سرور (۲ گزینه)

#### گزینه A: سرور ابری (توصیه — $6/ماه)

```
１. برو به: https://hetzner.com → Cloud
２. سرور CX22 (2 CPU, 4GB RAM) = ~$6/ماه
３. Ubuntu 24.04 انتخاب کن
４. بعد از ساخته شدن SSH بزن:
     ssh root@[IP]
     apt update && apt install -y git docker.io
     git clone [پروژه]
     cd AGENT-SYSTEM
     nano .env  ← API key هات
     docker-compose up -d
```

#### گزینه B: لپ‌تاپ خودت (رایگان)

```
cd AGENT-SYSTEM
pip install -r requirements.txt
nano .env  ← API key هات
python main_runner.py --daemon
```

---

## 📱 تلگرام — رابط تو با سیستم

هر روز ساعت ۸ صبح:

```
📋 7 new content pieces ready!

Content #abc123 — OOTD Day 1
Caption: Today's OOTD: Office Elegance 🕊️...
Platforms: instagram, tiktok, pinterest

[✅ Approve]  [❌ Reject]  [✏️ Edit]
```

یه دکمه می‌زنی — پست می‌شه.

---

## 💰 هزینه ماهانه

| سرویس | قیمت |
|-------|------|
| PostEverywhere | $۳۹ |
| HeyGen | $۲۴ |
| OpenAI | ~$۲۰ |
| سرور Hetzner | ~$۶ |
| **جمع** | **~$۸۹** |

---

## ⚡ گزینه سریع (بدون سرور — رایگان)

تا سرور نداری، من دستی-نیمه‌خودکار کمکت می‌کنم:

```
من ← اسکریپت + کپشن + هشتگ + عکس آماده می‌کنم
تو ← با اپلیکیشن هر پلتفرم پست می‌کنی
```

---

**بهم بگو: بریم سراغ PostEverywhere و API key ها، یا فعلاً دستی پیش بریم؟ 🚀**