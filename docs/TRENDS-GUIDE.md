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

---

# 🔬 تحلیل عمیق (مهندسی معکوس)

فراتر از پیدا کردن ترند، سیستم حالا ترندها رو **مهندسی معکوس** می‌کنه — یعنی می‌فهمه چرا و چطور کار می‌کنن.

## ۱) تحلیل عمیق عکس — `TrendVisualAnalyzer`
با **Gemini Vision** (رایگان با `GEMINI_API_KEY`) هر عکس ترند رو کالبدشکافی می‌کنه:
- **لباس و محصولات**: هر تکه لباس با رنگ/جنس/فرم + محصول شاخص (hero product)
- **ژست کاراکتر**: حالت بدن، دست‌ها، نگاه، حس
- **دوربین**: زاویه (eye-level/low/high)، اندازه شات، حس لنز، عمق میدان
- **نورپردازی، صحنه، ترکیب‌بندی، color grading**
- **چرا کار می‌کنه** + یک `recreate_prompt` آماده برای بازسازی

خروجی در `content/trend_visuals.json`. اگر `GEMINI_API_KEY` نباشه، فقط پالت رنگ (سریع و آفلاین با Pillow) استخراج می‌شه.

```python
from agents.trend_visual_analyzer import TrendVisualAnalyzer
rep = TrendVisualAnalyzer().run(limit=4)
print(rep["trending_aesthetics"], rep["trending_camera_angles"])
```
تلگرام: `/analyze`

## ۲) مهندسی معکوس ویدیو — `TrendVideoAnalyzer`
برای هر ویدیوی وایرال یوتیوب:
1. **متادیتای کامل** (عنوان، توضیح، تگ‌ها، ویو/لایک/کامنت، مدت) + **کامنت‌های برتر** (واکنش واقعی مردم) از YouTube Data API
2. **کالبدشکافی کامل با Gemini**: موضوع، هوک، ساختار، سبک فیلم‌برداری، تدوین، نحوه نوشتن کپشن/اسکریپت، محرک‌های تعامل، و **دلیل وایرال شدن**
3. یک **نقشه‌ی آماده‌ی اجرا** (`elina_recreation`): مفهوم، هوک، لیست شات، کپشن — برای بازسازی توسط الینا

خروجی در `content/trend_videos.json`. تلگرام: `/reverse` و بعد `/makevideos`.

```python
from agents.trend_video_analyzer import TrendVideoAnalyzer
rep = TrendVideoAnalyzer().run(limit=3)
```

## ۳) اتصال به تولید
- `PromptEngineer` سیگنال‌های عمیق (استایل، زاویه دوربین، محصول شاخص، ژست، پالت) رو به prompt عکس‌های الینا تزریق می‌کنه.
- `ContentCreator.create_video_ideas()` نقشه‌های بازسازی ویدیو رو به آیتم‌های محتوای آماده تبدیل می‌کنه.

## نیازمندی‌ها
- `GEMINI_API_KEY` → تحلیل عمیق AI (بدونش: فقط پالت رنگ + خلاصه heuristic)
- `YOUTUBE_API_KEY` → متادیتا و کامنت ویدیوها
- هر دو رایگان.
