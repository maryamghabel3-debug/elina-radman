# Common fixtures for ElinaOS tests - minimal, no secrets, no network
import pytest

@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Isolated temp cwd with content/queue - reusable fixture"""
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs("content/queue", exist_ok=True)
    yield tmp_path
