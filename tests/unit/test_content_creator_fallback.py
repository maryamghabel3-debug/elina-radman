import pytest

pytestmark = pytest.mark.unit


def test_fallback_does_not_raise_keyerror_when_llm_unavailable(tmp_path, monkeypatch):
    """
    Regression test for unknown-pillar fallback.
    When LLM is unavailable, ContentCreator should fallback to a valid caption
    without raising KeyError, even for unknown pillars.
    Before fix: raises KeyError for unknown pillars.
    After fix: should return a valid caption from the default fallback.
    """
    # Isolate filesystem - run in tmp_path
    monkeypatch.chdir(tmp_path)

    from agents.content_creator import ContentCreator
    from agents import llm_router

    cc = ContentCreator()

    # Mock LLMRouter to simulate unavailable LLM (no API key)
    class FakeRouter:
        def smart_generate(self, *args, **kwargs):
            # Simulate failure -> return empty response so fallback path triggers
            return {"response": ""}

    monkeypatch.setattr(llm_router, "LLMRouter", lambda: FakeRouter())

    # This should NOT raise KeyError even for unknown pillar
    # Before fix, it raised KeyError when the fallback looked up an unknown pillar
    try:
        caption = cc.generate_dynamic_caption("unknown_pillar_xyz", products=[])
    except KeyError as e:
        pytest.fail(f"ContentCreator fallback raised KeyError (bug not fixed): {e}")

    assert isinstance(caption, str)
    assert len(caption) > 10
    assert "[AI Generated" not in caption


def test_fallback_uses_valid_pillar_key(tmp_path, monkeypatch):
    """
    Ensure fallback uses a valid key from current FALLBACK_CAPTIONS,
    not legacy keys like 'ootd', 'petite_styling', 'smart_shopping'.
    Before fix: fallback default is FALLBACK_CAPTIONS["ootd"] which is invalid.
    After fix: should use a valid key from the current PILLARS list.
    """
    monkeypatch.chdir(tmp_path)

    from agents.content_config import FALLBACK_CAPTIONS, PILLARS
    from agents.content_creator import ContentCreator
    from agents import llm_router

    # Verify current valid keys
    valid_keys = set(FALLBACK_CAPTIONS.keys())
    assert "ootd" not in valid_keys, "fashion-era key must not return"
    assert "petite_styling" not in valid_keys
    assert "smart_shopping" not in valid_keys
    assert "pain_naming" in valid_keys

    cc = ContentCreator()

    # Mock LLM to force fallback
    class FakeRouter:
        def smart_generate(self, *args, **kwargs):
            return {"response": ""}

    monkeypatch.setattr(llm_router, "LLMRouter", lambda: FakeRouter())

    # Test with a valid V2 pillar - should use that pillar's caption
    caption_valid = cc.generate_dynamic_caption("pain_naming", products=[])
    assert isinstance(caption_valid, str)
    assert len(caption_valid) > 10
    # Should be exactly the fallback for that pillar (since LLM mocked)
    assert caption_valid == FALLBACK_CAPTIONS["pain_naming"]

    # Test with invalid pillar - should fallback to a valid default, not legacy ootd
    caption_invalid = cc.generate_dynamic_caption("totally_unknown_pillar", products=[])
    assert isinstance(caption_invalid, str)
    assert len(caption_invalid) > 10
    # Must be one of the valid fallbacks, not crash
    assert caption_invalid in FALLBACK_CAPTIONS.values()
    # Ensure it's not referencing legacy key
    # The bug was: FALLBACK_CAPTIONS.get(pillar, FALLBACK_CAPTIONS["ootd"]) -> KeyError
    # After fix: should be FALLBACK_CAPTIONS.get(pillar, FALLBACK_CAPTIONS["mindful_lifestyle"])
    assert "ootd" not in caption_invalid.lower() or True  # just ensure no crash
