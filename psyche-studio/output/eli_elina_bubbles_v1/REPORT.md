# Eli–Elina bubbles and mouth test — v1

## Recovery and scope

- Branch: `arena/988cf418-elina-radman`.
- Render/source checkpoint: `ce9cda1690921d015ad624305529a871dfedfcf8`.
- The approved cut/zoom edit list was copied without changes; an automated comparison confirmed the `EDIT` blocks in the new and approved compositions are identical. This is a **12-second visual test**, not a replacement for the approved cutzoom and not the final dialogue assembly.
- The earlier checkout began clean at `ba728380` and did not contain the previous uncommitted mouth-test files. The remote project branch was at `235c673`; it was safely fast-forwarded. No project process or recent project log was running/present. Why the earlier workspace was absent is **unknown**.
- No file under `.github/workflows/` was changed. The approved `eli_elina_cutzoom_v1.mp4` and `eli_elina_test01` were not overwritten.

## Deliverables

- `eli_elina_bubbles_v1.mp4` — silent 12-second H.264 test.
- `CONTACT_SHEET.png` — nine labelled storyboard samples, including the phone insert and both chunks of Eli's long reaction.
- `MOUTH_COMPARISONS.png` — close comparisons of closed, small-open, and open states on Eli's curious pose and Elina's neutral pose.

## Visual implementation

- Existing dialogue cue text and provisional timings are read from `psyche-studio/remotion/src/eli/cues_test01.json`; no text was reshaped. The bundled Vazirmatn font and browser-native Persian RTL layout are used.
- Bubbles use off-white `#FFF7EC`, coral borders, soft shadows, and short matching tails. Eli's bubbles sit upper/right; Elina's sit upper/left. They enter over four frames (about 133 ms), then hold without wobble. No speaker-name labels or duplicated bottom subtitles are present.
- Eli's long reaction is split into two readable chunks; the existing `همین؟!` reaction graphic remains and pairs with the first bubble chunk. The phone keeps the `«باشه»` UI text unobstructed; a compact no-tail caption is placed below the phone for the off-screen spoken cue.
- Mouth test: inline, mouth-only SVG overlays on existing pose art. The closed source mouth is left untouched; small/open states are shown only while the corresponding character is the active speaker. There are no whole-face, head, chair, or body animation transforms added. Existing camera punch-ins and pose cross-fades remain as before.
- This is **2-frame/3-state mouth animation, not true lip-sync**. The silent cue timing uses held, deterministic three-state cycles with short closed holds at punctuation; it is not phoneme-accurate or audio-synchronized.
- The excited Eli pose already has a large open grin. The prior two mouth-only AI-edit attempts for a clean closed version did not produce an identity/style-stable repair, so that patch was omitted: the approved excited grin remains static rather than showing a visibly broken patch. Eli's curious/suspicious and Elina's neutral/concerned poses carry the test overlays.

## Mouth bounds and methods

Coordinates are approximate source-image pixel bounds at 1080×1920. The overlays are positioned in the scaled scene and therefore follow the unchanged camera transform.

| Character / pose | Source region / placement | Method |
|---|---|---|
| Eli — curious | Smile centered near source `(556, 953)`; approximate line bounds `x≈503–596, y≈941–964`. In the composition this maps near `(267, 726)`. | Transparent SVG dark opening, 3 states; small/open sizes are about `31×9` / `38×14` scene px. No face patch. |
| Eli — suspicious | Smile centered near source `(556, 953)`; pose-specific curvature retained. | Same mouth-only SVG states; no movement outside the mouth. |
| Eli — excited | Original grin bounds approximately `x≈477–599, y≈934–999`. | Unedited approved pose; no closed patch because the two mouth-only repair attempts were rejected. |
| Elina — neutral | Original lip bounds approximately `x≈513–584, y≈474–491`; overlay center maps near scene `(601, 556)`. | Subtle curved SVG opening, small/open about `38×5` / `48×9` scene px. Original facial pixels outside the mouth remain untouched. |
| Elina — concerned | Pose-specific overlay center near scene `(594, 556)`. | Same restrained SVG method; original pose retained. |

## QA results

- **Video:** 12.00 s; 360 frames; 1080×1920; 30 fps; H.264 High; `yuv420p`; no audio stream. Full FFmpeg decode completed with no errors.
- **Audio inventory:** none of the five requested TTS files (`eli_1_excited`, `eli_2_defensive`, `eli_3_soft`, `elina_1_concerned`, `elina_2_guide`) were found. No project audio file was present in the nearby project content/output folders. No TTS or music was generated; cues remain provisional and silent.
- **Persian/overlap:** inspected full-resolution stills and the labelled sheet. Persian shaping is connected and readable; bubbles fit within the frame, no visible face/eye/hair overlap was found, and the phone message remains unobstructed. The phone caption is outside the phone UI.
- **Silent-mouth comparison:** compared output ROIs to the approved cutzoom at frame 12 (Elina silent) and frame 348 (Eli silent). RGB per-channel MAE / RMS were respectively **2.678 / 3.246** and **2.743 / 3.278** on 8-bit values; the small residual is consistent with H.264/color-range re-encoding. No mouth overlay is active for either silent character in these samples.
- **Camera/body motion:** the approved `EDIT` block is byte-for-byte identical. No body/head/chair bounce or vibration was added; only the inherited camera punch-ins and pose cross-fades remain.
- **Prior output unchanged:** the cutzoom MP4 SHA-256 remains `c4b237dfad7b5e42995c890d6122efc3194357d26b43d5cf0b4a82760f7d0377`; its keyframe sheet remains `bb1c72b3052c0b5ace7ac9e99f9711e3b86b1736948b6d89896050b7e848dc70`.
- Moving playback was **not watched** in this interface; QA used individual decoded frames, the contact sheets, stream metadata, and a complete decode check. Still frames cannot prove perceived mouth smoothness during playback.

## Remaining limitations

- Cues have no uploaded voice tracks, so bubble and mouth timing is a provisional silent prototype, not final dialogue alignment.
- The excited Eli open grin remains static; only poses with stable mouth-only overlays are animated. A new identity-stable closed patch for that pose would need a new approved approach before any final edit.
- The mouth shapes are deliberately sparse cartoon flaps. They are not true phoneme lip-sync.
