"""
Persian TTS voice generation agent (TASK M15).

Generates Persian narration audio from text using edge-tts
(Microsoft Edge neural voices). Free service, no API key required.

Wired into the render pipeline:
    plan_data.voice -> render_worker -> orchestrator
    -> VoiceGenerator.generate() -> Supabase Storage upload
    -> media assembly (voice track with ducking + loudness normalization).

Error philosophy (same as M11): never swallow errors. Every failure raises
VoiceGenerationError with a typed code so the render job can be classified
as terminal (bad plan data) or retryable (transient network issue).
"""

import asyncio
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import edge_tts

logger = logging.getLogger(__name__)

# Typed error codes
VOICE_TEXT_EMPTY = "VOICE_TEXT_EMPTY"
VOICE_TEXT_TOO_LONG = "VOICE_TEXT_TOO_LONG"
VOICE_UNSUPPORTED = "VOICE_UNSUPPORTED"
VOICE_RATE_INVALID = "VOICE_RATE_INVALID"
VOICE_GENERATION_FAILED = "VOICE_GENERATION_FAILED"

# edge-tts rate format: signed percentage, e.g. "+0%", "-10%", "+10%"
_RATE_RE = re.compile(r"^[+-]?\d{1,3}%$")


class VoiceGenerationError(Exception):
    """Typed error raised for all voice generation failures."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass
class VoiceResult:
    """Audio file plus optional word-boundary timing from edge-tts (M17).

    word_boundaries holds one {"start_sec", "end_sec", "text"} per spoken
    word, in utterance order (offsets converted from the 100ns ticks the
    edge-tts WordBoundary events use). Empty when timing was unavailable.
    """

    path: str
    word_boundaries: List[Dict[str, Any]] = field(default_factory=list)


class VoiceGenerator:
    """Generates Persian speech audio from text via edge-tts neural voices."""

    DEFAULT_VOICE = "fa-IR-DilaraNeural"
    SUPPORTED_VOICES = {
        "dilara": "fa-IR-DilaraNeural",   # female
        "farid": "fa-IR-FaridNeural",     # male
    }
    MAX_TEXT_CHARS = 2000

    def __init__(self, max_attempts: int = 2, retry_delay_sec: float = 1.0):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self.retry_delay_sec = retry_delay_sec

    def _validate_args(self, text: str, voice: str, rate: str) -> Tuple[str, str]:
        """Validate generation arguments; return (stripped_text, voice_id)."""
        if not isinstance(text, str) or not text.strip():
            raise VoiceGenerationError(
                VOICE_TEXT_EMPTY, "narration text must be a non-empty string"
            )
        text = text.strip()
        if len(text) > self.MAX_TEXT_CHARS:
            raise VoiceGenerationError(
                VOICE_TEXT_TOO_LONG,
                f"narration text is {len(text)} characters; maximum is {self.MAX_TEXT_CHARS}",
            )
        if voice not in self.SUPPORTED_VOICES:
            supported = ", ".join(
                f"{name} -> {voice_id}" for name, voice_id in sorted(self.SUPPORTED_VOICES.items())
            )
            raise VoiceGenerationError(
                VOICE_UNSUPPORTED,
                f"voice '{voice}' is not supported. Supported voices: {supported}",
            )
        if not isinstance(rate, str) or not _RATE_RE.match(rate):
            raise VoiceGenerationError(
                VOICE_RATE_INVALID,
                f"rate '{rate}' is invalid. Expected a signed percentage like '+0%', '-10%', '+10%'.",
            )
        return text, self.SUPPORTED_VOICES[voice]

    @staticmethod
    def _resolve_output_path(output_path: Optional[str]) -> str:
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="elina_voice_")
            os.close(fd)
        return output_path

    async def generate(
        self,
        text: str,
        voice: str = "dilara",
        rate: str = "+0%",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate speech audio from Persian text.

        Returns the local file path (mp3) of the generated audio.

        Raises VoiceGenerationError with a typed code:
        - VOICE_TEXT_EMPTY       text missing/empty
        - VOICE_TEXT_TOO_LONG    text longer than MAX_TEXT_CHARS
        - VOICE_UNSUPPORTED      unknown voice name
        - VOICE_RATE_INVALID     malformed rate string
        - VOICE_GENERATION_FAILED network/provider failure after retries
        """
        # --- Validation: fail fast, before any network I/O ---
        text, voice_id = self._validate_args(text, voice, rate)
        output_path = self._resolve_output_path(output_path)

        # --- Generation with a small retry for transient network failures ---
        last_error: Optional[BaseException] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                communicate = edge_tts.Communicate(text, voice_id, rate=rate)
                await communicate.save(output_path)
                # edge-tts can "succeed" while producing an empty file
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    raise RuntimeError("edge-tts produced an empty audio file")
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Voice generation attempt %d/%d failed: %s",
                    attempt, self.max_attempts, exc,
                )
                if attempt < self.max_attempts:
                    await asyncio.sleep(self.retry_delay_sec * attempt)
                continue

            logger.info(
                "Generated %d bytes of speech at %s (voice=%s, rate=%s)",
                os.path.getsize(output_path), output_path, voice_id, rate,
            )
            return output_path

        raise VoiceGenerationError(
            VOICE_GENERATION_FAILED,
            f"voice generation failed after {self.max_attempts} attempts: {last_error}",
        )

    async def generate_with_timing(
        self,
        text: str,
        voice: str = "dilara",
        rate: str = "+0%",
        output_path: Optional[str] = None,
    ) -> VoiceResult:
        """
        Generate speech audio AND collect per-word timing metadata (M17).

        Uses edge-tts streaming so WordBoundary events (offsets in 100ns
        ticks) can be captured. Returns a VoiceResult with the local audio
        path and word_boundaries (one entry per spoken word, utterance
        order). Raises the same typed VoiceGenerationError codes as
        generate(); timing is best-effort (an empty list is fine).
        """
        text, voice_id = self._validate_args(text, voice, rate)
        output_path = self._resolve_output_path(output_path)

        last_error: Optional[BaseException] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                # boundary="WordBoundary" requests per-word timing metadata
                # (the Communicate default is SentenceBoundary).
                try:
                    communicate = edge_tts.Communicate(
                        text, voice_id, rate=rate, boundary="WordBoundary"
                    )
                except TypeError:
                    # Very old edge-tts without the boundary option
                    communicate = edge_tts.Communicate(text, voice_id, rate=rate)
                boundaries: List[Dict[str, Any]] = []
                audio_bytes = 0
                with open(output_path, "wb") as f:
                    async for chunk in communicate.stream():
                        if not isinstance(chunk, dict):
                            continue
                        # edge-tts 6.x yields PascalCase keys ("Type"/"Offset"...)
                        # while 7.x yields lowercase ("type"/"offset"...) — accept both.
                        chunk_type = chunk.get("Type") or chunk.get("type")
                        if chunk_type in ("Audio", "audio"):
                            data = chunk.get("Data", chunk.get("data", b"")) or b""
                            f.write(data)
                            audio_bytes += len(data)
                        elif chunk_type in ("WordBoundary", "wordboundary"):
                            # Offset/Duration are 100ns ticks (1e-7 seconds)
                            start_sec = int(float(chunk.get("Offset", chunk.get("offset", 0)))) / 10_000_000
                            duration_sec = int(float(chunk.get("Duration", chunk.get("duration", 0)))) / 10_000_000
                            boundaries.append({
                                "start_sec": start_sec,
                                "end_sec": start_sec + duration_sec,
                                "text": chunk.get("Text", chunk.get("text", "")),
                            })
                if audio_bytes == 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    raise RuntimeError("edge-tts produced an empty audio file")
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Voice generation (with timing) attempt %d/%d failed: %s",
                    attempt, self.max_attempts, exc,
                )
                if attempt < self.max_attempts:
                    await asyncio.sleep(self.retry_delay_sec * attempt)
                continue

            logger.info(
                "Generated %d bytes of speech at %s with %d word boundaries (voice=%s, rate=%s)",
                audio_bytes, output_path, len(boundaries), voice_id, rate,
            )
            return VoiceResult(path=output_path, word_boundaries=boundaries)

        raise VoiceGenerationError(
            VOICE_GENERATION_FAILED,
            f"voice generation failed after {self.max_attempts} attempts: {last_error}",
        )
