# V3 Audio Cleanup Report

Non-destructive pipeline (`engine/audio_clean_v3.py`, driver `content/my_voice_cleaned_v3/run_cleanup_v3.py`). Sources in `content/my_voice_v2/` were never modified; every stem was decoded once to PCM and all processing stayed in PCM until the single final encode.

## Pipeline

1. single decode to mono 44.1 kHz PCM (numpy)
2. head/tail cosine fades (6/8 ms) for the encoder edge artifact
3. adaptive short-time RMS VAD; lead/trail room-tone trim with 120 ms padding
4. pause compression: non-speech runs > 0.75 s -> 0.25 s of original room tone, 8 ms cosine crossfades (normal speech pauses preserved)
5. atempo 1.12 (fastest value keeping natural Persian phrasing; no pitch change)
6. highpass 95 Hz; 250 Hz -4 dB (boominess); 3 kHz +2 dB presence; mild compressor (2.5:1); conservative afftdn nr=8 nf=-40 (no metallic/underwater target)
7. two-pass loudnorm I=-16 LUFS, TP=-2.0 dBTP; MP3 128 kbps encoded once
8. full voice: filter-concat with 0.30 s anullsrc gaps (no MP3 timestamp drift)

## Per-stem results

| Stem | Original (s) | Cleaned (s) | Saved (s) | I before (LUFS) | I after (LUFS) | TP after (dBTP) | Lead removed (s) | Trail removed (s) | Pauses compressed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cleaned_s1 | 70.687 | 49.732 | 20.955 | -31.4 | -17.4 | -2.0 | 0.72 | 0.0 | 17 |
| cleaned_s2 | 36.153 | 26.939 | 9.214 | -25.0 | -16.1 | -2.0 | 0.74 | 0.0 | 5 |
| cleaned_s3 | 36.441 | 29.39 | 7.051 | -23.1 | -16.0 | -2.0 | 0.98 | 0.221 | 3 |
| cleaned_s4 | 12.147 | 7.964 | 4.183 | -25.6 | -16.0 | -2.0 | 1.14 | 1.067 | 1 |

**Full voice** (`full_voice_cleaned.mp3`, 0.30 s gaps): I=-17.0 LUFS, true peak -2.4 dBTP.

## Click / transient handling

- **cleaned_s1**: impulses surviving the WAV decode = 0 (max sample jump 0.0842 FS). 4-sample encoder transient documented in TRANSCRIPT_REPORT.md; mitigation: 6 ms cosine head fade + 8 ms tail fade + VAD head trim; VAD head trim 0.72 s removes the edge region. Detected click events: 0.
- **cleaned_s2**: impulses surviving the WAV decode = 0 (max sample jump 0.0634 FS). 4-sample encoder transient documented in TRANSCRIPT_REPORT.md; mitigation: 6 ms cosine head fade + 8 ms tail fade + VAD head trim; VAD head trim 0.74 s removes the edge region. Detected click events: 0.
- **cleaned_s3**: impulses surviving the WAV decode = 0 (max sample jump 0.0673 FS). 4-sample encoder transient documented in TRANSCRIPT_REPORT.md; mitigation: 6 ms cosine head fade + 8 ms tail fade + VAD head trim; VAD head trim 0.98 s removes the edge region. Detected click events: 0.
- **cleaned_s4**: impulses surviving the WAV decode = 0 (max sample jump 0.054 FS). 4-sample encoder transient documented in TRANSCRIPT_REPORT.md; mitigation: 6 ms cosine head fade + 8 ms tail fade + VAD head trim; VAD head trim 1.14 s removes the edge region. Detected click events: 0.

## Compressed pauses (detail) and risky cuts

- **cleaned_s1**:
  - orig 0.72s, length 0.84s -> kept 0.25s (removed 0.59s)
  - orig 5.2s, length 1.48s -> kept 0.25s (removed 1.23s)
  - orig 8.86s, length 0.8s -> kept 0.25s (removed 0.55s)
  - orig 12.8s, length 0.76s -> kept 0.25s (removed 0.51s)
  - orig 27.5s, length 0.84s -> kept 0.25s (removed 0.59s)
  - orig 29.14s, length 1.12s -> kept 0.25s (removed 0.87s)
  - orig 30.46s, length 0.82s -> kept 0.25s (removed 0.57s)
  - orig 31.4s, length 1.02s -> kept 0.25s (removed 0.77s)
  - orig 33.4s, length 0.92s -> kept 0.25s (removed 0.67s)
  - orig 35.46s, length 1.26s -> kept 0.25s (removed 1.01s)
  - orig 37.46s, length 1.16s -> kept 0.25s (removed 0.91s)
  - orig 38.96s, length 1.42s -> kept 0.25s (removed 1.17s)
  - orig 41.8s, length 2.0s -> kept 0.25s (removed 1.75s)
  - orig 46.72s, length 0.76s -> kept 0.25s (removed 0.51s)
  - orig 51.52s, length 1.18s -> kept 0.25s (removed 0.93s)
  - orig 54.86s, length 0.84s -> kept 0.25s (removed 0.59s)
  - orig 66.98s, length 1.04s -> kept 0.25s (removed 0.79s)
  - RISK NOTE: borderline pause 0.84s at orig ~0.72s (within 0.10s of the 0.75s threshold)
  - RISK NOTE: borderline pause 0.80s at orig ~8.86s (within 0.10s of the 0.75s threshold)
  - RISK NOTE: borderline pause 0.76s at orig ~12.80s (within 0.10s of the 0.75s threshold)
  - RISK NOTE: borderline pause 0.84s at orig ~27.50s (within 0.10s of the 0.75s threshold)
  - RISK NOTE: borderline pause 0.82s at orig ~30.46s (within 0.10s of the 0.75s threshold)
  - RISK NOTE: borderline pause 0.76s at orig ~46.72s (within 0.10s of the 0.75s threshold)
  - RISK NOTE: borderline pause 0.84s at orig ~54.86s (within 0.10s of the 0.75s threshold)
- **cleaned_s2**:
  - orig 0.74s, length 0.86s -> kept 0.25s (removed 0.61s)
  - orig 5.76s, length 1.46s -> kept 0.25s (removed 1.21s)
  - orig 12.4s, length 1.2s -> kept 0.25s (removed 0.95s)
  - orig 25.44s, length 0.92s -> kept 0.25s (removed 0.67s)
  - orig 34.16s, length 1.98s -> kept 0.25s (removed 1.73s)
  - no borderline cuts
- **cleaned_s3**:
  - orig 0.98s, length 1.1s -> kept 0.25s (removed 0.85s)
  - orig 8.5s, length 0.78s -> kept 0.25s (removed 0.53s)
  - orig 17.9s, length 1.16s -> kept 0.25s (removed 0.91s)
  - RISK NOTE: borderline pause 0.78s at orig ~8.50s (within 0.10s of the 0.75s threshold)
- **cleaned_s4**:
  - orig 1.14s, length 1.26s -> kept 0.25s (removed 1.01s)
  - no borderline cuts

## Notes

- Risky-cut entries are borderline pauses within 0.10 s of the 0.75 s threshold; speech samples are never cut (0.25 s always retained + crossfade), these only flag small VAD-margin cases for review.
- s01 remains the quiet/off-mic take: its integrated loudness before cleanup was -31.4 LUFS; two-pass loudnorm brings it to -17.4 LUFS (linear mode limits gain to avoid amplifying room noise). Word-level kinetic typography still avoids its uncertain spans (see timeline.json).
- No intermediate MP3 re-encodes: WAV PCM throughout, one MP3 encode per stem.