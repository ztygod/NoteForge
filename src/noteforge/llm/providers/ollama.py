"""Ollama 本地 Chat API 适配器。"""

from typing import Sequence

from noteforge.config import LLMSettings
from noteforge.exceptions import LLMRequestError
from noteforge.llm.base import LLMClient
from noteforge.llm.providers import HTTPTransport, UrllibHTTPTransport
from noteforge.llm.models import (
    LLMMessage,
    LLMRequestOptions,
    LLMResponse,
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
            "stream": False,
        }
        ollama_options: RawJSON = {}
        if options and options.temperature is not None:
            ollama_options["temperature"] = options.temperature
        if options and options.max_tokens is not None:
            ollama_options["num_predict"] = options.max_tokens
        if ollama_options:
            payload["options"] = ollama_options

        result = self._transport.post_json(
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


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None
