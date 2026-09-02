import os
import shutil
from unittest.mock import MagicMock, patch
from shutil import copyfile

import pytest

from agents.audio.asset_pinner import AssetPinner

pytestmark = pytest.mark.unit


def make_storage(uploads=None, downloads=None):
    storage = MagicMock()
    storage.uploads = uploads if uploads is not None else []
    storage.downloads = downloads if downloads is not None else []

    def upload(local, dest, content_type=None):
        storage.uploads.append((local, dest, content_type))
        return dest

    def download(storage_path, local_path):
        storage.downloads.append((storage_path, local_path))
        raise FileNotFoundError(f"no such object: {storage_path}")  # default: missing

    storage.upload_file.side_effect = upload
    storage.download_file.side_effect = download
    return storage


# === A. build_sfx_key is deterministic for the same query ===

def test_A_build_key_deterministic():
    pinner = AssetPinner(make_storage())
    k1 = pinner.build_sfx_key("ELN-X", "click sound")
    k2 = pinner.build_sfx_key("ELN-X", "click sound")
    assert k1 == k2
    # deterministic shape: assets/sfx/<content_id>/<12-hex>.mp3
    assert k1.startswith("assets/sfx/ELN-X/")
    assert k1.endswith(".mp3")
    digest = k1.split("/")[-1][:-4]
    assert len(digest) == 12
    int(digest, 16)  # hex


# === B. normalization collapses whitespace/case to the same key ===

def test_B_normalization_collapses_case_and_whitespace():
    pinner = AssetPinner(make_storage())
    base = pinner.build_sfx_key("ELN-X", "Keyboard Click")
    assert pinner.build_sfx_key("ELN-X", "keyboard   click") == base
    assert pinner.build_sfx_key("ELN-X", "  KEYBOARD CLICK  ") == base
    assert pinner.build_sfx_key("ELN-X", "keyboard\tclick") == base
    assert AssetPinner.normalize_query("  A  B ") == "a b"


# === C. different queries produce different keys ===

def test_C_different_queries_different_keys():
    pinner = AssetPinner(make_storage())
    assert pinner.build_sfx_key("ELN-X", "click") != pinner.build_sfx_key("ELN-X", "thud")
    # different content_id -> different key (pins are per-content)
    assert pinner.build_sfx_key("ELN-X", "click") != pinner.build_sfx_key("ELN-Y", "click")


# === D. get_pinned_sfx returns None when the object is missing ===

def test_D_get_pinned_returns_none_when_missing():
    storage = make_storage()
    pinner = AssetPinner(storage)
    assert pinner.get_pinned_sfx("ELN-X", "click") is None
    # it queried the deterministic key
    key = pinner.build_sfx_key("ELN-X", "click")
    assert storage.downloads and storage.downloads[0][0] == key


# === E. pin_sfx uploads to the deterministic storage key ===

def test_E_pin_uploads_to_deterministic_key():
    storage = make_storage()
    pinner = AssetPinner(storage)
    local = "/tmp/fake_sfx.mp3"
    os.makedirs("/tmp", exist_ok=True)
    with open(local, "wb") as f:
        f.write(b"MP3DATA")

    key = pinner.pin_sfx("ELN-X", "  Click ", local)
    assert key == pinner.build_sfx_key("ELN-X", "Click")
    assert storage.uploads and storage.uploads[0] == (local, key, "audio/mpeg")

    # upload failures are soft: logged, key still returned, no exception
    storage.upload_file.side_effect = RuntimeError("bucket down")
    assert pinner.pin_sfx("ELN-X", "Click", local) == key
    os.unlink(local)


# --- orchestrator-level tests (F-I) ---

