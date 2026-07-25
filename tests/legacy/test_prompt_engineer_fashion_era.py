"""
Legacy Fashion-Era PromptEngineer Tests — ARCHIVED

این تست‌ها مربوط به عصر فشن پروژه هستند و رفتارهایی مانند
palette سلبریتی، styling ایرانی، quiet luxury tones و
متدهای pick_color_palette / *COLOR*PALETTES / extract_rich_styling_and_location
را انتظار داشتند.

این رفتارها طبق تصمیم قطعی پروژه از production حذف شده‌اند:

- Reference: docs/PROJECT-DEFINITION-V2.md
- Decision: D-001 — هویت روان‌شناختی-سینمایی (نه فشن)

این تست‌ها فقط برای مرجع تاریخی نگهداری می‌شوند و در CI اجرا نمی‌شوند.
جایگزین V2 آن‌ها در tests/unit/test_prompt_engineer_v2.py قرار دارد.
"""

import pytest
import os
import json

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skip(
        reason=(
            "Legacy fashion-era tests. Behavior intentionally removed in V2 "
            "per decision D-001 (psychology-cinematic identity). "
            "Kept for historical reference only. See docs/PROJECT-DEFINITION-V2.md."
        )
    ),
]

# ---- Archived tests below ----

def test_prompt_engineer_uses_palette(workdir):
    import json as _json

    os.makedirs("content", exist_ok=True)
    with open("content/trend_visuals.json", "w") as f:
        _json.dump(
            {"dominant_tones": ["cream/neutral", "camel"], "top_colors": ["#f5f0e8"]},
            f,
        )

    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    prompt = pe.generate_photo_prompt("in a cafe")
    assert "trending tones" in prompt
    assert "cream/neutral" in prompt

    # And it should be omittable
    plain = pe.generate_photo_prompt("in a cafe", use_trending_palette=False)
    assert "trending tones" not in plain

def test_prompt_engineer_uses_deep_signals(workdir):
    import json as _json

    os.makedirs("content", exist_ok=True)
    with open("content/trend_visuals.json", "w") as f:
        _json.dump(
            {
                "dominant_tones": ["cream/neutral"],
                "top_colors": ["#f5f0e8"],
                "trending_aesthetics": ["quiet luxury", "old money"],
                "trending_standout_products": ["camel wool trench coat"],
                "trending_camera_angles": ["low angle"],
                "sample_poses": ["walking away, glancing over shoulder"],
            },
            f,
        )

    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    prompt = pe.generate_photo_prompt("street style walk")
    # Deep reverse-engineered signals should surface in the prompt
    assert "quiet luxury" in prompt
    assert "camel wool trench coat" in prompt
    assert "low angle" in prompt


# --------------------------------------------------------------------------- #
# vision helper (offline: JSON extraction + no-key guard)
# --------------------------------------------------------------------------- #

def test_prompt_engineer_color_palette_is_not_always_neutral(workdir):
    """Regression test for a real bug: every single outfit/style_desc
    branch used to be hard-coded to cream/beige/ivory/camel with no code
    path that ever produced a different palette. Running many samples must
    show genuine variety, not the same neutral palette every time."""
    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    palette_keys = {pe.pick_color_palette("a casual outfit post")[0] for _ in range(60)}
    # With 60 samples across the weighted random.choices, we should see
    # more than just the single default "neutral_quiet_luxury" key.
    assert len(palette_keys) > 1
    assert "neutral_quiet_luxury" in palette_keys  # still her common default

def test_prompt_engineer_has_persian_inspired_palettes_available(workdir):
    """The new palette options must actually reference real Persian/Iranian
    color inspiration (tilework, carpets, rosewater aesthetics), not just
    be a generic 'colorful' catch-all."""
    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    palettes_text = " ".join(pe._COLOR_PALETTES.values()).lower()
    assert "persian" in palettes_text
    assert "turquoise" in palettes_text or "tilework" in palettes_text

def test_prompt_engineer_celebration_concepts_use_persian_palette(workdir):
    """Occasion/celebration-themed posts should lean into the Persian
    jewel-tone/rose palettes rather than defaulting to neutral quiet luxury
    every time."""
    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    for _ in range(20):
        key, _ = pe.pick_color_palette("celebration outfit for a festival")
        assert key != "neutral_quiet_luxury"

def test_prompt_engineer_outfit_sometimes_uses_iranian_styling(workdir):
    """extract_rich_styling_and_location must sometimes produce a bold/
    Persian-inspired outfit and location instead of ALWAYS defaulting to
    neutral camel/cream tones and a Parisian setting -- verified by
    checking that across many samples, at least one mentions a real
    Persian-inspired element (turquoise, Tehran, Persian tiled, manteau)."""
    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    found_bold_variant = False
    for _ in range(60):
        outfit, location, acc = pe.extract_rich_styling_and_location("petite trouser styling")
        combined = f"{outfit} {location} {acc}".lower()
        if "persian" in combined or "tehran" in combined:
            found_bold_variant = True
            break
    assert found_bold_variant

