"""M30 — tests for the /imageclip Studio Bot command."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY

pytestmark = pytest.mark.unit


def make_mock_update(is_owner=True, args=None, chat_id="12345", username="tester"):
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
    mock_message.text = "/imageclip " + " ".join(args) if args else "/imageclip"
    mock_message.caption = None

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = args or []

    return mock_update, mock_context, mock_msg_with_edit


def _last_reply(mock_update):
    return mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_non_owner_cannot_use_imageclip():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(
        is_owner=False, args=["ELN-RAW-20260910-abc123"]
    )

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_imageclip(mock_update, mock_context)

    reply = _last_reply(mock_update)
    assert "⛔" in reply
    assert "دسترسی" in reply


@pytest.mark.asyncio
async def test_missing_arguments_returns_persian_usage():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(is_owner=True, args=[])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_imageclip(mock_update, mock_context)

    reply = _last_reply(mock_update)
    assert "❌" in reply
    assert "/imageclip" in reply
    assert "ELN-RAW" in reply


@pytest.mark.asyncio
async def test_too_many_arguments_returns_persian_usage():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(
        is_owner=True, args=["ELN-RAW-1", "3", "zoom_in", "contain", "extra"]
    )

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_imageclip(mock_update, mock_context)

    reply = _last_reply(mock_update)
    assert "❌" in reply
    assert "دستور نامعتبر" in reply


@pytest.mark.asyncio
async def test_invalid_duration_returns_clear_persian_error():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(
        is_owner=True, args=["ELN-RAW-1", "abc", "zoom_in", "contain"]
    )

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_imageclip(mock_update, mock_context)

    reply = _last_reply(mock_update)
    assert "❌" in reply
    assert "مدت زمان" in reply


@pytest.mark.asyncio
async def test_invalid_motion_returns_clear_persian_error():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(
        is_owner=True, args=["ELN-RAW-1", "3", "fly", "contain"]
    )

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_imageclip(mock_update, mock_context)

    reply = _last_reply(mock_update)
    assert "❌" in reply
    assert "حرکت" in reply
    assert "zoom_in" in reply


@pytest.mark.asyncio
async def test_invalid_fit_returns_clear_persian_error():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(
        is_owner=True, args=["ELN-RAW-1", "3", "zoom_in", "stretch"]
    )

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_imageclip(mock_update, mock_context)

    reply = _last_reply(mock_update)
    assert "❌" in reply
    assert "نمایش" in reply
    assert "contain" in reply and "cover" in reply


@pytest.mark.asyncio
async def test_source_not_found_returns_persian_error():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, msg = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-ghost"]
    )

    with patch("agents.db.supabase_client.ElinaDB") as MockDB:
        MockDB.return_value.get_content_by_custom_id.return_value = None
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_imageclip(mock_update, mock_context)

    MockDB.return_value.get_content_by_custom_id.assert_called_once_with(
        "ELN-RAW-20260910-ghost"
    )
    assert "پیدا نشد" in msg.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_reel_source_rejected():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, msg = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-video1"]
    )

    item = {
        "id": "uuid-1",
        "custom_id": "ELN-RAW-20260910-video1",
        "content_type": "reel",
        "media_keys": ["intake/20260910/shot.mp4"],
    }
    with patch("agents.db.supabase_client.ElinaDB") as MockDB:
        MockDB.return_value.get_content_by_custom_id.return_value = item
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_imageclip(mock_update, mock_context)

    assert "single_post" in msg.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_non_image_media_key_rejected():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, msg = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-mp4asimage"]
    )

    item = {
        "id": "uuid-2",
        "custom_id": "ELN-RAW-20260910-mp4asimage",
        "content_type": "single_post",
        "media_keys": ["intake/20260910/ELN-RAW-20260910-mp4asimage.mp4"],
    }
    with patch("agents.db.supabase_client.ElinaDB") as MockDB:
        MockDB.return_value.get_content_by_custom_id.return_value = item
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_imageclip(mock_update, mock_context)

    assert "تصویر" in msg.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_success_returns_new_reel_eln_raw_id(tmp_path):
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, msg = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-pic", "3", "zoom_in", "contain"]
    )

    item = {
        "id": "uuid-3",
        "custom_id": "ELN-RAW-20260910-pic",
        "content_type": "single_post",
        "media_keys": ["intake/20260910/ELN-RAW-20260910-pic.jpg"],
    }

    def fake_download(storage_path, local_path):
        with open(local_path, "wb") as f:
            f.write(b"fake image bytes")
        return local_path

    def fake_build(image_path, output_path, **kwargs):
        with open(output_path, "wb") as f:
            f.write(b"fake mp4 bytes")
        return output_path

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage, \
         patch.object(bot_module, "StillImageClipBuilder") as MockBuilder, \
         patch("agents.intake.telegram_intake.IntakeProcessor") as MockProcessor:
        MockDB.return_value.get_content_by_custom_id.return_value = item
        MockStorage.return_value.download_file.side_effect = fake_download
        MockBuilder.return_value.build.side_effect = fake_build
        MockProcessor.return_value.process_incoming_media.return_value = {
            "custom_id": "ELN-RAW-20260910-newclip",
            "storage_path": "intake/20260910/ELN-RAW-20260910-newclip.mp4",
            "status": "RAW_RECEIVED",
        }
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_imageclip(mock_update, mock_context)

    # the builder received the downloaded image, the requested options
    build_kwargs = MockBuilder.return_value.build.call_args
    assert build_kwargs.kwargs.get("duration_sec") == 3.0
    assert build_kwargs.kwargs.get("motion") == "zoom_in"
    assert build_kwargs.kwargs.get("fit") == "contain"

    # registered as a new reel via IntakeProcessor with file_ext=".mp4"
    MockProcessor.return_value.process_incoming_media.assert_called_once_with(
        local_file_path=ANY,
        file_ext=".mp4",
        caption=ANY,
        telegram_message_id="1",
        sender_name="tester",
        source="imageclip",
    )

    reply = msg.edit_text.call_args[0][0]
    assert "✅" in reply
    assert "ELN-RAW-20260910-newclip" in reply
    assert "RAW_RECEIVED" in reply


@pytest.mark.asyncio
async def test_defaults_when_only_custom_id_given(tmp_path):
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, msg = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-pic"]
    )

    item = {
        "id": "uuid-4",
        "custom_id": "ELN-RAW-20260910-pic",
        "content_type": "single_post",
        "media_keys": ["intake/20260910/ELN-RAW-20260910-pic.jpg"],
    }

    def fake_download(storage_path, local_path):
        with open(local_path, "wb") as f:
            f.write(b"fake")
        return local_path

    def fake_build(image_path, output_path, **kwargs):
        with open(output_path, "wb") as f:
            f.write(b"fake mp4")
        return output_path

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage, \
         patch.object(bot_module, "StillImageClipBuilder") as MockBuilder, \
         patch("agents.intake.telegram_intake.IntakeProcessor") as MockProcessor:
        MockDB.return_value.get_content_by_custom_id.return_value = item
        MockStorage.return_value.download_file.side_effect = fake_download
        MockBuilder.return_value.build.side_effect = fake_build
        MockProcessor.return_value.process_incoming_media.return_value = {
            "custom_id": "ELN-RAW-20260910-default",
            "status": "RAW_RECEIVED",
        }
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_imageclip(mock_update, mock_context)

    build_kwargs = MockBuilder.return_value.build.call_args.kwargs
    assert build_kwargs["duration_sec"] == 3.0
    assert build_kwargs["motion"] == "zoom_in"
    assert build_kwargs["fit"] == "contain"


@pytest.mark.asyncio
async def test_builder_failure_returns_persian_error():
    import scripts.elina_studio_bot as bot_module
    from agents.editing.still_image_clip import StillImageClipError

    mock_update, mock_context, msg = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-pic", "1000"]
    )

    item = {
        "id": "uuid-5",
        "custom_id": "ELN-RAW-20260910-pic",
        "content_type": "single_post",
        "media_keys": ["intake/20260910/ELN-RAW-20260910-pic.jpg"],
    }

    def fake_download(storage_path, local_path):
        with open(local_path, "wb") as f:
            f.write(b"fake")
        return local_path

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage, \
         patch.object(bot_module, "StillImageClipBuilder") as MockBuilder:
        MockDB.return_value.get_content_by_custom_id.return_value = item
        MockStorage.return_value.download_file.side_effect = fake_download
        MockBuilder.return_value.build.side_effect = StillImageClipError(
            "duration_sec must be between 0.5 and 300.0 seconds, got: 1000.0"
        )
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_imageclip(mock_update, mock_context)

    reply = msg.edit_text.call_args[0][0]
    assert "❌" in reply
    assert "ساخت کلیپ" in reply


@pytest.mark.asyncio
async def test_help_text_contains_imageclip():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(is_owner=True)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_start_help(mock_update, mock_context)

    reply = _last_reply(mock_update)
    assert "/imageclip" in reply
    assert "zoom_in" in reply
    assert "contain" in reply and "cover" in reply
