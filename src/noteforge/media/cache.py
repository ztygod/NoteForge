"""用于存储标准化媒体数据的文件系统缓存。"""

from dataclasses import asdict
from enum import Enum
import json
from pathlib import Path
import tempfile
from typing import Any

from noteforge.media.models import SubtitleSegment, VideoMetadata, VideoPlatform


class MediaCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def video_dir(self, platform: str, video_id: str) -> Path:
        safe_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in video_id)
        platform_name = platform.value if isinstance(platform, VideoPlatform) else platform
        return self.root / platform_name / safe_id

    def load_metadata(self, platform: str, video_id: str) -> VideoMetadata | None:
        value = self._read(self.video_dir(platform, video_id) / "metadata.json")
        if not isinstance(value, dict):
            return None
        try:
            return VideoMetadata(**value)
        except (KeyError, TypeError, ValueError):
            return None

    def save_metadata(self, metadata: VideoMetadata) -> Path:
        return self._write(self.video_dir(metadata.platform, metadata.id) / "metadata.json", asdict(metadata))

    def load_transcript(self, platform: str, video_id: str) -> tuple[SubtitleSegment, ...] | None:
        value = self._read(self.video_dir(platform, video_id) / "subtitle.json")
        if not isinstance(value, list):
            return None
        try:
            return tuple(SubtitleSegment(**item) for item in value)
        except (TypeError, ValueError):
            return None

    def save_transcript(self, metadata: VideoMetadata, segments: tuple[SubtitleSegment, ...]) -> Path:
        return self._write(self.video_dir(metadata.platform, metadata.id) / "subtitle.json", [asdict(item) for item in segments])

    @staticmethod
    def _read(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _write(path: Path, value: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        def default(item: Any) -> Any:
            if isinstance(item, Enum):
                return item.value
            raise TypeError
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as output:
            json.dump(value, output, ensure_ascii=False, indent=2, default=default)
            temporary = Path(output.name)
        temporary.replace(path)
        return path
