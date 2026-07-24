# Regression and Testing Policy — ElinaOS V2

## سیاست رسمی جلوگیری از رگرشن و تست پروژه الینا

```yaml
document:
  title: "Regression and Testing Policy"
  project: "ElinaOS V2"
  version: "1.0.0"
  status: "APPROVED"
  owner: "Project Owner"
  maintained_by: "Project Manager"
  last_updated: "2026-07-24"
  applies_to: "Entire repository"
```

---

## ۱. هدف

این سند سیاست رسمی پروژه ElinaOS V2 برای جلوگیری از Regression است.

Regression زمانی رخ می‌دهد که یک تغییر جدید، رفتار سالم و از قبل موجود سیستم را
به‌صورت ناخواسته خراب کند.

این سیاست برای محافظت از بخش‌های حساس زیر طراحی شده است:

- دریافت و ثبت محتوا
- مدیریت فایل‌ها و دارایی‌های محتوا
- وضعیت‌های چرخه عمر محتوا
- بررسی ایمنی روان‌شناختی
- تأیید یا رد انسانی
- صف انتشار
- زمان‌بندی
- انتشار در شبکه‌های اجتماعی
- مدیریت خطا و Retry
- اعلان‌های اپراتور
- ایجنت‌ها و ابزارهای متصل
- اطلاعات خصوصی و حساس
- تنظیمات امنیتی

ElinaOS یک سیستم Human-in-the-Loop است و ممکن است با محتوای روان‌شناختی
حساس کار کند. بنابراین جلوگیری از Regression فقط یک الزام فنی نیست؛ بلکه یک
الزام عملیاتی، امنیتی و اخلاقی است.

---

## ۲. قوانین غیرقابل‌مذاکره

قواعد زیر برای تمام تغییرات پروژه الزامی هستند:

1. هر Pull Request باید تا جای ممکن کوچک و تک‌هدفه باشد.
2. هیچ تغییر مستقیمی روی branch اصلی `main` مجاز نیست.
3. هر تغییر باید روی branch جداگانه انجام شود.
4. هر تغییر مهم در منطق باید Unit Test داشته باشد.
5. هر Bug Fix باید Regression Test داشته باشد.
6. قبل از Refactor پرریسک باید Characterization Test نوشته شود.
7. مسیرهای اصلی کاربر باید Automated Test داشته باشند.
8. تست‌ها نباید به token، secret یا حساب واقعی نیاز داشته باشند.
9. تست‌ها نباید به شبکه یا API واقعی وابسته باشند، مگر در محیط Integration
   کنترل‌شده و با تأیید صریح.
10. شکست تست‌های الزامی باید Merge را متوقف کند.
11. تست‌ها نباید از اطلاعات واقعی یا روان‌شناختی مخاطبان استفاده کنند.
12. هیچ تستی نباید محتوای واقعی را منتشر کند.
13. هیچ تستی نباید workflow انتشار واقعی را فعال کند.
14. تغییرات امنیتی، صف انتشار و تأیید انسانی بدون تست قابل Merge نیستند.

---

## ۳. سیاست تغییرات کوچک

### ۳.۱. یک هدف برای هر Pull Request

هر Pull Request باید یک هدف اصلی و قابل‌توضیح داشته باشد.

نمونه‌های صحیح:

- اضافه‌کردن زیرساخت pytest
- نوشتن Unit Test برای Queue Manager
- اصلاح یک Bug در Retry Logic
- اضافه‌کردن Automated Test برای Approval Flow
- Refactor محدود یک Parser پس از ثبت Characterization Test

نمونه‌های نامناسب:

- تغییر برند، Refactor، Feature و Test در یک PR
- بازنویسی چند Agent نامرتبط در یک PR
- تغییر هم‌زمان Queue، Publisher، Dashboard و Telegram Bot
- اصلاح فایل‌های نامرتبط صرفاً به دلیل مشاهده Typo یا Formatting

### ۳.۲. بودجه پیش‌فرض PR

بودجه ترجیحی هر PR:

- حداکثر ۵ تا ۸ فایل اصلی
- ترجیحاً کمتر از ۴۰۰ خط تغییر خالص
- یک موضوع اصلی
- یک مسیر Rollback روشن

این حدود، راهنما هستند و در موارد مستندات بزرگ یا فایل‌های تولیدشده می‌توانند با
تأیید مدیر پروژه استثنا داشته باشند.

### ۳.۳. ممنوعیت Drive-by Changes

تغییرات خارج از Scope اصلی تسک نباید وارد PR شوند.

