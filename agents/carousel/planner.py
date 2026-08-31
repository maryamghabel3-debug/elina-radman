"""
AI carousel planner (M18C).

Given a topic (and optionally an image), Elina writes the Persian carousel
content herself and returns a fully validated CarouselDeck plus caption and
hashtags. Uses the existing LLMRouter (multi-provider fallback) and, when
configured, a soft Gemini image-description attempt for visual context.

Editorial rules from Brand Book V2 / Voice & Tone V2 / Content Safety V2
are encoded in the prompt; structural rules (cover first, exactly one cta
last, per-type text limits) are enforced by reusing the M18A/M18B deck
validation, with a single JSON repair retry when the model output is
broken.

No Telegram wiring, no publishing, no new dependencies.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from agents.carousel.brand_theme import TEMPLATES
from agents.carousel.deck_renderer import (
    CarouselDeck,
    parse_carousel_deck,
    _validate_deck_instance,
)
from agents.carousel.schema import (
    DEFAULT_TEMPLATE,
    SUPPORTED_SLIDE_TYPES,
    TEXT_LIMITS,
    CarouselConfigError,
    parse_carousel_slide,
)

logger = logging.getLogger(__name__)

# Typed planner error codes
CAROUSEL_PLAN_CONFIG_INVALID = "CAROUSEL_PLAN_CONFIG_INVALID"
CAROUSEL_PLAN_GENERATION_FAILED = "CAROUSEL_PLAN_GENERATION_FAILED"

SUPPORTED_GOALS = ("save_and_share", "follow", "reflect")
MIN_SLIDES = 3
MAX_SLIDES = 10
MAX_TOPIC_CHARS = 300

# From CONTENT-SAFETY-GUIDELINES-V2 section 5 (forbidden phrases)
_FORBIDDEN_PHRASES = (
    "تو قطعاً [اختلال] داری", "فقط مثبت فکر کن", "همه چیز درست می‌شود",
    "تو قوی هستی", "تو کافی هستی", "انرژی مثبت", "قانون جذب",
    "قربانی نباش", "بخشش کن تا شفا پیدا کنی", "معجزه شفا", "درمان قطعی",
    "تراپیست دیجیتال", "روان‌شناس AI", "درمانگر هوش مصنوعی",
)
# Clinical terms that require precise contextual explanation
_SENSITIVE_TERMS = (
    "PTSD", "اضطراب", "افسردگی", "تروما", "trauma bond",
    "gaslighting", "codependency", "inner child", "شخصیت مرزی", "خودشیفتگی",
)


class CarouselPlanError(Exception):
    """Base class for typed planner errors."""

    code: str = CAROUSEL_PLAN_CONFIG_INVALID

    def __init__(self, detail: str = ""):
        self.detail = detail
        super().__init__(f"{self.code}: {detail}" if detail else self.code)


class CarouselPlanConfigError(CarouselPlanError):
    code = CAROUSEL_PLAN_CONFIG_INVALID


class CarouselPlanGenerationError(CarouselPlanError):
    code = CAROUSEL_PLAN_GENERATION_FAILED


@dataclass
class CarouselPlanResult:
    """A validated deck plus the generated caption/hashtags and provenance."""

    deck: CarouselDeck
    caption: str
    hashtags: List[str] = field(default_factory=list)
    image_description: Optional[str] = None
    provider_used: Optional[str] = None


_GOAL_INSTRUCTIONS = {
    "save_and_share": (
        "نوع CTA: دعوت آرام به ذخیره و ارسال — مثلاً «این اسلایدها را ذخیره کن» "
        "یا «برای آن‌که نیاز دارد بشنود، بفرست»."
    ),
    "follow": (
        "نوع CTA: دعوت ملایم به دنبال‌کردن برای ادامه‌ی موضوع — "
        "بدون فشار یا وعده‌ی اغراق‌آمیز."
    ),
    "reflect": (
        "نوع CTA: یک سؤال آرام و باز برای تأمل در ذهن مخاطب — "
        "دعوت مستقیم به عمل نباشد."
    ),
}


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences if the model wrapped the JSON."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _extract_json_object(text: str) -> str:
    """Best-effort extraction of the first {...} block from model output."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


