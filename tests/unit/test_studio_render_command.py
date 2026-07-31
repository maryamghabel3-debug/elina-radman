import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.unit


def make_mock_update(is_owner=True, args=None, chat_id="12345", username="tester"):
    """Helper to create a mock Update and Context for testing telegram handlers."""
    mock_user = MagicMock()
    mock_user.username = username
    mock_user.first_name = "Test"

    mock_chat = MagicMock()
    mock_chat.id = chat_id if is_owner else "99999"

    # Mock the message that will be returned by reply_text (msg with edit_text)
    mock_msg_with_edit = MagicMock()
    mock_msg_with_edit.edit_text = AsyncMock()

    mock_message = MagicMock()
    mock_message.chat = mock_chat
    mock_message.from_user = mock_user
    mock_message.reply_text = AsyncMock(return_value=mock_msg_with_edit)
    mock_message.message_id = 1
    mock_message.caption = None
    mock_message.text = None

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = args or []

    return mock_update, mock_context, mock_msg_with_edit


@pytest.mark.asyncio
async def test_cmd_render_unauthorized_does_nothing(monkeypatch):
    """Unauthorized user should not trigger any reply or orchestrator call."""
    monkeypatch.setenv("OWNER_CHAT_ID", "12345")

    from scripts.elina_studio_bot import cmd_render

    mock_update, mock_context, _ = make_mock_update(is_owner=False, args=["ELN-RAW-TEST"])

    monkeypatch.setattr("scripts.elina_studio_bot.EditOrchestrator", lambda: MagicMock())

    await cmd_render(mock_update, mock_context)

    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_cmd_render_no_args_sends_usage(monkeypatch):
    """Without args, should send usage message."""
    monkeypatch.setenv("OWNER_CHAT_ID", "12345")

    from scripts.elina_studio_bot import cmd_render

    mock_update, mock_context, _ = make_mock_update(is_owner=True, args=[])

    await cmd_render(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    call_arg = mock_update.message.reply_text.call_args[0][0]
    assert "استفاده: /render" in call_arg


@pytest.mark.asyncio
async def test_cmd_render_success_with_mocked_orchestrator(monkeypatch):
    """With mocked orchestrator returning success, should send success via edit_text."""
    monkeypatch.setenv("OWNER_CHAT_ID", "12345")

    from scripts.elina_studio_bot import cmd_render

    mock_update, mock_context, mock_msg_with_edit = make_mock_update(is_owner=True, args=["ELN-RAW-TEST", "تو", "تنبل", "نیستی"])

    class FakeOrchestrator:
        def render_content(self, custom_id, hook_text=None, actor=None):
            return {
                "ok": True,
                "custom_id": custom_id,
                "output_key": "edited/ELN-RAW-TEST/final.mp4",
                "status": "READY_FOR_REVIEW"
            }

    monkeypatch.setattr("scripts.elina_studio_bot.EditOrchestrator", lambda: FakeOrchestrator())

    await cmd_render(mock_update, mock_context)

    # Should have called reply_text once for "in progress"
    assert mock_update.message.reply_text.call_count == 1
    first_call = mock_update.message.reply_text.call_args[0][0]
    assert "در حال رندر" in first_call

    # And edit_text should have been called with success
    mock_msg_with_edit.edit_text.assert_called_once()
    edit_call_arg = mock_msg_with_edit.edit_text.call_args[0][0]
    assert "✅ رندر تمام شد" in edit_call_arg
    assert "ELN-RAW-TEST" in edit_call_arg
