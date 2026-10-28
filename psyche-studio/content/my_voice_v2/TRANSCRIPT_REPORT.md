# New Narration Takes — Transcription Report (read-only pass)

Generated 2026-10-28. **No audio content was modified, no TTS was used, no video was rendered.** All audio analysis is objective (ffmpeg decode/PCM measurements); no listening or subjective quality claims.

## Method

- Primary recognizer: **faster-whisper 1.2.1 / CTranslate2 4.8.4, OpenAI Whisper 'medium' weights, CPU int8, beam_size=5, language=fa, word_timestamps=True**
- s01 rescue: **Whisper 'large-v3' int8 on the low-level 26.5-57.5s clip with per-clip AGC (3.8GB RAM cap prevents full-file large-v3)**
- Weights provenance: github.com/minicookie0208/faster-whisper-models (chunked non-LFS blobs, reassembled locally in /tmp; weights never committed)
- ASR-only preprocessing (decoded copies in /tmp, sources untouched): 16kHz mono decode; highpass70/lowpass9k + loudnorm I=-16; s01 quiet region additionally acompressor+dynaudnorm on an isolated clip
- Platform STT: no speech-to-text connector exists in this environment (whisper/speech-to-text/openai/assemblyai/deepgram all unsupported); CPU Whisper used per instruction
- Persian colloquial style preserved; grammar was NOT corrected to match the planned script. Uncertain words are marked [?]. Phrase- and word-level timestamps are in `narration_manifest.json` (per-word probability included).
- s01 note: the 27–57 s region was recorded ~10–15 dB below the rest (off-mic). medium emitted no text there on the raw file; per-clip AGC plus large-v3 recovered it. The sandbox has 3.8 GB RAM / no swap, so large-v3 could only run on short clips (one full-length second pass was OOM-killed).

## 1. File inventory (objective)

| New name | Uploaded name | Container / codec | SR | Ch | Duration (container / decoded) | Size | Peak / RMS | Lead silence | Trail silence | Decode validity | Clicks / transients |
|---|---|---|--:|--:|---|--:|---|---|---|---|---|
| s01.mp3 | قسمت اول.mp3 | mp3 (mp3float), CBR 128 kb/s | 44100 | 1 | 70.71 / 70.688 s | 1131439 B | -1.9 / -32.6 dBFS | 0.0 s (all gates; 4-sample edge blip at t=0) | 0.108 s @-40dBFS | 1 end-of-stream 'Header missing' (trailing non-audio bytes after last valid frame); no mid-file errors | shared 4-sample edge transient at t=0 (identical samples in all 4 files); zero 5ms windows crest>8 -> no mid-file clicks |
| s02.mp3 | قسمت دوم.mp3 | mp3 (mp3float), CBR 128 kb/s | 44100 | 1 | 36.19 / 36.154 s | 578997 B | -1.9 / -25.7 dBFS | 0.0 s (all gates; 4-sample edge blip at t=0) | 0.094 s @-40dBFS | 1 end-of-stream 'Header missing'; no mid-file errors | same 4-sample t=0 transient; zero 5ms windows crest>8 |
| s03.mp3 | قسمت 3.mp3 | mp3 (mp3float), CBR 128 kb/s | 44100 | 1 | 36.47 / 36.441 s | 583490 B | -1.9 / -23.6 dBFS | 0.0 s (all gates; 4-sample edge blip at t=0) | 0.341 s @-40dBFS | 1 end-of-stream 'Header missing'; no mid-file errors | same 4-sample t=0 transient; zero 5ms windows crest>8 |
| s04.mp3 | قسمت 4.mp3 | mp3 (mp3float), CBR 128 kb/s | 44100 | 1 | 12.2 / 12.147 s | 195183 B | -1.9 / -26.3 dBFS | 0.0 s (all gates; 4-sample edge blip at t=0) | 1.187 s @-40dBFS | 1 end-of-stream 'Header missing'; no mid-file errors | same 4-sample t=0 transient; zero 5ms windows crest>8 |

All four files: MP3 frame-sync start (no ID3 tags), muxed by Lavf61.1.100, CBR 128 kb/s, mono 44.1 kHz, identical 4-sample transient at t=0 (`0.612, 0.619, 0.651, 0.658` then silence — encoder edge artifact, not a spoken click), and exactly one end-of-stream `Header missing` error caused by trailing non-audio filler bytes after the last valid MP3 frame (tails `AA AA AA AA` / `55 55 55 55`). No mid-file decode errors; zero 5 ms windows with crest factor > 8 (no broadband clicks). sha256 of every file is unchanged after the rename (see manifest).

