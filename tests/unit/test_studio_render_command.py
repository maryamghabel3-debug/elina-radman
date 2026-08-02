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

    # Mock the message that will be returned by reply_text (msg with edit_text)
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


# === Tests for parse_render_command ===

def test_parse_legacy_hook_text():
    """Legacy single-line: /render ELN-XXX hook text"""
    from scripts.elina_studio_bot import parse_render_command

    result = parse_render_command("/render ELN-RAW-TEST تو تنبل نیستی")
    assert result["custom_id"] == "ELN-RAW-TEST"
    assert result["legacy_hook_text"] == "تو تنبل نیستی"
    assert result["hook"] is None
    assert result["segments"] == []


def test_parse_hook_on_second_line():
    """Extended syntax with hook= on second line"""
    from scripts.elina_studio_bot import parse_render_command

    text = "/render ELN-RAW-TEST\nhook=تو تنبل نیستی"
    result = parse_render_command(text)
    assert result["custom_id"] == "ELN-RAW-TEST"
    assert result["hook"] == "تو تنبل نیستی"
    assert result["legacy_hook_text"] is None


def test_parse_three_clips_with_timing():
    """Parse 3 clipN entries with mixed timing formats"""
    from scripts.elina_studio_bot import parse_render_command

    text = "/render ELN-RAW-TEST\nclip1=raw/shot1.mp4:0-3\nclip2=raw/shot2.mp4:1.2-4\nclip3=raw/shot3.mp4:0-"
    result = parse_render_command(text)
    assert result["custom_id"] == "ELN-RAW-TEST"
    assert len(result["segments"]) == 3

    assert result["segments"][0]["key"] == "raw/shot1.mp4"
    assert result["segments"][0]["start_sec"] == 0.0
    assert result["segments"][0]["end_sec"] == 3.0

    assert result["segments"][1]["key"] == "raw/shot2.mp4"
    assert result["segments"][1]["start_sec"] == 1.2
    assert result["segments"][1]["end_sec"] == 4.0

    assert result["segments"][2]["key"] == "raw/shot3.mp4"
    assert result["segments"][2]["start_sec"] == 0.0
    assert result["segments"][2]["end_sec"] is None


def test_parse_rejects_negative_start():
    """Negative start_sec should raise ValueError"""
    from scripts.elina_studio_bot import parse_render_command

    text = "/render ELN-TEST\nclip1=raw/shot.mp4:-1-5"
    with pytest.raises(ValueError, match="negative"):
        parse_render_command(text)


def test_parse_rejects_end_leq_start():
    """end_sec <= start_sec should raise ValueError"""
    from scripts.elina_studio_bot import parse_render_command

    text = "/render ELN-TEST\nclip1=raw/shot.mp4:5-3"
    with pytest.raises(ValueError, match="end_sec must be greater than start_sec"):
        parse_render_command(text)


def test_parse_ignores_comments_and_empty_lines():
    """Comments (#) and empty lines should be ignored"""
    from scripts.elina_studio_bot import parse_render_command

    text = "/render ELN-TEST\n# this is a comment\n\nclip1=raw/a.mp4\n\n# another"
    result = parse_render_command(text)
    assert result["custom_id"] == "ELN-TEST"
    assert len(result["segments"]) == 1


def test_parse_voice_and_music_keys():
    """voice= and music= should be parsed correctly"""
    from scripts.elina_studio_bot import parse_render_command

    text = "/render ELN-TEST\nvoice=voices/voice_a.wav\nmusic=music/ambient.mp3"
    result = parse_render_command(text)
    assert result["voice_key"] == "voices/voice_a.wav"
    assert result["music_key"] == "music/ambient.mp3"


def test_parse_full_multiline_command():
    """Full extended command with hook, voice, music, and clips"""
    from scripts.elina_studio_bot import parse_render_command

    text = "/render ELN-RAW-TEST\nhook=تو تنبل نیستی\nvoice=voices/voice_a.wav\nmusic=music/ambient_deep.mp3\nclip1=raw/shot1.mp4:0-3\nclip2=raw/shot2.mp4:1.2-4\nclip3=raw/shot3.mp4:0-"
    result = parse_render_command(text)
    assert result["custom_id"] == "ELN-RAW-TEST"
    assert result["hook"] == "تو تنبل نیستی"
    assert result["voice_key"] == "voices/voice_a.wav"
    assert result["music_key"] == "music/ambient_deep.mp3"
    assert len(result["segments"]) == 3