اگر هنگام اجرای تسک مشکل دیگری کشف شد:

1. آن را در گزارش ثبت کن.
2. برای آن Issue یا تسک جداگانه پیشنهاد بده.
3. بدون اجازه وارد PR فعلی نکن.

### ۳.۴. تفکیک تغییرات

تا جای ممکن موارد زیر باید در PRهای جدا باشند:

- Documentation
- Test Foundation
- Unit Tests
- Refactor
- Feature
- Migration
- Security Hardening
- Automated User Paths
- Dependency Updates

---

## ۴. طبقه‌بندی ریسک تغییرات

| سطح | تعریف | نمونه | حداقل تست لازم |
|---|---|---|---|
| R0 | فقط مستندات، بدون اثر Runtime | اصلاح سند | Link/format check |
| R1 | تغییر کم‌ریسک و محلی | Utility یا Parser ساده | Unit Test |
| R2 | تغییر جریان داخلی | Queue، Config، Memory | Unit + Integration |
| R3 | مسیر اصلی یا امنیتی | Approval، Publish، Auth | Unit + Integration + Smoke |
| R4 | تغییر بحرانی | انتشار واقعی، داده حساس، Migration | همه تست‌ها + تأیید دستی |

مدیر پروژه می‌تواند سطح ریسک یک تغییر را افزایش دهد.

ایجنت اجرایی حق ندارد بدون تأیید مدیر پروژه سطح ریسک تعیین‌شده را کاهش دهد.

---

## ۵. Characterization Tests قبل از Refactor

بخش‌هایی از ریپازیتوری ElinaOS از نسخه قدیمی پروژه باقی مانده‌اند.

قبل از Refactor یک ماژول Legacy:

1. رفتار فعلی آن شناسایی شود.
2. ورودی‌ها و خروجی‌های قابل‌مشاهده مشخص شوند.
3. Characterization Test برای رفتار موجود نوشته شود.
4. تست روی کد فعلی Pass شود.
5. سپس Refactor در یک PR جدا انجام شود.
6. همان تست‌ها بعد از Refactor نیز باید Pass بمانند.

هدف Characterization Test تأیید ایده‌آل‌بودن رفتار فعلی نیست؛ هدف ثبت رفتار موجود
برای جلوگیری از تغییر ناخواسته است.

اگر رفتار فعلی یک Bug امنیتی یا اخلاقی است، نباید به‌عنوان رفتار مطلوب تثبیت شود.
در این حالت:

- مشکل باید مستند شود.
- Regression Test باید رفتار صحیح مورد انتظار را تعریف کند.
- تست باید قبل از Fix شکست بخورد و بعد از Fix موفق شود.

---

## ۶. سیاست Unit Test

### ۶.۱. الزام عمومی

هر منطق جدید یا تغییریافته باید Unit Test متناسب داشته باشد.

حداقل تست برای یک رفتار مهم:

1. Happy Path
2. Edge Case یا Failure Path

### ۶.۲. اولویت Unit Testها

اولویت پوشش:

1. Queue و Status Transition
2. Validation و Parsing
3. Content Metadata
4. Config Loading
5. Retry و Error Classification
6. Approval Rules
7. Publisher Orchestration با Mock
8. Bot Command Handling با Mock
9. Storage Adapter
10. Security Validation

### ۶.۳. ویژگی Unit Test معتبر

Unit Test باید:

- سریع باشد
- deterministic باشد
- مستقل از ترتیب اجرای تست‌ها باشد
- به شبکه متصل نشود
- API واقعی را صدا نزند
- به token واقعی نیاز نداشته باشد
- فایل واقعی پروژه را خراب نکند
- از `tmp_path` برای فایل موقت استفاده کند
- وابستگی‌های خارجی را Mock کند
- دلیل شکست روشنی داشته باشد

### ۶.۴. تست‌های نامعتبر

موارد زیر تست معتبر محسوب نمی‌شوند:

```python
assert True
```

یا تستی که فقط وجود یک Constant را بدون رفتار معنادار بررسی می‌کند.

همچنین موارد زیر نامعتبرند:

- تستی که همیشه Skip می‌شود
- تستی که Exception را بدون بررسی می‌بلعد
- تستی که فقط Import می‌کند و Unit Test نامیده می‌شود
- تستی که برای موفقیت به Internet نیاز دارد
- تستی که خروجی آن به زمان واقعی یا Random کنترل‌نشده وابسته است

---

## ۷. سیاست Bug Fix

هر Bug Fix باید حداقل یک Regression Test داشته باشد.

فرایند استاندارد:

