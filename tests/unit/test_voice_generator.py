import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from agents.audio.voice_generator import (
    VoiceGenerator,
    VoiceGenerationError,
    VOICE_TEXT_EMPTY,
    VOICE_TEXT_TOO_LONG,
    VOICE_UNSUPPORTED,
    VOICE_RATE_INVALID,
    VOICE_GENERATION_FAILED,
)

pytestmark = pytest.mark.unit

# Tests use a zero retry delay so retry logic is exercised without real waits.
GEN_KWARGS = {"max_attempts": 2, "retry_delay_sec": 0}


def _write_fake_mp3(path, **kwargs):
    with open(path, "wb") as f:
        f.write(b"FAKE-MP3-AUDIO-BYTES")


# === Test A: valid Persian text -> default voice (dilara) ===

@pytest.mark.asyncio
async def test_generate_valid_persian_text_uses_default_dilara(tmp_path):
    """generate() with valid Persian text calls edge_tts with fa-IR-DilaraNeural and returns a file path."""
    out = str(tmp_path / "voice.mp3")
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        comm = MagicMock()
        comm.save = AsyncMock(side_effect=_write_fake_mp3)
        fake_edge.Communicate.return_value = comm

        path = await VoiceGenerator(**GEN_KWARGS).generate("سلام دنیا، این یک آزمایش است.", output_path=out)

    assert path == out
    assert os.path.getsize(out) > 0
    fake_edge.Communicate.assert_called_once_with("سلام دنیا، این یک آزمایش است.", "fa-IR-DilaraNeural", rate="+0%")


# === Test B: voice="farid" maps to fa-IR-FaridNeural ===

@pytest.mark.asyncio
async def test_generate_farid_maps_to_fa_ir_farid_neural(tmp_path):
    out = str(tmp_path / "voice.mp3")
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        comm = MagicMock()
        comm.save = AsyncMock(side_effect=_write_fake_mp3)
        fake_edge.Communicate.return_value = comm

        await VoiceGenerator(**GEN_KWARGS).generate("سلام.", voice="farid", output_path=out)

    fake_edge.Communicate.assert_called_once_with("سلام.", "fa-IR-FaridNeural", rate="+0%")


# === Test C: empty text raises validation error ===

@pytest.mark.asyncio
async def test_generate_empty_text_raises_validation_error():
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        with pytest.raises(VoiceGenerationError) as exc_info:
            await VoiceGenerator(**GEN_KWARGS).generate("")
        assert exc_info.value.code == VOICE_TEXT_EMPTY
    fake_edge.Communicate.assert_not_called()

    with pytest.raises(VoiceGenerationError) as exc_info:
        await VoiceGenerator(**GEN_KWARGS).generate("   ")
    assert exc_info.value.code == VOICE_TEXT_EMPTY


# === Test D: text > 2000 chars raises VOICE_TEXT_TOO_LONG ===

@pytest.mark.asyncio
async def test_generate_text_too_long_raises(tmp_path):
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        with pytest.raises(VoiceGenerationError) as exc_info:
            await VoiceGenerator(**GEN_KWARGS).generate("ک" * 2001)
        assert exc_info.value.code == VOICE_TEXT_TOO_LONG
    fake_edge.Communicate.assert_not_called()

    # Boundary: exactly 2000 chars is accepted
    out = str(tmp_path / "voice.mp3")
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        comm = MagicMock()
        comm.save = AsyncMock(side_effect=_write_fake_mp3)
        fake_edge.Communicate.return_value = comm
        path = await VoiceGenerator(**GEN_KWARGS).generate("ک" * 2000, output_path=out)
    assert path == out


# === Test E: unknown voice raises VOICE_UNSUPPORTED (listing supported) ===

@pytest.mark.asyncio
async def test_generate_unknown_voice_raises():
    with pytest.raises(VoiceGenerationError) as exc_info:
        await VoiceGenerator(**GEN_KWARGS).generate("سلام.", voice="sara")
    assert exc_info.value.code == VOICE_UNSUPPORTED
    # Error message must list the supported voices
    assert "dilara" in str(exc_info.value)
    assert "farid" in str(exc_info.value)


