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
