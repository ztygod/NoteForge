"""媒体提取领域模型，不向上层泄露具体后端的数据结构。"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class VideoPlatform(StrEnum):
    BILIBILI = "bilibili"
    YOUTUBE = "youtube"


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    id: str
    title: str
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    platform: str
    webpage_url: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class Subtitle:
    language: str
    format: str
    path: Path | None = None
    content: str | None = None
    is_automatic: bool = False


@dataclass(frozen=True, slots=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class VideoResource:
    metadata: VideoMetadata
    subtitles: tuple[Subtitle, ...] = ()
    transcript: tuple[SubtitleSegment, ...] = ()
    audio_path: Path | None = None
    video_path: Path | None = None
    transcript_source: str | None = None
