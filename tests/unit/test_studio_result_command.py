"""M32A — tests for the /result & /download Studio Bot commands."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit

JOB_UUID = "3f6f5c2e-1a2b-4c3d-8e9f-0a1b2c3d4e5f"
SIGNED_URL = "https://supabase.example.co/storage/v1/object/sign/elina-media/renders/final.mp4?token=24h"


def make_mock_update(is_owner=True, args=None, chat_id="12345", username="tester"):
    mock_user = MagicMock()
    mock_user.username = username
    mock_user.first_name = "Test"

    mock_chat = MagicMock()
    mock_chat.id = chat_id if is_owner else "99999"

    mock_message = MagicMock()
    mock_message.chat = mock_chat
    mock_message.from_user = mock_user
    mock_message.reply_text = AsyncMock()
    mock_message.reply_video = AsyncMock()
    mock_message.message_id = 1
    mock_message.text = "/result " + " ".join(args) if args else "/result"
    mock_message.caption = None

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = args or []

    return mock_update, mock_context


def _replies(mock_update):
    return [c[0][0] for c in mock_update.message.reply_text.call_args_list]


@pytest.mark.asyncio
async def test_non_owner_cannot_use_result():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=False, args=[JOB_UUID])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_result(mock_update, mock_context)

    replies = _replies(mock_update)
    assert "⛔" in replies[0]
    assert "دسترسی" in replies[0]
    mock_update.message.reply_video.assert_not_called()


@pytest.mark.asyncio
async def test_no_arguments_returns_persian_usage():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=True, args=[])

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_result(mock_update, mock_context)

    reply = _replies(mock_update)[0]
    assert "❌" in reply
    assert "/result" in reply
    assert "/download" in reply


@pytest.mark.asyncio
async def test_result_by_job_uuid_returns_fresh_signed_url():
    import scripts.elina_studio_bot as bot_module

    job = {
        "id": JOB_UUID,
        "content_id": "ELN-BUNDLE-20260910-shotzero",
        "status": "COMPLETED",
        "output_key": "renders/final.mp4",
    }

    mock_update, mock_context = make_mock_update(is_owner=True, args=[JOB_UUID])

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_render_job_by_id.return_value = job
        MockStorage.return_value.create_signed_url.return_value = SIGNED_URL
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_result(mock_update, mock_context)

    MockJobManager.return_value.get_render_job_by_id.assert_called_once_with(JOB_UUID)
    # fresh 24-hour signed URL (bucket stays private)
    MockStorage.return_value.create_signed_url.assert_called_once_with(
        "renders/final.mp4", 24 * 60 * 60
    )

    replies = _replies(mock_update)
    details = replies[0]
    assert SIGNED_URL in details
    assert "ELN-BUNDLE-20260910-shotzero" in details
    assert JOB_UUID in details
    assert "renders/final.mp4" in details
    assert "۲۴ ساعت" in details

    # direct sendVideo with the signed URL was attempted
    mock_update.message.reply_video.assert_called_once()
    video_kwargs = mock_update.message.reply_video.call_args
    assert SIGNED_URL in (video_kwargs.args + tuple(video_kwargs.kwargs.values()))


@pytest.mark.asyncio
async def test_result_by_content_id_returns_latest_completed_output():
    import scripts.elina_studio_bot as bot_module

    job = {
        "id": "11111111-2222-4333-8444-555555555555",
        "content_id": "ELN-BUNDLE-20260910-shotzero",
        "status": "COMPLETED",
        "output_key": "renders/latest.mp4",
    }

    mock_update, mock_context = make_mock_update(
        is_owner=True, args=["ELN-BUNDLE-20260910-shotzero"]
    )

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_latest_completed_render_for_content.return_value = job
        MockStorage.return_value.create_signed_url.return_value = SIGNED_URL
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_result(mock_update, mock_context)

    MockJobManager.return_value.get_latest_completed_render_for_content.assert_called_once_with(
        "ELN-BUNDLE-20260910-shotzero"
    )
    MockDB.return_value.get_content_by_custom_id.assert_not_called()
    MockStorage.return_value.create_signed_url.assert_called_once_with(
        "renders/latest.mp4", 24 * 60 * 60
    )

    details = _replies(mock_update)[0]
    assert SIGNED_URL in details
    assert "renders/latest.mp4" in details


@pytest.mark.asyncio
async def test_result_fallback_to_edited_media_key():
    import scripts.elina_studio_bot as bot_module

    item = {
        "id": "item-1",
        "custom_id": "ELN-RAW-20260910-abc123",
        "content_type": "reel",
        "media_keys": ["intake/20260910/ELN-RAW-20260910-abc123.mp4"],
        "edited_media_key": "edited/rendered_output.mp4",
    }

    mock_update, mock_context = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-abc123"]
    )

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        # no completed render job -> fallback path
        MockJobManager.return_value.get_latest_completed_render_for_content.return_value = None
        MockDB.return_value.get_content_by_custom_id.return_value = item
        MockStorage.return_value.create_signed_url.return_value = SIGNED_URL
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_result(mock_update, mock_context)

    MockStorage.return_value.create_signed_url.assert_called_once_with(
        "edited/rendered_output.mp4", 24 * 60 * 60
    )

    details = _replies(mock_update)[0]
    assert SIGNED_URL in details
    assert "edited/rendered_output.mp4" in details
    assert "ELN-RAW-20260910-abc123" in details


@pytest.mark.asyncio
async def test_non_completed_job_returns_persian_error():
    import scripts.elina_studio_bot as bot_module

    job = {
        "id": JOB_UUID,
        "content_id": "ELN-BUNDLE-20260910-shotzero",
        "status": "IN_PROGRESS",
        "output_key": None,
    }

    mock_update, mock_context = make_mock_update(is_owner=True, args=[JOB_UUID])

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_render_job_by_id.return_value = job
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_result(mock_update, mock_context)

    reply = _replies(mock_update)[0]
    assert "❌" in reply
    assert "کامل نشده" in reply
    assert "IN_PROGRESS" in reply
    MockStorage.return_value.create_signed_url.assert_not_called()
    mock_update.message.reply_video.assert_not_called()


@pytest.mark.asyncio
async def test_missing_output_key_returns_persian_error():
    import scripts.elina_studio_bot as bot_module

    job = {
        "id": JOB_UUID,
        "content_id": "ELN-BUNDLE-20260910-shotzero",
        "status": "COMPLETED",
        "output_key": None,
    }

    mock_update, mock_context = make_mock_update(is_owner=True, args=[JOB_UUID])

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_render_job_by_id.return_value = job
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_result(mock_update, mock_context)

    reply = _replies(mock_update)[0]
    assert "❌" in reply
    assert "خروجی" in reply
    MockStorage.return_value.create_signed_url.assert_not_called()
    mock_update.message.reply_video.assert_not_called()


@pytest.mark.asyncio
async def test_job_uuid_not_found_returns_persian_error():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=True, args=[JOB_UUID])

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_render_job_by_id.return_value = None
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_result(mock_update, mock_context)

    reply = _replies(mock_update)[0]
    assert "❌" in reply
    assert "پیدا نشد" in reply
    MockStorage.return_value.create_signed_url.assert_not_called()


@pytest.mark.asyncio
async def test_content_not_found_returns_persian_error():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-ghost"]
    )

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_latest_completed_render_for_content.return_value = None
        MockDB.return_value.get_content_by_custom_id.return_value = None
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_result(mock_update, mock_context)

    reply = _replies(mock_update)[0]
    assert "❌" in reply
    assert "پیدا نشد" in reply
    MockStorage.return_value.create_signed_url.assert_not_called()


@pytest.mark.asyncio
async def test_no_completed_render_and_no_edited_key_error():
    import scripts.elina_studio_bot as bot_module

    item = {
        "id": "item-2",
        "custom_id": "ELN-RAW-20260910-newshot",
        "content_type": "single_post",
        "media_keys": ["intake/20260910/ELN-RAW-20260910-newshot.jpg"],
        "edited_media_key": None,
    }

    mock_update, mock_context = make_mock_update(
        is_owner=True, args=["ELN-RAW-20260910-newshot"]
    )

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_latest_completed_render_for_content.return_value = None
        MockDB.return_value.get_content_by_custom_id.return_value = item
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_result(mock_update, mock_context)

    reply = _replies(mock_update)[0]
    assert "❌" in reply
    assert "خروجی رندر کامل‌شده" in reply
    MockStorage.return_value.create_signed_url.assert_not_called()


@pytest.mark.asyncio
async def test_sendvideo_failure_falls_back_to_signed_url_only():
    import scripts.elina_studio_bot as bot_module

    job = {
        "id": JOB_UUID,
        "content_id": "ELN-BUNDLE-20260910-shotzero",
        "status": "COMPLETED",
        "output_key": "renders/long_final.mp4",
    }

    mock_update, mock_context = make_mock_update(is_owner=True, args=[JOB_UUID])
    # Telegram refuses the direct video (file too big for direct upload)
    mock_update.message.reply_video.side_effect = Exception(
        "BadRequest: Failed to get http file: File is too big"
    )

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_render_job_by_id.return_value = job
        MockStorage.return_value.create_signed_url.return_value = SIGNED_URL
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            # must NOT raise
            await bot_module.cmd_result(mock_update, mock_context)

    replies = _replies(mock_update)
    # the signed URL was still delivered in the details message
    assert SIGNED_URL in replies[0]
    # and the exact Persian fallback note was appended
    assert bot_module.RESULT_VIDEO_TOO_BIG_FA in replies
    assert (
        "فایل احتمالاً برای ارسال مستقیم تلگرام بزرگ است؛ از لینک دانلود استفاده کن."
        in replies
    )


@pytest.mark.asyncio
async def test_download_alias_behaves_like_result():
    import scripts.elina_studio_bot as bot_module

    job = {
        "id": JOB_UUID,
        "content_id": "ELN-BUNDLE-20260910-shotzero",
        "status": "COMPLETED",
        "output_key": "renders/final.mp4",
    }

    mock_update, mock_context = make_mock_update(is_owner=True, args=[JOB_UUID])

    with patch("agents.db.supabase_client.ElinaDB") as MockDB, \
         patch("agents.rendering.job_manager.RenderJobManager") as MockJobManager, \
         patch("agents.storage.supabase_storage.ElinaStorage") as MockStorage:
        MockJobManager.return_value.get_render_job_by_id.return_value = job
        MockStorage.return_value.create_signed_url.return_value = SIGNED_URL
        with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
            await bot_module.cmd_download(mock_update, mock_context)

    details = _replies(mock_update)[0]
    assert SIGNED_URL in details
    mock_update.message.reply_video.assert_called_once()


@pytest.mark.asyncio
async def test_help_text_includes_result_and_download():
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context = make_mock_update(is_owner=True)

    with patch.object(bot_module, "OWNER_CHAT_ID", "12345"):
        await bot_module.cmd_start_help(mock_update, mock_context)

    reply = _replies(mock_update)[0]
    assert "/result" in reply
    assert "/download" in reply


# ---------------------------------------------------------------------------
# New read-only RenderJobManager helpers (query shape)
# ---------------------------------------------------------------------------

class _FakeFluent:
    """Records the query chain like the supabase fluent client."""

    def __init__(self, data):
        self._data = data
        self.calls = []

    def select(self, _q):
        return self

    def eq(self, *args):
        self.calls.append(("eq", args))
        return self

    def order(self, *args, **kwargs):
        self.calls.append(("order", args, tuple(sorted(kwargs.items()))))
        return self

    def limit(self, *args):
        self.calls.append(("limit", args))
        return self

    def execute(self):
        class _R:
            data = self._data

        return _R()


def _job_manager_with_fluent(data):
    from agents.rendering.job_manager import RenderJobManager

    fluent = _FakeFluent(data)
    fake_db = MagicMock()
    fake_db.client.table.return_value.select.return_value = fluent
    return RenderJobManager(db=fake_db), fluent


def test_get_render_job_by_id_queries_by_uuid():
    job = {"id": JOB_UUID, "status": "COMPLETED", "output_key": "renders/final.mp4"}
    mgr, fluent = _job_manager_with_fluent([job])

    assert mgr.get_render_job_by_id(JOB_UUID) == job
    assert ("eq", ("id", JOB_UUID)) in fluent.calls
    assert ("limit", (1,)) in fluent.calls


def test_get_latest_completed_render_filters_and_orders():
    job = {"id": "job-x", "content_id": "ELN-BUNDLE-1", "status": "COMPLETED"}
    mgr, fluent = _job_manager_with_fluent([job])

    assert mgr.get_latest_completed_render_for_content("ELN-BUNDLE-1") == job
    assert ("eq", ("content_id", "ELN-BUNDLE-1")) in fluent.calls
    assert ("eq", ("status", "COMPLETED")) in fluent.calls
    assert ("order", ("completed_at",), (("desc", True),)) in fluent.calls
    assert ("limit", (1,)) in fluent.calls


def test_latest_completed_returns_none_when_no_job():
    mgr, _ = _job_manager_with_fluent([])
    assert mgr.get_latest_completed_render_for_content("ELN-BUNDLE-1") is None
    mgr, _ = _job_manager_with_fluent([])
    assert mgr.get_render_job_by_id(JOB_UUID) is None
