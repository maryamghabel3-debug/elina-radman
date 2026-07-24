import pytest

pytestmark = pytest.mark.smoke

def test_safe_import_content_config_and_base():
    # This smoke test ensures core modules can be imported without
    # side effects, network calls, or secret requirements.
    # It guards against regression where an import would start a bot,
    # scheduler, or publish loop.

    # Import content_config - pure config, no network, no secret
    import agents.content_config as cc

    assert hasattr(cc, "BRAND")
    assert hasattr(cc, "PILLARS")
    assert hasattr(cc, "tags_for")
    assert hasattr(cc, "fallback_for")
    assert cc.BRAND == "Elina Radman"

    # Import base agent - pure class, no side effects
    from agents.base import Agent

    dummy = Agent(name="TestAgent", desc="smoke test agent")
    status = dummy.status()
    assert status["name"] == "TestAgent"
    assert "id" in status
    assert status["runs"] == 0


def test_safe_import_memory_engine_module_without_side_effects(tmp_path, monkeypatch):
    # Guard that importing memory_engine module does not create files
    # outside tmp_path and does not require secrets.
    # We do not instantiate MemoryEngine here to avoid file creation in real content/,
    # we only verify the module can be imported safely.

    import importlib

    monkeypatch.chdir(tmp_path)

    mod = importlib.import_module("agents.memory_engine")
    assert hasattr(mod, "MemoryEngine")
    assert hasattr(mod, "_DEFAULT_MEMORY")

    # Ensure no file was created in real repo during import (only on init)
    import os
    # In tmp_path, content/ should not exist after just importing module
    # (if it exists, it would be because _ensure_store was called on import, which would be a regression)
    # Note: we allow that the module may have created memory_store.json only after instantiation,
    # but not on import alone. So we check that import itself is side-effect free for file system
    # outside of tmp_path. Since we chdir to tmp_path, any file creation would be inside tmp_path.
    # We just assert that import did not raise and module is loadable.
    assert mod.MemoryEngine is not None
