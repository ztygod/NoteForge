"""基于统一 LLM Client 的批量知识点提取器。"""

import asyncio
from collections.abc import Callable
from typing import Protocol

from noteforge.exceptions import (
    KnowledgeExtractionError,
    LLMJSONDecodeError,
)
from noteforge.knowledge.extraction.builder import build_knowledge_point
from noteforge.knowledge.extraction.models import KnowledgePoint
from noteforge.knowledge.extraction.validation import (
    parse_knowledge_extraction_result,
    validate_knowledge_proposals,
)
from noteforge.knowledge.prompts import KnowledgeExtractionPrompt
from noteforge.knowledge.semantic.models import SemanticChunk
from noteforge.knowledge.tools import KNOWLEDGE_POINTS_TOOL
from noteforge.llm import LLMClient, LLMRequestOptions
from noteforge.llm.models import LLMMessage


class KnowledgeExtractor(Protocol):
    """从语义块中提取知识点。"""

    async def extract(
        self,
        chunks: tuple[SemanticChunk, ...],
    ) -> tuple[KnowledgePoint, ...]:
        """提取一批连续语义块中的知识点。"""


class LLMKnowledgeExtractor:
    """调用大语言模型提取知识点，并由程序恢复来源映射。"""

    def __init__(
        self,
        client: LLMClient,
        *,
        batch_size: int = 20,
        prompt: KnowledgeExtractionPrompt | None = None,
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
        self._prompt = prompt or KnowledgeExtractionPrompt()
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

    async def extract(
        self,
        chunks: tuple[SemanticChunk, ...],
    ) -> tuple[KnowledgePoint, ...]:
        if not isinstance(chunks, tuple) or not all(
            isinstance(chunk, SemanticChunk) for chunk in chunks
        ):
            raise TypeError("chunks 必须是 SemanticChunk 元组")

        total_batches = (len(chunks) + self._batch_size - 1) // self._batch_size
        if total_batches == 0:
            return ()
        semaphore = asyncio.Semaphore(self._max_concurrency)
        completion_lock = asyncio.Lock()
        completed_batches = 0
        if self._progress_handler:
            self._progress_handler(1, total_batches, False)

        async def process_batch(
            batch_number: int, start_index: int
        ) -> tuple[KnowledgePoint, ...]:
            nonlocal completed_batches
            batch = chunks[start_index : start_index + self._batch_size]
            async with semaphore:
                result = await self._extract_batch(
                    batch,
                    start_index=start_index,
                    all_chunks=chunks,
                    batch_number=batch_number,
                    total_batches=total_batches,
                )
            async with completion_lock:
                completed_batches += 1
                if self._progress_handler:
                    self._progress_handler(completed_batches, total_batches, True)
            return result

        batches = await asyncio.gather(*(
            process_batch(batch_number, start_index)
            for batch_number, start_index in enumerate(
                range(0, len(chunks), self._batch_size), start=1
            )
        ))
        return tuple(item for batch in batches for item in batch)

    async def _extract_batch(
        self,
        chunks: tuple[SemanticChunk, ...],
        *,
        start_index: int = 0,
        all_chunks: tuple[SemanticChunk, ...] | None = None,
        batch_number: int = 1,
        total_batches: int = 1,
    ) -> tuple[KnowledgePoint, ...]:
        """提取单批知识点。

        当前知识点只能引用同一批次内的语义块；跨批次合并留给后续的
        overlap window 或二次归并阶段。
        """

        if not chunks:
            return ()
        source_chunks = all_chunks if all_chunks is not None else chunks
        messages = list(self._prompt.build_for_chunks(chunks, start_index=start_index))
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            self._activity("requesting_model", batch_current=batch_number, batch_total=total_batches, attempt=attempt, max_attempts=self._max_attempts)
            try:
                response = await self._client.call_tool(
                    messages, tool=KNOWLEDGE_POINTS_TOOL,
                    options=LLMRequestOptions(temperature=0),
                )
                self._activity("tool_submitted", batch_current=batch_number, batch_total=total_batches, tool_name=response.tool_call.name, attempt=attempt)
                self._activity("validating_response", batch_current=batch_number, batch_total=total_batches, attempt=attempt)
                result = parse_knowledge_extraction_result(dict(response.tool_call.arguments))
                validate_knowledge_proposals(result.knowledge_points, len(source_chunks))
                batch_end = start_index + len(chunks)
                for position, proposal in enumerate(result.knowledge_points):
                    if any(index < start_index or index >= batch_end for index in proposal.source_indexes):
                        raise KnowledgeExtractionError(
                            f"Knowledge point {position} references source index outside the current batch"
                        )
                break
            except (LLMJSONDecodeError, KnowledgeExtractionError) as error:
                last_error = error
                if attempt >= self._max_attempts:
                    raise KnowledgeExtractionError(
                        f"Knowledge extraction failed after {self._max_attempts} attempts: {error}"
                    ) from error
                self._activity("retrying_validation", batch_current=batch_number, batch_total=total_batches, attempt=attempt + 1, max_attempts=self._max_attempts, reason=str(error))
                messages.append(LLMMessage(
                    "user",
                    "上一次提交未通过验证：\n"
                    f"{error}\n请调用 {KNOWLEDGE_POINTS_TOOL.name} 重新提交完整修正结果。",
                ))
            except Exception as error:
                raise KnowledgeExtractionError(f"Knowledge extraction model request failed: {error}") from error
        else:
            raise KnowledgeExtractionError(str(last_error)) from last_error

        # Python 的排序是稳定的，同一首索引保持模型返回顺序。
        ordered_proposals = sorted(
            result.knowledge_points,
            key=lambda proposal: proposal.source_indexes[0],
        )
        return tuple(
            build_knowledge_point(source_chunks, proposal)
            for proposal in ordered_proposals
        )
