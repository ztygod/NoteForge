"""媒体领域模型。

本模块刻意不包含 yt-dlp 的格式表达式、CLI 参数或 Cookie 内容。
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class VideoPlatform(StrEnum):
    """当前内置的平台标识。"""

    BILIBILI = "bilibili"
    YOUTUBE = "youtube"


Platform = VideoPlatform


class MediaType(StrEnum):
    """临时资产的内容类型。"""

    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"


class CookiePersistence(StrEnum):
    """Cookie 在任务结束后的处理策略。"""

    EPHEMERAL = "ephemeral"
    RETAIN = "retain"


class Browser(StrEnum):
    """Cookie Provider 支持的浏览器名称。"""

    CHROME = "chrome"
    CHROMIUM = "chromium"
    EDGE = "edge"
    FIREFOX = "firefox"
    BRAVE = "brave"
    VIVALDI = "vivaldi"
    OPERA = "opera"
    SAFARI = "safari"


@dataclass(frozen=True, slots=True)
class AuthRequest:
    """请求使用浏览器身份；不包含任何 Cookie 明文。"""

    browser: Browser | str  # Cookie 来源浏览器。
    profile: str | None = None  # 可选的浏览器配置目录。
    persistence: CookiePersistence = CookiePersistence.EPHEMERAL  # 默认用后即删。
    credential_id: str | None = None  # 已保留凭据 ID；设置后不再读取浏览器。


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """跨平台统一的视频基础信息。"""

    id: str  # 平台内稳定 ID。
    title: str
    uploader: str | None
    duration: int | None  # 秒。
    thumbnail: str | None  # 缩略图 URL，不下载图片。
    platform: str
    webpage_url: str  # 规范化后的详情页 URL。
    description: str | None = None


Metadata = VideoMetadata


@dataclass(frozen=True, slots=True)
class VideoFormat:
    """标准化的视频格式描述。"""

    id: str  # 后端格式标识，只能作为 VideoRequest.format_id 原样回传。
    container: str | None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    bitrate: float | None = None  # kbps。
    file_size: int | None = None  # 字节；可能是估算值。


@dataclass(frozen=True, slots=True)
class AudioFormat:
    """标准化的音频格式描述。"""

    id: str  # 后端格式标识，只能作为 AudioRequest.format_id 原样回传。
    container: str | None
    codec: str | None = None
    bitrate: float | None = None  # kbps。
    sample_rate: int | None = None  # Hz。
    file_size: int | None = None  # 字节；可能是估算值。


@dataclass(frozen=True, slots=True)
class MediaFormats:
    """一次格式发现返回的音视频格式集合。"""

    videos: tuple[VideoFormat, ...] = ()
    audios: tuple[AudioFormat, ...] = ()


@dataclass(frozen=True, slots=True)
class Subtitle:
    """字幕轨道；发现阶段通常只有描述，下载后才有正文或路径。"""

    language: str  # 平台返回的语言标识。
    format: str  # vtt、srt、ass 或 json3。
    path: Path | None = None  # 临时字幕路径，不应长期持有。
    content: str | None = None  # 内联字幕正文。
    is_automatic: bool = False


@dataclass(frozen=True, slots=True)
class PlaylistEntry:
    """播放列表中的轻量条目，不递归提取完整元数据。"""

    id: str
    title: str | None
    url: str
    index: int


@dataclass(frozen=True, slots=True)
class Playlist:
    """标准化播放列表。"""

    id: str
    title: str
    entries: tuple[PlaylistEntry, ...]


@dataclass(frozen=True, slots=True)
class VideoRequest:
    """视频下载约束；调用方无需了解 yt-dlp 格式表达式。"""

    format_id: str | None = None  # 来自 list_formats()。
    container: str | None = None
    max_height: int | None = None


@dataclass(frozen=True, slots=True)
class AudioRequest:
    """音频下载与转码约束。"""

    format_id: str | None = None  # 来自 list_formats()。
    codec: str = "mp3"  # 输出编码格式。
    bitrate: int | None = None  # 目标 kbps；后端不支持时可忽略。


@dataclass(frozen=True, slots=True)
class SubtitleRequest:
    """指定要下载的字幕语言和输出格式。"""

    language: str
    format: str = "vtt"


@dataclass(frozen=True, slots=True)
class SubtitleSegment:
    """标准化字幕时间片。"""

    start: float  # 起始秒数。
    end: float  # 结束秒数。
    text: str


@dataclass(frozen=True, slots=True)
class VideoResource:
    """面向笔记流水线的聚合结果，不包含 yt-dlp 原始数据。"""

    metadata: VideoMetadata
    subtitles: tuple[Subtitle, ...] = ()
    transcript: tuple[SubtitleSegment, ...] = ()
    audio_path: Path | None = None
    video_path: Path | None = None
    transcript_source: str | None = None  # cache/manual/automatic/whisper。
