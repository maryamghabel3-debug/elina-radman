import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

pytestmark = pytest.mark.unit


def make_mock_update(is_owner=True, args=None, chat_id="12345", username="tester", message_text=None):
    """Helper to create a mock Update and Context for testing telegram handlers."""
    mock_user = MagicMock()
    mock_user.username = username
    mock_user.first_name = "Test"

    mock_chat = MagicMock()
    mock_chat.id = chat_id if is_owner else "99999"

    mock_msg_with_edit = MagicMock()
    mock_msg_with_edit.edit_text = AsyncMock()

    mock_message = MagicMock()
    mock_message.chat = mock_chat
    mock_message.from_user = mock_user
    mock_message.reply_text = AsyncMock(return_value=mock_msg_with_edit)
    mock_message.message_id = 1
    mock_message.caption = None
    mock_message.text = message_text or (" ".join(args) if args else None)

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = args or []

    return mock_update, mock_context, mock_msg_with_edit


@pytest.mark.asyncio
async def test_cmd_render_calls_orchestrator():
    """cmd_render should call orchestrator with correct parameters."""
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, mock_msg_with_edit = make_mock_update(
        is_owner=True, args=["ELN-TEST", "متن", "هوک"]
    )

    orchestrator_called = []

    class FakeOrchestrator:
        def render_content(self, custom_id, hook_text=None, actor=None, **kwargs):
            orchestrator_called.append({
                "custom_id": custom_id,
                "hook_text": hook_text,
                "actor": actor,
            })
            return {"ok": True, "custom_id": "ELN-TEST", "output_key": "out.mp4", "status": "READY_FOR_REVIEW"}

    with patch.object(bot_module, "EditOrchestrator", lambda: FakeOrchestrator()):
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_render(mock_update, mock_context)

    # Orchestrator should be called
    assert len(orchestrator_called) == 1
    assert orchestrator_called[0]["custom_id"] == "ELN-TEST"
    assert orchestrator_called[0]["hook_text"] == "متن هوک"


@pytest.mark.asyncio
async def test_cmd_render_unauthorized_does_nothing():
    """Unauthorized user should not trigger any reply or orchestrator call."""
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(is_owner=False, args=["ELN-TEST"])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_render(mock_update, mock_context)

    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_cmd_whoami_when_owner():
    """whoami should reply confirming owner status"""
    import scripts.elina_studio_bot as bot_module

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        mock_update, mock_context, _ = make_mock_update(is_owner=True, chat_id="12345")
        await bot_module.cmd_whoami(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "✅" in text
    assert "مالک" in text
    assert "12345" in text


@pytest.mark.asyncio
async def test_cmd_whoami_when_not_owner():
    """whoami should reply explaining owner mismatch"""
    import scripts.elina_studio_bot as bot_module

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        mock_update, mock_context, _ = make_mock_update(is_owner=False, chat_id="99999")
        await bot_module.cmd_whoami(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "❌" in text
    assert "99999" in text
    assert "12345" in text


@pytest.mark.asyncio
async def test_cmd_help_when_not_owner():
    """help/start should reply with access denied and /whoami prompt if not owner"""
    import scripts.elina_studio_bot as bot_module

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        mock_update, mock_context, _ = make_mock_update(is_owner=False, chat_id="99999")
        await bot_module.cmd_start_help(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "⛔" in text
    assert "دسترسی فقط برای مالک است" in text
    assert "/whoami" in text