1. Bug با یک تست بازتولید شود.
2. تست روی نسخه معیوب Fail شود.
3. Fix کوچک و محدود اعمال شود.
4. تست جدید Pass شود.
5. تست‌های قبلی نیز Pass بمانند.

هیچ Bug Fix مهمی فقط با بررسی دستی Merge نمی‌شود.

---

## ۸. مسیرهای اصلی کاربر

مسیرهای زیر Core User Paths پروژه هستند و باید به‌تدریج Automated Test داشته
باشند.

### مسیر ۱: Content Intake

```text
External Agent/Human
        ↓
Content Intake
        ↓
Validation
        ↓
Asset and Metadata Registration
        ↓
DRAFT / ASSETS_READY
```

تست‌ها باید بررسی کنند:

- ورودی معتبر پذیرفته می‌شود.
- ورودی ناقص به‌صورت کنترل‌شده رد می‌شود.
- فایل نامعتبر باعث Crash نمی‌شود.
- Pathهای غیرمجاز پذیرفته نمی‌شوند.
- محتوای ورودی نمی‌تواند دستور اجرایی تزریق کند.

### مسیر ۲: Editing and Assembly

```text
Raw Assets
    ↓
Hook / Subtitle / Voice / Audio / Cover
    ↓
Assembly
    ↓
READY_FOR_REVIEW
```

تست‌ها باید بررسی کنند:

- Assetهای لازم شناسایی می‌شوند.
- نبود Asset ضروری خطای کنترل‌شده ایجاد می‌کند.
- فایل ورودی خارج از محدوده مجاز خوانده نمی‌شود.
- مرحله Assembly بدون تأیید، انتشار انجام نمی‌دهد.

### مسیر ۳: Safety and Strategy Review

```text
READY_FOR_REVIEW
        ↓
Safety Review
        ↓
Strategy Review
        ↓
Human Decision
```

تست‌ها باید بررسی کنند:

- محتوای Blocked قابل Approve خودکار نیست.
- Trigger Warning در صورت نیاز حفظ می‌شود.
- Agent نمی‌تواند Human Approval را جعل کند.
- نتیجه Safety Review در Metadata ثبت می‌شود.

### مسیر ۴: Human Approval

```text
READY_FOR_REVIEW
        ↓
APPROVED / NEEDS_REVISION / REJECTED
```

تست‌ها باید بررسی کنند:

- محتوای تأییدنشده وارد صف انتشار نمی‌شود.
- محتوای Rejected منتشر نمی‌شود.
- Approver نامعتبر مجوز تغییر وضعیت ندارد.
- Approval قابل Audit است.

### مسیر ۵: Scheduling and Queue

```text
APPROVED
    ↓
SCHEDULED
    ↓
Due Item Selection
```

تست‌ها باید بررسی کنند:

- فقط محتوای APPROVED زمان‌بندی می‌شود.
- زمان و Timezone به‌درستی تفسیر می‌شوند.
- اجرای دوباره Scheduler باعث انتشار تکراری نمی‌شود.
- Queue در خطا خراب یا حذف نمی‌شود.

### مسیر ۶: Publishing

```text
SCHEDULED
    ↓
PUBLISHING
    ↓
PUBLISHED / RETRY_PENDING / FAILED
```

تست‌ها باید بررسی کنند:

- موفقیت Publisher وضعیت را به PUBLISHED تغییر می‌دهد.
- خطای موقت وارد RETRY_PENDING می‌شود.
- خطای دائمی به FAILED یا MANUAL_PUBLISH_REQUIRED می‌رود.
- تعداد Retry محدود است.
- محتوا در خطا از دست نمی‌رود.
- Test هیچ پست واقعی منتشر نمی‌کند.

### مسیر ۷: Operator Control and Recovery

تست‌ها باید بررسی کنند:

- اپراتور مجاز می‌تواند وضعیت را ببیند.
- اپراتور غیرمجاز Block می‌شود.
- Pause و Resume قابل Audit هستند.
- Recovery باعث Double Publish نمی‌شود.
- خطاها بدون نمایش Secret گزارش می‌شوند.

---

## ۹. قواعد قطعی Human-in-the-Loop

Invariantهای زیر نباید در هیچ شرایطی نقض شوند:

```text
NOT APPROVED → MUST NOT PUBLISH
REJECTED → MUST NOT PUBLISH
BLOCKED BY SAFETY → MUST NOT AUTO-APPROVE
FAILED → CONTENT MUST NOT BE LOST
RETRY → MUST BE BOUNDED
PUBLISHED → MUST NOT PUBLISH AGAIN
```

