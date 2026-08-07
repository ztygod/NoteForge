"""为 Whisper 或其他语音转文字后端提供的扩展接口。"""

from pathlib import Path
from typing import Protocol

from noteforge.media.models import SubtitleSegment


class AudioTranscriber(Protocol):
    def transcribe(self, audio_path: Path, *, language: str | None = None) -> tuple[SubtitleSegment, ...]: ...
