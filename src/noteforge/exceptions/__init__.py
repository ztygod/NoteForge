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

__all__ = [
    "CollectionError",
    "InvalidCollectionResponseError",
    "LoginRequiredError",
    "RemoteCollectionError",
    "RiskControlError",
    "UnsupportedSourceError",
    "VideoUnavailableError",
]
