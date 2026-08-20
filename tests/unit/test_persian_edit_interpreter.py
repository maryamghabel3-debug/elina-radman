import pytest
from agents.editing.persian_edit_interpreter import (
    normalize_persian_text,
    persian_ordinal_to_int,
    PersianEditInterpreter,
    PersianEditPlan,
    PersianShotInstruction,
    PersianSFXInstruction,
    PersianMusicInstruction,
    format_plan_preview_fa
)

pytestmark = pytest.mark.unit


# 1. Persian digits normalize correctly
def test_persian_digits_normalization():
    assert normalize_persian_text("۱۲۳۴۵۶۷۸۹۰") == "1234567890"


# 2. Arabic digits normalize correctly
def test_arabic_digits_normalization():
    assert normalize_persian_text("١٢٣٤٥٦٧٨٩٠") == "1234567890"


# 3. Arabic ی/ک normalize correctly
def test_arabic_chars_normalization():
    assert normalize_persian_text("يك يک") == "یک یک"


# 4. Ordinal first through fifth parse correctly
def test_ordinal_parsing():
    assert persian_ordinal_to_int("اول") == 1
    assert persian_ordinal_to_int("دوم") == 2
    assert persian_ordinal_to_int("سوم") == 3
    assert persian_ordinal_to_int("چهارم") == 4
    assert persian_ordinal_to_int("پنجم") == 5


# 5. Parse "آخرین بسته"
def test_parse_latest_bundle_target():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("برنامه ادیت آخرین بسته:\nشات اول کامل باشد")
    assert plan.target_mode == "latest_bundle"


# 6. Parse explicit ELN-BUNDLE custom ID
def test_parse_explicit_eln_bundle_target():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("بسته ELN-BUNDLE-20260804-abcdef:\nشات اول کامل باشد")
    assert plan.target_mode == "custom_id"
    assert plan.target_custom_id == "ELN-BUNDLE-20260804-abcdef"


# 7. Parse mute-original-audio instruction
def test_parse_mute_original_audio():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات اول کامل باشد\nصدای اصلی قطع شود")
    assert plan.mute_original_audio is True


# 8. Parse keep-original-audio instruction
def test_parse_keep_original_audio():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات اول کامل باشد\nصدای اصلی بماند")
    assert plan.mute_original_audio is False


# 9. Parse five shot trim lines
def test_parse_five_shot_trim_lines():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse(
        "شات اول از 0 تا 2.8\n"
        "شات دوم از 1.2 تا 3.8\n"
        "شات سوم کامل باشد\n"
        "شات چهارم از 5 تا آخر\n"
        "شات پنجم حذف شود"
    )
    assert len(plan.shots) == 5
    assert plan.shots[0].shot_index == 1
    assert plan.shots[0].start_sec == 0.0
    assert plan.shots[0].end_sec == 2.8
    assert plan.shots[4].shot_index == 5
    assert plan.shots[4].remove is True


# 10. Parse "از ابتدا تا ۴"
def test_parse_from_beginning_to_num():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات اول از ابتدا تا 4")
    assert len(plan.shots) == 1
    assert plan.shots[0].start_sec == 0.0
    assert plan.shots[0].end_sec == 4.0


# 11. Parse "از ۲ تا آخر"
def test_parse_from_num_to_end():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات اول از 2 تا آخر")
    assert len(plan.shots) == 1
    assert plan.shots[0].start_sec == 2.0
    assert plan.shots[0].end_sec is None


# 12. Parse full clip instruction
def test_parse_full_clip_instruction():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("کلیپ دوم کامل باشد")
    assert len(plan.shots) == 1
    assert plan.shots[0].shot_index == 2
    assert plan.shots[0].start_sec == 0.0
    assert plan.shots[0].end_sec is None


# 13. Parse remove-shot instruction
def test_parse_remove_shot():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات سوم حذف شود")
    assert len(plan.shots) == 1
    assert plan.shots[0].shot_index == 3
    assert plan.shots[0].remove is True


# 14. Reject negative start time through validation
def test_validation_rejects_negative_start():
    plan = PersianEditPlan(
        shots=[PersianShotInstruction(shot_index=1, start_sec=-2.5)],
        confidence=1.0
    )
    errors = plan.validate()
    assert any("start_sec" in e or "negative" in e for e in errors)


# 15. Detect end <= start
def test_validation_detects_end_leq_start():
    plan = PersianEditPlan(
        shots=[PersianShotInstruction(shot_index=1, start_sec=4.0, end_sec=3.5)],
        confidence=1.0
    )
    errors = plan.validate()
    assert any("end_sec" in e or "greater" in e for e in errors)