## 2. Per-file transcripts and section mapping

### s01.mp3 — `قسمت اول.mp3`  (70.688 s)

**Raw transcript — verbatim recognizer output (phrase timestamps; word timestamps + probabilities in JSON):**

- `[  0.880–  4.800]` (med, lp -0.362, nsp 0.353)  یه پیام ساده یک گوچی چطور میتونه حال ما رو تغییر بده؟
- `[  5.980–  8.480]` (med, lp -0.362, nsp 0.353)  خب، تا هله برا تون پیش اومد حتماً
- `[  9.020– 12.720]` (med, lp -0.362, nsp 0.353)  که به یکی پیام میدادین و اون برگشت گفته باشه
- `[ 12.720– 14.860]` (med, lp -0.362, nsp 0.353)  یه جواب خد کتاح داده
- `[ 14.860– 16.760]` (med, lp -0.362, nsp 0.353)  و چه تفاقی گفته داده؟
- `[ 16.760– 17.920]` (med, lp -0.362, nsp 0.353)  یهو!
- `[ 18.100– 19.880]` (med, lp -0.362, nsp 0.353)  ما میریم توی یه فازه دیگه
- `[ 19.880– 21.540]` (med, lp -0.362, nsp 0.353)  به خودمون میگیم
- `[ 21.540– 22.100]` (med, lp -0.362, nsp 0.353)  اه!
- `[ 22.300– 23.120]` (med, lp -0.362, nsp 0.353)  چی شد؟
- `[ 23.120– 24.400]` (med, lp -0.362, nsp 0.353)  چرا ایندوری شد؟
- `[ 24.400– 25.580]` (med, lp -0.362, nsp 0.353)  چقدر کتاح جواب داد
- `[ 26.500– 30.680]` (lv3, lp -0.211, nsp 0.484)  باشه. فکر میکنم نراحت شده. شاید از اصلا اصابانیم.
- `[ 32.120– 34.960]` (lv3, lp -0.211, nsp 0.484)  نمیدونم. شاید اصلا برای شما هم نیستم.
- `[ 35.360– 38.940]` (lv3, lp -0.211, nsp 0.484)  اصلا با من اهمیت نمیدونیم. حتما دوستم نداره.
- `[ 39.220– 41.900]` (lv3, lp -0.211, nsp 0.484)  به خاطر این که دوستم نداره اینطوری جواب داده.
- `[ 42.400– 45.880]` (lv3, lp -0.211, nsp 0.484)  و این فکر را اینقدر ادامه پیدا میکنن
- `[ 45.880– 51.280]` (lv3, lp -0.211, nsp 0.484)  که یه خودتون میانید و ببینید حالتون هم عوض شده.
- `[ 51.520– 54.360]` (lv3, lp -0.211, nsp 0.484)  یعنی دیگه اون آدم یه ساعت قبل نیستیم.
- `[ 54.360– 56.120]` (lv3, lp -0.34, nsp 0.073)  الان اصابه نیترین
- `[ 56.120– 57.360]` (lv3, lp -0.34, nsp 0.073)  الان نارهت
- `[ 57.980– 60.000]` (med, lp -0.3, nsp 0.218)  و هلون حالتون خرابه
- `[ 60.000– 61.840]` (med, lp -0.3, nsp 0.218)  دوسترین باشته او کنین
- `[ 61.840– 64.800]` (med, lp -0.3, nsp 0.218)  دوسترین پیام بدین روابط رو به هم بزنین
- `[ 64.800– 65.980]` (med, lp -0.3, nsp 0.218)  دوسترین بدلکش کنین
- `[ 66.740– 67.980]` (med, lp -0.3, nsp 0.218)  شاید هم
- `[ 68.520– 69.780]` (med, lp -0.3, nsp 0.218)  بدلکش کرده باشین

**Planned-section mapping:**

- **P1** `0.88–16.76s` — hook + scenario; paraphrased ('حال ما رو تغییر بده' instead of 'حالت رو خراب کنه')
- **P2** `18.1–41.9s` — spiral questions; 'مگه من چی گفتم؟' not recoverable (quiet region); several [?] tokens
- **P3** `42.4–69.78s` — thoughts continue, mood changes, fight/message/block; 'زنگ نمی‌زنم' absent; verbs rephrased with دوست دارین

