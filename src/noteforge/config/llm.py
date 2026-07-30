"""大模型运行时配置。

配置只在应用边界从环境变量读取，LLM provider 不直接访问环境变量。
"""

from dataclasses import dataclass
from typing import Mapping

from noteforge.config.dotenv import merged_environment


_DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434",
}


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """大模型连接配置。"""

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
                    "未知 provider 必须配置 NOTEFORGE_LLM_BASE_URL"
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
