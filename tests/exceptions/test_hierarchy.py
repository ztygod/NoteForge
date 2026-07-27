from noteforge.exceptions import (
    CollectionError,
    LLMConfigurationError,
    LLMError,
    LLMJSONDecodeError,
    LLMRequestError,
    LLMTimeoutError,
    NoteForgeError,
    SubtitleError,
)
from noteforge.llm import LLMError as ExportedLLMError


def test_domain_errors_share_project_root() -> None:
    assert issubclass(CollectionError, NoteForgeError)
    assert issubclass(SubtitleError, NoteForgeError)
    assert issubclass(LLMError, NoteForgeError)


def test_llm_error_hierarchy() -> None:
    assert issubclass(LLMConfigurationError, LLMError)
    assert issubclass(LLMRequestError, LLMError)
    assert issubclass(LLMTimeoutError, LLMRequestError)
    assert issubclass(LLMJSONDecodeError, LLMError)


def test_llm_package_keeps_compatible_exception_export() -> None:
    assert ExportedLLMError is LLMError
