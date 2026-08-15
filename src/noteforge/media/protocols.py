"""媒体服务内部可替换组件的接口。"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from noteforge.media.models import SubtitleSegment


class AudioTranscriber(Protocol):
    """Whisper 或其他语音转文字后端接口。"""

    def transcribe(
        self, audio_path: Path, *, language: str | None = None
    ) -> tuple[SubtitleSegment, ...]: ...


class MediaWorker(Protocol):
    """隔离媒体后端的执行接口。"""

    def execute(self, payload: dict[str, Any]) -> Mapping[str, Any]: ...

    def close(self) -> None: ...