**Word-level diff vs planned script:**
- Matches: چی شد؟; فقط ... باشه; ناراحت شده; دوستم نداره (plan: منو دوست نداره); عصبانی/ناراحت; بلاکش کنین/کرده باشین; این فکرها ادامه پیدا می‌کنن; حال‌تون عوض شده
- Paraphrases: «حالت رو خراب کنه؟» → «حال ما رو تغییر بده؟»; scenario line reworded (پیام می‌دادین و اون برگشت گفته باشه); P3 questions recast as «دوست دارین ...» instead of «شاید با خودتون بگین»; «شاید» mostly rendered as «حتماً/فکر می‌کنم»
- Omissions: P2 «مگه من چی گفتم؟» — no recoverable equivalent (quiet 27-57s region); P3 «دیگه پیام نمی‌دم، زنگ نمی‌زنم» — زنگ نمی‌زنم absent; پیام بدین روابط رو به هم بزنین replaces it
- Additions: fillers: یهو (16.76s), اه (21.54s), اممم/نمی‌دونم (31.7-32.8s); «ما میریم توی یه فاز دیگه، به خودمون می‌گیم» (18.1s); «به خاطر این‌که دوستم نداره این‌طوری جواب داده» (39.2s); incoherent segment 51.52-54.36s (uncertain, see [?] list)
- Uncertain: 11 flagged tokens; concentrated in the low-level 27-57s region

**Uncertain tokens [?]:** یک گوچی (ASR for کوچیک؟); اون برگشت گفته باشه [?]; چه تفاقی گفته داده [?]; شاید از اصلا عصبانیم [?]; برای شما هم نیستم [?] (plan had براش مهم نیستم); اصلا با من اهمیت نمیدونیم [?]; یه خودتون میانید [?]; یه ساعت قبل نیستیم (whole segment 51.52-54.36s semantically incoherent); اصابه نیترین (عصبانی‌ترین؟); نارهت (ناراحت؟); دوست دارین باشه دعوا کنین [?]

**Recommended corrected narration (only what was actually said; ASR errors normalized, colloquial style kept):**

> یه پیام ساده‌ی کوچیک، چطور می‌تونه حال ما رو تغییر بده؟ خب، تا حالا براتون پیش اومده حتماً که به یکی پیام می‌دادین و اون [برگشت؟] گفته باشه یه جواب خیلی کوتاه داده. و چه اتفاقی افتاده [؟]؟ یهو! ما میریم توی یه فاز دیگه، به خودمون می‌گیم: اه! چی شد؟ چرا این‌طوری شد؟ چقدر کوتاه جواب داد؟ فقط گفته: باشه. فکر می‌کنم ناراحت شده. شاید [از؟] عصبانی‌ام [؟]. نمی‌دونم. شاید اصلاً برای شما هم نیستم [؟]. اصلاً [به من؟] اهمیت نمی‌ده [؟]. حتماً دوستم نداره. به خاطر این‌که دوستم نداره این‌طوری جواب داده. و این فکرها این‌قدر ادامه پیدا می‌کنن که خودتون می‌بینید حال‌تون هم عوض شده. [بخش ۵۱٫۵۲ تا ۵۴٫۳۶ ثانیه نامفهوم است]. الان عصبانی‌ترین، الان ناراحت‌ترین. و حالا حال‌تون خرابه. دوست دارین [باهاش؟] دعوا کنین. دوست دارین پیام بدین روابط رو به هم بزنین. دوست دارین بلاکش کنین. شاید هم بلاکش کرده باشین.

### s02.mp3 — `قسمت دوم.mp3`  (36.154 s)

**Raw transcript — verbatim recognizer output (phrase timestamps; word timestamps + probabilities in JSON):**

