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
    LLMTool,
    LLMToolCall,
    LLMToolResponse,
)


class LLMClient(ABC):
    """所有模型供应商必须实现的统一同步接口。"""

    @abstractmethod
    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> LLMResponse:
        """生成文本响应。"""

    async def generate_json(
        self,
        messages: Sequence[LLMMessage],
        *,
        options: LLMRequestOptions | None = None,
    ) -> JSONValue:
        """生成响应并将内容解析为 JSON。"""

        response = await self.generate(messages, options=options)
        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as error:
            raise LLMJSONDecodeError(response.content) from error

    async def call_tool(
        self,
        messages: Sequence[LLMMessage],
        *,
        tool: LLMTool,
        options: LLMRequestOptions | None = None,
    ) -> LLMToolResponse:
        """调用一个固定工具；旧 Provider 默认退回 JSON 文本生成。"""

        response = await self.generate(messages, options=options)
        try:
            arguments = json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as error:
            raise LLMJSONDecodeError(response.content) from error
        if not isinstance(arguments, dict):
            raise LLMJSONDecodeError(response.content)
        return LLMToolResponse(
            tool_call=LLMToolCall(tool.name, arguments),
            model=response.model,
            usage=response.usage,
            finish_reason=response.finish_reason,
            request_id=response.request_id,
        )

    async def aclose(self) -> None:
        """释放底层异步连接；无状态测试 Client 可沿用默认实现。"""
