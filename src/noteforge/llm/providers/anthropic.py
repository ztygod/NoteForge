"""Anthropic Messages API 适配器。"""

from typing import Sequence

from noteforge.config import LLMSettings
from noteforge.exceptions import (
    LLMConfigurationError,
    LLMRequestError,
)
from noteforge.llm.base import LLMClient
from noteforge.llm.providers import HTTPTransport, UrllibHTTPTransport
from noteforge.llm.models import (
    LLMMessage,
    LLMRequestOptions,
    LLMResponse,
    LLMUsage,
    RawJSON,
)


class AnthropicClient(LLMClient):
    """调用 Anthropic Messages API。"""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        if not settings.api_key:
            raise LLMConfigurationError("Anthropic provider 缺少 api_key")
        self._settings = settings
        self._transport = transport or UrllibHTTPTransport()

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        if not messages:
            raise ValueError("messages 不能为空")

        system_parts = [
            message.content for message in messages if message.role == "system"
        ]
        chat_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role != "system"
        ]
        if not chat_messages:
            raise ValueError("Anthropic 请求至少需要一条非 system 消息")

        payload: RawJSON = {
            "model": self._settings.model,
            "messages": chat_messages,
            "max_tokens": (
                options.max_tokens
                if options and options.max_tokens is not None
                else 1024
            ),
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if options and options.temperature is not None:
            payload["temperature"] = options.temperature

        result = self._transport.post_json(
            f"{self._settings.base_url}/messages",
            headers={
                "x-api-key": self._settings.api_key,
                "anthropic-version": "2023-06-01",
            },
            payload=payload,
            timeout_seconds=self._settings.timeout_seconds,
        )
        try:
            blocks = result.data["content"]
            if not isinstance(blocks, list):
                raise TypeError
            content = "".join(
                block["text"]
                for block in blocks
                if isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            )
        except (KeyError, TypeError) as error:
            raise LLMRequestError("Anthropic 响应结构不完整") from error
        if not content:
            raise LLMRequestError("Anthropic 响应没有文本内容")

        usage_data = result.data.get("usage", {})
        input_tokens = _usage_int(usage_data, "input_tokens")
        output_tokens = _usage_int(usage_data, "output_tokens")
        total_tokens = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        return LLMResponse(
            content=content,
            model=str(result.data.get("model", self._settings.model)),
            usage=LLMUsage(input_tokens, output_tokens, total_tokens),
            finish_reason=_str_or_none(result.data.get("stop_reason")),
            request_id=_str_or_none(result.data.get("id")),
        )


def _usage_int(value: object, key: str) -> int | None:
    if isinstance(value, dict) and isinstance(value.get(key), int):
        return value[key]
    return None


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None
