import pytest

pytestmark = pytest.mark.unit

def test_tags_for_valid_pillar_returns_expected_tags():
    from agents.content_config import tags_for, TAGS

    # Happy path: valid pillar should return its tag string
    for pillar, expected_tags in TAGS.items():
        result = tags_for(pillar)
        assert isinstance(result, str)
        assert result == expected_tags
        assert result.strip() != ""
        assert "#" in result  # tags contain hashtag


def test_tags_for_invalid_pillar_returns_empty_string():
    from agents.content_config import tags_for

    # Edge case: unknown pillar should return empty string, not crash
    assert tags_for("nonexistent_pillar") == ""
    assert tags_for("") == ""
    assert tags_for("OOTD") == ""  # old fashion pillar not valid in V2


def test_fallback_for_valid_pillar_returns_real_caption():
    from agents.content_config import fallback_for, FALLBACK_CAPTIONS

    # Happy path: valid pillar returns its specific fallback
    for pillar in FALLBACK_CAPTIONS:
        caption = fallback_for(pillar)
        assert isinstance(caption, str)
        assert len(caption) > 10
        assert "[AI Generated" not in caption  # must not emit old placeholder
        assert caption.strip() != ""


def test_fallback_for_invalid_pillar_returns_default_mindful_lifestyle():
    from agents.content_config import fallback_for, FALLBACK_CAPTIONS

    # Failure / edge path: invalid pillar falls back to mindful_lifestyle
    default_caption = FALLBACK_CAPTIONS["mindful_lifestyle"]
    assert fallback_for("invalid_pillar") == default_caption
    assert fallback_for("") == default_caption
    assert fallback_for("unknown") == default_caption


def test_pillars_and_brand_constants_are_sane():
    from agents.content_config import PILLARS, BRAND, NICHE, TONE, BASE_TAGS

    # Behavioral check: core constants exist and are non-empty, prevents regression
    # if someone accidentally deletes or empties them
    assert isinstance(BRAND, str) and BRAND.strip() == "Elina Radman"
    assert isinstance(PILLARS, list) and len(PILLARS) == 4
    assert "psychology_insights" in PILLARS
    assert "ai_art_therapy" in PILLARS
    assert isinstance(NICHE, str) and "Psychology" in NICHE
    assert isinstance(TONE, str) and len(TONE) > 10
    assert isinstance(BASE_TAGS, str) and "#ElinaRadman" in BASE_TAGS
