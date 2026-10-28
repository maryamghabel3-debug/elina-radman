"""Central configuration for the psyche-studio motion-graphics engine.

All canvas, font, colour and path constants live here so scenes and the
video pipeline never hard-code magic values. Dark psychology theme:
deep navy/indigo backgrounds, cream text, a single violet accent.
"""
from pathlib import Path

# --- Canvas / timing -------------------------------------------------------
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# --- Filesystem layout -----------------------------------------------------
STUDIO_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = STUDIO_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
IMAGE_DIR = ASSETS_DIR / "images"
CONTENT_DIR = STUDIO_DIR / "content"
PROBES_DIR = STUDIO_DIR / "probes"
OUTPUT_DIR = STUDIO_DIR / "output"

# --- Vazirmatn fonts (all four weights verified loadable) -----------------
FONT_REGULAR = FONT_DIR / "Vazirmatn-Regular.ttf"
FONT_MEDIUM = FONT_DIR / "Vazirmatn-Medium.ttf"
FONT_BOLD = FONT_DIR / "Vazirmatn-Bold.ttf"
FONT_BLACK = FONT_DIR / "Vazirmatn-Black.ttf"

# --- Dark psychology palette (RGB) -----------------------------------------
# V2 brand palette (exact hex brief): violet/navy identity.
COLORS = {
    # Backgrounds: deep navy -> indigo
    "background": (14, 18, 38),        # #0E1226
    "background_alt": (24, 26, 58),
    # Foreground: warm cream / white
    "text": (245, 240, 232),           # #F5F0E8
    "text_dim": (178, 180, 205),
    # Single accent: violet
    "accent": (139, 124, 255),         # #8B7CFF
    "violet": (139, 124, 255),
    "accent_soft": (104, 92, 200),
    # Gold: trigger / key-concept emphasis
    "highlight": (240, 200, 120),      # #F0C878
    "gold": (240, 200, 120),
    # Cards
    "card_bg": (28, 32, 60),           # #1C203C
    "card": (28, 32, 60),
    "card_border": (92, 98, 158),
    # Semantic highlights
    "danger": (255, 107, 107),         # #FF6B6B negative thoughts
    "success": (94, 214, 162),         # #5ED6A2 reality / healthy action
    # V2 semantic aliases
    "bg": (14, 18, 38),
}

# --- Subtitle style (bottom safe area, burned into frames) ----------------
SUBTITLE_STYLE = {
    "font_path": FONT_MEDIUM,
    "font_size": 44,
    "min_font_size": 28,
    "center_y": 1750,
    "max_width": WIDTH - 140,
    "padding_x": 32,
    "padding_y": 22,
    "line_spacing": 1.35,
    "box_color": (8, 10, 24),
    "box_opacity": 200,          # 0-255
    "box_radius": 24,
    "text_color": COLORS["text"],
}

# --- Encoder ---------------------------------------------------------------
ENCODE_CRF = 18
ENCODE_PRESET = "medium"
