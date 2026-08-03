"""供应商无关的大模型调用接口。"""

from noteforge.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMJSONDecodeError,
    LLMRequestError,
    LLMTimeoutError,
)
from noteforge.llm.base import LLMClient
from noteforge.llm.client import create_llm_client, register_provider
from noteforge.llm.models import (
    JSONValue,
    LLMMessage,
    LLMRequestOptions,
    LLMResponse,
    LLMRole,
    LLMTool,
    LLMToolCall,
    LLMToolResponse,
    LLMUsage,
)

__all__ = [
    "JSONValue",
    "LLMClient",
    "LLMConfigurationError",
    "LLMError",
    "LLMJSONDecodeError",
    "LLMMessage",
    "LLMRequestError",
    "LLMRequestOptions",
    "LLMResponse",
    "LLMRole",
    "LLMTimeoutError",
    "LLMTool",
    "LLMToolCall",
    "LLMToolResponse",
    "LLMUsage",
    "create_llm_client",
    "register_provider",
]
