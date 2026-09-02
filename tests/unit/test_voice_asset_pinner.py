import os
from unittest.mock import MagicMock, patch

import pytest

from agents.audio.asset_pinner import AssetPinner

pytestmark = pytest.mark.unit

TEXT = "سلام، این ویدیو درباره‌ی تو است."
VOICE = "farid"
RATE = "-10%"


def make_storage(uploads=None, downloads=None, pinned_objects=None):
    """Mock storage. `pinned_objects`: {key: bytes} that download_file serves."""
    storage = MagicMock()
    storage.uploads = uploads if uploads is not None else []
    storage.downloads = downloads if downloads is not None else []
    pinned = pinned_objects or {}

    def upload(local, dest, content_type=None):
        storage.uploads.append((local, dest, content_type))
        return dest

    def download(storage_path, local_path):
        storage.downloads.append((storage_path, local_path))
        if storage_path in pinned:
            with open(local_path, "wb") as f:
                f.write(pinned[storage_path])
            return local_path
        raise FileNotFoundError(f"no such object: {storage_path}")

    storage.upload_file.side_effect = upload
    storage.download_file.side_effect = download
    return storage


# === A. build_voice_key is deterministic for the same text/voice/rate ===

def test_A_voice_key_deterministic():
    pinner = AssetPinner(make_storage())
    k1 = pinner.build_voice_key("ELN-X", TEXT, VOICE, RATE)
    k2 = pinner.build_voice_key("ELN-X", TEXT, VOICE, RATE)
    assert k1 == k2
    assert k1.startswith("voice/ELN-X/")
    assert k1.endswith(".mp3")
    digest = k1.split("/")[-1][:-4]
    assert len(digest) == 12
    int(digest, 16)  # hex


# === B. text whitespace normalization leads to the same key ===

def test_B_text_normalization_same_key():
    pinner = AssetPinner(make_storage())
    base = pinner.build_voice_key("ELN-X", TEXT, VOICE, RATE)
    assert pinner.build_voice_key("ELN-X", "  " + TEXT + "  ", VOICE, RATE) == base
    assert pinner.build_voice_key("ELN-X", TEXT.replace("، ", "،   "), VOICE, RATE) == base
    # case is NOT normalized (TTS content, not a query)
    assert AssetPinner.normalize_text("  a   b ") == "a b"
    assert AssetPinner.normalize_text("SALAM") == "SALAM"
    assert pinner.build_voice_key("ELN-X", "SALAM", VOICE, RATE) != pinner.build_voice_key("ELN-X", "salam", VOICE, RATE)


# === C. different voice names produce different keys ===

def test_C_different_voice_names_different_keys():
    pinner = AssetPinner(make_storage())
    assert pinner.build_voice_key("ELN-X", TEXT, "dilara", RATE) != pinner.build_voice_key("ELN-X", TEXT, "farid", RATE)
    # different text / content_id also differ
    assert pinner.build_voice_key("ELN-X", TEXT + "!", VOICE, RATE) != pinner.build_voice_key("ELN-X", TEXT, VOICE, RATE)
    assert pinner.build_voice_key("ELN-Y", TEXT, VOICE, RATE) != pinner.build_voice_key("ELN-X", TEXT, VOICE, RATE)


# === D. different rates produce different keys ===

def test_D_different_rates_different_keys():
    pinner = AssetPinner(make_storage())
    assert pinner.build_voice_key("ELN-X", TEXT, VOICE, "-10%") != pinner.build_voice_key("ELN-X", TEXT, VOICE, "+0%")


# === E. get_pinned_voice returns None when missing ===

def test_E_get_pinned_voice_missing_returns_none():
    storage = make_storage()
    pinner = AssetPinner(storage)
    assert pinner.get_pinned_voice("ELN-X", TEXT, VOICE, RATE) is None
    # it queried the deterministic key
    key = pinner.build_voice_key("ELN-X", TEXT, VOICE, RATE)
    assert storage.downloads and storage.downloads[0][0] == key


# === F. pin_voice uploads to the deterministic storage key ===

def test_F_pin_voice_uploads_to_deterministic_key(tmp_path):
    storage = make_storage()
    pinner = AssetPinner(storage)
    local = str(tmp_path / "voice.mp3")
    with open(local, "wb") as f:
        f.write(b"MP3DATA")

    key = pinner.pin_voice("ELN-X", TEXT, VOICE, RATE, local)
    assert key == pinner.build_voice_key("ELN-X", TEXT, VOICE, RATE)
    assert storage.uploads and storage.uploads[0] == (local, key, "audio/mpeg")

    # upload failures are soft: key still returned, no exception
    storage.upload_file.side_effect = RuntimeError("bucket down")
    assert pinner.pin_voice("ELN-X", TEXT, VOICE, RATE, local) == key


# --- orchestrator-level tests (G-K) ---

