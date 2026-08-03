"""OpenAI Chat Completions API 适配器。"""

import json

from typing import Sequence
from urllib.parse import urlparse

from noteforge.config import LLMSettings
from noteforge.exceptions import (
    LLMConfigurationError,
    LLMJSONDecodeError,
    LLMRequestError,
)
from noteforge.llm.base import LLMClient
from noteforge.llm.providers import HTTPTransport, HttpxHTTPTransport
from noteforge.llm.models import (
    LLMMessage,
    LLMRequestOptions,
    LLMResponse,
    LLMTool,
    LLMToolCall,
    LLMToolResponse,
    LLMUsage,
    RawJSON,
)


class OpenAIClient(LLMClient):
    """通过 OpenAI 兼容的 Chat Completions API 调用模型。"""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        if not settings.api_key:
            raise LLMConfigurationError("OpenAI provider 缺少 api_key")
        self._settings = settings
        self._transport = transport or HttpxHTTPTransport()

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        if not messages:
            raise ValueError("messages 不能为空")
        payload: RawJSON = {
            "model": self._settings.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
        }
        if options and options.temperature is not None:
            payload["temperature"] = options.temperature
        if options and options.max_tokens is not None:
            payload["max_tokens"] = options.max_tokens

        result = await self._transport.post_json(
            f"{self._settings.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.api_key}"},
            payload=payload,
            timeout_seconds=self._settings.timeout_seconds,
        )
        try:
            choice = result.data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMRequestError("OpenAI 响应结构不完整") from error
        if not isinstance(content, str):
            raise LLMRequestError("OpenAI 响应内容不是文本")

        usage_data = result.data.get("usage", {})
        return LLMResponse(
            content=content,
            model=str(result.data.get("model", self._settings.model)),
            usage=LLMUsage(
                input_tokens=_optional_int(usage_data, "prompt_tokens"),
                output_tokens=_optional_int(usage_data, "completion_tokens"),
                total_tokens=_optional_int(usage_data, "total_tokens"),
            ),
            finish_reason=_optional_str(choice.get("finish_reason")),
            request_id=_optional_str(result.data.get("id")),
        )

    async def call_tool(
        self,
        messages: Sequence[LLMMessage],
        *,
        tool: LLMTool,
        options: LLMRequestOptions | None = None,
    ) -> LLMToolResponse:
        is_deepseek = _is_deepseek_endpoint(self._settings.base_url)
        function: RawJSON = {
            "name": tool.name,
            "description": tool.description,
            "parameters": dict(tool.parameters),
        }
        # DeepSeek 的 strict tool schema 只在 /beta endpoint 开放。
        if not is_deepseek or urlparse(self._settings.base_url).path.rstrip("/").endswith("/beta"):
            function["strict"] = True
        payload: RawJSON = {
            "model": self._settings.model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "tools": [{
                "type": "function",
                "function": function,
            }],
            "tool_choice": {"type": "function", "function": {"name": tool.name}},
        }
        if is_deepseek:
            # V4 默认开启 thinking，但 thinking 模式不接受强制 tool_choice。
            # 结构化提取使用非 thinking 模式更快，语义约束由本地校验兜底。
            payload["thinking"] = {"type": "disabled"}
        if options and options.temperature is not None:
            payload["temperature"] = options.temperature
        if options and options.max_tokens is not None:
            payload["max_tokens"] = options.max_tokens
        result = await self._transport.post_json(
            f"{self._settings.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.api_key}"},
            payload=payload,
            timeout_seconds=self._settings.timeout_seconds,
        )
        try:
            choice = result.data["choices"][0]
            function = choice["message"]["tool_calls"][0]["function"]
            name = function["name"]
            arguments = json.loads(function["arguments"])
        except json.JSONDecodeError as error:
            raise LLMJSONDecodeError(str(function.get("arguments", ""))) from error
        except (KeyError, IndexError, TypeError) as error:
            raise LLMRequestError("OpenAI 响应没有有效的工具调用") from error
        if name != tool.name or not isinstance(arguments, dict):
            raise LLMRequestError(f"OpenAI 未调用要求的工具：{tool.name}")
        usage_data = result.data.get("usage", {})
        return LLMToolResponse(
            LLMToolCall(name, arguments),
            model=str(result.data.get("model", self._settings.model)),
            usage=LLMUsage(
                _optional_int(usage_data, "prompt_tokens"),
                _optional_int(usage_data, "completion_tokens"),
                _optional_int(usage_data, "total_tokens"),
            ),
            finish_reason=_optional_str(choice.get("finish_reason")),
            request_id=_optional_str(result.data.get("id")),
        )

    async def aclose(self) -> None:
        await self._transport.aclose()


def _optional_int(value: object, key: str) -> int | None:
    if isinstance(value, dict) and isinstance(value.get(key), int):
        return value[key]
    return None


def _is_deepseek_endpoint(base_url: str) -> bool:
    hostname = (urlparse(base_url).hostname or "").lower()
    return hostname == "api.deepseek.com" or hostname.endswith(".deepseek.com")


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
