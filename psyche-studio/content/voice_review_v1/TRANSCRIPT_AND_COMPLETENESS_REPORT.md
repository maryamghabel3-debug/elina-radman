# Voice inventory and transcript/completeness review

**Status: inventory and safe listening samples are ready; speaker attribution and transcription are blocked.** No dialogue was assembled or rendered.

## Recovery

- Verified branch: `arena/988cf418-elina-radman`.
- At review start, the local checkout was clean but at the base commit. The remote branch was safely fast-forwarded to `9f43db83425db8c7fc136130a9352c93ac1db3ce` before inspecting uploads.
- The files below are tracked originals. They were not renamed, moved, edited, or overwritten. The reference samples are bit-for-bit copies, verified by SHA-256.

## Uploaded-file inventory

| Candidate | Exact source path | Container / stream | Duration | Size | SHA-256 |
|---|---|---|---:|---:|---|
| Candidate 01 | `psyche-studio/content/voice_gemini_v1/tts-audio (8).mp3` | MP3; 1 audio stream, no video; 24 kHz mono; 128 kb/s | 77.16 s | 1,234,560 bytes | `b0b85794b44d7d1f995b09290be4a5b879ce5213bc12168c1f03a016e1ff9e39` |
| Candidate 02 | `psyche-studio/content/voice_gemini_v1/صدای الی.mp3` | MP3; 1 audio stream, no video; 24 kHz mono; 128 kb/s | 66.50 s | 1,064,064 bytes | `ab8e034d61501b990011f1ba1918eba4f8bbbb94b1b92a242e8c543ae4235e05` |

Both files pass a complete FFmpeg decode. The Persian filename translates approximately to “Eli’s voice,” but that is only a filename hint—not evidence of the spoken content or speaker. `tts-audio (8)` contains no speaker-identifying stem. **Neither candidate can be assigned to Eli or Elina from the evidence available here.**

## Transcription and completeness: not verified

There is no local Persian ASR executable/module or cached speech-recognition model in this checkout, and this interface cannot listen to the uploaded audio. No transcript was fabricated, and no model or external transcription service was used. Consequently:

- The presence/order of the six first-scene turns is **unknown**, not confirmed and not disproven.
- The words actually spoken, pronunciation of `«باشه»` or `ذهن‌خوانی`, unexpected read-aloud instructions, and missing/repeated lines are **not verified**.
- Beginning/ending truncation and whether the website’s character limit cut off later dialogue are **unknown**. Duration alone cannot establish completeness.
- The silent-silence scan found no interval at least 2.0 seconds below −45 dBFS in either file. This is only a technical threshold check; it does not identify words or determine whether shorter pauses are intentional.

The requested first-scene checklist is therefore:

| Turn | Reference text | Presence / recoverability |
|---:|---|---|
| 01 Eli | `الینا! الینا! گوشیت لرزید!` | Not verifiable |
| 02 Elina | `آره، دیدم... جواب داده.` | Not verifiable |
| 03 Eli | `خب؟ چی نوشته؟ زود باش بخون!` | Not verifiable |
| 04 Elina | `فقط نوشته «باشه».` | Not verifiable |
| 05 Eli | `همین؟! فقط باشه؟ نه سلامی، نه استیکری، نه هیچی؟` | Not verifiable |
| 06 Elina | `نه... فقط همین.` | Not verifiable |

Because speaker identity, transcript, and turn boundaries cannot be verified, I **stopped before dialogue assembly**. No first-scene preview or cue manifest was created; no pauses were used as guessed turn boundaries.

## Listening files and conservative level match

The reference MP3s below are exact copies of the uploaded originals. Prepared WAVs are generic candidate labels because mapping them to character names is unverified.

| Candidate | Unprocessed reference | Lightly level-matched sample |
|---|---|---|
| 01 (`tts-audio (8).mp3`) | [candidate_01_reference.mp3](candidate_01_reference.mp3) | [candidate_01_prepared.wav](candidate_01_prepared.wav) |
| 02 (`صدای الی.mp3`) | [candidate_02_reference.mp3](candidate_02_reference.mp3) | [candidate_02_prepared.wav](candidate_02_prepared.wav) |

