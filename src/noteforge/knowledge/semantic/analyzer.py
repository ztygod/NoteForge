"""基于统一 LLM Client 的批量语义分析器。"""

import asyncio
from collections.abc import Callable
from typing import Protocol

from noteforge.exceptions import LLMJSONDecodeError, SemanticAnalysisError
from noteforge.knowledge.preprocessor import PreprocessedChunk
from noteforge.knowledge.prompts import SemanticAnalysisPrompt
from noteforge.knowledge.semantic.builder import build_semantic_chunk
from noteforge.knowledge.semantic.models import SemanticChunk
from noteforge.knowledge.semantic.validation import (
    parse_semantic_analysis_result,
    validate_semantic_analysis_result,
)
from noteforge.knowledge.tools import SEMANTIC_ANALYSIS_TOOL
from noteforge.llm import LLMClient, LLMRequestOptions
from noteforge.llm.models import LLMMessage


class SemanticAnalyzer(Protocol):
    """PreprocessedChunk 到 SemanticChunk 的异步接口。"""

    async def analyze(
        self,
        chunks: tuple[PreprocessedChunk, ...],
    ) -> tuple[SemanticChunk, ...]:
        """分析一批连续预处理块。"""


class LLMSemanticAnalyzer:
    """将批处理、模型调用、校验和确定性组装串联起来。"""

    def __init__(
        self,
        client: LLMClient,
        *,
        batch_size: int = 20,
        prompt: SemanticAnalysisPrompt | None = None,
        progress_handler: Callable[[int, int, bool], None] | None = None,
        activity_handler: Callable[[str, dict[str, object]], None] | None = None,
        max_attempts: int = 2,
        max_concurrency: int = 2,
    ) -> None:
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size <= 0
        ):
            raise ValueError("batch_size 必须是正整数")
        self._client = client
        self._batch_size = batch_size
        self._prompt = prompt or SemanticAnalysisPrompt()
        self._progress_handler = progress_handler
        self._activity_handler = activity_handler
        self._max_attempts = max_attempts
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int) or max_concurrency <= 0:
            raise ValueError("max_concurrency 必须是正整数")
        self._max_concurrency = max_concurrency

    def set_progress_handler(
        self,
        handler: Callable[[int, int, bool], None],
    ) -> None:
        """绑定批次进度处理器，参数依次为当前批次、总批次和是否完成。"""

        self._progress_handler = handler

    def set_activity_handler(
        self, handler: Callable[[str, dict[str, object]], None]
    ) -> None:
        self._activity_handler = handler

    def _activity(self, operation: str, **data: object) -> None:
        if self._activity_handler:
            self._activity_handler(operation, data)

    async def analyze(
        self,
        chunks: tuple[PreprocessedChunk, ...],
    ) -> tuple[SemanticChunk, ...]:
        if not isinstance(chunks, tuple) or not all(
            isinstance(chunk, PreprocessedChunk) for chunk in chunks
        ):
            raise TypeError("chunks 必须是 PreprocessedChunk 元组")
        total_batches = (len(chunks) + self._batch_size - 1) // self._batch_size
        if total_batches == 0:
            return ()
        semaphore = asyncio.Semaphore(self._max_concurrency)
        completion_lock = asyncio.Lock()
        completed_batches = 0
        if self._progress_handler:
            self._progress_handler(1, total_batches, False)

        async def process_batch(
            batch_number: int, start: int
        ) -> tuple[SemanticChunk, ...]:
            nonlocal completed_batches
            batch = chunks[start : start + self._batch_size]
            async with semaphore:
                result = await self._analyze_batch(
                    batch, batch_number=batch_number, total_batches=total_batches
                )
            async with completion_lock:
                completed_batches += 1
                if self._progress_handler:
                    self._progress_handler(completed_batches, total_batches, True)
            return result

        batches = await asyncio.gather(*(
            process_batch(batch_number, start)
            for batch_number, start in enumerate(
                range(0, len(chunks), self._batch_size), start=1
            )
        ))
        return tuple(item for batch in batches for item in batch)

    async def _analyze_batch(
        self,
        chunks: tuple[PreprocessedChunk, ...],
        *,
        batch_number: int = 1,
        total_batches: int = 1,
    ) -> tuple[SemanticChunk, ...]:
        """分析单批输入；批次策略可独立替换为 token 预算策略。"""

        if not chunks:
            return ()
        messages = list(self._prompt.build_for_chunks(chunks))
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            self._activity("requesting_model", batch_current=batch_number, batch_total=total_batches, attempt=attempt, max_attempts=self._max_attempts)
            try:
                response = await self._client.call_tool(
                    messages, tool=SEMANTIC_ANALYSIS_TOOL,
                    options=LLMRequestOptions(temperature=0),
                )
                self._activity("tool_submitted", batch_current=batch_number, batch_total=total_batches, tool_name=response.tool_call.name, attempt=attempt)
                self._activity("validating_response", batch_current=batch_number, batch_total=total_batches, attempt=attempt)
                result = parse_semantic_analysis_result(dict(response.tool_call.arguments))
                validate_semantic_analysis_result(result, len(chunks))
                return tuple(build_semantic_chunk(chunks, proposal) for proposal in result.semantic_chunks)
            except (LLMJSONDecodeError, SemanticAnalysisError) as error:
                last_error = error
                if attempt >= self._max_attempts:
                    break
                self._activity("retrying_validation", batch_current=batch_number, batch_total=total_batches, attempt=attempt + 1, max_attempts=self._max_attempts, reason=str(error))
                messages.append(LLMMessage(
                    "user",
                    "上一次提交未通过验证：\n"
                    f"{error}\n请调用 {SEMANTIC_ANALYSIS_TOOL.name} 重新提交完整修正结果。",
                ))
        raise SemanticAnalysisError(
            f"Semantic analysis failed after {self._max_attempts} attempts: {last_error}"
        ) from last_error