# === Test F: edge_tts failure raises VoiceGenerationError after retries ===

@pytest.mark.asyncio
async def test_generate_network_failure_raises_after_retries(tmp_path):
    out = str(tmp_path / "voice.mp3")
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        comm = MagicMock()
        comm.save = AsyncMock(side_effect=RuntimeError("simulated network failure"))
        fake_edge.Communicate.return_value = comm

        with pytest.raises(VoiceGenerationError) as exc_info:
            await VoiceGenerator(**GEN_KWARGS).generate("سلام.", output_path=out)

    assert exc_info.value.code == VOICE_GENERATION_FAILED
    # 2 attempts (default max_attempts=2)
    assert fake_edge.Communicate.call_count == 2
    assert "simulated network failure" in str(exc_info.value)


# === Additional coverage ===

@pytest.mark.asyncio
async def test_generate_transient_failure_then_success(tmp_path):
    """First attempt fails (transient), second succeeds -> returns the file path."""
    out = str(tmp_path / "voice.mp3")
    calls = {"n": 0}

    async def flaky_save(path, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient glitch")
        _write_fake_mp3(path)

    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        comm = MagicMock()
        comm.save = AsyncMock(side_effect=flaky_save)
        fake_edge.Communicate.return_value = comm

        path = await VoiceGenerator(**GEN_KWARGS).generate("سلام.", output_path=out)

    assert path == out
    assert fake_edge.Communicate.call_count == 2
    assert os.path.getsize(out) > 0


@pytest.mark.asyncio
async def test_generate_empty_output_file_raises_after_retries(tmp_path):
    """edge-tts 'succeeding' with an empty file must raise VOICE_GENERATION_FAILED."""
    out = str(tmp_path / "voice.mp3")
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        comm = MagicMock()
        comm.save = AsyncMock()  # writes nothing
        fake_edge.Communicate.return_value = comm

        with pytest.raises(VoiceGenerationError) as exc_info:
            await VoiceGenerator(**GEN_KWARGS).generate("سلام.", output_path=out)

    assert exc_info.value.code == VOICE_GENERATION_FAILED
    assert fake_edge.Communicate.call_count == 2


@pytest.mark.asyncio
async def test_generate_rate_is_forwarded(tmp_path):
    """rate='-10%' (slower) is forwarded to edge_tts.Communicate."""
    out = str(tmp_path / "voice.mp3")
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        comm = MagicMock()
        comm.save = AsyncMock(side_effect=_write_fake_mp3)
        fake_edge.Communicate.return_value = comm

        await VoiceGenerator(**GEN_KWARGS).generate("سلام.", rate="-10%", output_path=out)

    fake_edge.Communicate.assert_called_once_with("سلام.", "fa-IR-DilaraNeural", rate="-10%")


@pytest.mark.asyncio
async def test_generate_invalid_rate_raises():
    """Malformed rate (not a signed percentage) raises VOICE_RATE_INVALID."""
    with pytest.raises(VoiceGenerationError) as exc_info:
        await VoiceGenerator(**GEN_KWARGS).generate("سلام.", rate="fast")
    assert exc_info.value.code == VOICE_RATE_INVALID


@pytest.mark.asyncio
async def test_generate_without_output_path_creates_temp_mp3():
    """When output_path is None, a temp .mp3 file is created and returned."""
    with patch("agents.audio.voice_generator.edge_tts") as fake_edge:
        comm = MagicMock()
        comm.save = AsyncMock(side_effect=_write_fake_mp3)
        fake_edge.Communicate.return_value = comm

        path = await VoiceGenerator(**GEN_KWARGS).generate("سلام.")

    try:
        assert path.endswith(".mp3")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        if os.path.exists(path):
            os.unlink(path)
