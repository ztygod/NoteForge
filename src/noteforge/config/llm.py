"""大模型运行时配置。

配置只在应用边界从环境变量读取，LLM API 适配器不直接访问环境变量。
"""

from dataclasses import dataclass
from typing import Mapping

from noteforge.config.dotenv import merged_environment


_DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434",
}

_API_FORMAT_LABELS = {
    "openai": "OpenAI-compatible",
    "anthropic": "Anthropic Messages",
    "ollama": "Ollama native",
}


def llm_api_format_label(value: str) -> str:
    """返回面向用户的 API 格式名称。"""

    normalized = value.strip().lower()
    return _API_FORMAT_LABELS.get(normalized, normalized)


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """大模型连接配置。

    ``provider`` 是为兼容 0.1 配置保留的字段名，其值实际表示请求所用的
    API 格式，而不是模型服务商身份。
    """

    provider: str
    model: str
    api_key: str | None
    base_url: str
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "LLMSettings":
        """从 ``NOTEFORGE_LLM_*`` 环境变量加载配置。"""

        values = (
            merged_environment()
            if environ is None
            else environ
        )
        provider = values.get("NOTEFORGE_LLM_PROVIDER", "").strip().lower()
        model = values.get("NOTEFORGE_LLM_MODEL", "").strip()
        api_key = values.get("NOTEFORGE_LLM_API_KEY") or None
        base_url = values.get("NOTEFORGE_LLM_BASE_URL", "").strip()

        if not provider:
            raise ValueError("缺少配置：NOTEFORGE_LLM_PROVIDER")
        if not model:
            raise ValueError("缺少配置：NOTEFORGE_LLM_MODEL")
        if not base_url:
            try:
                base_url = _DEFAULT_BASE_URLS[provider]
            except KeyError as error:
                raise ValueError(
                    "未知 API 格式必须配置 NOTEFORGE_LLM_BASE_URL"
                ) from error

        timeout_value = values.get("NOTEFORGE_LLM_TIMEOUT_SECONDS", "60")
        try:
            timeout_seconds = float(timeout_value)
        except ValueError as error:
            raise ValueError(
                "NOTEFORGE_LLM_TIMEOUT_SECONDS 必须是数字"
            ) from error
        if timeout_seconds <= 0:
            raise ValueError("LLM 超时时间必须大于 0")

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout_seconds=timeout_seconds,
        )
