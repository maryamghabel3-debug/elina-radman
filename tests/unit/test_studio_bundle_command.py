import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

pytestmark = pytest.mark.unit


def make_mock_update(is_owner=True, chat_id="12345", username="tester", args=None):
    """Helper to create a mock Update and Context for testing telegram handlers."""
    mock_user = MagicMock()
    mock_user.username = username
    mock_user.first_name = "Test"

    mock_chat = MagicMock()
    mock_chat.id = chat_id if is_owner else "99999"

    mock_message = MagicMock()
    mock_message.chat = mock_chat
    mock_message.from_user = mock_user
    mock_message.reply_text = AsyncMock()
    mock_message.message_id = 1

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = args or []

    return mock_update, mock_context


@pytest.mark.asyncio
async def test_non_owner_cannot_create_bundle():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=False, args=["bundle-name", "ELN-RAW-1", "ELN-RAW-2"])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_bundle(mock_update, mock_context)

    # Check that access denied reply was sent
    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "⛔" in reply
    assert "دسترسی" in reply


@pytest.mark.asyncio
async def test_missing_arguments_returns_persian_usage():
    import scripts.elina_studio_bot as bot_module

    # Call with fewer than 3 arguments (missing clip IDs)
    mock_update, mock_context = make_mock_update(is_owner=True, args=["bundle-name"])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_bundle(mock_update, mock_context)

    # Assert usage guide replied
    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "❌" in reply
    assert "دستور نامعتبر است" in reply
    assert "/bundle" in reply


@pytest.mark.asyncio
async def test_success_response_includes_eln_bundle_id_and_clip_count():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=True, args=["shot-zero", "ELN-RAW-1", "ELN-RAW-2"])

    mock_result = {
        "ok": True,
        "custom_id": "ELN-BUNDLE-20260804-abcde123",
        "bundle_name": "shot-zero",
        "clip_count": 2,
        "status": "NEEDS_EDIT"
    }

    with patch("agents.studio.bundle_manager.VideoBundleManager") as MockManager:
        instance = MockProcessor = MockManager.return_value
        instance.create_bundle.return_value = mock_result

        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_bundle(mock_update, mock_context)

        # Confirm VideoBundleManager was called
        instance.create_bundle.assert_called_once_with(
            bundle_name="shot-zero",
            source_custom_ids=["ELN-RAW-1", "ELN-RAW-2"],
            actor="tester"
        )

        # Confirm reply contains custom_id, bundle_name, clip_count, and status
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "✅" in reply_text
        assert "shot-zero" in reply_text
        assert "ELN-BUNDLE-20260804-abcde123" in reply_text
        assert "2" in reply_text
        assert "NEEDS_EDIT" in reply_text
