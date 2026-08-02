import pytest
from agents.editing.recipe_schema import EditRecipe

pytestmark = pytest.mark.unit

def test_recipe_validation_passes():
    data = {"content_id": "test-123", "input_media": {"video_keys": ["v.mp4"]}}
    recipe = EditRecipe.from_dict(data)
    assert not recipe.validate()

def test_recipe_validation_fails_no_content_id():
    data = {"input_media": {"video_keys": ["v.mp4"]}}
    recipe = EditRecipe.from_dict(data)
    assert "content_id is required." in recipe.validate()

def test_recipe_validation_fails_no_media():
    data = {"content_id": "test-123"}
    recipe = EditRecipe.from_dict(data)
    assert any("At least one" in e for e in recipe.validate())

def test_recipe_validation_fails_invalid_project_type():
    data = {"content_id": "test", "project_type": "invalid", "input_media": {"video_keys": ["v"]}}
    assert any("invalid project_type" in e for e in EditRecipe.from_dict(data).validate())

def test_recipe_validation_fails_empty_hook():
    data = {"content_id": "test", "input_media": {"video_keys": ["v"]}, "hook": {"enabled": True, "text": "   "}}
    assert any("Hook is enabled but text is empty" in e for e in EditRecipe.from_dict(data).validate())

def test_from_dict_handles_invalid_type():
    with pytest.raises(TypeError):
        EditRecipe.from_dict(["not", "a", "dict"])

def test_from_dict_video_keys_list():
    data = {"content_id": "test", "input_media": {"video_keys": ["a.mp4", "b.mp4"]}}
    recipe = EditRecipe.from_dict(data)
    assert recipe.input_media.video_keys == ["a.mp4", "b.mp4"]

def test_from_dict_legacy_video_key():
    """Legacy single video_key should be converted to video_keys list."""
    data = {"content_id": "test", "input_media": {"video_key": "legacy.mp4"}}
    recipe = EditRecipe.from_dict(data)
    assert "legacy.mp4" in recipe.input_media.video_keys

# === Video Segments Tests ===

def test_valid_video_segments_pass():
    """Valid video_segments with proper key, start, end should pass."""
    data = {
        "content_id": "test",
        "input_media": {
            "video_segments": [
                {"key": "raw/clip1.mp4", "start": 1.2, "end": 5.8},
                {"key": "raw/clip2.mp4", "start": 0.0, "end": 4.0},
                {"key": "raw/clip3.mp4", "start": 2.5, "end": None},
            ]
        }
    }
    recipe = EditRecipe.from_dict(data)
    errors = recipe.validate()
    assert not errors

def test_video_segments_negative_start_fails():
    """Segment with negative start_sec should fail validation."""
    data = {
        "content_id": "test",
        "input_media": {
            "video_segments": [
                {"key": "raw/clip1.mp4", "start": -1.0, "end": 5.0},
            ]
        }
    }
    recipe = EditRecipe.from_dict(data)
    errors = recipe.validate()
    assert any("cannot be negative" in e for e in errors)

def test_video_segments_end_leq_start_fails():
    """Segment with end <= start should fail validation."""
    data = {
        "content_id": "test",
        "input_media": {
            "video_segments": [
                {"key": "raw/clip1.mp4", "start": 5.0, "end": 3.0},
            ]
        }
    }
    recipe = EditRecipe.from_dict(data)
    errors = recipe.validate()
    assert any("end_sec must be greater than start_sec" in e for e in errors)

def test_video_segments_end_equals_start_fails():
    """Segment with end == start should fail validation."""
    data = {
        "content_id": "test",
        "input_media": {
            "video_segments": [
                {"key": "raw/clip1.mp4", "start": 3.0, "end": 3.0},
            ]
        }
    }
    recipe = EditRecipe.from_dict(data)
    errors = recipe.validate()
    assert any("end_sec must be greater than start_sec" in e for e in errors)

def test_video_segments_missing_key_fails():
    """Segment without key should fail validation."""
    data = {
        "content_id": "test",
        "input_media": {
            "video_segments": [
                {"start": 0.0, "end": 5.0},
            ]
        }
    }
    recipe = EditRecipe.from_dict(data)
    errors = recipe.validate()
    assert any("must have a key" in e for e in errors)

def test_video_keys_convert_to_segments():
    """video_keys should be converted to video_segments with defaults."""
    data = {
        "content_id": "test",
        "input_media": {
            "video_keys": ["a.mp4", "b.mp4", "c.mp4"]
        }
    }
    recipe = EditRecipe.from_dict(data)
    assert len(recipe.input_media.video_segments) == 3
    assert all(seg.start_sec == 0.0 for seg in recipe.input_media.video_segments)
    assert all(seg.end_sec is None for seg in recipe.input_media.video_segments)
    assert [seg.key for seg in recipe.input_media.video_segments] == ["a.mp4", "b.mp4", "c.mp4"]

def test_video_segments_with_start_sec_end_sec_keys():
    """video_segments should support start_sec and end_sec keys."""
    data = {
        "content_id": "test",
        "input_media": {
            "video_segments": [
                {"key": "clip.mp4", "start_sec": 1.0, "end_sec": 10.0},
            ]
        }
    }
    recipe = EditRecipe.from_dict(data)
    assert len(recipe.input_media.video_segments) == 1
    assert recipe.input_media.video_segments[0].start_sec == 1.0
    assert recipe.input_media.video_segments[0].end_sec == 10.0

def test_video_segments_null_end_allowed():
    """Segment with null/None end should be allowed (open-ended trim)."""
    data = {
        "content_id": "test",
        "input_media": {
            "video_segments": [
                {"key": "raw/clip.mp4", "start": 5.0},
            ]
        }
    }
    recipe = EditRecipe.from_dict(data)
    errors = recipe.validate()
    assert not errors
    assert recipe.input_media.video_segments[0].end_sec is None
