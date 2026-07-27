"""NoteForge 对外暴露的异常类型。"""

from noteforge.exceptions.base import NoteForgeError
from noteforge.exceptions.collect import (
    CollectionError,
    InvalidCollectionResponseError,
    LoginRequiredError,
    RemoteCollectionError,
    RiskControlError,
    UnsupportedSourceError,
    VideoUnavailableError,
)
from noteforge.exceptions.llm import (
    LLMConfigurationError,
    LLMError,
    LLMJSONDecodeError,
    LLMRequestError,
    LLMTimeoutError,
)
from noteforge.exceptions.semantic import SemanticAnalysisError
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
    "LLMConfigurationError",
    "LLMError",
    "LLMJSONDecodeError",
    "LLMRequestError",
    "LLMTimeoutError",
    "LoginRequiredError",
    "NoteForgeError",
    "InvalidSubtitleResponseError",
    "RemoteCollectionError",
    "RiskControlError",
    "SemanticAnalysisError",
    "UnsupportedSourceError",
    "VideoUnavailableError",
    "SubtitleDownloadError",
    "SubtitleError",
    "SubtitleNotFoundError",
    "SubtitleParseError",
]
