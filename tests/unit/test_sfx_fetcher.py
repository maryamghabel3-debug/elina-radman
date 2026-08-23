import pytest
import requests
from unittest.mock import patch, MagicMock
from agents.audio.freesound_provider import FreesoundProvider, normalize_license
from agents.audio.sfx_fetcher import SFXFetcher
from agents.audio.base_provider import SoundResult, DownloadedSound

pytestmark = pytest.mark.unit


def test_freesound_missing_api_key_raises():
    import os
    old = os.environ.pop("FREESOUND_API_KEY", None)
    try:
        with pytest.raises(ValueError):
            FreesoundProvider(api_key=None)
    finally:
        if old:
            os.environ["FREESOUND_API_KEY"] = old


def test_freesound_empty_query_raises():
    provider = FreesoundProvider(api_key="test_key")
    with pytest.raises(ValueError):
        provider.search("")


# === License Normalization Tests ===

def test_normalize_license_variants():
    # Creative Commons 0 variations accepted
    assert normalize_license("Creative Commons 0") == "cc0"
    assert normalize_license("http://creativecommons.org/publicdomain/zero/1.0/") == "cc0"
    assert normalize_license("CC0") == "cc0"
    assert normalize_license("cc0 1.0 Universal") == "cc0"

    # Attribution variations accepted
    assert normalize_license("Attribution") == "attribution"
    assert normalize_license("http://creativecommons.org/licenses/by/4.0/") == "attribution"
    assert normalize_license("cc-by") == "attribution"

    # NonCommercial variations explicitly rejected
    assert normalize_license("Attribution NonCommercial") is None
    assert normalize_license("Attribution Noncommercial") is None
    assert normalize_license("by-nc") is None
    assert normalize_license("http://creativecommons.org/licenses/by-nc/4.0/") is None

    # Other licenses rejected
    assert normalize_license("Sampling+") is None
    assert normalize_license("Sampling Plus") is None
    assert normalize_license("") is None
    assert normalize_license(None) is None


# === Freesound Provider Hardened Behavior Mocks ===

@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_401_becomes_auth_failed(mock_get):
    """HTTP 401 -> SFX_AUTH_FAILED."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized Token"
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="invalid_key")
    with pytest.raises(RuntimeError, match="SFX_AUTH_FAILED"):
        provider.search("rain")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_400_becomes_request_invalid(mock_get):
    """HTTP 400 -> SFX_SEARCH_REQUEST_INVALID."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad parameters"
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="valid_key")
    with pytest.raises(RuntimeError, match="SFX_SEARCH_REQUEST_INVALID"):
        provider.search("bad")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_429_becomes_rate_limited(mock_get):
    """HTTP 429 -> SFX_RATE_LIMITED."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Throttled"
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="valid_key")
    with pytest.raises(RuntimeError, match="SFX_RATE_LIMITED"):
        provider.search("rain")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_timeout_becomes_provider_timeout(mock_get):
    """timeout -> SFX_PROVIDER_TIMEOUT."""
    mock_get.side_effect = requests.Timeout("Network Timeout")

    provider = FreesoundProvider(api_key="valid_key")
    with pytest.raises(RuntimeError, match="SFX_PROVIDER_TIMEOUT"):
        provider.search("rain")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_500_becomes_provider_unavailable(mock_get):
    """HTTP 500 -> SFX_PROVIDER_UNAVAILABLE."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="valid_key")
    with pytest.raises(RuntimeError, match="SFX_PROVIDER_UNAVAILABLE"):
        provider.search("rain")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_separate_cc0_and_by_merged_and_deduplicated(mock_get):
    """separate CC0 + Attribution results merged and deduplicated."""
    # First search (CC0) return ID 1
    mock_response_cc0 = MagicMock()
    mock_response_cc0.status_code = 200
    mock_response_cc0.json.return_value = {
        "results": [
            {
                "id": 1,
                "name": "rain soft",
                "license": "Creative Commons 0",
                "username": "user1",
                "duration": 5.0,
                "download": "",
                "previews": {"preview-hq-mp3": "http://example.com/1.mp3"},
                "tags": []
            }
        ]
    }

    # Second search (Attribution) return ID 1 and ID 2
    mock_response_by = MagicMock()
    mock_response_by.status_code = 200
    mock_response_by.json.return_value = {
        "results": [
            {
                "id": 1,
                "name": "rain soft",
                "license": "Creative Commons 0",
                "username": "user1",
                "duration": 5.0,
                "download": "",
                "previews": {"preview-hq-mp3": "http://example.com/1.mp3"},
                "tags": []
            },
            {
                "id": 2,
                "name": "heavy rain",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "username": "user2",
                "duration": 12.0,
                "download": "",
                "previews": {"preview-hq-mp3": "http://example.com/2.mp3"},
                "tags": []
            }
        ]
    }

    mock_get.side_effect = [mock_response_cc0, mock_response_by]

    provider = FreesoundProvider(api_key="valid_key")
    results = provider.search("rain")
    
    # Check merged & deduplicated size
    assert len(results) == 2
    assert results[0].external_id == "1"
    assert results[1].external_id == "2"


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_raw_results_exist_but_all_unsafe_sfx_license_filter_empty(mock_get):
    """HTTP 200 with raw results but all locally rejected/unsafe -> raw results exist but empty accepted."""
    # Step 1 & 2 (filtered search) return empty
    mock_response_empty = MagicMock()
    mock_response_empty.status_code = 200
    mock_response_empty.json.return_value = {"results": []}

    # Fallback search (unfiltered larger page) returns only unsafe Attribution NonCommercial
    mock_response_fallback = MagicMock()
    mock_response_fallback.status_code = 200
    mock_response_fallback.json.return_value = {
        "results": [
            {
                "id": 99,
                "name": "noncommercial sound",
                "license": "Attribution NonCommercial",
                "username": "user",
                "duration": 4.0,
                "download": "",
                "previews": {"preview-hq-mp3": "http://example.com/99.mp3"},
                "tags": []
            }
        ]
    }

    mock_get.side_effect = [mock_response_empty, mock_response_empty, mock_response_fallback]

    provider = FreesoundProvider(api_key="valid_key")
    results = provider.search("rain", max_duration_sec=30.0)
    
    # Should reject the unsafe license locally and return an empty list
    assert len(results) == 0


