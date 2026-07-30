from dataclasses import dataclass


@dataclass
class DuckingParams:
    target_reduction_db: int = 6
    attack: float = 0.2
    release: float = 0.6
    threshold_db: float = -24.0
    ratio: float = 4.0


def build_ffmpeg_sidechain_filter(params: DuckingParams, voice_stream: str = "1:a", music_stream: str = "0:a") -> str:
    """
    Builds an FFmpeg filter_complex string for sidechain compression.
    Voice (narration) controls the compression of the music track.
    """
    if params.attack < 0 or params.release < 0:
        raise ValueError("attack and release must not be negative.")
    if params.target_reduction_db < 0:
        raise ValueError("target_reduction_db must not be negative.")

    filter_str = (
        f"[{music_stream}][{voice_stream}]"
        f"sidechaincompress=threshold={params.threshold_db}dB:"
        f"ratio={params.ratio}:"
        f"attack={int(params.attack * 1000)}:"
        f"release={int(params.release * 1000)}"
        f"[ducked_music]"
    )
    return filter_str


def validate_ducking_params(params: DuckingParams) -> list:
    errors = []
    if params.attack < 0:
        errors.append("attack must not be negative")
    if params.release < 0:
        errors.append("release must not be negative")
    if params.target_reduction_db < 0:
        errors.append("target_reduction_db must not be negative")
    if params.ratio <= 0:
        errors.append("ratio must be greater than 0")
    return errors
