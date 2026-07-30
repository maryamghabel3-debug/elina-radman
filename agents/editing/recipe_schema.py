from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class HookConfig:
    enabled: bool = False
    text: str = ""
    style: str = "hook_bold_center"
    start_sec: float = 0.0
    end_sec: float = 3.0

@dataclass
class SubtitleConfig:
    enabled: bool = False
    style: str = "farsi_cinematic_bottom"

@dataclass
class AudioDucking:
    enabled: bool = True
    target_reduction_db: int = 6
    attack: float = 0.2
    release: float = 0.6

@dataclass
class AudioConfig:
    voice_key: Optional[str] = None
    music_key: Optional[str] = None
    music_gain_db: int = -12
    ducking: AudioDucking = field(default_factory=AudioDucking)

@dataclass
class ExportConfig:
    resolution: str = "1080x1920"
    fps: int = 30
    format: str = "mp4"
    max_size_mb: int = 18

@dataclass
class EditRecipe:
    """
    Represents a single, validated instruction set for the render engine.
    """
    content_id: str
    video_key: Optional[str] = None
    hook: HookConfig = field(default_factory=HookConfig)
    subtitles: SubtitleConfig = field(default_factory=SubtitleConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    def validate(self) -> List[str]:
        """Returns a list of error strings. Empty list means valid."""
        errors = []
        if not self.content_id:
            errors.append("content_id is required.")
        if self.hook.enabled and not self.hook.text:
            errors.append("Hook is enabled but text is empty.")
        if self.video_key is None and self.subtitles.enabled:
             errors.append("Subtitles enabled but no video_key provided for context.")
        return errors

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "EditRecipe":
        hook_data = data.get("hook", {})
        sub_data = data.get("subtitles", {})
        audio_data = data.get("audio", {})
        ducking_data = audio_data.get("ducking", {})
        export_data = data.get("export", {})

        return EditRecipe(
            content_id=data.get("content_id"),
            video_key=data.get("video_key"),
            hook=HookConfig(**hook_data),
            subtitles=SubtitleConfig(**sub_data),
            audio=AudioConfig(
                voice_key=audio_data.get("voice_key"),
                music_key=audio_data.get("music_key"),
                music_gain_db=audio_data.get("music_gain_db", -12),
                ducking=AudioDucking(**ducking_data)
            ),
            export=ExportConfig(**export_data)
        )
