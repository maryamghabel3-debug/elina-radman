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


def test_command_includes_adelay_for_sfx():
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    sfx_items = [
        {
            "path": "sfx.mp3",
            "start_sec": 2.5,
            "gain_db": -5,
            "fade_in_sec": 0.5,
            "fade_out_sec": 1.0,
            "attribution": None,
        }
    ]
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
        sfx_items=sfx_items,
    )
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "adelay=2500|2500" in filter_arg


def test_command_includes_volume_gain_for_sfx():
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    sfx_items = [
        {
            "path": "sfx.mp3",
            "start_sec": 0.0,
            "gain_db": -8,
            "fade_in_sec": 0.0,
            "fade_out_sec": 0.0,
            "attribution": None,
        }
    ]
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
        sfx_items=sfx_items,
    )
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "volume=-8dB" in filter_arg


def test_command_without_sfx_is_backward_compatible():
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
        sfx_items=None,
    )
    if "-filter_complex" in cmd:
        filter_arg = cmd[cmd.index("-filter_complex") + 1]
        assert "adelay" not in filter_arg
    else:
        assert True


def test_multiple_sfx_inputs_are_included():
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    sfx_items = [
        {
            "path": "sfx1.mp3",
            "start_sec": 1.0,
            "gain_db": -3,
            "fade_in_sec": 0.0,
            "fade_out_sec": 0.0,
            "attribution": "Attribution 1",
        },
        {
            "path": "sfx2.mp3",
            "start_sec": 4.5,
            "gain_db": -6,
            "fade_in_sec": 1.0,
            "fade_out_sec": 0.5,
            "attribution": "Attribution 2",
        },
    ]
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path="/tmp/music.mp3",
        hook_png_path="/tmp/hook.png",
        output_path="/tmp/o.mp4",
        sfx_items=sfx_items,
    )

    # Assert both paths are added as ffmpeg inputs
    inputs = [cmd[i+1] for i in range(len(cmd)) if cmd[i] == "-i"]
    assert "sfx1.mp3" in inputs
    assert "sfx2.mp3" in inputs

    # Assert final filter has both
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "sfx_0_clean" in filter_arg
    assert "sfx_1_clean" in filter_arg


def test_overlay_ducking_loudnorm_and_sfx_can_coexist():
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    sfx_items = [
        {
            "path": "sfx1.mp3",
            "start_sec": 1.5,
            "gain_db": -3,
            "fade_in_sec": 0.5,
            "fade_out_sec": 0.5,
            "attribution": None,
        }
    ]
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path="/tmp/music.mp3",
        hook_png_path="/tmp/hook.png",
        output_path="/tmp/o.mp4",
        sfx_items=sfx_items,
    )
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "afftdn" in filter_arg
    assert "sidechaincompress" in filter_arg
    assert "amix" in filter_arg
    assert "loudnorm" in filter_arg
    assert "overlay" in filter_arg
    assert "adelay" in filter_arg


def test_build_command_keeps_base_audio_when_requested():
    """use_base_audio=True must mix the base video audio into the final audio."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio = AudioConfig(voice_key=None, music_key=None)
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
        use_base_audio=True,
    )
    assert "-filter_complex" in cmd
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "[0:a]aresample=48000,aformat=channel_layouts=stereo[base_audio]" in filter_arg
    assert "[base_audio]loudnorm" in filter_arg
    assert "-map" in cmd and "[final_audio]" in cmd


def test_build_command_default_no_base_audio():
    """Default use_base_audio=False must not reference input 0 audio."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio = AudioConfig(voice_key=None, music_key=None)
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
    )
    assert "-filter_complex" not in cmd
    assert "base_audio" not in cmd


def test_build_command_maps_input_video_without_brackets_when_no_overlay():
    """With a filter graph but no hook overlay, the video must be mapped as
    plain input reference '0:v' (bracketed '[0:v]' is not a valid -map label)."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio = AudioConfig(voice_key="voice.wav", music_key=None)
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
    )
    assert "-filter_complex" in cmd
    assert "-map" in cmd
    assert "0:v" in cmd
    assert "[0:v]" not in cmd
    assert "[final_audio]" in cmd


def test_build_command_maps_overlay_label_when_hook_present():
    """With a hook overlay, the video is mapped from the graph label [final_video]."""
    engine = MediaAssemblyEngine()
    cmd = engine.build_assembly_command(
        recipe=make_recipe(),
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path="/tmp/music.mp3",
        hook_png_path="/tmp/hook.png",
        output_path="/tmp/o.mp4",
    )
    assert "[final_video]" in cmd


def test_build_command_applies_music_gain_db():
    """Test A — music_gain_db appears in FFmpeg graph:
    The generated command/filter graph contains a volume filter for music,
    and it applies the specified gain_db."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio.music_gain_db = -14

    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path="/tmp/music.mp3",
        hook_png_path=None,
        output_path="/tmp/o.mp4",
    )
    assert "-filter_complex" in cmd
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    # Expect the volume filter applied to music stream (input index 1 here because voice is None)
    assert "[1:a]volume=-14dB[music_gained]" in filter_arg