def test_parse_invalid_custom_id():
    """Invalid custom_id pattern should raise ValueError"""
    from scripts.elina_studio_bot import parse_render_command

    with pytest.raises(ValueError, match="Invalid custom_id"):
        parse_render_command("/render BAD-ID")


# === Tests for cmd_render with segments/voice/music ===

@pytest.mark.asyncio
async def test_cmd_render_with_segments():
    """cmd_render should call orchestrator with segments when provided"""
    import scripts.elina_studio_bot as bot_module

    message_text = "/render ELN-TEST\nclip1=raw/shot1.mp4:0-3\nclip2=raw/shot2.mp4:1.2-4"
    mock_update, mock_context, mock_msg_with_edit = make_mock_update(
        is_owner=True, message_text=message_text
    )

    captured_args = {}

    class FakeOrchestrator:
        def render_content(self, custom_id, hook_text=None, actor=None, video_segments=None, voice_key=None, music_key=None):
            captured_args.update({
                "custom_id": custom_id,
                "hook_text": hook_text,
                "video_segments": video_segments,
                "voice_key": voice_key,
                "music_key": music_key,
            })
            return {"ok": True, "custom_id": custom_id, "output_key": "out.mp4", "status": "READY_FOR_REVIEW"}

    with patch.object(bot_module, "EditOrchestrator", lambda: FakeOrchestrator()):
        await bot_module.cmd_render(mock_update, mock_context)

    assert captured_args["custom_id"] == "ELN-TEST"
    assert len(captured_args["video_segments"]) == 2
    assert captured_args["video_segments"][0]["key"] == "raw/shot1.mp4"
    assert captured_args["video_segments"][0]["start_sec"] == 0.0
    assert captured_args["video_segments"][0]["end_sec"] == 3.0
    assert captured_args["video_segments"][1]["start_sec"] == 1.2
    assert captured_args["video_segments"][1]["end_sec"] == 4.0


@pytest.mark.asyncio
async def test_cmd_render_with_voice_and_music():
    """cmd_render should pass voice_key and music_key to orchestrator"""
    import scripts.elina_studio_bot as bot_module

    message_text = "/render ELN-TEST\nvoice=voices/v.wav\nmusic=music/m.mp3"
    mock_update, mock_context, mock_msg_with_edit = make_mock_update(
        is_owner=True, message_text=message_text
    )

    captured_args = {}

    class FakeOrchestrator:
        def render_content(self, custom_id, hook_text=None, actor=None, video_segments=None, voice_key=None, music_key=None):
            captured_args.update({
                "voice_key": voice_key,
                "music_key": music_key,
            })
            return {"ok": True, "custom_id": custom_id, "output_key": "out.mp4", "status": "READY_FOR_REVIEW"}

    with patch.object(bot_module, "EditOrchestrator", lambda: FakeOrchestrator()):
        await bot_module.cmd_render(mock_update, mock_context)

    assert captured_args["voice_key"] == "voices/v.wav"
    assert captured_args["music_key"] == "music/m.mp3"


@pytest.mark.asyncio
async def test_cmd_render_unauthorized_does_nothing():
    """Unauthorized user should not trigger any reply or orchestrator call."""
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(is_owner=False, message_text="/render ELN-TEST")

    await bot_module.cmd_render(mock_update, mock_context)

    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_cmd_render_invalid_input_shows_error():
    """Invalid input should reply with error message."""
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, _ = make_mock_update(is_owner=True, message_text="/render BAD-ID")

    await bot_module.cmd_render(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    call_arg = mock_update.message.reply_text.call_args[0][0]
    assert "❌" in call_arg or "نامعتبر" in call_arg


@pytest.mark.asyncio
async def test_cmd_render_calls_orchestrator():
    """cmd_render should call orchestrator with correct parameters."""
    import scripts.elina_studio_bot as bot_module

    mock_update, mock_context, mock_msg_with_edit = make_mock_update(
        is_owner=True, message_text="/render ELN-TEST"
    )

    orchestrator_called = []

    class FakeOrchestrator:
        def render_content(self, **kwargs):
            orchestrator_called.append(kwargs)
            return {"ok": True, "custom_id": "ELN-TEST", "output_key": "out.mp4", "status": "READY_FOR_REVIEW"}

    with patch.object(bot_module, "EditOrchestrator", lambda: FakeOrchestrator()):
        await bot_module.cmd_render(mock_update, mock_context)

    # Orchestrator should be called
    assert len(orchestrator_called) == 1
    assert orchestrator_called[0]["custom_id"] == "ELN-TEST"
