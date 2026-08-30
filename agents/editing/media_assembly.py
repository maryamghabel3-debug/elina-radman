import os
import logging
import subprocess
from typing import Optional, List

from agents.editing.recipe_schema import EditRecipe
from agents.editing.audio_engine import (
    build_ffmpeg_afftdn_filter,
    build_ffmpeg_loudnorm_filter,
)
from agents.editing.ducking import DuckingParams, build_ffmpeg_sidechain_filter

logger = logging.getLogger(__name__)


def _get_audio_duration(path: str, ffprobe_binary: str = "ffprobe") -> float:
    """
    Get duration of audio file using ffprobe.
    """
    if not path or not os.path.exists(path):
        return 0.0
    try:
        result = subprocess.run(
            [
                ffprobe_binary,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0.0


class MediaAssemblyEngine:
    """
    Assembles final MP4 output by combining:
    - Base video
    - Voice narration (with denoise + cinematic processing)
    - Background music (with ducking)
    - Text overlays (hook PNG, subtitle PNG)
    - Sound effects (SFX) mixed with specific timings, gains, and fades
    - Final loudness normalization
    """

    def __init__(self, ffmpeg_binary: str = "ffmpeg", ffprobe_binary: str = "ffprobe"):
        self.ffmpeg_binary = ffmpeg_binary
        self.ffprobe_binary = ffprobe_binary

    def build_assembly_command(
        self,
        recipe: EditRecipe,
        video_path: str,
        voice_path: Optional[str],
        music_path: Optional[str],
        hook_png_path: Optional[str],
        output_path: str,
        sfx_items: Optional[List[dict]] = None,
        use_base_audio: bool = False,
        video_duration: Optional[float] = None,
    ) -> List[str]:
        """
        Constructs the ffmpeg command as a list of arguments.
        Does NOT execute; returns the command for testing or later execution.

        use_base_audio mixes the original audio stream of the base video
        (input 0) into the final audio when the user asked to keep the
        original shot audio.
        """
        if not recipe.content_id:
            raise ValueError("Recipe must have content_id.")
        if not video_path:
            raise ValueError("video_path is required.")

        if video_duration is None:
            video_duration = _get_audio_duration(video_path, ffprobe_binary=self.ffprobe_binary)

        cmd = [self.ffmpeg_binary, "-y"]

        # Inputs
        cmd += ["-i", video_path]
        if voice_path:
            cmd += ["-i", voice_path]
        if music_path:
            cmd += ["-i", music_path]
        if hook_png_path:
            cmd += ["-i", hook_png_path]

        sfx_indices = []
        if sfx_items:
            current_input_index = 1 + (1 if voice_path else 0) + (1 if music_path else 0) + (1 if hook_png_path else 0)
            for sfx in sfx_items:
                if sfx.get("background_bed"):
                    cmd += ["-stream_loop", "-1"]
                cmd += ["-i", sfx["path"]]
                sfx_indices.append(current_input_index)
                current_input_index += 1

        # Filter complex
        filter_parts = []

        # Denoise voice if present (optional gain + start delay applied first,
        # both disabled by default so the historical voice chain is unchanged)
        voice_index = 1 if voice_path else None
        if voice_index is not None:
            voice_prefix = []
            if recipe.audio.voice_start_sec is not None and recipe.audio.voice_start_sec > 0:
                delay_ms = int(round(recipe.audio.voice_start_sec * 1000))
                voice_prefix.append(f"adelay={delay_ms}|{delay_ms}")
            if recipe.audio.voice_gain_db is not None:
                voice_prefix.append(f"volume={int(recipe.audio.voice_gain_db)}dB")
            afftdn = build_ffmpeg_afftdn_filter(-30)
            voice_chain = ",".join(voice_prefix + [afftdn])
            filter_parts.append(f"[{voice_index}:a]{voice_chain}[voice_clean]")

        # Process music volume / gain if present
        music_stream_label = None
        if music_path:
            music_index = 2 if voice_path else 1
            gain_db = recipe.audio.music_gain_db
            if gain_db is None:
                gain_db = -12
            try:
                gain_db = int(gain_db)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid music_gain_db value: {gain_db}. Must be an integer.")

            filter_parts.append(f"[{music_index}:a]volume={gain_db}dB[music_gained]")
            music_stream_label = "music_gained"

        # Ducking if both voice and music
        if voice_path and music_path:
            duck_params = DuckingParams(
                target_reduction_db=recipe.audio.ducking.target_reduction_db,
                attack=recipe.audio.ducking.attack,
                release=recipe.audio.ducking.release,
            )
            duck_filter = build_ffmpeg_sidechain_filter(
                duck_params,
                voice_stream="voice_clean",
                music_stream=music_stream_label,
            )
            filter_parts.append(duck_filter)
            # Mix ducked music with voice
            filter_parts.append(
                "[ducked_music][voice_clean]amix=inputs=2:duration=first[mixed_audio]"
            )
            audio_out = "mixed_audio"
        elif voice_path:
            audio_out = "voice_clean"
        elif music_path:
            audio_out = music_stream_label
        else:
            audio_out = None

        # Process each SFX item and generate clean audio stream
        if sfx_items:
            for i, sfx in enumerate(sfx_items):
                idx = sfx_indices[i]
                filters = []

                # Loudness normalization (default true) before gain_db
                normalize_loudness = sfx.get("normalize_loudness", True)
                if normalize_loudness:
                    filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

                # Volume / gain
                gain_db = sfx.get("gain_db", 0)
                filters.append(f"volume={gain_db}dB")

                # Background bed vs normal anchored SFX
                bg_bed = sfx.get("background_bed", False)
                if bg_bed:
                    # Ignore anchors/start_sec. Trim to video_duration
                    filters.append(f"atrim=start=0:end={video_duration},asetpts=PTS-STARTPTS")

                    # Apply fade_in at 0.0
                    fade_in_sec = sfx.get("fade_in_sec", 0.0)
                    if fade_in_sec > 0:
                        filters.append(f"afade=t=in:st=0:d={fade_in_sec}")

                    # Apply fade_out at the very end of the video
                    fade_out_sec = sfx.get("fade_out_sec", 0.0)
                    if fade_out_sec > 0:
                        st_out = max(0.0, video_duration - fade_out_sec)
                        filters.append(f"afade=t=out:st={st_out}:d={fade_out_sec}")
                else:
                    # Fade in
                    fade_in_sec = sfx.get("fade_in_sec", 0.0)
                    if fade_in_sec > 0:
                        filters.append(f"afade=t=in:st=0:d={fade_in_sec}")

                    # Fade out
                    fade_out_sec = sfx.get("fade_out_sec", 0.0)
                    if fade_out_sec > 0:
                        duration = sfx.get("duration") or sfx.get("duration_sec") or _get_audio_duration(sfx["path"], ffprobe_binary=self.ffprobe_binary)
                        if duration > fade_out_sec:
                            filters.append(f"afade=t=out:st={duration - fade_out_sec}:d={fade_out_sec}")

                    # Adelay
                    start_sec = sfx.get("start_sec", 0.0)
                    delay_ms = int(start_sec * 1000)
                    filters.append(f"adelay={delay_ms}|{delay_ms}")

                filter_str = ",".join(filters)
                filter_parts.append(f"[{idx}:a]{filter_str}[sfx_{i}_clean]")

        # Original base-video audio (kept when the user asked to keep it)
        if use_base_audio:
            filter_parts.append("[0:a]aresample=48000,aformat=channel_layouts=stereo[base_audio]")
            base_audio_label = "base_audio"
        else:
            base_audio_label = None

        # Mix all SFX streams with existing audio_out stream
        mix_inputs = []
        if audio_out:
            mix_inputs.append(audio_out)

        if base_audio_label:
            mix_inputs.append(base_audio_label)

        if sfx_items:
            for i in range(len(sfx_items)):
                mix_inputs.append(f"sfx_{i}_clean")

        if len(mix_inputs) > 1:
            inputs_str = "".join(f"[{stream}]" for stream in mix_inputs)
            filter_parts.append(
                f"{inputs_str}amix=inputs={len(mix_inputs)}:duration=first[mixed_final]"
            )
            audio_out = "mixed_final"
        elif len(mix_inputs) == 1:
            audio_out = mix_inputs[0]
        else:
            audio_out = None

        # Loudness normalize the final audio
        if audio_out:
            loudnorm = build_ffmpeg_loudnorm_filter()
            filter_parts.append(f"[{audio_out}]{loudnorm}[final_audio]")
            final_audio_label = "final_audio"
        else:
            final_audio_label = None

        # Video overlay for hook
        if hook_png_path:
            overlay_index = 1 + (1 if voice_path else 0) + (1 if music_path else 0)
            filter_parts.append(
                f"[0:v][{overlay_index}:v]overlay=(W-w)/2:(H-h)/3:"
                f"enable='between(t,{recipe.hook.start_sec},{recipe.hook.end_sec})'[final_video]"
            )
            final_video_label = "final_video"
        else:
            final_video_label = "0:v"

        if filter_parts:
            cmd += ["-filter_complex", ";".join(filter_parts)]
            # Input stream references (e.g. "0:v") must NOT be bracketed in -map;
            # only filter-graph output labels (e.g. "[final_video]") are bracketed.
            map_video_label = f"[{final_video_label}]" if final_video_label != "0:v" else final_video_label
            cmd += ["-map", map_video_label]
            if final_audio_label:
                cmd += ["-map", f"[{final_audio_label}]"]

        # Encoding
        cmd += [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
        ]

        # Resolution
        if recipe.export.resolution:
            width, height = recipe.export.resolution.split("x")
            cmd += ["-s", f"{width}x{height}"]

        cmd += ["-r", str(recipe.export.fps)]
        cmd += [output_path]

        return cmd

    def run_assembly(
        self,
        recipe: EditRecipe,
        video_path: str,
        voice_path: Optional[str],
        music_path: Optional[str],
        hook_png_path: Optional[str],
        output_path: str,
        timeout_seconds: int = 300,
        sfx_items: Optional[List[dict]] = None,
        use_base_audio: bool = False,
        video_duration: Optional[float] = None,
    ) -> str:
        """
        Executes the ffmpeg assembly command.
        Returns the output_path on success.
        """
        cmd = self.build_assembly_command(
            recipe=recipe,
            video_path=video_path,
            voice_path=voice_path,
            music_path=music_path,
            hook_png_path=hook_png_path,
            output_path=output_path,
            sfx_items=sfx_items,
            use_base_audio=use_base_audio,
            video_duration=video_duration,
        )

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        logger.info("Running ffmpeg assembly for %s", recipe.content_id)
        logger.info("Executing FFmpeg command: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            logger.error("FFmpeg failed: %s", result.stderr[-2000:])
            raise RuntimeError(
                f"FFmpeg assembly failed for {recipe.content_id}: {result.stderr[-2000:]}"
            )

        return output_path


def run_qc_checks(
    output_path: str,
    recipe: EditRecipe,
    ffprobe_binary: str = "ffprobe",
) -> List[str]:
    """
    Runs post-render quality checks.
    Returns a list of QC error strings. Empty list means pass.
    """
    errors = []

    if not os.path.exists(output_path):
        errors.append("Output file does not exist.")
        return errors

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    if size_mb > recipe.export.max_size_mb:
        errors.append(
            f"Output size {size_mb:.1f}MB exceeds max {recipe.export.max_size_mb}MB."
        )
    if size_mb < 0.01:
        errors.append("Output file is nearly empty.")

    # Optional: run ffprobe if available
    try:
        result = subprocess.run(
            [ffprobe_binary, "-v", "error", "-show_entries",
             "stream=width,height,duration", "-of", "csv=p=0", output_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            # Basic sanity check on output
            if not result.stdout.strip():
                errors.append("ffprobe returned no stream info.")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffprobe check skipped: %s", exc)

    return errors
