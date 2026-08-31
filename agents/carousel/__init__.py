"""
ElinaOS Carousel Studio (M18A) — deterministic branded Persian static
carousel slides rendered with Pillow.

See docs/CAROUSEL-STUDIO-MVP.md for capabilities and limits.
"""

from agents.carousel.schema import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    MIN_BULLETS,
    MAX_BULLETS,
    SUPPORTED_SLIDE_TYPES,
    SUPPORTED_TEMPLATES,
    TEXT_LIMITS,
    CAROUSEL_SLIDE_CONFIG_INVALID,
    CAROUSEL_IMAGE_NOT_FOUND,
    CAROUSEL_FONT_NOT_FOUND,
    CAROUSEL_TEXT_OVERFLOW,
    CAROUSEL_RENDER_FAILED,
    CarouselError,
    CarouselConfigError,
    CarouselImageError,
    CarouselFontError,
    CarouselTextOverflowError,
    CarouselRenderError,
    CarouselSlide,
    parse_carousel_slide,
)
from agents.carousel.brand_theme import PALETTE, TEMPLATES, TemplateTheme, get_template, hex_to_rgb, palette_rgb
from agents.carousel.slide_renderer import CarouselSlideRenderer

__all__ = [
    "CANVAS_WIDTH",
    "CANVAS_HEIGHT",
    "SUPPORTED_SLIDE_TYPES",
    "SUPPORTED_TEMPLATES",
    "TEXT_LIMITS",
    "MIN_BULLETS",
    "MAX_BULLETS",
    "CAROUSEL_SLIDE_CONFIG_INVALID",
    "CAROUSEL_IMAGE_NOT_FOUND",
    "CAROUSEL_FONT_NOT_FOUND",
    "CAROUSEL_TEXT_OVERFLOW",
    "CAROUSEL_RENDER_FAILED",
    "CarouselError",
    "CarouselConfigError",
    "CarouselImageError",
    "CarouselFontError",
    "CarouselTextOverflowError",
    "CarouselRenderError",
    "CarouselSlide",
    "parse_carousel_slide",
    "PALETTE",
    "TEMPLATES",
    "TemplateTheme",
    "get_template",
    "hex_to_rgb",
    "palette_rgb",
    "CarouselSlideRenderer",
]
