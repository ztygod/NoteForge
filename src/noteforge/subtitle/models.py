"""结构化字幕数据模型。"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SubtitleFile:
    """下载到本地的字幕文件。"""

    path: Path
    language: str
    extension: str
    is_automatic: bool


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """带时间范围的一段字幕文本。"""

    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True, slots=True)
class Transcript:
    """完成结构化解析的字幕。"""

    language: str
    segments: tuple[TranscriptSegment, ...]
    source: str