هر تغییر در Queue، Scheduler، Publisher یا Approval باید این قواعد را با تست پوشش
دهد.

---

## ۱۰. هرم تست ElinaOS

### لایه اول: Unit Tests

- تعداد زیاد
- اجرای سریع
- بدون شبکه
- بدون Secret
- تمرکز روی منطق محلی

### لایه دوم: Integration Tests

- تعداد متوسط
- اتصال چند ماژول
- استفاده از Fake یا Mock Adapter
- بدون سرویس واقعی در حالت پیش‌فرض

### لایه سوم: Smoke and Core Path Tests

- تعداد کم
- پوشش مسیرهای اصلی
- اطمینان از اتصال صحیح اجزای حیاتی
- بدون انتشار واقعی

### لایه چهارم: Manual Acceptance

برای تغییرات پرریسک:

- بررسی انسانی
- بررسی امنیت
- بررسی محتوایی و اخلاقی
- تأیید مالک قبل از Merge یا Deploy

---

## ۱۱. ساختار تست‌ها

ساختار هدف:

```text
tests/
├── unit/
├── integration/
├── smoke/
├── fixtures/
└── conftest.py
```

Markerهای استاندارد:

```text
unit
integration
smoke
slow
```

قواعد:

- تست‌های Unit نباید به Integration وابسته باشند.
- تست‌های Smoke باید کوچک و پایدار باشند.
- تست‌های Slow در CI عادی قابل حذف هستند، اما باید در اجرای دوره‌ای اجرا شوند.
- هر تست باید نامی داشته باشد که رفتار مورد انتظار را توضیح دهد.

نمونه نام مناسب:

```text
test_rejected_content_cannot_be_scheduled
test_publish_failure_preserves_queue_item
test_invalid_metadata_returns_validation_error
```

---

## ۱۲. داده تست و حریم خصوصی

استفاده از داده‌های واقعی مخاطبان ممنوع است.

تست‌ها نباید شامل موارد زیر باشند:

- پیام واقعی کاربران
- اطلاعات درمانی یا روان‌شناختی واقعی
- شماره تلفن
- ایمیل شخصی
- Chat ID واقعی
- Access Token
- API Key
- اطلاعات حساب شبکه اجتماعی
- فایل خصوصی مخاطب

تمام داده‌های تست باید:

- ساختگی باشند
- حداقل اطلاعات لازم را داشته باشند
- قابل حذف باشند
- در صورت حساس‌بودن با عبارت `SYNTHETIC_TEST_DATA` علامت‌گذاری شوند

---

## ۱۳. کنترل زمان، Random و شبکه

تست‌ها نباید به عوامل غیرقابل‌کنترل وابسته باشند.

برای زمان:

- از clock قابل تزریق یا mock استفاده شود.
- تست نباید به ساعت واقعی سیستم وابسته باشد.

برای Random:

- seed ثابت استفاده شود.
- خروجی غیرقابل‌پیش‌بینی وارد Assertion نشود.

برای شبکه:

- تمام درخواست‌های HTTP در Unit Test Mock شوند.
- تست شبکه واقعی فقط با Marker مخصوص و تأیید مدیر پروژه اجرا شود.
- CI پیش‌فرض نباید به APIهای تولید محتوا یا شبکه‌های اجتماعی متصل شود.

---

## ۱۴. سیاست Flaky Test

Flaky Test تستی است که بدون تغییر کد گاهی Pass و گاهی Fail می‌شود.

قواعد:

1. Flaky Test نباید نادیده گرفته شود.
2. Retry خودکار نباید جای Fix را بگیرد.
3. تست مشکل‌دار باید Issue داشته باشد.
4. Skip موقت باید دلیل و تاریخ انقضا داشته باشد.
5. تست بحرانی نباید بدون جایگزین غیرفعال شود.
6. Merge نباید با اجرای مجدد تصادفی تست Failشده توجیه شود.

---

## ۱۵. CI Gate

حداقل Gateهای CI:

1. نصب موفق وابستگی‌های تست
2. اجرای Unit Tests
3. اجرای Smoke Tests
4. شکست workflow در صورت Failشدن تست
5. Secret Pattern Scan
6. بررسی خطاهای syntax
7. جلوگیری از اجرای تست‌های وابسته به Secret واقعی
8. حداقل دسترسی workflow

Workflow تست باید در حالت پیش‌فرض:

```text
pytest -m "not slow"
```

را اجرا کند.

Workflow باید حداقل permission زیر را داشته باشد:

```yaml
permissions:
  contents: read
```

