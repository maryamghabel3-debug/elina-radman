import os
import logging
from PIL import Image, ImageDraw, ImageFont, features
import arabic_reshaper
from bidi.algorithm import get_display

logger = logging.getLogger(__name__)

class TypographyEngine:
    def __init__(self, font_path: str = None, render_mode: str = "auto"):
        self.font_path = font_path or os.environ.get("ELINA_FONT_PRIMARY_PATH")
        if not self.font_path or not os.path.exists(self.font_path):
            raise FileNotFoundError(f"Font not found at path: {self.font_path}")

        valid_modes = ["auto", "raqm", "fallback"]
        if render_mode not in valid_modes:
            raise ValueError(f"Invalid render_mode. Must be one of {valid_modes}")

        self.active_render_mode = self._determine_mode(render_mode)

    def is_raqm_available(self) -> bool:
        return features.check("raqm")

    def _determine_mode(self, mode: str) -> str:
        if mode == "auto":
            return "raqm" if self.is_raqm_available() else "fallback"
        elif mode == "raqm":
            if not self.is_raqm_available():
                raise RuntimeError("libraqm is requested but not available in Pillow.")
            return "raqm"
        return "fallback"

    def _prepare_text_fallback(self, text: str) -> str:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text

    def render_text_to_png(
        self,
        text: str,
        output_path: str,
        font_size: int = 70,
        canvas_size: tuple = (1080, 300),
        color: tuple = (255, 255, 255, 255),
        stroke_width: int = 2,
        stroke_color: tuple = (0, 0, 0, 255),
        safe_margin: int = 20
    ) -> str:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty.")
        if not output_path.lower().endswith(".png"):
            raise ValueError("Output path must end with .png")
        if font_size <= 0 or canvas_size[0] <= 0 or canvas_size[1] <= 0:
            raise ValueError("Font size and canvas dimensions must be positive.")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        img = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(self.font_path, font_size)
        except IOError as e:
            logger.error(f"Failed to load font: {e}")
            raise

        if self.active_render_mode == "raqm":
            display_text = text
            direction = "rtl"
            language = "fa"
        else:
            display_text = self._prepare_text_fallback(text)
            direction = None
            language = None

        # Handle multiline: split by \n and measure each line
        lines = display_text.split("\n")
        # For simplicity, we will render first line for bbox check but actual rendering will handle multiline via manual y offset?
        # To keep implementation simple and pass tests, we will render the whole text as single block using Pillow's multiline support if available
        # However, we need to check overflow based on real rendered size

        # Use textbbox with multiline? Pillow's textbbox does not handle \n well in older versions, so we estimate
        # For overflow check, we measure the longest line
        max_width = 0
        total_height = 0
        line_heights = []
        for line in lines:
            if not line.strip():
                line_heights.append(font_size)  # blank line
                continue
            bbox = draw.textbbox((0, 0), line, font=font, direction=direction, language=language, stroke_width=stroke_width)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            max_width = max(max_width, w)
            line_heights.append(h)
            total_height += h + 10  # 10px line spacing

        if max_width > canvas_size[0] - (2 * safe_margin) or total_height > canvas_size[1] - (2 * safe_margin):
            raise ValueError("Text exceeds safe area/canvas size. Reduce font size or wrap text.")

        # Center the block
        y_start = (canvas_size[1] - total_height) / 2
        y = y_start
        for idx, line in enumerate(lines):
            if not line.strip():
                y += line_heights[idx] + 10
                continue
            bbox = draw.textbbox((0, 0), line, font=font, direction=direction, language=language, stroke_width=stroke_width)
            text_width = bbox[2] - bbox[0]
            x = (canvas_size[0] - text_width) / 2
            # Ensure x is within safe_margin
            if x < safe_margin:
                x = safe_margin
            if x + text_width > canvas_size[0] - safe_margin:
                raise ValueError("Text exceeds safe area horizontally.")

            draw.text(
                (x, y),
                line,
                font=font,
                fill=color,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
                direction=direction,
                language=language
            )
            y += line_heights[idx] + 10

        alpha_extrema = img.getextrema()[3]
        if alpha_extrema[1] == 0:
            raise ValueError("Generated PNG is completely transparent.")

        img.save(output_path, "PNG")
        return output_path
