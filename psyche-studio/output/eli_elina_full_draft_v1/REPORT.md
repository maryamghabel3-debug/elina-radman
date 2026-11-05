# Eli–Elina full voiced draft v1 — build and QA report

## Deliverables

- `eli_elina_full_draft_v1.mp4` — 1080×1920, 30 fps, H.264/yuv420p video with AAC-LC stereo audio.
- `full_cues.json` — all 35 turns in script order, with active-speech start/end, padded segment bounds, speaker, Persian text, camera/visual metadata, per-turn RMS envelope, confidence, and segmentation measurements.
- `CONTACT_SHEET.png` — 12 labelled narrative frames.

Runtime is **114.27 seconds** (3,428 frames). The MP4 container reports 114.28 seconds because of AAC encoder padding.

## Audio and turn assembly

- Eli uses `content/voice_review_v2/eli_presetB.mp3` unchanged.
- Elina uses the replaceable stem path `content/voice_review_v2/elina_draft.mp3`. It was made from preset B with a 140 Hz high-pass, −5 dB at 220 Hz/Q1, +2 dB high shelf above 4 kHz, moderate compression, loudness processing, and a 48 kHz mono MP3 encode. The measured final stem is **−16.3 LUFS / −1.7 dBFS true peak**. No subjective voice-quality claim is made.
- Segmentation used 24 kHz decoded PCM and 10 ms RMS windows; the floor estimate was the per-stem 20th percentile, with candidate silences below floor+6 dB for at least 180 ms. No ASR was run.
- The 17 Elina and 18 Eli chunks were ordered by the supplied alternating script. Each boundary retains 80 ms of source padding. A 40 ms timeline insert compensates for the retained padding; measured active-speech-to-active-speech gaps are **0.200 s min / mean / max**. There are no crossfades; the mixed dialogue is encoded once into the video’s AAC track.
- Longest-silence-only chunk-duration/text-character correlation was weak (Pearson r: Elina **0.183**, Eli **0.200**). The constrained, character-duration-guided pause reselection improved this to Elina **0.971** and Eli **0.855**. This is only a segmentation heuristic, not transcript verification.

### Confidence

| Speaker | High | Medium | Low | Refined duration/character r |
|---|---:|---:|---:|---:|
| Elina (17 turns) | 10 | 7 | 0 | 0.971 |
| Eli (18 turns) | 0 | 9 | 9 | 0.855 |

Low-confidence Eli turns are **5, 7, 13, 15, 25, 27, 29, 33, 35**. The most conspicuous duration outliers are Eli source lines 13–15 (video turns 25, 27, 29); their duration/expected-character ratios are approximately **2.115, 0.507, and 0.308**. Those boundaries may be misplaced. Elina’s medium-confidence turns are 10, 16, 18, 22, 24, 28, and 30. Keep the timing provisional if editing the dialogue.

## Visual implementation

The new direct Remotion entry reuses the existing room plate, Eli/Elina pose images, and bundled Vazirmatn font without changing the existing bubble-test composition. Cue metadata drives shared shots, Eli and Elina close-ups, and phone close-ups, with the requested thought storm, block impulse, “استپ” freeze, rewind, tone labels, fact-vs-story split card, chat/question/reply, warm outro, and final gag/CTA-safe space. Persian text uses RTL layout and browser-native shaping with Vazirmatn. No name tags or body-bounce animation were added.

Mouth motion is a **per-turn RMS-threshold lip-flap**, with the listener’s mouth closed. It is not phoneme-based lip-sync.

## QA performed

- `npx tsc --noEmit` passed for the Remotion project.
- Full FFmpeg decode completed without errors: 3,428 video frames; H.264 High, 1080×1920, 30 fps, yuv420p; AAC-LC, 48 kHz stereo.
- Compared the rendered AAC’s 10 ms RMS envelope with the lossless mix reference: maximum correlation **0.967 at 0-frame lag**. The five spot-check turns 1, 7, 14, 28, and 35 all had audio energy across their cue windows; the measured levels were −18.0, −18.4, −16.7, −17.1, and −17.6 dBFS RMS respectively.
- Inspected the 12 labelled contact-sheet frames, including bubble/effect placement at turns 1, 7, 14, 28, and 35. Persian shaping is visible in the sampled frames; faces are not visibly cropped in those samples. The assets remain still apart from pose cuts, overlays, and camera zooms.
- **Only still frames were inspected; the moving footage was not watched end-to-end.**

## Known limitations

- Several Eli segment boundaries remain uncertain, especially lines 13–15; the supplied script is aligned by RMS pauses and character counts, not ASR or manual waveform listening.
- Lip motion is an approximate RMS-driven flap, not true lip-sync. The character art is still imagery, so emotion/motion is conveyed by pose selection, camera cuts/zooms, bubbles, and effects.
- This is a rough first draft. Review continuous playback and correct dialogue timing/visual beats before treating it as a final edit.

## Reproduction

Install the Python helpers with `python3 -m pip install -r psyche-studio/remotion/scripts/requirements-full-draft.txt`, then run `python3 psyche-studio/remotion/scripts/build-full-draft-audio.py`. To render, run `npm ci` from `psyche-studio/remotion`, followed by `./scripts/render-full-draft-v1.sh`. The render script stages its temporary cue/audio files under `remotion/public/` and removes them on exit. To swap Elina’s voice, replace `content/voice_review_v2/elina_draft.mp3` and rerun the audio build; the cue duration source is regenerated with it.