@patch("agents.audio.freesound_provider.requests.get")
def test_preview_url_parsed_correctly(mock_get):
    """previews are parsed correctly, prioritizing preview-hq-mp3 over preview-lq-mp3."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "id": 1,
                "name": "creak",
                "license": "Creative Commons 0",
                "username": "user",
                "duration": 2.0,
                "download": "",
                "previews": {
                    "preview-hq-mp3": "http://example.com/hq.mp3",
                    "preview-lq-mp3": "http://example.com/lq.mp3"
                },
                "tags": []
            }
        ]
    }
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="valid_key")
    results = provider._search_request("creak", max_duration_sec=15.0, filter_license=None, limit=5)
    
    assert len(results) == 1
    assert results[0].preview_url == "http://example.com/hq.mp3"


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_download_saves_file(mock_get, tmp_path):
    mock_get.return_value = MagicMock(status_code=200, content=b"fakemp3data")
    provider = FreesoundProvider(api_key="valid_key")
    sound = SoundResult(
        provider="freesound",
        external_id="1",
        name="test",
        license="Creative Commons 0",
        attribution=None,
        duration_sec=2.0,
        download_url="http://example.com/1.wav",
        preview_url="http://example.com/1.mp3"
    )
    out = tmp_path / "out.mp3"
    result = provider.download(sound, str(out))
    assert out.exists()
    assert result.metadata.external_id == "1"


def test_sfx_fetcher_uses_provided_provider():
    fake_provider = MagicMock()
    fake_provider.search.return_value = [
        SoundResult(
            provider="fake", external_id="x", name="n",
            license="Creative Commons 0", attribution=None,
            duration_sec=1.0, download_url="",
            preview_url="http://example.com/preview.mp3"
        )
    ]
    fake_provider.download.return_value = DownloadedSound(
        local_path="/tmp/x.mp3",
        metadata=fake_provider.search.return_value[0]
    )
    fetcher = SFXFetcher(provider=fake_provider)
    result = fetcher.fetch_best_match("test", "/tmp/x.mp3")
    assert result is not None
    assert result.local_path == "/tmp/x.mp3"


def test_sfx_fetcher_returns_none_when_no_results():
    fake_provider = MagicMock()
    fake_provider.search.return_value = []
    fetcher = SFXFetcher(provider=fake_provider)
    result = fetcher.fetch_best_match("nothing", "/tmp/none.mp3")
    assert result is None