class CarouselPlanner:
    """Plans a complete branded Persian carousel deck from a topic."""

    def __init__(self, router=None):
        # Dependency-injected for testability; defaults to the real router.
        if router is None:
            from agents.llm_router import LLMRouter
            router = LLMRouter()
        self.router = router

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(
        self,
        topic: str,
        slide_count: int = 6,
        template: str = DEFAULT_TEMPLATE,
        image_path: Optional[str] = None,
        image_description: Optional[str] = None,
        goal: str = "save_and_share",
        language: str = "fa",
    ) -> CarouselPlanResult:
        """
        Generate a validated CarouselDeck (plus caption/hashtags) for the
        given topic. See module docstring for the editorial contract.
        """
        self._validate_inputs(topic, slide_count, template, goal, language, image_path)

        # B. Optional image understanding (soft: never fails the plan)
        description = image_description
        if not description and image_path:
            description = self._describe_image(image_path)

        # C + D. LLM call with a single repair retry
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            topic.strip(), slide_count, goal, description, image_path is not None
        )

        result = self._llm_call(user_prompt, system_prompt, language)
        raw = result.get("response", "")
        provider = result.get("provider", "")
        if not raw.strip():
            raise CarouselPlanGenerationError(
                "no LLM provider returned content (attempts: "
                f"{result.get('attempts', [])})"
            )

        data, error = self._parse_and_validate(raw, slide_count)
        if data is None:
            logger.warning("Planner JSON repair needed: %s", error)
            repair_prompt = (
                f"پاسخ قبلی نامعتبر بود. خطا: {error}\n"
                "فقط JSON اصلاح‌شده و کامل را برگردان."
            )
            result = self._llm_call(repair_prompt, system_prompt, language)
            raw = result.get("response", "")
            provider = result.get("provider", provider)
            if not raw.strip():
                raise CarouselPlanGenerationError(
                    "repair attempt returned no content "
                    f"(original error: {error})"
                )
            data, error = self._parse_and_validate(raw, slide_count)
            if data is None:
                raise CarouselPlanGenerationError(
                    f"deck generation failed after repair attempt: {error}"
                )

        # E. Deck assembly + final validation (same gate the deck renderer uses)
        deck = self._assemble_deck(data, template, image_path)
        return CarouselPlanResult(
            deck=deck,
            caption=(data.get("caption") or "").strip(),
            hashtags=[h for h in (data.get("hashtags") or []) if isinstance(h, str) and h.strip()],
            image_description=description,
            provider_used=provider,
        )

    # ------------------------------------------------------------------
    # Input validation (A)
    # ------------------------------------------------------------------

    def _validate_inputs(self, topic, slide_count, template, goal, language, image_path):
        if not isinstance(topic, str) or not topic.strip():
            raise CarouselPlanConfigError("topic must be a non-empty string")
        if len(topic.strip()) > MAX_TOPIC_CHARS:
            raise CarouselPlanConfigError(
                f"topic is {len(topic.strip())} chars; maximum is {MAX_TOPIC_CHARS}"
            )
        if not isinstance(slide_count, int) or isinstance(slide_count, bool) or not (MIN_SLIDES <= slide_count <= MAX_SLIDES):
            raise CarouselPlanConfigError(
                f"slide_count must be an integer between {MIN_SLIDES} and {MAX_SLIDES} (got {slide_count!r})"
            )
        if not isinstance(template, str) or template not in TEMPLATES:
            raise CarouselPlanConfigError(
                f"template '{template}' is not supported (use one of {sorted(TEMPLATES)})"
            )
        if goal not in SUPPORTED_GOALS:
            raise CarouselPlanConfigError(
                f"goal '{goal}' is not supported (use one of {list(SUPPORTED_GOALS)})"
            )
        if language != "fa":
            raise CarouselPlanConfigError(
                f"language '{language}' is not supported (public text is Persian-only)"
            )
        if image_path is not None:
            if not isinstance(image_path, str) or not os.path.exists(image_path):
                raise CarouselPlanConfigError(
                    f"image_path does not exist: {image_path!r}"
                )

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def _llm_call(self, prompt: str, system_prompt: str, language: str) -> Dict[str, Any]:
        res = self.router.smart_generate(
            prompt,
            task_type="creative_writing",
            system_prompt=system_prompt,
            language=language,
        )
        return res if isinstance(res, dict) else {"provider": "", "response": ""}

    def _build_system_prompt(self) -> str:
        limits = ", ".join(
            f"{t}: title≤{l.get('title', 0)}"
            + (f"/body≤{l['body']}" if l.get("body") else "")
            + (f"/bullet≤{l['bullet']}" if l.get("bullet") else "")
            for t, l in TEXT_LIMITS.items()
        )
        forbidden = "، ".join(f"«{p}»" for p in _FORBIDDEN_PHRASES)
        sensitive = "، ".join(_SENSITIVE_TERMS)
        return f"""تو «الینا رادمان»، نویسنده‌ی محتوای روان‌شناختی-عینی برای اینستاگرامی فارسی‌زبان هستی.
مأموریتت: نوشتن محتوای یک کاروسل از موضوع داده‌شده.

قانون اصلی صدا:
- «تو» برای احساس، لحن غیرشخصی برای تحلیل.
- لحن صمیم، عمیق روان‌شناختی و آرام؛ نه واعظانه، نه کلیشه‌ی انگیزشی، نه clickbait.

قواعد ویرایشی:
- همه‌ی متن‌های عمومی صرفاً فارسی باشد.
- عنوان کاور: هوک قوی، حداکثر {TEXT_LIMITS['cover']['title']} نویسه، بدون ایموجی.
- متن‌ها برای موبایل کوتاه و خوانا؛ حتماً این سقف‌ها را رعایت کن: {limits}
- bullets: بین ۲ تا ۵ مورد، هر کدام کوتاه.
- slide_type اول حتماً cover و آخرین slide حتماً cta باشد؛ دقیقاً یک cta.
- متن اسلاید quote داخل «...» بگذار.
- caption: ۲ تا ۴ پاراگراف کوتاه فارسی + یک دعوت آرام در پایان.
- hashtags: ۵ تا ۱۰ تگ، ترکیب فارسی و انگلیسی، مرتبط، بدون تگ اسپمی.

ممنوعات (از CONTENT-SAFETY-GUIDELINES-V2):
- ادعای پزشکی یا بالینی، زبان تشخیصی، یا وعده‌ی درمان — مطلقاً نه.
- عبارات ممنوع مطلق: {forbidden}
- واژه‌های بالینی ({sensitive}) فقط در صورت توضیح دقیق و بافت مناسب؛ در غیر این صورت از آن‌ها اجتناب کن.

خروجی:
- فقط یک JSON معتبر و کامل، بدون markdown، بدون متن اضافه، بدون کامنت.
"""

    def _build_user_prompt(
        self,
        topic: str,
        slide_count: int,
        goal: str,
        image_description: Optional[str],
        has_image: bool,
    ) -> str:
        parts = [
            f"موضوع کاروسل: {topic}",
            f"تعداد دقیق اسلایدها: {slide_count} (اول cover، آخر cta)",
            _GOAL_INSTRUCTIONS[goal],
        ]
        if image_description:
            parts.append(
                "تصویر منبع برای اسلاید کاور موجود است. توضیح تصویر: "
                f"{image_description}\n"
                "اگر تعداد اسلایدها اجازه می‌دهد (>= 6)، می‌توانی یک اسلاید "
                "image_text هم بنویسی که با این تصویر همخوانی داشته باشد."
            )
        elif has_image:
            parts.append(
                "تصویر منبع برای اسلاید کاور موجود است (بدون توضیح جزئی). "
                "محتوای اسلایدها را متناسق با یک تصویر عمومی بنویس."
            )
        else:
            parts.append(
                "تصویر منبعی وجود ندارد؛ از slide_type image_text استفاده نکن."
            )
        parts.append("حالا فقط JSON نهایی را برگردان.")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # JSON parsing + validation (D)
    # ------------------------------------------------------------------

    def _parse_and_validate(self, raw: str, slide_count: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Return (data, None) on success or (None, error_message) on failure."""
        text = _strip_code_fences(raw or "")
        if not text:
            return None, "empty model response"

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                data = json.loads(_extract_json_object(text))
            except json.JSONDecodeError as exc:
                return None, f"output is not valid JSON: {exc}"

        if not isinstance(data, dict):
            return None, "JSON root must be an object"

        deck_title = data.get("deck_title")
        if not isinstance(deck_title, str) or not deck_title.strip():
            return None, "'deck_title' must be a non-empty string"

        slides = data.get("slides")
        if not isinstance(slides, list):
            return None, "'slides' must be a list"
        if len(slides) != slide_count:
            return None, f"expected exactly {slide_count} slides, got {len(slides)}"

        # Order enforcement: cover first, exactly one cta last (reorder when
        # possible, error otherwise — the repair loop can then fix it).
        covers = [i for i, s in enumerate(slides) if isinstance(s, dict) and s.get("slide_type") == "cover"]
        ctas = [i for i, s in enumerate(slides) if isinstance(s, dict) and s.get("slide_type") == "cta"]
        if len(covers) != 1:
            return None, f"exactly one cover slide is required (got {len(covers)})"
        if len(ctas) != 1:
            return None, f"exactly one cta slide is required (got {len(ctas)})"
        if covers[0] != 0:
            slides.insert(0, slides.pop(covers[0]))
            ctas = [i for i, s in enumerate(slides) if s.get("slide_type") == "cta"]
        if ctas[0] != len(slides) - 1:
            slides.append(slides.pop(ctas[0]))

        for i, s in enumerate(slides):
            if not isinstance(s, dict):
                return None, f"slide {i + 1} must be an object"
            stype = s.get("slide_type")
            if stype not in SUPPORTED_SLIDE_TYPES:
                return None, f"slide {i + 1} has unsupported slide_type '{stype}'"
            title = s.get("title")
            if not isinstance(title, str) or not title.strip():
                return None, f"slide {i + 1} ({stype}) requires a non-empty title"
            try:
                parse_carousel_slide(s)
            except CarouselConfigError as exc:
                return None, f"slide {i + 1} ({stype}): {exc.detail}"

        return data, None

    # ------------------------------------------------------------------
    # Deck assembly (E)
    # ------------------------------------------------------------------

    def _assemble_deck(
        self,
        data: Dict[str, Any],
        template: str,
        image_path: Optional[str],
    ) -> CarouselDeck:
        slides = [
            parse_carousel_slide(s)
            for s in data["slides"]
        ]
        # Inject the source image into the cover (and any image_text slide
        # the model produced for it).
        if image_path:
            for s in slides:
                if s.slide_type in ("cover", "image_text"):
                    s.image_path = image_path

        deck = CarouselDeck(
            title=data["deck_title"].strip(),
            template=template,
            slides=slides,
        )
        # Final gate: the same validation the deck renderer applies.
        _validate_deck_instance(deck)
        # Full parse-path validation (child slides + deck rules) on the
        # assembled deck, so nothing partially valid escapes silently.
        parse_carousel_deck({
            "title": deck.title,
            "template": deck.template,
            "slides": [
                {
                    "slide_type": s.slide_type,
                    "title": s.title,
                    "body": s.body,
                    "bullets": s.bullets,
                    "image_path": s.image_path,
                    "eyebrow": s.eyebrow,
                    "footer": s.footer,
                    "template": s.template,
                    "accent": s.accent,
                    "slide_number": s.slide_number,
                }
                for s in slides
            ],
        })
        return deck

    # ------------------------------------------------------------------
    # Soft image description (B)
    # ------------------------------------------------------------------

    def _describe_image(self, image_path: str) -> Optional[str]:
        """
        Best-effort image description via Gemini (when configured).
        Soft by design: ANY failure (no key, network, SDK) returns None and
        the plan proceeds without image context.
        """
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            logger.info("No GEMINI_API_KEY configured; proceeding without image description")
            return None
        try:
            from google import genai
            ext = os.path.splitext(image_path)[1].lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    "توضیح مختصر این تصویر را در ۲ تا  جمله‌ی فارسی بنویس: "
                    "جوّ کلی، پالت رنگ، عناصر بصری اصلی و لحن عاطفی. "
                    "فقط توضیح را برگردان.",
                    {"mime_type": mime, "data": image_bytes},
                ],
            )
            text = (getattr(resp, "text", "") or "").strip()
            return text or None
        except Exception as exc:
            logger.warning("Image description failed (continuing without image context): %s", exc)
            return None