- `[  0.740–  5.500]` (med, lp -0.306, nsp 0.161)  خب، خب، استوپ کنیم، بین برگردیم اخب، ببینیم واقعاً چی شد.
- `[  6.460– 11.840]` (med, lp -0.306, nsp 0.161)  همه چیز از از اینجایی شروع شد که اون فقط یه جواب قوطا نوشت، خیلی قوطا و گفت باشیم.
- `[ 12.960– 19.480]` (med, lp -0.306, nsp 0.161)  زهنماشون آدت نداره همه چی اینقدر ساده باشه، شروع میکنه به پر کردن و جاهای خالی.
- `[ 19.640– 25.140]` (med, lp -0.306, nsp 0.161)  و از اینجایی که همیشه میخواسته بقایی ما رو حفظ کنه، اولویت با بدترین چیز هست.
- `[ 25.140– 31.100]` (med, lp -0.368, nsp 0.051)  پس میریم سراقه بدترین و دردناکترین چیز ها تکن بود اطلاعات رو جبران کنیم.
- `[ 31.200– 32.620]` (med, lp -0.368, nsp 0.051)  جالب شد نه؟
- `[ 32.620– 33.460]` (med, lp -0.368, nsp 0.051)  به همین سادگی.

**Planned-section mapping:**

- **P4** `0.74–11.84s` — stop / go back / short answer باشه
- **P5** `12.96–32.62s` — mind fills gaps, worst-case bias; full coverage incl. 'جالب شد نه؟'
- **EXTRA (unplanned)** `32.62–33.46s` — unplanned addition: 'به همین سادگی.'

**Word-level diff vs planned script:**
- Matches: خب خب استپ; برگردیم عقب; واقعاً چی شد؟; جواب کوتاه، خیلی کوتاه، باشه; ذهن عادت نداره ساده باشه / پر کردن جاهای خالی; بقای ما رو حفظ کنه / اولویت بدترین; بدترین و دردناک‌ترین / کمبود اطلاعات جبران; جالب شد نه؟
- Paraphrases: «استپ» spoken as «استوپ کنیم»; stutter «از از» kept in raw; «ببینیم» inserted before واقعاً چی شد
- Omissions: none
- Additions: closing «به همین سادگی.» (32.62-33.46s) — not in plan
- Uncertain: none semantic; recognition errors قوطا→کوتاه, زهنماشون→ذهنمون, سراقه→سراغ corrected by cross-file context

**Uncertain tokens [?]:** استوپ کنیم (likely spoken 'stop' فارسی‌شده؛ kept as heard)

**Recommended corrected narration (only what was actually said; ASR errors normalized, colloquial style kept):**

> خب، خب، استپ کنیم. بیاین برگردیم عقب، ببینیم واقعاً چی شد. همه‌چیز از اینجایی شروع شد که اون فقط یه جواب کوتاه نوشت، خیلی کوتاه، و گفت: باشه. ذهنمون عادت نداره همه‌چی این‌قدر ساده باشه، شروع می‌کنه به پر کردن جاهای خالی. و از اینجایی که همیشه می‌خواسته بقای ما رو حفظ کنه، اولویت با بدترین چیز هست. پس میریم سراغ بدترین و دردناک‌ترین چیزها تا کمبود اطلاعات رو جبران کنیم. جالب شد، نه؟ به همین سادگی.

### s03.mp3 — `قسمت 3.mp3`  (36.441 s)

**Raw transcript — verbatim recognizer output (phrase timestamps; word timestamps + probabilities in JSON):**

- `[  1.000–  2.500]` (med, lp -0.202, nsp 0.094)  خب، حالا چی کار کنیم؟
- `[  2.500–  4.780]` (med, lp -0.202, nsp 0.094)  باید بتونیم واقعیت رو تفکی کنیم.
- `[  4.920–  6.160]` (med, lp -0.202, nsp 0.094)  واقعیت چیه؟
- `[  6.160–  7.880]` (med, lp -0.202, nsp 0.094)  جواب کتاح باشه.
- `[  8.220–  9.440]` (med, lp -0.202, nsp 0.094)  فکرهای من چیه؟
- `[  9.440– 11.040]` (med, lp -0.202, nsp 0.094)  همه اون دستانایی که گفتن.
- `[ 11.580– 14.200]` (med, lp -0.202, nsp 0.094)  واقعیت چیزی که واقعا نه تفاق افتاده
- `[ 14.200– 17.440]` (med, lp -0.202, nsp 0.094)  اما تفسیر دستانایی که زهن من اون رو ساخته.
- `[ 18.080– 21.980]` (med, lp -0.202, nsp 0.094)  پس بجای اینکه جای خادی رو با حدس های خودمون پر کنیم,
- `[ 22.100– 23.980]` (med, lp -0.202, nsp 0.094)  بهتره که یه سوال بپرسیم.
- `[ 23.980– 31.320]` (med, lp -0.236, nsp 0.071)  مثلا، چه پیام قطایی دادی؟ حالت خوبه؟ سرت شلوغه؟ نیاز به کمک داری؟
- `[ 31.320– 36.220]` (med, lp -0.236, nsp 0.071)  این طوری اطلاعات و با چیزای درست پر میکنیم، نه چیزای که فکر میکنیم.

