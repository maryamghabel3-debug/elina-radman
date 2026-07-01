# 🔥 راهنمای ترندیابی (TrendHunter)

این سند توضیح می‌ده که سیستم چطور ترندهای واقعی فشن و «عکس‌هایی که بیشترین ویو می‌گیرن» رو پیدا می‌کنه.

## منابع داده (همه رایگان، بدون کلید API)

| منبع | چی می‌ده | وضعیت |
|------|----------|-------|
| **Reddit** — فیدهای `top/.rss?t=week` | پست‌های واقعی فشن مرتب‌شده بر اساس **upvote** (معیار محبوبیت/ویو) + **URL عکس** | ✅ کار می‌کنه |
| **Google Trends RSS** | جستجوهای پرطرفدار (فیلترشده روی کلمات فشن) + تخمین ترافیک | ✅ کار می‌کنه |
| **YouTube Data API v3** | ویدیوهای ترند واقعی با **تعداد ویو/لایک واقعی** + تصویر بندانگشتی | ✅ با `YOUTUBE_API_KEY` |
| ~~Pinterest RSS~~ | ~~ترندهای پینترست~~ | ❌ پینترست این endpoint رو حذف کرده (404) |

## کش (Cache)
نتایج ترند به مدت **۶ ساعت** در `content/trends_cache.json` کش می‌شن تا از rate limit ردیت جلوگیری بشه و فراخوانی مجدد آنی باشه. برای دور زدن کش: `TrendHunter().run(use_cache=False)`.

## تحلیل بصری ترند (TrendVisualAnalyzer)
ایجنت `TrendVisualAnalyzer` عکس‌های پرویو رو دانلود می‌کنه، **پالت رنگ غالب** و لحن رنگی رو استخراج می‌کنه (`content/trend_visuals.json`)، و `PromptEngineer` هنگام ساخت prompt عکس‌های الینا، اون‌ها رو به سمت رنگ‌های ترند color-grade می‌کنه — یعنی عکس‌های الینا از نظر بصری شبیه چیزی می‌شن که همین الان ویو می‌گیره.

```python
from agents.trend_visual_analyzer import TrendVisualAnalyzer
report = TrendVisualAnalyzer().run()   # {top_colors, dominant_tones, ...}
```

### زیرردیت‌های استفاده‌شده (مرتبط با نیچ الینا)
- `r/femalefashionadvice`
- `r/petitefashionadvice` ← دقیقاً نیچ الینا (petite)
- `r/womensstreetwear`
- `r/streetwear`

می‌تونی این لیست رو در `agents/trend_hunter.py` → `_FASHION_SUBS` تغییر بدی.

## استفاده

```python
from agents.trend_hunter import TrendHunter

th = TrendHunter()
th.run()                       # همه ترندها (Reddit + Google + فرمت‌های همیشگی)
top = th.top_images(limit=5)   # فقط عکس‌های پرویو
for t in top:
    print(t["name"], t["image"], t["url"])
```

از تلگرام:
- `/trends` → لیست ترندهای زنده
- `/topimages` → عکس‌هایی که بیشترین ویو می‌گیرن

## چطور «ویو بیشتر» تشخیص داده می‌شه؟
فیدهای Reddit با مرتب‌سازی **top** برمی‌گردن، یعنی پست‌های اول بیشترین upvote (و در نتیجه بیشترین بازدید/تعامل) رو در بازه زمانی انتخاب‌شده دارن. فیلد `popularity_rank` این رتبه رو نگه می‌داره (۱ = بالاترین).

## محدودیت‌ها و نکات
- **محدودیت نرخ (Rate limit)**: Reddit به درخواست‌های سریع HTTP 429 می‌ده. کد با backoff مدیریتش می‌کنه، ولی در محیط‌های shared (مثل GitHub Actions) ممکنه بعضی درخواست‌ها ناموفق بشن. با `time.sleep` بین زیرردیت‌ها این ریسک کم شده.
- **User-Agent**: Reddit یک User-Agent توصیفی می‌خواد؛ در کد تنظیم شده.
- اگر همه منابع زنده در دسترس نباشن، سیستم داده mock **با برچسب واضح** برمی‌گردونه تا هیچ‌وقت کرش نکنه.

## ارتقاهای پیشنهادی آینده
- **YouTube Data API** (رایگان، ۱۰٬۰۰۰ درخواست/روز) برای ترندهای ویدیویی و شمارش ویو واقعی.
- **دانلود و تحلیل عکس‌های ترند** با یک مدل بینایی برای استخراج پالت رنگ/استایل و تزریق به PromptEngineer.
- **کش کردن نتایج** (مثلاً ۶ ساعت) برای کاهش فشار روی Reddit و دور زدن rate limit.
