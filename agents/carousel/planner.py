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
from agents.carousel.character_assets import CharacterAssetProvider
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
CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE = "CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE"

SUPPORTED_GOALS = ("save_and_share", "follow", "reflect")
SUPPORTED_MODES = ("ai_planned", "text_overlay", "image_deck")
# Character hint used when enforcing character presence (ElinaOS universe)
_CHARACTER_HINT = "elina"
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


class CarouselCharacterAssetsError(CarouselPlanError):
    code = CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE


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
        topic: str = "",
        slide_count: int = 6,
        template: str = DEFAULT_TEMPLATE,
        image_path: Optional[str] = None,
        image_description: Optional[str] = None,
        goal: str = "save_and_share",
        language: str = "fa",
        mode: str = "ai_planned",
        image_paths: Optional[List[str]] = None,
        slide_texts: Optional[List[Dict[str, str]]] = None,
        character_asset_provider: Optional[CharacterAssetProvider] = None,
    ) -> CarouselPlanResult:
        """
        Generate a validated CarouselDeck (plus caption/hashtags).

        Modes:
        - "ai_planned" (default, M18C): topic -> LLM writes everything.
          When character_asset_provider is given, every content slide
          (except cta) must end up with a character visual (soft fallback:
          reuse the last successful image; CAROUSEL_CHARACTER_ASSETS_
          UNAVAILABLE only when nothing can be assigned at all).
        - "text_overlay" (M18C-UPDATE): user images + user texts, zipped in
          order; NO LLM call. Requires image_paths + slide_texts (same
          length, > 0). First image -> cover.
        - "image_deck" (M18C-UPDATE): user images + topic; the LLM writes
          exactly len(image_paths) slides, zipped with the images in order.

        See the module docstring for the editorial contract.
        """
        if mode not in SUPPORTED_MODES:
            raise CarouselPlanConfigError(
                f"mode '{mode}' is not supported (use one of {list(SUPPORTED_MODES)})"
            )
        if not isinstance(template, str) or template not in TEMPLATES:
            raise CarouselPlanConfigError(
                f"template '{template}' is not supported (use one of {sorted(TEMPLATES)})"
            )
        if language != "fa":
            raise CarouselPlanConfigError(
                f"language '{language}' is not supported (public text is Persian-only)"
            )

        if mode == "text_overlay":
            return self._plan_text_overlay(image_paths, slide_texts, template)
        if mode == "image_deck":
            return self._plan_image_deck(
                topic, template, goal, language, image_paths, image_description
            )
        return self._plan_ai_planned(
            topic, slide_count, template, image_path, image_description, goal,
            language, character_asset_provider,
        )

    # ------------------------------------------------------------------
    # MODE 3 (M18C + character presence): ai_planned
    # ------------------------------------------------------------------

    def _plan_ai_planned(
        self, topic, slide_count, template, image_path, image_description,
        goal, language, character_asset_provider,
    ) -> CarouselPlanResult:
        self._validate_inputs(topic, slide_count, template, goal, language, image_path)

        # B. Optional image understanding (soft: never fails the plan)
        description = image_description
        if not description and image_path:
            description = self._describe_image(image_path)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            topic.strip(), slide_count, goal, description, image_path is not None
        )
        data, provider = self._generate_deck_data(user_prompt, system_prompt, language, slide_count)

        # E. Deck assembly + final validation (same gate the deck renderer uses)
        deck = self._assemble_deck(data, template, image_path)

        # Character visual enforcement (only when a provider is supplied)
        if character_asset_provider is not None:
            self._enforce_character_presence(deck, template, character_asset_provider)

        return CarouselPlanResult(
            deck=deck,
            caption=(data.get("caption") or "").strip(),
            hashtags=[h for h in (data.get("hashtags") or []) if isinstance(h, str) and h.strip()],
            image_description=description,
            provider_used=provider,
        )

    # ------------------------------------------------------------------
    # MODE 2 (M18C-UPDATE): image_deck — user images, LLM writes the text
    # ------------------------------------------------------------------

    def _plan_image_deck(
        self, topic, template, goal, language, image_paths, image_description
    ) -> CarouselPlanResult:
        if not isinstance(topic, str) or not topic.strip():
            raise CarouselPlanConfigError("image_deck mode requires a non-empty topic")
        if len(topic.strip()) > MAX_TOPIC_CHARS:
            raise CarouselPlanConfigError(
                f"topic is {len(topic.strip())} chars; maximum is {MAX_TOPIC_CHARS}"
            )
        if goal not in SUPPORTED_GOALS:
            raise CarouselPlanConfigError(
                f"goal '{goal}' is not supported (use one of {list(SUPPORTED_GOALS)})"
            )
        paths = self._validate_image_paths(image_paths)
        slide_count = len(paths)  # forced: one slide per provided image
        if not (MIN_SLIDES <= slide_count <= MAX_SLIDES):
            raise CarouselPlanConfigError(
                f"image_deck needs {MIN_SLIDES}-{MAX_SLIDES} images "
                f"(got {slide_count} image_paths)"
            )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            topic.strip(), slide_count, goal, image_description,
            has_image=True, paired_images=True,
        )
        data, provider = self._generate_deck_data(user_prompt, system_prompt, language, slide_count)

        deck = self._assemble_deck(data, template, None)
        # Zip the generated text with the provided images, in order.
        # Image-bearing text slides get the full-bleed image_overlay layout
        # (M22) instead of the 65/35 image_text panel — unless an explicit
        # image_layout was set (M22A), which is preserved as-is.
        for slide, path in zip(deck.slides, paths):
            slide.image_path = path
            if slide.slide_type == "image_text" and slide.image_layout is None:
                slide.slide_type = "image_overlay"
        self._final_validate_deck(deck)

        return CarouselPlanResult(
            deck=deck,
            caption=(data.get("caption") or "").strip(),
            hashtags=[h for h in (data.get("hashtags") or []) if isinstance(h, str) and h.strip()],
            image_description=image_description,
            provider_used=provider,
        )

    # ------------------------------------------------------------------
    # MODE 1 (M18C-UPDATE): text_overlay — user images + user texts, no LLM
    # ------------------------------------------------------------------

    def _plan_text_overlay(
        self, image_paths, slide_texts, template
    ) -> CarouselPlanResult:
        paths = self._validate_image_paths(image_paths)
        if not isinstance(slide_texts, list) or len(slide_texts) != len(paths):
            raise CarouselPlanConfigError(
                f"text_overlay requires slide_texts with exactly one entry per image "
                f"({len(paths)} images, got "
                f"{len(slide_texts) if isinstance(slide_texts, list) else 'no list'})"
            )

        slides = []
        for i, (img, text) in enumerate(zip(paths, slide_texts)):
            if not isinstance(text, dict):
                raise CarouselPlanConfigError(f"slide_texts[{i}] must be a dictionary")
            title = text.get("title")
            if not isinstance(title, str) or not title.strip():
                raise CarouselPlanConfigError(
                    f"slide_texts[{i}] requires a non-empty title"
                )
            body = (text.get("body") or "").strip()
            eyebrow = (text.get("eyebrow") or "").strip()
            if i == 0:
                raw_slide = {
                    "slide_type": "cover",
                    "title": title.strip(),
                    "eyebrow": eyebrow,
                    "image_path": img,
                }
            else:
                # Non-cover slides always carry their paired image, so they
                # stay image_text with the photo-preserving "auto" layout
                # (M22A): full-bleed caption when the source is close to
                # 4:5, letterboxed contain otherwise. (title_body requires a
                # body and would silently drop the user's image.)
                raw_slide = {
                    "slide_type": "image_text",
                    "title": title.strip(),
                    "body": body,
                    "eyebrow": eyebrow,
                    "image_path": img,
                    "image_layout": "auto",
                }
            try:
                slides.append(parse_carousel_slide(raw_slide))
            except CarouselConfigError as exc:
                raise CarouselPlanConfigError(f"slide_texts[{i}]: {exc.detail}") from exc

        deck = CarouselDeck(title=slides[0].title, template=template, slides=slides)
        self._final_validate_deck(deck)
        return CarouselPlanResult(
            deck=deck,
            caption="",
            hashtags=[],
            image_description=None,
            provider_used=None,  # no LLM involved
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _validate_image_paths(self, image_paths) -> List[str]:
        if not isinstance(image_paths, list) or not image_paths:
            raise CarouselPlanConfigError("image_paths must be a non-empty list of paths")
        for p in image_paths:
            if not isinstance(p, str) or not os.path.exists(p):
                raise CarouselPlanConfigError(f"image_path does not exist: {p!r}")
        return image_paths

    def _generate_deck_data(
        self, user_prompt: str, system_prompt: str, language: str, slide_count: int
    ) -> Tuple[Dict[str, Any], str]:
        """C + D. LLM call with a single repair retry -> validated data dict."""
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
        return data, provider

    def _enforce_character_presence(
        self, deck: CarouselDeck, template: str, provider: CharacterAssetProvider
    ) -> None:
        """
        ai_planned rule: every content slide (except cta) must have a
        character visual.

        Soft fallback chain per slide: user image -> provider asset ->
        last successful image. Raises CAROUSEL_CHARACTER_ASSETS_UNAVAILABLE
        only when NO content slide ends up with an image.
        """
        last_image: Optional[str] = None
        for slide in deck.slides:
            if slide.image_path:
                last_image = slide.image_path

        for slide in deck.slides:
            if slide.slide_type == "cta":
                continue
            if slide.image_path:
                last_image = slide.image_path
                continue
            asset = None
            try:
                asset = provider.get_asset(
                    _CHARACTER_HINT, slide.title, slide.slide_type, template
                )
            except Exception as exc:
                # Providers must be soft; guard anyway so a buggy provider
                # cannot kill the plan.
                logger.warning(
                    "Character asset provider raised (treating as missing): %s", exc
                )
            if asset:
                slide.image_path = asset
                last_image = asset
            elif last_image:
                slide.image_path = last_image  # soft fallback: reuse previous

        if not any(s.image_path for s in deck.slides if s.slide_type != "cta"):
            raise CarouselCharacterAssetsError(
                "no character assets available for content slides "
                "(provider returned nothing and no fallback image exists)"
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
        paired_images: bool = False,
    ) -> str:
        parts = [
            f"موضوع کاروسل: {topic}",
            f"تعداد دقیق اسلایدها: {slide_count} (اول cover، آخر cta)",
            _GOAL_INSTRUCTIONS[goal],
        ]
        if paired_images:
            # image_deck mode: every slide will be paired (in order) with a
            # user-provided image; image_overlay slides use a placeholder path.
            parts.append(
                "برای این کاروسل به تعداد دقیقِ اسلایدها، تصویر از طرف کاربر "
                "و به همان ترتیب جفت می‌شود. برای هر اسلاید بعد از cover که "
                "متن آن باید روی تصویر دیده شود، slide_type=image_overlay را "
                "استفاده کن و image_path را دقیقاً مقدار pending بگذار "
                "(سیستم تصویر واقعی را جایگزین می‌کند). برای اسلایدهای بدون "
                "تصویر از title_body یا quote استفاده کن."
            )
            if image_description:
                parts.append(f"توضیح کلی تصاویر: {image_description}")
        elif image_description:
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
        self._final_validate_deck(deck)
        return deck

    def _final_validate_deck(self, deck: CarouselDeck) -> None:
        """Final gate: the same validation the deck renderer applies, plus
        a full parse-path pass so nothing partially valid escapes silently."""
        _validate_deck_instance(deck)
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
                    "image_layout": s.image_layout,
                    "eyebrow": s.eyebrow,
                    "footer": s.footer,
                    "template": s.template,
                    "accent": s.accent,
                    "slide_number": s.slide_number,
                }
                for s in deck.slides
            ],
        })

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