def test_build_command_missing_music_gain_preserves_default():
    """Test B — missing music_gain_db preserves default:
    Assert old/default graph behavior (-12dB default) is preserved when music_gain_db is missing/None."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio.music_gain_db = None

    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path="/tmp/music.mp3",
        hook_png_path=None,
        output_path="/tmp/o.mp4",
    )
    assert "-filter_complex" in cmd
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    # Default is -12dB
    assert "[1:a]volume=-12dB[music_gained]" in filter_arg


def test_build_command_all_audio_mix_and_music_gain_applied_once():
    """Test C — music + voice + SFX + base audio:
    Build a scenario with all audio inputs. Assert the filter graph includes
    all expected inputs in amix and music gain is applied exactly once."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio.music_gain_db = -5

    sfx_items = [
        {
            "path": "sfx.mp3",
            "start_sec": 1.0,
            "gain_db": -3,
        }
    ]

    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path="/tmp/music.mp3",
        hook_png_path="/tmp/hook.png",
        output_path="/tmp/o.mp4",
        sfx_items=sfx_items,
        use_base_audio=True,
    )
    assert "-filter_complex" in cmd
    filter_arg = cmd[cmd.index("-filter_complex") + 1]

    # Music gain applied once
    assert filter_arg.count("volume=-5dB") == 1
    # Music gained stream goes into amix / ducking sidechain
    assert "[music_gained]" in filter_arg
    # sfx and base audio are mixed
    assert "sfx_0_clean" in filter_arg
    assert "base_audio" in filter_arg


def test_build_command_mute_original_keeps_music_gain_drops_base_audio():
    """Test D — mute_original=True + music:
    Assert base audio is not included, and music gain still applies."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio.music_gain_db = -10

    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path="/tmp/music.mp3",
        hook_png_path=None,
        output_path="/tmp/o.mp4",
        use_base_audio=False,  # mute original is True
    )
    assert "-filter_complex" in cmd
    filter_arg = cmd[cmd.index("-filter_complex") + 1]

    # No base_audio mixed
    assert "base_audio" not in filter_arg
    # Music gain still applied
    assert "[1:a]volume=-10dB[music_gained]" in filter_arg


# === New Polish Audio Suite Tests ===

def test_sfx_loudness_normalization():
    """SFX with normalize_loudness=True adds loudnorm filter before volume."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    sfx_items = [
        {
            "path": "sfx.mp3",
            "start_sec": 1.0,
            "gain_db": -5,
            "normalize_loudness": True,
        }
    ]
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
        sfx_items=sfx_items,
    )
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    
    # Assert loudnorm is present
    assert "loudnorm=I=-16:TP=-1.5:LRA=11" in filter_arg
    # Assert loudnorm comes before volume
    assert "loudnorm=I=-16:TP=-1.5:LRA=11,volume=-5dB" in filter_arg


def test_sfx_background_bed_loop_and_trim():
    """SFX with background_bed=True loops infinitely and trims to total video duration."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    sfx_items = [
        {
            "path": "ambient.mp3",
            "background_bed": True,
            "fade_in_sec": 0.5,
            "fade_out_sec": 1.0,
            "gain_db": -12,
            "normalize_loudness": False,
        }
    ]
    
    # Specify total video duration = 15.5 seconds
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path=None,
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
        sfx_items=sfx_items,
        video_duration=15.5,
    )
    
    # Verify -stream_loop -1 is placed right before input
    inputs = []
    for idx, arg in enumerate(cmd):
        if arg == "-i":
            # get the preceding args if it was loop
            if idx >= 2 and cmd[idx-2] == "-stream_loop" and cmd[idx-1] == "-1":
                inputs.append((cmd[idx-2], cmd[idx-1], cmd[idx+1]))
            else:
                inputs.append(cmd[idx+1])
    
    # The sfx item input (ambient.mp3) must be prepended by loop flags
    assert ("-stream_loop", "-1", "ambient.mp3") in inputs

    # Verify atrim matches video duration and fade out starts at 15.5 - 1.0 = 14.5s
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "atrim=start=0:end=15.5" in filter_str if "filter_str" in locals() else "atrim=start=0:end=15.5" in filter_arg
    assert "afade=t=in:st=0:d=0.5" in filter_arg
    assert "afade=t=out:st=14.5:d=1.0" in filter_arg
    # Verify no adelay is generated
    assert "adelay" not in filter_arg



# === New Voice Gain/Start (M15 Persian TTS) Tests ===

def test_build_command_voice_gain_and_start_chain():
    """voice_gain_db + voice_start_sec prepend volume/adelay to the voice chain before denoise."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio = AudioConfig(voice_key="voice.wav", music_key=None, voice_gain_db=-3, voice_start_sec=1.5)
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "[1:a]adelay=1500|1500,volume=-3dB,afftdn=nf=-30[voice_clean]" in fc


def test_build_command_voice_gain_only_chain():
    """voice_gain_db without start_sec adds only the volume filter."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio = AudioConfig(voice_key="voice.wav", music_key=None, voice_gain_db=2)
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "[1:a]volume=2dB,afftdn=nf=-30[voice_clean]" in fc


def test_build_command_voice_chain_default_unchanged():
    """Default AudioConfig (no gain/start) keeps the historical voice chain byte-for-byte."""
    engine = MediaAssemblyEngine()
    recipe = make_recipe()
    recipe.audio = AudioConfig(voice_key="voice.wav", music_key=None)
    cmd = engine.build_assembly_command(
        recipe=recipe,
        video_path="/tmp/v.mp4",
        voice_path="/tmp/voice.wav",
        music_path=None,
        hook_png_path=None,
        output_path="/tmp/o.mp4",
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "[1:a]afftdn=nf=-30[voice_clean]" in fc
    assert "adelay" not in fc
    assert "volume=" not in fc
