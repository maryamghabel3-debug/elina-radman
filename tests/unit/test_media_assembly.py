import pytest
from agents.editing.recipe_schema import EditRecipe, InputMediaConfig, HookConfig, AudioConfig, AudioDucking
from agents.editing.media_assembly import MediaAssemblyEngine, run_qc_checks

pytestmark = pytest.mark.unit


def make_recipe():
    return EditRecipe(
        content_id="test-1",
        project_type="reel",
        input_media=InputMediaConfig(video_keys=["v.mp4"]),
        hook=HookConfig(enabled=True, text="تو تنبل نیستی", start_sec=0.0, end_sec=3.0),
        audio=AudioConfig(
            voice_key="voice.wav",
            music_key="music.mp3",
            ducking=AudioDucking(enabled=True, target_reduction_db=6),
        ),
    )


def test_build_command_returns_list_with_ffmpeg():
    engine = MediaAssemblyEngine()
    cmd = engine.build_assembly_command(
        recipe=make_recipe(),
        video_path="/tmp/video.mp4",
        voice_path="/tmp/voice.wav",
        music_path="/tmp/music.mp3",
        hook_png_path="/tmp/hook.png",
        output_path="/tmp/out.mp4",
    )
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "/tmp/video.mp4" in cmd
    assert "/tmp/out.mp4" in cmd


def test_build_command_no_content_id_raises():
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.content_id = ""
    with pytest.raises(ValueError):
        engine.build_assembly_command(
            recipe=recipe,
            video_path="/tmp/v.mp4",
            voice_path=None,
            music_path=None,
            hook_png_path=None,
            output_path="/tmp/o.mp4",
        )


def test_build_command_no_video_raises():
    engine = MediaAssemblyEngine()
    with pytest.raises(ValueError):
        engine.build_assembly_command(
            recipe=make_recipe(),
            video_path="",
            voice_path=None,
            music_path=None,
            hook_png_path=None,
            output_path="/tmp/o.mp4",
        )


def test_command_includes_filter_complex_when_audio_and_overlay():
    engine = MediaAssemblyEngine()
    cmd = engine.build_assembly_command(
        recipe=make_recipe(),
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path="/tmp/m.mp3",
        hook_png_path="/tmp/h.png",
        output_path="/tmp/o.mp4",
    )
    assert "-filter_complex" in cmd
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "afftdn" in filter_arg
    assert "sidechaincompress" in filter_arg
    assert "amix" in filter_arg
    assert "loudnorm" in filter_arg
    assert "overlay" in filter_arg


def test_command_uses_recipe_resolution_and_fps():
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.export.resolution = "1080x1920"
    recipe.export.fps = 30
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
    )
    assert "1080x1920" in cmd
    assert "30" in cmd


def test_qc_returns_error_when_file_missing(tmp_path):
    recipe = make_recipe()
    errors = run_qc_checks(str(tmp_path / "nonexistent.mp4"), recipe)
    assert any("does not exist" in e for e in errors)


def test_qc_returns_error_when_file_too_small(tmp_path):
    output = tmp_path / "tiny.mp4"
    output.write_bytes(b"x")  # 1 byte
    recipe = make_recipe()
    errors = run_qc_checks(str(output), recipe)
    assert any("nearly empty" in e for e in errors)
