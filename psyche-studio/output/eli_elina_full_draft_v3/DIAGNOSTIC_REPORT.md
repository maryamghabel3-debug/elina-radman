# گزارش تشخیصی Stage 1 — Elina و Eli

**وضعیت تاریخی (اکنون superseded):** در ارزیابی قبلی، اجرای محلی ASR به‌علت محدودیت دانلود مدل ممکن نبود و Path B پیشنهاد شده بود. مالک اکنون تأیید کرده متن‌های مرجع، متن گفتار واقعی‌اند و ASR لازم نیست؛ این گزارش فقط سابقهٔ مانع قبلی است و مبنای کار v2 نیست. هیچ transcript/CER/confidence تولیدشده‌ای از آن برنامه وجود ندارد.

## محیط اجرا

| قابلیت | نتیجهٔ مشاهده‌شده |
|---|---|
| نسخهٔ Python | 3.11.2 |
| CPU | 2 vCPU، Intel Xeon 2.60 GHz |
| GPU | GPU قابل‌استفاده مشاهده نشد؛ `nvidia-smi` در دسترس نیست |
| RAM | 3.8 GiB کل، حدود 3.6 GiB آزاد هنگام probe |
| دیسک | حدود 20 GiB آزاد روی filesystem ریشه |
| اینترنت | دسترسی به PyPI و GitHub پاسخ HTTP 200 داد |
| pip | نصب واقعی `faster-whisper==1.2.1` و `huggingface-hub==0.34.4` در `/tmp` موفق شد |
| ffmpeg | `ffmpeg` روی PATH سیستم موجود نیست؛ برای ASR این workflow از PyAV استفاده می‌کند |
| دریافت مدل Hugging Face | در این sandbox ممکن نیست: `huggingface.co` خارج از allowlist خروجی شبکه است. میزبان مسدودشده را مستقیماً probe نکردم. مدل یا cache محلی وجود ندارد. |

## مسیر انتخاب‌شده و نسخه‌ها

این بخش شرح تصمیم قبلی است، نه مسیر اجرای این درخواست: نصب packageها به‌تنهایی ASR محلی را ممکن نکرد، چون وزن‌های مدل Hugging Face در این sandbox در دسترس نبودند. آن زمان Path B طراحی شد، اما workflow اجرا نشد. طبق override مالک، هیچ workflow یا ASR برای v2 لازم نیست؛ این محدودیت دیگر مانع کار با اسکریپت‌های تأییدشده نیست.

- Package lock دقیق: `psyche-studio/content/voice_review_v2/requirements-asr.txt`؛ نصب آزمایشی موفق با همان pinها در `/tmp`.
- Primary model: `Systran/faster-whisper-large-v3`.
- Cross-check مستقل: `Systran/faster-whisper-medium`.
- هر اجرای workflow یک‌بار `main` هر مخزن مدل را به commit SHA ثابت ۴۰ رقمی resolve می‌کند، همان SHA را به `faster-whisper` می‌دهد و آن را در artifact (`model_revisions.json` و `TRANSCRIPT_REVIEW.md`) ثبت می‌کند. از این sandbox نمی‌شد SHAهای Hugging Face را دریافت کرد؛ SHAها تا اجرای workflow نامعلوم‌اند و جعل نشده‌اند.
- اجرای هر دو مدل با `language=fa`, `word_timestamps=True`, `vad_filter=True` تنظیم شده است.

## فایل‌های صوتی و منابع متنی

فایل‌های موردنیاز در شاخهٔ همگام‌شده موجودند: `elina_new.mp3`, `elina_draft.mp3`, `eli_presetB.mp3`. اندازه‌گیری قبلی ffprobe/FFmpeg loudnorm در گزارش Stage 0 ثبت شده بود:

| Stem | مدت | مشخصات | integrated LUFS |
|---|---:|---|---:|
| Elina جدید | 81.456 s | MP3, 24 kHz, mono | −20.43 |
| Elina قدیمی | 65.448 s | MP3, 48 kHz, mono | −16.36 |
| Eli preset B | 53.736 s | MP3, 24 kHz, mono | −17.97 |

هر دو متن مرجع اختیاری در شاخهٔ فعلی **وجود ندارند**:
- `psyche-studio/content/scenario/source_text_eli.txt`
- `psyche-studio/content/scenario/source_text_elina.txt`

پس هیچ forced alignment نسبت به متن مالک یا diff نسبت به source text قابل اجرا نیست. اسکریپت transcript این نبودن را در گزارش نهایی ثبت می‌کند.

## سناریو و زمینهٔ موجود در مخزن

فیلمنامهٔ کاملِ canonical برای همین اپیزود پیدا نشد. `docs/CHARACTER-UNIVERSE-V2.md` فقط lore تأییدشدهٔ الینا و الی را ثبت می‌کند: الی به‌عنوان بخش آسیب‌پذیر و کودکانه؛ الینا به‌عنوان کسی که احساسش را برای مخاطب ترجمه می‌کند و نباید با او بجنگد یا فوراً تغییرش دهد. آرایه‌های قبلی `ELI_LINES`/`ELINA_LINES` در `psyche-studio/remotion/scripts/build-full-draft-audio.py` یک گفت‌وگوی کامل‌تر دارند و می‌توانند به‌عنوان ترتیب مرجعِ موقت برای پیشنهاد مکالمه استفاده شوند؛ آن‌ها transcript صدای جدید نیستند و بدون بررسی انسانی نباید جایگزین گفتار شوند.

## فایل‌های تولیدی و محدودیت وضعیت فعلی

- فایل pending قدیمی: `psyche-studio/output/eli_elina_full_draft_v3/transcripts/TRANSCRIPT_REVIEW.md`؛ این گزارش به‌عنوان خروجی ASR معتبر نیست و اکنون superseded است.
- ASR و workflow در ساخت v2 استفاده نمی‌شوند. Workflow پیشنهادی قبلی به branch/push این کار منتقل نشده است.
- هیچ cue، تغییر Remotion، سناریوی نهایی یا ویدئوی v3 از برنامهٔ ASR قبلی ساخته نشده است.
- PR #116 و prototypeهای 3D هنگام جمع‌آوری این گزارش ویرایش نشده‌اند. شاخهٔ remote در شروع بررسی قبلی روی `8e36f5dbe4b2a89804f2a7355323699f1996d9ba` بود.
