# Voice V2 listening variants — report

## Status

- **Speaker mapping:** accepted from the user: candidate 01 = Elina; candidate 02 (`صدای الی`) = Eli. This mapping was not inferred from filenames.
- **Originals:** left unchanged. SHA-256 still matches the prior manifest: candidate 01 `b0b85794b44d7d1f995b09290be4a5b879ce5213bc12168c1f03a016e1ff9e39`; candidate 02 `ab8e034d61501b990011f1ba1918eba4f8bbbb94b1b92a242e8c543ae4235e05`.
- **ASR:** no transcript obtained. This reset has no faster-whisper/Whisper package, CTranslate2 runtime, model, ignored project venv, or cached model chunks; `/tmp` is empty. The project and current checkout contain no pinned model/revision or verifiable acquisition recipe. Faster-whisper’s standard checkpoint route is the Hugging Face Hub, which is not reachable from this sandbox’s permitted outbound hosts. I did not fetch unofficial weights or any ASR model.
- **Signal-processing tools:** FFmpeg and NumPy were installed temporarily under this review folder solely for PCM processing/QA; their temporary runtime/work files are not part of the deliverables.

## Transcript / opening-turn boundary check

No spoken words can be verified, so presence, omission, repetition, the 1,000-character truncation risk, and pronunciation of `«باشه»` / `«ذهن‌خوانی»` remain unknown. The first six turns are **not classed as present or missing**:

| Turn | Expected speaker / text | Status |
|---:|---|---|
| 01 | Eli — `الینا! الینا! گوشیت لرزید!` | Not verified |
| 02 | Elina — `آره، دیدم... جواب داده.` | Not verified |
| 03 | Eli — `خب؟ چی نوشته؟ زود باش بخون!` | Not verified |
| 04 | Elina — `فقط نوشته «باشه».` | Not verified |
| 05 | Eli — `همین؟! فقط باشه؟ نه سلامی، نه استیکری، نه هیچی؟` | Not verified |
| 06 | Elina — `نه... فقط همین.` | Not verified |

I also checked the decoded originals’ short-time RMS envelope. At a −35 dBFS threshold with 10 ms windows, both tracks contain many sub-second low-energy gaps rather than a stable three-turn pattern per character. Merging gaps up to 0.50 s yields 29 candidate clusters for Elina and 12 for Eli; increasing that tolerance to 0.75 s collapses them to 2 and 1. There are no inter-speech gaps of 0.8 s or longer at that threshold. These counts are highly threshold-dependent and include ordinary within-line phrase pauses; they do **not** verify turn count or text. Therefore the six-turn cuts are ambiguous and no dialogue preview or `scene1_cues.json` was created.

## Processing and listening samples

Each original was decoded once to floating-point PCM; all filtering, speed/pitch changes, loudness control, and excerpt fades were applied before MP3 encoding. No source trimming, word edits, heavy denoising, or internal-pause removal was done.

- **Preset A — clean_bright_fast:** Elina high-pass 102 Hz, −4 dB at 230 Hz, +2.5 dB at 3.5 kHz, 1.15× tempo. Eli high-pass 130 Hz, −5 dB at 250 Hz, +3.5 dB at 4 kHz, 1.22× tempo.
- **Preset B — character_contrast:** Elina uses the same cleanup at 1.18× tempo. Eli uses the same cleanup at 1.24× total tempo and +2 semitones through resampling with tempo compensation.
- Both use gentle 2:1 compression, loudness normalization, and a peak-safety stage. Final MP3 true peaks were measured after encoding. No subjective claim about liveliness, professionalism, or listening preference is made; please judge the samples yourself.

### Full-file variants

| Character / preset | Original → processed duration | Measured speed | Original → output LUFS | Original → output true peak | Spectral centroid, original → processed | Relative 20–300 Hz energy reduction* |
|---|---:|---:|---:|---:|---:|---:|
| Elina A | 77.160 → 67.100 s | 1.15× | −27.4 → −18.4 | −8.0 → −1.8 dBFS | 2286 → 2645 Hz (+359 Hz) | 1.72 dB |
| Elina B | 77.160 → 65.410 s | 1.18× | −27.4 → −17.9 | −8.0 → −1.6 dBFS | 2286 → 2633 Hz (+347 Hz) | 1.72 dB |
| Eli A | 66.504 → 54.530 s | 1.22× | −19.6 → −17.8 | −1.5 → −2.9 dBFS | 1869 → 2258 Hz (+390 Hz) | 1.36 dB |
| Eli B | 66.504 → 53.680 s | 1.24×, +2 semitones | −19.6 → −17.9 | −1.5 → −2.0 dBFS | 1869 → 2403 Hz (+535 Hz) | 1.52 dB |

All final variants decode fully and meet the requested true-peak ceiling of −1.5 dBFS. The normalization pass targeted −16 LUFS; conservative post-encode peak safety trims leave the delivered files at −17.8 to −18.4 LUFS.

\*Spectral measurements use 24 kHz PCM before MP3 encoding: Hann-windowed 2048-sample frames, 1024-sample hop, centroid over 20 Hz–10 kHz (frames above −45 dBFS), and low-band power ratio 20–300 Hz relative to 20 Hz–10 kHz. Reduction is the change in that ratio versus the corresponding original. These are objective spectral comparisons, not a guarantee of subjective preference.

### Full files

- [Elina — Preset A](elina_presetA.mp3)
- [Elina — Preset B](elina_presetB.mp3)
- [Eli — Preset A](eli_presetA.mp3)
- [Eli — Preset B](eli_presetB.mp3)

### Start excerpts for quick A/B listening

Because the opening turns were not verified, these are **prefix excerpts, not scene dialogue**. Each is 16.90–18.85 seconds and ends in a low-RMS pause with a 10 ms fade; all decode checks pass.

- [Elina — Preset A excerpt](elina_presetA_excerpt.mp3)
- [Elina — Preset B excerpt](elina_presetB_excerpt.mp3)
- [Eli — Preset A excerpt](eli_presetA_excerpt.mp3)
- [Eli — Preset B excerpt](eli_presetB_excerpt.mp3)

## Not produced

`scene1_dialogue_presetA.mp3`, `scene1_dialogue_presetB.mp3`, `scene1_cues.json`, and the voiced video were not created. Without verified words and line boundaries, creating those would require guessing. No video composition was modified or rendered.
