# V3 Style Test — QA Report

All metrics objective (ffmpeg + numpy). No listening or subjective quality claims. Frames: `qa_<skin>_t<seconds>.jpg` (5 per video).

## Motion / container QA

| Metric | Paper-cut | Dark-glass |
|---|---:|---:|
| Duration (s) | 40.0 | 40.0 |
| Size (MiB) | 6.59 | 5.37 |
| Decode error lines | 0 | 0 |
| Frozen ratio (freezedetect) | 0.0 | 0.0 |
| Longest freeze (s) | 0.0 | 0.0 |
| Max event gap (s) | 1.15 | 1.15 |
| Mean event gap (s) | 0.905 | 0.905 |
| Exact word impact events | 3 | 3 |
| Key phrase events | 9 | 9 |

## Active layers (structural estimate)

- **papercut**: 7-9: paper sheets+grain, confetti floaters, progress chrome, dots, subtitle, phrase chip/cloud, word chips, paper phone (t<14.5s)
- **glass**: 8-10: gradient+grain, orange bloom, floor grid, center scrim, particles, RTL progress, dots, subtitle, glass panel, stamp text+glow

## Sync check (visual bump within ±3 frames, 30 fps)

- **papercut**: 22/22 reliable events synced -> PASS
- **glass**: 22/22 reliable events synced -> PASS

## Final-mix loudness (voice + procedural bed/SFX)

- **papercut**: I=-15.9 LUFS (target -14..-16), true peak=-2.1 dBTP (limit -1.5)
- **glass**: I=-15.9 LUFS (target -14..-16), true peak=-2.1 dBTP (limit -1.5)

## Visual verification (5 frames each)

- Persian text rendered via arabic-reshaper + python-bidi (never `direction='rtl'`): correct joined/shaped forms, no mirrored glyphs, question marks and ZWNJ intact.
- Safe zone: key text occupies y ~560-1260 (paper) / ~700-1050 (glass), inside the required 250-1500 band; subtitles sit at y≈1480 pill-free as specified.
- Panels are content-hugging (width measured from wrapped text + padding, capped at 84% frame width): no giant empty panels.
- Paper-cut shows cream paper, torn clouds, chips and the paper phone; glass shows the near-black gradient, orange bloom, floor grid, frosted panels and metallic stamp text. No brand handles.

## Event density
- 44 events in the 40 s window; max scheduled gap 1.15 s (requirement 0.8-1.2 s).
- Exact word impacts (3): «باشه»@7.689s, «کوتاه»@18.399s, «باشه.»@20.011s
- s01 weak-region rule: no exact word-level impact was emitted from the original 27-57.5 s off-mic span; those moments use phrase-level chips/visual metaphor only.