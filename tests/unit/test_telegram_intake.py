import pytest
from agents.intake.telegram_intake import IntakeProcessor

pytestmark = pytest.mark.unit


def test_process_incoming_media_inserts_db_and_uploads(monkeypatch, tmp_path):
    class MockDB:
        def insert_content(self, data): pass
        def log_event(self, content_id, event_type, from_status, to_status, actor, detail): pass

    class MockStorage:
        def upload_file(self, local_file_path, destination_path): pass

    monkeypatch.setattr("agents.intake.telegram_intake.ElinaDB", MockDB)
    monkeypatch.setattr("agents.intake.telegram_intake.ElinaStorage", MockStorage)

    processor = IntakeProcessor()
    test_file = tmp_path / "test.mp4"
    test_file.write_text("dummy video content")

    result = processor.process_incoming_media(
        str(test_file), ".mp4", "test caption", "123", "tester"
    )

    assert result["status"] == "RAW_RECEIVED"
    assert result["custom_id"].startswith("ELN-RAW-")
    assert result["storage_path"].endswith(".mp4")
