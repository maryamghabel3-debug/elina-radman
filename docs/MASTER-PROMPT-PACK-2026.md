# 🎯 مجموعه پرامپت‌های طلایی و راهنمای ساخت دستی عکس فوق‌واقع‌گرایانه الینا (ویژه سال ۲۰۲۶)

این سند پاسخی جامع به جستجوی عمیق ما پیرامون **مهندسی پرامپت (Prompt Engineering) اینفلوئنسرهای هوش مصنوعی در سال ۲۰۲۶** است. اگر می‌خواهید عکس‌ها را به صورت دستی در سایت‌های رایگان یا کم‌هزینه بسازید، این راهنما و پرامپت‌های کپی-پیست (Copy-Paste) به شما بالاترین کیفیت ممکن (در حد عکاسی مجله Vogue و بدون کوچک‌ترین حالت مصنوعی) را می‌دهند.

---

## 🏗️ ۱. معماری ۴ لایه‌ای پرامپت حرفه‌ای (تکنیک سال ۲۰۲۶)

بر اساس آخرین مقالات و تجربیات تیم‌های برتر عکاسی هوش مصنوعی، پرامپت‌های قدیمی که پر از کلماتی مثل `8K, hyperrealistic, masterpiece` بودند منسوخ شده‌اند (زیرا موتورهای جدید مثل FLUX و جمینای این کلمات را به عنوان رندر سه بعدی CGI شناسایی می‌کنند!).

یک پرامپت اصولی باید از **۴ لایه دقیق** تشکیل شود:
- **لایه ۰ (هویت ثابت / Identity Anchor):** تعریف دقیق ساختار صورت، سن، پوست و ویژگی‌های فیزیکی الینا.
- **لایه ۱ (لوکیشن و اکشن / Scene & Action):** توضیح زنده و طبیعی محیط، زاویه بدن و کاری که در حال انجام است.
- **لایه ۲ (استایل و لباس / Styling & Outfit):** جزئیات بافت پارچه، رنگ‌بندی و جواهرات بر اساس ترندهای روز.
- **لایه ۳ (فیزیک دوربین و نورپردازی / Camera & Lighting):** مشخص کردن دقیق لنز، نوع نگاتیو عکاسی (مثل Kodak Portra)، بافت واقعی پوست (micro-pores) و نورپردازی.

---

## 🌐 ۲. معرفی بهترین سایت‌ها و ابزارها برای ساخت دستی (با کمترین هزینه یا رایگان)

