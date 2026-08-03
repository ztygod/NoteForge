"""Ollama 本地 Chat API 适配器。"""

import json

from typing import Sequence

from noteforge.config import LLMSettings
from noteforge.exceptions import LLMJSONDecodeError, LLMRequestError
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


class OllamaClient(LLMClient):
    """调用 Ollama ``/api/chat`` 接口。"""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
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
            "stream": False,
        }
        ollama_options: RawJSON = {}
        if options and options.temperature is not None:
            ollama_options["temperature"] = options.temperature
        if options and options.max_tokens is not None:
            ollama_options["num_predict"] = options.max_tokens
        if ollama_options:
            payload["options"] = ollama_options

        result = await self._transport.post_json(
            f"{self._settings.base_url}/api/chat",
            headers={},
            payload=payload,
            timeout_seconds=self._settings.timeout_seconds,
        )
        try:
            content = result.data["message"]["content"]
        except (KeyError, TypeError) as error:
            raise LLMRequestError("Ollama 响应结构不完整") from error
        if not isinstance(content, str):
            raise LLMRequestError("Ollama 响应内容不是文本")

        input_tokens = _int_or_none(result.data.get("prompt_eval_count"))
        output_tokens = _int_or_none(result.data.get("eval_count"))
        total_tokens = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        return LLMResponse(
            content=content,
            model=str(result.data.get("model", self._settings.model)),
            usage=LLMUsage(input_tokens, output_tokens, total_tokens),
            finish_reason="stop" if result.data.get("done") is True else None,
        )

    async def call_tool(
        self,
        messages: Sequence[LLMMessage],
        *,
        tool: LLMTool,
        options: LLMRequestOptions | None = None,
    ) -> LLMToolResponse:
        payload: RawJSON = {
            "model": self._settings.model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "stream": False,
            "tools": [{"type": "function", "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters),
            }}],
        }
        if options and (options.temperature is not None or options.max_tokens is not None):
            payload["options"] = {
                **({"temperature": options.temperature} if options.temperature is not None else {}),
                **({"num_predict": options.max_tokens} if options.max_tokens is not None else {}),
            }
        result = await self._transport.post_json(
            f"{self._settings.base_url}/api/chat", headers={}, payload=payload,
            timeout_seconds=self._settings.timeout_seconds,
        )
        try:
            function = result.data["message"]["tool_calls"][0]["function"]
            name = function["name"]
            arguments = function["arguments"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMRequestError("Ollama 响应没有有效的工具调用") from error
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as error:
                raise LLMJSONDecodeError(arguments) from error
        if name != tool.name or not isinstance(arguments, dict):
            raise LLMRequestError(f"Ollama 未调用要求的工具：{tool.name}")
        input_tokens = _int_or_none(result.data.get("prompt_eval_count"))
        output_tokens = _int_or_none(result.data.get("eval_count"))
        return LLMToolResponse(
            LLMToolCall(name, arguments),
            model=str(result.data.get("model", self._settings.model)),
            usage=LLMUsage(input_tokens, output_tokens, input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None),
            finish_reason="stop" if result.data.get("done") is True else None,
        )

    async def aclose(self) -> None:
        await self._transport.aclose()


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None
