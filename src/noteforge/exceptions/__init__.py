"""NoteForge 对外暴露的异常类型。"""

from noteforge.exceptions.collect import (
    CollectionError,
    InvalidCollectionResponseError,
    LoginRequiredError,
    RemoteCollectionError,
    RiskControlError,
    UnsupportedSourceError,
    VideoUnavailableError,
)
from noteforge.exceptions.subtitle import (
    InvalidSubtitleResponseError,
    SubtitleDownloadError,
    SubtitleError,
    SubtitleNotFoundError,
    SubtitleParseError,
)

__all__ = [
    "CollectionError",
    "InvalidCollectionResponseError",
    "LoginRequiredError",
    "InvalidSubtitleResponseError",
    "RemoteCollectionError",
    "RiskControlError",
    "UnsupportedSourceError",
    "VideoUnavailableError",
    "SubtitleDownloadError",
    "SubtitleError",
    "SubtitleNotFoundError",
    "SubtitleParseError",
]
