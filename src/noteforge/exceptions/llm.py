"""大模型配置、请求和响应处理异常。"""

from noteforge.exceptions.base import NoteForgeError


class LLMError(NoteForgeError):
    """LLM 调用失败的基础异常。"""


class LLMConfigurationError(LLMError):
    """模型供应商配置无效。"""


class LLMRequestError(LLMError):
    """供应商 API 请求或响应失败。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMTimeoutError(LLMRequestError):
    """模型请求超时。"""


class LLMJSONDecodeError(LLMError):
    """模型返回内容不是有效 JSON。"""

    def __init__(self, content: str) -> None:
        super().__init__("模型返回内容不是有效 JSON")
        self.content = content
