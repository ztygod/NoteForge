"""LLM Client 工厂。"""

from collections.abc import Callable

from noteforge.config import LLMSettings
from noteforge.exceptions import LLMConfigurationError
from noteforge.llm.base import LLMClient
from noteforge.llm.providers.anthropic import AnthropicClient
from noteforge.llm.providers.ollama import OllamaClient
from noteforge.llm.providers.openai import OpenAIClient


ClientFactory = Callable[[LLMSettings], LLMClient]

_PROVIDERS: dict[str, ClientFactory] = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "ollama": OllamaClient,
}


def register_provider(name: str, factory: ClientFactory) -> None:
    """注册自定义 provider，供插件或应用启动代码扩展。"""

    normalized_name = name.strip().lower()
    if not normalized_name:
        raise ValueError("provider 名称不能为空")
    _PROVIDERS[normalized_name] = factory


def create_llm_client(
    settings: LLMSettings | None = None,
) -> LLMClient:
    """根据配置创建统一的 LLM Client。"""

    if settings is None:
        try:
            settings = LLMSettings.from_env()
        except ValueError as error:
            raise LLMConfigurationError(str(error)) from error

    try:
        factory = _PROVIDERS[settings.provider.strip().lower()]
    except KeyError as error:
        raise LLMConfigurationError(
            f"不支持的 LLM provider：{settings.provider}"
        ) from error
    return factory(settings)
