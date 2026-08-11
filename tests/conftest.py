# Common fixtures for ElinaOS tests - minimal, no secrets, no network
import pytest
import os

# Set required environment variables for tests (no secrets, placeholders only)
os.environ.setdefault("OWNER_CHAT_ID", "12345")
os.environ.setdefault("STUDIO_BOT_TOKEN", "test_token_for_testing")
os.environ.setdefault("GITHUB_TOKEN", "test_github_token_for_ci")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test_supabase_key_for_ci")
os.environ["ELINA_TEST_ALLOW_MOCKS"] = "true"


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Isolated temp cwd with content/queue - reusable fixture"""
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs("content/queue", exist_ok=True)
    yield tmp_path
