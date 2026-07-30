import os
import logging
import numpy as np
import soundfile as sf
from pedalboard import Pedalboard, NoiseGate, Compressor, Reverb, Limiter, HighpassFilter

logger = logging.getLogger(__name__)

VOICE_PRESETS = {
    "elina_cinematic_voice": {
        "noise_gate_threshold_db": -40,
        "highpass_hz": 80,
        "compressor_threshold_db": -18,
        "compressor_ratio": 3.0,
        "reverb_room_size": 0.4,
        "reverb_wet_level": 0.15,
        "limiter_threshold_db": -1.0,
    },
    "maryam_natural_voice": {
        "noise_gate_threshold_db": -35,
        "highpass_hz": 100,
        "compressor_threshold_db": -15,
        "compressor_ratio": 2.0,
        "reverb_room_size": 0.2,
        "reverb_wet_level": 0.08,
        "limiter_threshold_db": -1.0,
    },
    "crisis_gentle_voice": {
        "noise_gate_threshold_db": -45,
        "highpass_hz": 90,
        "compressor_threshold_db": -14,
        "compressor_ratio": 2.0,
        "reverb_room_size": 0.0,
        "reverb_wet_level": 0.0,
        "limiter_threshold_db": -1.0,
    },
}


def build_ffmpeg_afftdn_filter(noise_floor_db: int = -30) -> str:
    """
    Returns an ffmpeg afftdn filter string for broadband denoise.
    Example output: 'afftdn=nf=-30'
    """
    if noise_floor_db > 0:
        raise ValueError("noise_floor_db must be 0 or negative.")
    return f"afftdn=nf={noise_floor_db}"


def build_ffmpeg_loudnorm_filter(
    target_i: int = -16,
    target_lra: int = 11,
    target_tp: float = -1.5
) -> str:
    """
    Returns an ffmpeg loudnorm filter string for final loudness normalization.
    """
    return f"loudnorm=I={target_i}:LRA={target_lra}:TP={target_tp}"


class AudioEngine:
    """
    Processes voice audio: applies noise gating, EQ (highpass), compression,
    cinematic reverb, and limiting according to a named preset.
    Uses Pedalboard (Spotify) for DSP processing.
    AudioEngine handles cinematic voice styling in-memory via Pedalboard.
    True denoise and final loudness normalization for export are handled by FFmpeg helpers.
    """

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

    def get_preset(self, preset_name: str) -> dict:
        if preset_name not in VOICE_PRESETS:
            available = ", ".join(VOICE_PRESETS.keys())
            raise ValueError(f"Unknown preset '{preset_name}'. Available: {available}")
        return VOICE_PRESETS[preset_name]

    def build_pedalboard(self, preset_name: str) -> Pedalboard:
        p = self.get_preset(preset_name)
        board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=p["highpass_hz"]),
            NoiseGate(threshold_db=p["noise_gate_threshold_db"], ratio=4, release_ms=150),
            Compressor(threshold_db=p["compressor_threshold_db"], ratio=p["compressor_ratio"]),
            Reverb(room_size=p["reverb_room_size"], wet_level=p["reverb_wet_level"]),
            Limiter(threshold_db=p["limiter_threshold_db"]),
        ])
        return board

    def process_voice_array(self, audio: np.ndarray, preset_name: str) -> np.ndarray:
        """
        Applies the cinematic voice chain to an in-memory numpy audio array.
        audio shape: (samples,) or (channels, samples)
        """
        if audio.size == 0:
            raise ValueError("Audio array is empty.")

        board = self.build_pedalboard(preset_name)
        processed = board(audio, self.sample_rate)
        return processed

    def process_voice_file(self, input_path: str, output_path: str, preset_name: str) -> str:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input audio file not found: {input_path}")

        audio, sr = sf.read(input_path, always_2d=False)
        audio = audio.astype(np.float32)

        if audio.ndim == 1:
            audio_for_board = audio.reshape(1, -1)
        else:
            audio_for_board = audio.T

        board = self.build_pedalboard(preset_name)
        processed = board(audio_for_board, sr)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        output_audio = processed.T if processed.ndim > 1 else processed
        sf.write(output_path, output_audio, sr)
        return output_path

    def calculate_peak_db(self, audio: np.ndarray) -> float:
        """Returns the peak level in dB for QC purposes."""
        peak = np.max(np.abs(audio))
        if peak == 0:
            return -120.0
        return float(20 * np.log10(peak))
