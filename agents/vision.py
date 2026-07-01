"""Shared Gemini Vision helper for deep trend analysis.

Wraps Google Gemini's multimodal model so other agents can send an image (or a
text description of a video) plus a prompt and get back structured JSON.

Everything degrades gracefully:
  * no GEMINI_API_KEY  -> returns {"available": False, ...} so callers can fall
    back to their cheap/offline heuristics (e.g. colour palette only).
  * API / parse errors  -> logged and reported, never raised.

Gemini's free tier (gemini-1.5-flash / 2.x-flash) supports vision at no cost,
which is why it's the default engine for reverse-engineering trending media.
"""

import os
import io
import re
import json

import requests

_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")

# Browser-like headers so hot-linked CDN images (reddit, ytimg) don't 403.
_IMG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.reddit.com/",
    "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
}


def gemini_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _configure():
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai


def _extract_json(text: str):
    """Best-effort pull of a JSON object from an LLM reply."""
    if not text:
        return None
    # Strip ```json fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    raw = fenced.group(1) if fenced else text
    # Fall back to the first {...} / [...] block
    if not fenced:
        m = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
        if m:
            raw = m.group(1)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def download_image_bytes(url: str, timeout: int = 15):
    """Download raw image bytes with browser headers. Returns bytes or None."""
    try:
        r = requests.get(url, headers=_IMG_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.content
    except requests.RequestException:
        return None


def analyze_image(url: str, prompt: str, image_bytes: bytes = None) -> dict:
    """Send an image + prompt to Gemini Vision and return parsed JSON.

    Returns {"available": False} when no key is set, or {"error": ...} on failure.
    """
    if not gemini_available():
        return {"available": False, "reason": "no_gemini_key"}

    data = image_bytes or download_image_bytes(url)
    if not data:
        return {"error": "image_download_failed", "url": url}

    try:
        genai = _configure()
        model = genai.GenerativeModel(_MODEL)
        resp = model.generate_content(
            [prompt, {"mime_type": "image/jpeg", "data": data}]
        )
        parsed = _extract_json(resp.text)
        if parsed is None:
            return {"error": "unparseable_response", "raw": (resp.text or "")[:500]}
        return {"available": True, **parsed} if isinstance(parsed, dict) else {"available": True, "result": parsed}
    except Exception as e:  # noqa: BLE001 - report any provider error
        return {"error": str(e)[:300]}


def analyze_text(prompt: str) -> dict:
    """Send a text-only prompt to Gemini and return parsed JSON."""
    if not gemini_available():
        return {"available": False, "reason": "no_gemini_key"}
    try:
        genai = _configure()
        model = genai.GenerativeModel(_MODEL)
        resp = model.generate_content(prompt)
        parsed = _extract_json(resp.text)
        if parsed is None:
            return {"error": "unparseable_response", "raw": (resp.text or "")[:500]}
        return {"available": True, **parsed} if isinstance(parsed, dict) else {"available": True, "result": parsed}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:300]}
