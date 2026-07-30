import pytest
from agents.editing.recipe_schema import EditRecipe

pytestmark = pytest.mark.unit

def test_recipe_from_dict_minimal():
    data = {"content_id": "test-123"}
    recipe = EditRecipe.from_dict(data)
    assert recipe.content_id == "test-123"
    assert recipe.hook.enabled is False
    assert recipe.export.fps == 30

def test_recipe_validation_fails_on_empty_hook_text():
    data = {
        "content_id": "test-456",
        "hook": {"enabled": True, "text": ""}
    }
    recipe = EditRecipe.from_dict(data)
    errors = recipe.validate()
    assert len(errors) > 0
    assert "Hook is enabled" in errors[0]

def test_recipe_validation_passes_valid_data():
    data = {
        "content_id": "test-789",
        "hook": {"enabled": True, "text": "سلام دنیا"}
    }
    recipe = EditRecipe.from_dict(data)
    errors = recipe.validate()
    assert len(errors) == 0
