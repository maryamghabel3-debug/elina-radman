from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class VideoSegmentConfig:
    key: str
    start_sec: float = 0.0
    end_sec: Optional[float] = None

@dataclass
class InputMediaConfig:
    video_keys: List[str] = field(default_factory=list)
    video_segments: List[VideoSegmentConfig] = field(default_factory=list)
    image_keys: List[str] = field(default_factory=list)
    voice_key: Optional[str] = None
    music_key: Optional[str] = None

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
    source_text: str = ""
    style: str = "farsi_cinematic_bottom"
    highlight_keywords: bool = False

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
class CoverConfig:
    enabled: bool = False
    text: str = ""
    style: str = "cover_dark_gold"

@dataclass
class ExportConfig:
    resolution: str = "1080x1920"
    fps: int = 30
    format: str = "mp4"
    max_size_mb: int = 18

@dataclass
class EditRecipe:
    content_id: str
    recipe_version: str = "1.0"
    project_type: str = "reel"
    preset: str = "elina_cinematic_reel"
    input_media: InputMediaConfig = field(default_factory=InputMediaConfig)
    hook: HookConfig = field(default_factory=HookConfig)
    subtitles: SubtitleConfig = field(default_factory=SubtitleConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    cover: CoverConfig = field(default_factory=CoverConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    def validate(self) -> List[str]:
        errors = []
        if not self.content_id:
            errors.append("content_id is required.")
        valid_types = ["reel", "story", "carousel_video", "maryam_video", "preview"]
        if self.project_type not in valid_types:
            errors.append(f"invalid project_type. Must be one of {valid_types}")

        # Validate video segments or video_keys
        has_video_segments = self.input_media.video_segments or self.input_media.video_keys
        if not has_video_segments and not self.input_media.image_keys:
            errors.append("At least one of video_segments, video_keys, or image_keys must be provided.")

        # Validate each video segment
        for seg in self.input_media.video_segments:
            if not seg.key:
                errors.append("Video segment must have a key.")
            if seg.start_sec < 0:
                errors.append(f"Video segment start_sec cannot be negative: {seg.start_sec}.")
            if seg.end_sec is not None and seg.end_sec <= seg.start_sec:
                errors.append(f"Video segment end_sec must be greater than start_sec: end={seg.end_sec}, start={seg.start_sec}.")
        if self.hook.enabled:
            if not self.hook.text.strip():
                errors.append("Hook is enabled but text is empty.")
            if self.hook.start_sec < 0:
                errors.append("Hook start_sec cannot be negative.")
            if self.hook.end_sec <= self.hook.start_sec:
                errors.append("Hook end_sec must be greater than start_sec.")
        if self.subtitles.enabled and not self.subtitles.source_text.strip():
            errors.append("Subtitles enabled but source_text is empty.")
        if self.export.fps <= 0:
            errors.append("Export fps must be greater than 0.")
        if self.export.max_size_mb <= 0:
            errors.append("Export max_size_mb must be greater than 0.")
        if "x" not in self.export.resolution:
            errors.append("Export resolution must follow WIDTHxHEIGHT pattern.")
        if self.export.format not in ["mp4", "jpg", "png"]:
            errors.append("Export format must be mp4, jpg, or png.")
        if self.audio.ducking.enabled:
            if self.audio.ducking.attack < 0 or self.audio.ducking.release < 0:
                errors.append("Audio ducking attack and release cannot be negative.")
        return errors

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "EditRecipe":
        if not isinstance(data, dict):
            raise TypeError("Input data must be a dictionary.")

        im_data = data.get("input_media", {})

        # Parse video_segments
        raw_segments = im_data.get("video_segments", [])
        video_segments = []
        for seg in raw_segments:
            if isinstance(seg, dict):
                key = seg.get("key", "")
                start = float(seg.get("start", seg.get("start_sec", 0.0)))
                end = seg.get("end", seg.get("end_sec"))
                end = float(end) if end is not None else None
                video_segments.append(VideoSegmentConfig(key=key, start_sec=start, end_sec=end))

        # Support legacy video_keys list (convert to segments if no segments provided)
        v_keys = im_data.get("video_keys", [])
        # Support legacy single video_key if present
        v_key = im_data.get("video_key")
        if v_key and v_key not in v_keys:
            v_keys.append(v_key)

        # If no video_segments but video_keys exist, convert keys to segments
        if not video_segments and v_keys:
            video_segments = [VideoSegmentConfig(key=k) for k in v_keys]

        hook_data = data.get("hook", {})
        sub_data = data.get("subtitles", {})
        audio_data = data.get("audio", {})
        duck_data = audio_data.get("ducking", {}) if isinstance(audio_data, dict) else {}
        cov_data = data.get("cover", {})
        exp_data = data.get("export", {})

        return EditRecipe(
            content_id=data.get("content_id", ""),
            recipe_version=data.get("recipe_version", "1.0"),
            project_type=data.get("project_type", "reel"),
            preset=data.get("preset", "elina_cinematic_reel"),
            input_media=InputMediaConfig(
                video_keys=v_keys,
                video_segments=video_segments,
                image_keys=im_data.get("image_keys", []),
                voice_key=im_data.get("voice_key"),
                music_key=im_data.get("music_key"),
            ),
            hook=HookConfig(
                enabled=hook_data.get("enabled", False),
                text=hook_data.get("text", ""),
                style=hook_data.get("style", "hook_bold_center"),
                start_sec=hook_data.get("start_sec", 0.0),
                end_sec=hook_data.get("end_sec", 3.0),
            ),
            subtitles=SubtitleConfig(
                enabled=sub_data.get("enabled", False),
                source_text=sub_data.get("source_text", ""),
                style=sub_data.get("style", "farsi_cinematic_bottom"),
                highlight_keywords=sub_data.get("highlight_keywords", False),
            ),
            audio=AudioConfig(
                voice_key=audio_data.get("voice_key"),
                music_key=audio_data.get("music_key"),
                music_gain_db=audio_data.get("music_gain_db", -12),
                ducking=AudioDucking(
                    enabled=duck_data.get("enabled", True),
                    target_reduction_db=duck_data.get("target_reduction_db", 6),
                    attack=duck_data.get("attack", 0.2),
                    release=duck_data.get("release", 0.6),
                )
            ),
            cover=CoverConfig(
                enabled=cov_data.get("enabled", False),
                text=cov_data.get("text", ""),
                style=cov_data.get("style", "cover_dark_gold"),
            ),
            export=ExportConfig(
                resolution=exp_data.get("resolution", "1080x1920"),
                fps=exp_data.get("fps", 30),
                format=exp_data.get("format", "mp4"),
                max_size_mb=exp_data.get("max_size_mb", 18),
            )
        )
