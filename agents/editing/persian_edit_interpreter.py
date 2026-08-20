import os
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from agents.studio.bundle_ids import normalize_bundle_custom_id

logger = logging.getLogger(__name__)


@dataclass
class PersianShotInstruction:
    shot_index: int
    start_sec: float = 0.0
    end_sec: Optional[float] = None
    remove: bool = False


@dataclass
class PersianSFXInstruction:
    query_fa: str
    query_en: Optional[str] = None
    start_sec: float = 0.0
    gain_db: int = -8
    fade_in_sec: float = 0.1
    fade_out_sec: float = 0.3


@dataclass
class PersianMusicInstruction:
    enabled: bool = False
    query_fa: Optional[str] = None
    gain_db: int = -14
    loop: bool = True
    explicit: bool = False
    """True when the user actually mentioned music (positive or negative).
    Lets the pipeline distinguish 'بدون موسیقی' (explicit no-music) from a
    plan that never mentions music at all."""


@dataclass
class PersianEditPlan:
    target_mode: str = "latest_bundle"
    target_custom_id: Optional[str] = None
    mute_original_audio: bool = True
    shots: List[PersianShotInstruction] = field(default_factory=list)
    sound_effects: List[PersianSFXInstruction] = field(default_factory=list)
    music: PersianMusicInstruction = field(default_factory=PersianMusicInstruction)
    hook_text: Optional[str] = None
    clarification_questions: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def validate(self) -> List[str]:
        errors = []
        if self.target_mode not in ["latest_bundle", "custom_id"]:
            errors.append("target_mode must be 'latest_bundle' or 'custom_id'")
        if self.target_mode == "custom_id" and not self.target_custom_id:
            errors.append("target_custom_id is required when target_mode is 'custom_id'")

        if not self.shots:
            errors.append("At least one shot is required")

        shot_indices = []
        for shot in self.shots:
            if shot.shot_index < 1:
                errors.append(f"shot_index must be >= 1, got {shot.shot_index}")
            if shot.shot_index in shot_indices:
                errors.append(f"shot_index {shot.shot_index} must be unique")
            else:
                shot_indices.append(shot.shot_index)

            if shot.start_sec < 0:
                errors.append(f"start_sec cannot be negative, got {shot.start_sec}")
            if shot.end_sec is not None and shot.end_sec <= shot.start_sec:
                errors.append(f"end_sec must be greater than start_sec: {shot.end_sec} <= {shot.start_sec}")

        for sfx in self.sound_effects:
            if sfx.start_sec < 0:
                errors.append(f"SFX start_sec cannot be negative, got {sfx.start_sec}")
            if not sfx.query_fa or not sfx.query_fa.strip():
                errors.append("SFX query_fa cannot be blank")

        if self.confidence < 0.0 or self.confidence > 1.0:
            errors.append(f"confidence must be between 0 and 1, got {self.confidence}")

        return errors


def normalize_persian_text(text: str) -> str:
    if not text:
        return ""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"

    trans_digits = str.maketrans(persian_digits + arabic_digits, english_digits + english_digits)
    text = text.translate(trans_digits)

    text = text.replace("ي", "ی")
    text = text.replace("ك", "ک")

    for char in ["\u200b", "\u200e", "\u200f", "\ufeff"]:
        text = text.replace(char, "")

    lines = text.splitlines()
    normalized_lines = []
    for line in lines:
        line = " ".join(line.split())
        normalized_lines.append(line)
    text = "\n".join(normalized_lines)

    return text