**Planned-section mapping:**

- **P6** `1.0–17.44s` — reality vs interpretation; 'یه' before 'جواب کوتاه' omitted; 'اما' added
- **P7** `18.08–36.22s` — ask questions; closing line paraphrased ('اطلاعات رو با چیزای درست پر می‌کنیم' instead of 'اطلاعات درست‌تری می‌گیریم')

**Word-level diff vs planned script:**
- Matches: حالا چیکار کنیم; واقعیت رو تفکیک کنیم; واقعیت چیه / جواب کوتاه باشه; فکرهای من چیه / داستانایی که گفتم; واقعیت چیزیه که واقعاً اتفاق افتاده; تفسیر داستانیه که ذهن ساخته; جای خالی با حدس پر کردن / سوال بپرسیم; چه پیام کوتاهی دادی؟ حالت خوبه؟ سرت شلوغه؟ نیاز به کمک داری؟
- Paraphrases: closing «اطلاعات درست‌تری می‌گیریم» → «اطلاعات رو با چیزای درست پر می‌کنیم، نه چیزایی که فکر می‌کنیم»
- Omissions: «یه» before «جواب کوتاه» (6.16s)
- Additions: «اما» before تفسیر (14.2s); expanded closing sentence
- Uncertain: none semantic; کتاح/قطایی→کوتاه, تفکی→تفکیک, خادی→خالی corrected by context

**Uncertain tokens [?]:** قطایی/کتاح (context: کوتاه across all files)

**Recommended corrected narration (only what was actually said; ASR errors normalized, colloquial style kept):**

> خب، حالا چی‌کار کنیم؟ باید بتونیم واقعیت رو تفکیک کنیم. واقعیت چیه؟ جواب کوتاه: باشه. فکرهای من چیه؟ همه‌ی اون داستانایی که گفتم. واقعیت چیزیه که واقعاً اتفاق افتاده. اما تفسیر، داستانیه که ذهن من اون رو ساخته. پس به‌جای اینکه جای خالی رو با حدس‌های خودمون پر کنیم، بهتره که یه سوال بپرسیم. مثلاً: چه پیام کوتاهی دادی؟ حالت خوبه؟ سرت شلوغه؟ نیاز به کمک داری؟ این‌طوری اطلاعات رو با چیزای درست پر می‌کنیم، نه چیزایی که فکر می‌کنیم.

### s04.mp3 — `قسمت 4.mp3`  (12.147 s)

**Raw transcript — verbatim recognizer output (phrase timestamps; word timestamps + probabilities in JSON):**

- `[  1.000–  5.000]` (med, lp -0.203, nsp 0.177)  و اینطوری حالمون احتمالا به خاطره یه باشه ساده خراب نمیشه.
- `[  6.200– 11.240]` (med, lp -0.203, nsp 0.177)  یادتون باشه هر فکر که میاد توی زهنمون لوزومن واقعیت نداره.

**Planned-section mapping:**

- **P8** `1.0–11.24s` — outro; closing paraphrased ('لزوماً واقعیت نداره' instead of 'واقعیت نیست')

**Word-level diff vs planned script:**
- Matches: حالمون احتمالاً به‌خاطر یه باشه ساده خراب نمی‌شه; یادتون باشه; هر فکری که میاد توی ذهنمون; واقعیت نداره
- Paraphrases: «واقعیت نیست» → «لزوماً واقعیت نداره»; «یه باشه‌ی ساده» → «یه باشه ساده»
- Omissions: none
- Additions: 
- Uncertain: none semantic; لوزومن→لزوماً, زهنمون→ذهنمون corrected by context

**Uncertain tokens [?]:** لوزومن (context: لزوماً)

**Recommended corrected narration (only what was actually said; ASR errors normalized, colloquial style kept):**

> و این‌طوری حالمون احتمالاً به‌خاطر یه باشه ساده خراب نمی‌شه. یادتون باشه هر فکری که میاد توی ذهنمون لزوماً واقعیت نداره.

## 3. Coverage of the eight planned sections

