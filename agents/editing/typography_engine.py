import os
import logging
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

logger = logging.getLogger(__name__)

class TypographyEngine:
    """
    Solves the Persian/Arabic rendering issue in FFmpeg by pre-rendering
    text into a transparent PNG using Pillow, reshaper, and bidi algorithm.
    """

    def __init__(self, font_path: str = None):
        self.font_path = font_path or os.environ.get("ELINA_FONT_PRIMARY_PATH")
        if not self.font_path or not os.path.exists(self.font_path):
            raise FileNotFoundError(
                f"Font not found at path: {self.font_path}. "
                "Set ELINA_FONT_PRIMARY_PATH environment variable."
            )

    def _prepare_text(self, text: str) -> str:
        """Reshapes Arabic/Farsi letters and applies BiDi algorithm."""
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
        stroke_color: tuple = (0, 0, 0, 255)
    ) -> str:
        """
        Renders Persian text onto a transparent canvas and saves it as PNG.
        Returns the output_path.
        """
        if not text:
            raise ValueError("Text cannot be empty for rendering.")

        display_text = self._prepare_text(text)

        img = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(self.font_path, font_size)
        except IOError as e:
            logger.error(f"Failed to load font: {e}")
            raise

        bbox = draw.textbbox((0, 0), display_text, font=font, stroke_width=stroke_width)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (canvas_size[0] - text_width) / 2
        y = (canvas_size[1] - text_height) / 2

        draw.text(
            (x, y),
            display_text,
            font=font,
            fill=color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color
        )

        img.save(output_path, "PNG")
        return output_path
