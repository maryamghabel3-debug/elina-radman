import os
import shutil
import sys
from pathlib import Path

def check_cmd(name):
    return shutil.which(name) is not None

def main():
    ok = True

    print("Editor Environment Healthcheck")

    for cmd in ["ffmpeg", "ffprobe"]:
        exists = check_cmd(cmd)
        print(f"{cmd}: {'OK' if exists else 'MISSING'}")
        if not exists:
            ok = False

    font_path = os.environ.get("ELINA_FONT_PRIMARY_PATH")
    print(f"ELINA_FONT_PRIMARY_PATH: {'SET' if font_path else 'MISSING'}")
    if not font_path or not Path(font_path).exists():
        print(f"Font file: MISSING ({font_path})")
        ok = False
    else:
        print(f"Font file: OK ({font_path})")

    try:
        from PIL import features
        print(f"Pillow libraqm: {'YES' if features.check('raqm') else 'NO'}")
    except Exception as exc:
        print(f"Pillow check failed: {exc}")
        ok = False

    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        print("Farsi fallback libs: OK")
    except Exception as exc:
        print(f"Farsi fallback libs: MISSING ({exc})")
        ok = False

    try:
        import pedalboard
        import soundfile
        print("Audio libs: OK")
    except Exception as exc:
        print(f"Audio libs: MISSING ({exc})")
        ok = False

    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