| Section | Found in | In-file time range | Status |
|---|---|---|---|
| P1 | s01 | 0.88–16.76 s | present, paraphrased opening |
| P2 | s01 | 18.10–41.90 s | present; «مگه من چی گفتم؟» unrecoverable, quiet region |
| P3 | s01 | 42.40–69.78 s | present, recast verbs; «زنگ نمی‌زنم» absent; one incoherent sub-segment |
| P4 | s02 | 0.74–11.84 s | present, full |
| P5 | s02 | 12.96–32.62 s | present, full, incl. «جالب شد نه؟» |
| P6 | s03 | 1.00–17.44 s | present, full |
| P7 | s03 | 18.08–36.22 s | present; closing line paraphrased |
| P8 | s04 | 1.00–11.24 s | present; closing line paraphrased |

- **No planned section is missing entirely.** All eight occur across the four takes in narrative order (s01 = P1+P2+P3, s02 = P4+P5, s03 = P6+P7, s04 = P8).
- **Unplanned content:** s02 adds «به همین سادگی.»; s01 adds fillers (یهو، اه، اممم/نمی‌دونم), the bridge line «ما میریم توی یه فاز دیگه ...», «به خاطر اینکه دوستم نداره این‌طوری جواب داده», and one semantically incoherent 51.52–54.36 s segment; s03 adds «اما» and an expanded closing sentence.
- **Not recoverable (no reliable words, not silent):** s01 51.52–54.36 s; parts of 29–38 s carry [?] tokens.

## 4. Reliability for subtitles / kinetic typography

- **s01.mp3**: mean word probability 0.837, min 0.211, mean segment logprob -0.307, low-probability tokens (p<0.70): 29
- **s02.mp3**: mean word probability 0.818, min 0.188, mean segment logprob -0.333, low-probability tokens (p<0.70): 15
- **s03.mp3**: mean word probability 0.856, min 0.29, mean segment logprob -0.208, low-probability tokens (p<0.70): 9
- **s04.mp3**: mean word probability 0.85, min 0.422, mean segment logprob -0.203, low-probability tokens (p<0.70): 2

- s02, s03, s04: high reliability (mean word p 0.82–0.86, low no-speech probabilities) — suitable for subtitles and kinetic typography after normalizing the listed context-corrected ASR spellings (کوتاه، تفکیک، خالی، لزوماً، ذهن).
- s01: loud sections (0–27 s, 58–70 s) equally reliable; the quiet 27–57 s middle is medium-confidence even after large-v3 rescue (29 low-p tokens, one incoherent segment). **Human review of the s01 [?] list is required before locking subtitles.** Word timestamps exist for every token, so kinetic scheduling is still possible; mark [?] tokens as non-anchor words.

## 5. Cleanup recommendations (no cleaning performed in this pass)

- **s01.mp3**: remove shared 4-sample t=0 edge transient; trim 0.11s trail silence; level automation/AGC required: 27-57s region sits 10-15 dB below the rest (off-mic); file RMS -32.6 dBFS; compress 36 internal pauses >=0.5s (longest 1.92s) toward 0.5-0.7s; highpass 80 Hz; light afftdn (nr 8-10, nf -40); loudnorm to I=-16 LUFS TP=-2 dBTP; playback 1.0x (optionally 1.03-1.05x only if the timeline requires it)
- **s02.mp3**: remove shared 4-sample t=0 edge transient; trim 0.09s trail silence; compress the 2.62s pause at 33.42s and 1.46s pause at 5.02s; highpass 80 Hz; light denoise; loudnorm I=-16 TP=-2; playback 1.0x
- **s03.mp3**: remove shared 4-sample t=0 edge transient; trim 0.32s trail silence; internal pauses <=1.16s: minimal compression only; highpass 80 Hz; light denoise; loudnorm I=-16 TP=-2; playback 1.0x
- **s04.mp3**: remove shared 4-sample t=0 edge transient; trim 1.1-1.2s trail silence; compress 1.24s pause at 10.96s if desired; highpass 80 Hz; light denoise; loudnorm I=-16 TP=-2; playback 1.0x

Objective pause inventory (runs ≥ 0.5 s below -40 dBFS): s01 = 36 runs, longest 1.92 s at 41.08 s; s02 = 11 runs, longest 2.62 s at 33.42 s; s03 = 6 runs, longest 1.16 s at 16.92 s; s04 = 3 runs, longest 1.24 s at 0.02 s edge region. Loudness spread across files: RMS -32.6 / -25.7 / -23.6 / -26.3 dBFS — loudness normalization is required before mixing.
