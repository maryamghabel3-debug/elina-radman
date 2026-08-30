from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class VideoSegmentConfig:
    key: str
    start_sec: float = 0.0
    end_sec: Optional[float] = None
    transition_out: Optional[Dict[str, Any]] = None
    freeze_tail_sec: Optional[float] = None
    transform: Optional[Dict[str, Any]] = None
    brightness_keyframes: Optional[List[Dict[str, Any]]] = None
    visual_adjustments: Optional[Dict[str, Any]] = None

@dataclass
class SFXConfig:
    key: Optional[str] = None
    start_sec: float = 0.0
    gain_db: int = 0
    fade_in_sec: float = 0.0
    fade_out_sec: float = 0.0
    normalize_loudness: bool = True
    background_bed: bool = False

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
class SubtitleEntry:
    """One timed Persian subtitle on the global final timeline (TASK M16).

    Rendered as a transparent PNG (shaped RTL text + semi-transparent
    background box) and overlaid with FFmpeg on the fully composed video.
    """
    text: str
    start_sec: float
    end_sec: float
    position: str = "bottom_center"
    style: str = "default"
    font_size: int = 52
    max_width_ratio: float = 0.82
    margin_bottom: int = 180
    font_color: str = "#FFFFFF"
    background_color: str = "#000000"
    background_opacity: float = 0.55
    fade_in_sec: float = 0.12
    fade_out_sec: float = 0.12

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
    # Optional voice (narration) mix settings. None = no extra processing,
    # which preserves the historical voice chain byte-for-byte.
    voice_gain_db: Optional[int] = None
    voice_start_sec: Optional[float] = None

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
    subtitles: Optional[List[SubtitleEntry]] = None
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
            # Validate static per-segment color grade (visual_adjustments)
            va = seg.visual_adjustments
            if va is not None:
                if not isinstance(va, dict):
                    errors.append(f"Visual adjustments for segment '{seg.key}' must be a dictionary.")
                else:
                    va_ranges = {
                        "brightness": (-1.0, 1.0),
                        "contrast": (-2.0, 2.0),
                        "saturation": (0.0, 3.0),
                        "gamma": (0.1, 10.0),
                    }
                    for va_key, va_val in va.items():
                        if va_key not in va_ranges:
                            errors.append(f"Visual adjustments for segment '{seg.key}' contain unknown key: '{va_key}'.")
                            continue
                        if isinstance(va_val, bool) or not isinstance(va_val, (int, float)):
                            errors.append(f"Visual adjustments '{va_key}' for segment '{seg.key}' must be a number.")
                            continue
                        lo, hi = va_ranges[va_key]
                        if va_val < lo or va_val > hi:
                            errors.append(f"Visual adjustments '{va_key}' for segment '{seg.key}' must be between {lo} and {hi}: got {va_val}.")
        if self.hook.enabled:
            if not self.hook.text.strip():
                errors.append("Hook is enabled but text is empty.")
            if self.hook.start_sec < 0:
                errors.append("Hook start_sec cannot be negative.")
            if self.hook.end_sec <= self.hook.start_sec:
                errors.append("Hook end_sec must be greater than start_sec.")
        # Validate timed subtitles (M16)
        if self.subtitles is not None:
            if not isinstance(self.subtitles, list):
                errors.append("subtitles must be a list of subtitle entries.")
            else:
                supported_positions = ("bottom_center", "center", "top_center")
                supported_styles = ("default", "hook", "whisper", "name_reveal")
                for s_idx, sub in enumerate(self.subtitles):
                    if not isinstance(sub, SubtitleEntry):
                        errors.append(f"Subtitle {s_idx} must be a SubtitleEntry.")
                        continue
                    if not sub.text.strip():
                        errors.append(f"Subtitle {s_idx} text must be non-empty.")
                    if sub.start_sec < 0:
                        errors.append(f"Subtitle {s_idx} start_sec cannot be negative.")
                    if sub.end_sec <= sub.start_sec:
                        errors.append(f"Subtitle {s_idx} end_sec must be greater than start_sec.")
                    if not 24 <= sub.font_size <= 120:
                        errors.append(f"Subtitle {s_idx} font_size must be between 24 and 120.")
                    if not 0.3 <= sub.max_width_ratio <= 0.95:
                        errors.append(f"Subtitle {s_idx} max_width_ratio must be between 0.3 and 0.95.")
                    if not 0.0 <= sub.background_opacity <= 1.0:
                        errors.append(f"Subtitle {s_idx} background_opacity must be between 0 and 1.")
                    if sub.fade_in_sec < 0 or sub.fade_out_sec < 0:
                        errors.append(f"Subtitle {s_idx} fade durations cannot be negative.")
                    duration = sub.end_sec - sub.start_sec
                    if sub.fade_in_sec + sub.fade_out_sec > duration:
                        errors.append(f"Subtitle {s_idx} fade durations exceed subtitle duration ({duration}s).")
                    if sub.position not in supported_positions:
                        errors.append(f"Subtitle {s_idx} position '{sub.position}' is not supported.")
                    if sub.style not in supported_styles:
                        errors.append(f"Subtitle {s_idx} style '{sub.style}' is not supported.")
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
                transition_out = seg.get("transition_out")
                freeze_tail_sec = seg.get("freeze_tail_sec")
                if freeze_tail_sec is not None:
                    freeze_tail_sec = float(freeze_tail_sec)
                transform = seg.get("transform")
                brightness_keyframes = seg.get("brightness_keyframes")
                visual_adjustments = seg.get("visual_adjustments")
                video_segments.append(VideoSegmentConfig(
                    key=key, start_sec=start, end_sec=end,
                    transition_out=transition_out,
                    freeze_tail_sec=freeze_tail_sec,
                    transform=transform,
                    brightness_keyframes=brightness_keyframes,
                    visual_adjustments=visual_adjustments
                ))

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
        raw_subtitles = data.get("subtitles")
        subtitles = None
        if raw_subtitles is not None:
            if isinstance(raw_subtitles, list):
                subtitles = [
                    SubtitleEntry(
                        text=str(s.get("text", "")),
                        start_sec=float(s.get("start_sec", 0.0)),
                        end_sec=float(s.get("end_sec", 0.0)),
                        position=s.get("position", "bottom_center"),
                        style=s.get("style", "default"),
                        font_size=int(s.get("font_size", 52)),
                        max_width_ratio=float(s.get("max_width_ratio", 0.82)),
                        margin_bottom=int(s.get("margin_bottom", 180)),
                        font_color=s.get("font_color", "#FFFFFF"),
                        background_color=s.get("background_color", "#000000"),
                        background_opacity=float(s.get("background_opacity", 0.55)),
                        fade_in_sec=float(s.get("fade_in_sec", 0.12)),
                        fade_out_sec=float(s.get("fade_out_sec", 0.12)),
                    )
                    for s in raw_subtitles
                    if isinstance(s, dict)
                ]
            else:
                subtitles = None  # non-list values are reported by validate()
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
            subtitles=subtitles,
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
