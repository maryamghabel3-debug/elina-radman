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
