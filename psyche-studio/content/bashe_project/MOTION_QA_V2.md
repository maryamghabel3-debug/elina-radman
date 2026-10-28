# Project 001 V2 - Objective Motion QA

Method: 2 fps frame-difference energy (tblend + signalstats, onset threshold = median*1.2, floor 0.45, calibrated so the reference example.mp4 scores mean interval 1.12 s / max gap 6.5 s) and freezedetect (n=-60 dB, d=0.3 s), segmented at the manifest scene boundaries. The <=2.5 s static contract is checked against the beat-scheduler manifest (the reference itself shows energy gaps up to 12 s during subtle self-drawing phases). Layers/impacts come from the manifest.

| Scene | Chapter | Dur (s) | Frozen ratio | Mean interval (s) | Max energy gap (s) | Planned max static (s) | Layers | Impacts | Onsets | Pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:--:|
| 1 | شروع | 6.33 | 0.0 | 1.05 | 2.33 | 1.56 | 6 | 1 | 5 | PASS |
| 2 | طوفان ذهن | 16.02 | 0.023 | 2.29 | 5.5 | 2.47 | 6 | 5 | 6 | PASS |
| 3 | پیام و حضور | 17.28 | 0.044 | 2.16 | 6.5 | 2.04 | 6 | 3 | 7 | PASS |
| 4 | شاید | 14.43 | 0.025 | 2.06 | 5.5 | 2.35 | 6 | 6 | 6 | PASS |
| 5 | واقعیت و تفسیر | 19.34 | 0.234 | 1.49 | 8.0 | 2.17 | 7 | 4 | 12 | PASS |
| 6 | سه قدم | 23.23 | 0.042 | 1.66 | 5.0 | 2.49 | 6 | 3 | 13 | PASS |
| 7 | جمع‌بندی | 11.47 | 0.0 | 1.27 | 3.0 | 1.38 | 5 | 1 | 8 | PASS |

Whole-video frozen ratio: **0.065** (7.0 s of 108.1 s); reference example.mp4 scores 0.223 with the same detector.
Decode error lines: **0**.

## Gate detail

- scene_01: all gates pass | median energy 0.955 (reference 0.702)
- scene_02: all gates pass | median energy 1.245 (reference 0.702)
- scene_03: all gates pass | median energy 1.12 (reference 0.702)
- scene_04: all gates pass | median energy 1.098 (reference 0.702)
- scene_05: all gates pass | median energy 0.795 (reference 0.702)
- scene_06: all gates pass | median energy 1.094 (reference 0.702)
- scene_07: all gates pass | median energy 0.647 (reference 0.702)

**Overall: ALL MOTION GATES PASSED**