def _orchestrator_fakes(tmp_path):
    import scripts  # noqa: F401  (ensures package import path works)
    from tests.unit.test_edit_orchestrator import (
        FakeDB, FakeStorage, FakeTypography, FakeAssembler,
    )
    db = FakeDB(item={
        "id": "uuid-sfx-pin",
        "custom_id": "ELN-PIN-TEST",
        "content_type": "reel",
        "media_keys": ["raw/video.mp4"],
        "status": "NEEDS_EDIT",
    })
    storage = FakeStorage()
    assembler = FakeAssembler()
    from agents.editing.orchestrator import EditOrchestrator
    orchestrator = EditOrchestrator(
        db=db, storage=storage, typography=FakeTypography(), assembler=assembler
    )
    return orchestrator


def _fake_fetched(tmp_path, content=b"FREESOUND-BYTES"):
    from agents.audio.base_provider import DownloadedSound, SoundResult
    local = str(tmp_path / "fetched.mp3")
    with open(local, "wb") as f:
        f.write(content)
    return DownloadedSound(
        local_path=local,
        metadata=SoundResult(
            provider="freesound", external_id="42", name="click",
            license="CC0", attribution="attribution-text",
            duration_sec=1.2, download_url="", preview_url="http://x/p.mp3",
        ),
    )


def test_F_and_G_pinned_file_skips_freesound(tmp_path):
    """F+G: when a pinned file exists, the pinner is consulted BEFORE the
    fetcher and Freesound is NOT called; the pinned bytes are used."""
    from agents.editing.orchestrator import EditOrchestrator
    import agents.editing.orchestrator as orch_mod

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    orchestrator = _orchestrator_fakes(tmp_path)

    # a "pinned" object that exists: pinner.get_pinned_sfx returns a real file
    pinned_file = tmp_path / "pinned.mp3"
    pinned_file.write_bytes(b"PINNED-BYTES")

    fake_pinner = MagicMock()
    fake_pinner.get_pinned_sfx.return_value = str(pinned_file)

    sfx_plan = [{
        "query": "Click Sound",
        "start_sec": 1.5,
        "gain_db": -6,
        "fade_in_sec": 0.1,
        "fade_out_sec": 0.3,
    }]

    with patch("agents.audio.asset_pinner.AssetPinner", return_value=fake_pinner), \
         patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher, \
         patch("shutil.copyfile", side_effect=copyfile) as mock_copy:
        import agents.editing.orchestrator as _o
        with patch.object(_o, "VideoConcatenator", lambda: MockConcatenator()):
            result = orchestrator.render_content(
                "ELN-PIN-TEST", actor="tester", plan_sfx=sfx_plan,
            )

    assert result["ok"] is True
    # pinner consulted, fetcher NEVER called
    fake_pinner.get_pinned_sfx.assert_called_once_with("ELN-PIN-TEST", "Click Sound")
    MockFetcher.return_value.fetch_best_match.assert_not_called()
    # the pinned file was copied into the session dir and used as the SFX path
    mock_copy.assert_called_once()
    copy_src, copy_dst = mock_copy.call_args[0]
    assert copy_src == str(pinned_file)
    assert copy_dst.endswith("plan_sfx_0.mp3")
    item = orchestrator.assembler.calls[0]["sfx_items"][0]
    assert item["path"] == copy_dst
    # attribution is not available on pin reuse (unused by the mixer)
    assert item["attribution"] is None


