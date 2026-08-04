import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import asyncio

pytestmark = pytest.mark.unit


def make_mock_update(is_owner=True, chat_id="12345", username="tester", message_text=None, video=None, photo=None, document=None, audio=None, voice=None):
    """Helper to create a mock Update and Context for testing telegram handlers."""
    mock_user = MagicMock()
    mock_user.username = username
    mock_user.first_name = "Test"

    mock_chat = MagicMock()
    mock_chat.id = chat_id if is_owner else "99999"

    mock_message = MagicMock()
    mock_message.chat = mock_chat
    mock_message.chat_id = chat_id if is_owner else "99999"
    mock_message.from_user = mock_user
    mock_message.reply_text = AsyncMock()
    mock_message.message_id = 1
    mock_message.caption = None
    mock_message.text = message_text

    mock_message.video = video
    mock_message.photo = photo
    mock_message.document = document
    mock_message.audio = audio
    mock_message.voice = voice

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()

    return mock_update, mock_context


@pytest.mark.asyncio
async def test_non_owner_media_upload_gets_access_denied():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=False, message_text="some text")

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.handle_studio_media(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "⛔" in reply
    assert "دسترسی" in reply


@pytest.mark.asyncio
async def test_owner_text_only_upload_calls_intake_processor_with_source():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=True, message_text="فایل متنی منتخب")

    mock_result = {"custom_id": "ELN-RAW-20260804-abcdef", "status": "RAW_RECEIVED"}

    with patch("agents.intake.telegram_intake.IntakeProcessor") as MockProcessor:
        instance = MockProcessor.return_value
        instance.process_incoming_media.return_value = mock_result

        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.handle_studio_media(mock_update, mock_context)

        instance.process_incoming_media.assert_called_once_with(
            local_file_path=ANY,
            file_ext=".txt",
            caption="Text-only intake",
            telegram_message_id="1",
            sender_name="tester",
            source="telegram_studio_upload"
        )


@pytest.mark.asyncio
async def test_owner_video_upload_replies_with_custom_id():
    import scripts.elina_studio_bot as bot_module

    mock_file = MagicMock()
    mock_file.download_to_drive = AsyncMock()

    mock_video = MagicMock()
    mock_video.get_file = AsyncMock(return_value=mock_file)

    mock_update, mock_context = make_mock_update(is_owner=True, video=mock_video, message_text=None)

    mock_result = {"custom_id": "ELN-RAW-20260804-video123", "status": "RAW_RECEIVED"}

    with patch("agents.intake.telegram_intake.IntakeProcessor") as MockProcessor:
        instance = MockProcessor.return_value
        instance.process_incoming_media.return_value = mock_result

        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.handle_studio_media(mock_update, mock_context)

        mock_video.get_file.assert_called_once()
        mock_file.download_to_drive.assert_called_once()

        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "ELN-RAW-20260804-video123" in reply_text
        assert "RAW_RECEIVED" in reply_text


@pytest.mark.asyncio
async def test_help_text_contains_all_commands():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=True)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_start_help(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    reply_text = mock_update.message.reply_text.call_args[0][0]

    assert "/render" in reply_text
    assert "/promote" in reply_text
    assert "/approve" in reply_text
    assert "/whoami" in reply_text
