"""标准化媒体元数据与转录文本的持久化仓库。"""

import json
import tempfile
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from noteforge.media.models import SubtitleSegment, VideoMetadata, VideoPlatform


class MediaRepository:
    """只保存非敏感、小体积的标准化数据，不保存媒体或 Cookie。"""

    def __init__(self, root: Path) -> None:
        self.root = root

    def video_dir(self, platform: str, video_id: str) -> Path:
        """生成经过目录穿越防护的平台资源目录。"""

        safe_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in video_id)
        platform_name = (
            platform.value if isinstance(platform, VideoPlatform) else platform
        )
        return self.root / platform_name / safe_id

    def load_metadata(self, platform: str, video_id: str) -> VideoMetadata | None:
        """读取元数据；文件缺失或结构损坏时视为未命中。"""

        value = self._read(self.video_dir(platform, video_id) / "metadata.json")
        if not isinstance(value, dict):
            return None
        try:
            return VideoMetadata(**value)
        except (KeyError, TypeError, ValueError):
            return None

    def save_metadata(self, metadata: VideoMetadata) -> Path:
        """原子写入标准化元数据。"""

        return self._write(
            self.video_dir(metadata.platform, metadata.id) / "metadata.json",
            asdict(metadata),
        )

    def load_transcript(
        self, platform: str, video_id: str
    ) -> tuple[SubtitleSegment, ...] | None:
        """读取标准化字幕片段；无效缓存不会传播到上层。"""

        value = self._read(self.video_dir(platform, video_id) / "subtitle.json")
        if not isinstance(value, list):
            return None
        try:
            return tuple(SubtitleSegment(**item) for item in value)
        except (TypeError, ValueError):
            return None

    def save_transcript(
        self, metadata: VideoMetadata, segments: tuple[SubtitleSegment, ...]
    ) -> Path:
        """原子写入标准化字幕片段。"""

        return self._write(
            self.video_dir(metadata.platform, metadata.id) / "subtitle.json",
            [asdict(item) for item in segments],
        )

    @staticmethod
    def _read(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _write(path: Path, value: Any) -> Path:
        """先写同目录临时文件，再替换目标，避免半写入文件。"""

        path.parent.mkdir(parents=True, exist_ok=True)

        def default(item: Any) -> Any:
            if isinstance(item, Enum):
                return item.value
            raise TypeError

        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as output:
            json.dump(value, output, ensure_ascii=False, indent=2, default=default)
            temporary = Path(output.name)
        temporary.replace(path)
        return path
