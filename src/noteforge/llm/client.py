"""LLM Client 工厂。"""

from collections.abc import Callable

from noteforge.config import LLMSettings
from noteforge.exceptions import LLMConfigurationError
from noteforge.llm.base import LLMClient
from noteforge.llm.providers.anthropic import AnthropicMessagesClient
from noteforge.llm.providers.ollama import OllamaClient
from noteforge.llm.providers.openai import OpenAICompatibleClient


ClientFactory = Callable[[LLMSettings], LLMClient]

_API_FORMATS: dict[str, ClientFactory] = {
    "openai": OpenAICompatibleClient,
    "anthropic": AnthropicMessagesClient,
    "ollama": OllamaClient,
}


def register_api_format(name: str, factory: ClientFactory) -> None:
    """注册自定义 API 格式适配器，供插件或应用启动代码扩展。"""

    normalized_name = name.strip().lower()
    if not normalized_name:
        raise ValueError("API 格式名称不能为空")
    _API_FORMATS[normalized_name] = factory


def register_provider(name: str, factory: ClientFactory) -> None:
    """兼容旧名称；新代码应使用 :func:`register_api_format`。"""

    register_api_format(name, factory)


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
        factory = _API_FORMATS[settings.provider.strip().lower()]
    except KeyError as error:
        raise LLMConfigurationError(
            f"不支持的 LLM API 格式：{settings.provider}"
        ) from error
    return factory(settings)