def _orchestrator_fakes(tmp_path):
    from tests.unit.test_edit_orchestrator import (
        FakeDB, FakeStorage, FakeTypography, FakeAssembler,
    )
    db = FakeDB(item={
        "id": "uuid-voice-pin",
        "custom_id": "ELN-VPIN",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "status": "NEEDS_EDIT",
    })
    storage = FakeStorage()
    assembler = FakeAssembler()
    from agents.editing.orchestrator import EditOrchestrator
    return EditOrchestrator(
        db=db, storage=storage, typography=FakeTypography(), assembler=assembler
    ), storage


def _mock_concat(monkeypatch):
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    monkeypatch.setattr(orch_mod, "VideoConcatenator", lambda: MockConcatenator())


def test_G_and_H_pinned_voice_skips_tts(tmp_path, monkeypatch):
    """G+H: the pinner is checked before generation; when a pinned voice
    exists, VoiceGenerator is NOT called and the pinned bytes are used."""
    _mock_concat(monkeypatch)
    orchestrator, storage = _orchestrator_fakes(tmp_path)

    key = AssetPinner(storage).build_voice_key("ELN-VPIN", TEXT, VOICE, RATE)
    pinned_file = tmp_path / "pinned_voice.mp3"
    pinned_file.write_bytes(b"PINNED-VOICE")

    fake_pinner = MagicMock()
    fake_pinner.get_pinned_voice.return_value = str(pinned_file)
    fake_pinner.build_voice_key.side_effect = AssetPinner(storage).build_voice_key
    fake_pinner.pin_voice.return_value = key

    gen_calls = []

    class RecordingVoiceGenerator:
        def __init__(self, *a, **k):
            gen_calls.append("init")

        async def generate(self, **kw):
            gen_calls.append("generate")
            raise AssertionError("TTS must be skipped when pinned")

        async def generate_with_timing(self, **kw):
            gen_calls.append("generate_with_timing")
            raise AssertionError("TTS must be skipped when pinned")

    from shutil import copyfile
    with patch("agents.audio.asset_pinner.AssetPinner", return_value=fake_pinner), \
         patch("agents.audio.voice_generator.VoiceGenerator", RecordingVoiceGenerator), \
         patch("shutil.copyfile", side_effect=copyfile) as mock_copy:
        result = orchestrator.render_content(
            "ELN-VPIN", actor="tester",
            plan_voice={"text": TEXT, "voice": VOICE, "rate": RATE},
        )

    assert result["ok"] is True
    # G: pinner consulted with (content_id, text, voice, rate)
    fake_pinner.get_pinned_voice.assert_called_once_with("ELN-VPIN", TEXT, VOICE, RATE)
    # H: VoiceGenerator never constructed/called; no pin upload
    assert gen_calls == []
    fake_pinner.pin_voice.assert_not_called()
    # the pinned file was copied into the session dir and used as voice_path
    mock_copy.assert_called_once()
    copy_src, copy_dst = mock_copy.call_args[0]
    assert copy_src == str(pinned_file)
    call = orchestrator.assembler.calls[0]
    assert call["voice_path"] == copy_dst
    assert copy_dst.endswith("voice_tts.mp3")
    # voice_key recorded as the deterministic pin key (no redundant upload)
    assert call["recipe"].input_media.voice_key == key
    # no fresh voice upload happened
    assert not [u for u in storage.uploads if u[1].startswith("voice/ELN-VPIN/job")]


