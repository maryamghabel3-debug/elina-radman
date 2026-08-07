import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import asyncio

pytestmark = pytest.mark.unit


def make_mock_update(is_owner=True, chat_id="12345", username="tester", args=None, message_text=None, chat_data=None, video=None):
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
    mock_message.photo = None
    mock_message.document = None
    mock_message.audio = None
    mock_message.voice = None

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = args or []
    mock_context.chat_data = chat_data if chat_data is not None else {}

    return mock_update, mock_context


# 1. /plan without ID returns usage
@pytest.mark.asyncio
async def test_cmd_plan_without_id_returns_usage():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=True, args=[])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("استفاده: /plan ELN-BUNDLE-...")


# 2. /plan with ID activates plan_mode and stores target id
@pytest.mark.asyncio
async def test_cmd_plan_with_id_activates_mode():
    import scripts.elina_studio_bot as bot_module

    chat_data = {}
    mock_update, mock_context = make_mock_update(is_owner=True, args=["ELN-BUNDLE-123"], chat_data=chat_data)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan(mock_update, mock_context)

    assert chat_data.get("plan_mode") is True
    assert chat_data.get("plan_target_id") == "ELN-BUNDLE-123"
    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "حالت برنامه‌ریزی ادیت فعال شد" in reply


# 3. /plan_cancel clears plan session
@pytest.mark.asyncio
async def test_cmd_plan_cancel_clears_session():
    import scripts.elina_studio_bot as bot_module

    chat_data = {"plan_mode": True, "plan_target_id": "ELN-BUNDLE-123", "plan_preview": "some_preview"}
    mock_update, mock_context = make_mock_update(is_owner=True, chat_data=chat_data)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan_cancel(mock_update, mock_context)

    assert chat_data.get("plan_mode") is False
    assert chat_data.get("plan_target_id") is None
    assert chat_data.get("plan_preview") is None
    mock_update.message.reply_text.assert_called_once_with("❌ حالت برنامه‌ریزی ادیت لغو شد.")


# 4. plain text in plan_mode goes to interpreter and returns preview
@pytest.mark.asyncio
async def test_plain_text_in_plan_mode_returns_preview():
    import scripts.elina_studio_bot as bot_module

    chat_data = {"plan_mode": True, "plan_target_id": "ELN-BUNDLE-123"}
    # Plain text instruction
    text = "شات اول از صفر تا 2.5\nصدای اصلی قطع شود"
    mock_update, mock_context = make_mock_update(is_owner=True, message_text=text, chat_data=chat_data)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.handle_studio_media(mock_update, mock_context)

    # Assert plan was parsed and saved to preview
    assert chat_data.get("plan_preview") is not None
    plan = chat_data["plan_preview"]
    assert plan.target_custom_id == "ELN-BUNDLE-123"
    assert len(plan.shots) == 1
    assert plan.shots[0].shot_index == 1
    assert plan.shots[0].start_sec == 0.0
    assert plan.shots[0].end_sec == 2.5
    assert plan.mute_original_audio is True

    # Assert preview reply was sent with transition options
    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "برداشت من از برنامه ادیت:" in reply
    assert "/plan_ok" in reply
    assert "/plan_cancel" in reply


# 5. plain text outside plan_mode returns guidance instead of upload
@pytest.mark.asyncio
async def test_plain_text_outside_plan_mode_returns_guidance():
    import scripts.elina_studio_bot as bot_module

    chat_data = {"plan_mode": False}
    mock_update, mock_context = make_mock_update(is_owner=True, message_text="سلام چطورید؟", chat_data=chat_data)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.handle_studio_media(mock_update, mock_context)

    # Check that guidance message is sent, no intake upload
    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "برای برنامه‌ریزی ادیت" in reply
    assert "/plan" in reply


# 6. /plan_ok without preview returns proper message
@pytest.mark.asyncio
async def test_cmd_plan_ok_without_preview():
    import scripts.elina_studio_bot as bot_module

    chat_data = {"plan_mode": True, "plan_preview": None}
    mock_update, mock_context = make_mock_update(is_owner=True, chat_data=chat_data)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan_ok(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("هیچ برنامه‌ای برای تأیید وجود ندارد.")


# 7. /plan_ok with preview returns success registration message
@pytest.mark.asyncio
async def test_cmd_plan_ok_with_preview():
    import scripts.elina_studio_bot as bot_module

    chat_data = {"plan_mode": True, "plan_preview": "fake_plan_object"}
    mock_update, mock_context = make_mock_update(is_owner=True, chat_data=chat_data)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan_ok(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "ثبت شد" in reply
    assert "اجرای رندر" in reply


# 8. non-owner cannot use /plan
@pytest.mark.asyncio
async def test_non_owner_cannot_use_plan():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=False, args=["ELN-BUNDLE-123"])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("⛔ دسترسی فقط برای مالک است.")


# 9. media upload still works while not in plan mode
@pytest.mark.asyncio
async def test_media_upload_works_outside_plan_mode():
    import scripts.elina_studio_bot as bot_module

    mock_file = MagicMock()
    mock_file.download_to_drive = AsyncMock()

    mock_video = MagicMock()
    mock_video.get_file = AsyncMock(return_value=mock_file)

    # Upload video outside plan mode
    chat_data = {"plan_mode": False}
    mock_update, mock_context = make_mock_update(is_owner=True, video=mock_video, chat_data=chat_data)

    mock_result = {"custom_id": "ELN-RAW-20260804-video123", "status": "RAW_RECEIVED"}

    with patch("agents.intake.telegram_intake.IntakeProcessor") as MockProcessor:
        instance = MockProcessor.return_value
        instance.process_incoming_media.return_value = mock_result

        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.handle_studio_media(mock_update, mock_context)

        # Download and process are called
        mock_video.get_file.assert_called_once()
        mock_file.download_to_drive.assert_called_once()

        # Confirm reply is sent with custom_id
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "ELN-RAW-20260804-video123" in reply_text
