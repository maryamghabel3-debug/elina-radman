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
    text = "شات اول از صفر تا 2.5\nصدای اصلی قطع شود"
    mock_update, mock_context = make_mock_update(is_owner=True, message_text=text, chat_data=chat_data)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.handle_studio_media(mock_update, mock_context)

    assert chat_data.get("plan_preview") is not None
    plan = chat_data["plan_preview"]
    assert plan.target_custom_id == "ELN-BUNDLE-123"
    assert len(plan.shots) == 1
    assert plan.shots[0].shot_index == 1
    assert plan.shots[0].start_sec == 0.0
    assert plan.shots[0].end_sec == 2.5
    assert plan.mute_original_audio is True

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

    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "برای برنامه‌ریزی ادیت" in reply
    assert "/plan" in reply


# 6. /plan_ok without preview returns proper message
@pytest.mark.asyncio
async def test_cmd_plan_ok_without_preview():
    import scripts.elina_studio_bot as bot_module

    chat_data = {"plan_mode": True, "plan_preview": None, "plan_target_id": "ELN-BUNDLE-123"}
    mock_update, mock_context = make_mock_update(is_owner=True, chat_data=chat_data)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan_ok(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    reply = mock_update.message.reply_text.call_args[0][0]
    assert "هیچ برنامه‌ای وجود ندارد" in reply


# 7. /plan_ok with preview queues job and returns success queue message
@pytest.mark.asyncio
async def test_cmd_plan_ok_with_preview():
    import scripts.elina_studio_bot as bot_module
    from agents.editing.persian_edit_interpreter import PersianEditPlan, PersianShotInstruction, PersianSFXInstruction

    plan = PersianEditPlan(
        target_mode="custom_id",
        target_custom_id="ELN-BUNDLE-123",
        shots=[PersianShotInstruction(shot_index=1, start_sec=0.0, end_sec=3.0)],
        sound_effects=[PersianSFXInstruction(query_fa="صدای کلید", start_sec=1.5)],
        hook_text="هوک تست",
        confidence=1.0
    )
    chat_data = {"plan_mode": True, "plan_preview": plan, "plan_target_id": "ELN-BUNDLE-123"}
    mock_update, mock_context = make_mock_update(is_owner=True, chat_data=chat_data)

    mock_job = {"id": "job-123", "status": "QUEUED"}

    with patch("agents.rendering.job_manager.RenderJobManager") as MockManager:
        instance = MockManager.return_value
        instance.queue_job.return_value = mock_job

        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_plan_ok(mock_update, mock_context)

        # Check queue_job was called with correct parameters
        instance.queue_job.assert_called_once()

        # Check chat_data was cleared
        assert "plan_preview" not in chat_data
        assert "plan_target_id" not in chat_data
        assert "plan_mode" not in chat_data

        # Check message was updated to success queue message
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "✅ رندر وارد صف شد." in reply_text
        assert "job-123" in reply_text


# 8. /plan_ok serializes shot removals so the worker can honor them
@pytest.mark.asyncio
async def test_cmd_plan_ok_serializes_shot_removal():
    import scripts.elina_studio_bot as bot_module
    from agents.editing.persian_edit_interpreter import PersianEditPlan, PersianShotInstruction

    plan = PersianEditPlan(
        target_mode="custom_id",
        target_custom_id="ELN-BUNDLE-123",
        shots=[
            PersianShotInstruction(shot_index=1, start_sec=0.0, end_sec=3.0),
            PersianShotInstruction(shot_index=2, remove=True),
        ],
        confidence=1.0
    )
    chat_data = {"plan_mode": True, "plan_preview": plan, "plan_target_id": "ELN-BUNDLE-123"}
    mock_update, mock_context = make_mock_update(is_owner=True, chat_data=chat_data)

    with patch("agents.rendering.job_manager.RenderJobManager") as MockManager:
        instance = MockManager.return_value
        instance.queue_job.return_value = {"id": "job-rem", "status": "QUEUED"}

        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_plan_ok(mock_update, mock_context)

        instance.queue_job.assert_called_once()
        plan_data = instance.queue_job.call_args.kwargs["plan_data"]
        assert plan_data["shots"] == [
            {"index": 1, "start": 0.0, "end": 3.0, "remove": False},
            {"index": 2, "start": 0.0, "end": None, "remove": True},
        ]


# 9. failed render queuing shows error and keeps plan
@pytest.mark.asyncio
async def test_cmd_plan_ok_failed_render():
    import scripts.elina_studio_bot as bot_module
    from agents.editing.persian_edit_interpreter import PersianEditPlan

    plan = PersianEditPlan(
        target_mode="custom_id",
        target_custom_id="ELN-BUNDLE-123",
        confidence=1.0
    )
    chat_data = {"plan_mode": True, "plan_preview": plan, "plan_target_id": "ELN-BUNDLE-123"}
    mock_update, mock_context = make_mock_update(is_owner=True, chat_data=chat_data)

    with patch("agents.rendering.job_manager.RenderJobManager") as MockManager:
        instance = MockManager.return_value
        instance.queue_job.side_effect = Exception("Supabase connection error")

        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_plan_ok(mock_update, mock_context)

        # Check plan was NOT cleared on failure
        assert chat_data.get("plan_preview") is plan
        assert chat_data.get("plan_target_id") == "ELN-BUNDLE-123"

        # Check reply shows failure
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "❌ خطا در ثبت رندر" in reply_text
        assert "Supabase connection error" in reply_text


# 10. non-owner cannot use /plan
@pytest.mark.asyncio
async def test_non_owner_cannot_use_plan():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=False, args=["ELN-BUNDLE-123"])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_plan(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once_with("⛔ دسترسی فقط برای مالک است.")


# 11. media upload still works while not in plan mode
@pytest.mark.asyncio
async def test_media_upload_works_outside_plan_mode():
    import scripts.elina_studio_bot as bot_module

    mock_file = MagicMock()
    mock_file.download_to_drive = AsyncMock()

    mock_video = MagicMock()
    mock_video.get_file = AsyncMock(return_value=mock_file)

    chat_data = {"plan_mode": False}
    mock_update, mock_context = make_mock_update(is_owner=True, video=mock_video, chat_data=chat_data)

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


# 12. Bundle ID fix produces correct format
def test_bundle_id_fix_produces_correct_format():
    from agents.studio.bundle_manager import VideoBundleManager

    mock_db = MagicMock()
    mock_db.get_content_by_custom_id.side_effect = lambda cid: {
        "id": "1", "custom_id": cid, "content_type": "reel", "media_keys": ["path/1.mp4"]
    }

    manager = VideoBundleManager(db=mock_db)
    result = manager.create_bundle("shot-zero", ["ELN-RAW-1", "ELN-RAW-2"], "owner")

    assert result["ok"] is True
    custom_id = result["custom_id"]

    assert custom_id.startswith("ELN-BUNDLE-")
    assert not custom_id.startswith("ELN-BUNDLE-ELN-BUNDLE-")


# 13. /plan_ok serializes SFX entries with fades so the worker can resolve them
@pytest.mark.asyncio
async def test_cmd_plan_ok_serializes_sfx_with_fades():
    import scripts.elina_studio_bot as bot_module
    from agents.editing.persian_edit_interpreter import PersianEditPlan, PersianShotInstruction, PersianSFXInstruction

    plan = PersianEditPlan(
        target_mode="custom_id",
        target_custom_id="ELN-BUNDLE-123",
        shots=[PersianShotInstruction(shot_index=1, start_sec=0.0, end_sec=3.0)],
        sound_effects=[PersianSFXInstruction(query_fa="صدای کلید", start_sec=1.5, gain_db=-6, fade_in_sec=0.2, fade_out_sec=0.4)],
        confidence=1.0
    )
    chat_data = {"plan_mode": True, "plan_preview": plan, "plan_target_id": "ELN-BUNDLE-123"}
    mock_update, mock_context = make_mock_update(is_owner=True, chat_data=chat_data)

    with patch("agents.rendering.job_manager.RenderJobManager") as MockManager:
        instance = MockManager.return_value
        instance.queue_job.return_value = {"id": "job-sfx", "status": "QUEUED"}

        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_plan_ok(mock_update, mock_context)

        plan_data = instance.queue_job.call_args.kwargs["plan_data"]
        assert plan_data["sfx"] == [{
            "query": "صدای کلید",
            "start": 1.5,
            "gain": -6,
            "fade_in": 0.2,
            "fade_out": 0.4,
        }]