def test_I_miss_generates_and_pins(tmp_path, monkeypatch):
    """I: when no pinned voice exists, the generator IS called and the result
    is pinned for future re-renders."""
    _mock_concat(monkeypatch)
    orchestrator, storage = _orchestrator_fakes(tmp_path)

    fake_pinner = MagicMock()
    fake_pinner.get_pinned_voice.return_value = None
    fake_pinner.build_voice_key.side_effect = AssetPinner(storage).build_voice_key
    expected_key = AssetPinner(storage).build_voice_key("ELN-VPIN", TEXT, VOICE, RATE)
    fake_pinner.pin_voice.return_value = expected_key

    gen_calls = []

    class RecordingVoiceGenerator:
        def __init__(self, *a, **k):
            pass

        async def generate(self, text, voice="dilara", rate="+0%", output_path=None):
            gen_calls.append({"text": text, "voice": voice, "rate": rate,
                              "output_path": output_path})
            with open(output_path, "wb") as f:
                f.write(b"GENERATED-VOICE")
            return output_path

        async def generate_with_timing(self, **kw):
            gen_calls.append(kw)
            raise AssertionError("plain generate expected (no auto_subtitles)")

    with patch("agents.audio.asset_pinner.AssetPinner", return_value=fake_pinner), \
         patch("agents.audio.voice_generator.VoiceGenerator", RecordingVoiceGenerator):
        result = orchestrator.render_content(
            "ELN-VPIN", actor="tester", job_id="jobvoice9",
            plan_voice={"text": TEXT, "voice": VOICE, "rate": RATE},
        )

    assert result["ok"] is True
    # generator called once with the plan values
    assert len(gen_calls) == 1
    assert gen_calls[0]["text"] == TEXT
    assert gen_calls[0]["voice"] == VOICE
    assert gen_calls[0]["rate"] == RATE
    # and the result was pinned (content_id, text, voice, rate, local file)
    fake_pinner.pin_voice.assert_called_once()
    pin_args = fake_pinner.pin_voice.call_args[0]
    assert pin_args[0] == "ELN-VPIN"
    assert pin_args[1] == TEXT
    assert pin_args[2] == VOICE
    assert pin_args[3] == RATE
    assert pin_args[4].endswith("voice_tts.mp3")
    # fresh-generation upload naming preserved (job_id key)
    voice_uploads = [u for u in storage.uploads if u[1].startswith("voice/ELN-VPIN/")]
    assert len(voice_uploads) == 1
    assert voice_uploads[0][1] == "voice/ELN-VPIN/jobvoice9.mp3"
    assert voice_uploads[0][2] == "audio/mpeg"
    call = orchestrator.assembler.calls[0]
    assert call["recipe"].input_media.voice_key == "voice/ELN-VPIN/jobvoice9.mp3"
    # the freshly generated session file is the one handed to the assembly
    assert call["voice_path"] == gen_calls[0]["output_path"]
    assert call["voice_path"].endswith("voice_tts.mp3")


def test_J_auto_subtitles_with_pinned_voice(tmp_path, monkeypatch):
    """J: auto_subtitles still generates cues when the voice is pinned
    (no word boundaries -> soft proportional fallback over the file duration)."""
    from tests.unit.test_edit_orchestrator import FakeSubtitleRenderer
    _mock_concat(monkeypatch)
    orchestrator, storage = _orchestrator_fakes(tmp_path)

    pinned_file = tmp_path / "pinned_voice.mp3"
    pinned_file.write_bytes(b"PINNED-VOICE")

    fake_pinner = MagicMock()
    fake_pinner.get_pinned_voice.return_value = str(pinned_file)
    fake_pinner.build_voice_key.side_effect = AssetPinner(storage).build_voice_key

    gen_calls = []

    class RecordingVoiceGenerator:
        def __init__(self, *a, **k):
            gen_calls.append("init")

        async def generate(self, **kw):
            gen_calls.append("generate")
            raise AssertionError("TTS must be skipped when pinned")

        async def generate_with_timing(self, **kw):
            gen_calls.append("generate_with_timing")
            raise AssertionError("TTS must be skipped when pinned")

    with patch("agents.audio.asset_pinner.AssetPinner", return_value=fake_pinner), \
         patch("agents.audio.voice_generator.VoiceGenerator", RecordingVoiceGenerator), \
         patch("agents.editing.subtitle_renderer.SubtitleRenderer", FakeSubtitleRenderer):
        result = orchestrator.render_content(
            "ELN-VPIN", actor="tester",
            plan_voice={"text": "سلام دنیا، این آزمایش است.", "auto_subtitles": True},
        )

    assert result["ok"] is True
    assert gen_calls == []  # TTS skipped
    # subtitles were still generated (proportional fallback over the file)
    recipe = orchestrator.assembler.calls[0]["recipe"]
    assert recipe.subtitles  # cues derived
    overlays = orchestrator.assembler.calls[0]["subtitle_overlays"]
    assert len(overlays) == len(recipe.subtitles)


def test_K_voice_gain_start_unchanged_with_pinned_voice(tmp_path, monkeypatch):
    """K: voice gain_db / start_sec flow into the recipe unchanged on the
    pinned-voice path (and on the fresh-generation path)."""
    _mock_concat(monkeypatch)
    orchestrator, storage = _orchestrator_fakes(tmp_path)

    pinned_file = tmp_path / "pinned_voice.mp3"
    pinned_file.write_bytes(b"PINNED-VOICE")

    fake_pinner = MagicMock()
    fake_pinner.get_pinned_voice.return_value = str(pinned_file)
    fake_pinner.build_voice_key.side_effect = AssetPinner(storage).build_voice_key

    with patch("agents.audio.asset_pinner.AssetPinner", return_value=fake_pinner), \
         patch("agents.audio.voice_generator.VoiceGenerator") as MockGen:
        result = orchestrator.render_content(
            "ELN-VPIN", actor="tester",
            plan_voice={"text": TEXT, "voice": VOICE, "rate": RATE,
                        "gain_db": -3, "start_sec": 1.5},
        )

    assert result["ok"] is True
    MockGen.assert_not_called()
    recipe = orchestrator.assembler.calls[0]["recipe"]
    assert recipe.audio.voice_gain_db == -3
    assert recipe.audio.voice_start_sec == 1.5
