"""统一的 LLM Client 接口与基础异常。"""

from abc import ABC, abstractmethod
import json
from typing import Sequence

from noteforge.exceptions import LLMJSONDecodeError
from noteforge.llm.models import (
    JSONValue,
    LLMMessage,
    LLMRequestOptions,
    LLMResponse,
)


class LLMClient(ABC):
    """所有模型供应商必须实现的统一同步接口。"""

    @abstractmethod
    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        """生成文本响应。"""

    def generate_json(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> JSONValue:
        """生成响应并将内容解析为 JSON。"""

        response = self.generate(messages, options=options)
        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as error:
            raise LLMJSONDecodeError(response.content) from error