# 16. Parse three timed SFX instructions
def test_parse_three_timed_sfx():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse(
        "شات اول کامل باشد\n"
        "در ثانیه 0.5 صدای کلید اضافه شود\n"
        "صدای مداد در ثانیه 4.2\n"
        "از ثانیه 10 صدای نفس آرام پخش شود"
    )
    assert len(plan.sound_effects) == 3
    assert plan.sound_effects[0].query_fa == "صدای کلید"
    assert plan.sound_effects[0].start_sec == 0.5
    assert plan.sound_effects[1].query_fa == "صدای مداد"
    assert plan.sound_effects[1].start_sec == 4.2
    assert plan.sound_effects[2].query_fa == "صدای نفس آرام"
    assert plan.sound_effects[2].start_sec == 10.0


# 17. Parse music disabled
def test_parse_music_disabled():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات اول کامل باشد\nموسیقی نمیخواهم")
    assert plan.music.enabled is False


# 18. Parse music requested
def test_parse_music_requested():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات اول کامل باشد\nیک موسیقی آرام و تاریک اضافه کن")
    assert plan.music.enabled is True
    assert plan.music.query_fa == "موسیقی آرام و تاریک"


# 19. Parse hook text
def test_parse_hook_text():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات اول کامل باشد\nهوک: برای دردهایی که دیده نمیشوند")
    assert plan.hook_text == "برای دردهایی که دیده نمیشوند"


# 20. Unknown sentence creates clarification question
def test_unknown_sentence_creates_clarification_question():
    interpreter = PersianEditInterpreter()
    plan = interpreter.parse("شات اول کامل باشد\nبعضی حرف‌ها ناگفته بماند")
    assert len(plan.clarification_questions) == 1
    assert "متوجه این دستور نشدم" in plan.clarification_questions[0]
    assert plan.confidence < 1.0


# 21. Missing shots creates clarification question
def test_missing_shots_creates_clarification_question():
    interpreter = PersianEditInterpreter()
    # No shots mentioned
    plan = interpreter.parse("صدای اصلی قطع شود\nموسیقی نمیخواهم")
    assert any("مشخص کن هر شات" in q for q in plan.clarification_questions)
    assert plan.confidence < 1.0


# 22. Preview is Persian and includes "هنوز اجرا نشده"
def test_preview_is_persian_and_includes_message():
    plan = PersianEditPlan(
        target_mode="latest_bundle",
        mute_original_audio=True,
        shots=[PersianShotInstruction(shot_index=1, start_sec=0.0, end_sec=2.8)],
        sound_effects=[PersianSFXInstruction(query_fa="صدای کلید", start_sec=0.5)],
        music=PersianMusicInstruction(enabled=False),
        hook_text="برای دردهایی که دیده نمی‌شوند",
        confidence=1.0
    )
    preview = format_plan_preview_fa(plan)
    assert "برداشت من از برنامه ادیت:" in preview
    assert "این برنامه هنوز اجرا نشده" in preview
    assert "آخرین بسته" in preview


# 23. Duplicate shot index fails validation
def test_validation_fails_on_duplicate_shot_index():
    plan = PersianEditPlan(
        shots=[
            PersianShotInstruction(shot_index=1, start_sec=0.0, end_sec=2.0),
            PersianShotInstruction(shot_index=1, start_sec=2.0, end_sec=4.0)
        ],
        confidence=1.0
    )
    errors = plan.validate()
    assert any("unique" in e or "duplicate" in e for e in errors)


# 24. Confidence is between 0 and 1
def test_validation_confidence_range():
    plan_low = PersianEditPlan(shots=[PersianShotInstruction(shot_index=1)], confidence=-0.1)
    plan_high = PersianEditPlan(shots=[PersianShotInstruction(shot_index=1)], confidence=1.2)
    plan_ok = PersianEditPlan(shots=[PersianShotInstruction(shot_index=1)], confidence=0.85)

    assert len(plan_low.validate()) > 0
    assert len(plan_high.validate()) > 0
    assert len(plan_ok.validate()) == 0


# 19. Music instructions carry explicit flag
def test_parse_music_explicit_flags():
    interpreter = PersianEditInterpreter()

    # Positive request -> explicit True, enabled True
    plan = interpreter.parse("شات اول کامل باشد\nیک موسیقی آرام و تاریک اضافه کن")
    assert plan.music.enabled is True
    assert plan.music.explicit is True

    # Explicit no-music -> explicit True, enabled False
    plan = interpreter.parse("شات اول کامل باشد\nموسیقی نمیخواهم")
    assert plan.music.enabled is False
    assert plan.music.explicit is True

    # No music mention at all -> explicit False
    plan = interpreter.parse("شات اول کامل باشد")
    assert plan.music.enabled is False
    assert plan.music.explicit is False
