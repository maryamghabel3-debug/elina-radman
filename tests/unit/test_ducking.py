import pytest
from agents.editing.ducking import DuckingParams, build_ffmpeg_sidechain_filter, validate_ducking_params

pytestmark = pytest.mark.unit


def test_default_params_are_valid():
    params = DuckingParams()
    errors = validate_ducking_params(params)
    assert errors == []


def test_negative_attack_is_invalid():
    params = DuckingParams(attack=-0.1)
    errors = validate_ducking_params(params)
    assert any("attack" in e for e in errors)


def test_negative_release_is_invalid():
    params = DuckingParams(release=-0.1)
    errors = validate_ducking_params(params)
    assert any("release" in e for e in errors)


def test_zero_ratio_is_invalid():
    params = DuckingParams(ratio=0)
    errors = validate_ducking_params(params)
    assert any("ratio" in e for e in errors)


def test_build_filter_string_contains_sidechaincompress():
    params = DuckingParams()
    filter_str = build_ffmpeg_sidechain_filter(params)
    assert "sidechaincompress" in filter_str
    assert "ducked_music" in filter_str


def test_build_filter_raises_on_negative_attack():
    params = DuckingParams(attack=-1)
    with pytest.raises(ValueError):
        build_ffmpeg_sidechain_filter(params)


def test_build_filter_uses_custom_streams():
    params = DuckingParams()
    filter_str = build_ffmpeg_sidechain_filter(params, voice_stream="2:a", music_stream="3:a")
    assert "[3:a][2:a]" in filter_str