Measured original integrated loudness differed by about 7.8 LU (candidate 01: −27.4 LUFS; candidate 02: −19.6 LUFS). For comparison only, I applied static gain of +3.9 dB and −3.9 dB respectively, targeting approximately −23.5 LUFS. The resulting files measure −23.5 and −23.4 LUFS, with true peaks −4.1 and −5.4 dBFS. No EQ, denoising, gating, dynamic compression, time stretch, internal-pause removal, splicing, or word edits were applied. A −2 dBFS safety limiter was present but the measured peaks stayed below −4 dBFS.

Level matching only makes the candidates easier to compare. It does not improve acting or make an ordinary performance expressive. No subjective claim about performance quality is made here; please use the paired samples for listening judgement.

## Next verification needed

Before naming files `eli_prepared` / `elina_prepared`, cutting any turns, or building the first-scene audio preview, the actual spoken transcript and speaker-to-file mapping must be verified. The filenames alone do not meet that requirement. Once verified, turn boundaries should be aligned from the spoken words/timestamps—not inferred from text line breaks or silence detection.

---

## Environment and ASR feasibility recheck — 2026-11-04

**Result: transcription is still blocked in this sandbox.** This recheck did not alter or re-encode either original audio file.

### 1. Availability and acquisition route

- The current Python environment has no `faster-whisper`, `ctranslate2`, Whisper, PyTorch, ONNX Runtime, or Hugging Face Hub package; no corresponding command-line ASR tool was found. No Whisper/CTranslate2 model files or model cache were found under the workspace or user cache, and the pip wheel cache contains no locally built wheels.
- The project architecture document (`docs/architecture/EDITOR-SUITE-SPEC-V2.md`) lists `faster-whisper` as an optional engine, but does **not** pin a model ID/revision, provide an acquisition recipe, or record file checksums. Repository reports/history likewise contain no prior model artifact or verifiable acquisition record. I cannot recover the previous session’s model from this checkout.
- I checked the [official SYSTRAN faster-whisper README](https://github.com/SYSTRAN/faster-whisper#model-conversion). It says the standard named-model path downloads its CTranslate2 checkpoint from the Hugging Face Hub. The official model host is not among this sandbox’s permitted outbound hosts. The runtime package can be obtained from PyPI, but installing it alone would not provide the model weights.
- No weights were downloaded or used. Because no exact checkpoint/revision was identified and the official artifact host cannot be reached here, I did not estimate or fetch a model payload. No unofficial mirror or unverified weights were considered.

With a verified multilingual Whisper/CTranslate2 model already available locally, a Persian (`fa`) faster-whisper run with segment/word timestamps would be technically possible. That has **not** been tested on these recordings, so accuracy/reliability cannot be claimed now.

### 2. Transcript obtained

**None.** No text was inferred from filenames, planned dialogue, pauses, or metadata.

### 3. Opening-turn coverage

All six remain **unknown / not verifiable**, not “missing”: turns 01–06 in the checklist above. Speaker-to-file assignment is also unverified.

### 4. Uncertain words and truncation

No spoken words or timestamps are available to mark as uncertain. Pronunciation of `«باشه»` and `«ذهن‌خوانی»`, omissions/repetitions, unexpected speech, and beginning/ending or website-character-limit truncation remain **unverified** for both sources. File duration and the earlier silence-threshold scan cannot settle these questions.

### 5. Exact smallest next action

Make the **previously used, Persian-capable CTranslate2 model directory** available locally with its official model ID/revision and a provenance/integrity manifest (SHA-256 for the model files), or provide a route that permits fetching that exact official checkpoint. Then install the faster-whisper runtime from PyPI if needed and run it on the two unchanged sources. Until that checkpoint is verifiably available, transcription and turn-coverage claims must remain blocked.