_persian_ordinal_map = {
    "اول": 1, "اولین": 1, "یک": 1, "یکم": 1, "نخست": 1, "۱": 1, "1": 1,
    "دوم": 2, "دومین": 2, "دو": 2, "۲": 2, "2": 2,
    "سوم": 3, "سومین": 3, "سه": 3, "۳": 3, "3": 3,
    "چهارم": 4, "چهارمین": 4, "چهار": 4, "۴": 4, "4": 4,
    "پنجم": 5, "پنجمین": 5, "پنج": 5, "۵": 5, "5": 5,
    "ششم": 6, "ششمین": 6, "شش": 6, "۶": 6, "6": 6,
    "هفتم": 7, "هفتمین": 7, "هفت": 7, "۷": 7, "7": 7,
    "هشتم": 8, "هشتمین": 8, "هشت": 8, "۸": 8, "8": 8,
    "نهم": 9, "نهمین": 9, "نه": 9, "۹": 9, "9": 9,
    "دهم": 10, "دهمین": 10, "ده": 10, "۱۰": 10, "10": 10,
    "یازدهم": 11, "یازدهمین": 11, "یازده": 11, "۱۱": 11, "11": 11,
    "دوازدهم": 12, "دوازدهمین": 12, "دوازده": 12, "۱۲": 12, "12": 12,
    "سیزدهم": 13, "سیزدهمین": 13, "سیزده": 13, "۱۳": 13, "13": 13,
    "چهاردهم": 14, "چهاردهمین": 14, "چهارده": 14, "۱۴": 14, "14": 14,
    "پانزدهم": 15, "پانزدهمین": 15, "پانزده": 15, "۱۵": 15, "15": 15,
    "شانزدهم": 16, "شانزدهمین": 16, "شانزده": 16, "۱۶": 16, "16": 16,
    "هفدهم": 17, "هفدهمین": 17, "هفده": 17, "۱۷": 17, "17": 17,
    "هجدهم": 18, "هجدهمین": 18, "هجده": 18, "۱۸": 18, "18": 18,
    "نوزدهم": 19, "نوزدهمین": 19, "نوزده": 19, "۱۹": 19, "19": 19,
    "بیستم": 20, "بیستمین": 20, "بیست": 20, "۲۰": 20, "20": 20,
}


def persian_ordinal_to_int(value: str) -> Optional[int]:
    if not value:
        return None
    val = value.strip().lower()

    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    trans_digits = str.maketrans(persian_digits + arabic_digits, english_digits + english_digits)
    val = val.translate(trans_digits)

    if val in _persian_ordinal_map:
        return _persian_ordinal_map[val]

    if val.isdigit():
        return int(val)

    return None


def extract_float(value: str) -> Optional[float]:
    match = re.search(r"[-+]?\d*\.\d+|\d+", value)
    if match:
        return float(match.group())
    return None


def parse_sfx_line(line_norm: str) -> Optional[PersianSFXInstruction]:
    if "صدا" not in line_norm and "افکت" not in line_norm:
        return None
    if "صدای اصلی" in line_norm or "صدای خود ویدیو" in line_norm or "صدای شات" in line_norm:
        return None

    start_sec = 0.0
    num_match = re.search(r"(?:ثانیه\s*)?([-+]?\d*\.\d+|\d+)", line_norm)
    if num_match:
        start_sec = float(num_match.group(1))

    query_match = re.search(r"صدای\s+([^\d\s]+(?:\s+[^\d\s]+)?)", line_norm)
    if query_match:
        query_fa = "صدای " + query_match.group(1).strip()
    else:
        query_fa = "صدای افکت"

    for stop_word in ["اضافه", "پخش", "شود", "در", "از"]:
        if query_fa.endswith(" " + stop_word):
            query_fa = query_fa[:-len(stop_word)-1].strip()
        elif query_fa.startswith(stop_word + " "):
            query_fa = query_fa[len(stop_word)+1:].strip()

    return PersianSFXInstruction(query_fa=query_fa, start_sec=start_sec)


class EditPlanLanguageProvider:
    def interpret(self, text: str) -> dict:
        raise NotImplementedError