Workflow تست نباید:

- به `main` push کند
- PR را Merge کند
- Secret را چاپ کند
- پست واقعی منتشر کند
- workflow انتشار را Trigger کند
- به حساب واقعی Instagram، Telegram یا سرویس AI متصل شود

---

## ۱۶. Definition of Done

یک تغییر زمانی Done محسوب می‌شود که:

- [ ] Scope تغییر روشن و کوچک است.
- [ ] تغییر روی branch جدا انجام شده است.
- [ ] Direct Push به main انجام نشده است.
- [ ] تست مناسب برای منطق جدید وجود دارد.
- [ ] Bug Fix دارای Regression Test است.
- [ ] مسیر اصلی تغییرکرده Automated Test دارد.
- [ ] تست‌ها بدون Secret واقعی اجرا می‌شوند.
- [ ] تست‌ها بدون API واقعی اجرا می‌شوند.
- [ ] تمام تست‌های الزامی Pass هستند.
- [ ] Secret Scan موفق است.
- [ ] تغییرات خارج از Scope وجود ندارند.
- [ ] ریسک‌ها در PR توضیح داده شده‌اند.
- [ ] Rollback مشخص است.
- [ ] بازبینی مدیر پروژه انجام شده است.
- [ ] تأیید مالک برای Merge دریافت شده است.

---

## ۱۷. شرایط مسدودکننده Merge

در موارد زیر Merge ممنوع است:

- Failشدن Unit Test
- Failشدن Smoke Test
- Failشدن تست مسیر اصلی مرتبط
- مشاهده Secret یا Credential
- تغییر مستقیم main
- نبود Regression Test برای Bug Fix مهم
- حذف یا Skip تست برای سبزکردن CI
- تغییر خارج از Scope
- نبود تأیید انسانی
- امکان انتشار بدون Approval
- امکان Double Publish
- احتمال حذف محتوا در Failure
- وجود Prompt Injection اجرای‌نشده‌نشده در ورودی عملیاتی
- نبود توضیح درباره تغییر Production Behavior

---

## ۱۸. سیاست استثنا

استثنا فقط با تأیید صریح مدیر پروژه و مالک ممکن است.

هر استثنا باید شامل موارد زیر باشد:

- دلیل
- سطح ریسک
- محدوده زمانی
- برنامه جبران
- مسئول
- تسک یا Issue پیگیری

عبارت‌هایی مانند موارد زیر دلیل قابل‌قبول نیستند:

- وقت نداشتیم
- تست سخت بود
- تغییر کوچک بود
- روی سیستم من کار می‌کند
- بعداً تست می‌نویسیم

در شرایط اضطراری، Hotfix می‌تواند با تست حداقلی Merge شود؛ اما Regression Test باید
در اولین PR بعدی اضافه شود.

---

## ۱۹. Rollback و Recovery

هر تغییر R2 یا بالاتر باید مسیر Rollback داشته باشد.

برای تغییرات Queue و Publishing:

- داده قبلی نباید حذف شود.
- Migration باید قابل بازگشت یا دارای Backup باشد.
- Retry نباید باعث Double Publish شود.
- Rollback نباید Approval History را حذف کند.

برای تغییرات Agent:

- Prompt و Config قبلی باید نسخه‌بندی شوند.
- Rollback به نسخه قبلی باید ممکن باشد.
- Agent جدید نباید قبل از تأیید به ابزار Production دسترسی بگیرد.

---

## ۲۰. برنامه مرحله‌ای پوشش تست

### فاز A — Test Foundation

- سیاست رسمی تست
- pytest configuration
- حداقل دو Unit Test واقعی
- یک Smoke Test
- CI پایه

### فاز B — Core Unit Tests

- Queue
- Status Transition
- Metadata Validation
- Retry Classification
- Config and Memory

### فاز C — Automated Core User Paths

- Content Intake
- Safety Review
- Human Approval
- Scheduling
- Publish Success
- Publish Failure and Retry
- Operator Recovery

### فاز D — Security Regression

- Prompt Injection Defense
- Unauthorized Command
- Path Traversal
- Secret Leakage
- Unsafe Tool Call
- Unauthorized Publish

---

## ۲۱. اصل نهایی

سرعت توسعه مهم است، اما نباید به قیمت ازدست‌رفتن قابلیت اعتماد تمام شود.

در ElinaOS:

> تغییر کوچک، تست‌شده و قابل‌بازگشت از تغییر بزرگ، سریع و غیرقابل‌اعتماد ارزشمندتر است.

END OF DOCUMENT
