"""Probe A — Pillow text-engine capability check.

Reports the Pillow version and whether libraqm (complex / RTL text shaping)
is available. The result decides the Persian text architecture:
  - raqm available  -> raw text + direction="rtl" + language="fa"
  - raqm missing    -> arabic-reshaper + python-bidi pre-processing
Read-only probe: writes nothing.
"""
import PIL
import PIL.features

print(f"Pillow version : {PIL.__version__}")
for feature in ("raqm", "freetype2", "libjpeg_turbo", "zlib", "lcms"):
    try:
        print(f"check({feature!r:16}) = {PIL.features.check(feature)}")
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"check({feature!r:16}) ERROR: {exc}")

if PIL.features.check("raqm"):
    try:
        print("raqm module version:", PIL.features.version_module("raqm"))
    except Exception as exc:
        print("raqm version unknown:", exc)