class PersianEditInterpreter:

    def parse(self, text: str) -> PersianEditPlan:
        text_norm = normalize_persian_text(text)
        lines = text_norm.splitlines()

        target_mode = "latest_bundle"
        target_custom_id = None
        mute_original_audio = True
        shots = []
        sound_effects = []
        music = PersianMusicInstruction(enabled=False)
        hook_text = None
        clarification_questions = []
        confidence = 1.0

        for raw_line in lines:
            line_norm = raw_line.strip()
            if not line_norm or line_norm.startswith("برنامه ادیت") or line_norm.startswith("برداشت من"):
                continue

            matched = False

            # 1. Target
            if "آخرین بسته" in line_norm:
                target_mode = "latest_bundle"
                matched = True
            elif "بسته ELN-BUNDLE-" in line_norm or "پروژه ELN-BUNDLE-" in line_norm:
                target_mode = "custom_id"
                match = re.search(r"ELN-BUNDLE-[A-Za-z0-9_-]+", line_norm)
                if match:
                    target_custom_id = normalize_bundle_custom_id(match.group())
                matched = True

            # 2. Original Audio
            if any(phrase in line_norm for phrase in ["صدای اصلی قطع شود", "صدای خود ویدیوها را حذف کن", "صدای شات‌ها بی‌صدا شود", "صدای اصلی حذف شود"]):
                mute_original_audio = True
                matched = True
            elif "صدای اصلی بماند" in line_norm or "صدای خود ویدیوها بماند" in line_norm:
                mute_original_audio = False
                matched = True

            # 3. Hook
            if line_norm.startswith("هوک:") or line_norm.startswith("هوک :"):
                hook_text = line_norm.partition("هوک")[2].replace(":", "").strip()
                matched = True
            elif "متن اول ویدیو:" in line_norm or "متن اول ویدیو :" in line_norm:
                hook_text = line_norm.partition("متن اول ویدیو")[2].replace(":", "").strip()
                matched = True

            # 4. Music
            if "موسیقی" in line_norm or "موزیک" in line_norm or "آهنگ" in line_norm:
                if any(word in line_norm for word in ["نمیخواهم", "نمی‌خواهم", "نمی خواهم", "بدون", "حذف", "نه", "قطع"]):
                    music = PersianMusicInstruction(enabled=False, explicit=True)
                else:
                    query_fa = "موسیقی آرام"
                    for kw in ["موسیقی", "موزیک", "آهنگ"]:
                        if kw in line_norm:
                            query_fa = line_norm[line_norm.index(kw):].strip()
                            break
                    for stop_word in ["اضافه کن", "اضافه", "کن", "پخش", "بگذار", "شود"]:
                        if query_fa.endswith(" " + stop_word):
                            query_fa = query_fa[:-len(stop_word)-1].strip()
                        elif query_fa.endswith(stop_word):
                            query_fa = query_fa[:-len(stop_word)].strip()
                    music = PersianMusicInstruction(enabled=True, query_fa=query_fa, explicit=True)
                matched = True

            # 5. Shot trims (only if not already matched by music/audio/hook)
            if not matched:
                shot_match = re.search(r"(?:شات|ویدیو|ویدیوی|کلیپ)\s+([^\s]+)", line_norm)
                if shot_match:
                    ordinal_str = shot_match.group(1)
                    shot_idx = persian_ordinal_to_int(ordinal_str)
                    if shot_idx is not None:
                        if any(phrase in line_norm for phrase in ["حذف شود", "حذف کن", "حذف"]):
                            shots.append(PersianShotInstruction(shot_index=shot_idx, remove=True))
                        elif "کامل باشد" in line_norm or "کامل" in line_norm:
                            shots.append(PersianShotInstruction(shot_index=shot_idx, start_sec=0.0, end_sec=None))
                        else:
                            cleaned_line = line_norm.replace("ثانیه", "").replace("ثانیه‌ی", "").replace("ثانیه‌ های", "")
                            range_match = re.search(r"از\s+([^\s]+)\s+تا\s+([^\s]+)", cleaned_line)
                            if range_match:
                                start_str = range_match.group(1)
                                end_str = range_match.group(2)

                                if "ابتدا" in start_str or "صفر" in start_str or "0" in start_str:
                                    start_sec = 0.0
                                else:
                                    val = extract_float(start_str)
                                    start_sec = val if val is not None else 0.0

                                if "آخر" in end_str:
                                    end_sec = None
                                else:
                                    val = extract_float(end_str)
                                    end_sec = val if val is not None else None

                                shots.append(PersianShotInstruction(shot_index=shot_idx, start_sec=start_sec, end_sec=end_sec))
                            else:
                                shots.append(PersianShotInstruction(shot_index=shot_idx, start_sec=0.0, end_sec=None))
                        matched = True

            # 6. SFX (only if not already matched)
            if not matched:
                sfx_item = parse_sfx_line(line_norm)
                if sfx_item:
                    sound_effects.append(sfx_item)
                    matched = True

            if not matched:
                clarification_questions.append(f"متوجه این دستور نشدم: '{raw_line}'")
                confidence = max(0.0, confidence - 0.2)

        if not shots:
            clarification_questions.append("لطفاً مشخص کن هر شات از چه زمانی تا چه زمانی استفاده شود.")
            confidence = max(0.0, confidence - 0.5)

        plan = PersianEditPlan(
            target_mode=target_mode,
            target_custom_id=target_custom_id,
            mute_original_audio=mute_original_audio,
            shots=shots,
            sound_effects=sound_effects,
            music=music,
            hook_text=hook_text,
            clarification_questions=clarification_questions,
            confidence=round(confidence, 2)
        )
        return plan