def test_H_miss_fetches_and_pins(tmp_path):
    """H: when no pinned object exists, Freesound IS called and the result is
    pinned for future re-renders."""
    orchestrator = _orchestrator_fakes(tmp_path)
    from agents.editing.orchestrator import EditOrchestrator  # noqa: F401

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    fetched = _fake_fetched(tmp_path)
    fake_pinner = MagicMock()
    fake_pinner.get_pinned_sfx.return_value = None

    sfx_plan = [{"query": "Door Thud", "start_sec": 0.5, "gain_db": -3}]

    with patch("agents.audio.asset_pinner.AssetPinner", return_value=fake_pinner), \
         patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher:
        MockFetcher.return_value.fetch_best_match.return_value = fetched
        import agents.editing.orchestrator as _o
        with patch.object(_o, "VideoConcatenator", lambda: MockConcatenator()):
            result = orchestrator.render_content(
                "ELN-PIN-TEST", actor="tester", plan_sfx=sfx_plan,
            )

    assert result["ok"] is True
    # fetcher WAS called with the query
    MockFetcher.return_value.fetch_best_match.assert_called_once()
    call_args = MockFetcher.return_value.fetch_best_match.call_args[0]
    assert call_args[0] == "Door Thud"
    # and the result was pinned (content_id, query, local file)
    fake_pinner.pin_sfx.assert_called_once()
    pin_args = fake_pinner.pin_sfx.call_args[0]
    assert pin_args[0] == "ELN-PIN-TEST"
    assert pin_args[1] == "Door Thud"
    assert os.path.exists(pin_args[2])
    # assembled item uses the fetched local file
    item = orchestrator.assembler.calls[0]["sfx_items"][0]
    assert open(item["path"], "rb").read() == b"FREESOUND-BYTES"
    assert item["attribution"] == "attribution-text"


def test_I_timing_gain_fields_unchanged(tmp_path):
    """I: timing/gain/fade fields flow through unchanged in both paths
    (pinned reuse and fresh fetch)."""
    orchestrator = _orchestrator_fakes(tmp_path)

    class MockConcatenator:
        def concat_segments(self, segments, output_path, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"0" * 20000)
            return output_path

    # NOTE: no "anchor" here — anchor resolution (M15) rewrites start_sec from
    # video durations and is unrelated to pinning; this test pins an
    # absolute-timing item.
    sfx_plan = [{
        "query": "Rain Loop",
        "start_sec": 2.25,
        "gain_db": -8,
        "fade_in_sec": 0.5,
        "fade_out_sec": 1.25,
        "normalize_loudness": False,
        "background_bed": True,
    }]

    import agents.editing.orchestrator as _o

    # Path 1: pinned reuse
    pinned_file = tmp_path / "pinned_rain.mp3"
    pinned_file.write_bytes(b"RAIN")
    fake_pinner = MagicMock()
    fake_pinner.get_pinned_sfx.return_value = str(pinned_file)
    with patch("agents.audio.asset_pinner.AssetPinner", return_value=fake_pinner), \
         patch("agents.audio.sfx_fetcher.SFXFetcher"), \
         patch.object(_o, "VideoConcatenator", lambda: MockConcatenator()):
        result = orchestrator.render_content(
            "ELN-PIN-TEST", actor="tester", plan_sfx=sfx_plan,
        )
    assert result["ok"] is True
    item = orchestrator.assembler.calls[-1]["sfx_items"][0]
    assert item["start_sec"] == 2.25
    assert item["gain_db"] == -8
    assert item["fade_in_sec"] == 0.5
    assert item["fade_out_sec"] == 1.25
    assert item["normalize_loudness"] is False
    assert item["background_bed"] is True

    # Path 2: fresh fetch — same timing fields
    orchestrator2 = _orchestrator_fakes(tmp_path)
    fetched = _fake_fetched(tmp_path, content=b"RAIN2")
    fake_pinner2 = MagicMock()
    fake_pinner2.get_pinned_sfx.return_value = None
    with patch("agents.audio.asset_pinner.AssetPinner", return_value=fake_pinner2), \
         patch("agents.audio.sfx_fetcher.SFXFetcher") as MockFetcher, \
         patch.object(_o, "VideoConcatenator", lambda: MockConcatenator()):
        MockFetcher.return_value.fetch_best_match.return_value = fetched
        result2 = orchestrator2.render_content(
            "ELN-PIN-TEST", actor="tester", plan_sfx=sfx_plan,
        )
    assert result2["ok"] is True
    item2 = orchestrator2.assembler.calls[-1]["sfx_items"][0]
    assert item2["start_sec"] == 2.25
    assert item2["gain_db"] == -8
    assert item2["fade_in_sec"] == 0.5
    assert item2["fade_out_sec"] == 1.25
    assert item2["background_bed"] is True