| نام سایت/ابزار | هزینه | روش ساخت و حفظ چهره الینا | لینک دسترسی |
|:---|:---|:---|:---|
| **Google AI Studio (Gemini)** | **کاملاً رایگان** | عکس مرجع الینا (`images/elina-final-02.jpg`) را در چت پیست کنید و یکی از پرامپت‌های زیر را بفرستید. مدل `gemini-3-pro-image-preview` (نانو بنانا پرو) دقیق‌ترین چهره را می‌سازد. | [aistudio.google.com](https://aistudio.google.com) |
| **NVIDIA NIM (FLUX.1-dev)** | **رایگان (۱۰۰۰+ اعتبار)** | استفاده از مدل FLUX.1-dev با سرعت بی‌نظیر. برای حفظ چهره می‌توانید از پرامپت‌های توصیفی دقیق زیر استفاده کنید. | [build.nvidia.com](https://build.nvidia.com) |
| **Hugging Face ZeroGPU** | **رایگان** | ورود به اسپیس `yanze/PuLID-FLUX`، آپلود عکس مرجع الینا و پیست کردن پرامپت در کادر متن. | [huggingface.co/spaces/yanze/PuLID-FLUX](https://huggingface.co/spaces/yanze/PuLID-FLUX) |
| **Midjourney v7** | ۱۰ دلار/ماه | نوشتن پرامپت + افزودن پارامتر حفظ چهره: `--cref [لینک عکس الینا] --cw 80 --style raw --ar 4:5 --v 7` | [midjourney.com](https://www.midjourney.com) |

---

## 📋 ۳. ده (۱۰) پرامپت مستر کپی-پیست برای تولید دستی عکس الینا

هر یک از این پرامپت‌ها بر اساس معماری ۴ لایه‌ای فوق‌واقع‌گرایانه نوشته شده است. کافیست آن را کپی کرده و همراه با عکس مرجع الینا استفاده کنید:

### استایل ۱: تراس کافه در خیابان‌های پاریس (بسیار محبوب و ترند)
```text
Candid 35mm lifestyle photograph of Elina Radman, a 24-year-old Iranian woman with warm wheat skin, soft dark brown eyes, full lips with subtle nude lip color, and long natural near-black wavy hair tucked behind her ears. She is sitting outdoors at a sunlit Parisian street cafe terrace, softly laughing while holding a white ceramic espresso cup. She is wearing a tailored petite camel wool trench coat over wide-leg pleated cream trousers and minimal 18k gold hoop earrings. Shot on Canon EOS R5 with 85mm f/1.4 lens, natural morning golden hour sunlight cutting through cafe shadows. Real-world photography characteristics: natural detailed skin texture, visible micro-pores, soft organic facial highlights, Kodak Portra 400 film grain, shallow depth of field with softly blurred street background. Unfiltered UGC influencer aesthetic with zero CGI, 3D render, or artificial beauty airbrushing.
```

### استایل ۲: استایل خیابانی در هفته مد میلان (شیک و باابهت)
```text
Full-body candid fashion editorial photograph of Elina Radman, a 24-year-old petite Iranian woman with warm wheat skin and thick dark eyebrows, walking confidently across a cobblestone street in Milan during Fashion Week. She wears a structured oversized navy blazer over a crisp white silk blouse, tailored ankle-length trousers, and pointed-toe nude slingback heels. Shot from a slightly low angle on a 35mm lens, diffused overcast daylight creating soft elegant shadows. Highly detailed natural skin texture, visible pores, realistic fabric drape and movement, cinematic color grading toward neutral beige and navy tones. Zero plastic look, authentic street-style influencer snapshot.
```

### استایل ۳: بالکن آفتاب‌گیر در سانتورینی (محتوای تعطیلات و لایف‌استایل)
```text
Authentic travel influencer photograph of Elina Radman, a 24-year-old Iranian woman with warm olive-wheat skin and natural dark brown eyes, leaning gracefully against a white Mediterranean balcony railing overlooking the sea at sunset. She is wearing an effortless off-white linen maxi dress and delicate gold layered necklaces. Warm golden hour sunlight illuminating the side of her face, capturing natural skin shine, micro-details, and soft hair strands moving in the breeze. Shot on Leica M11, 50mm f/1.2 lens, rich natural color rendering, film grain, photorealistic vacation lifestyle capture.
```

### استایل ۴: استودیوی خانگی و مینیمال (محتوای آموزشی / صمیمی)
```text
Intimate and cozy indoor lifestyle photograph of Elina Radman, a 24-year-old petite Iranian woman sitting relaxed on a cream bouclé sofa in a minimalist sunlit apartment. Her hair is tied in a soft low bun with a few framing tendrils. She is wearing an oversized beige cashmere knit sweater and beige tailored lounging trousers, looking toward the camera with a warm, gentle smile. Soft window sunlight streaming from the right, natural dust particles floating in the light beams, shallow depth of field. Ultra-realistic skin texture, unfiltered Instagram aesthetic.
```

### استایل ۵: گالری هنری مدرن (استایل روشنفکری و Quiet Luxury)
```text
Three-quarter length editorial portrait of Elina Radman, a 24-year-old Iranian woman standing inside a high-ceiling modern art gallery beside abstract minimalist sculptures. She is wearing a monochrome all-black tailored outfit featuring a structured vest and wide-leg trousers. Clean studio architecture lighting with soft shadows, capturing realistic facial contours, authentic skin texture, and sharp focus on fabric weave. Shot on medium format camera, f/2.8, sophisticated and intelligent quiet luxury atmosphere.
```

### استایل ۶: پیاده‌روی پاییزی در پارک (رنگ‌های گرم و پاییزی)
```text
Candid outdoor autumn snapshot of Elina Radman, a 24-year-old Iranian woman walking along a tree-lined park pathway covered in golden fall leaves. She is wrapped in a tailored double-breasted chocolate brown wool coat and a cream cashmere scarf. Soft afternoon autumn sunlight creating warm amber highlights in her dark eyes and hair. Natural lifestyle candid photography, Kodak Portra film grain, real skin texture, authentic seasonal mood.
```

### استایل ۷: سلفی آینه‌ای رئال در هتل بوتیک (سبک کاملاً طبیعی UGC)
```text
Ultra-realistic candid mirror selfie of Elina Radman, a 24-year-old Iranian woman standing in a luxury boutique hotel room mirror. She is holding an iPhone casually angled in front of her, dressed in a chic neutral lounge set (cream knit cardigan and matching wide trousers). Natural warm room lighting, authentic mirror reflections, visible phone camera sharpness, real skin glow with subtle micro-detail and zero airbrushing. Perfect authentic TikTok/Instagram Story vibe.
```

### استایل ۸: لانژ فرودگاه بین‌المللی (استایل جت‌ست و مسافرتی)
```text
Lifestyle travel capture of Elina Radman, a 24-year-old petite Iranian woman sitting in a modern airport executive lounge with floor-to-ceiling windows overlooking airplanes. She is dressed in comfortable yet chic airport attire: tailored camel jogger trousers, a white rib-top, and a beige trench coat draped over her shoulders. Natural bright daylight, cinematic depth of field, authentic candid expression, professional lifestyle magazine quality.
```

### استایل ۹: روف‌تاپ شهری در غروب آفتاب (انرژی باابهت و شبانه)
```text
Golden hour rooftop photograph of Elina Radman, a 24-year-old Iranian woman standing on a city rooftop with the skyline behind her during dusk. She wears a sharp sleeveless tailored vest in forest green and high-waisted tailored trousers. Warm city lights and setting sun reflecting softly in her eyes, realistic skin micro-pores, cinematic f/1.8 aperture bokeh, confident modern influencer portrait.
```

### استایل ۱۰: کتابفروشی کلاسیک و دنج (استایل کاتج‌کور و آکادمیک)
```text
Charming documentary photograph of Elina Radman, a 24-year-old Iranian woman browsing shelves inside an aesthetic vintage bookstore. She reaches for a book while glancing back toward the camera with a gentle expression. She wears a tailored tweed blazer over a fine-knit turtleneck. Warm ambient indoor lighting, rich wooden textures in the background, Kodak Gold 200 film aesthetic, ultra-photorealistic candid moment.
```

---

## 🚫 کلماتی که هرگز نباید در پرامپت‌های ۲۰۲۶ بنویسید (Negative List)
برای جلوگیری از مصنوعی شدن عکس در هر سایتی، کلمات زیر را در کادر **Negative Prompt** قرار دهید:
```text
AI generated, CGI, 3D render, illustration, digital art, plastic skin, overly smooth skin, airbrushed, doll-like, uncanny valley, deformed hands, extra fingers, mutated limbs, bad anatomy, artificial lighting, studio backdrop, blurry, low resolution, watermark, text
```
