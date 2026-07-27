"""OpenAI Chat Completions API 适配器。"""

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
        self._transport = transport or UrllibHTTPTransport()

    def generate(
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

        result = self._transport.post_json(
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


def _optional_int(value: object, key: str) -> int | None:
    if isinstance(value, dict) and isinstance(value.get(key), int):
        return value[key]
    return None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
