import pytest
import numpy as np
from agents.editing.audio_engine import AudioEngine, VOICE_PRESETS

pytestmark = pytest.mark.unit


def generate_sine_wave(duration_sec=1.0, freq=440, sr=48000):
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    wave = 0.5 * np.sin(2 * np.pi * freq * t)
    return wave.astype(np.float32)


def test_get_preset_returns_valid_config():
    engine = AudioEngine()
    preset = engine.get_preset("elina_cinematic_voice")
    assert "noise_gate_threshold_db" in preset
    assert preset["highpass_hz"] == 80


def test_get_preset_invalid_raises_error():
    engine = AudioEngine()
    with pytest.raises(ValueError):
        engine.get_preset("nonexistent_preset")


def test_process_voice_array_returns_processed_audio():
    engine = AudioEngine(sample_rate=48000)
    audio = generate_sine_wave()
    audio_2d = audio.reshape(1, -1)
    processed = engine.process_voice_array(audio_2d, "elina_cinematic_voice")
    assert processed is not None
    assert processed.shape[-1] == audio_2d.shape[-1]


def test_process_voice_array_empty_raises_error():
    engine = AudioEngine()
    with pytest.raises(ValueError):
        engine.process_voice_array(np.array([]), "elina_cinematic_voice")


def test_all_presets_are_processable():
    engine = AudioEngine()
    audio = generate_sine_wave().reshape(1, -1)
    for preset_name in VOICE_PRESETS.keys():
        result = engine.process_voice_array(audio, preset_name)
        assert result is not None


def test_calculate_peak_db_silence_returns_very_low():
    engine = AudioEngine()
    silence = np.zeros(1000, dtype=np.float32)
    db = engine.calculate_peak_db(silence)
    assert db <= -100.0


def test_calculate_peak_db_full_scale_near_zero():
    engine = AudioEngine()
    full_scale = np.ones(1000, dtype=np.float32)
    db = engine.calculate_peak_db(full_scale)
    assert db >= -1.0

def test_build_ffmpeg_afftdn_filter_default():
    from agents.editing.audio_engine import build_ffmpeg_afftdn_filter
    assert build_ffmpeg_afftdn_filter() == "afftdn=nf=-30"


def test_build_ffmpeg_afftdn_filter_rejects_positive_noise_floor():
    from agents.editing.audio_engine import build_ffmpeg_afftdn_filter
    import pytest
    with pytest.raises(ValueError):
        build_ffmpeg_afftdn_filter(5)


def test_build_ffmpeg_loudnorm_filter_contains_expected_values():
    from agents.editing.audio_engine import build_ffmpeg_loudnorm_filter
    filt = build_ffmpeg_loudnorm_filter()
    assert "loudnorm" in filt
    assert "I=-16" in filt
    assert "LRA=11" in filt
    assert "TP=-1.5" in filt
