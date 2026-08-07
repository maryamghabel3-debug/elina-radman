# Render Editor Environment

The Smart Editor requires:

- ffmpeg
- ffprobe
- Persian font
- ELINA_FONT_PRIMARY_PATH

Render build command must run:

bash scripts/setup_render_environment.sh && pip install -r requirements-core.txt

Required Render environment variable:

ELINA_FONT_PRIMARY_PATH=/tmp/fonts/Vazirmatn-Bold.ttf

Do not commit font files to the repository unless license and size are explicitly approved.