def to_persian_digits(text: str) -> str:
    if not text:
        return ""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    trans = str.maketrans(english_digits, persian_digits)
    return text.translate(trans)


def format_sec(sec: float) -> str:
    if sec == int(sec):
        return str(int(sec))
    return str(sec)


def format_plan_preview_fa(plan: PersianEditPlan) -> str:
    dest = "آخرین بسته" if plan.target_mode == "latest_bundle" else (plan.target_custom_id or "نامشخص")
    audio_status = "قطع" if plan.mute_original_audio else "وصل"

    shot_lines = []
    for i, shot in enumerate(plan.shots):
        num_fa = to_persian_digits(str(i+1))
        shot_idx_fa = to_persian_digits(str(shot.shot_index))
        if shot.remove:
            line = f"{num_fa}) شات {shot_idx_fa}: حذف شود"
        else:
            start_fa = to_persian_digits(format_sec(shot.start_sec))
            if shot.end_sec is None:
                line = f"{num_fa}) شات {shot_idx_fa}: از {start_fa} تا آخر"
            else:
                end_fa = to_persian_digits(format_sec(shot.end_sec))
                line = f"{num_fa}) شات {shot_idx_fa}: از {start_fa} تا {end_fa} ثانیه"
        shot_lines.append(line)

    sfx_lines = []
    for sfx in plan.sound_effects:
        start_fa = to_persian_digits(format_sec(sfx.start_sec))
        sfx_lines.append(f"- {sfx.query_fa} در {start_fa} ثانیه")

    music_str = plan.music.query_fa if plan.music.enabled else "ندارد"
    hook_str = plan.hook_text if plan.hook_text else "ندارد"

    preview = (
        "برداشت من از برنامه ادیت:\n\n"
        f"مقصد: {dest}\n"
        f"صدای اصلی شات‌ها: {audio_status}\n\n"
        "شات‌ها:\n"
        + "\n".join(shot_lines) + "\n\n"
        "افکت‌های صوتی:\n"
        + ("\n".join(sfx_lines) if sfx_lines else "ندارد") + "\n\n"
        f"موسیقی: {music_str}\n"
        f"هوک: {hook_str}\n\n"
        "وضعیت:\n"
        "این برنامه هنوز اجرا نشده و به تأیید تو نیاز دارد."
    )

    if plan.clarification_questions:
        q_lines = [f"- {q}" for q in plan.clarification_questions]
        preview += "\n\nسؤال‌های لازم:\n" + "\n".join(q_lines)

    return preview
