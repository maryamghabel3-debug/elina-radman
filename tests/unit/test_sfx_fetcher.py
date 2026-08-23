import pytest
from unittest.mock import patch, MagicMock
from agents.audio.freesound_provider import FreesoundProvider
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


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_returns_filtered_results(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "id": 1,
                "name": "door creak",
                "license": "Creative Commons 0",
                "username": "user1",
                "duration": 2.5,
                "download": "http://example.com/1.wav",
                "previews": {"preview-hq-mp3": "http://example.com/1.mp3"},
                "tags": ["door"]
            },
            {
                "id": 2,
                "name": "restricted",
                "license": "Sampling+",
                "username": "user2",
                "duration": 3.0,
                "download": "http://example.com/2.wav",
                "previews": {"preview-hq-mp3": "http://example.com/2.mp3"},
                "tags": []
            }
        ]
    }
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="test_key")
    results = provider.search("door")
    assert len(results) == 1
    assert results[0].external_id == "1"
    assert results[0].provider == "freesound"


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_download_saves_file(mock_get, tmp_path):
    mock_get.return_value = MagicMock(status_code=200, content=b"fakemp3data")
    provider = FreesoundProvider(api_key="test_key")
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


# === New Mocked Hardening Tests ===

@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_http_200_rain(mock_get):
    """valid API key + HTTP 200 + rain results."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "id": 123,
                "name": "distant rain ambience",
                "license": "Creative Commons 0",
                "username": "rainmaker",
                "duration": 5.0,
                "download": "",
                "previews": {"preview-hq-mp3": "http://example.com/rain.mp3"},
                "tags": ["rain"]
            }
        ]
    }
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="valid_key")
    results = provider.search("rain")
    assert len(results) == 1
    assert results[0].external_id == "123"
    assert results[0].name == "distant rain ambience"


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_401_auth_failed(mock_get):
    """401 becomes SFX_AUTH_FAILED."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Authentication failed details"
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="invalid_key")
    with pytest.raises(RuntimeError, match="SFX_AUTH_FAILED"):
        provider.search("rain")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_400_request_invalid(mock_get):
    """400 becomes SFX_SEARCH_REQUEST_INVALID."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request details"
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="valid_key")
    with pytest.raises(RuntimeError, match="SFX_SEARCH_REQUEST_INVALID"):
        provider.search("bad query")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_429_rate_limited(mock_get):
    """429 becomes SFX_RATE_LIMITED."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limited details"
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="valid_key")
    with pytest.raises(RuntimeError, match="SFX_RATE_LIMITED"):
        provider.search("rain")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_timeout_raises_provider_timeout(mock_get):
    """timeout becomes SFX_PROVIDER_TIMEOUT."""
    import requests
    mock_get.side_effect = requests.Timeout("Network timeout")

    provider = FreesoundProvider(api_key="valid_key")
    with pytest.raises(RuntimeError, match="SFX_PROVIDER_TIMEOUT"):
        provider.search("rain")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_500_raises_provider_unavailable(mock_get):
    """500 becomes SFX_PROVIDER_UNAVAILABLE."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_get.return_value = mock_response

    provider = FreesoundProvider(api_key="valid_key")
    with pytest.raises(RuntimeError, match="SFX_PROVIDER_UNAVAILABLE"):
        provider.search("rain")


@patch("agents.audio.freesound_provider.requests.get")
def test_freesound_search_zero_result_activates_aliases(mock_get):
    """HTTP 200 zero result activates aliases and stops at the first successful query."""
    mock_response_empty = MagicMock()
    mock_response_empty.status_code = 200
    mock_response_empty.json.return_value = {"results": []}

    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {
        "results": [
            {
                "id": 999,
                "name": "soft rain ambience",
                "license": "Creative Commons 0",
                "username": "user",
                "duration": 5.0,
                "download": "",
                "previews": {"preview-hq-mp3": "http://example.com/soft_rain.mp3"},
                "tags": []
            }
        ]
    }

    mock_get.side_effect = [mock_response_empty, mock_response_success]

    provider = FreesoundProvider(api_key="valid_key")
    results = provider.search("rain ambience distant")
    assert len(results) == 1
    assert results[0].external_id == "999"
    assert mock_get.call_count == 2

