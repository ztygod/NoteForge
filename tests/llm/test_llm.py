import json
from typing import Mapping, Sequence

import pytest

from noteforge.config import LLMSettings
from noteforge.llm import (
    LLMClient,
    LLMConfigurationError,
    LLMJSONDecodeError,
    LLMMessage,
    LLMRequestOptions,
    LLMResponse,
    create_llm_client,
)
from noteforge.llm.providers import HTTPResult
from noteforge.llm.providers.anthropic import AnthropicClient
from noteforge.llm.providers.ollama import OllamaClient
from noteforge.llm.providers.openai import OpenAIClient
from noteforge.llm.models import RawJSON


class FakeTransport:
    def __init__(self, response: RawJSON) -> None:
        self.response = response
        self.requests: list[tuple[str, Mapping[str, str], RawJSON, float]] = []

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: RawJSON,
        timeout_seconds: float,
    ) -> HTTPResult:
        self.requests.append((url, headers, payload, timeout_seconds))
        return HTTPResult(self.response, {})


class StaticClient(LLMClient):
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        return LLMResponse(content=self.content, model="test")


def settings(provider: str, api_key: str | None = "secret") -> LLMSettings:
    return LLMSettings(provider, "test-model", api_key, "http://llm.test", 5)


def test_generate_json() -> None:
    assert StaticClient('{"answer": 42}').generate_json([]) == {"answer": 42}
    with pytest.raises(LLMJSONDecodeError):
        StaticClient("not json").generate_json([])


def test_openai_adapter_maps_request_and_response() -> None:
    transport = FakeTransport(
        {
            "id": "req-1",
            "model": "returned-model",
            "choices": [
                {"message": {"content": "你好"}, "finish_reason": "stop"}
            ],
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 3,
                "total_tokens": 5,
            },
        }
    )
    client = OpenAIClient(settings("openai"), transport=transport)

    response = client.generate(
        [LLMMessage("user", "问题")],
        options=LLMRequestOptions(temperature=0.2, max_tokens=100),
    )

    assert response.content == "你好"
    assert response.usage.total_tokens == 5
    url, headers, payload, timeout = transport.requests[0]
    assert url == "http://llm.test/chat/completions"
    assert headers["Authorization"] == "Bearer secret"
    assert payload["temperature"] == 0.2
    assert timeout == 5


def test_ollama_adapter_maps_usage() -> None:
    transport = FakeTransport(
        {
            "model": "llama",
            "message": {"role": "assistant", "content": "本地回答"},
            "done": True,
            "prompt_eval_count": 4,
            "eval_count": 6,
        }
    )
    response = OllamaClient(
        settings("ollama", None), transport=transport
    ).generate([LLMMessage("user", "问题")])

    assert response.content == "本地回答"
    assert response.usage.total_tokens == 10
    assert transport.requests[0][0] == "http://llm.test/api/chat"


def test_anthropic_adapter_separates_system_message() -> None:
    transport = FakeTransport(
        {
            "id": "msg-1",
            "model": "claude",
            "content": [{"type": "text", "text": "回答"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 3, "output_tokens": 2},
        }
    )
    client = AnthropicClient(settings("anthropic"), transport=transport)

    response = client.generate(
        [LLMMessage("system", "规则"), LLMMessage("user", "问题")]
    )

    assert response.content == "回答"
    payload = transport.requests[0][2]
    assert payload["system"] == "规则"
    assert payload["messages"] == [{"role": "user", "content": "问题"}]


def test_factory_and_environment_configuration() -> None:
    loaded = LLMSettings.from_env(
        {
            "NOTEFORGE_LLM_PROVIDER": "ollama",
            "NOTEFORGE_LLM_MODEL": "qwen",
        }
    )
    assert loaded.base_url == "http://localhost:11434"
    assert isinstance(create_llm_client(loaded), OllamaClient)

    with pytest.raises(LLMConfigurationError):
        create_llm_client(settings("unknown"))


def test_api_key_is_not_serialized_into_payload() -> None:
    transport = FakeTransport(
        {
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
        }
    )
    OpenAIClient(settings("openai"), transport=transport).generate(
        [LLMMessage("user", "问题")]
    )

    assert "secret" not in json.dumps(transport.requests[0][2])
